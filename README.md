# EndlessDB

EndlessDB is a lightweight Python wrapper around MongoDB that lets you work with databases, collections, and documents as dynamic Python objects.

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
- Mongo-backed updates for collection items and document properties.
- Document references stored as DBRef-compatible values.
- JSON and YAML serialization helpers.
- YAML-based default documents.
- Access to the underlying PyMongo database and collection objects when needed.
- Debugger-friendly string representations for VS Code and other Python debuggers.

## Installation

EndlessDB requires Python 3.13 or newer and a reachable MongoDB server.

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

## References

Assigning one `EndlessDocument` to another document field stores a reference-like value in MongoDB. When the document is loaded again, EndlessDB resolves it back to an `EndlessDocument` wrapper.

```python
departments = db.Department
departments["it"] = {"Name": "IT"}

employees["john"].Department = departments["it"]

assert employees["john"].Department == departments["it"]
```

## Querying

Use `find_one()` and `find()` from the collection logic container for simple Mongo-style filters:

```python
employees["john"] = {"Name": "John", "Age": 26}
employees["jane"] = {"Name": "Jane", "Age": 31}

match = employees().find_one({"Name": "Jane"})
matches = list(employees().find({"Age": 31}))
```

`find()` returns an iterator of `EndlessDocument` objects.

## Serialization

Logic containers can export data to dictionaries, JSON, or YAML:

```python
data = employees["john"]().to_dict()
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
- debugger-friendly representations.

Run a sample from the repository root:

```powershell
docker compose -f samples/docker-compose.yml up -d
python -m pip install -e .
python samples\01_quickstart.py
```

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

Build the package locally:

```powershell
.\.venv\Scripts\python.exe -m build
```

## License

EndlessDB is licensed under the Apache License 2.0. See [LICENSE.txt](LICENSE.txt) for details.