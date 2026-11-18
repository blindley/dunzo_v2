PROJECT-HIERARCHY BRIEF
# BRIEF — d: schema_forms

Brief rev: 1 · Parent: master · Children: none yet
Project: dunzo (codename) — a local single-user spaced-repetition flashcard web app: Python 3.12, FastAPI, SQLite, sandboxed JavaScript "executors" render cards.

> This file is your entire world. Read all of it. Do not ask for other files; if something you need is missing, file a REQ (see §9).

## 1. Mission
Convert between a note's JSON Schema and HTML form fields: a template-neutral form model out, submitted strings back into typed values.

## 2. Responsibilities (you own these)
- Implement §4 exactly; the form model contains no HTML (the page templates render it).
- Missing `title` falls back to the property name; `required` comes from the parent object's `required` list; `default` fills `value` when no value is given.
- Tests: round trip build -> render-agnostic submit -> parse for nested objects and arrays of scalars and objects; required/empty errors; strict number parsing; boolean absent = false; unsupported schemas rejected by `is_supported` and `build_form`; arrays with gaps in indices.

## 3. Non-responsibilities (owned elsewhere; do NOT build or reason about them)
- Rendering HTML, templates or JavaScript (the `manage` component).
- Validating values against the schema (`content` validates with jsonschema).

## 4. Public API you provide
Contract version: v1. Do not change without parent approval.
### `dunzo.schema_forms` (contract v1; owner: agent `d`). Pure.
Supported JSON Schema subset (`is_supported` is true iff all hold): root `type: object` with `properties`; every property (recursively) is `string` (optional `enum`; `x-widget: "textarea"` selects a textarea), `integer`, `number`, `boolean`, `object` (with `properties`) or `array` whose `items` is one of those; `title`, `description`, `default` and object-level `required` are used; other validation keywords (min/max, pattern, ...) are ignored here (the caller validates with jsonschema); no `$ref`, `oneOf`/`anyOf`/`allOf`.
```python
FieldKind = Literal["text", "textarea", "integer", "number", "boolean", "select", "object", "array"]
@dataclass(frozen=True) class FormField:
    name: str; label: str; kind: FieldKind; required: bool; description: str
    value: Any                       # current scalar value (None if unset or for object/array)
    options: tuple[str, ...]         # for select
    items: tuple["FormField", ...]   # object: child fields; array: existing item fields named f"{name}.{i}"
    new_item: "FormField | None"     # arrays only: a blank item named f"{name}.{len(items)}"
@dataclass(frozen=True) class FormModel: fields: tuple[FormField, ...]
@dataclass(frozen=True) class ParseResult: values: dict[str, Any]; errors: dict[str, str]   # errors keyed by field name
class SchemaFormError(ValueError): ...
def is_supported(schema: dict) -> bool
def build_form(schema: dict, values: dict | None = None) -> FormModel    # SchemaFormError if unsupported
def parse_form(schema: dict, submitted: Mapping[str, str]) -> ParseResult
```
Naming: property `b` of object `a` is `a.b`; array item `i` of `a` is `a.i`; object item in an array: `a.0.b`. Parsing: values are strings; for non-required fields an empty/absent value omits the key; boolean: absent = false, `on`/`true` = true; required and empty -> error; integers/numbers parsed strictly; array = items whose index is present, in index order, skipping items whose fields are all empty. Labels default to the property name (or `title`).


## 5. APIs you consume
Black boxes. Use exactly as written. Do not look inside.
None.

## 6. Constraints & conventions
- Stack / language / versions: Python 3.12 + the project's pinned dependencies (see Global conventions below).
- Code directory (project-root-relative): src/dunzo/schema_forms/    Docs directory: .hierarchy/d/
- Permitted touch-points outside your directories: none
- Existing files supplied to you: none (your directory is empty; `src/dunzo/__init__.py`, `config.py`, `main.py`, `pyproject.toml` exist and are master-owned: read-only for you)
- Global conventions:
  - Stack: Python 3.12, type hints throughout, frozen dataclasses for value types, stdlib `sqlite3`, `ruff` (line length 100). Add no dependency beyond `pyproject.toml` (fastapi, jinja2, jsonschema, python-multipart, python-dotenv, tzdata, tzlocal, uvicorn; dev: pytest, httpx2, playwright, ruff); if you need one, file a REQ.
  - Imports: other components only through their package's public names (`from dunzo.<dir> import ...`); never import their submodules or touch their tables/files. Your `__init__.py` re-exports exactly your §4 API (plus private helpers stay private).
  - Tests: pytest, inside your own directory at `<code dir>/tests/test_*.py` (no root `tests/`); run with `uv run pytest <code dir>`. Tests must not need network, other components' code, or the user's data dir (use `tmp_path`).
  - Time: Python values are aware UTC `datetime`s; take `now` as a parameter, never read the clock in logic. IDs: `core.new_id()` UUID strings. Errors: raise the `dunzo.core` error types across boundaries; pure components raise their own `ValueError` subclass.
  - Logging: stdlib `logging.getLogger("dunzo.<dir>")`; no `print`. No global mutable state. Treat all file names, paths and uploaded bytes as untrusted.

## 7. Acceptance criteria (definition of done)
- [ ] Behaviour matches §4; tests pass; `uv run ruff check src/dunzo/schema_forms` is clean.
- [ ] Only the standard library is imported.

## 8. Report requirements
Beyond the standard report format, the parent specifically needs: any schema construct you had to decide on; the exact error message format for field errors.

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
