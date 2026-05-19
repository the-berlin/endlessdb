# EndlessDB

EndlessDB is a lightweight Python wrapper around MongoDB that lets you work with databases, collections, and documents as dynamic Python objects.

It is a developer tool for scripts, prototypes, fixtures, notebooks, and debugger-friendly workflows. It is not a full ODM and does not try to hide PyMongo.

It keeps MongoDB as the source of truth while making common document access feel natural:

```python
from endlessdb import EndlessConfiguration, EndlessDatabase


class LocalConfiguration(EndlessConfiguration):
    def override(self):
        self.MONGO_URI = "mongodb://root:root@localhost:27017/"
        self.MONGO_DATABASE = "example"


LocalConfiguration.apply()

db = EndlessDatabase()
employees = db.Employee

employees["john"] = {"Name": "John", "Age": 25}
employees["john"].Age = 26

print(employees["john"].Name)
print(employees["john"]().to_dict())
```

## Features

- Dynamic wrappers for MongoDB databases, collections, and documents.
- Attribute and item access for collections and document fields.
- Dot-path writes for nested document values.
- Lazy document wrappers for paths that do not exist until written.
- Strict mode for typo-safe attribute access when you do not want virtual paths.
- Mongo-backed updates for collection items and document properties.
- Explicit patch, replace, unset, and delete operations.
- Query helpers for filters, sorting, limits, offsets, counts, existence checks, and raw PyMongo access.
- Document references stored as DBRef-compatible values.
- Dictionary, JSON, and YAML serialization helpers.
- YAML-based default documents.
- Access to the underlying PyMongo database and collection objects when needed.
- Debugger-friendly string representations for VS Code and other Python debuggers.

## Installation

EndlessDB requires Python 3.11 or newer and a reachable MongoDB server.

Install the package from PyPI:

```powershell
python -m pip install endlessdb
```

For local examples, you can start MongoDB with Docker Compose from this repository:

```powershell
docker compose -f samples/docker-compose.yml up -d
```

## Quick Start

Configure the MongoDB connection before creating `EndlessDatabase`:

```python
from endlessdb import EndlessConfiguration, EndlessDatabase


class AppConfiguration(EndlessConfiguration):
    def override(self):
        self.MONGO_URI = "mongodb://root:root@localhost:27017/"
        self.MONGO_DATABASE = "app"


AppConfiguration.apply()

db = EndlessDatabase()
```

Collections are available through attributes or item access:

```python
employees = db.Employee
same_collection = db["Employee"]
```

Documents are addressed by MongoDB `_id`:

```python
employees["john"] = {"Name": "John", "Age": 25}
john = employees["john"]
```

Fields can be read and written through attributes or item paths:

```python
john.Age = 26
john["Profile.City"] = "New York"

assert john.Age == 26
assert john.Profile.City == "New York"
```

## Object Model

EndlessDB exposes public wrappers for everyday use:

- `EndlessDatabase` represents a MongoDB database.
- `EndlessCollection` represents a MongoDB collection.
- `EndlessDocument` represents a MongoDB document or nested document path.

Calling a wrapper returns its logic container. Logic containers expose metadata, lower-level Mongo objects, serialization, reload, and delete operations:

```python
db = EndlessDatabase()
collection = db.Employee
document = collection["john"]

print(collection().key())
print(document().path(True))
print(document().mongo())
```

This split keeps application code compact while still making lower-level operations available when you need them.

## Configuration

`EndlessConfiguration` controls the default MongoDB connection, database name, config collection, and YAML defaults file.

```python
class AppConfiguration(EndlessConfiguration):
    def override(self):
        self.CONFIG_YML = "config.yml"
        self.CONFIG_COLLECTION = "config"
        self.MONGO_URI = "mongodb://root:root@localhost:27017/"
        self.MONGO_DATABASE = "app"
```

You can also pass connection values directly when creating a database:

```python
db = EndlessDatabase(
    url="mongodb://root:root@localhost:27017/",
    database="app",
)
```

