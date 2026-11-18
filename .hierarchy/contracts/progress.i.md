### `dunzo.progress` — the subset the management UI uses (contract v1; excerpt of the full contract)
```python
@dataclass(frozen=True) class ProgressSummary: card_states: int; reviews: int
class Progress:
    def __init__(self, conn: sqlite3.Connection): ...
    def summary_for_note(self, note_id: str, *, from_index: int = 0) -> ProgressSummary   # cards with card_index >= from_index
    def summary_for_deck(self, deck_id: str) -> ProgressSummary
    def delete_from_index(self, note_id: str, from_index: int) -> int   # removes progress rows with card_index >= from_index; returns card_state rows removed
```
Rule for callers: before shrinking a note's card_count, or deleting a note or deck, call the summary; if it is non-zero, require explicit user confirmation first. Wrap the content change and any `delete_from_index` in one `core.transaction`.
