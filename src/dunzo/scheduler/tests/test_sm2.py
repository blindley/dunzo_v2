import copy
import json
import random
from datetime import UTC, datetime, time, timedelta, timezone

import pytest

from dunzo.scheduler import (
    AGAIN,
    EASY,
    GOOD,
    HARD,
    SchedulerConfig,
    SchedulerError,
    ScheduleResult,
    get_scheduler,
)

NOW = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
CFG = SchedulerConfig()
S = get_scheduler("sm2")


def review(interval, ease=2.5, reps=5, lapses=0):
    return {"phase": "review", "ease": ease, "interval_days": interval, "reps": reps,
            "lapses": lapses}


def run(grades, now=NOW, cfg=CFG, state=None):
    for g in grades:
        r = S.schedule(state, g, now, cfg)
        state, now = r.state, r.due
    return state, now


def test_first_review_again():
    r = S.schedule(None, AGAIN, NOW, CFG)
    assert r.state == {"phase": "learning", "ease": 2.5, "interval_days": 0, "reps": 0,
                       "lapses": 0}
    assert r.due == NOW + timedelta(minutes=10)


@pytest.mark.parametrize(
    "grade,ease,interval",
    [(HARD, 2.36, 1), (GOOD, 2.5, 1), (EASY, 2.6, 4)],
)
def test_first_review_graduates(grade, ease, interval):
    r = S.schedule(None, grade, NOW, CFG)
    assert r.state == {"phase": "review", "ease": ease, "interval_days": interval, "reps": 1,
                       "lapses": 0}
    assert r.due == datetime(2026, 1, 10 + interval, 4, 0, tzinfo=UTC)


def test_good_sequence():
    intervals = []
    state = None
    now = NOW
    for _ in range(6):
        r = S.schedule(state, GOOD, now, CFG)
        state, now = r.state, r.due
        intervals.append(state["interval_days"])
    assert intervals == [1, 6, 15, 38, 95, 238]
    assert state["ease"] == 2.5 and state["reps"] == 6


def test_rounding_is_half_up():
    assert S.schedule(review(5), GOOD, NOW, CFG).state["interval_days"] == 13  # 12.5


def test_hard_and_easy_intervals():
    assert S.schedule(review(10), HARD, NOW, CFG).state["interval_days"] == 12
    r = S.schedule(review(10), EASY, NOW, CFG)
    assert r.state["ease"] == 2.6 and r.state["interval_days"] == 34  # 10*2.6*1.3 = 33.8


def test_hard_always_grows_by_at_least_one():
    r = S.schedule(review(2, ease=1.3), HARD, NOW, CFG)
    assert r.state["interval_days"] == 3 and r.state["ease"] == 1.3


def test_good_strictly_greater_even_at_min_ease():
    assert S.schedule(review(1, ease=1.3, reps=3), GOOD, NOW, CFG).state["interval_days"] == 2


def test_reps_two_gives_six_days_for_any_passing_grade():
    for g in (HARD, GOOD, EASY):
        st = S.schedule(review(1, reps=1), g, NOW, CFG).state
        assert st["interval_days"] == 6 and st["reps"] == 2


def test_easy_first_then_second_review():
    st = S.schedule(None, EASY, NOW, CFG).state
    assert S.schedule(st, GOOD, NOW, CFG).state["interval_days"] == 6


def test_interval_cap():
    assert S.schedule(review(36000), EASY, NOW, CFG).state["interval_days"] == 36500
    assert S.schedule(review(36500), GOOD, NOW, CFG).state["interval_days"] == 36500


def test_ease_floor():
    st = review(10, ease=1.3)
    for _ in range(3):
        st = S.schedule(st, HARD, NOW, CFG).state
        assert st["ease"] == 1.3


def test_lapse_and_relearning():
    r = S.schedule(review(10, reps=4), AGAIN, NOW, CFG)
    assert r.state == {"phase": "relearning", "ease": 2.3, "interval_days": 5, "reps": 4,
                       "lapses": 1}
    assert r.due == NOW + timedelta(minutes=10)
    r2 = S.schedule(r.state, AGAIN, r.due, CFG)  # still relearning, no second lapse
    assert r2.state == r.state and r2.due == r.due + timedelta(minutes=10)
    r3 = S.schedule(r2.state, GOOD, r2.due, CFG)
    assert r3.state == {"phase": "review", "ease": 2.3, "interval_days": 5, "reps": 4,
                        "lapses": 1}
    assert r3.due == datetime(2026, 1, 15, 4, 0, tzinfo=UTC)


