import hashlib

import pytest

from dunzo.file_rules import (
    DENIED_EXTENSIONS,
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    FileEntry,
    FileMeta,
    FileRuleError,
    files_hash,
    sha256_hex,
    validate_files,
)


def fe(path: str, data: bytes = b"x") -> FileEntry:
    return FileEntry(path, data)


def problems_of(files) -> list[str]:
    with pytest.raises(FileRuleError) as exc:
        validate_files(files)
    return exc.value.problems


def test_valid_set_sorted_with_meta():
    metas = validate_files([fe("z.js", b"zz"), fe("index.html", b"<p>"), fe("a/b.png", b"\x89")])
    assert [m.path for m in metas] == ["a/b.png", "index.html", "z.js"]
    by_path = {m.path: m for m in metas}
    assert by_path["index.html"] == FileMeta("index.html", sha256_hex(b"<p>"), "text/html", 3)
    assert by_path["a/b.png"].mime == "image/png"
    assert by_path["z.js"].mime == "text/javascript"


def test_denied_extension_list_matches_contract():
    expected = ".exe .dll .so .dylib .sh .bat .cmd .ps1 .php .py .pl .rb .jar .msi .scr .com .vbs"
    assert len(expected.split()) == 17
    assert frozenset(expected.split()) == DENIED_EXTENSIONS


@pytest.mark.parametrize("ext", sorted(DENIED_EXTENSIONS))
def test_denied_extensions(ext):
    assert any("not allowed" in p for p in problems_of([fe("index.html"), fe(f"tool{ext}")]))


def test_denied_extension_case_insensitive():
    assert any("not allowed" in p for p in problems_of([fe("index.html"), fe("x.PHP")]))


def test_missing_index_and_nested_index():
    assert any("index.html" in p for p in problems_of([fe("a.js")]))
    assert any("index.html" in p for p in problems_of([fe("sub/index.html")]))
    assert any("index.html" in p for p in problems_of([]))
    assert any("index.html" in p for p in problems_of([fe("INDEX.HTML")]))


@pytest.mark.parametrize("path", ["dunzo/x.js", "dunzo/a/b.js", "dunzo", "Dunzo/x.js"])
def test_reserved_dir(path):
    assert any("reserved" in p for p in problems_of([fe("index.html"), fe(path)]))


def test_dunzo_prefix_name_is_not_reserved():
    assert validate_files([fe("index.html"), fe("dunzo.js"), fe("dunzo2/x.js")])


def test_empty_file_rejected():
    assert any("empty" in p for p in problems_of([fe("index.html"), fe("e.txt", b"")]))


def test_bad_paths_rejected():
    ps = problems_of([fe("index.html"), fe("../x"), fe("a b"), fe("/abs"), fe("a\\b")])
    assert len(ps) >= 4


def test_duplicate_paths():
    assert any("duplicate" in p for p in problems_of([fe("index.html"), fe("index.html")]))


def test_file_folder_clash():
    assert any("both" in p for p in problems_of([fe("index.html"), fe("a"), fe("a/b")]))


def test_count_limit():
    ok = [fe("index.html")] + [fe(f"f{i}.txt") for i in range(MAX_FILES - 1)]
    assert len(validate_files(ok)) == MAX_FILES
    assert any("too many files" in p for p in problems_of([*ok, fe("one-more.txt")]))


def test_per_file_limit():
    big = b"x" * MAX_FILE_BYTES
    assert validate_files([fe("index.html"), fe("big.bin", big)])
    assert any(
        "file limit" in p for p in problems_of([fe("index.html"), fe("big.bin", big + b"x")])
    )


def test_total_limit():
    chunk = b"x" * MAX_FILE_BYTES  # one object reused: no extra memory
    ok = [fe("index.html", chunk)] + [fe(f"f{i}.bin", chunk) for i in range(4)]
    assert sum(len(f.data) for f in ok) == MAX_TOTAL_BYTES
    assert validate_files(ok)
    assert any("total size" in p for p in problems_of([*ok, fe("tiny.txt")]))


def test_collects_all_problems_at_once():
    ps = problems_of([fe("a.exe"), fe("dunzo/x"), fe("e", b""), fe("bad name")])
    joined = " | ".join(ps)
    for needle in ("not allowed", "reserved", "empty", "characters", "index.html"):
        assert needle in joined


def test_files_hash_known_value_and_order_independent():
    a = FileMeta("a.txt", sha256_hex(b"A"), "text/plain", 1)
    b = FileMeta("b/c.js", sha256_hex(b"B"), "text/javascript", 1)
    expected = hashlib.sha256(f"a.txt\0{a.hash}\nb/c.js\0{b.hash}".encode()).hexdigest()
    assert files_hash([a, b]) == expected
    assert files_hash([b, a]) == expected


def test_files_hash_ignores_mime_and_size_but_tracks_path_and_content():
    base = validate_files([fe("index.html", b"1"), fe("a.js", b"2")])
    same = validate_files([fe("a.js", b"2"), fe("index.html", b"1")])
    assert files_hash(base) == files_hash(same)
    changed = validate_files([fe("index.html", b"1"), fe("a.js", b"3")])
    renamed = validate_files([fe("index.html", b"1"), fe("b.js", b"2")])
    assert len({files_hash(base), files_hash(changed), files_hash(renamed)}) == 3


def test_files_hash_empty():
    assert files_hash([]) == hashlib.sha256(b"").hexdigest()
