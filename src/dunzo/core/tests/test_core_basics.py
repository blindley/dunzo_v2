"""Errors, ids/time and the sandbox constants."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from dunzo.core import (
    SANDBOX_CSP,
    SANDBOX_HEADERS,
    ConfirmationRequired,
    Conflict,
    DunzoError,
    Invalid,
    NotFound,
    from_epoch,
    new_id,
    to_epoch,
    utcnow,
)


def test_error_codes_and_fields():
    cases = [
        (NotFound, "not_found"),
        (Invalid, "invalid"),
        (Conflict, "conflict"),
        (ConfirmationRequired, "confirmation_required"),
    ]
    for cls, code in cases:
        err = cls("boom", details={"id": 1})
        assert isinstance(err, DunzoError)
        assert (err.code, err.message, err.details, str(err)) == (code, "boom", {"id": 1}, "boom")
    assert NotFound("x").details == {}


def test_error_details_are_copied():
    d = {"problems": ["a"]}
    err = Invalid("bad", details=d)
    d["problems"].append("b")
    err.details["extra"] = 1
    assert "extra" not in d


def test_new_id_is_lowercase_hyphenated_uuid4():
    a, b = new_id(), new_id()
    assert a != b
    assert a == a.lower() and len(a) == 36 and a.count("-") == 4 and a[14] == "4"


def test_epoch_roundtrip_and_awareness():
    dt = datetime(2026, 3, 1, 12, 30, 15, 250000, tzinfo=UTC)
    x = to_epoch(dt)
    assert isinstance(x, float)
    back = from_epoch(x)
    assert back == dt and back.utcoffset() == timedelta(0)


def test_to_epoch_accepts_other_aware_zones():
    dt = datetime(2026, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=5)))
    assert to_epoch(dt) == to_epoch(datetime(2026, 1, 1, 7, 0, tzinfo=UTC))


def test_to_epoch_rejects_naive():
    with pytest.raises(ValueError):
        to_epoch(datetime(2026, 1, 1))


def test_utcnow_is_aware_utc():
    assert utcnow().utcoffset() == timedelta(0)


def test_sandbox_csp_exact():
    assert SANDBOX_CSP == (
        "default-src 'none'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' data:; "
        "font-src 'self' data:; connect-src 'none'; form-action 'none'; base-uri 'none'; "
        "sandbox allow-scripts"
    )


def test_sandbox_headers_exact():
    assert SANDBOX_HEADERS == {
        "Content-Security-Policy": SANDBOX_CSP,
        "X-Content-Type-Options": "nosniff",
        "Access-Control-Allow-Origin": "*",
        "Cross-Origin-Resource-Policy": "cross-origin",
        "Referrer-Policy": "no-referrer",
    }
    assert dict(SANDBOX_HEADERS) is not SANDBOX_HEADERS
