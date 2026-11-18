PROJECT-HIERARCHY BRIEF
# BRIEF — i: manage

Brief rev: 1 · Parent: master · Children: none yet
Project: dunzo (codename) — a local single-user spaced-repetition flashcard web app: Python 3.12, FastAPI, SQLite, sandboxed JavaScript "executors" render cards.

> This file is your entire world. Read all of it. Do not ask for other files; if something you need is missing, file a REQ (see §9).

## 1. Mission
Build the server-rendered management UI: decks, notes, executors, media and package export/import pages, as one FastAPI router.

## 2. Responsibilities (you own these)
- Provide `router` per §4 and the URL map in §5. Templates: Jinja2 with HTMX (vendor `htmx.min.js` into `manage/static/`; get it from the npm package `htmx.org` if you have network, else REQ asking the user to supply it). No CDN at runtime.
- Decks: list, create, rename, delete. Deck page lists its notes in order with move-to-deck, reorder and delete. Deleting a deck or note that has progress (`summary_*` non-zero) shows a confirmation page stating the consequences first; only then delete.
- Notes: create and edit. The editor shows the executor's schema form (`schema_forms`) when the executor has a supported `note_schema`, else a raw JSON box; validates on save (`Invalid` problems shown inline); sets `card_count`; changing the executor revalidates and shows mismatches instead of saving. Shrinking `card_count` with progress requires confirmation, then `update_note` + `progress.delete_from_index` in one `core.transaction`.
- Media in the note editor: drag-and-drop upload area (JavaScript `fetch` to `POST /media/upload`, sends `X-CSRF-Token`) plus a text field to attach an existing media hash (checked with `media_exists`); thumbnails/links via `GET /media/{id}`. Unsaved uploads are safe (garbage collection has a 24 h grace).
- Executors: list, create from a zip upload (`file_rules.read_zip`) or from a starter (`starters`), edit name and `note_schema` (JSON textarea, validated), replace files (zip), delete (a `Conflict` when notes use it is shown as a message), file listing.
- Media serving: `GET /media/{id}` returns the bytes with `core.SANDBOX_HEADERS`, `Content-Disposition: attachment` and the stored mime type, always.
- Packages: export selected decks as a download (`dunzo-package.zip`), import by upload with a result report page.
- Settings and review UI are not yours. Escape all user content (Jinja autoescape on); all state-changing forms carry the hidden `csrf_token`.
- This is a large component: you are expected to split (§9 rule 4), e.g. `i1` decks and notes pages (including the note editor), `i2` executors pages, `i3` media and packages pages. You own the shared layout/base template, static files and the combined router; children contribute routers/templates inside their own directories. The split must not alter §4. Write tests with `fastapi.testclient` and fakes or a real `Content`/`Progress` on a temp database (stub middleware sets `request.state.csrf_token`).

## 3. Non-responsibilities (owned elsewhere; do NOT build or reason about them)
- Review sessions, settings, backup pages, executor frames (`review`).
- Persistence, validation rules, zip/package formats (`content`, `file_rules`, `packages`).
- CSRF/Host enforcement, error pages, app wiring (`app`).

## 4. Public API you provide
Contract version: v1. Do not change without parent approval.
### `dunzo.manage` (owner: agent `i`)
```python
router: fastapi.APIRouter      # full paths, no prefix; included by `app`
```
HTTP surface (in addition to the HTML pages you design under `/decks…`, `/notes…`, `/executors…`, `/packages…`):
- `POST /media/upload` — multipart field `file`; returns JSON `{"id", "mime", "size"}` (a `core.Invalid` for empty/oversized files becomes HTTP 422 via `app`).
- `GET /media/{id}` — the bytes with `core.SANDBOX_HEADERS`, `Content-Disposition: attachment`, stored mime type.
- `GET /packages/export?deck=<id>&deck=<id>` — downloads `dunzo-package.zip`; `POST /packages/import` — multipart field `file`, renders an import report.
- `GET /manage-static/{path}` — your static files (including vendored `htmx.min.js`).
- Every HTML page includes the hidden field `csrf_token` in state-changing forms (value `request.state.csrf_token`).

