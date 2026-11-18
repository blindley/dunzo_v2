PROJECT-HIERARCHY BRIEF
# BRIEF — j: review

Brief rev: 1 · Parent: master · Children: none yet
Project: dunzo (codename) — a local single-user spaced-repetition flashcard web app: Python 3.12, FastAPI, SQLite, sandboxed JavaScript "executors" render cards.

> This file is your entire world. Read all of it. Do not ask for other files; if something you need is missing, file a REQ (see §9).

## 1. Mission
Build the review experience: serve each card's sandboxed executor frame, the review shell page that hosts it, the endpoints that hand out cards and record reports, and the settings, statistics, history and progress-backup pages.

## 2. Responsibilities (you own these)
- Provide `router` per §4 and the URL map in §5.
- FIRST, before building the rest: write a browser spike (Playwright, headless Chromium; `uv run playwright install chromium`) that proves the sandbox design with a minimal frame, and report the result: the strict CSP works with `'self'` from an opaque (sandboxed) origin including module scripts and fonts; `postMessage` from the frame is accepted only when `event.source` is the host's iframe; a frame cannot reach the network, navigate, read cookies or the host DOM; opening a frame file directly is sandboxed. If any part of the contract (e.g. `SANDBOX_HEADERS`) must change, file a `contract-change` REQ immediately and continue with unblocked work.
- Frame serving (`/review/frame/{note_id}/{card_index}/{path}`): 404 unless 0 <= card_index < card_count. `dunzo/api.js` is one static script implementing the executor API (§4) the same for every card; `dunzo/card.js` is generated per card (`window.dunzoCard`, JSON-escaped safely, media urls `/cards/{note_id}/media/{hash}`), `Cache-Control: no-store`; any other `dunzo/...` path is 404; every other path comes from `Content.open_executor_file(note.executor_id, path)` (exact match) with `ETag` = file hash and the file's mime. Every frame response carries `core.SANDBOX_HEADERS`. `GET /cards/{note_id}/media/{hash}` uses `open_note_media` and sends `SANDBOX_HEADERS` plus `Content-Disposition: attachment`.
- Shell (`/review`, `/review/session`): `/review` lets the user pick one or more decks (or all) with `deck_stats`; `/review/session?deck=<id>&deck=<id>` renders the shell: an iframe `sandbox="allow-scripts"` only, plus counters, a message area for executor `error`s, an end-of-session screen, and an "extra study" button (shown when the new-card limit is reached) calling `POST /review/extra-new`. The shell asks `/review/next`, loads `frame_url`, and on a `done` message from its own iframe (check `event.source`) posts to `/review/report` with the card's `version`, then asks for the next card. It never shows grade buttons. A card whose executor errors can be skipped: the shell adds it to `exclude`.
- Endpoints: `GET /review/next?deck=…&exclude=<note_id>:<index>,…` returns `{"card": {note_id, card_index, kind, version, frame_url} | null, "counts": {due, new_available, new_drawn_today, learning_ahead}}` using `QueueConfig` built from `Progress.get_settings()`, the study day (`scheduler.study_day(now, rollover, settings.tz)`) and `get_extra_new`. `POST /review/report` takes `{note_id, card_index, version, grade, detail?}`: 404 unknown note, 422 for a bad grade or `card_index >= card_count`, otherwise `get_card_state` (use its `scheduler` name, or `DEFAULT_SCHEDULER` for a new card), `scheduler.schedule(state, grade, now, SchedulerConfig(again_delay, day_rollover, tz))`, then `record_review(expected_version=version, deck_id=note.deck_id, study_day=…)`; a stale version is HTTP 409 and the shell simply fetches the next card.
- Pages: `/review/history/{note_id}` (reviews, newest first), `/review/stats` (deck statistics), `/settings` (view/edit `UserSettings`; validation errors inline), `/backup` (create a backup file and download it; restore from an uploaded file after an explicit confirmation page; show the restore report). Use a temp file for backup downloads and delete it afterwards.
- Large component: you are expected to split (§9 rule 4), e.g. `j1` frame server + `dunzo/api.js` + the spike (security-critical, do it first), `j2` the shell page and its JavaScript, `j3` next/report/extra-new, history, stats, settings and backup routes. You own the combined router. The split must not alter §4. Tests: `fastapi.testclient` with fakes or real components on a temp database (stub middleware sets `request.state.csrf_token`); Playwright tests for the shell + a real executor frame (including a sample front/back executor written by you for tests only).

## 3. Non-responsibilities (owned elsewhere; do NOT build or reason about them)
- Management pages and media upload/preview (`manage`).
- Scheduling math, queue selection, persistence (`scheduler`, `review_queue`, `progress`, `content`).
- CSRF/Host enforcement and app wiring (`app`); the starter executors (`starters`).

