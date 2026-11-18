"""Small web helpers: per-request connection and the exact sandbox headers."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import Request

from dunzo.config import get_settings

from .db import connect

SANDBOX_CSP: str = (
    "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; media-src 'self' data:; font-src 'self' data:; connect-src 'none'; "
    "form-action 'none'; base-uri 'none'; sandbox allow-scripts"
)

SANDBOX_HEADERS: dict[str, str] = {
    "Content-Security-Policy": SANDBOX_CSP,
    "X-Content-Type-Options": "nosniff",
    "Access-Control-Allow-Origin": "*",
    "Cross-Origin-Resource-Policy": "cross-origin",
    "Referrer-Policy": "no-referrer",
}


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request, closed afterwards."""
    conn = connect(get_settings().database_path)
    try:
        yield conn
    finally:
        conn.close()
