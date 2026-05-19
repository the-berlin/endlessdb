# Storage CLI Sample App

This folder contains a tiny Mongo-backed task storage CLI app built on EndlessDB.

It is intentionally small: `StorageService` wraps an `EndlessCollection`, uses YAML settings from `config.yml`, and exposes methods that look like normal application code while still keeping the underlying PyMongo collection reachable through EndlessDB.

Run from the repository root after starting MongoDB:

```powershell
docker compose -f samples/docker-compose.yml up -d
.\.venv\Scripts\python.exe samples\storage\app.py
```

The default `demo` command creates sample tasks, marks one complete, prints filtered query results, exports the collection as JSON, and drops its sample collection before exiting.

You can also use it as a tiny CLI application:

```powershell
.\.venv\Scripts\python.exe samples\storage\app.py add inbox "Review storage app" --tag docs
.\.venv\Scripts\python.exe samples\storage\app.py list --state open
.\.venv\Scripts\python.exe samples\storage\app.py complete inbox
.\.venv\Scripts\python.exe samples\storage\app.py export
.\.venv\Scripts\python.exe samples\storage\app.py reset
.\.venv\Scripts\python.exe samples\storage\app.py --help
```

Use `--collection <name>` before the command to point the app at a different Mongo collection without changing `config.yml`.