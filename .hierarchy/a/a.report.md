# REPORT-a
Status: complete      Brief rev worked against: 1
Summary: `dunzo.core` implemented per §4 in `src/dunzo/core/` (errors, clock, db, web, `__init__`). 36 tests pass; `ruff check` and `ruff format --check` clean (line length 100). `__init__` re-exports exactly the §4 names (`__all__`).
Public API as built: unchanged

Deviations & assumptions:
- ASSUMPTION: `migrate` raises `ValueError` for a malformed set (gap, duplicate/unsorted version, not starting at 1, duplicate owner), validated for ALL sets before anything is applied. SQL failures propagate as `sqlite3.Error` (with an `add_note` naming owner and version).
- ASSUMPTION: if the recorded version is higher than the set's highest migration (DB newer than code), `migrate` is a no-op for that owner.
- ASSUMPTION: `DunzoError.details` is a copy of the dict passed (default `{}`); `.code` is a class attribute.
- Brief typo only: §4 comment says "l maps them to HTTP"; read as `app` (§3). No effect.
- Brief lists dev dep `httpx2` (probably `httpx`). Not needed: tests call `get_conn` as a plain generator.

Decisions made:
- SANDBOX_HEADERS exact value:
  `{"Content-Security-Policy": SANDBOX_CSP, "X-Content-Type-Options": "nosniff", "Access-Control-Allow-Origin": "*", "Cross-Origin-Resource-Policy": "cross-origin", "Referrer-Policy": "no-referrer"}`
  with SANDBOX_CSP = `default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' data:; font-src 'self' data:; connect-src 'none'; form-action 'none'; base-uri 'none'; sandbox allow-scripts`
- How `migrate` splits scripts: walks each `;` and cuts when `sqlite3.complete_statement` says the text since the last cut is one complete statement. Semicolons in strings, comments and trigger bodies (BEGIN..END) therefore don't split; several statements on one line are separated. Comment-only/blank leftovers are dropped; a final statement without `;` is kept. Each statement runs via `conn.execute`; never `executescript`.
- Atomicity: each migration = one `transaction()` (script + version bump). Schema table `schema_migration` created with `IF NOT EXISTS`. Recorded version is re-read inside each migration's transaction.
- Threads: `check_same_thread=False` only permits using a connection from another thread. It is NOT made thread-safe: `transaction` nesting relies on per-connection state (`in_transaction`), so two threads interleaving on one connection can corrupt nesting/commit boundaries. Use one connection per request/thread (what `get_conn` gives); share one only if externally serialised.
- Savepoint names are `dz_<uuid hex>` (no global counter).

Children: none
Delivery: a-001.zip · Apply: cd <project root> && unzip -o a-001.zip · Then delete: none
Verification: `PYTHONPATH=src pytest src/dunzo/core` → 36 passed (ordering across sets, idempotency, gap/malformed rejected before any change, failure rollback and resume, nested/deep/sibling rollback, exception through all levels, caller-managed BEGIN, FK and WAL on, naive datetimes rejected, `get_conn` closes on normal exit and on error, header constants character-exact). Run in a scratch tree with stub `dunzo/__init__.py` and `config.py` (not delivered); real run: `uv run pytest src/dunzo/core`.

Integration notes:
- Migration scripts must not contain BEGIN/COMMIT/SAVEPOINT, and `PRAGMA foreign_keys`/`journal_mode` have no effect inside the migration transaction.
- `migrate` may be called inside a caller's transaction (it then uses savepoints).
- Tests import `dunzo.config` (via `dunzo.core.web`) but only monkeypatch `get_settings`; `PORT` need not be set.
- Test files are prefixed `test_core_` so basenames can't collide with other components under pytest's default import mode.

Known issues / follow-ups: none.
