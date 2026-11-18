### `dunzo.progress` (contract v1; owner: agent `f`). Progress tables only (card_state, review_log, new_draw_log, day_override, setting).
```python
MIGRATIONS: MigrationSet            # owner "progress"; must be migrated AFTER content's (foreign keys point at content tables)
@dataclass(frozen=True) class UserSettings:
    new_per_day: int = 20; day_rollover: time = time(4, 0); again_delay_minutes: int = 10; learn_ahead_minutes: int = 20
@dataclass(frozen=True) class CardState: note_id: str; card_index: int; due: datetime; scheduler: str; state: dict; version: int
@dataclass(frozen=True) class ReviewEntry:
    id: int; note_id: str; card_index: int; reviewed_at: datetime; grade: int
    detail: dict | None; state_before: dict | None; state_after: dict
@dataclass(frozen=True) class ProgressSummary: card_states: int; reviews: int
@dataclass(frozen=True) class BackupInfo: path: Path; card_states: int; reviews: int; created_at: datetime
@dataclass(frozen=True) class RestoreReport:
    card_states: int; reviews: int; draws: int; skipped_card_states: int; skipped_reviews: int; skipped_draws: int
class Progress:
    def __init__(self, conn: sqlite3.Connection): ...
    # Raises NotFound / Invalid(details["problems"]) / Conflict as stated. Writers are atomic and nest inside core.transaction.
    def get_settings(self) -> UserSettings                          # stored values over the defaults above
    def update_settings(self, *, new_per_day: int | None = None, day_rollover: time | None = None,
                        again_delay_minutes: int | None = None, learn_ahead_minutes: int | None = None) -> UserSettings
        # Invalid unless 0 <= new_per_day <= 10000, 1 <= again_delay_minutes <= 1440, 0 <= learn_ahead_minutes <= 240
    def get_extra_new(self, day: date) -> int                       # 0 if none
    def add_extra_new(self, day: date, count: int) -> int           # count >= 1; returns the new total for that study day
    def get_card_state(self, note_id: str, card_index: int) -> CardState | None
    def record_review(self, *, note_id: str, card_index: int, deck_id: str, grade: int, detail: dict | None,
                      scheduler: str, state: dict, due: datetime, expected_version: int | None,
                      reviewed_at: datetime, study_day: date) -> CardState
        # atomic. expected_version None = first review: the card must have no card_state row; inserts it (version 1) and
        # writes a new_draw_log row (study_day, deck_id, note, index). Otherwise the row must exist at exactly that version;
        # it is updated and version+1. A review_log row is written (state_before None on a first review; state_after = state).
        # Conflict on any version mismatch (including a row that appeared or vanished); NotFound if the note does not exist;
        # Invalid if grade not in 1..4. Does NOT check card_index < card_count (caller's job).
    def list_reviews(self, note_id: str, *, card_index: int | None = None, limit: int = 100,
                     before: datetime | None = None) -> list[ReviewEntry]       # newest first
    def count_new_drawn(self, day: date) -> int                     # new_draw_log rows for that study day
    def summary_for_note(self, note_id: str, *, from_index: int = 0) -> ProgressSummary   # cards with card_index >= from_index
    def summary_for_deck(self, deck_id: str) -> ProgressSummary
    def delete_from_index(self, note_id: str, from_index: int) -> int   # removes card_state, review_log and new_draw_log rows with card_index >= from_index; returns card_state rows removed
    def backup_to(self, dest: Path, *, now: datetime) -> BackupInfo
        # consistent snapshot into a NEW sqlite file holding only progress tables + settings (never content); Conflict if dest exists
    def restore_from(self, src: Path) -> RestoreReport
        # replaces ALL progress tables and settings with the backup's, atomically; rows whose note/deck no longer exists are
        # skipped and counted; Invalid if src is not a valid dunzo progress backup
```
Invariant: the scheduler `state` dict is stored verbatim as JSON and never interpreted here.
Example: `p.record_review(note_id=n, card_index=0, deck_id=d, grade=3, detail=None, scheduler="sm2", state=r.state, due=r.due, expected_version=None, reviewed_at=now, study_day=day)`.
