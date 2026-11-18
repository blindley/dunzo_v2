# MASTER — dunzo

Updated: 2026-11-18 · This file is the master's memory. Keep it compact.

## Summary
dunzo (codename, to be replaced) is a local, single-user spaced-repetition flashcard web app. Content (decks, notes, executors, media) is separate from progress (scheduling state, review log, settings). Cards are rendered by sandboxed JavaScript "executors". Full design: `ARCHITECTURE.md` (rev 2, approved 2026-11-17).

## Architecture
Components and single data owners:
- `core` (a): errors, ids/time, SQLite connect/transaction/migrate, web helpers (per-request connection, exact sandbox headers). Owns no data.
- `content` (e): tables deck, executor, executor_file, note, media, note_media + blob stores (media, executor). `progress` (f): card_state, review_log, new_draw_log, day_override, setting + backup/restore. `review_queue` (g): read-only joins.
- Pure: `scheduler` (b), `file_rules` (c), `schema_forms` (d), `starters` (k).
- `packages` (h): export/import via `Content` only. `manage` (i) and `review` (j): web routers. `app` (l): assembly, middleware, error pages.
Main flows: review = j asks g for next card -> serves frame (content) -> executor `done` -> j calls b then f.record_review (version-checked). Destructive content edits = i asks f for a progress summary, confirms with the user, then calls e (and f.delete_from_index) in one transaction.

## Global conventions
Python 3.12, FastAPI sync routes, stdlib sqlite3, uv, ruff (100 cols), pytest tests inside each component dir (`src/dunzo/<dir>/tests/`, importmode importlib, no root tests/). Cross-component imports only via public package names. Aware-UTC datetimes with explicit `now`; DB timestamps REAL epoch; study_day TEXT. Errors: `dunzo.core` types across boundaries (404/422/409/409), pure components raise own ValueError subclasses. Security: executors untrusted (sandbox + CSP headers from core), localhost bind, Host check + CSRF in `app`. Master owns root files: `pyproject.toml`, `.env.example`, `.env`, `.gitignore`, `README.md`, `ARCHITECTURE.md`, `src/dunzo/{__init__,config,main}.py`. Conventions of project-hierarchy win over python-project (zips unzip at the project root; per-agent directories).

## Node registry
| id | name | parent | directory | mission (one line) | status | brief rev | contract |
|----|------|--------|-----------|--------------------|--------|-----------|----------|
| a | core | master | src/dunzo/core/ | shared errors, time, db, migrations, web helpers | done (a-001, 36 tests) | 1 | v1 |
| b | scheduler | master | src/dunzo/scheduler/ | pure SM-2 + study-day arithmetic | done (b-001, 78 tests) | 1 | v1 |
| c | file_rules | master | src/dunzo/file_rules/ | pure upload rules, safe zip reading, media types | briefed | 1 | v1 |
| d | schema_forms | master | src/dunzo/schema_forms/ | JSON Schema <-> form model | briefed | 1 | v1 |
| e | content | master | src/dunzo/content/ | content persistence, blobs, GC (expects to split) | briefed | 1 | v1 |
| f | progress | master | src/dunzo/progress/ | progress persistence, settings, backup/restore | briefed | 1 | v1 |
| g | review_queue | master | src/dunzo/review_queue/ | read-only next-card/counts/stats | briefed | 1 | v1 |
| h | packages | master | src/dunzo/packages/ | content export/import zips | briefed | 1 | v1 |
| i | manage | master | src/dunzo/manage/ | management UI router (expects to split) | briefed | 1 | v1 |
| j | review | master | src/dunzo/review/ | frames, shell, report recording, settings/backup pages (expects to split; sandbox spike first) | briefed | 1 | v1 |
| k | starters | master | src/dunzo/starters/ | starter executors | briefed | 1 | v1 |
| l | app | master | src/dunzo/app/ | app assembly, middleware, error pages | briefed | 1 | v1 |

Master owns the project root and root-level files (manifests, top-level config, CI). Child directories nest inside their parent's.

