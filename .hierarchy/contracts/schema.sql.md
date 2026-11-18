### Schema contract (master-owned, v1) — table layouts shared by content (e), progress (f), review queue (g)
Content tables are written only by `content`; progress tables only by `progress`; `review_queue` only reads. Timestamps are REAL unix epoch seconds (UTC); `study_day` is TEXT `YYYY-MM-DD`; JSON columns are TEXT. Connections run with `PRAGMA foreign_keys=ON`.
```sql
-- content
CREATE TABLE deck (id TEXT PRIMARY KEY, name TEXT NOT NULL, parent_id TEXT REFERENCES deck(id));
CREATE TABLE executor (id TEXT PRIMARY KEY, name TEXT NOT NULL, files_hash TEXT NOT NULL, note_schema TEXT);
CREATE TABLE executor_file (
  executor_id TEXT NOT NULL REFERENCES executor(id) ON DELETE CASCADE,
  path TEXT NOT NULL, hash TEXT NOT NULL, mime TEXT NOT NULL, size INTEGER NOT NULL CHECK (size > 0),
  PRIMARY KEY (executor_id, path));
CREATE TABLE note (
  id TEXT PRIMARY KEY,
  deck_id TEXT NOT NULL REFERENCES deck(id) ON DELETE CASCADE,
  executor_id TEXT NOT NULL REFERENCES executor(id) ON DELETE RESTRICT,
  card_count INTEGER NOT NULL CHECK (card_count >= 1),
  position INTEGER NOT NULL, properties TEXT NOT NULL,
  created_at REAL NOT NULL, updated_at REAL NOT NULL,
  UNIQUE (deck_id, position));
CREATE TABLE media (id TEXT PRIMARY KEY, mime TEXT NOT NULL, size INTEGER NOT NULL, created_at REAL NOT NULL);
CREATE TABLE note_media (
  note_id TEXT NOT NULL REFERENCES note(id) ON DELETE CASCADE,
  media_id TEXT NOT NULL REFERENCES media(id) ON DELETE RESTRICT,
  PRIMARY KEY (note_id, media_id));
CREATE INDEX note_executor ON note(executor_id);
CREATE INDEX note_media_media ON note_media(media_id);
-- progress (private; foreign keys point at content, never the reverse)
CREATE TABLE card_state (
  note_id TEXT NOT NULL REFERENCES note(id) ON DELETE CASCADE,
  card_index INTEGER NOT NULL, due REAL NOT NULL, scheduler TEXT NOT NULL, state TEXT NOT NULL,
  version INTEGER NOT NULL, PRIMARY KEY (note_id, card_index));
CREATE INDEX card_state_due ON card_state(due);
CREATE TABLE review_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  note_id TEXT NOT NULL REFERENCES note(id) ON DELETE CASCADE,
  card_index INTEGER NOT NULL, reviewed_at REAL NOT NULL,
  grade INTEGER NOT NULL CHECK (grade BETWEEN 1 AND 4),
  detail TEXT, state_before TEXT, state_after TEXT NOT NULL);
CREATE INDEX review_log_card ON review_log(note_id, card_index, reviewed_at);
CREATE TABLE new_draw_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, study_day TEXT NOT NULL,
  deck_id TEXT NOT NULL REFERENCES deck(id) ON DELETE CASCADE,
  note_id TEXT NOT NULL REFERENCES note(id) ON DELETE CASCADE,
  card_index INTEGER NOT NULL, drawn_at REAL NOT NULL);
CREATE INDEX new_draw_day ON new_draw_log(study_day);
CREATE INDEX new_draw_deck ON new_draw_log(deck_id, drawn_at);
CREATE TABLE day_override (study_day TEXT PRIMARY KEY, extra_new INTEGER NOT NULL CHECK (extra_new >= 0));
CREATE TABLE setting (key TEXT PRIMARY KEY, value TEXT NOT NULL);
```
