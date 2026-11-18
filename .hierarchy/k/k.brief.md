PROJECT-HIERARCHY BRIEF
# BRIEF — k: starters

Brief rev: 1 · Parent: master · Children: none yet
Project: dunzo (codename) — a local single-user spaced-repetition flashcard web app: Python 3.12, FastAPI, SQLite, sandboxed JavaScript "executors" render cards.

> This file is your entire world. Read all of it. Do not ask for other files; if something you need is missing, file a REQ (see §9).

## 1. Mission
Provide ready-made executors that the new-executor form can create, starting with a basic front/back executor.

## 2. Responsibilities (you own these)
- Implement §4. The executor is plain static files: `index.html` plus optional CSS/JS files; it uses only the executor API in §5.
- Behaviour: load via `dunzo.onInit`; index 0 shows `front` (and `front_media` if present), a Show answer button (also Space/Enter) reveals `back` (and `back_media`); index 1 swaps the roles. After reveal show four buttons Again, Hard, Good, Easy (also keys 1-4) that call `dunzo.done(grade)`. Media is resolved with `dunzo.mediaUrl(hash)` and rendered by mime type from `card.note.media` (image -> `<img>`, audio -> `<audio controls>`, video -> `<video controls>`, else a link). All text is inserted with `textContent` (never `innerHTML`). Works without any network. Readable on a phone-sized viewport and in light and dark mode.
- Tests: unit tests for `list_starters`/`get_starter` (shape, `note_schema` inside the supported subset: only string properties with `x-widget`, `required`; no path starts with `dunzo/`; `index.html` present; files non-empty). Plus a Playwright test that loads `index.html` with a hand-written fake `dunzo/api.js` and `dunzo/card.js` served from a temporary directory and checks the flow and the `done` grades (skip the browser test automatically if Chromium is not installed).

## 3. Non-responsibilities (owned elsewhere; do NOT build or reason about them)
- Serving executors, the real `dunzo/api.js`, the review shell (`review`).
- Creating executors in the database (`manage` via `content`).
- Any Python dependency on other components.

## 4. Public API you provide
Contract version: v1. Do not change without parent approval.
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


## 5. APIs you consume
Black boxes. Use exactly as written. Do not look inside.
(provider: master)
### Executor API (contract v1; master-owned). Provided by `review` (the files `dunzo/api.js`, `dunzo/card.js`), used by executors such as `starters`.
An executor is a directory of static web files with `index.html` at its top, run in `<iframe sandbox="allow-scripts">` (no `allow-same-origin`). It loads the app's two generated files by relative URL: `<script src="dunzo/api.js"></script><script src="dunzo/card.js"></script>`. Its own files are loaded by relative path; nothing else on the server is reachable (strict CSP: scripts/styles/images/audio/video/fonts from the server only, inline allowed, no network, no eval, no navigation).
```js
window.dunzoCard = { note: { id, properties, media: [ {id, mime, size, url} ] }, index, card_count }   // from dunzo/card.js
dunzo.card                      // same object as window.dunzoCard
dunzo.onInit(callback)          // callback(card) once the page has loaded (immediately if it already has)
dunzo.done(grade, detail?)      // grade: integer 1..4 (1 Again, 2 Hard, 3 Good, 4 Easy); detail: optional JSON-serializable value stored with the review
dunzo.mediaUrl(hash)            // URL for a media hash listed in card.note.media, else null
```
Messages to the host (the only channel; `parent.postMessage(msg, "*")`): `{type:"done", grade, detail?}` and `{type:"error", message}` (reported for a missing card.js or a throwing onInit callback). The host accepts messages only when `event.source` is its own iframe window, validates `grade`, and moves on to the next card after recording a `done`. The host never shows grade buttons; the executor decides whether to show its own. An executor may send `done` at any time. There is no host-to-executor message.


## 6. Constraints & conventions
- Stack / language / versions: Python 3.12 + the project's pinned dependencies (see Global conventions below).
- Code directory (project-root-relative): src/dunzo/starters/    Docs directory: .hierarchy/k/
- Permitted touch-points outside your directories: none
- Existing files supplied to you: none (your directory is empty; `src/dunzo/__init__.py`, `config.py`, `main.py`, `pyproject.toml` exist and are master-owned: read-only for you)
- Global conventions:
  - Stack: Python 3.12, type hints throughout, frozen dataclasses for value types, stdlib `sqlite3`, `ruff` (line length 100). Add no dependency beyond `pyproject.toml` (fastapi, jinja2, jsonschema, python-multipart, python-dotenv, tzdata, tzlocal, uvicorn; dev: pytest, httpx2, playwright, ruff); if you need one, file a REQ.
  - Imports: other components only through their package's public names (`from dunzo.<dir> import ...`); never import their submodules or touch their tables/files. Your `__init__.py` re-exports exactly your §4 API (plus private helpers stay private).
  - Tests: pytest, inside your own directory at `<code dir>/tests/test_*.py` (no root `tests/`); run with `uv run pytest <code dir>`. Tests must not need network, other components' code, or the user's data dir (use `tmp_path`).
  - Time: Python values are aware UTC `datetime`s; take `now` as a parameter, never read the clock in logic. IDs: `core.new_id()` UUID strings. Errors: raise the `dunzo.core` error types across boundaries; pure components raise their own `ValueError` subclass.
  - Logging: stdlib `logging.getLogger("dunzo.<dir>")`; no `print`. No global mutable state. Treat all file names, paths and uploaded bytes as untrusted.

## 7. Acceptance criteria (definition of done)
- [ ] Behaviour matches §2 and §4; unit tests pass; the browser test passes when Chromium is available.
- [ ] `uv run ruff check src/dunzo/starters` is clean; only the standard library is imported.

## 8. Report requirements
Beyond the standard report format, the parent specifically needs: the file list and sizes; how media types are rendered; keyboard shortcuts.

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