## 5. APIs you consume
Black boxes. Use exactly as written. Do not look inside.
(provider: e)
### `dunzo.content` (contract v1; owner: agent `e`). Content tables only (deck, executor, executor_file, note, media, note_media) plus the blob stores under `data_dir/blobs/{media,executor}/`.
```python
MIGRATIONS: MigrationSet            # owner "content"; creates the content tables exactly as in the schema contract
UNSET: Final                         # sentinel meaning "leave unchanged" (for nullable arguments)
@dataclass(frozen=True) class Deck: id: str; name: str; parent_id: str | None
@dataclass(frozen=True) class DeckSummary: id: str; name: str; parent_id: str | None; note_count: int
@dataclass(frozen=True) class Executor: id: str; name: str; files_hash: str; note_schema: dict | None
@dataclass(frozen=True) class ExecutorSummary: id: str; name: str; note_count: int; file_count: int
@dataclass(frozen=True) class MediaInfo: id: str; mime: str; size: int          # id = sha256 hex of the bytes
@dataclass(frozen=True) class Note:
    id: str; deck_id: str; executor_id: str; card_count: int; position: int
    properties: dict; media_list: tuple[MediaInfo, ...]; created_at: datetime; updated_at: datetime
@dataclass(frozen=True) class StoredFile: meta: FileMeta; path: Path           # path of the bytes on disk
@dataclass(frozen=True) class StoredMedia: info: MediaInfo; path: Path
@dataclass(frozen=True) class GcReport: media_deleted: int; executor_blobs_deleted: int; bytes_freed: int
class Content:
    def __init__(self, conn: sqlite3.Connection, data_dir: Path, max_media_bytes: int = 20 * 1024 * 1024): ...
    # Every method raises NotFound for unknown ids and Invalid(details["problems"]) for bad input, unless stated.
    # Every writing method is atomic and safe to call inside an outer core.transaction.
    # --- decks
    def create_deck(self, name: str, *, parent_id: str | None = None) -> Deck
    def get_deck(self, deck_id: str) -> Deck
    def list_decks(self) -> list[DeckSummary]                       # ordered by name
    def rename_deck(self, deck_id: str, name: str) -> Deck
    def delete_deck(self, deck_id: str) -> None                     # deletes its notes (and, by cascade, any progress); media left for GC
    # --- executors
    def create_executor(self, name: str, files: Sequence[FileEntry], *, note_schema: dict | None = None,
                        id: str | None = None, now: datetime) -> Executor
        # files checked with file_rules.validate_files (FileRuleError -> Invalid); note_schema must itself be a valid
        # JSON Schema (jsonschema, Draft 2020-12); explicit `id` already in use -> Conflict
    def replace_executor_files(self, executor_id: str, files: Sequence[FileEntry], *, now: datetime) -> Executor
    def update_executor(self, executor_id: str, *, name: str | None = None, note_schema: dict | None | UNSET = UNSET) -> Executor
    def delete_executor(self, executor_id: str) -> None             # Conflict if any note uses it
    def find_executor(self, executor_id: str) -> Executor | None
    def get_executor(self, executor_id: str) -> Executor
    def list_executors(self) -> list[ExecutorSummary]               # ordered by name
    def list_executor_files(self, executor_id: str) -> list[FileMeta]
    def open_executor_file(self, executor_id: str, path: str) -> StoredFile   # exact path match in executor_file, else NotFound
    # --- media
    def put_media(self, data: bytes, filename: str, *, now: datetime) -> MediaInfo
        # Invalid if empty or larger than max_media_bytes; id = sha256; mime = file_rules.detect_media_mime(filename, data[:512]);
        # idempotent; re-putting existing media refreshes its created_at (so it survives garbage collection)
    def get_media(self, media_id: str) -> MediaInfo
    def media_exists(self, media_id: str) -> bool
    def open_media(self, media_id: str) -> StoredMedia
    def open_note_media(self, note_id: str, media_id: str) -> StoredMedia    # NotFound unless that media is linked to that note
    # --- notes
    def create_note(self, deck_id: str, executor_id: str, properties: dict, card_count: int, *,
                    media_ids: Sequence[str] = (), now: datetime) -> Note
        # appended at the end of the deck; 1 <= card_count <= 10000; properties validated against the executor's note_schema
        # when it has one; every media id must exist (else Invalid)
    def get_note(self, note_id: str) -> Note
    def list_notes(self, deck_id: str) -> list[Note]                # ordered by position
    def update_note(self, note_id: str, *, properties: dict | None = None, executor_id: str | None = None,
                    card_count: int | None = None, media_ids: Sequence[str] | None = None, now: datetime) -> Note
        # only the given fields change; properties are revalidated against the (possibly new) executor's schema.
        # Never touches progress and never warns about a shrinking card_count (the caller does both)
    def move_note(self, note_id: str, deck_id: str, *, now: datetime) -> Note       # to the end of that deck
    def reorder_note(self, note_id: str, after_note_id: str | None, *, now: datetime) -> Note   # same deck; None = first
    def delete_note(self, note_id: str) -> None
    # --- maintenance
    def collect_garbage(self, now: datetime, grace: timedelta = timedelta(hours=24)) -> GcReport
        # deletes media rows with no note_media link and created_at older than `grace`, with their bytes; deletes executor
        # blobs referenced by no executor_file and older than `grace` (file mtime)
```
Invariants: positions in a deck are unique, increasing, spaced 1024 apart, renumbered by the content layer when a gap runs out; bytes are written before rows commit (a crash may leave orphan blobs, which GC removes); blob paths never derive from user-supplied strings.
Example: `c = Content(conn, data_dir); d = c.create_deck("Spanish"); n = c.create_note(d.id, ex.id, {"front": "hola", "back": "hello"}, 2, now=now)`.

