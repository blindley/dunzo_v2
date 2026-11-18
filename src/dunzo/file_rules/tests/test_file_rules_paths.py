import hashlib

import pytest

from dunzo.file_rules import FileRuleError, normalize_path, sha256_hex


@pytest.mark.parametrize(
    "path",
    ["index.html", "a/b/c.js", "img/logo-2@2x.png", "x_y.z~1", "a=b+c/d.txt", ".hidden", "a/.b"],
)
def test_normalize_path_accepts(path):
    assert normalize_path(path) == path


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/",
        "/abs.txt",
        "\\win.txt",
        "a\\b.txt",
        "../x",
        "a/../x",
        "a/./x",
        ".",
        "..",
        "a//b",
        "a/",
        "a b.txt",
        "caf\u00e9.txt",
        "a/b\n.txt",
        "a:b",
        "a\x00b",
        "a*b",
        "C:/x",
    ],
)
def test_normalize_path_rejects(path):
    with pytest.raises(FileRuleError) as exc:
        normalize_path(path)
    assert exc.value.problems


def test_normalize_path_collects_problems():
    with pytest.raises(FileRuleError) as exc:
        normalize_path("/a//b/../c d")
    assert len(exc.value.problems) >= 4


def test_error_is_value_error_and_caps_problems():
    err = FileRuleError([f"p{i}" for i in range(500)])
    assert isinstance(err, ValueError)
    assert len(err.problems) == 101
    assert err.problems[-1].startswith("... and 400 more")
    assert FileRuleError("one").problems == ["one"]


def test_sha256_hex():
    assert sha256_hex(b"abc") == hashlib.sha256(b"abc").hexdigest()
    assert sha256_hex(b"") == hashlib.sha256(b"").hexdigest()
