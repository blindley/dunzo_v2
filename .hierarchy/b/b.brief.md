PROJECT-HIERARCHY BRIEF
# BRIEF — b: scheduler

Brief rev: 1 · Parent: master · Children: none yet
Project: dunzo (codename) — a local single-user spaced-repetition flashcard web app: Python 3.12, FastAPI, SQLite, sandboxed JavaScript "executors" render cards.

> This file is your entire world. Read all of it. Do not ask for other files; if something you need is missing, file a REQ (see §9).

## 1. Mission
Decide when a card is next due: a pure, swappable scheduling interface with an SM-2 implementation (with relearning steps) and the study-day arithmetic.

## 2. Responsibilities (you own these)
- Implement §4. Registry maps names to schedulers; `sm2` is the first.
- SM-2 specification. Quality mapping: grade 1,2,3,4 -> quality 1,3,4,5. Ease starts at 2.5 and after each non-lapse review becomes `max(1.3, ease + 0.1 - (5-q)*(0.08 + (5-q)*0.02))`. State keys: `phase` (`learning` | `review` | `relearning`), `ease`, `interval_days` (int), `reps`, `lapses`.
- First review (state None): Again -> phase `learning`, due now + again_delay. Hard or Good -> phase `review`, reps 1, interval 1 day. Easy -> review, reps 1, interval 4 days. Ease is updated for Hard and Easy by the formula above.
- In `learning` or `relearning`: Again -> due now + again_delay again. Hard/Good/Easy graduate to `review` with interval 1 (Easy 4) from learning, or with the already-reduced `interval_days` from relearning.
- In `review`: Again is a lapse: lapses+1, ease = max(1.3, ease - 0.2), interval_days = max(1, interval_days // 2), phase `relearning`, due now + again_delay. Otherwise reps+1 and the ease formula applies; interval: reps 1 -> 1 day, reps 2 -> 6 days, then Good = round(interval*ease), Hard = max(interval+1, round(interval*1.2)), Easy = round(interval*ease*1.3); always strictly greater than the previous interval, capped at 36500.
- Due for any interval of 1 day or more is `study_day_start(study_day(now, rollover, tz) + interval_days, rollover, tz)`; short delays are exact (`now + again_delay`).
- Document the final rules in `.hierarchy/b/sm2.md`. Tests: sequences of grades, lapse and relearning, determinism, JSON round-trip of state, invalid grade, naive `now`, `study_day` around 03:59/04:00 and across DST changes, `study_day_start` inverse.

## 3. Non-responsibilities (owned elsewhere; do NOT build or reason about them)
- Storing state or reading settings (progress component, route layer).
- The review queue, new-card logic, or any database/web code.
- Other algorithms (FSRS is future work; only keep the interface swappable).

## 4. Public API you provide
Contract version: v1. Do not change without parent approval.
### `dunzo.scheduler` (contract v1; owner: agent `b`). Pure: no I/O, no database or web imports.
```python
AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4
@dataclass(frozen=True) class SchedulerConfig:
    again_delay: timedelta = timedelta(minutes=10); day_rollover: time = time(4, 0); tz: tzinfo = timezone.utc
@dataclass(frozen=True) class ScheduleResult: state: dict[str, Any]; due: datetime   # state JSON-serializable; due aware UTC
class Scheduler(Protocol):
    name: str
    def schedule(self, state: dict | None, grade: int, now: datetime, config: SchedulerConfig) -> ScheduleResult
        # state None = the card's first review. SchedulerError if grade not in 1..4 or `now` is naive.
DEFAULT_SCHEDULER = "sm2"
def get_scheduler(name: str) -> Scheduler            # SchedulerError if unknown
class SchedulerError(ValueError): ...
def study_day(now: datetime, rollover: time, tz: tzinfo) -> date
    # the calendar date in `tz` of (now - rollover as a duration): 03:59 with rollover 04:00 belongs to the previous day
def study_day_start(day: date, rollover: time, tz: tzinfo) -> datetime   # aware UTC instant at which `day` begins
```
Guarantees: deterministic; the returned state is opaque to everyone but the scheduler that produced it; a grade of AGAIN yields `due = now + again_delay`.


## 5. APIs you consume
Black boxes. Use exactly as written. Do not look inside.
None.

## 6. Constraints & conventions
- Stack / language / versions: Python 3.12 + the project's pinned dependencies (see Global conventions below).
- Code directory (project-root-relative): src/dunzo/scheduler/    Docs directory: .hierarchy/b/
- Permitted touch-points outside your directories: none
- Existing files supplied to you: none (your directory is empty; `src/dunzo/__init__.py`, `config.py`, `main.py`, `pyproject.toml` exist and are master-owned: read-only for you)
- Global conventions:
  - Stack: Python 3.12, type hints throughout, frozen dataclasses for value types, stdlib `sqlite3`, `ruff` (line length 100). Add no dependency beyond `pyproject.toml` (fastapi, jinja2, jsonschema, python-multipart, python-dotenv, tzdata, tzlocal, uvicorn; dev: pytest, httpx2, playwright, ruff); if you need one, file a REQ.
  - Imports: other components only through their package's public names (`from dunzo.<dir> import ...`); never import their submodules or touch their tables/files. Your `__init__.py` re-exports exactly your §4 API (plus private helpers stay private).
  - Tests: pytest, inside your own directory at `<code dir>/tests/test_*.py` (no root `tests/`); run with `uv run pytest <code dir>`. Tests must not need network, other components' code, or the user's data dir (use `tmp_path`).
  - Time: Python values are aware UTC `datetime`s; take `now` as a parameter, never read the clock in logic. IDs: `core.new_id()` UUID strings. Errors: raise the `dunzo.core` error types across boundaries; pure components raise their own `ValueError` subclass.
  - Logging: stdlib `logging.getLogger("dunzo.<dir>")`; no `print`. No global mutable state. Treat all file names, paths and uploaded bytes as untrusted.

## 7. Acceptance criteria (definition of done)
- [ ] Behaviour matches §2 and §4; all tests pass; `uv run ruff check src/dunzo/scheduler` is clean.
- [ ] The package imports nothing outside the standard library.

## 8. Report requirements
Beyond the standard report format, the parent specifically needs: any rule in §2 you changed or found ambiguous (and why); the state dict shape; `.hierarchy/b/sm2.md` location.

## 9. Working protocol (authoritative; follow it even if you have no other instructions)

**Your place.** You are a *node* in a project hierarchy. Your id and parent are in the header. Your parent owns this brief and your contracts; you own the work inside your boundary. The human carries files between sessions; they are the only channel.

**Rules**
1. **Stay in your lane.** Use only this brief and the APIs in §5. Never guess at other components' internals. Don't touch what §3 excludes.
2. **No silent changes to contracts.** You may not change §4 or §5 yourself. If you need to, file a REQ (type `contract-change`).
3. **Ask, don't assume.** If something is unclear, missing, or contradictory, write a REQ, say which items it blocks, and continue with unblocked work. If you must proceed on an assumption, label it `ASSUMPTION` and list it in your report.
4. **Splitting.** If the work exceeds one session or has cleanly separable parts, you may split it into child nodes. Name them by alternating letters and numbers: children of `a` are `a1`, `a2`; of `a1` are `a1a`, `a1b`; of `a1a` are `a1a1`, `a1a2`. Give each child a code directory inside your own. Write each child a brief in this same format (sections 1–9, including this protocol, with `Parent: {your id}`), carry the exact API text they need into their §5, and keep a `{id}.tree.md` listing children, status, and brief revs. You become their parent: you answer their REQs, issue their CHGs, and integrate their reports. A split must not alter your own §4 contract; if it would, REQ upward first.
5. **Changes from above.** A `CHG` notice, or a higher `Brief rev`, supersedes earlier text. Apply it, note the new rev, and cascade to your children if affected.
6. **Context hygiene.** Read only what you need; use targeted reads; don't paste large files into chat; don't re-read what you already hold. If the session becomes long or slow, write a CHECKPOINT and tell the user to continue in a fresh session with this brief + the checkpoint.
7. **Where files go, and how you deliver them.** §6 gives your `Code directory` (project-root-relative) and your docs directory `.hierarchy/{id path}/` (each ancestor id in turn: for `a1a` it is `.hierarchy/a/a1/a1a/`). Write only in those two places; anything else needs a REQ unless §6 lists it as a permitted touch-point. You need no knowledge of siblings' paths. Deliver files as a zip containing only added or changed files (whole files, not diffs) at paths relative to the project root (never absolute, never `..`), so that unzipping at the project root with overwrite puts everything in place. Recipe: make a staging folder laid out like the project root, copy in the changed files plus your docs (report, child briefs, tree, REQs/RESPs/CHGs), add a manifest `.hierarchy/{id path}/deliveries/{id}-{nnn}.manifest.md` listing the files and a `Delete:` list (zips can't delete; a move is a delete plus an add), then `cd staging && zip -r ../{id}-{nnn}.zip .`. If the skill's `make_delivery.py` is available it does this and rejects out-of-boundary paths. Deliver updated child briefs and messages the same way.
8. **Finish with a REPORT** when acceptance criteria (§7) are met, or when you are blocked and can go no further.

