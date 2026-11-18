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