(provider: d)
### `dunzo.schema_forms` (contract v1; owner: agent `d`). Pure.
Supported JSON Schema subset (`is_supported` is true iff all hold): root `type: object` with `properties`; every property (recursively) is `string` (optional `enum`; `x-widget: "textarea"` selects a textarea), `integer`, `number`, `boolean`, `object` (with `properties`) or `array` whose `items` is one of those; `title`, `description`, `default` and object-level `required` are used; other validation keywords (min/max, pattern, ...) are ignored here (the caller validates with jsonschema); no `$ref`, `oneOf`/`anyOf`/`allOf`.
```python
FieldKind = Literal["text", "textarea", "integer", "number", "boolean", "select", "object", "array"]
@dataclass(frozen=True) class FormField:
    name: str; label: str; kind: FieldKind; required: bool; description: str
    value: Any                       # current scalar value (None if unset or for object/array)
    options: tuple[str, ...]         # for select
    items: tuple["FormField", ...]   # object: child fields; array: existing item fields named f"{name}.{i}"
    new_item: "FormField | None"     # arrays only: a blank item named f"{name}.{len(items)}"
@dataclass(frozen=True) class FormModel: fields: tuple[FormField, ...]
@dataclass(frozen=True) class ParseResult: values: dict[str, Any]; errors: dict[str, str]   # errors keyed by field name
class SchemaFormError(ValueError): ...
def is_supported(schema: dict) -> bool
def build_form(schema: dict, values: dict | None = None) -> FormModel    # SchemaFormError if unsupported
def parse_form(schema: dict, submitted: Mapping[str, str]) -> ParseResult
```
Naming: property `b` of object `a` is `a.b`; array item `i` of `a` is `a.i`; object item in an array: `a.0.b`. Parsing: values are strings; for non-required fields an empty/absent value omits the key; boolean: absent = false, `on`/`true` = true; required and empty -> error; integers/numbers parsed strictly; array = items whose index is present, in index order, skipping items whose fields are all empty. Labels default to the property name (or `title`).

(provider: c)
### `dunzo.file_rules` (contract v1; owner: agent `c`). Pure: no filesystem, database or network access.
```python
MAX_FILES = 500; MAX_FILE_BYTES = 20 * 1024 * 1024; MAX_TOTAL_BYTES = 100 * 1024 * 1024
RESERVED_DIR = "dunzo"; INDEX_FILE = "index.html"
DENIED_EXTENSIONS: frozenset[str]   # lowercase with dot: .exe .dll .so .dylib .sh .bat .cmd .ps1 .php .py .pl .rb .jar .msi .scr .com .vbs
class FileRuleError(ValueError): problems: list[str]
@dataclass(frozen=True) class FileEntry: path: str; data: bytes
@dataclass(frozen=True) class FileMeta: path: str; hash: str; mime: str; size: int   # hash = sha256 hex
def sha256_hex(data: bytes) -> str
def normalize_path(path: str) -> str      # segments of [A-Za-z0-9._\-@+=~], "/"-separated, no empty/"."/".." segment, no leading "/" or "\"; returns path or raises FileRuleError
def guess_mime(path: str) -> str          # by extension from a fixed table; unknown -> "application/octet-stream"
def detect_media_mime(filename: str, head: bytes) -> str   # extension table first, then magic bytes of `head` (png jpeg gif webp mp3 ogg wav mp4 webm pdf); else "application/octet-stream"; never raises
def read_zip(data: bytes) -> list[FileEntry]
    # strips one common top-level folder if every entry is under it; skips directory entries.
    # Raises FileRuleError for: unsafe paths (absolute, "..", backslash), symlinks, encrypted entries, duplicate paths,
    # more than MAX_FILES entries, any file or the total over the limits (checked from headers AND while inflating), corrupt zip
def validate_files(files: Sequence[FileEntry]) -> list[FileMeta]
    # sorted by path; enforces path rules, no empty files, per-file/total/count limits, INDEX_FILE present at top level,
    # nothing at or under RESERVED_DIR, no DENIED_EXTENSIONS; collects all problems into one FileRuleError
def files_hash(metas: Sequence[FileMeta]) -> str   # sha256 hex over "\n".join(f"{m.path}\0{m.hash}") of metas sorted by path (UTF-8)
```
Example: `metas = validate_files(read_zip(zip_bytes)); h = files_hash(metas)`.