def test_lapse_floors():
    st = S.schedule(review(1, ease=1.4), AGAIN, NOW, CFG).state
    assert st["interval_days"] == 1 and st["ease"] == 1.3


def test_relearning_graduation_ignores_easy_bonus_interval():
    st = S.schedule(review(20), AGAIN, NOW, CFG).state
    assert S.schedule(st, EASY, NOW, CFG).state["interval_days"] == 10


def test_learning_again_repeats_then_graduates():
    st, due = run([AGAIN, AGAIN])
    assert st["phase"] == "learning"
    st, _ = run([GOOD], now=due, state=st)
    assert st["phase"] == "review" and st["reps"] == 1 and st["interval_days"] == 1


def test_again_due_is_now_plus_delay_with_custom_config():
    cfg = SchedulerConfig(again_delay=timedelta(minutes=3))
    now = datetime(2026, 1, 10, 23, 0, tzinfo=timezone(timedelta(hours=5)))
    r = S.schedule(review(10), AGAIN, now, cfg)
    assert r.due == now + timedelta(minutes=3)
    assert r.due.utcoffset() == timedelta(0)


def test_due_is_aware_utc_and_study_day_based():
    cfg = SchedulerConfig(day_rollover=time(4, 0), tz=timezone(timedelta(hours=-5)))
    now = datetime(2026, 1, 10, 8, 30, tzinfo=UTC)  # 03:30 local -> study day Jan 9
    r = S.schedule(review(6, reps=2), GOOD, now, cfg)  # 15 days
    assert r.state["interval_days"] == 15
    assert r.due == datetime(2026, 1, 24, 9, 0, tzinfo=UTC)  # Jan 24 04:00 at UTC-5
    assert r.due.tzinfo is UTC


def test_determinism_and_no_input_mutation():
    st = review(10)
    before = copy.deepcopy(st)
    a = S.schedule(st, GOOD, NOW, CFG)
    b = S.schedule(st, GOOD, NOW, CFG)
    assert a == b and st == before and a.state is not st
    assert isinstance(a, ScheduleResult)


def test_json_round_trip():
    state, now = None, NOW
    rng = random.Random(7)
    for _ in range(40):
        g = rng.choice([1, 2, 3, 4])
        direct = S.schedule(state, g, now, CFG)
        via_json = S.schedule(None if state is None else json.loads(json.dumps(state)), g, now, CFG)
        assert direct == via_json
        json.dumps(direct.state)
        state, now = direct.state, direct.due


def test_random_walk_invariants():
    rng = random.Random(1234)
    state, now = None, NOW
    for _ in range(60):
        prev = state
        r = S.schedule(state, rng.choice([1, 2, 3, 4]), now, CFG)
        state = r.state
        assert state["ease"] >= 1.3
        assert r.due > now
        if prev and prev["phase"] == "review" and state["phase"] == "review":
            assert state["interval_days"] > prev["interval_days"] or state["interval_days"] == 36500
        now = r.due


@pytest.mark.parametrize("grade", [0, 5, -1, "3", 3.0, True, None])
def test_invalid_grade(grade):
    with pytest.raises(SchedulerError):
        S.schedule(None, grade, NOW, CFG)


def test_naive_now():
    with pytest.raises(SchedulerError):
        S.schedule(None, GOOD, datetime(2026, 1, 10, 10, 0), CFG)


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"phase": "nope", "ease": 2.5, "interval_days": 1, "reps": 1, "lapses": 0},
        {"phase": "review", "ease": 2.5, "interval_days": 1.5, "reps": 1, "lapses": 0},
        {"phase": "review", "ease": "x", "interval_days": 1, "reps": 1, "lapses": 0},
        {"phase": "review", "ease": 2.5, "interval_days": -1, "reps": 1, "lapses": 0},
        "review",
    ],
)
def test_invalid_state(bad):
    with pytest.raises(SchedulerError):
        S.schedule(bad, GOOD, NOW, CFG)


def test_due_overflow_is_a_scheduler_error():
    now = datetime(9999, 12, 31, 12, 0, tzinfo=UTC)
    with pytest.raises(SchedulerError):
        S.schedule(review(100), GOOD, now, CFG)
