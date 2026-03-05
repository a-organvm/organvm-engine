# CLAUDE.md — organvm-engine

**ORGAN Meta** (Meta) · `meta-organvm/organvm-engine`
**Status:** ACTIVE · **Branch:** `main`

## What This Repo Is

Core Python package — governance, registry, seed discovery, metrics, dispatch, and unified CLI for the eight-organ system. Consolidates ~30 standalone scripts into a proper installable package.

## Stack

**Languages:** Python
**Build:** Python (pip/setuptools)
**Testing:** pytest (likely)

## Directory Structure

```
📁 .github/
📁 src/
    organvm_engine
📁 tests/
    fixtures
    test_dispatch.py
    test_governance.py
    test_metrics.py
    test_registry.py
    test_seed.py
  CHANGELOG.md
  README.md
  pyproject.toml
  seed.yaml
```

## Key Files

- `README.md` — Project documentation
- `pyproject.toml` — Python project config
- `seed.yaml` — ORGANVM orchestration metadata
- `src/` — Main source code
- `tests/` — Test suite

## Development

```bash
pip install -e .    # Install in development mode
pytest              # Run tests
```

## ORGANVM Context

This repository is part of the **ORGANVM** eight-organ creative-institutional system.
It belongs to **ORGAN Meta (Meta)** under the `meta-organvm` GitHub organization.

**Dependencies:**
- meta-organvm/schema-definitions

**Registry:** [`registry-v2.json`](https://github.com/meta-organvm/organvm-corpvs-testamentvm/blob/main/registry-v2.json)
**Corpus:** [`organvm-corpvs-testamentvm`](https://github.com/meta-organvm/organvm-corpvs-testamentvm)

<!-- ORGANVM:AUTO:START -->
## System Context (auto-generated — do not edit)

**Organ:** META-ORGANVM (Meta) | **Tier:** flagship | **Status:** CANDIDATE
**Org:** `unknown` | **Repo:** `organvm-engine`

### Edges
- **Produces** → `unknown`: unknown
- **Produces** → `unknown`: unknown
- **Consumes** ← `META-ORGANVM`: unknown
- **Consumes** ← `META-ORGANVM`: unknown

### Siblings in Meta
`.github`, `organvm-corpvs-testamentvm`, `alchemia-ingestvm`, `schema-definitions`, `system-dashboard`, `organvm-mcp-server`

### Governance
- *Standard ORGANVM governance applies*

*Last synced: 2026-02-24T12:41:28Z*
<!-- ORGANVM:AUTO:END -->


## ⚡ Conductor OS Integration
This repository is a managed component of the ORGANVM meta-workspace.
- **Orchestration:** Use `conductor patch` for system status and work queue.
- **Lifecycle:** Follow the `FRAME -> SHAPE -> BUILD -> PROVE` workflow.
- **Governance:** Promotions are managed via `conductor wip promote`.
- **Intelligence:** Conductor MCP tools are available for routing and mission synthesis.
