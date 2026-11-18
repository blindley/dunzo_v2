### `dunzo.config` (master-owned root file; contract v1)
```python
@dataclass(frozen=True) class Settings:
    host: str; port: int; data_dir: Path; max_media_bytes: int; tz: tzinfo   # tz = TIMEZONE env or system zone
    database_path: Path   # property: data_dir / "dunzo.db"
def get_settings() -> Settings        # cached; PORT is required. Tests construct explicit values instead of calling it.
```
