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
