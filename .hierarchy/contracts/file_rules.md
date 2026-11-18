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
