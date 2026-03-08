# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Core Python package for the ORGANVM eight-organ system: registry, governance, seed discovery, metrics, dispatch, git superproject management, context file sync, session analysis, plan atomization, prompt narrative extraction, and the unified `organvm` CLI.

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

Every other module imports from these; change them carefully.

- **`organ_config.py`** — Single source of truth for organ key/directory/registry-key/GitHub-org mappings. The `ORGANS` dict maps CLI short keys (`"I"`, `"META"`, `"LIMINAL"`) to metadata. All organ lookups across the codebase derive from helper functions here (`organ_dir_map`, `organ_aliases`, `registry_key_to_dir`, etc.).

- **`paths.py`** — Resolves canonical filesystem paths (`workspace_root`, `corpus_dir`, `registry_path`, `governance_rules_path`, `soak_dir`, `atoms_dir`). Reads `ORGANVM_WORKSPACE_DIR` and `ORGANVM_CORPUS_DIR` env vars, falls back to `~/Workspace` conventions.

- **`domain.py`** — Content-based identity for atomic units. `domain_fingerprint()` produces a SHA256[:16] digest from tags + file refs. `domain_set()` builds prefixed sets for Jaccard similarity comparison. Used by both `atoms/` and `prompts/` to link tasks and prompts by content DNA.

- **`project_slug.py`** — Canonical project slug derivation (`meta-organvm/organvm-engine` form). Converts filesystem paths, plan directory names, and raw slugs to a normalized slash-separated format. Shared across `prompts/`, `plans/`, and `session/`.

### Domain modules (16)

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
| `plans/` | Plan file atomization, indexing, hygiene checks, overlap detection, and per-organ synthesis |
| `prompts/` | Prompt extraction, classification, narrative threading, and clipboard history analysis |
| `atoms/` | Cross-system linking pipeline: Jaccard matching tasks↔prompts, git reconciliation, per-organ rollups |
| `cli/` | One module per command group (21 modules), wired together in `cli/__init__.py` |

### The atomization pipeline

The `atoms/`, `plans/`, and `prompts/` modules form a three-stage pipeline that can run independently or chained via `organvm atoms pipeline`:

1. **Atomize** (`plans/atomizer.py`) — Parse plan `.md` files into atomic tasks with tags, file refs, status, and project metadata. Discovers plans across `~/.claude/plans/`, `.gemini/plans/`, `.codex/plans/` in every workspace project.

2. **Narrate** (`prompts/narrator.py`) — Extract user prompts from session transcripts, classify them (`prompts/classifier.py`), assign domain fingerprints, and thread them into narrative episodes (`prompts/threading.py`).

3. **Link** (`atoms/linker.py`) — Jaccard-match atomized tasks against annotated prompts using `domain.py` domain sets. Produces `atom-links.jsonl`.

4. **Reconcile** (`atoms/reconciler.py`) — Cross-reference tasks against git commit history to detect completed work. Verdicts: `likely_completed`, `partially_done`, `stale`, `unknown`.

5. **Fanout** (`atoms/rollup.py`) — Aggregate centralized atom data into per-organ rollup JSON files in each organ superproject's `.atoms/` directory.

All pipeline outputs go to `corpus_dir/data/atoms/` with a `pipeline-manifest.json` tracking file hashes and counts.

### CLI dispatch pattern

`cli/__init__.py` builds an argparse tree with `build_parser()`. Commands with subcommands that are in the original tuple-dict (`registry`, `governance`, `seed`, `metrics`, etc.) dispatch via `{(command, subcommand): handler}`. Newer command groups (`session`, `plans`, `prompts`, `atoms`, `organism`) use per-group inline dispatch dicts in explicit `if args.command == ...` branches. Top-level commands without subcommands (`status`, `deadlines`, `refresh`, `lint-vars`) dispatch via standalone `if` branches. Each CLI module exports `cmd_*` functions taking `argparse.Namespace` and returning `int`.

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
- **Dry-run by default** — destructive CLI commands (`context sync`, `omega update`, `plans tidy`, `atoms pipeline`) default to `--dry-run=True` and require `--write` to execute

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `ORGANVM_WORKSPACE_DIR` | `~/Workspace` | Workspace root for all organ directories |
| `ORGANVM_CORPUS_DIR` | `<workspace>/meta-organvm/organvm-corpvs-testamentvm` | Path to corpus repo (registry, governance rules) |

<!-- ORGANVM:AUTO:START -->
## System Context (auto-generated — do not edit)

**Organ:** META-ORGANVM (Meta) | **Tier:** flagship | **Status:** CANDIDATE
**Org:** `meta-organvm` | **Repo:** `organvm-engine`

### Edges
- **Produces** → `ORGAN-IV, META-ORGANVM`: governance-policy
- **Produces** → `ORGAN-IV, META-ORGANVM`: registry
- **Consumes** ← `META-ORGANVM`: registry
- **Consumes** ← `META-ORGANVM`: schema

### Siblings in Meta
`.github`, `organvm-corpvs-testamentvm`, `alchemia-ingestvm`, `schema-definitions`, `system-dashboard`, `organvm-mcp-server`, `praxis-perpetua`

