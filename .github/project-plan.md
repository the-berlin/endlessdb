# EndlessDB Project Plan

This plan captures the preparation and implementation work needed to turn the current dynamic MongoDB wrapper into a documented, tested, and release-ready package.

## Current Preparation State

- Local virtual environment: `.venv` with Python 3.13.1.
- Installed development dependencies: runtime requirements, `pytest`, `build`, and `twine`.
- Integration MongoDB target: `mongodb://root:root@localhost:27017/` from `tests/docker-compose.yml`.
- Docker CLI is available; use the standard MongoDB port `27017` for local samples and integration tests.
- Current branch state before implementation: local `main` is ahead of `origin/main`; there is an existing local deletion of `endlessdb.code-workspace` that is unrelated to this plan.
- Do not read, print, or commit local `.pypirc` credentials.

## Completed Implementation

- Expanded `README.md` with the object model, configuration, CRUD, references, serialization, debugger visualization, development setup, and release notes.
- Updated `.github/copilot-instructions.md` with `.venv`, planning, testing, and PyPI publishing workflows.
- Standardized local MongoDB usage on `mongodb://root:root@localhost:27017/` in tests, docs, and Docker Compose files.
- Replaced the old broad skipped scenario in `tests/test_endlessdb.py` with focused pytest coverage.
- Fixed module consistency issues around configuration defaults, YAML loading/reload, descendant caching, `create`/`rewrite`, `find`, collection equality, protected/root returns, user-facing typos, and value validation before Mongo writes.
- Current verification result: `10 passed` with `.\.venv\Scripts\python.exe -m pytest tests -q`.

## Documentation Work

- Keep README examples aligned with tested behavior as the API evolves.
- Add more advanced examples for typed descendants after the behavior is fully specified.
- Add packaging installation examples after the next PyPI release is published and verified.

## Module Consistency Backlog

- Continue replacing broad `except:` blocks with explicit conversions and error handling.
- Decide whether the temporary helper wrapper class `w` should be removed or documented.
- Clarify typed descendant behavior for scalar type expectations and expand tests for it.
- Consider introducing custom exception types instead of broad `Exception` messages.
- Review whether dynamic `__getattribute__` in `EndlessConfiguration` can be simplified without breaking override inheritance.

## Test Plan

- Add dedicated tests for magic-key escaping once the desired external API is documented.
- Add negative tests for missing YAML files and non-dict YAML files.
- Add explicit tests for typed descendant scalar expectations such as `int` and `str`.
- Add tests for list values and nested lists in Mongo writes.
- Add packaging smoke tests after packaging metadata is finalized.

## Release Plan

- Before any TestPyPI or PyPI upload, change `[project].version` in `pyproject.toml`.
- Verify the chosen version does not already exist on TestPyPI or PyPI.
- Build in a clean local state with `.venv` tools: `.\.venv\Scripts\python.exe -m build` and `.\.venv\Scripts\python.exe -m twine check dist/*`.
- Upload to TestPyPI first, verify installation, then upload the same artifacts to public PyPI.
- Never commit tokens, `.pypirc`, generated MongoDB data, build artifacts, or test exports.

## Verification Commands

Run tests with:

```powershell
Set-Location S:\development\source\endlessdb
.\.venv\Scripts\python.exe -m pytest tests
```

If MongoDB is not running, start it with:

```powershell
docker compose -f tests/docker-compose.yml up -d
```