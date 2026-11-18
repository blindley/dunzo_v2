PROJECT-HIERARCHY BRIEF
# BRIEF — f: progress

Brief rev: 1 · Parent: master · Children: none yet
Project: dunzo (codename) — a local single-user spaced-repetition flashcard web app: Python 3.12, FastAPI, SQLite, sandboxed JavaScript "executors" render cards.

> This file is your entire world. Read all of it. Do not ask for other files; if something you need is missing, file a REQ (see §9).

## 1. Mission
Own all persistence of private study data: card state, review log, new-card draw log, daily overrides and user settings, plus progress backup and restore.

## 2. Responsibilities (you own these)
- Implement §4 exactly: migrations creating the progress tables as in the schema contract (they reference content tables, so assume content migrated first), and the `Progress` class.
- `record_review` is one atomic step (state row, review log row, and on a first review the new_draw_log row); concurrency is decided by `expected_version` only.
- Settings are stored as JSON values in `setting`; unknown keys are ignored; `day_rollover` is stored as `HH:MM`.
- Backup format: a SQLite file with the five progress tables (same columns, no foreign keys) plus `backup_meta(format TEXT, version INTEGER, created_at REAL)` holding `dunzo-progress`, 1. Create it from a consistent snapshot of the live database (ATTACH + one read transaction or the sqlite backup API with a table copy). Restore validates the format first, then replaces all progress tables and settings in one transaction, skipping rows whose note or deck is missing.
- Tests need content tables: in tests create them by executing the schema-contract SQL (you may not import `dunzo.content`).

## 3. Non-responsibilities (owned elsewhere; do NOT build or reason about them)
- Content tables, blob storage, executors, media (owned by `content`).
- Scheduling math (`scheduler`) and queue selection (`review_queue`).
- Deciding when to warn about destructive changes (callers).

## 4. Public API you provide
Contract version: v1. Do not change without parent approval.
### `dunzo.progress` (contract v1; owner: agent `f`). Progress tables only (card_state, review_log, new_draw_log, day_override, setting).
```python
MIGRATIONS: MigrationSet            # owner "progress"; must be migrated AFTER content's (foreign keys point at content tables)
@dataclass(frozen=True) class UserSettings:
    new_per_day: int = 20; day_rollover: time = time(4, 0); again_delay_minutes: int = 10; learn_ahead_minutes: int = 20
@dataclass(frozen=True) class CardState: note_id: str; card_index: int; due: datetime; scheduler: str; state: dict; version: int
@dataclass(frozen=True) class ReviewEntry:
    id: int; note_id: str; card_index: int; reviewed_at: datetime; grade: int
    detail: dict | None; state_before: dict | None; state_after: dict
@dataclass(frozen=True) class ProgressSummary: card_states: int; reviews: int
@dataclass(frozen=True) class BackupInfo: path: Path; card_states: int; reviews: int; created_at: datetime
@dataclass(frozen=True) class RestoreReport:
    card_states: int; reviews: int; draws: int; skipped_card_states: int; skipped_reviews: int; skipped_draws: int
class Progress:
    def __init__(self, conn: sqlite3.Connection): ...
    # Raises NotFound / Invalid(details["problems"]) / Conflict as stated. Writers are atomic and nest inside core.transaction.
    def get_settings(self) -> UserSettings                          # stored values over the defaults above
    def update_settings(self, *, new_per_day: int | None = None, day_rollover: time | None = None,
                        again_delay_minutes: int | None = None, learn_ahead_minutes: int | None = None) -> UserSettings
        # Invalid unless 0 <= new_per_day <= 10000, 1 <= again_delay_minutes <= 1440, 0 <= learn_ahead_minutes <= 240
    def get_extra_new(self, day: date) -> int                       # 0 if none
    def add_extra_new(self, day: date, count: int) -> int           # count >= 1; returns the new total for that study day
    def get_card_state(self, note_id: str, card_index: int) -> CardState | None
    def record_review(self, *, note_id: str, card_index: int, deck_id: str, grade: int, detail: dict | None,
                      scheduler: str, state: dict, due: datetime, expected_version: int | None,
                      reviewed_at: datetime, study_day: date) -> CardState
        # atomic. expected_version None = first review: the card must have no card_state row; inserts it (version 1) and
        # writes a new_draw_log row (study_day, deck_id, note, index). Otherwise the row must exist at exactly that version;
        # it is updated and version+1. A review_log row is written (state_before None on a first review; state_after = state).
        # Conflict on any version mismatch (including a row that appeared or vanished); NotFound if the note does not exist;
        # Invalid if grade not in 1..4. Does NOT check card_index < card_count (caller's job).
    def list_reviews(self, note_id: str, *, card_index: int | None = None, limit: int = 100,
                     before: datetime | None = None) -> list[ReviewEntry]       # newest first
    def count_new_drawn(self, day: date) -> int                     # new_draw_log rows for that study day
    def summary_for_note(self, note_id: str, *, from_index: int = 0) -> ProgressSummary   # cards with card_index >= from_index
    def summary_for_deck(self, deck_id: str) -> ProgressSummary
    def delete_from_index(self, note_id: str, from_index: int) -> int   # removes card_state, review_log and new_draw_log rows with card_index >= from_index; returns card_state rows removed
    def backup_to(self, dest: Path, *, now: datetime) -> BackupInfo
        # consistent snapshot into a NEW sqlite file holding only progress tables + settings (never content); Conflict if dest exists
    def restore_from(self, src: Path) -> RestoreReport
        # replaces ALL progress tables and settings with the backup's, atomically; rows whose note/deck no longer exists are
        # skipped and counted; Invalid if src is not a valid dunzo progress backup
```
Invariant: the scheduler `state` dict is stored verbatim as JSON and never interpreted here.
Example: `p.record_review(note_id=n, card_index=0, deck_id=d, grade=3, detail=None, scheduler="sm2", state=r.state, due=r.due, expected_version=None, reviewed_at=now, study_day=day)`.


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

