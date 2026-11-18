"""Constants, value types and path rules for uploaded files (contract v1)."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass

MAX_FILES = 500
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 100 * 1024 * 1024
RESERVED_DIR = "dunzo"
INDEX_FILE = "index.html"
DENIED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".exe", ".dll", ".so", ".dylib", ".sh", ".bat", ".cmd", ".ps1", ".php",
        ".py", ".pl", ".rb", ".jar", ".msi", ".scr", ".com", ".vbs",
    }
)  # fmt: skip

_SEGMENT_RE = re.compile(r"[A-Za-z0-9._\-@+=~]+")
_MAX_PROBLEMS = 100


def quote(text: str) -> str:
    """Short, repr-escaped form of untrusted text for use in messages."""
    shown = text if len(text) <= 80 else text[:77] + "..."
    return repr(shown)


class FileRuleError(ValueError):
    """An upload broke a file rule. ``problems`` lists every problem found."""

    problems: list[str]

    def __init__(self, problems: Sequence[str] | str) -> None:
        listed = [problems] if isinstance(problems, str) else list(problems)
        if not listed:
            listed = ["invalid file set"]
        if len(listed) > _MAX_PROBLEMS:
            extra = len(listed) - _MAX_PROBLEMS
            listed = [*listed[:_MAX_PROBLEMS], f"... and {extra} more problems"]
        self.problems = listed
        head = "; ".join(listed[:10])
        more = f" (and {len(listed) - 10} more)" if len(listed) > 10 else ""
        super().__init__(head + more)


@dataclass(frozen=True)
class FileEntry:
    path: str
    data: bytes


@dataclass(frozen=True)
class FileMeta:
    path: str
    hash: str  # sha256 hex
    mime: str
    size: int


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def path_problems(path: str) -> list[str]:
    """Return every reason ``path`` breaks the path rules (empty list if it is fine)."""
    if not isinstance(path, str) or path == "":
        return ["path is empty"]
    problems: list[str] = []
    if path[0] in "/\\":
        problems.append("must not start with '/' or '\\'")
    rest = path.lstrip("/\\")
    if rest == "":
        return problems
    for segment in rest.split("/"):
        if segment == "":
            problems.append("has an empty segment")
        elif segment in (".", ".."):
            problems.append(f"has a {segment!r} segment")
        elif _SEGMENT_RE.fullmatch(segment) is None:
            problems.append(f"segment {quote(segment)} has characters outside [A-Za-z0-9._-@+=~]")
    return problems


def normalize_path(path: str) -> str:
    """Return ``path`` unchanged if it obeys the path rules, else raise FileRuleError."""
    problems = path_problems(path)
    if problems:
        label = quote(path) if isinstance(path, str) else "path"
        raise FileRuleError([f"{label}: {p}" for p in problems])
    return path
