PROJECT-HIERARCHY BRIEF
# BRIEF — l: app

Brief rev: 1 · Parent: master · Children: none yet
Project: dunzo (codename) — a local single-user spaced-repetition flashcard web app: Python 3.12, FastAPI, SQLite, sandboxed JavaScript "executors" render cards.

> This file is your entire world. Read all of it. Do not ask for other files; if something you need is missing, file a REQ (see §9).

## 1. Mission
Assemble the application: create the FastAPI app, run migrations and garbage collection at startup, and provide the cross-cutting protections (Host check, CSRF, error pages).

## 2. Responsibilities (you own these)
- Implement §4. `src/dunzo/main.py` (master-owned) already runs `uvicorn.run("dunzo.app:app")`: `dunzo/app/__init__.py` must export `create_app` and `app`.
- Middleware and dependencies per the web conventions in §5: random per-process CSRF token placed in `request.state.csrf_token`; every non-GET/HEAD/OPTIONS request must present it as header `X-CSRF-Token` or form field `csrf_token` and, if an `Origin` header is present, it must match the request's host; otherwise HTTP 403. Reject requests whose `Host` header is not the configured host, `localhost`, `127.0.0.1` or `[::1]` with the configured port (HTTP 400; guards against DNS rebinding). Frame and card-media responses are not touched (they carry their own headers).
- Error handling: `NotFound` 404, `Invalid` 422, `Conflict` 409, `ConfirmationRequired` 409, unexpected exceptions 500 (logged, no stack trace to the client). Browsers (Accept: text/html) get a small self-contained HTML error page; everyone else gets JSON `{"error": {"code", "message", "details"}}`.
- Lifespan: `connect` + `migrate(conn, [content.MIGRATIONS, progress.MIGRATIONS])`; garbage collection once at startup and then every 24 h in a background task (`Content(conn, settings.data_dir, settings.max_media_bytes).collect_garbage(utcnow())`), failures logged not fatal; stop the task on shutdown.
- Routes: `/` redirects to `/decks`; `/healthz` returns `{"ok": true}`. Mount `manage.router` and `review.router` (import them as `from dunzo.manage import router`, `from dunzo.review import router`).
- Tests with `fastapi.testclient`: use stub routers satisfying the web conventions where the real ones are not available; test CSRF acceptance/rejection, Host check, error mapping (HTML vs JSON), migrations run on a temp data dir (twice, idempotent), the GC task scheduling (inject the interval), `/` and `/healthz`.

## 3. Non-responsibilities (owned elsewhere; do NOT build or reason about them)
- Any page, form or domain route (`manage`, `review`).
- Schema, queries or business rules.
- `config.py` and `main.py` (master-owned).

## 4. Public API you provide
Contract version: v1. Do not change without parent approval.
### `dunzo.app` (contract v1; owner: agent `l`)
```python
def create_app(settings: Settings | None = None) -> FastAPI   # no I/O at construction; startup work happens in the lifespan
app: FastAPI                                                  # = create_app(); this is what `dunzo.main` serves ("dunzo.app:app")
```
Lifespan: open the database, `migrate(conn, [content.MIGRATIONS, progress.MIGRATIONS])` (content first), run `Content.collect_garbage` once at startup and then daily in a background task. Mounts `manage.router` and `review.router`. Provides the middleware, error handling and routes listed in the web conventions (CSRF token in `request.state.csrf_token`, Host-header check, error pages, `/`, `/healthz`).


## 5. APIs you consume
Black boxes. Use exactly as written. Do not look inside.
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

(provider: e)
### `dunzo.content` — the parts the app shell uses (contract v1; excerpt of the full contract)
```python
MIGRATIONS: MigrationSet            # owner "content"
@dataclass(frozen=True) class GcReport: media_deleted: int; executor_blobs_deleted: int; bytes_freed: int
class Content:
    def __init__(self, conn: sqlite3.Connection, data_dir: Path, max_media_bytes: int = 20 * 1024 * 1024): ...
    def collect_garbage(self, now: datetime, grace: timedelta = timedelta(hours=24)) -> GcReport
```

(provider: f)
### `dunzo.progress` — the parts the app shell uses (contract v1; excerpt of the full contract)
```python
MIGRATIONS: MigrationSet            # owner "progress"; must be migrated AFTER content's
```


## 6. Constraints & conventions
- Stack / language / versions: Python 3.12 + the project's pinned dependencies (see Global conventions below).
- Code directory (project-root-relative): src/dunzo/app/    Docs directory: .hierarchy/l/
- Permitted touch-points outside your directories: none
- Existing files supplied to you: none (your directory is empty; `src/dunzo/__init__.py`, `config.py`, `main.py`, `pyproject.toml` exist and are master-owned: read-only for you)
- Global conventions:
  - Stack: Python 3.12, type hints throughout, frozen dataclasses for value types, stdlib `sqlite3`, `ruff` (line length 100). Add no dependency beyond `pyproject.toml` (fastapi, jinja2, jsonschema, python-multipart, python-dotenv, tzdata, tzlocal, uvicorn; dev: pytest, httpx2, playwright, ruff); if you need one, file a REQ.
  - Imports: other components only through their package's public names (`from dunzo.<dir> import ...`); never import their submodules or touch their tables/files. Your `__init__.py` re-exports exactly your §4 API (plus private helpers stay private).
  - Tests: pytest, inside your own directory at `<code dir>/tests/test_*.py` (no root `tests/`); run with `uv run pytest <code dir>`. Tests must not need network, other components' code, or the user's data dir (use `tmp_path`).
  - Time: Python values are aware UTC `datetime`s; take `now` as a parameter, never read the clock in logic. IDs: `core.new_id()` UUID strings. Errors: raise the `dunzo.core` error types across boundaries; pure components raise their own `ValueError` subclass.
  - Logging: stdlib `logging.getLogger("dunzo.<dir>")`; no `print`. No global mutable state. Treat all file names, paths and uploaded bytes as untrusted.

## 7. Acceptance criteria (definition of done)
- [ ] `uv run dunzo` starts the app with both routers mounted once `manage` and `review` are delivered (until then your tests use stubs).
- [ ] CSRF, Host check, error handling, lifespan behave as §2 and tests pass; `uv run ruff check src/dunzo/app` is clean.

## 8. Report requirements
Beyond the standard report format, the parent specifically needs: the exact middleware order; how the token is delivered to pages; what you need from `manage`/`review` that the conventions do not yet say.

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
