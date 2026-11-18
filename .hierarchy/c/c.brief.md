PROJECT-HIERARCHY BRIEF
# BRIEF — c: file_rules

Brief rev: 2 · Parent: master · Children: none yet
Project: dunzo (codename) — a local single-user spaced-repetition flashcard web app: Python 3.12, FastAPI, SQLite, sandboxed JavaScript "executors" render cards.

> This file is your entire world. Read all of it. Do not ask for other files; if something you need is missing, file a REQ (see §9).

## 1. Mission
Provide the pure rules for uploaded files: path and type rules, limits, hostile-zip-safe reading, the file-set hash, and media type detection.

## 2. Responsibilities (you own these)
- Implement §4. `guess_mime` uses a fixed table covering at least html, css, js, mjs, json, svg, png, jpg, jpeg, gif, webp, avif, ico, woff, woff2, ttf, otf, mp3, ogg, wav, m4a, mp4, webm, txt, md, xml, csv, wasm, pdf.
- `read_zip` must be safe against hostile archives: path traversal, absolute paths, symlinks (check the unix mode in `external_attr`), encrypted entries, duplicate names, zip bombs (enforce the limits from declared sizes and again while inflating in bounded chunks), entry-count bombs.
- Ignore OS junk in `read_zip` (rev 2): entries under a top-level `__MACOSX/` folder and files named `.DS_Store` at any depth are dropped before anything else (before limit counting and wrapper stripping); add tests with a zip made the macOS Finder way (wrapper folder + `__MACOSX/` + `.DS_Store`).
- Collect all problems in one `FileRuleError.problems` list where practical.
- Tests with crafted archives for every rejection above, plus a valid folder-wrapped zip and a flat zip, and `files_hash` stability (order-independent).

## 3. Non-responsibilities (owned elsewhere; do NOT build or reason about them)
- Storing bytes or touching the filesystem or database.
- Deciding what to do with a rejected upload (callers do).
- Media size caps (`content` enforces `max_media_bytes`).

## 4. Public API you provide
Contract version: v1. Do not change without parent approval.
### `dunzo.file_rules` (contract v1; owner: agent `c`). Pure: no filesystem, database or network access.
```python
MAX_FILES = 500; MAX_FILE_BYTES = 20 * 1024 * 1024; MAX_TOTAL_BYTES = 100 * 1024 * 1024
RESERVED_DIR = "dunzo"; INDEX_FILE = "index.html"
DENIED_EXTENSIONS: frozenset[str]   # lowercase with dot: .exe .dll .so .dylib .sh .bat .cmd .ps1 .php .py .pl .rb .jar .msi .scr .com .vbs
class FileRuleError(ValueError): problems: list[str]
@dataclass(frozen=True) class FileEntry: path: str; data: bytes
@dataclass(frozen=True) class FileMeta: path: str; hash: str; mime: str; size: int   # hash = sha256 hex
def sha256_hex(data: bytes) -> str
def normalize_path(path: str) -> str      # segments of [A-Za-z0-9._\-@+=~], "/"-separated, no empty/"."/".." segment, no leading "/" or "\"; returns path or raises FileRuleError
def guess_mime(path: str) -> str          # by extension from a fixed table; unknown -> "application/octet-stream"
def detect_media_mime(filename: str, head: bytes) -> str   # extension table first, then magic bytes of `head` (png jpeg gif webp mp3 ogg wav mp4 webm pdf); else "application/octet-stream"; never raises
def read_zip(data: bytes) -> list[FileEntry]
    # first ignores OS junk (entries under a top-level `__MACOSX/` folder and files named `.DS_Store` at any depth; ignored
    # entries do not count toward any limit and do not affect folder stripping), then strips one common top-level folder
    # if every remaining entry is under it; skips directory entries.
    # Raises FileRuleError for: unsafe paths (absolute, "..", backslash), symlinks, encrypted entries, duplicate paths,
    # more than MAX_FILES entries, any file or the total over the limits (checked from headers AND while inflating), corrupt zip
def validate_files(files: Sequence[FileEntry]) -> list[FileMeta]
    # sorted by path; enforces path rules, no empty files, per-file/total/count limits, INDEX_FILE present at top level,
    # nothing at or under RESERVED_DIR, no DENIED_EXTENSIONS; collects all problems into one FileRuleError
def files_hash(metas: Sequence[FileMeta]) -> str   # sha256 hex over "\n".join(f"{m.path}\0{m.hash}") of metas sorted by path (UTF-8)
```
Example: `metas = validate_files(read_zip(zip_bytes)); h = files_hash(metas)`.


