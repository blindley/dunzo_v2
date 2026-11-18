"""Hostile-archive-safe zip reading."""

from __future__ import annotations

import io
import logging
import lzma
import re
import stat
import struct
import zipfile
import zlib

from ._types import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    FileEntry,
    FileRuleError,
    quote,
)

log = logging.getLogger("dunzo.file_rules")

_CHUNK = 64 * 1024
_MAX_RAW_ENTRIES = MAX_FILES * 4  # files plus folder entries; bounds central-directory work
_MAX_CENTRAL_DIR_BYTES = 4 * 1024 * 1024
_EOCD = b"PK\x05\x06"
_EOCD_LEN = 22
_ZIP_ERRORS = (
    zipfile.BadZipFile,
    zipfile.LargeZipFile,
    NotImplementedError,
    RuntimeError,
    zlib.error,
    lzma.LZMAError,
    EOFError,
    OSError,
    ValueError,
    struct.error,
)
_DRIVE_RE = re.compile(r"[A-Za-z]:")


class _LimitError(Exception):
    """Raised while inflating when a size limit is crossed; ``kind`` is 'file' or 'total'."""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


def _declared_directory(data: bytes) -> tuple[int, int] | None:
    """Entry count and central-directory size as declared by the end record, if findable."""
    pos = data.rfind(_EOCD, max(0, len(data) - _EOCD_LEN - 0xFFFF))
    if pos < 0 or pos + _EOCD_LEN > len(data):
        return None
    total, cd_size = struct.unpack_from("<HI", data, pos + 10)
    if total != 0xFFFF and cd_size != 0xFFFFFFFF:
        return total, cd_size
    loc = pos - 20  # zip64 end-record locator
    if loc < 0 or data[loc : loc + 4] != b"PK\x06\x07":
        return total, cd_size
    (rec,) = struct.unpack_from("<Q", data, loc + 8)
    if rec + 56 > len(data) or data[rec : rec + 4] != b"PK\x06\x06":
        return total, cd_size
    total64, cd_size64 = struct.unpack_from("<QQ", data, rec + 32)
    return total64, cd_size64


def _unsafe_reason(name: str) -> str | None:
    if name == "":
        return "has an empty name"
    if "\\" in name:
        return "contains a backslash"
    if name.startswith("/"):
        return "is an absolute path"
    if _DRIVE_RE.match(name):
        return "starts with a drive letter"
    if ".." in name.split("/"):
        return "contains a '..' segment"
    return None


def _common_folder(infos: list[zipfile.ZipInfo]) -> str:
    """Prefix ('name/') of the single top-level folder holding every entry, else ''."""
    names = [i.filename for i in infos]
    files = [i.filename for i in infos if not i.is_dir()]
    if not files or any("/" not in n for n in files):
        return ""
    firsts = {n.split("/", 1)[0] for n in names}
    if len(firsts) != 1:
        return ""
    (first,) = firsts
    if first in ("", ".", "..") or "\\" in first:
        return ""
    return first + "/"


def _check_declared_sizes(files: list[zipfile.ZipInfo], problems: list[str]) -> None:
    declared_total = 0
    for info in files:
        declared_total += info.file_size
        if info.file_size > MAX_FILE_BYTES:
            problems.append(
                f"{quote(info.filename)}: declares {info.file_size} bytes, "
                f"over the {MAX_FILE_BYTES} byte file limit"
            )
    if declared_total > MAX_TOTAL_BYTES:
        problems.append(
            f"archive declares {declared_total} bytes in total, "
            f"over the {MAX_TOTAL_BYTES} byte limit"
        )


def _inflate_entry(
    zf: zipfile.ZipFile, info: zipfile.ZipInfo, file_limit: int, total_left: int
) -> bytes:
    """Inflate one entry in bounded chunks, stopping as soon as a limit is crossed."""
    buf = bytearray()
    with zf.open(info) as fh:
        while chunk := fh.read(_CHUNK):
            buf += chunk
            if len(buf) > file_limit:
                raise _LimitError("file")
            if len(buf) > total_left:
                raise _LimitError("total")
    return bytes(buf)


def read_zip(data: bytes) -> list[FileEntry]:
    """Read an uploaded zip safely and return its files (archive order).

    Strips one common top-level folder if every entry is under it; skips folder entries.
    Raises FileRuleError listing every problem found.
    """
    declared = _declared_directory(data)
    if declared is not None and (
        declared[0] > _MAX_RAW_ENTRIES or declared[1] > _MAX_CENTRAL_DIR_BYTES
    ):
        raise FileRuleError(
            f"zip declares too many entries ({declared[0]}); at most {MAX_FILES} files are allowed"
        )
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except _ZIP_ERRORS as exc:
        raise FileRuleError(f"not a valid zip archive: {exc}") from None

    with zf:
        try:
            infos = zf.infolist()
        except _ZIP_ERRORS as exc:  # pragma: no cover - defensive
            raise FileRuleError(f"not a valid zip archive: {exc}") from None
        if len(infos) > _MAX_RAW_ENTRIES:
            raise FileRuleError(
                f"zip has too many entries ({len(infos)}); at most {MAX_FILES} files are allowed"
            )
        files = [i for i in infos if not i.is_dir()]
        problems: list[str] = []
        if len(files) > MAX_FILES:
            problems.append(f"too many files: {len(files)} (at most {MAX_FILES})")

        prefix = _common_folder(infos)
        paths: dict[int, str] = {}
        seen: set[str] = set()
        reported_dupes: set[str] = set()
        for info in infos:
            raw = info.filename
            path = raw[len(prefix) :] if prefix and raw.startswith(prefix) else raw
            reason = _unsafe_reason(raw)
            if reason is None and path not in (raw, ""):  # "" is the stripped wrapper folder
                reason = _unsafe_reason(path)
            if reason is not None:
                problems.append(f"{quote(raw)}: {reason}")
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                problems.append(f"{quote(raw)}: is a symbolic link")
            elif (
                info.create_system == 3
                and not info.is_dir()
                and stat.S_IFMT(mode) not in (0, stat.S_IFREG)
            ):
                problems.append(f"{quote(raw)}: is a special file, not a regular file")
            if info.is_dir():
                continue
            if info.flag_bits & 0x1:
                problems.append(f"{quote(raw)}: is encrypted")
            if path in seen and path not in reported_dupes:
                reported_dupes.add(path)
                problems.append(f"{quote(path)}: duplicate path in archive")
            seen.add(path)
            paths[id(info)] = path

        _check_declared_sizes(files, problems)
        if problems:
            log.debug("rejected zip at header stage: %d problems", len(problems))
            raise FileRuleError(problems)

        entries: list[FileEntry] = []
        total = 0
        for info in files:
            label = quote(info.filename)
            try:
                content = _inflate_entry(zf, info, MAX_FILE_BYTES, MAX_TOTAL_BYTES - total)
            except _LimitError as exc:
                if exc.kind == "total":
                    problems.append(f"archive inflates past the {MAX_TOTAL_BYTES} byte total limit")
                    break
                problems.append(f"{label}: inflates past the {MAX_FILE_BYTES} byte file limit")
                total += MAX_FILE_BYTES
                continue
            except _ZIP_ERRORS as exc:
                problems.append(f"{label}: corrupt entry ({exc})")
                continue
            if len(content) != info.file_size:
                problems.append(f"{label}: inflated size differs from the size in the header")
                continue
            total += len(content)
            entries.append(FileEntry(path=paths[id(info)], data=content))

        if problems:
            log.debug("rejected zip while inflating: %d problems", len(problems))
            raise FileRuleError(problems)
        return entries
