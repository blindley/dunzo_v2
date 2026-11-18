"""Media type lookup by extension and by magic bytes."""

from __future__ import annotations

_OCTET = "application/octet-stream"

_MIME_BY_EXT: dict[str, str] = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".xml": "application/xml",
    ".csv": "text/csv",
    ".wasm": "application/wasm",
    ".pdf": "application/pdf",
}


def _extension(name: str) -> str:
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    dot = base.rfind(".")
    return base[dot:].lower() if dot > 0 else ""


def guess_mime(path: str) -> str:
    """Media type by extension from a fixed table; unknown -> application/octet-stream."""
    try:
        return _MIME_BY_EXT.get(_extension(path), _OCTET)
    except (AttributeError, TypeError):
        return _OCTET


def _sniff(head: bytes) -> str:
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "audio/wav"
    if head.startswith(b"OggS"):
        return "audio/ogg"
    if head.startswith(b"ID3") or (
        len(head) >= 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0 and (head[1] >> 1) & 3 != 0
    ):
        return "audio/mpeg"
    if head[4:8] == b"ftyp":
        return "audio/mp4" if head[8:12] in (b"M4A ", b"M4B ") else "video/mp4"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    return _OCTET


def detect_media_mime(filename: str, head: bytes) -> str:
    """Extension table first, then magic bytes of ``head``; never raises."""
    try:
        by_ext = _MIME_BY_EXT.get(_extension(filename))
        if by_ext is not None:
            return by_ext
        return _sniff(bytes(head[:16]))
    except (AttributeError, TypeError, ValueError):
        return _OCTET
