# EndlessDB Samples

Run samples from the repository root after starting MongoDB:

```powershell
docker compose -f samples/docker-compose.yml up -d
.\.venv\Scripts\python.exe samples\01_quickstart.py
```

Available samples:

- `01_quickstart.py` shows basic collection/document creation, attribute writes, and `to_dict()`.
- `02_nested_paths.py` shows nested dot-path item access and dynamic nested documents.
- `03_references.py` shows assigning one `EndlessDocument` as a reference from another document.
- `04_serialization.py` shows JSON, base64 JSON, YAML, bytes, and datetime serialization.
- `05_yaml_defaults.py` shows loading a read-only YAML collection with `CollectionLogicContainer.from_yml()`.
- `06_debugger_view.py` prints the debugger-friendly `repr()` values for database, collection, document, and nested document wrappers.

Each Mongo-backed sample creates temporary collections with unique names and drops them before exiting.
