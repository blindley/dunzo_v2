import io
import stat
import struct
import warnings
import zipfile

import pytest

from dunzo.file_rules import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    FileEntry,
    FileRuleError,
    _archive,
    files_hash,
    read_zip,
    validate_files,
)


def make_zip(entries, compression=zipfile.ZIP_DEFLATED, infos=None) -> bytes:
    """entries: list of (name, bytes); infos: ready-made ZipInfo objects written as given."""
    buf = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # duplicate names warn
        with zipfile.ZipFile(buf, "w", compression) as zf:
            for name, content in entries:
                info = zipfile.ZipInfo(name)
                info.compress_type = compression
                zf.writestr(info, content)
            for info, content in infos or []:
                zf.writestr(info, content)
    return buf.getvalue()


def rejected(data: bytes) -> list[str]:
    with pytest.raises(FileRuleError) as exc:
        read_zip(data)
    return exc.value.problems


def as_dict(entries: list[FileEntry]) -> dict[str, bytes]:
    return {e.path: e.data for e in entries}


# ---------------------------------------------------------------- valid archives


def test_flat_zip():
    data = make_zip([("index.html", b"<h1>"), ("css/a.css", b"body{}")])
    assert as_dict(read_zip(data)) == {"index.html": b"<h1>", "css/a.css": b"body{}"}


def test_folder_wrapped_zip_is_stripped_and_dirs_skipped():
    data = make_zip(
        [("deck/", b""), ("deck/index.html", b"<h1>"), ("deck/css/", b""), ("deck/css/a.css", b"x")]
    )
    assert as_dict(read_zip(data)) == {"index.html": b"<h1>", "css/a.css": b"x"}


def test_wrapper_without_explicit_dir_entry_is_stripped():
    data = make_zip([("deck/index.html", b"a"), ("deck/b.js", b"b")])
    assert set(as_dict(read_zip(data))) == {"index.html", "b.js"}


def test_only_one_folder_level_is_stripped():
    data = make_zip([("a/b/index.html", b"a"), ("a/b/c.js", b"b")])
    assert set(as_dict(read_zip(data))) == {"b/index.html", "b/c.js"}


def test_not_stripped_when_something_is_outside_the_folder():
    data = make_zip([("deck/index.html", b"a"), ("other.js", b"b")])
    assert set(as_dict(read_zip(data))) == {"deck/index.html", "other.js"}
    data = make_zip([("deck/index.html", b"a"), ("other/x.js", b"b")])
    assert set(as_dict(read_zip(data))) == {"deck/index.html", "other/x.js"}


def test_bare_end_record_is_a_valid_empty_archive():
    assert read_zip(b"PK\x05\x06" + b"\0" * 18) == []


def test_stored_and_empty_entries_and_empty_archive():
    data = make_zip([("index.html", b"hi"), ("e.txt", b"")], compression=zipfile.ZIP_STORED)
    assert as_dict(read_zip(data)) == {"index.html": b"hi", "e.txt": b""}
    assert read_zip(make_zip([])) == []


def test_example_pipeline_is_deterministic():
    one = make_zip([("w/index.html", b"<p>"), ("w/a.js", b"1")])
    two = make_zip([("a.js", b"1"), ("index.html", b"<p>")])  # flat, different order
    assert files_hash(validate_files(read_zip(one))) == files_hash(validate_files(read_zip(two)))


def test_spaces_and_unicode_names_pass_read_but_fail_validate():
    entries = read_zip(make_zip([("index.html", b"x"), ("my file.txt", b"y")]))
    with pytest.raises(FileRuleError):
        validate_files(entries)


# ---------------------------------------------------------------- hostile archives


@pytest.mark.parametrize(
    ("name", "needle"),
    [
        ("../evil.txt", ".."),
        ("a/../../evil.txt", ".."),
        ("a/b/../c.txt", ".."),
        ("/etc/passwd", "absolute"),
        ("C:/windows/x.txt", "drive"),
        ("a\\b.txt", "backslash"),
        ("..\\evil.txt", "backslash"),
    ],
)
def test_unsafe_paths(name, needle):
    problems = rejected(make_zip([("index.html", b"x"), (name, b"bad")]))
    assert any(needle in p for p in problems)


def test_traversal_hidden_behind_common_folder():
    assert any("'..'" in p for p in rejected(make_zip([("../a.txt", b"1"), ("../b.txt", b"2")])))
    assert any("'..'" in p for p in rejected(make_zip([("w/../a.txt", b"1"), ("w/b.txt", b"2")])))


def test_traversal_in_directory_entry():
    assert rejected(make_zip([("index.html", b"x"), ("../up/", b"")]))


def test_symlink_rejected():
    link = zipfile.ZipInfo("link.txt")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    problems = rejected(make_zip([("index.html", b"x")], infos=[(link, b"/etc/passwd")]))
    assert any("symbolic link" in p for p in problems)


def test_special_file_rejected():
    fifo = zipfile.ZipInfo("pipe")
    fifo.create_system = 3
    fifo.external_attr = (stat.S_IFIFO | 0o644) << 16
    assert rejected(make_zip([("index.html", b"x")], infos=[(fifo, b"x")]))


def test_regular_file_with_unix_mode_is_fine():
    info = zipfile.ZipInfo("index.html")
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    assert as_dict(read_zip(make_zip([], infos=[(info, b"ok")]))) == {"index.html": b"ok"}


def _patch(data: bytes, signature: bytes, offset: int, fmt: str, value: int) -> bytes:
    raw = bytearray(data)
    i = raw.find(signature)
    while i != -1:
        struct.pack_into(fmt, raw, i + offset, value)
        i = raw.find(signature, i + 4)
    return bytes(raw)


