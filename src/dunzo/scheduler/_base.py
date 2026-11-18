"""Shared value types, constants and errors for the scheduler package (private)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta, tzinfo
from typing import Any, Protocol

AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4

DEFAULT_SCHEDULER = "sm2"


class SchedulerError(ValueError):
    """Invalid input to the scheduler (bad grade, naive datetime, unknown name, bad state)."""


@dataclass(frozen=True)
class SchedulerConfig:
    again_delay: timedelta = timedelta(minutes=10)
    day_rollover: time = time(4, 0)
    tz: tzinfo = UTC


@dataclass(frozen=True)
class ScheduleResult:
    state: dict[str, Any]  # JSON-serializable; opaque to everyone but the producing scheduler
    due: datetime  # aware UTC


class Scheduler(Protocol):
    name: str

    def schedule(
        self,
        state: dict[str, Any] | None,
        grade: int,
        now: datetime,
        config: SchedulerConfig,
    ) -> ScheduleResult:
        """Return the new state and due time. ``state`` None means the card's first review.

        Raises SchedulerError if ``grade`` is not in 1..4 or ``now`` is naive.
        """
        ...


def require_aware(value: datetime, what: str = "now") -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise SchedulerError(f"{what} must be a timezone-aware datetime")
