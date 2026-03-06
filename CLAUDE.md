# CLAUDE.md — organvm-engine

Core Python package for the ORGANVM eight-organ system: registry, governance, seed discovery, metrics, dispatch, git superproject management, context file sync, session analysis, and the unified `organvm` CLI.

## Commands

```bash
# Install (use the workspace venv at meta-organvm/.venv)
pip install -e ".[dev]"

# Test
pytest tests/ -v                              # all tests
pytest tests/test_registry.py -v              # one module
pytest tests/test_registry.py::test_name -v   # one test

# Lint
ruff check src/

# Typecheck
pyright
```

## Architecture

### Foundation modules

Every other module imports from these two; change them carefully.

- **`organ_config.py`** — Single source of truth for organ key/directory/registry-key/GitHub-org mappings. The `ORGANS` dict maps CLI short keys (`"I"`, `"META"`, `"LIMINAL"`) to metadata. All organ lookups across the codebase derive from helper functions here (`organ_dir_map`, `organ_aliases`, `registry_key_to_dir`, etc.).

- **`paths.py`** — Resolves canonical filesystem paths (`workspace_root`, `corpus_dir`, `registry_path`, `governance_rules_path`, `soak_dir`). Reads `ORGANVM_WORKSPACE_DIR` and `ORGANVM_CORPUS_DIR` env vars, falls back to `~/Workspace` conventions.

### Domain modules (13)

| Module | Role |
|--------|------|
| `registry/` | Load/save/query/validate/update `registry-v2.json` |
| `governance/` | Promotion state machine, dependency graph validation, audit, blast-radius impact |
| `seed/` | Discover `seed.yaml` files across workspace, read them, build produces/consumes graph |
| `metrics/` | Calculate system metrics, propagate into markdown/JSON, timeseries, variable resolution |
| `dispatch/` | Event payload validation, routing, cascade |
| `git/` | Superproject init/sync, submodule status/drift, workspace reproduction |
| `contextmd/` | Auto-generate CLAUDE.md/GEMINI.md/AGENTS.md across all repos from templates |
| `omega/` | 17-criterion binary scorecard for system maturity |
| `ci/` | CI health triage from soak-test data |
| `deadlines/` | Parse deadlines from `rolling-todo.md` |
| `pitchdeck/` | HTML pitch deck generation per repo |
| `session/` | Multi-agent session transcript parsing (Claude, Gemini, Codex), plan auditing, prompt analysis |
| `cli/` | One module per command group, wired together in `cli/__init__.py` |

### CLI dispatch pattern

`cli/__init__.py` builds an argparse tree with `build_parser()` and dispatches via a `(command, subcommand)` tuple dict. Each CLI module (e.g., `cli/registry.py`) exports `cmd_*` functions that take an `argparse.Namespace` and return an `int` exit code. Top-level commands without subcommands (`status`, `deadlines`, `refresh`, `lint-vars`, `organism`, `session`) are dispatched via explicit `if` branches before the dict lookup.

### Registry data safety

`registry/loader.py` → `save_registry()` refuses to write fewer than 50 repos to the production path. This prevents test fixtures from accidentally overwriting the real `registry-v2.json` (2,200+ lines).

### Test isolation

`tests/conftest.py` has an **autouse** fixture `_block_production_paths` that monkeypatches `paths._DEFAULT_WORKSPACE` and `loader._default_registry_path` to `/nonexistent/organvm-test-guard`. Every test runs in this sandbox — any test needing real file I/O must use `tmp_path` or `tests/fixtures/`. The `registry` fixture loads `fixtures/registry-minimal.json`.

## Key conventions

- **`src/` layout** — all imports are `from organvm_engine.X import Y`
- **No default exports** — CLI entry point is `organvm_engine.cli:main` (declared in `pyproject.toml`)
- **ruff config** — line-length 100, py311, rules: E/F/W/I/B/PTH/RET/SIM/COM/PL (see `pyproject.toml` for ignores)
- **pyright** — basic mode, py311
- **Commit prefixes** — `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `ORGANVM_WORKSPACE_DIR` | `~/Workspace` | Workspace root for all organ directories |
| `ORGANVM_CORPUS_DIR` | `<workspace>/meta-organvm/organvm-corpvs-testamentvm` | Path to corpus repo (registry, governance rules) |
