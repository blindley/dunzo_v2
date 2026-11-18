"""SQLite connection, nested transactions and per-owner migrations."""

from __future__ import annotations

import logging
import re
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .clock import new_id

log = logging.getLogger("dunzo.core")

_COMMENTS_ONLY = re.compile(r"(?:\s|--[^\n]*(?:\n|$)|/\*.*?\*/)*", re.DOTALL)


def connect(path: Path) -> sqlite3.Connection:
    """Open a connection with explicit transactions, FKs on, WAL, 5 s busy timeout."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """Outermost: BEGIN IMMEDIATE..COMMIT; nested: SAVEPOINT..RELEASE. Rolls back on error."""
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield
            conn.execute("COMMIT")
        except BaseException:
            _rollback(conn)
            raise
    else:
        name = "dz_" + new_id().replace("-", "")
        conn.execute(f"SAVEPOINT {name}")
        try:
            yield
            conn.execute(f"RELEASE {name}")
        except BaseException:
            _rollback_to(conn, name)
            raise


def _rollback(conn: sqlite3.Connection) -> None:
    # SQLite may already have rolled back on its own (e.g. disk full); then there is nothing to do.
    if conn.in_transaction:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            log.warning("rollback failed", exc_info=True)


def _rollback_to(conn: sqlite3.Connection, name: str) -> None:
    if conn.in_transaction:
        try:
            conn.execute(f"ROLLBACK TO {name}")
            conn.execute(f"RELEASE {name}")
        except sqlite3.Error:
            log.warning("savepoint rollback failed", exc_info=True)


@dataclass(frozen=True)
class Migration:
    version: int
    sql: str


@dataclass(frozen=True)
class MigrationSet:
    owner: str
    migrations: tuple[Migration, ...]


def split_statements(script: str) -> list[str]:
    """Split an SQL script into single statements using ``sqlite3.complete_statement``.

    Cuts at each ``;`` where the text since the last cut is a complete statement, so semicolons
    inside strings, comments and trigger bodies do not split. Comment-only or blank leftovers
    are dropped; a final statement lacking ``;`` is kept.
    """
    statements: list[str] = []
    start = 0
    pos = script.find(";")
    while pos != -1:
        candidate = script[start : pos + 1]
        if sqlite3.complete_statement(candidate):
            statements.append(candidate.strip())
            start = pos + 1
        pos = script.find(";", pos + 1)
    rest = script[start:].strip()
    if rest and not _COMMENTS_ONLY.fullmatch(rest):
        statements.append(rest)  # a final statement lacking ';'
    return statements


def _validate(sets: Sequence[MigrationSet]) -> None:
    owners: set[str] = set()
    for s in sets:
        if s.owner in owners:
            raise ValueError(f"duplicate migration owner {s.owner!r}")
        owners.add(s.owner)
        versions = [m.version for m in s.migrations]
        if versions != list(range(1, len(versions) + 1)):
            raise ValueError(
                f"migrations for {s.owner!r} must be versions 1..n consecutive in order, "
                f"got {versions}"
            )


def _recorded_version(conn: sqlite3.Connection, owner: str) -> int:
    row = conn.execute("SELECT version FROM schema_migration WHERE owner = ?", (owner,)).fetchone()
    return int(row["version"]) if row else 0


def migrate(conn: sqlite3.Connection, sets: Sequence[MigrationSet]) -> None:
    """Apply each owner's pending migrations, each atomically with its version bump."""
    _validate(sets)  # reject malformed sets before touching the database
    with transaction(conn):
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migration("
            "owner TEXT PRIMARY KEY, version INTEGER NOT NULL)"
        )
    for s in sets:
        for m in s.migrations:
            with transaction(conn):
                if m.version <= _recorded_version(conn, s.owner):
                    continue
                try:
                    for stmt in split_statements(m.sql):
                        conn.execute(stmt)
                except sqlite3.Error as exc:
                    exc.add_note(f"migration {s.owner!r} version {m.version} failed")
                    log.error("migration %s v%d failed: %s", s.owner, m.version, exc)
                    raise
                conn.execute(
                    "INSERT INTO schema_migration(owner, version) VALUES (?, ?) "
                    "ON CONFLICT(owner) DO UPDATE SET version = excluded.version",
                    (s.owner, m.version),
                )
                log.info("applied migration %s v%d", s.owner, m.version)
