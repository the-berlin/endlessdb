# Changelog

All notable changes to EndlessDB are documented in this file.

## Unreleased

### Changed
- Reworked the README for public project usage with PyPI installation, package imports, concise feature documentation, and no internal release or planning notes.

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
