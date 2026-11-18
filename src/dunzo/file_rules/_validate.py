"""Whole-file-set validation and the file-set hash."""

from __future__ import annotations

from collections.abc import Sequence

from ._mime import guess_mime
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
    path_problems,
    quote,
    sha256_hex,
)


def validate_files(files: Sequence[FileEntry]) -> list[FileMeta]:
    """Check a file set against every rule; return metas sorted by path.

    All problems found are collected into a single FileRuleError.
    """
    problems: list[str] = []
    if len(files) > MAX_FILES:
        problems.append(f"too many files: {len(files)} (at most {MAX_FILES})")

    seen: set[str] = set()
    good_paths: set[str] = set()
    reported_dupes: set[str] = set()
    total = 0
    for entry in files:
        label = quote(entry.path)
        bad = path_problems(entry.path)
        problems.extend(f"{label}: {p}" for p in bad)
        if entry.path in seen and entry.path not in reported_dupes:
            reported_dupes.add(entry.path)
            problems.append(f"{label}: duplicate path")
        seen.add(entry.path)

        size = len(entry.data)
        total += size
        if size == 0:
            problems.append(f"{label}: file is empty")
        if size > MAX_FILE_BYTES:
            problems.append(f"{label}: {size} bytes exceeds the {MAX_FILE_BYTES} byte file limit")
        if bad:
            continue
        good_paths.add(entry.path)
        if entry.path.split("/")[0].casefold() == RESERVED_DIR:
            problems.append(f"{label}: '{RESERVED_DIR}' is a reserved name")
        lowered = entry.path.lower()
        denied = next((e for e in sorted(DENIED_EXTENSIONS) if lowered.endswith(e)), None)
        if denied is not None:
            problems.append(f"{label}: files ending in {denied} are not allowed")

    if total > MAX_TOTAL_BYTES:
        problems.append(f"total size {total} bytes exceeds the {MAX_TOTAL_BYTES} byte limit")
    if INDEX_FILE not in good_paths:
        problems.append(f"missing {INDEX_FILE} at the top level")

    folders = {"/".join(p.split("/")[:i]) for p in good_paths for i in range(1, p.count("/") + 1)}
    for clash in sorted(good_paths & folders):
        problems.append(f"{quote(clash)}: is both a file and a folder")

    if problems:
        raise FileRuleError(problems)

    metas = [
        FileMeta(path=e.path, hash=sha256_hex(e.data), mime=guess_mime(e.path), size=len(e.data))
        for e in files
    ]
    metas.sort(key=lambda m: m.path)
    return metas


def files_hash(metas: Sequence[FileMeta]) -> str:
    """sha256 hex over path/hash pairs sorted by path; independent of input order."""
    ordered = sorted(metas, key=lambda m: m.path)
    joined = "\n".join(f"{m.path}\0{m.hash}" for m in ordered)
    return sha256_hex(joined.encode("utf-8"))
