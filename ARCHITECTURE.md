# dunzo: Architecture (rev 2)

"dunzo" is a codename and will be replaced. Keep the name in a single constant and in the package directory so renaming stays cheap.

## 1. What it is

A web app for spaced-repetition flashcards. One user, runs locally. Content (decks, notes, executors, media) is separate from progress (scheduling state, review history, settings), so content can be exported and shared without dragging anyone's progress along.

**In scope (v1):** decks, notes, executors, media (with garbage collection), review sessions across selected decks, scheduling (SM-2 with relearning), a daily new-card limit, review history, content export/import, progress backup/restore.
**Out of scope (v1):** accounts/auth, sync, mobile app, hosted sharing, executor version management, nested decks (the schema is prepared), a media browser, automatic backups.

## 2. Vocabulary

- **Deck**: a named collection of notes. Flat in v1; `parent_id` exists but is unused.
- **Note**: a unit of content. Free-form `properties` JSON, plus media. Generates `card_count` cards.
- **Card**: not stored as content. It is the pair `(note_id, card_index)` with `0 <= card_index < card_count`.
- **New card**: a card with no `card_state` row, meaning it has never been reviewed.
- **Executor**: a small, mostly static web page that renders and runs one card (a mini interactive app): a directory of files with an `index.html` at its top level, plus any scripts, styles, images, audio, video and fonts the author includes. One executor per note (changeable later). The executor uses `card.index` to decide what to show. There is no built-in notion of front/back. ("Template" refers only to Jinja page templates.)
- **Report**: what an executor sends back when a card is done: a grade plus optional detail.
- **Progress**: per-card scheduling state, the review log, new-card draw log and user settings. Never exported with content.
- **Study day**: the day a review belongs to. It starts at the configured rollover time (default 04:00 local) instead of midnight.

## 3. Stack and configuration

| Area | Choice | Why |
|---|---|---|
| Language / framework | Python 3.12, FastAPI, uvicorn, uv, `src/dunzo/` layout | Decided |
| Database | SQLite (stdlib `sqlite3`), single file in the data directory; WAL mode; `PRAGMA foreign_keys=ON` on every connection; schema versioned with `PRAGMA user_version` and a migration runner | No server, easy to back up, cascades depend on the pragma |
| Management UI | Jinja2 page templates + HTMX | Server-rendered, small |
| Review UI | Small client-side shell hosting a sandboxed iframe | Executors are JavaScript |
| Scheduling | SM-2 first, behind a scheduler interface | Swappable later (e.g. FSRS) |
| Validation | `jsonschema` for `note_schema` | Standard |

**Environment (`.env`)**: `PORT` (required, no default in code), `HOST` (default `127.0.0.1`), `DATA_DIR` (default `data/`), `MAX_MEDIA_BYTES` (default 20 MB), `TIMEZONE` (optional, default system local).
**User settings (stored in the database, progress side)**: `new_per_day` (20), `day_rollover` (04:00), `again_delay_minutes` (10), `learn_ahead_minutes` (20).

## 4. Data model

**Rule: references go one way. Progress points at content. Content never points at progress.** Content and progress tables live in the same SQLite file for v1, but no content table has a foreign key to a progress table, and export reads only content tables. Progress tables do have foreign keys to content, with `ON DELETE CASCADE`, so deleting a note or deck removes whatever progress exists for it (usually none).

### Content (shareable)

- **deck**: `id` (UUID), `name`, `parent_id` (nullable, unused in v1)
- **executor**: `id` (UUID), `name`, `files_hash` (sha256 over the sorted (path, file hash) pairs, so it identifies the whole file set), `note_schema` (JSON Schema, nullable)
- **executor_file**: `executor_id`, `path` (relative, `/`-separated, e.g. `css/main.css`), `hash` (sha256 of the bytes; stored on disk content-addressed in the executor blob store), `mime` (decided from the file extension), `size` (> 0). Primary key `(executor_id, path)`; cascades when the executor is deleted. `index.html` must exist; `dunzo/` is reserved.
- **note**: `id` (UUID), `deck_id`, `executor_id`, `card_count`, `position` (integer, order within the deck), `properties` (JSON), `created_at`, `updated_at`
- **media**: `id` (sha256 of bytes), `mime`, `size`, `created_at`. Bytes stored on disk, content-addressed by `id`, in the media blob store (separate from the executor blob store).
- **note_media**(`note_id`, `media_id`): link table, so unused media and export bundles are easy to compute. The API presents it as `media_list`. An executor's own files are not media: they live in `executor_file` and are referred to by relative path.

