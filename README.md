# EndlessDB

EndlessDB is a small Python wrapper around MongoDB that lets an application work with databases, collections, and documents as dynamic Python objects.

The goal is to keep the natural MongoDB shape while making day-to-day access feel direct:

```python
from src.endlessdb import EndlessConfiguration, EndlessDatabase


class LocalConfiguration(EndlessConfiguration):
	def override(self):
		self.CONFIG_YML = "tests/config.yml"
		self.MONGO_URI = "mongodb://root:root@localhost:27017/"
		self.MONGO_DATABASE = "tests-endlessdb"


LocalConfiguration.apply()

edb = EndlessDatabase()
employees = edb.Employee
employees["john"] = {"Name": "John", "Age": 25}

john = employees["john"]
john.Age = 26

print(john.Name)
print(john().to_dict())
```

## What It Provides

- Dynamic database, collection, and document wrappers: `EndlessDatabase`, `EndlessCollection`, and `EndlessDocument`.
- Attribute and index access for collections and nested document properties.
- Mongo-backed writes for collection items and document fields.
- Lazy/virtual documents for paths that do not exist yet.
- Document references stored as MongoDB DBRef-compatible data.
- JSON and YAML export helpers.
- YAML-based defaults and configuration override hooks.
- Direct access to the underlying PyMongo database and collection objects when the wrapper should not hide MongoDB.

## Object Model

EndlessDB has two layers for each public object:

- The public wrapper (`EndlessDatabase`, `EndlessCollection`, `EndlessDocument`) is what application code touches.
- The logic container returned by calling the wrapper (`edb()`, `collection()`, `document()`) exposes metadata and lower-level operations.

Common examples:

```python
edb = EndlessDatabase()

collection = edb.Employee
collection_logic = collection()

document = collection["john"]
document_logic = document()

print(collection_logic.key())
print(document_logic.path(True))
print(document_logic.mongo())
```

This split keeps everyday code compact while still making the internal path, parent, Mongo object, serialization, and reload/delete operations available when needed.

## Configuration

Configuration is controlled through `EndlessConfiguration`. A project can override the default MongoDB connection, database name, config collection, and YAML defaults file by subclassing `EndlessConfiguration` and calling `apply()` before creating `EndlessDatabase`.

```python
class AppConfiguration(EndlessConfiguration):
	def override(self):
		self.CONFIG_YML = "config.yml"
		self.CONFIG_COLLECTION = "config"
		self.MONGO_URI = "mongodb://root:root@localhost:27017/"
		self.MONGO_DATABASE = "app"


AppConfiguration.apply()
edb = EndlessDatabase()
```

The test suite uses this mechanism to point EndlessDB at the integration database in `tests/docker-compose.yml`.

## Reading And Writing

Collections can be reached through attribute or item access:

```python
employees = edb.Employee
same_collection = edb["Employee"]
```

Documents are addressed by MongoDB `_id`:

```python
employees["john"] = {"Name": "John", "Age": 25}
john = employees["john"]
```

Document fields can be read and written as Python attributes or nested item paths:

```python
john.Age = 26
john["Profile.City"] = "New York"

assert john.Age == 26
assert john.Profile.City == "New York"
```

When a document is already loaded, external MongoDB changes are visible after reloading the document logic:

```python
john().reload()
```

## References

Assigning an `EndlessDocument` to another document stores a reference-like value in MongoDB and resolves it back to an `EndlessDocument` on reload.

```python
departments = edb.Department
departments["it"] = {"Name": "IT"}

john.Department = departments["it"]
assert john.Department == departments["it"]
```

## Serialization

Each logic container can export to dictionaries, JSON, or YAML.

```python
data = john().to_dict()
json_text = john().to_json()
yaml_text = employees().to_yml()
```

Bytes are base64 encoded for JSON, and `date`/`datetime` values are encoded with ISO format.

## Debugger Visualization

EndlessDB is intentionally friendly in the VS Code debugger. Public wrappers and logic containers implement `__str__` and `__repr__` so the debugger watch window shows useful state instead of anonymous Python objects.

The visual representation is compact but information dense:

- Database, collection, and document objects each show their kind.
- Paths are composed from database, collection, document id, and nested property names.
- Length counters show how many collections, documents, or fields are visible at that point.
- Virtual documents are marked so it is clear when a path exists only in Python until it is written.
- Protected/read-only and open/writeable states are shown directly in the representation.
- Debug mode adds an extra marker, making debug-enabled objects easy to spot while stepping through code.

That means expressions such as `edb`, `edb.Employee`, `edb.Employee["john"]`, and `edb.Employee["john"].Profile` reveal their identity, path, size, and state directly in the debugger without extra logging.

## Samples

The `samples` folder contains runnable examples for the main EndlessDB workflows:

- quickstart collection/document writes;
- nested dot-path updates;
- document references;
- JSON, base64 JSON, and YAML serialization;
- YAML defaults loading;
- debugger-friendly representations.

Start MongoDB and run any sample from the repository root:

```powershell
docker compose -f samples/docker-compose.yml up -d
.\.venv\Scripts\python.exe samples\01_quickstart.py
```

## Development Setup

EndlessDB currently targets Python 3.13+.

Create or refresh the local virtual environment from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Start the integration MongoDB instance:

```powershell
docker compose -f tests/docker-compose.yml up -d
```

Run the tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests
```

The test suite contains focused pytest tests for configuration overrides, Mongo-backed writes, nested paths, document references, YAML collections, serialization, protected mode, and debugger-friendly representations. See `.github/project-plan.md` for the active backlog.

To prepare a release interactively, use the release assistant. It asks before each stage, can increment `pyproject.toml` by major/minor/patch/dev/rc/custom version, checks that the selected version is not already published, builds the package, validates it with Twine, and then asks whether to upload to TestPyPI, public PyPI, both, or neither:

```powershell
.\scripts\release.ps1
```

## Release Notes

Publishing is intentionally manual. Before uploading to TestPyPI or PyPI, the version in `pyproject.toml` must change and must not already exist on the target package index. Build and validate the distribution locally, publish to TestPyPI first, verify installation, and only then publish the same built artifacts to public PyPI.