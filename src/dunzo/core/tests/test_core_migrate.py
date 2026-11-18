"""migrate and script splitting."""

import sqlite3

import pytest

from dunzo.core import Migration, MigrationSet, connect, migrate
from dunzo.core.db import split_statements


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "m.db")
    yield c
    c.close()


def ms(owner, *sqls):
    return MigrationSet(owner, tuple(Migration(i, s) for i, s in enumerate(sqls, 1)))


def versions(c):
    return {r["owner"]: r["version"] for r in c.execute("SELECT * FROM schema_migration")}


def tables(c):
    q = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    return {r["name"] for r in c.execute(q)}


def test_apply_in_order_across_sets(conn):
    a = ms("a", "CREATE TABLE p(id INTEGER PRIMARY KEY);", "ALTER TABLE p ADD COLUMN n TEXT;")
    b = ms("b", "CREATE TABLE c(pid INTEGER REFERENCES p(id));")  # needs a's table first
    migrate(conn, [a, b])
    assert versions(conn) == {"a": 2, "b": 1}
    assert tables(conn) >= {"p", "c", "schema_migration"}


def test_set_order_is_respected(conn):
    a = ms("a", "CREATE TABLE p(id INTEGER PRIMARY KEY);")
    b = ms("b", "CREATE TABLE c(pid INTEGER REFERENCES p(id)); INSERT INTO p VALUES (1);")
    with pytest.raises(sqlite3.Error):
        migrate(conn, [b, a])  # b's INSERT needs p, which a has not created yet
    assert tables(conn) == {"schema_migration"}


def test_idempotent_and_incremental(conn):
    v1 = ms("a", "CREATE TABLE t(x);")
    migrate(conn, [v1])
    migrate(conn, [v1])
    assert versions(conn) == {"a": 1}
    v2 = ms("a", "CREATE TABLE t(x);", "CREATE TABLE t2(y);")
    migrate(conn, [v2])
    migrate(conn, [v2])
    assert versions(conn) == {"a": 2} and "t2" in tables(conn)


def test_gap_and_malformed_rejected_before_any_change(conn):
    good = ms("a", "CREATE TABLE t(x);")
    gap = MigrationSet("b", (Migration(1, "SELECT 1;"), Migration(3, "SELECT 2;")))
    with pytest.raises(ValueError):
        migrate(conn, [good, gap])
    assert tables(conn) == set()  # nothing applied, not even the good set
    for bad in (
        MigrationSet("c", (Migration(2, "SELECT 1;"),)),
        MigrationSet("c", (Migration(1, "SELECT 1;"), Migration(1, "SELECT 1;"))),
        MigrationSet("c", (Migration(2, "SELECT 1;"), Migration(1, "SELECT 1;"))),
    ):
        with pytest.raises(ValueError):
            migrate(conn, [bad])
    with pytest.raises(ValueError):
        migrate(conn, [good, good])  # duplicate owner


def test_failure_rolls_back_that_migration_only(conn):
    sets = [ms("a", "CREATE TABLE ok(x);", "CREATE TABLE half(x); INSERT INTO missing VALUES (1);")]
    with pytest.raises(sqlite3.OperationalError) as ei:
        migrate(conn, sets)
    assert any("version 2" in n for n in ei.value.__notes__)
    assert versions(conn) == {"a": 1}
    assert "ok" in tables(conn) and "half" not in tables(conn)
    assert not conn.in_transaction
    fixed = [ms("a", "CREATE TABLE ok(x);", "CREATE TABLE half(x);")]
    migrate(conn, fixed)  # resumes at version 2
    assert versions(conn) == {"a": 2} and "half" in tables(conn)


def test_failure_in_later_set_keeps_earlier_sets(conn):
    with pytest.raises(sqlite3.Error):
        migrate(conn, [ms("a", "CREATE TABLE t(x);"), ms("b", "NOT SQL;")])
    assert versions(conn) == {"a": 1}


def test_database_newer_than_code_is_noop(conn):
    migrate(conn, [ms("a", "CREATE TABLE t(x);", "CREATE TABLE t2(x);")])
    migrate(conn, [ms("a", "CREATE TABLE t(x);")])
    assert versions(conn) == {"a": 2}


def test_runs_inside_caller_transaction(conn):
    conn.execute("BEGIN")
    with pytest.raises(sqlite3.Error):
        migrate(conn, [ms("a", "CREATE TABLE t(x);", "BAD;")])
    conn.execute("ROLLBACK")
    assert tables(conn) == set()  # the caller's rollback undid everything, as it owns the txn


def test_empty_sets_ok(conn):
    migrate(conn, [])
    migrate(conn, [MigrationSet("a", ())])
    assert versions(conn) == {}


def test_split_statements_edge_cases():
    script = """
    -- a comment; with semicolon
    CREATE TABLE t(x TEXT DEFAULT 'a;b');  /* trailing; comment */ CREATE TABLE u(y);
    CREATE TRIGGER trg AFTER INSERT ON t BEGIN
        INSERT INTO u VALUES (1);
        INSERT INTO u VALUES (2);
    END;
    INSERT INTO t VALUES ('x;y')
    """
    parts = split_statements(script)
    assert len(parts) == 4
    assert parts[2].startswith("CREATE TRIGGER") and parts[2].endswith("END;")
    assert parts[3] == "INSERT INTO t VALUES ('x;y')"
    assert split_statements("") == [] and split_statements("  -- only comment\n") == []
    assert split_statements("/* c */") == []


def test_script_with_trigger_executes(conn):
    sql = """
    CREATE TABLE t(x); CREATE TABLE log(n);
    CREATE TRIGGER trg AFTER INSERT ON t BEGIN INSERT INTO log VALUES (new.x); END;
    INSERT INTO t VALUES (7);
    """
    migrate(conn, [ms("a", sql)])
    assert conn.execute("SELECT n FROM log").fetchone()["n"] == 7