def test_encrypted_entry_rejected():
    raw = bytearray(make_zip([("index.html", b"plain"), ("s.txt", b"secret")], zipfile.ZIP_STORED))
    for sig, off in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        i = raw.find(sig)
        while i != -1:
            raw[i + off] |= 0x1
            i = raw.find(sig, i + 4)
    problems = rejected(bytes(raw))
    assert sum("encrypted" in p for p in problems) == 2


def test_duplicate_names_rejected():
    problems = rejected(make_zip([("index.html", b"1"), ("a.js", b"2"), ("a.js", b"3")]))
    assert any("duplicate" in p for p in problems)


def test_duplicate_after_stripping_wrapper():
    assert rejected(make_zip([("w/a.js", b"1"), ("w/a.js", b"2")]))


def test_declared_oversize_file():
    data = make_zip([("index.html", b"x"), ("big.bin", b"\0" * (MAX_FILE_BYTES + 1))])
    assert any("file limit" in p for p in rejected(data))


def test_declared_total_over_limit_is_rejected_without_inflating():
    chunk = b"\0" * (MAX_FILE_BYTES - 1024)
    n = MAX_TOTAL_BYTES // len(chunk) + 1
    data = make_zip([(f"f{i}.bin", chunk) for i in range(n)])
    assert len(data) < 1024 * 1024  # a classic zip bomb: tiny archive, huge content
    assert any("in total" in p for p in rejected(data))


def test_lying_header_smaller_than_content_is_rejected():
    data = make_zip([("index.html", b"x"), ("lie.bin", b"\0" * 1_000_000)])
    lied = _patch(data, b"PK\x01\x02", 24, "<I", 10)  # central directory says 10 bytes
    lied = _patch(lied, b"PK\x03\x04", 22, "<I", 10)
    assert rejected(lied)


def test_lying_header_declaring_huge_size_is_rejected():
    data = make_zip([("index.html", b"x")])
    lied = _patch(data, b"PK\x01\x02", 24, "<I", MAX_FILE_BYTES + 1)
    assert any("file limit" in p for p in rejected(lied))


def test_inflate_loop_stops_at_file_limit():
    data = make_zip([("a.bin", b"\0" * 1_000_000)])
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        info = zf.infolist()[0]
        with pytest.raises(_archive._LimitError) as exc:
            _archive._inflate_entry(zf, info, 1000, 10**9)
        assert exc.value.kind == "file"
        with pytest.raises(_archive._LimitError) as exc:
            _archive._inflate_entry(zf, info, 10**9, 1000)
        assert exc.value.kind == "total"
        assert len(_archive._inflate_entry(zf, info, 10**9, 10**9)) == 1_000_000


def test_read_zip_enforces_limits_while_inflating(monkeypatch):
    """With the header check disabled, the bounded inflate loop alone must catch oversize."""
    monkeypatch.setattr(_archive, "_check_declared_sizes", lambda files, problems: None)
    monkeypatch.setattr(_archive, "MAX_FILE_BYTES", 1000)
    assert any("file limit" in p for p in rejected(make_zip([("a.bin", b"\0" * 5000)])))
    monkeypatch.setattr(_archive, "MAX_FILE_BYTES", 1000)
    monkeypatch.setattr(_archive, "MAX_TOTAL_BYTES", 1500)
    data = make_zip([(f"f{i}.bin", b"\0" * 800) for i in range(5)])
    assert any("total limit" in p for p in rejected(data))


def test_file_exactly_at_limit_is_accepted():
    data = make_zip([("index.html", b"x"), ("big.bin", b"\0" * MAX_FILE_BYTES)])
    entries = read_zip(data)
    assert len(as_dict(entries)["big.bin"]) == MAX_FILE_BYTES


def test_too_many_files():
    ok = make_zip([(f"f{i}.txt", b"x") for i in range(MAX_FILES)])
    assert len(read_zip(ok)) == MAX_FILES
    too_many = make_zip([(f"f{i}.txt", b"x") for i in range(MAX_FILES + 1)])
    assert any("too many files" in p for p in rejected(too_many))


def test_entry_count_bomb_rejected_before_parsing():
    data = make_zip([(f"f{i}.txt", b"") for i in range(3000)])
    assert any("too many entries" in p for p in rejected(data))


def test_lying_entry_count_in_end_record():
    data = make_zip([("index.html", b"x")])
    pos = data.rfind(b"PK\x05\x06")
    raw = bytearray(data)
    struct.pack_into("<HH", raw, pos + 8, 60000, 60000)
    assert any("too many entries" in p for p in rejected(bytes(raw)))


def test_lying_central_directory_size_in_end_record():
    data = make_zip([("index.html", b"x")])
    pos = data.rfind(b"PK\x05\x06")
    raw = bytearray(data)
    struct.pack_into("<I", raw, pos + 12, 50 * 1024 * 1024)
    assert rejected(bytes(raw))


@pytest.mark.parametrize(
    "junk", [b"", b"not a zip at all", b"PK\x03\x04" + b"\0" * 18, b"\0" * 100]
)
def test_corrupt_archives(junk):
    assert rejected(junk)


def test_truncated_archive():
    data = make_zip([("index.html", b"hello" * 1000)])
    assert rejected(data[: len(data) // 2])


def test_corrupt_entry_data_bad_crc():
    data = make_zip([("index.html", b"hello world" * 100)], zipfile.ZIP_STORED)
    raw = bytearray(data)
    i = raw.find(b"hello world")
    raw[i] ^= 0xFF
    assert any("corrupt" in p for p in rejected(bytes(raw)))


def test_collects_multiple_problems():
    data = make_zip([("../a", b"1"), ("/b", b"2"), ("c\\d", b"3"), ("ok.txt", b"4")])
    assert len(rejected(data)) >= 3
