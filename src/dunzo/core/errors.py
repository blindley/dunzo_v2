"""Error types raised across component boundaries (mapped to HTTP by the app layer)."""

from __future__ import annotations


class DunzoError(Exception):
    """Base class: carries a machine-readable ``code``, a ``message`` and ``details``."""

    code: str = "error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message: str = message
        self.details: dict = dict(details) if details else {}


class NotFound(DunzoError):
    code = "not_found"


class Invalid(DunzoError):
    """By convention ``details["problems"]`` is a list of human-readable strings."""

    code = "invalid"


class Conflict(DunzoError):
    """Stale version, already exists, still in use."""

    code = "conflict"


class ConfirmationRequired(DunzoError):
    """``details`` describe the consequences the caller must confirm."""

    code = "confirmation_required"