### Progress (private)

- **card_state**: `note_id`, `card_index`, `due` (real column, indexed), `scheduler` (name, e.g. `sm2`), `state` (JSON owned by that scheduler), `version` (integer, +1 per review). Primary key `(note_id, card_index)`. **A row is created only when the card is first reviewed**, never earlier.
- **review_log**: `id`, `note_id`, `card_index`, `reviewed_at`, `grade` (1-4), `detail` (JSON from the executor, nullable), `state_before` (null for a card's first review), `state_after` (JSON). Enough to rebuild any scheduler's state by replay.
- **new_draw_log**: `id`, `study_day`, `deck_id`, `note_id`, `card_index`, `drawn_at`. One row is written, in the same transaction as the card's first `card_state`, when a new card is first reviewed. It counts today's new cards against the limit and records which decks new cards came from.
- **day_override**: `study_day` (primary key), `extra_new` (integer): extra new cards allowed for that day.
- **setting**: `key`, `value` (JSON). The user settings listed in section 3.

### Rules

- Notes, decks and executors use UUIDs so shared content never collides on import. Media is content-addressed. On import, decks and notes get new ids. An executor keeps its id when the id is unknown or already exists with the same `files_hash` (reuse it); if the id exists with a different `files_hash`, it is imported under a new id and the imported notes are remapped.
- Card indices are permanent identities. They are never renumbered. Shrinking `card_count` deletes progress for the removed indices, and deleting a note or deck deletes the progress of its cards; in both cases the user is warned and must confirm, but only when such progress exists.
- Changing a note's executor keeps its progress (progress is keyed by note and index). Properties are revalidated against the new executor's schema; a mismatch is shown to the user and not saved silently. A changed `card_count` follows the shrink rule above.
- Saving a note or changing its `card_count` never touches progress tables (except the shrink case above). Importing or deleting a large unreviewed deck therefore writes nothing to progress.
- Notes in a deck have a strict order via `note.position`: integers spaced 1024 apart, `UNIQUE(deck_id, position)`, so inserts and moves rarely need renumbering. The content layer renumbers a deck when a gap runs out. New notes append to the end by default. Moving a note to another deck puts it at the end of that deck and keeps its progress.
- Order is content. Export stores a deck's notes as an ordered list (not raw position numbers) and import preserves that order.
- `properties` are validated against `executor.note_schema` on save when a schema exists. The schema is also used to generate the note editing form, for a defined subset of JSON Schema (types, enums, arrays, required, defaults); anything outside the subset, or no schema, falls back to a raw JSON editor.
- `card_count` is set explicitly by the note author in v1.
- **Media garbage collection:** media with no `note_media` link, older than a 24-hour grace period (so uploads not yet saved into a note survive), is deleted along with its bytes. Executor blobs no longer referenced by any `executor_file`, older than the same grace period, are deleted too. Collection runs at startup and daily.
- **Nested decks (later):** `parent_id` is already present. The review queue takes a set of deck ids, so selecting a parent later only expands to its descendants.

## 5. Executor contract

An executor is a directory of mostly static web files (an `index.html` plus whatever it uses), run inside a sandboxed iframe. It is untrusted code (it can arrive in shared packages).

**Files:** paths are relative and `/`-separated, made of letters, digits and `. _ - @ + = ~`; the mime type is decided by extension (unknown extensions become `application/octet-stream`); any file type is allowed except a small denylist of extensions with no use in a web page (executables, shell scripts, server-side scripts, archives such as `.exe .dll .so .dylib .sh .bat .cmd .ps1 .php .py .pl .rb .jar .msi .scr`); limits: 500 files, 20 MB per file, 100 MB in total, no empty files. Authors upload a zip (a zip of the folder itself also works; the folder is stripped). Zip reading rejects paths escaping the root, symlinks, and over-limit expansion. The directory `dunzo/` is reserved for the app.

**Serving:** `index.html` is loaded into the iframe from `/review/frame/{note_id}/{card_index}/index.html`. Everything it loads by relative URL comes from the same per-card directory: the executor's own files (looked up by exact path in `executor_file`, never on disk by name), plus two generated files in the reserved directory:
- `dunzo/api.js`: the executor API, the same for every card.
- `dunzo/card.js`: `window.dunzoCard = {...}`, the card being reviewed: `{ note: { id, properties, media }, index, card_count }`, where `media` is a list of `{ id, mime, size, url }` for the media linked to the note.

Nothing else exists under `dunzo/` (404). Future extensions are more files there. The card index is in the URL so that `card.js` can carry this card's data (the frame has no cookies). `card.js` is served `Cache-Control: no-store`; executor files use ETag by hash.

**Sandboxing (non-negotiable):**
- `<iframe sandbox="allow-scripts">` with no `allow-same-origin`. Every file of the frame is served with the strict CSP (`default-src 'none'`; scripts, styles, images, audio, video and fonts from the server only; inline scripts and styles allowed, because the sandbox contains them; `connect-src 'none'`, no `eval`, no forms, no navigation; `sandbox allow-scripts`), `nosniff` and `Access-Control-Allow-Origin: *` (fonts and module scripts are fetched with CORS from an opaque origin), so opening a file directly is sandboxed too.
- The only channel from the executor to the host is `postMessage`. The card reaches the executor as a script, not as a message, so there is no host-to-executor message.
- The host accepts messages only when `event.source` is its own iframe's window.
- Executors refer to note media by hash. `dunzo.mediaUrl(hash)` returns the host-served URL for a hash listed in the card's `media`, else null. The host serves the bytes from `/cards/{note_id}/media/{hash}`, which answers 404 for anything not linked to the note.
- **Media serving (and management-UI media previews):** every media response carries `X-Content-Type-Options: nosniff`, the same strict sandbox CSP, and `Content-Disposition: attachment`. Uploaded mime types are never trusted: extension plus a small content sniff decide, with `application/octet-stream` as fallback. No allowlist is needed.
- **Known residual risks, accepted for v1 (single local user):** the CSP does not cover WebRTC, so a determined executor could leak data; and an executor can load another note's `card.js` as a script and read its properties. Neither exposes progress. Revisit if sharing grows.
- A spike must prove the whole design in a real browser (CSP `'self'` from an opaque origin, module scripts and fonts, `postMessage` source check) before the review area is built out.

**API (`window.dunzo`, after `<script src="dunzo/api.js">` and `<script src="dunzo/card.js">`):**
- `dunzo.onInit(callback)`: calls `callback(card)` once the page has loaded (immediately if it already has). A missing `card.js`, or a callback that throws, is reported as an `error` message.
- `dunzo.card`: the card object (same as `window.dunzoCard`).
- `dunzo.done(grade, detail?)`: posts the report. `dunzo.mediaUrl(hash)` as above.

**Messages (executor to host):**
- `done`: `{ type: "done", grade, detail? }`
- `error`: `{ type: "error", message }` (script errors, shown in the review shell)
  - `grade` is an integer 1-4 (1=Again, 2=Hard, 3=Good, 4=Easy). The host validates and rejects anything else. Executors that want fewer buttons may send only some of the values.
  - `detail` is optional free-form JSON, stored in `review_log` (e.g. the typed answer).
- The executor decides whether to show its own grade buttons. The host never shows grade buttons itself.
- Executors may send `done` at any time; the host moves to the next card after recording it.
- **Recording is safe against duplicates:** when the host hands out a card it includes the card's current `version` (null for a new card). The report is recorded only if the version still matches; otherwise it is rejected and the shell fetches the next card. Reports for deleted notes or out-of-range indices are rejected.

**Trust:** the scheduler treats the reported grade as authoritative. This is acceptable for a single local user. If sharing grows, revisit.

**Local-app protection:** bind to `HOST` (default `127.0.0.1`); reject requests whose `Host` header is not the configured host and port (DNS rebinding); require a CSRF token or a matching `Origin` on every mutating route.

## 6. Scheduling and the review queue

- The scheduler is pure: `(state | None, grade, now, config) -> (new_state, due)`. No database or web dependencies. A pure `study_day(now, rollover, timezone)` helper lives alongside it.
- SM-2 is the first implementation, registered by name (`sm2`). State is a JSON dict stored in `card_state.state` (phase, ease, interval, repetitions, lapses).
- **Grades:** 1 Again, 2 Hard, 3 Good, 4 Easy, mapped to SM-2 quality 1, 3, 4, 5. Quality below 3 is a lapse; the ease factor changes with quality and never drops below 1.3.
- **Again brings the card back:** a card graded Again (new or reviewed) is due again after `again_delay_minutes` and stays in the session. It is in a learning/relearning phase; the first success after that graduates it to the normal SM-2 intervals (reduced after a lapse). Hard on a card's first review counts as a pass with a short first interval.
- An initial state is defined for a card's first review. The `card_state` row is written when that first report arrives.
- **Review scope:** the user selects one or more decks (or all). Notes in the selected decks (descendants too, once nesting exists) feed the queue.
- **Next card:** (1) the due card (`due <= now`) with the earliest `due`; else (2) a new card, if the day's new count is below `new_per_day + extra_new`; else (3) the earliest learning card due within `learn_ahead_minutes`; else the session is done.
- **New-card selection is round-robin across the selected decks.** The queue picks the deck whose most recent new-card draw (from `new_draw_log`, across days) is oldest, with never-drawn decks first. Within a deck, cards come in order by `note.position`, then `card_index`; a note's card indices are enumerated at query time, not by storing rows. Because rotation state survives across days, if there are more decks than the daily limit, tomorrow continues where today stopped.
- **Extra study:** the user can raise today's limit; this writes `day_override` for the current study day and continues the same rotation.

## 7. Backup

Progress is backed up on its own: a command and a UI action produce a progress-only file (progress tables and settings) using SQLite's online backup API, consistent while the app runs. Restore replaces the progress tables only; rows pointing at notes that no longer exist are skipped and reported. Automatic backups are out of scope for v1.

## 8. Components and boundaries

**Components**
- **Core:** settings (`.env`), database connection and pragmas, migration runner.
- **Scheduler:** pure scheduling functions and the study-day helper.
- **Note-schema form handling:** pure conversion between a note's JSON Schema and HTML form fields and submitted values.
- **Executor file rules:** pure rules for an executor's files (paths, types, denylist, limits, zip reading, file-set hash).
- **Content access:** all SQL for decks, notes, executors and media (content tables only), the two blob stores and garbage collection.
- **Progress access:** all SQL for `card_state`, `review_log`, `new_draw_log`, `day_override` and `setting`, and progress backup/restore (progress tables only).
- **Review queue:** read-only queries joining content and progress: due cards, next new cards, stats.
- **Starter executors:** ready-made executors (a basic front/back executor) that the new-executor form can create.
- **Packages:** content export/import as a zip containing a manifest, notes, executors and media.
- **Web layer:** management routes (decks, notes, executors, media) and review routes (review pages, next card, recording a report, the executor's per-card directory, stats, note history, backup), plus an app shell (app factory, error pages, router registration, entry point). Browsers get HTML error pages; other clients get JSON errors.

**Boundaries**
- The scheduler and executor file rules perform no I/O.
- Content SQL lives only in content access; progress SQL lives only in progress access. The review queue is the only place allowed to join the two, and only read-only. Its table layouts come from a shared schema contract owned by the project lead.
- Packages must not import progress access (so export can never include progress).
- Routes call the access layers and the scheduler. The review route calls the scheduler and then hands the result to progress access to record; progress access does not import the scheduler.
