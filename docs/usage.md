# EndlessDB Usage Guide

This guide documents the public EndlessDB 0.5.x behavior for scripts, prototypes, fixtures, notebooks, and debugger-friendly workflows.

EndlessDB is a dynamic object facade over MongoDB. It is intentionally smaller than an ODM: MongoDB remains the source of truth, PyMongo remains reachable, and dynamic access stays available for exploratory work.

## Installation

```powershell
python -m pip install endlessdb
```

EndlessDB requires Python 3.11 or newer and a reachable MongoDB server.

## Configuration

Configure defaults by subclassing `EndlessConfiguration` before creating `EndlessDatabase`:

```python
from endlessdb import EndlessConfiguration, EndlessDatabase


class AppConfiguration(EndlessConfiguration):
    def override(self):
        self.MONGO_URI = "mongodb://root:root@localhost:27017/"
        self.MONGO_DATABASE = "app"
        self.CONFIG_COLLECTION = "config"
        self.CONFIG_YML = "config.yml"


AppConfiguration.apply()
db = EndlessDatabase()
```

You can also pass connection values directly. These per-instance values override configuration defaults:

```python
db = EndlessDatabase(
    url="mongodb://root:root@localhost:27017/app?authSource=admin",
)
```

## Object Model

EndlessDB exposes three public wrappers:

- `EndlessDatabase` for a MongoDB database;
- `EndlessCollection` for a MongoDB collection;
- `EndlessDocument` for a MongoDB document or nested document path.

Attribute access and item access both resolve dynamic paths:

```python
employees = db.Employee
same_collection = db["Employee"]

employees["john"] = {"name": "John", "age": 25}
john = employees["john"]

print(john.name)
print(john["age"])
```

Calling a wrapper returns its logic container. Logic containers expose metadata, persistence helpers, serialization helpers, and PyMongo escape hatches:

```python
print(employees().key())
print(john().path(True))
print(employees().raw())
```

## Dynamic And Strict Access

By default, missing dynamic paths can create virtual wrappers. This is useful in scripts and notebooks:

```python
profile = employees["john"].profile
profile.city = "New York"
```

Use strict mode when typos should fail fast:

```python
from endlessdb import EndlessDatabase, PropertyNotFoundError

db = EndlessDatabase(strict=True)

try:
    db.MissingCollection
except PropertyNotFoundError:
    print("missing collection")
```

Strict mode propagates from database to collections and documents. You can also enable it fluently on existing wrappers:

```python
employees(strict=True)
john(strict=True)
```

## Writing Data

Assign a dictionary to create or patch a root document:

```python
employees["john"] = {"name": "John", "age": 25}
employees["john"] = {"age": 26}
```

Item assignment remains patch-compatible for compatibility. Existing fields are preserved.

Nested fields can be written through attributes or dot-path item access:

```python
john.profile.city = "New York"
john["profile.timezone"] = "America/New_York"
```

Use explicit methods when patch versus replacement matters:

```python
employees().patch("john", {"role": "developer"})
employees().replace("jane", {"name": "Jane", "status": "active"})
```

`patch()` uses MongoDB `$set`. `replace()` performs a full MongoDB replacement and removes fields that are not present in the replacement document.

## Deleting And Unsetting

Unset fields below a document:

```python
john().unset("profile.city")
```

Unset through the collection logic when you already have a full document path:

```python
employees().unset("john.profile.timezone")
```

Deleting a nested document path unsets that nested object:

```python
john.profile().delete()
```

Root document deletion remains explicit:

```python
employees["john"]().delete()
```

Protected wrappers reject writes, unsets, and deletes:

```python
john(protected=True)
```

## Query Helpers

Collection logic wraps common PyMongo query behavior while returning `EndlessDocument` wrappers:

```python
open_tasks = list(
    tasks().find(
        {"done": False},
        sort=[("priority", -1)],
        skip=0,
        limit=10,
    )
)
```

Convenience helpers:

```python
first_open = tasks().first({"done": False}, sort=[("priority", -1)])
open_count = tasks().count({"done": False})
has_archive = tasks().exists({"_id": "archive"})
raw_collection = tasks().raw()
```

When returning EndlessDB wrappers, projections must include `_id`:

```python
list(tasks().find({"done": False}, projection={"_id": 1, "name": 1}))
```

Use `raw()` for advanced PyMongo behavior that EndlessDB does not wrap.

## References

Assigning one `EndlessDocument` to another document field stores a DBRef-compatible value in MongoDB. EndlessDB resolves it back to a document wrapper on reload:

```python
departments["it"] = {"name": "IT"}
employees["john"].department = departments["it"]

employees["john"]().reload()
print(employees["john"].department.name)
```

Serialize references as target ids when needed:

```python
data = employees["john"]().to_dict(ref_to_id=True)
```

## Serialization

`to_dict()` returns a concrete dictionary in EndlessDB 0.5.x:

```python
data = employees["john"]().to_dict()
```

Use `iter_items()` for generator-style traversal:

```python
for key, value in employees["john"]().iter_items():
    print(key, value)
```

JSON and YAML helpers are available on document, collection, and database logic containers:

```python
json_text = employees["john"]().to_json()
yaml_text = employees().to_yml()
```

Bytes are base64 encoded for JSON. `date` and `datetime` values are serialized as ISO strings.

## YAML Defaults

YAML defaults are useful for local defaults, fixtures, and sample data:

```yaml
Employee:
  john:
    name: John
    age: 25
```

Set `CONFIG_YML`, then create `EndlessDatabase()` as usual. You can also load a read-only YAML collection directly:

```python
from endlessdb import CollectionLogicContainer

config = CollectionLogicContainer.from_yml("config.yml")
```

YAML collections are read-only and reloadable from their source path.

## Representations

Default `repr()` output is plain and professional:

```python
repr(employees["john"])
```

Enable debug or emoji-rich representations for debugger-oriented workflows:

```python
employees(debug=True)
employees["john"](emojify=True)
```

## Migration Notes From 0.4.x

- `to_dict()` now returns a concrete `dict`; use `iter_items()` when you need lazy key/value iteration.
- `collection["id"] = {...}` remains patch-compatible and preserves existing fields.
- Use `replace()` for full document replacement.
- Missing paths can raise `PropertyNotFoundError` when `strict=True` is enabled.
- Default `repr()` no longer uses emoji; use `debug=True` or `emojify=True` for emoji-rich output.

## Samples

Runnable examples live in `samples/`:

```powershell
docker compose -f samples/docker-compose.yml up -d
.\.venv\Scripts\python.exe samples\01_quickstart.py
```

The samples cover quickstart writes, nested paths, references, serialization, YAML defaults, debugger representations, strict mode, query helpers, update/delete semantics, a storage CLI app, and an interactive notebook app.