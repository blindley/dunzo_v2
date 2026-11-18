"""Ids and time helpers. Python side: aware UTC datetimes; DB side: REAL epoch seconds."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime


def new_id() -> str:
    """A fresh uuid4, lowercase and hyphenated."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Current time as an aware UTC datetime (route layers only; logic takes ``now``)."""
    return datetime.now(UTC)


def to_epoch(dt: datetime) -> float:
    """Epoch seconds for an aware datetime; ``ValueError`` if naive."""
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("naive datetime not allowed; use an aware datetime")
    return dt.timestamp()


def from_epoch(x: float) -> datetime:
    """Aware UTC datetime for epoch seconds."""
    return datetime.fromtimestamp(x, tz=UTC)
