### `dunzo.review_queue` (contract v1; owner: agent `g`). Read-only; joins content and progress tables (layouts: schema contract).
```python
@dataclass(frozen=True) class QueueConfig:
    study_day: date; new_per_day: int; extra_new: int = 0
    learn_ahead: timedelta = timedelta(minutes=20); deck_ids: frozenset[str] | None = None   # None = all decks
@dataclass(frozen=True) class QueuedCard:
    note_id: str; card_index: int; deck_id: str; kind: Literal["due", "new", "learning"]
    version: int | None; due: datetime | None          # None for new cards
@dataclass(frozen=True) class QueueCounts: due: int; new_available: int; new_drawn_today: int; learning_ahead: int
@dataclass(frozen=True) class DeckStats: deck_id: str; name: str; total_cards: int; new_cards: int; due_cards: int
class ReviewQueue:
    def __init__(self, conn: sqlite3.Connection): ...
    def next_card(self, config: QueueConfig, now: datetime,
                  *, exclude: AbstractSet[tuple[str, int]] = frozenset()) -> QueuedCard | None
    def counts(self, config: QueueConfig, now: datetime) -> QueueCounts
        # new_available = min(remaining daily allowance, new cards that exist in scope); learning_ahead = cards with now < due <= now+learn_ahead
    def deck_stats(self, now: datetime, deck_ids: frozenset[str] | None = None) -> list[DeckStats]   # ordered by deck name
```
Rules. Scope: notes of the selected decks; only cards with card_index < note.card_count. `next_card` returns the first applicable of: (1) kind "due": card_state.due <= now, earliest due first (ties: note position, note id, index); (2) kind "new": only while new_drawn_today < new_per_day + extra_new, where new_drawn_today counts new_draw_log rows of config.study_day for ALL decks. Round-robin: among selected decks that still have a new card (not excluded), pick the deck whose latest new_draw_log.drawn_at over all days is oldest (never-drawn decks first; ties by deck name, then id), and return that deck's first never-reviewed card by (note.position, card_index); (3) kind "learning": earliest card with now < due <= now + learn_ahead; else None. `exclude` applies to every kind. Never writes.
