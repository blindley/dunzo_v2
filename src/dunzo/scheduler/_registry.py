"""Scheduler registry (private). Maps names to scheduler instances."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from ._base import Scheduler, SchedulerError
from ._sm2 import Sm2Scheduler

_SCHEDULERS: Mapping[str, Scheduler] = MappingProxyType(
    {s.name: s for s in (Sm2Scheduler(),)}
)


def get_scheduler(name: str) -> Scheduler:
    """Return the scheduler registered under ``name``; SchedulerError if unknown."""
    if not isinstance(name, str) or name not in _SCHEDULERS:
        shown = name if isinstance(name, str) and len(name) <= 40 else "<invalid>"
        raise SchedulerError(f"unknown scheduler: {shown!r}")
    return _SCHEDULERS[name]
