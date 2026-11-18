PROJECT-HIERARCHY BRIEF
# BRIEF — g: review_queue

Brief rev: 1 · Parent: master · Children: none yet
Project: dunzo (codename) — a local single-user spaced-repetition flashcard web app: Python 3.12, FastAPI, SQLite, sandboxed JavaScript "executors" render cards.

> This file is your entire world. Read all of it. Do not ask for other files; if something you need is missing, file a REQ (see §9).

## 1. Mission
Answer, read-only, what to review next: due cards, round-robin new cards under the daily limit, learning cards about to come due, plus counts and per-deck statistics.

## 2. Responsibilities (you own these)
- Implement §4 exactly with plain `sqlite3` queries over the schema-contract tables; never write.
- New cards are never stored: enumerate a note's card indices at query time (for example with `WITH RECURSIVE` or `json_each`) and exclude those with a `card_state` row. Take care that the result is lazy: finding the first new card must not scan all cards of all decks.
- Performance target: `next_card` and `counts` under 50 ms on 20,000 notes with 2 cards each across 20 decks (add this as a test with generated data); report the query plans you rely on. You cannot add indexes: they belong to the schema contract; if you need one, file a REQ.
- Tests build the tables by executing the schema-contract SQL; cover round-robin fairness across days (a second call after draws), exclusion, limits with `extra_new`, deck scoping, orphaned indices (`card_index >= card_count`), and ties.

## 3. Non-responsibilities (owned elsewhere; do NOT build or reason about them)
- Recording reviews or drawing (progress writes happen in `progress.record_review`).
- Computing the study day, reading settings, or scheduling.
- Creating tables or indexes.

## 4. Public API you provide
Contract version: v1. Do not change without parent approval.
### `dunzo.review_queue` (contract v1; owner: agent `g`). Read-only; joins content and progress tables (layouts: schema contract).
```python
@dataclass(frozen=True) class QueueConfig:
    study_day: date; new_per_day: int; extra_new: int = 0
    learn_ahead: timedelta = timedelta(minutes=20); deck_ids: frozenset[str] | None = None   # None = all decks
@dataclass(frozen=True) class QueuedCard:
    note_id: str; card_index: int; deck_id: str; kind: Literal["due", "new", "learning"]
    version: int | None; due: datetime | None          # None for new cards
@dataclass(frozen=True) class QueueCounts: due: int; new_available: int; new_drawn_today: int; learning_ahead: int
@dataclass(frozen=True) class DeckStats: deck_id: str; name: str; total_cards: int; new_cards: int; due_cards: int
class ReviewQueue:
    def __init__(self, conn: sqlite3.Connection): ...
    def next_card(self, config: QueueConfig, now: datetime,
                  *, exclude: AbstractSet[tuple[str, int]] = frozenset()) -> QueuedCard | None
    def counts(self, config: QueueConfig, now: datetime) -> QueueCounts
        # new_available = min(remaining daily allowance, new cards that exist in scope); learning_ahead = cards with now < due <= now+learn_ahead
    def deck_stats(self, now: datetime, deck_ids: frozenset[str] | None = None) -> list[DeckStats]   # ordered by deck name
```
Rules. Scope: notes of the selected decks; only cards with card_index < note.card_count. `next_card` returns the first applicable of: (1) kind "due": card_state.due <= now, earliest due first (ties: note position, note id, index); (2) kind "new": only while new_drawn_today < new_per_day + extra_new, where new_drawn_today counts new_draw_log rows of config.study_day for ALL decks. Round-robin: among selected decks that still have a new card (not excluded), pick the deck whose latest new_draw_log.drawn_at over all days is oldest (never-drawn decks first; ties by deck name, then id), and return that deck's first never-reviewed card by (note.position, card_index); (3) kind "learning": earliest card with now < due <= now + learn_ahead; else None. `exclude` applies to every kind. Never writes.


