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
