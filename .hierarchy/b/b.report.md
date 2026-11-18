# REPORT-b
Status: complete      Brief rev worked against: 1
Summary: `dunzo.scheduler` is built per §2/§4: Sm2Scheduler (learning, review and relearning), a registry (`sm2` default), `study_day` and `study_day_start` (DST-safe). Stdlib only, pure, deterministic. Rules are in `.hierarchy/b/sm2.md`. 78 tests pass and ruff is clean.
State dict shape: `{"phase": "learning"|"review"|"relearning", "ease": float, "interval_days": int, "reps": int, "lapses": int}`. Opaque to consumers; None = first review.
Public API as built: unchanged (v1). `__init__` re-exports exactly the §4 names.
Deviations & assumptions:
- ASSUMPTION (§2 ambiguous): the ease formula applies to every non-lapse review, including graduation from learning and from relearning (Good leaves ease unchanged, Hard -0.14, Easy +0.10).
- ASSUMPTION: graduating from learning sets reps = reps+1 (so 1); graduating from relearning keeps reps and the reduced interval for Hard, Good and Easy (no Easy bonus). Again in learning or relearning leaves the state unchanged (no extra lapse).
- ASSUMPTION: the review-interval formulas use the new (just-updated) ease. reps 1 -> 1 day and reps 2 -> 6 days apply to any passing grade.
- ASSUMPTION: "round" means half-up, not banker's. Ease is rounded to 4 decimals to keep stored values clean. The 36500 cap wins over "strictly greater" at the cap.
- ASSUMPTION: `study_day` compares local wall-clock time to the rollover, which is the same as subtracting the rollover as a duration on a zoneinfo-aware datetime. Study days are therefore 23 or 25 hours across DST. `study_day_start` handles a rollover inside a DST gap (first instant at or after it) and inside an overlap (first occurrence).
- Extras within contract: SchedulerError also covers a malformed state, a bool or float grade, and a due date beyond year 9999.
Decisions made: none needing parent action. No REQs filed.
Children: none.
Delivery: b-001.zip · Apply: cd <project root> && unzip -o b-001.zip · Then delete: none
Verification: `pytest src/dunzo/scheduler` 78 passed. `ruff check src/dunzo/scheduler` clean. A test AST-scans the package for non-stdlib imports (none). Tests cover grade sequences, lapse and relearning, determinism, JSON round-trip, invalid grade, naive `now`, 03:59/04:00, DST (New York spring and fall, gap and overlap rollovers) and a `study_day_start` inverse sweep over 7 zones x 4 rollovers x 366 days.
Integration notes: `get_scheduler(DEFAULT_SCHEDULER).schedule(state, grade, now, config)` returns `ScheduleResult(state, due)`. Store `state` as JSON and pass it back unchanged. `now` must be aware (any offset). `due` is aware UTC.
Known issues / follow-ups: the `pyproject.toml` dev dependency is spelled `httpx2` (likely a typo for `httpx`, master-owned, not mine). My sandbox ruff applied extra rule sets (I, UP, RUF, PLW) and the code passes those too.