## 5. APIs you consume
Black boxes. Use exactly as written. Do not look inside.
None.

## 6. Constraints & conventions
- Stack / language / versions: Python 3.12 + the project's pinned dependencies (see Global conventions below).
- Code directory (project-root-relative): src/dunzo/file_rules/    Docs directory: .hierarchy/c/
- Permitted touch-points outside your directories: none
- Existing files supplied to you: none (your directory is empty; `src/dunzo/__init__.py`, `config.py`, `main.py`, `pyproject.toml` exist and are master-owned: read-only for you)
- Global conventions:
  - Stack: Python 3.12, type hints throughout, frozen dataclasses for value types, stdlib `sqlite3`, `ruff` (line length 100). Add no dependency beyond `pyproject.toml` (fastapi, jinja2, jsonschema, python-multipart, python-dotenv, tzdata, tzlocal, uvicorn; dev: pytest, httpx2, playwright, ruff); if you need one, file a REQ.
  - Imports: other components only through their package's public names (`from dunzo.<dir> import ...`); never import their submodules or touch their tables/files. Your `__init__.py` re-exports exactly your §4 API (plus private helpers stay private).
  - Tests: pytest, inside your own directory at `<code dir>/tests/test_*.py` (no root `tests/`); run with `uv run pytest <code dir>`. Tests must not need network, other components' code, or the user's data dir (use `tmp_path`).
  - Time: Python values are aware UTC `datetime`s; take `now` as a parameter, never read the clock in logic. IDs: `core.new_id()` UUID strings. Errors: raise the `dunzo.core` error types across boundaries; pure components raise their own `ValueError` subclass.
  - Logging: stdlib `logging.getLogger("dunzo.<dir>")`; no `print`. No global mutable state. Treat all file names, paths and uploaded bytes as untrusted.

## 7. Acceptance criteria (definition of done)
- [ ] Behaviour matches §4; every hostile-archive case is rejected with a clear problem message.
- [ ] `uv run ruff check src/dunzo/file_rules` is clean; only the standard library is imported.

## 8. Report requirements
Beyond the standard report format, the parent specifically needs: the final mime table; any hostile-zip case you could not cover; memory behaviour when reading a 100 MB archive.

## 9. Working protocol (authoritative; follow it even if you have no other instructions)

**Your place.** You are a *node* in a project hierarchy. Your id and parent are in the header. Your parent owns this brief and your contracts; you own the work inside your boundary. The human carries files between sessions; they are the only channel.