## 5. APIs you consume
Black boxes. Use exactly as written. Do not look inside.
(provider: master)
### Schema contract (master-owned, v1) — table layouts shared by content (e), progress (f), review queue (g)
Content tables are written only by `content`; progress tables only by `progress`; `review_queue` only reads. Timestamps are REAL unix epoch seconds (UTC); `study_day` is TEXT `YYYY-MM-DD`; JSON columns are TEXT. Connections run with `PRAGMA foreign_keys=ON`.
```sql
-- content
CREATE TABLE deck (id TEXT PRIMARY KEY, name TEXT NOT NULL, parent_id TEXT REFERENCES deck(id));
CREATE TABLE executor (id TEXT PRIMARY KEY, name TEXT NOT NULL, files_hash TEXT NOT NULL, note_schema TEXT);
CREATE TABLE executor_file (
  executor_id TEXT NOT NULL REFERENCES executor(id) ON DELETE CASCADE,
  path TEXT NOT NULL, hash TEXT NOT NULL, mime TEXT NOT NULL, size INTEGER NOT NULL CHECK (size > 0),
  PRIMARY KEY (executor_id, path));
CREATE TABLE note (
  id TEXT PRIMARY KEY,
  deck_id TEXT NOT NULL REFERENCES deck(id) ON DELETE CASCADE,
  executor_id TEXT NOT NULL REFERENCES executor(id) ON DELETE RESTRICT,
  card_count INTEGER NOT NULL CHECK (card_count >= 1),
  position INTEGER NOT NULL, properties TEXT NOT NULL,
  created_at REAL NOT NULL, updated_at REAL NOT NULL,
  UNIQUE (deck_id, position));
CREATE TABLE media (id TEXT PRIMARY KEY, mime TEXT NOT NULL, size INTEGER NOT NULL, created_at REAL NOT NULL);
CREATE TABLE note_media (
  note_id TEXT NOT NULL REFERENCES note(id) ON DELETE CASCADE,
  media_id TEXT NOT NULL REFERENCES media(id) ON DELETE RESTRICT,
  PRIMARY KEY (note_id, media_id));
CREATE INDEX note_executor ON note(executor_id);
CREATE INDEX note_media_media ON note_media(media_id);
-- progress (private; foreign keys point at content, never the reverse)
CREATE TABLE card_state (
  note_id TEXT NOT NULL REFERENCES note(id) ON DELETE CASCADE,
  card_index INTEGER NOT NULL, due REAL NOT NULL, scheduler TEXT NOT NULL, state TEXT NOT NULL,
  version INTEGER NOT NULL, PRIMARY KEY (note_id, card_index));
CREATE INDEX card_state_due ON card_state(due);
CREATE TABLE review_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  note_id TEXT NOT NULL REFERENCES note(id) ON DELETE CASCADE,
  card_index INTEGER NOT NULL, reviewed_at REAL NOT NULL,
  grade INTEGER NOT NULL CHECK (grade BETWEEN 1 AND 4),
  detail TEXT, state_before TEXT, state_after TEXT NOT NULL);
CREATE INDEX review_log_card ON review_log(note_id, card_index, reviewed_at);
CREATE TABLE new_draw_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, study_day TEXT NOT NULL,
  deck_id TEXT NOT NULL REFERENCES deck(id) ON DELETE CASCADE,
  note_id TEXT NOT NULL REFERENCES note(id) ON DELETE CASCADE,
  card_index INTEGER NOT NULL, drawn_at REAL NOT NULL);
CREATE INDEX new_draw_day ON new_draw_log(study_day);
CREATE INDEX new_draw_deck ON new_draw_log(deck_id, drawn_at);
CREATE TABLE day_override (study_day TEXT PRIMARY KEY, extra_new INTEGER NOT NULL CHECK (extra_new >= 0));
CREATE TABLE setting (key TEXT PRIMARY KEY, value TEXT NOT NULL);
```


## 6. Constraints & conventions
- Stack / language / versions: Python 3.12 + the project's pinned dependencies (see Global conventions below).
- Code directory (project-root-relative): src/dunzo/review_queue/    Docs directory: .hierarchy/g/
- Permitted touch-points outside your directories: none
- Existing files supplied to you: none (your directory is empty; `src/dunzo/__init__.py`, `config.py`, `main.py`, `pyproject.toml` exist and are master-owned: read-only for you)
- Global conventions:
  - Stack: Python 3.12, type hints throughout, frozen dataclasses for value types, stdlib `sqlite3`, `ruff` (line length 100). Add no dependency beyond `pyproject.toml` (fastapi, jinja2, jsonschema, python-multipart, python-dotenv, tzdata, tzlocal, uvicorn; dev: pytest, httpx2, playwright, ruff); if you need one, file a REQ.
  - Imports: other components only through their package's public names (`from dunzo.<dir> import ...`); never import their submodules or touch their tables/files. Your `__init__.py` re-exports exactly your §4 API (plus private helpers stay private).
  - Tests: pytest, inside your own directory at `<code dir>/tests/test_*.py` (no root `tests/`); run with `uv run pytest <code dir>`. Tests must not need network, other components' code, or the user's data dir (use `tmp_path`).
  - Time: Python values are aware UTC `datetime`s; take `now` as a parameter, never read the clock in logic. IDs: `core.new_id()` UUID strings. Errors: raise the `dunzo.core` error types across boundaries; pure components raise their own `ValueError` subclass.
  - Logging: stdlib `logging.getLogger("dunzo.<dir>")`; no `print`. No global mutable state. Treat all file names, paths and uploaded bytes as untrusted.

## 7. Acceptance criteria (definition of done)
- [ ] Behaviour matches §4 and the rules text exactly; tests pass including the performance test.
- [ ] `uv run ruff check src/dunzo/review_queue` is clean; no imports from other dunzo components.

## 8. Report requirements
Beyond the standard report format, the parent specifically needs: the SQL strategy for new-card enumeration; measured timings; any index you would want.

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
