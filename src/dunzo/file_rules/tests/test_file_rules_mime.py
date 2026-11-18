import pytest

from dunzo.file_rules import detect_media_mime, guess_mime

OCTET = "application/octet-stream"

TABLE = {
    "html": "text/html", "css": "text/css", "js": "text/javascript",
    "mjs": "text/javascript", "json": "application/json", "svg": "image/svg+xml",
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif",
    "webp": "image/webp", "avif": "image/avif", "ico": "image/x-icon",
    "woff": "font/woff", "woff2": "font/woff2", "ttf": "font/ttf", "otf": "font/otf",
    "mp3": "audio/mpeg", "ogg": "audio/ogg", "wav": "audio/wav", "m4a": "audio/mp4",
    "mp4": "video/mp4", "webm": "video/webm", "txt": "text/plain", "md": "text/markdown",
    "xml": "application/xml", "csv": "text/csv", "wasm": "application/wasm",
    "pdf": "application/pdf",
}  # fmt: skip


@pytest.mark.parametrize(("ext", "mime"), sorted(TABLE.items()))
def test_guess_mime_table(ext, mime):
    assert guess_mime(f"dir/file.{ext}") == mime
    assert guess_mime(f"FILE.{ext.upper()}") == mime


@pytest.mark.parametrize("path", ["noext", "a.unknown", "a/b.", ".js", "dir.js/file", ""])
def test_guess_mime_unknown(path):
    assert guess_mime(path) == OCTET


MAGIC = [
    (b"\x89PNG\r\n\x1a\n\x00\x00", "image/png"),
    (b"\xff\xd8\xff\xe0\x00\x10JFIF", "image/jpeg"),
    (b"GIF89a\x01\x00", "image/gif"),
    (b"GIF87a\x01\x00", "image/gif"),
    (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp"),
    (b"RIFF\x00\x00\x00\x00WAVEfmt ", "audio/wav"),
    (b"ID3\x04\x00\x00\x00\x00\x00\x00", "audio/mpeg"),
    (b"\xff\xfb\x90\x00" + b"\x00" * 12, "audio/mpeg"),
    (b"OggS\x00\x02" + b"\x00" * 10, "audio/ogg"),
    (b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00", "video/mp4"),
    (b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00", "audio/mp4"),
    (b"\x1a\x45\xdf\xa3\x01\x00\x00\x00", "video/webm"),
    (b"%PDF-1.7\n", "application/pdf"),
]


@pytest.mark.parametrize(("head", "mime"), MAGIC)
def test_detect_by_magic(head, mime):
    assert detect_media_mime("upload.bin", head) == mime
    assert detect_media_mime("noextension", head) == mime


def test_extension_wins_over_magic():
    assert detect_media_mime("a.png", b"%PDF-1.7") == "image/png"


def test_detect_unknown_and_never_raises():
    assert detect_media_mime("x.bin", b"hello world") == OCTET
    assert detect_media_mime("x.bin", b"") == OCTET
    assert detect_media_mime("", b"") == OCTET
    assert detect_media_mime("a\x00b", b"\xff") == OCTET
    assert detect_media_mime("x.bin", bytearray(b"%PDF-")) == "application/pdf"
    assert detect_media_mime(None, b"abc") == OCTET  # type: ignore[arg-type]
    assert detect_media_mime("x.bin", None) == OCTET  # type: ignore[arg-type]