**Rules**
1. **Stay in your lane.** Use only this brief and the APIs in §5. Never guess at other components' internals. Don't touch what §3 excludes.
2. **No silent changes to contracts.** You may not change §4 or §5 yourself. If you need to, file a REQ (type `contract-change`).
3. **Ask, don't assume.** If something is unclear, missing, or contradictory, write a REQ, say which items it blocks, and continue with unblocked work. If you must proceed on an assumption, label it `ASSUMPTION` and list it in your report.
4. **Splitting.** If the work exceeds one session or has cleanly separable parts, you may split it into child nodes. Name them by alternating letters and numbers: children of `a` are `a1`, `a2`; of `a1` are `a1a`, `a1b`; of `a1a` are `a1a1`, `a1a2`. Give each child a code directory inside your own. Write each child a brief in this same format (sections 1–9, including this protocol, with `Parent: {your id}`), carry the exact API text they need into their §5, and keep a `{id}.tree.md` listing children, status, and brief revs. You become their parent: you answer their REQs, issue their CHGs, and integrate their reports. A split must not alter your own §4 contract; if it would, REQ upward first.
5. **Changes from above.** A `CHG` notice, or a higher `Brief rev`, supersedes earlier text. Apply it, note the new rev, and cascade to your children if affected.
6. **Context hygiene.** Read only what you need; use targeted reads; don't paste large files into chat; don't re-read what you already hold. If the session becomes long or slow, write a CHECKPOINT and tell the user to continue in a fresh session with this brief + the checkpoint.
7. **Where files go, and how you deliver them.** §6 gives your `Code directory` (project-root-relative) and your docs directory `.hierarchy/{id path}/` (each ancestor id in turn: for `a1a` it is `.hierarchy/a/a1/a1a/`). Write only in those two places; anything else needs a REQ unless §6 lists it as a permitted touch-point. You need no knowledge of siblings' paths. Deliver files as a zip containing only added or changed files (whole files, not diffs) at paths relative to the project root (never absolute, never `..`), so that unzipping at the project root with overwrite puts everything in place. Recipe: make a staging folder laid out like the project root, copy in the changed files plus your docs (report, child briefs, tree, REQs/RESPs/CHGs), add a manifest `.hierarchy/{id path}/deliveries/{id}-{nnn}.manifest.md` listing the files and a `Delete:` list (zips can't delete; a move is a delete plus an add), then `cd staging && zip -r ../{id}-{nnn}.zip .`. If the skill's `make_delivery.py` is available it does this and rejects out-of-boundary paths. Deliver updated child briefs and messages the same way.
8. **Finish with a REPORT** when acceptance criteria (§7) are met, or when you are blocked and can go no further.

**Naming files:** `{id}-{nnn}.zip` (deliveries), `{id}.brief.md`, `{id}.report.md`, `REQ-{from}-{nnn}.md`, `RESP-{to}-{nnn}.md`, `CHG-{to}-{nnn}.md`, `CHECKPOINT-{id}-{nnn}.md`. Always tell the user which file goes to which session (parent or child).

### Message formats (keep each short)

**REQ** (child → parent)
```
# REQ-{from}-{nnn} → {parent}
Brief rev: {n} · Type: clarification | contract-change | missing-api | scope-conflict
Blocks: {items blocked, or "nothing"}
Question: {one clear question}
Context: {minimum needed to decide}
Options I see: {A / B, with my recommendation}
Meanwhile I am: {what I'm continuing with}
```

**RESP** (parent → child)
```
# RESP-{to}-{nnn} ← answers REQ-{from}-{nnn}
Decision: {clear answer}
Brief changes: none | rev {n→m}: {what changed}   (updated brief attached if changed)
Effect on you: {what to do differently, if anything}
```

**CHG** (parent → child; requirements or contracts changed)
```
# CHG-{to}-{nnn}
Brief rev: {old} → {new}
Changed: {section: before → after}, one line each
Action required: {what the node must redo or adjust}
In-progress work: can continue | must pause | must revisit {part}
```

**REPORT** (node → parent; ≲1 page)
```
# REPORT-{id}
Status: complete | partial | blocked      Brief rev worked against: {n}
Summary: {≤8 lines}
Public API as built: unchanged | differs: {exact differences}
Deviations & assumptions: {each flagged ASSUMPTION or DEVIATION, with why}
Decisions made: {only those the parent should know}
Children (if split): {id: status}
Delivery: {id}-{nnn}.zip · Apply: cd <project root> && unzip -o {id}-{nnn}.zip · Then delete: {paths | none}
Verification: {tests run, results}
Integration notes: {only what a consumer needs; the API, not the internals}
Known issues / follow-ups: {…}
```

**CHECKPOINT** (node → its own future session)
```
# CHECKPOINT-{id}-{nnn}
Done so far: {…}
Current state: {what works, what's mid-change}
Next steps: {ordered}
Decisions & gotchas: {things the next session must not relearn}
Open REQs: {ids + status}
Files touched: {paths}
```
