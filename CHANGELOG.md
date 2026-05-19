# Changelog

All notable changes to EndlessDB are documented in this file.

## Unreleased

### Changed
- Reworked the README for public project usage with PyPI installation, package imports, concise feature documentation, and no internal release or planning notes.
- Added a public roadmap and internal implementation plan for developer-tool positioning, strict mode, dictionary iteration clarity, query expansion, field deletion, patch/replace semantics, Python compatibility, quality tooling, and optional emoji representations.
- Lowered declared Python compatibility to Python 3.11+ and switched tests/samples toward public `endlessdb` imports while still testing the local source tree.

### Added
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
