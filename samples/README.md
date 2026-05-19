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
- `07_strict_mode.py` shows typo-safe strict mode with `PropertyNotFoundError` for missing documents and fields.
- `08_query_helpers.py` shows `find()`, `count()`, `exists()`, `first()`, sorting, limiting, and raw PyMongo access.
- `09_updates_and_deletes.py` shows patch-compatible assignment, explicit `patch()`, `replace()`, `unset()`, nested delete, and root document delete.
- `storage/` contains a small Mongo-backed task storage CLI app built on an EndlessDB service class.
- `notebook/` contains a Jupyter notebook app for interactive EndlessDB exploration.

Each Mongo-backed sample creates temporary collections with unique names and drops them before exiting.

For a fuller API walkthrough, see `docs/usage.md` from the repository root.