(provider: k)
### `dunzo.starters` (contract v1; owner: agent `k`). Pure, no dependencies on other components.
```python
@dataclass(frozen=True) class Starter:
    key: str; name: str; description: str
    note_schema: dict                  # JSON Schema in the schema_forms-supported subset
    default_card_count: int
    files: Mapping[str, bytes]         # path -> bytes; includes "index.html"; no path starts with "dunzo/"
def list_starters() -> list[Starter]   # at least the two below, in this order
def get_starter(key: str) -> Starter   # raises KeyError if unknown
```
Required starters: `basic` ("Basic", default_card_count 1) and `basic-reversed` ("Basic and reversed", default_card_count 2). Both share the same files. Note schema: `front` and `back` (required strings, textarea), `front_media` and `back_media` (optional strings: a media hash from `card.note.media`). Card index 0 asks `front` and reveals `back`; index 1 asks `back` and reveals `front`.

(provider: h)
### `dunzo.packages` (contract v1; owner: agent `h`). Library only (no routes). Uses `Content` only; never imports progress.
```python
PACKAGE_FORMAT = "dunzo-package"; PACKAGE_VERSION = 1
@dataclass(frozen=True) class ExportReport: decks: int; notes: int; executors: int; media: int; bytes: int
@dataclass(frozen=True) class ImportedDeck: id: str; name: str; notes: int
@dataclass(frozen=True) class ImportReport:
    decks: tuple[ImportedDeck, ...]; notes: int; executors_created: int; executors_reused: int
    executors_remapped: int; media_added: int
class Packages:
    def __init__(self, content: Content): ...
    def export_decks(self, deck_ids: Sequence[str], out: BinaryIO) -> ExportReport
        # writes a zip to `out`; NotFound for an unknown deck; contains content only (decks, ordered notes, the executors they use, linked media)
    def import_package(self, src: BinaryIO, *, now: datetime, max_bytes: int = 2 * 1024**3) -> ImportReport
        # all-or-nothing (one core.transaction); Invalid for a corrupt, oversized, unsupported or inconsistent package.
        # New decks and notes get new ids and keep their order. Executor rule: unknown id -> created with that id;
        # same id and same files_hash -> reused; same id but different files_hash -> created under a new id and the imported notes remapped.
```
Example: `buf = io.BytesIO(); Packages(content).export_decks([deck.id], buf); report = Packages(content).import_package(buf, now=now)`.

(provider: f)
### `dunzo.progress` — the subset the management UI uses (contract v1; excerpt of the full contract)
```python
@dataclass(frozen=True) class ProgressSummary: card_states: int; reviews: int
class Progress:
    def __init__(self, conn: sqlite3.Connection): ...
    def summary_for_note(self, note_id: str, *, from_index: int = 0) -> ProgressSummary   # cards with card_index >= from_index
    def summary_for_deck(self, deck_id: str) -> ProgressSummary
    def delete_from_index(self, note_id: str, from_index: int) -> int   # removes progress rows with card_index >= from_index; returns card_state rows removed
```
Rule for callers: before shrinking a note's card_count, or deleting a note or deck, call the summary; if it is non-zero, require explicit user confirmation first. Wrap the content change and any `delete_from_index` in one `core.transaction`.

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
- Code directory (project-root-relative): src/dunzo/manage/    Docs directory: .hierarchy/i/
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
- [ ] Every page and endpoint in §2 works against the real `Content`, `Progress` and `Packages` on a temp database; tests cover the confirmation flows, editor validation, media upload and attach, executor create from zip and starter, export/import.
- [ ] All responses escape user content; every POST form has the csrf field; `GET /media/{id}` carries the sandbox headers and `attachment`.
- [ ] `uv run ruff check src/dunzo/manage` is clean; no SQL; no import of `dunzo.review_queue` or `dunzo.scheduler`.

## 8. Report requirements
Beyond the standard report format, the parent specifically needs: the child tree if you split; template/static layout; anything in the consumed contracts that made the UI awkward (suggest changes as REQs, not workarounds).

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
