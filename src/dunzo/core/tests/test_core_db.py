"""connect and transaction."""

import sqlite3

import pytest

from dunzo.core import connect, transaction


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "sub" / "t.db")
    c.execute("CREATE TABLE t(x INTEGER)")
    yield c
    c.close()


def rows(c):
    return [r["x"] for r in c.execute("SELECT x FROM t ORDER BY x")]


def test_connect_settings(tmp_path):
    c = connect(tmp_path / "a" / "b" / "t.db")  # parent dirs created
    try:
        assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert c.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert c.isolation_level is None
        assert not c.in_transaction
        c.execute("CREATE TABLE r(a)")
        c.execute("INSERT INTO r VALUES (1)")
        assert c.execute("SELECT a FROM r").fetchone()["a"] == 1  # Row factory
    finally:
        c.close()


def test_foreign_keys_enforced(conn):
    conn.execute("CREATE TABLE p(id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE c(pid INTEGER REFERENCES p(id))")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO c VALUES (99)")


def test_cross_thread_use_allowed(conn):
    import threading

    out = []
    th = threading.Thread(target=lambda: out.append(conn.execute("SELECT 1").fetchone()[0]))
    th.start()
    th.join()
    assert out == [1]


def test_commit(conn, tmp_path):
    other = connect(tmp_path / "sub" / "t.db")
    with transaction(conn):
        conn.execute("INSERT INTO t VALUES (1)")
        assert rows(other) == []  # not visible before commit
    assert rows(other) == [1] and not conn.in_transaction
    other.close()


def test_rollback_and_reraise(conn):
    with pytest.raises(RuntimeError, match="x"):
        with transaction(conn):
            conn.execute("INSERT INTO t VALUES (1)")
            raise RuntimeError("x")
    assert rows(conn) == [] and not conn.in_transaction


def test_outermost_is_immediate(conn, tmp_path):
    other = connect(tmp_path / "sub" / "t.db")
    other.execute("PRAGMA busy_timeout = 50")
    with transaction(conn):
        with pytest.raises(sqlite3.OperationalError):  # writer lock taken at BEGIN
            other.execute("BEGIN IMMEDIATE")
    other.close()


def test_nested_inner_rollback_outer_commits(conn):
    with transaction(conn):
        conn.execute("INSERT INTO t VALUES (1)")
        with pytest.raises(ValueError):
            with transaction(conn):
                conn.execute("INSERT INTO t VALUES (2)")
                raise ValueError
        conn.execute("INSERT INTO t VALUES (3)")
    assert rows(conn) == [1, 3] and not conn.in_transaction


def test_exception_through_all_levels_rolls_back_everything(conn):
    with pytest.raises(KeyError):
        with transaction(conn):
            conn.execute("INSERT INTO t VALUES (1)")
            with transaction(conn):
                conn.execute("INSERT INTO t VALUES (2)")
                with transaction(conn):
                    conn.execute("INSERT INTO t VALUES (3)")
                    raise KeyError
    assert rows(conn) == [] and not conn.in_transaction


def test_inner_success_then_outer_failure_rolls_back_inner(conn):
    with pytest.raises(KeyError):
        with transaction(conn):
            with transaction(conn):
                conn.execute("INSERT INTO t VALUES (1)")
            raise KeyError
    assert rows(conn) == []


def test_same_level_siblings_independent(conn):
    with transaction(conn):
        for i in range(3):
            try:
                with transaction(conn):
                    conn.execute("INSERT INTO t VALUES (?)", (i,))
                    if i == 1:
                        raise ValueError
            except ValueError:
                pass
    assert rows(conn) == [0, 2]


def test_deep_nesting(conn):
    def go(n):
        with transaction(conn):
            conn.execute("INSERT INTO t VALUES (?)", (n,))
            if n < 25:
                go(n + 1)

    go(0)
    assert rows(conn) == list(range(26))


def test_usable_after_failure_and_inside_caller_begin(conn):
    with pytest.raises(ValueError):
        with transaction(conn):
            raise ValueError
    conn.execute("BEGIN")  # caller-managed outer transaction: ours becomes a savepoint
    with transaction(conn):
        conn.execute("INSERT INTO t VALUES (1)")
    assert conn.in_transaction
    conn.execute("ROLLBACK")
    assert rows(conn) == []


def test_constraint_error_in_inner_keeps_outer_usable(conn):
    conn.execute("CREATE TABLE u(k PRIMARY KEY)")
    with transaction(conn):
        conn.execute("INSERT INTO u VALUES (1)")
        with pytest.raises(sqlite3.IntegrityError):
            with transaction(conn):
                conn.execute("INSERT INTO u VALUES (2)")
                conn.execute("INSERT INTO u VALUES (1)")
        conn.execute("INSERT INTO u VALUES (3)")
    assert [r[0] for r in conn.execute("SELECT k FROM u ORDER BY k")] == [1, 3]