## 4. Public API you provide
Contract version: v1. Do not change without parent approval.
### `dunzo.review` (owner: agent `j`)
```python
router: fastapi.APIRouter      # full paths, no prefix; included by `app`
```
HTTP surface (pages in addition): `GET /review/next?deck=<id>&deck=<id>&exclude=<note_id>:<index>,…` -> `{"card": {"note_id","card_index","kind","version","frame_url"} | null, "counts": {"due","new_available","new_drawn_today","learning_ahead"}}`; `POST /review/report` JSON `{"note_id","card_index","version","grade","detail"?}` -> `{"ok": true}` (404 unknown note; 422 bad grade or index; 409 stale version); `POST /review/extra-new` JSON `{"count": n}` -> `{"extra_new": total_for_today}`; `GET /review/frame/{note_id}/{card_index}/{path:path}`; `GET /cards/{note_id}/media/{hash}`; plus the pages `/review`, `/review/session`, `/review/history/{note_id}`, `/review/stats`, `/settings`, `/backup…` and static files under `/review/static/…`. All state-changing requests carry the CSRF token (header `X-CSRF-Token` from a `<meta>` tag in the shell page).
You also provide, to executors, the executor API below (files `dunzo/api.js` and `dunzo/card.js` served inside every frame):
### Executor API (contract v1; master-owned). Provided by `review` (the files `dunzo/api.js`, `dunzo/card.js`), used by executors such as `starters`.
An executor is a directory of static web files with `index.html` at its top, run in `<iframe sandbox="allow-scripts">` (no `allow-same-origin`). It loads the app's two generated files by relative URL: `<script src="dunzo/api.js"></script><script src="dunzo/card.js"></script>`. Its own files are loaded by relative path; nothing else on the server is reachable (strict CSP: scripts/styles/images/audio/video/fonts from the server only, inline allowed, no network, no eval, no navigation).
```js
window.dunzoCard = { note: { id, properties, media: [ {id, mime, size, url} ] }, index, card_count }   // from dunzo/card.js
dunzo.card                      // same object as window.dunzoCard
dunzo.onInit(callback)          // callback(card) once the page has loaded (immediately if it already has)
dunzo.done(grade, detail?)      // grade: integer 1..4 (1 Again, 2 Hard, 3 Good, 4 Easy); detail: optional JSON-serializable value stored with the review
dunzo.mediaUrl(hash)            // URL for a media hash listed in card.note.media, else null
```
Messages to the host (the only channel; `parent.postMessage(msg, "*")`): `{type:"done", grade, detail?}` and `{type:"error", message}` (reported for a missing card.js or a throwing onInit callback). The host accepts messages only when `event.source` is its own iframe window, validates `grade`, and moves on to the next card after recording a `done`. The host never shows grade buttons; the executor decides whether to show its own. An executor may send `done` at any time. There is no host-to-executor message.


## 5. APIs you consume
Black boxes. Use exactly as written. Do not look inside.
(provider: e)
### `dunzo.content` — the subset the review component uses (contract v1; excerpt of the full contract)
```python
@dataclass(frozen=True) class MediaInfo: id: str; mime: str; size: int
@dataclass(frozen=True) class Note: id: str; deck_id: str; executor_id: str; card_count: int; position: int; properties: dict; media_list: tuple[MediaInfo, ...]; created_at: datetime; updated_at: datetime
@dataclass(frozen=True) class StoredFile: meta: FileMeta; path: Path        # FileMeta(path, hash, mime, size) from dunzo.file_rules
@dataclass(frozen=True) class StoredMedia: info: MediaInfo; path: Path
class Content:
    def __init__(self, conn: sqlite3.Connection, data_dir: Path, max_media_bytes: int = 20 * 1024 * 1024): ...
    def get_note(self, note_id: str) -> Note                                   # NotFound if unknown
    def open_executor_file(self, executor_id: str, path: str) -> StoredFile    # exact path match, else NotFound
    def open_note_media(self, note_id: str, media_id: str) -> StoredMedia      # NotFound unless linked to that note
```

(provider: f)
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

(provider: g)
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

(provider: b)
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

(provider: master)
### `dunzo.config` (master-owned root file; contract v1)
```python
@dataclass(frozen=True) class Settings:
    host: str; port: int; data_dir: Path; max_media_bytes: int; tz: tzinfo   # tz = TIMEZONE env or system zone
    database_path: Path   # property: data_dir / "dunzo.db"
def get_settings() -> Settings        # cached; PORT is required. Tests construct explicit values instead of calling it.
```