## Contract index
Full texts in `.hierarchy/contracts/`. Shared types live here (master-owned): schema (DDL), settings, web conventions, executor API.
| provider | consumers | version | file |
|----------|-----------|---------|------|
| master (schema) | e, f, g | v1 | schema.sql.md |
| master (`dunzo.config`) | a, i, j, l | v1 | settings.md |
| master (web conventions) | i, j, l | v1 | routes.md |
| master (executor API) | j (provides), k | v1 | executor_api.md |
| a core | e, f, h, i, j, l | v1 | core.md |
| b scheduler | j | v1 | scheduler.md |
| c file_rules | e, h, i | v1 | file_rules.md |
| d schema_forms | i | v1 | schema_forms.md |
| e content | h, i, j (excerpt), l (excerpt) | v1 | content.md, content.j.md, content.l.md |
| f progress | i (excerpt), j, l (excerpt) | v1 | progress.md, progress.i.md, progress.l.md |
| g review_queue | j | v1 | review_queue.md |
| h packages | i | v1 | packages.md |
| k starters | i | v1 | starters.md |
| l app | (entry point only) | v1 | app.md |
Briefs embed the fragment texts in §4/§5; a contract change means updating the fragment and every brief that embeds it (CHG to each consumer).

## Decision log
- 2026-11-17: Architecture rev 2 approved with all review decisions (new-card limit 20 + same-day raise, round-robin across selected decks, 4am rollover, learning "Again", 4 grades kept, nested decks prepared via `deck.parent_id`, media GC with 24 h grace, no media allowlist but sandboxed attachment serving, progress backup separate).
- Per-owner `schema_migration` table instead of a single `PRAGMA user_version` — two independent migration owners (content, progress).
- Directory `file_rules` (not `executor_files`): it also hosts media-type detection. Directory `review_queue` (not `queue`): avoids the stdlib clash.
- Tests live inside component directories; root `tests/` dropped; pytest `testpaths=["src"]`, `--import-mode=importlib`.
- `config.py` and `main.py` are master-owned root files derived from the python-project scaffold; `app` exports `dunzo.app:app`, so `main.py` needs no change.
- Web layer split into sibling components `manage` (decks, notes, executors, media, packages) and `review` (frames, shell, report, history, stats, settings, backup). Package export/import routes belong to `manage`.
- Progress deletion on card_count shrink is orchestrated by routes (`manage`), because `content` may not touch progress tables; atomic via nested `core.transaction`.
- Duplicate-report protection: `card_state.version` optimistic check. New-card draws are logged on first review (same transaction).
- Assumptions made on the user's behalf (approved 2026-11-17): study day uses the local zone (`TIMEZONE` override); extra study continues the same rotation; backups manual only in v1; Hard on a first review is a pass.
- CSRF/Host protection enforced centrally in `app`; routers never enforce it.

- 2026-11-18: Accepted REPORT-a (core complete, contract v1 unchanged). Accepted its assumptions: `migrate` validates all sets first and raises `ValueError` for a malformed set, `sqlite3.Error` for SQL failures; a DB newer than the code is a no-op for that owner; migration scripts must not contain BEGIN/COMMIT/SAVEPOINT or PRAGMA foreign_keys/journal_mode; a connection must be used by one request/thread at a time (use `get_conn`).
- 2026-11-18: `httpx2` stays in the dev group: verified that `fastapi.testclient.TestClient` works with the pinned dependencies.

- 2026-11-18: Accepted REPORT-b (scheduler complete, contract v1 unchanged; rules in `.hierarchy/b/sm2.md`). Accepted its assumptions: the ease formula applies to every non-lapse review (Hard -0.14, Good 0, Easy +0.10); graduating from relearning keeps the reduced interval with no Easy bonus; Again inside learning/relearning leaves the state unchanged; rounding is half-up; the 36500-day cap wins; study days are 23 or 25 hours across DST. State shape: `{phase, ease, interval_days, reps, lapses}`, opaque to consumers.

## Open requests
- none

## Pending changes to propagate
- CHG-e-001, CHG-f-001, CHG-h-001, CHG-l-001 (clarifications of how `core.migrate` behaves; no contract or brief rev change) — delivered in master-002.zip; mark done when the user confirms they reached those sessions.

## Build order / notes
- Start in parallel: a, b, c, d, k, g (they need no other component; g only needs the schema contract).
- Also start now against the contract texts (stubs/fakes allowed): e, f (need a, c), then h; i, j (j's browser spike first), l.
- Expect e, i, j to split into children; I answer their REQs and issue CHGs.
- Integration is the master's job after reports arrive: wire-up check with `uv sync && uv run pytest && uv run dunzo`. Consider an end-to-end agent (`m`) once e, f, i, j, l are delivered.
- Spike risk to watch (j): CSP `'self'` from an opaque origin; may force a contract change to `SANDBOX_HEADERS` (a core change, then CHG to a, j, i).
