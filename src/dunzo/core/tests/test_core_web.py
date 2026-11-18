"""get_conn."""

import sqlite3
from types import SimpleNamespace

import pytest

from dunzo.core import get_conn


@pytest.fixture
def patched(tmp_path, monkeypatch):
    path = tmp_path / "data" / "dunzo.db"
    monkeypatch.setattr("dunzo.core.web.get_settings", lambda: SimpleNamespace(database_path=path))
    return path


def test_get_conn_yields_then_closes(patched):
    gen = get_conn(None)  # the request object is unused
    conn = next(gen)
    assert conn.execute("SELECT 1").fetchone()[0] == 1 and patched.exists()
    with pytest.raises(StopIteration):
        next(gen)
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_get_conn_closes_on_error(patched):
    gen = get_conn(None)
    conn = next(gen)
    with pytest.raises(RuntimeError):
        gen.throw(RuntimeError("handler failed"))
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_each_request_gets_its_own_connection(patched):
    g1, g2 = get_conn(None), get_conn(None)
    c1, c2 = next(g1), next(g2)
    assert c1 is not c2
    g1.close()
    g2.close()
