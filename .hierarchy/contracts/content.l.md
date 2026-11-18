### `dunzo.content` — the parts the app shell uses (contract v1; excerpt of the full contract)
```python
MIGRATIONS: MigrationSet            # owner "content"
@dataclass(frozen=True) class GcReport: media_deleted: int; executor_blobs_deleted: int; bytes_freed: int
class Content:
    def __init__(self, conn: sqlite3.Connection, data_dir: Path, max_media_bytes: int = 20 * 1024 * 1024): ...
    def collect_garbage(self, now: datetime, grace: timedelta = timedelta(hours=24)) -> GcReport
```