### Governance
- *Standard ORGANVM governance applies*

*Last synced: 2026-03-08T13:07:06Z*

## Session Review Protocol

At the end of each session that produces or modifies files:
1. Run `organvm session review --latest` to get a session summary
2. Check for unimplemented plans: `organvm session plans --project .`
3. Export significant sessions: `organvm session export <id> --slug <slug>`

Transcripts are on-demand (never committed):
- `organvm session transcript <id>` — conversation summary
- `organvm session transcript <id> --unabridged` — full audit trail
- `organvm session prompts <id>` — human prompts only


## Active Directives

| Scope | Phase | Name | Description |
|-------|-------|------|-------------|
| repo | any | cli-module-pattern | cli-module-pattern |
| organ | any | commit-and-release-workflow | Commit & Release Workflow |
| organ | any | session-state-management | session-state-management |
| organ | any | submodule-sync-protocol | submodule-sync-protocol |
| system | any | prompting-standards | Prompting Standards |
| system | any | research-standards-bibliography | APPENDIX: Research Standards Bibliography |
| system | any | research-standards | METADOC: Architectural Typology & Research Standards |
| system | any | sop-ecosystem | METADOC: SOP Ecosystem — Taxonomy, Inventory & Coverage |
| system | any | autopoietic-systems-diagnostics | SOP: Autopoietic Systems Diagnostics (The Mirror of Eternity) |
| system | any | cicd-resilience-and-recovery | SOP: CI/CD Pipeline Resilience & Recovery |
| system | hardening | completeness-verification | completeness-verification |
| system | any | cross-agent-handoff | SOP: Cross-Agent Session Handoff |
| system | any | document-audit-feature-extraction | SOP: Document Audit & Feature Extraction |
| system | any | essay-publishing-and-distribution | SOP: Essay Publishing & Distribution |
| system | any | market-gap-analysis | SOP: Full-Breath Market-Gap Analysis & Defensive Parrying |
| system | any | pitch-deck-rollout | SOP: Pitch Deck Generation & Rollout |
| system | hardening | product-deployment-and-revenue-activation | product-deployment-and-revenue-activation |
| system | any | promotion-and-state-transitions | SOP: Promotion & State Transitions |
| system | any | repo-onboarding-and-habitat-creation | SOP: Repo Onboarding & Habitat Creation |
| system | any | research-to-implementation-pipeline | SOP: Research-to-Implementation Pipeline (The Gold Path) |
| system | any | security-and-accessibility-audit | SOP: Security & Accessibility Audit |
| system | any | session-self-critique | session-self-critique |
| system | any | source-evaluation-and-bibliography | SOP: Source Evaluation & Annotated Bibliography (The Refinery) |
| system | any | stranger-test-protocol | SOP: Stranger Test Protocol |
| system | any | strategic-foresight-and-futures | SOP: Strategic Foresight & Futures (The Telescope) |
| system | hardening | structural-integrity-audit | structural-integrity-audit |
| system | any | typological-hermeneutic-analysis | SOP: Typological & Hermeneutic Analysis (The Archaeology) |
| unknown | any | SOP-001-vector-pipeline-activation | SOP-001: Vector Pipeline Activation |
| unknown | any | cicd-resilience | SOP: CI/CD Pipeline Resilience & Recovery |
| unknown | any | document-audit-feature-extraction | SOP: Document Audit & Feature Extraction v2.0 |
| unknown | any | pitch-deck-rollout | SOP: Pitch Deck Generation & Rollout |

Linked skills: cross-agent-handoff, deployment-cicd, evaluation-to-growth, session-self-critique, structural-integrity-audit, verification-loop


**Prompting (Anthropic)**: context 200K tokens, format: XML tags, thinking: extended thinking (budget_tokens)


## Task Queue (from pipeline)

**80** pending tasks | Last pipeline: unknown

- `54c4a1aea9f6` 1. `taxonomy.py` — 15 Operational Patterns [bash, express, go]
- `72a9af6b5018` 2. `matcher.py` — Scoring Logic [bash, express, go]
- `4485ac8f6a2a` 3. `coverage.py` — SOP Coverage Report [bash, express, go]
- `60e49fdaec6c` 4. `scaffold.py` — SOP Generation [bash, express, go]
- `f04f9c8af299` tests/test_distill_taxonomy.py — pattern definitions, regex matching [bash, express, go]
- `75ab138ca5ac` tests/test_distill_pipeline.py — matcher scoring, coverage analysis, scaffold generation [bash, express, go]
- `67b2e6ebb226` taxonomy.py (pure data, no deps) [bash, express, go]
- `2f94b5f043e6` matcher.py (depends on taxonomy + clipboard schema) [bash, express, go]
- ... and 72 more

Cross-organ links: 416 | Top tags: `python`, `bash`, `pytest`, `mcp`, `go`

Run: `organvm atoms pipeline --write && organvm atoms fanout --write`

<!-- ORGANVM:AUTO:END -->
