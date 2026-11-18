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
