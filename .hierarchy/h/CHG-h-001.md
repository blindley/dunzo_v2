# CHG-h-001
Brief rev: 1 → 1 (clarification only)
Changed: nothing in §4/§5 (contract v1 stays). Clarifications from the finished `core` component (REPORT-a):
- `migrate` first validates ALL sets and raises `ValueError` for a malformed set (gap, duplicate or unsorted version, not starting at 1, duplicate owner); an SQL failure propagates as `sqlite3.Error` naming owner and version.
- Migration scripts must not contain BEGIN/COMMIT/SAVEPOINT; `PRAGMA foreign_keys` and `journal_mode` have no effect inside a migration (`connect` already sets them).
- If a DB's recorded version is newer than your set, `migrate` does nothing for you (no downgrade).
- `migrate` may be called inside a caller's transaction (it then uses savepoints).
- A connection must be used by one request/thread at a time (use one per request via `core.get_conn`).
Action required: When tests build a real Content, call `core.migrate` and `content.MIGRATIONS` directly; no change otherwise.
In-progress work: can continue
