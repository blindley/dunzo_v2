"""Settings, loaded from the environment (and .env at the project root).

Real environment variables take precedence over values in .env.
Owned by the project lead (master): components must not edit this file.
"""

import os
from dataclasses import dataclass
from datetime import timezone, tzinfo
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# src/<package>/config.py -> project root is three levels up from this file's directory
PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_MAX_MEDIA_BYTES = 20 * 1024 * 1024


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Add it to {PROJECT_ROOT / '.env'} (see .env.example)."
        )
    return value


def _resolve_data_dir() -> Path:
    raw = os.getenv("DATA_DIR")
    path = Path(raw).expanduser() if raw else Path("data")
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_tz() -> tzinfo:
    name = os.getenv("TIMEZONE")
    if name:
        return ZoneInfo(name)
    try:
        from tzlocal import get_localzone

        return get_localzone()
    except Exception:  # pragma: no cover - fall back rather than fail to start
        return timezone.utc


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    data_dir: Path
    max_media_bytes: int
    tz: tzinfo

    @property
    def database_path(self) -> Path:
        return self.data_dir / "dunzo.db"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(_require("PORT")),
        data_dir=_resolve_data_dir(),
        max_media_bytes=int(os.getenv("MAX_MEDIA_BYTES", DEFAULT_MAX_MEDIA_BYTES)),
        tz=_resolve_tz(),
    )
