"""Pure rules for uploaded files (contract v1; owner: agent ``c``).

No filesystem, database or network access.
"""

from ._archive import read_zip
from ._mime import detect_media_mime, guess_mime
from ._types import (
    DENIED_EXTENSIONS,
    INDEX_FILE,
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    RESERVED_DIR,
    FileEntry,
    FileMeta,
    FileRuleError,
    normalize_path,
    sha256_hex,
)
from ._validate import files_hash, validate_files

__all__ = [
    "DENIED_EXTENSIONS",
    "INDEX_FILE",
    "MAX_FILES",
    "MAX_FILE_BYTES",
    "MAX_TOTAL_BYTES",
    "RESERVED_DIR",
    "FileEntry",
    "FileMeta",
    "FileRuleError",
    "detect_media_mime",
    "files_hash",
    "guess_mime",
    "normalize_path",
    "read_zip",
    "sha256_hex",
    "validate_files",
]
