"""SM-2 scheduler with relearning steps (private). Rules are documented in .hierarchy/b/sm2.md."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from ._base import (
    AGAIN,
    EASY,
    GOOD,
    HARD,
    SchedulerConfig,
    SchedulerError,
    ScheduleResult,
    require_aware,
)
from ._days import study_day, study_day_start

LEARNING = "learning"
REVIEW = "review"
RELEARNING = "relearning"
_PHASES = (LEARNING, REVIEW, RELEARNING)

INITIAL_EASE = 2.5
MIN_EASE = 1.3
LAPSE_EASE_PENALTY = 0.2
MAX_INTERVAL_DAYS = 36500
_QUALITY = {AGAIN: 1, HARD: 3, GOOD: 4, EASY: 5}


def _round(x: float) -> int:
    """Round half up (Python's round() is banker's rounding)."""
    return math.floor(x + 0.5)


def _next_ease(ease: float, quality: int) -> float:
    d = 5 - quality
    return round(max(MIN_EASE, ease + 0.1 - d * (0.08 + d * 0.02)), 4)


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _parse_state(state: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise SchedulerError("sm2 state must be a dict or None")
    try:
        phase, ease = state["phase"], state["ease"]
        interval, reps, lapses = state["interval_days"], state["reps"], state["lapses"]
    except KeyError as exc:
        raise SchedulerError(f"sm2 state is missing key {exc.args[0]!r}") from None
    if phase not in _PHASES:
        raise SchedulerError("sm2 state has an unknown phase")
    if isinstance(ease, bool) or not isinstance(ease, (int, float)) or not math.isfinite(ease):
        raise SchedulerError("sm2 state has an invalid ease")
    if ease < MIN_EASE - 1e-9:
        raise SchedulerError("sm2 state has an ease below the minimum")
    for key, value in (("interval_days", interval), ("reps", reps), ("lapses", lapses)):
        if not _is_int(value) or value < 0:
            raise SchedulerError(f"sm2 state has an invalid {key}")
    return {
        "phase": phase,
        "ease": float(ease),
        "interval_days": interval,
        "reps": reps,
        "lapses": lapses,
    }


def _review_interval(prev: int, reps: int, grade: int, ease: float) -> int:
    """Interval for a successful review; ``reps`` is the new rep count, ``ease`` the new ease."""
    if reps <= 1:
        raw = 1
    elif reps == 2:
        raw = 6
    elif grade == HARD:
        raw = max(prev + 1, _round(prev * 1.2))
    elif grade == GOOD:
        raw = _round(prev * ease)
    else:  # EASY
        raw = _round(prev * ease * 1.3)
    return min(MAX_INTERVAL_DAYS, max(prev + 1, raw))


class Sm2Scheduler:
    name: str = "sm2"

    def schedule(
        self,
        state: dict[str, Any] | None,
        grade: int,
        now: datetime,
        config: SchedulerConfig,
    ) -> ScheduleResult:
        if not _is_int(grade) or grade not in _QUALITY:
            raise SchedulerError("grade must be an int in 1..4")
        require_aware(now)

        if state is None:
            cur = {"phase": LEARNING, "ease": INITIAL_EASE, "interval_days": 0,
                   "reps": 0, "lapses": 0}
        else:
            cur = _parse_state(state)

        now_utc = now.astimezone(UTC)
        phase, ease = cur["phase"], cur["ease"]
        interval, reps, lapses = cur["interval_days"], cur["reps"], cur["lapses"]
        quality = _QUALITY[grade]

        if phase in (LEARNING, RELEARNING):
            if grade == AGAIN:
                return self._short(phase, ease, interval, reps, lapses, now_utc, config)
            ease = _next_ease(ease, quality)
            if phase == LEARNING:
                interval = 4 if grade == EASY else 1
                reps += 1
            # relearning: keep the already-reduced interval and the rep count
            return self._long(ease, interval, reps, lapses, now_utc, config)

        # review phase
        if grade == AGAIN:
            return self._short(
                RELEARNING,
                max(MIN_EASE, round(ease - LAPSE_EASE_PENALTY, 4)),
                max(1, interval // 2),
                reps,
                lapses + 1,
                now_utc,
                config,
            )
        ease = _next_ease(ease, quality)
        reps += 1
        interval = _review_interval(interval, reps, grade, ease)
        return self._long(ease, interval, reps, lapses, now_utc, config)

    @staticmethod
    def _make(phase: str, ease: float, interval: int, reps: int, lapses: int) -> dict[str, Any]:
        return {"phase": phase, "ease": ease, "interval_days": interval,
                "reps": reps, "lapses": lapses}

    def _short(self, phase, ease, interval, reps, lapses, now_utc, config) -> ScheduleResult:
        return ScheduleResult(
            state=self._make(phase, ease, interval, reps, lapses),
            due=now_utc + config.again_delay,
        )

    def _long(self, ease, interval, reps, lapses, now_utc, config) -> ScheduleResult:
        try:
            day = study_day(now_utc, config.day_rollover, config.tz) + timedelta(days=interval)
            due = study_day_start(day, config.day_rollover, config.tz)
        except OverflowError:
            raise SchedulerError("due date is out of the supported range") from None
        return ScheduleResult(state=self._make(REVIEW, ease, interval, reps, lapses), due=due)