(provider: master)
### Web conventions and URL map (contract v1; master-owned) — shared by `manage` (i), `review` (j), `app` (l)
Each of `dunzo.manage` and `dunzo.review` exports `router: fastapi.APIRouter` with full paths (no prefix), and serves its own static files and templates from inside its own package directory. `app` includes both routers. Route functions are synchronous (`def`).
- `manage` owns: `/decks…`, `/notes…`, `/executors…`, `/media…` (upload `POST /media/upload` → JSON MediaInfo; preview `GET /media/{id}`), `/packages…` (export download, import upload), `/manage-static/…`.
- `review` owns: `/review` (deck selection), `/review/session` (the shell page), `/review/next` (JSON), `/review/report` (POST JSON), `/review/frame/{note_id}/{card_index}/{path:path}`, `/cards/{note_id}/media/{hash}`, `/review/history/{note_id}`, `/review/stats`, `/settings`, `/backup…`, `/review/static/…`.
- `app` owns: `/` (redirects to `/decks`), `/healthz`, the error pages, middleware.
Rules: (1) Routers raise `dunzo.core` errors; `app` renders them (HTML for browsers, JSON `{"error": {"code", "message", "details"}}` otherwise) with HTTP 404 / 422 / 409 / 409 for NotFound / Invalid / Conflict / ConfirmationRequired. (2) CSRF and Host checks are enforced by `app` for every non-GET/HEAD/OPTIONS request: requests must carry the token `request.state.csrf_token` as header `X-CSRF-Token` or form field `csrf_token`. Routers never enforce this themselves; every HTML form includes the hidden field and every fetch() sends the header. In tests, supply a stub middleware that sets `request.state.csrf_token = "test"`. (3) Per-request database connection: `conn = Depends(dunzo.core.get_conn)`; components build `Content(conn, settings.data_dir, settings.max_media_bytes)`, `Progress(conn)`, `ReviewQueue(conn)` from it with `dunzo.config.get_settings()`. (4) Timestamps come from `dunzo.core.utcnow()` in the route layer only.


## 6. Constraints & conventions
- Stack / language / versions: Python 3.12 + the project's pinned dependencies (see Global conventions below).
- Code directory (project-root-relative): src/dunzo/review/    Docs directory: .hierarchy/j/
- Permitted touch-points outside your directories: none
- Existing files supplied to you: none (your directory is empty; `src/dunzo/__init__.py`, `config.py`, `main.py`, `pyproject.toml` exist and are master-owned: read-only for you)
- Global conventions:
  - Stack: Python 3.12, type hints throughout, frozen dataclasses for value types, stdlib `sqlite3`, `ruff` (line length 100). Add no dependency beyond `pyproject.toml` (fastapi, jinja2, jsonschema, python-multipart, python-dotenv, tzdata, tzlocal, uvicorn; dev: pytest, httpx2, playwright, ruff); if you need one, file a REQ.
  - Imports: other components only through their package's public names (`from dunzo.<dir> import ...`); never import their submodules or touch their tables/files. Your `__init__.py` re-exports exactly your §4 API (plus private helpers stay private).
  - Tests: pytest, inside your own directory at `<code dir>/tests/test_*.py` (no root `tests/`); run with `uv run pytest <code dir>`. Tests must not need network, other components' code, or the user's data dir (use `tmp_path`).
  - Time: Python values are aware UTC `datetime`s; take `now` as a parameter, never read the clock in logic. IDs: `core.new_id()` UUID strings. Errors: raise the `dunzo.core` error types across boundaries; pure components raise their own `ValueError` subclass.
  - Logging: stdlib `logging.getLogger("dunzo.<dir>")`; no `print`. No global mutable state. Treat all file names, paths and uploaded bytes as untrusted.
- Security: executors and uploaded files are untrusted; escape all user content; never serve user-supplied bytes without the sandbox headers specified above.

## 7. Acceptance criteria (definition of done)
- [ ] The spike's findings are reported and the sandbox properties hold in a real browser.
- [ ] A complete review loop works in Playwright: pick decks, get a card, executor calls `dunzo.done`, the report is recorded, the next card appears, duplicate/stale reports are rejected, new-card limit and extra study behave as §2 says.
- [ ] Frames and card media carry `SANDBOX_HEADERS`; `card.js` is `no-store`; other `dunzo/` paths 404.
- [ ] `uv run ruff check src/dunzo/review` is clean; no SQL; no import of `dunzo.manage`.

## 8. Report requirements
Beyond the standard report format, the parent specifically needs: the spike results first; the child tree if you split; deviations from §4; browser versions tested.

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
