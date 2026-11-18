from datetime import UTC, date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from dunzo.scheduler import SchedulerError, study_day, study_day_start

NY = ZoneInfo("America/New_York")
R4 = time(4, 0)


def test_boundary_at_rollover():
    assert study_day(datetime(2026, 1, 10, 3, 59, tzinfo=UTC), R4, UTC) == date(2026, 1, 9)
    assert study_day(datetime(2026, 1, 10, 4, 0, tzinfo=UTC), R4, UTC) == date(2026, 1, 10)
    assert study_day(datetime(2026, 1, 10, 0, 0, tzinfo=UTC), R4, UTC) == date(2026, 1, 9)
    assert study_day(datetime(2026, 1, 10, 23, 59, tzinfo=UTC), R4, UTC) == date(2026, 1, 10)


def test_midnight_rollover_is_calendar_date():
    assert study_day(datetime(2026, 1, 10, 0, 0, tzinfo=UTC), time(0, 0), UTC) == date(2026, 1, 10)


def test_uses_tz_not_input_offset():
    now = datetime(2026, 1, 10, 8, 30, tzinfo=UTC)  # 03:30 in New York
    assert study_day(now, R4, NY) == date(2026, 1, 9)
    same = now.astimezone(timezone(timedelta(hours=9)))
    assert study_day(same, R4, NY) == date(2026, 1, 9)


def test_naive_now_rejected():
    with pytest.raises(SchedulerError):
        study_day(datetime(2026, 1, 10, 4, 0), R4, UTC)


def test_start_basic():
    assert study_day_start(date(2026, 1, 10), R4, UTC) == datetime(2026, 1, 10, 4, tzinfo=UTC)
    assert study_day_start(date(2026, 1, 10), R4, NY) == datetime(2026, 1, 10, 9, tzinfo=UTC)
    assert study_day_start(date(2026, 1, 10), R4, NY).tzinfo is UTC


def test_dst_spring_forward_new_york():
    # 2026-03-08: clocks jump 02:00 -> 03:00 EST->EDT at 07:00Z.
    assert study_day(datetime(2026, 3, 8, 7, 59, tzinfo=UTC), R4, NY) == date(2026, 3, 7)  # 03:59
    assert study_day(datetime(2026, 3, 8, 8, 0, tzinfo=UTC), R4, NY) == date(2026, 3, 8)  # 04:00
    d7, d8 = (study_day_start(date(2026, 3, d), R4, NY) for d in (7, 8))
    assert d7 == datetime(2026, 3, 7, 9, tzinfo=UTC) and d8 == datetime(2026, 3, 8, 8, tzinfo=UTC)
    assert d8 - d7 == timedelta(hours=23)


def test_dst_fall_back_new_york():
    # 2026-11-01: clocks fall 02:00 EDT -> 01:00 EST at 06:00Z.
    assert study_day(datetime(2026, 11, 1, 8, 59, tzinfo=UTC), R4, NY) == date(2026, 10, 31)  # 03:59
    assert study_day(datetime(2026, 11, 1, 9, 0, tzinfo=UTC), R4, NY) == date(2026, 11, 1)  # 04:00
    d0, d1 = (study_day_start(date(2026, 11, d), R4, NY) for d in (0 + 1, 2))
    assert d0 == datetime(2026, 11, 1, 9, tzinfo=UTC) and d1 == datetime(2026, 11, 2, 9, tzinfo=UTC)
    oct31 = study_day_start(date(2026, 10, 31), R4, NY)
    assert oct31 == datetime(2026, 10, 31, 8, tzinfo=UTC)
    assert d0 - oct31 == timedelta(hours=25)  # the study day that contains the repeated hour


def test_rollover_inside_spring_gap():
    r = time(2, 30)  # does not exist on 2026-03-08 in New York
    start = study_day_start(date(2026, 3, 8), r, NY)
    assert start == datetime(2026, 3, 8, 7, 0, tzinfo=UTC)  # 03:00 EDT, first instant after gap
    assert study_day(start, r, NY) == date(2026, 3, 8)
    assert study_day(start - timedelta(microseconds=1), r, NY) == date(2026, 3, 7)


def test_rollover_inside_fall_overlap():
    r = time(1, 30)  # occurs twice on 2026-11-01
    start = study_day_start(date(2026, 11, 1), r, NY)
    assert start == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)  # first 01:30 (EDT)
    assert study_day(start - timedelta(microseconds=1), r, NY) == date(2026, 10, 31)
    assert study_day(datetime(2026, 11, 1, 6, 30, tzinfo=UTC), r, NY) == date(2026, 11, 1)


@pytest.mark.parametrize(
    "tzname",
    ["UTC", "America/New_York", "Europe/Berlin", "Asia/Kolkata", "Australia/Lord_Howe",
     "America/Havana", "Pacific/Auckland"],
)
@pytest.mark.parametrize("rollover", [time(0, 0), time(1, 30), time(2, 30), time(4, 0)])
def test_start_is_inverse_of_study_day(tzname, rollover):
    tz = ZoneInfo(tzname)
    prev = None
    day = date(2026, 1, 1)
    for _ in range(366):
        start = study_day_start(day, rollover, tz)
        assert start.tzinfo is UTC
        assert study_day(start, rollover, tz) == day
        assert study_day(start - timedelta(microseconds=1), rollover, tz) == day - timedelta(days=1)
        if prev is not None:
            assert start > prev
        prev, day = start, day + timedelta(days=1)
