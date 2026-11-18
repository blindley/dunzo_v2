import ast
import sys
from dataclasses import FrozenInstanceError
from datetime import UTC, time, timedelta
from pathlib import Path

import pytest

import dunzo.scheduler as pkg
from dunzo.scheduler import (
    AGAIN,
    DEFAULT_SCHEDULER,
    EASY,
    GOOD,
    HARD,
    SchedulerConfig,
    SchedulerError,
    get_scheduler,
)


def test_exports_exactly_the_contract():
    assert set(pkg.__all__) == {
        "AGAIN", "HARD", "GOOD", "EASY", "SchedulerConfig", "ScheduleResult", "Scheduler",
        "DEFAULT_SCHEDULER", "get_scheduler", "SchedulerError", "study_day", "study_day_start",
    }
    assert (AGAIN, HARD, GOOD, EASY) == (1, 2, 3, 4)


def test_config_defaults_and_frozen():
    c = SchedulerConfig()
    assert (c.again_delay, c.day_rollover, c.tz) == (timedelta(minutes=10), time(4, 0), UTC)
    with pytest.raises(FrozenInstanceError):
        c.again_delay = timedelta(0)  # type: ignore[misc]


def test_registry():
    assert DEFAULT_SCHEDULER == "sm2"
    assert get_scheduler(DEFAULT_SCHEDULER).name == "sm2"
    for bad in ("fsrs", "", None, 3):
        with pytest.raises(SchedulerError):
            get_scheduler(bad)  # type: ignore[arg-type]
    assert issubclass(SchedulerError, ValueError)


def test_stdlib_only_imports():
    stdlib = set(sys.stdlib_module_names)
    for path in Path(pkg.__file__).parent.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            else:
                continue
            for name in names:
                assert name.split(".")[0] in stdlib, f"{path.name} imports {name}"