**Naming files:** `{id}-{nnn}.zip` (deliveries), `{id}.brief.md`, `{id}.report.md`, `REQ-{from}-{nnn}.md`, `RESP-{to}-{nnn}.md`, `CHG-{to}-{nnn}.md`, `CHECKPOINT-{id}-{nnn}.md`. Always tell the user which file goes to which session (parent or child).

### Message formats (keep each short)

**REQ** (child → parent)
```
# REQ-{from}-{nnn} → {parent}
Brief rev: {n} · Type: clarification | contract-change | missing-api | scope-conflict
Blocks: {items blocked, or "nothing"}
Question: {one clear question}
Context: {minimum needed to decide}
Options I see: {A / B, with my recommendation}
Meanwhile I am: {what I'm continuing with}
```

**RESP** (parent → child)
```
# RESP-{to}-{nnn} ← answers REQ-{from}-{nnn}
Decision: {clear answer}
Brief changes: none | rev {n→m}: {what changed}   (updated brief attached if changed)
Effect on you: {what to do differently, if anything}
```

**CHG** (parent → child; requirements or contracts changed)
```
# CHG-{to}-{nnn}
Brief rev: {old} → {new}
Changed: {section: before → after}, one line each
Action required: {what the node must redo or adjust}
In-progress work: can continue | must pause | must revisit {part}
```

**REPORT** (node → parent; ≲1 page)
```
# REPORT-{id}
Status: complete | partial | blocked      Brief rev worked against: {n}
Summary: {≤8 lines}
Public API as built: unchanged | differs: {exact differences}
Deviations & assumptions: {each flagged ASSUMPTION or DEVIATION, with why}
Decisions made: {only those the parent should know}
Children (if split): {id: status}
Delivery: {id}-{nnn}.zip · Apply: cd <project root> && unzip -o {id}-{nnn}.zip · Then delete: {paths | none}
Verification: {tests run, results}
Integration notes: {only what a consumer needs; the API, not the internals}
Known issues / follow-ups: {…}
```

**CHECKPOINT** (node → its own future session)
```
# CHECKPOINT-{id}-{nnn}
Done so far: {…}
Current state: {what works, what's mid-change}
Next steps: {ordered}
Decisions & gotchas: {things the next session must not relearn}
Open REQs: {ids + status}
Files touched: {paths}
```
