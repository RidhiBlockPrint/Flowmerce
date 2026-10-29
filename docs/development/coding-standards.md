# Coding standards

- **Language:** Python 3.12+. Other languages only as recorded in ADR 0002; anything else needs explicit owner approval first.
- **Style:** PEP 8 enforced by `ruff` (line length 100, rules E,F,I,B,UP,N,S). Run `ruff format` before committing.
- **Naming:** `snake_case` modules/functions, `PascalCase` classes, `UPPER_CASE` constants. Names describe responsibility; no `utils2.py` or `misc.py`.
- **Types:** annotate all public functions and data structures; `mypy --strict` must pass for `src/`.
- **Docstrings:** every module, public class and public function. Explain business rules and non-obvious logic, not the obvious.
- **Errors:** raise specific exceptions with actionable messages (see `ConfigError`). No bare `except:`, no silent swallowing; catch broad `Exception` only at process boundaries and log it.
- **Logging:** use `logging.getLogger(__name__)`; never log secrets, tokens, passwords or customer personal data.
- **Imports:** absolute (`from flowmerce.config import ...`), standard library first, sorted by ruff.
- **Modularity:** one responsibility per file; modules do not import each other's internals.
- **Testing:** new behaviour and bug fixes ship with tests. Unit tests in `tests/unit/`, interaction tests in `tests/integration/`. Tests must not need network or real credentials.
- **Secrets:** environment variables only; `.env` is git-ignored; keep `.env.example` current.
- **Legacy exclusions:** `src/flowmerce/modules/seo`, its tests and `scripts/run_seo.py` are excluded from ruff and mypy in `pyproject.toml` because they were migrated unchanged. New code in those folders should meet the standards; remove the exclusions as files are cleaned up.
- **Documentation:** any file added, moved, changed or removed updates `docs/FILE_REGISTRY.md`, `docs/architecture/folder-structure.md` (if structure changed) and `CHANGELOG.md` in the same change.
