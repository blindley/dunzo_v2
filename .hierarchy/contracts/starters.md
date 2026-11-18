### `dunzo.starters` (contract v1; owner: agent `k`). Pure, no dependencies on other components.
```python
@dataclass(frozen=True) class Starter:
    key: str; name: str; description: str
    note_schema: dict                  # JSON Schema in the schema_forms-supported subset
    default_card_count: int
    files: Mapping[str, bytes]         # path -> bytes; includes "index.html"; no path starts with "dunzo/"
def list_starters() -> list[Starter]   # at least the two below, in this order
def get_starter(key: str) -> Starter   # raises KeyError if unknown
```
Required starters: `basic` ("Basic", default_card_count 1) and `basic-reversed` ("Basic and reversed", default_card_count 2). Both share the same files. Note schema: `front` and `back` (required strings, textarea), `front_media` and `back_media` (optional strings: a media hash from `card.note.media`). Card index 0 asks `front` and reveals `back`; index 1 asks `back` and reveals `front`.
