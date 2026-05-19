# Changelog

All notable changes to EndlessDB are documented in this file.

## 0.5.2 - 2026-05-20

### Changed
- Added Ruff format checks to CI and documented the formatter workflow.
- Applied the Ruff formatter to the existing Python source, tests, and samples.

### Added
- Added `docs/usage.md` with practical API guidance for configuration, strict mode, queries, updates, deletes, references, serialization, YAML defaults, representations, and 0.4.x migration notes.
- Expanded `samples/storage` into a small Mongo-backed task storage CLI app and added a notebook app under `samples/notebook`.

## 0.5.1 - 2026-05-20

### Changed
- Replaced the public README roadmap section with a current project status note and a short future-improvements paragraph.

## 0.5.0 - 2026-05-20

### Changed
- Changed `to_dict()` on database, collection, and document logic containers to return concrete dictionaries; lazy key/value traversal is now exposed through `iter_items()`.
- Switched default `repr()` output to plain professional representations while keeping emoji-rich debugger output behind `debug=True` or `emojify=True`.
- Kept collection item assignment patch-compatible and documented explicit `patch()` versus `replace()` semantics.
- Reworked the README for public project usage with PyPI installation, package imports, concise feature documentation, and no internal release or planning notes.
- Added a public roadmap and internal implementation plan for developer-tool positioning, strict mode, dictionary iteration clarity, query expansion, field deletion, patch/replace semantics, Python compatibility, quality tooling, and optional emoji representations.
- Lowered declared Python compatibility to Python 3.11+ and switched tests/samples toward public `endlessdb` imports while still testing the local source tree.

### Added
- Added Ruff lint/import checks and pytest coverage reporting with a 70% baseline gate to the development and CI workflow.
- Added runnable samples for strict mode, query helpers, and explicit update/delete semantics.
- Added `strict=True` support for `EndlessDatabase` and wrapper logic calls so missing collections, documents, and fields raise typed `PropertyNotFoundError` instead of silently creating virtual descendants.
- Added collection query helpers for sort, limit, skip, projection validation, `count()`, `exists()`, `first()`, and `raw()` PyMongo collection access.
- Added explicit field deletion helpers through `unset()` and nested document `delete()` behavior that uses MongoDB `$unset` while keeping root document deletion explicit.
- Added explicit `patch()` and `replace()` methods for root document writes.
- Expanded integration coverage for strict mode, query helpers, `to_dict()`/`iter_items()`, unset/delete, patch/replace, and plain/emoji representations.
- Added GitHub Actions CI for Python 3.11, 3.12, and 3.13 with MongoDB integration tests and package distribution checks.
- Added a tag-driven GitHub Release workflow that builds, validates, and attaches wheel/source distributions to releases.
- Added `scripts/create-github-release-tag.ps1` to create and push `v<version>` tags that trigger GitHub Releases.

## 0.4.16 - 2026-05-20

### Changed
- Documented the main module as a canonical Python module with public exports, logic-container docstrings, dynamic wrapper docstrings, and clearer section boundaries.
- Kept `EndlessConfiguration` as the global default source while making explicit `EndlessDatabase(...)` connection arguments act as per-instance overrides.
- Changed `CollectionLogicContainer.find()` to behave like a normal Python iterator: an empty query now yields no values; use `find_one()` when a single `None` result is desired.

### Added
- Added typed EndlessDB exception classes for read-only access, invalid values, unsupported comparisons, missing dynamic properties, and type expectation failures.
- Added broader URL masking/building coverage for MongoDB URLs with credentials, without credentials, database names, and query strings.
- Added explicit TestPyPI and PyPI upload scripts that use the repository-local `.pypirc` through Twine's `--config-file` option.

### Removed
- Removed the unused public `w` dictionary proxy helper from the module API.
