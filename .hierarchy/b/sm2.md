# SM-2 scheduler — final rules (agent b, contract v1, brief rev 1)

Code: `src/dunzo/scheduler/`. Registry name `sm2` (`DEFAULT_SCHEDULER`). Pure; stdlib only.

## State (JSON-serializable dict, opaque to consumers)
`{"phase": "learning"|"review"|"relearning", "ease": float, "interval_days": int, "reps": int, "lapses": int}`
`None` = first review (treated as `learning`, ease 2.5, interval 0, reps 0, lapses 0). Input is never mutated.
A malformed state raises `SchedulerError`.

## Quality and ease
Grade 1,2,3,4 (Again, Hard, Good, Easy) -> quality q = 1,3,4,5.
Every non-lapse review: `ease = round(max(1.3, ease + 0.1 - (5-q)*(0.08 + (5-q)*0.02)), 4)`
(Good: no change, Hard: -0.14, Easy: +0.10). Ease is rounded to 4 decimals so stored values stay clean.

## Transitions
| From | Grade | Result |
|---|---|---|
| none / learning | Again | stay `learning`, state unchanged (first review: ease 2.5, reps 0), due = now + again_delay |
| none / learning | Hard, Good | `review`, reps+1 (so 1), interval 1, ease formula |
| none / learning | Easy | `review`, reps+1, interval 4, ease formula |
| relearning | Again | stay `relearning`, state unchanged (no extra lapse), due = now + again_delay |
| relearning | Hard/Good/Easy | `review`, keep reduced `interval_days` and `reps`, ease formula (no Easy bonus) |
| review | Again (lapse) | lapses+1, ease = max(1.3, ease-0.2), interval = max(1, interval//2), reps unchanged, `relearning`, due = now + again_delay |
| review | Hard/Good/Easy | reps+1, ease formula (new ease used below), interval below |

Review interval (`prev` = old interval, `reps` = new count, `ease` = new ease):
- reps 1 -> 1 day; reps 2 -> 6 days (any passing grade)
- reps >= 3: Good `round(prev*ease)`, Hard `max(prev+1, round(prev*1.2))`, Easy `round(prev*ease*1.3)`
- then `interval = min(36500, max(prev+1, raw))` (strictly greater, cap wins at 36500).
`round` is half-up (`floor(x+0.5)`), not Python's banker's rounding.

## Due times
- Again / lapse: exactly `now + again_delay`, aware UTC.
- Interval >= 1 day: `study_day_start(study_day(now, rollover, tz) + interval_days, rollover, tz)`.

## Study days
- `study_day(now, rollover, tz)`: local date of `now` in `tz`; the previous date if the local wall time is before `rollover` (03:59 with 04:00 rollover = previous day). Wall-clock based, so DST days are 23 or 25 hours long.
- `study_day_start(day, rollover, tz)`: aware UTC instant the day begins. If the rollover time falls in a DST gap, the first instant at/after it; if it occurs twice, the first occurrence. Always `study_day(study_day_start(d)) == d` and one microsecond earlier is `d-1`.

## Errors (`SchedulerError`, a `ValueError`)
Grade not an int in 1..4 (bool, float, str rejected); naive `now`; unknown scheduler name; malformed state; due date beyond year 9999.

## Tests
`src/dunzo/scheduler/tests/`: `uv run pytest src/dunzo/scheduler` (78 tests, no I/O).
