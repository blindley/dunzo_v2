"""Study-day arithmetic (private).

A study day runs from ``rollover`` on one calendar date to ``rollover`` on the next, measured in
the wall-clock time of ``tz``. Comparisons use wall-clock time, so across a DST change a study
day is 23 or 25 hours long rather than the clock drifting by an hour.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, tzinfo

from ._base import require_aware

_MICRO = timedelta(microseconds=1)


def _naive(rollover: time) -> time:
    return rollover.replace(tzinfo=None)


def study_day(now: datetime, rollover: time, tz: tzinfo) -> date:
    """Calendar date in ``tz`` of ``now - rollover`` (03:59 with rollover 04:00 is yesterday)."""
    require_aware(now)
    local = now.astimezone(tz)
    day = local.date()
    if local.time() < _naive(rollover):  # local.time() is naive wall-clock time
        day -= timedelta(days=1)
    return day


def study_day_start(day: date, rollover: time, tz: tzinfo) -> datetime:
    """Aware UTC instant at which study day ``day`` begins.

    If the rollover wall time does not exist that day (DST gap) the day begins at the first
    instant whose wall time is at or after it; if it occurs twice (DST overlap) the first
    occurrence is used. Either way ``study_day(study_day_start(d)) == d`` and one microsecond
    earlier is day ``d - 1``.
    """
    wall = datetime.combine(day, _naive(rollover))
    utc = wall.replace(tzinfo=tz).astimezone(UTC)
    back = utc.astimezone(tz).replace(tzinfo=None)
    if back == wall:
        return utc
    # DST gap: ``wall`` does not exist. The transition lies in (utc - gap, utc].
    gap = back - wall
    lo, hi = 0, (gap // _MICRO)  # microsecond offsets above ``utc - gap``; hi satisfies, lo not
    base = utc - gap
    while hi - lo > 1:
        mid = (lo + hi) // 2
        probe = base + mid * _MICRO
        if probe.astimezone(tz).replace(tzinfo=None) >= wall:
            hi = mid
        else:
            lo = mid
    return base + hi * _MICRO