(provider: a)
### `dunzo.core` (contract v1; owner: agent `a`)
```python
# errors — raise these across component boundaries; l maps them to HTTP (404/422/409/409)
class DunzoError(Exception):            # .code: str, .message: str, .details: dict
    def __init__(self, message: str, *, details: dict | None = None): ...
class NotFound(DunzoError): ...         # code "not_found"
class Invalid(DunzoError): ...          # code "invalid"; by convention details["problems"]: list[str]
class Conflict(DunzoError): ...         # code "conflict" (stale version, already exists, still in use)
class ConfirmationRequired(DunzoError): ...  # code "confirmation_required"; details describe consequences
# ids and time (Python side: aware UTC datetimes only; DB side: REAL epoch seconds)
def new_id() -> str                     # uuid4, lowercase hyphenated
def utcnow() -> datetime                # aware UTC (only route layers call this; logic takes `now`)
def to_epoch(dt: datetime) -> float     # ValueError if naive
def from_epoch(x: float) -> datetime    # aware UTC
# database
def connect(path: Path) -> sqlite3.Connection
    # creates parent dir; row_factory=sqlite3.Row; isolation_level=None (explicit transactions);
    # check_same_thread=False; foreign_keys=ON; journal_mode=WAL; busy_timeout=5000
@contextmanager
def transaction(conn) -> Iterator[None]
    # outermost: BEGIN IMMEDIATE .. COMMIT, ROLLBACK on exception (re-raised).
    # nested: SAVEPOINT .. RELEASE / ROLLBACK TO. Safe to nest arbitrarily and across components.
@dataclass(frozen=True) class Migration: version: int; sql: str     # versions 1,2,3.. consecutive per owner
@dataclass(frozen=True) class MigrationSet: owner: str; migrations: tuple[Migration, ...]
def migrate(conn, sets: Sequence[MigrationSet]) -> None
    # for each set, in the order given: apply migrations newer than the owner's recorded version, each
    # atomically (script + version bump in one transaction). Versions live in table
    # schema_migration(owner TEXT PRIMARY KEY, version INTEGER). Idempotent. Raises on a gap or failure.
# web helpers (imports fastapi)
def get_conn(request: Request) -> Iterator[sqlite3.Connection]
    # FastAPI dependency: connect(get_settings().database_path) per request, closed afterwards
SANDBOX_CSP: str                        # exactly the string below
SANDBOX_HEADERS: dict[str, str]         # exactly the headers below; copy with dict(SANDBOX_HEADERS)
```
`SANDBOX_CSP` = `default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' data:; font-src 'self' data:; connect-src 'none'; form-action 'none'; base-uri 'none'; sandbox allow-scripts`
`SANDBOX_HEADERS` = `Content-Security-Policy: <SANDBOX_CSP>`, `X-Content-Type-Options: nosniff`, `Access-Control-Allow-Origin: *`, `Cross-Origin-Resource-Policy: cross-origin`, `Referrer-Policy: no-referrer`.
Example: `with transaction(conn): conn.execute("INSERT ...")`; `raise NotFound("deck not found", details={"id": deck_id})`.


## 6. Constraints & conventions
- Stack / language / versions: Python 3.12 + the project's pinned dependencies (see Global conventions below).
- Code directory (project-root-relative): src/dunzo/progress/    Docs directory: .hierarchy/f/
- Permitted touch-points outside your directories: none
- Existing files supplied to you: none (your directory is empty; `src/dunzo/__init__.py`, `config.py`, `main.py`, `pyproject.toml` exist and are master-owned: read-only for you)
- Global conventions:
  - Stack: Python 3.12, type hints throughout, frozen dataclasses for value types, stdlib `sqlite3`, `ruff` (line length 100). Add no dependency beyond `pyproject.toml` (fastapi, jinja2, jsonschema, python-multipart, python-dotenv, tzdata, tzlocal, uvicorn; dev: pytest, httpx2, playwright, ruff); if you need one, file a REQ.
  - Imports: other components only through their package's public names (`from dunzo.<dir> import ...`); never import their submodules or touch their tables/files. Your `__init__.py` re-exports exactly your §4 API (plus private helpers stay private).
  - Tests: pytest, inside your own directory at `<code dir>/tests/test_*.py` (no root `tests/`); run with `uv run pytest <code dir>`. Tests must not need network, other components' code, or the user's data dir (use `tmp_path`).
  - Time: Python values are aware UTC `datetime`s; take `now` as a parameter, never read the clock in logic. IDs: `core.new_id()` UUID strings. Errors: raise the `dunzo.core` error types across boundaries; pure components raise their own `ValueError` subclass.
  - Logging: stdlib `logging.getLogger("dunzo.<dir>")`; no `print`. No global mutable state. Treat all file names, paths and uploaded bytes as untrusted.

## 7. Acceptance criteria (definition of done)
- [ ] Behaviour matches §4 and the schema contract; migration yields exactly the progress tables and indexes.
- [ ] Tests cover first/second review, version conflicts, settings validation, summaries, deletion, backup and restore (including skipped rows); `uv run ruff check src/dunzo/progress` is clean.
- [ ] No import of `dunzo.content`; no SQL on content tables except foreign-key references and the existence check needed for `NotFound`.

## 8. Report requirements
Beyond the standard report format, the parent specifically needs: how backup achieves a consistent snapshot; restore semantics you chose for edge cases; settings storage format.

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