Use strict mode when missing collections, documents, or fields should raise `PropertyNotFoundError` instead of creating virtual wrappers:

```python
db = EndlessDatabase(
    url="mongodb://root:root@localhost:27017/app",
    strict=True,
)
```

## References

Assigning one `EndlessDocument` to another document field stores a reference-like value in MongoDB. When the document is loaded again, EndlessDB resolves it back to an `EndlessDocument` wrapper.

```python
departments = db.Department
departments["it"] = {"Name": "IT"}

employees["john"].Department = departments["it"]

assert employees["john"].Department == departments["it"]
```

## Querying

Use `find_one()` and `find()` from the collection logic container for Mongo-style filters:

```python
employees["john"] = {"Name": "John", "Age": 26}
employees["jane"] = {"Name": "Jane", "Age": 31}

match = employees().find_one({"Name": "Jane"})
matches = list(
    employees().find(
        {"Age": {"$gte": 25}},
        sort=[("Age", -1)],
        limit=10,
    )
)
```

`find()` returns an iterator of `EndlessDocument` objects. The collection logic also exposes `count()`, `exists()`, `first()`, and `raw()` for direct PyMongo collection access.

## Updating And Deleting

Item assignment keeps patch-compatible `$set` behavior:

```python
employees["john"] = {"Name": "John", "Age": 25}
employees["john"] = {"Age": 26}
```

Use explicit methods when the difference matters:

```python
employees().patch("john", {"Role": "developer"})
employees().replace("john", {"Name": "John", "Status": "active"})
employees["john"]().unset("Profile.City")
employees["john"].Profile().delete()
```

Root document deletion remains explicit:

```python
employees["john"]().delete()
```

## Serialization

Logic containers can export data to dictionaries, JSON, or YAML. Use `iter_items()` when you need lazy key/value traversal.

```python
data = employees["john"]().to_dict()
items = list(employees["john"]().iter_items())
json_text = employees["john"]().to_json()
yaml_text = employees().to_yml()
```

Bytes are base64 encoded for JSON. `date` and `datetime` values are encoded in ISO format.

## YAML Defaults

EndlessDB can load default collections and documents from YAML. This is useful for sample data, local application defaults, and repeatable test fixtures.

```yaml
Employee:
  john:
    Name: John
    Age: 25
```

Set `CONFIG_YML` in your configuration class, then create `EndlessDatabase()` as usual.

## Samples

The [samples](samples) directory contains runnable examples for the main workflows:

- quickstart collection and document writes;
- nested dot-path updates;
- document references;
- JSON, base64 JSON, and YAML serialization;
- YAML defaults loading;
- debugger-friendly representations;
- strict mode;
- query helpers;
- patch, replace, unset, and delete behavior.

Run a sample from the repository root:

```powershell
docker compose -f samples/docker-compose.yml up -d
python -m pip install -e .
python samples\01_quickstart.py
```

## Roadmap

The next development stage continues to harden EndlessDB as a small developer tool:

- formatter and type checking once the dynamic public API has settled further;
- higher coverage for negative paths and pure helpers;
- continued typing work without hiding the dynamic API.

## Development

Create a local virtual environment and install development dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Start the integration MongoDB instance:

```powershell
docker compose -f tests/docker-compose.yml up -d
```

Run the test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests
```

Run lint checks:

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests samples
```

Pytest writes a terminal coverage summary and `coverage.xml` through `pytest-cov`; the current baseline gate is 70%.

Build the package locally:

```powershell
.\.venv\Scripts\python.exe -m build
```

GitHub Actions runs tests against Python 3.11, 3.12, and 3.13 with a MongoDB service container, then builds and checks the package distributions.

To create a GitHub Release, commit the version change first, then create and push a `v<version>` tag. The release workflow verifies that the tag matches `pyproject.toml`, runs tests, builds the wheel and source distribution, checks them with Twine, and attaches the artifacts to the GitHub Release:

```powershell
.\scripts\create-github-release-tag.ps1
```

## License

EndlessDB is licensed under the Apache License 2.0. See [LICENSE.txt](LICENSE.txt) for details.