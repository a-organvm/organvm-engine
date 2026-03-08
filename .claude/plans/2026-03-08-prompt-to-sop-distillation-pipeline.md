# Plan: Prompt-to-SOP Distillation Pipeline

**Date:** 2026-03-08
**Status:** COMPLETED
**Organ:** META-ORGANVM
**Repo:** organvm-engine + praxis-perpetua

## Outcome

Built a four-module `distill/` package that bridges clipboard prompt classification → operational pattern taxonomy → SOP coverage analysis → SOP scaffolding, then used it to produce 8 new SOPs from 833 real clipboard prompts.

## Phase A: Pipeline Implementation (COMPLETED)

### New Package: `src/organvm_engine/distill/`

| Module | Purpose |
|--------|---------|
| `__init__.py` | Package docstring |
| `taxonomy.py` | 15 `OperationalPattern` definitions with regex/keyword/category signals, alias mappings |
| `matcher.py` | `match_prompt()` / `match_batch()` — scores prompts (regex=+0.3, keyword=+0.1, category=+0.2, threshold≥0.3) |
| `coverage.py` | `analyze_coverage()` — cross-refs matched patterns against discovered SOPs → covered/partial/uncovered |
| `scaffold.py` | `generate_sop_scaffold()` / `generate_scaffolds()` — produces SOP markdown with frontmatter |

### CLI Integration

- `cmd_prompts_distill()` added to `cli/prompts.py`
- Wired into `cli/__init__.py` as `organvm prompts distill`
- Args: `--input`, `--output-dir`, `--dry-run`, `--write`, `--json`, `--scaffold`

### Tests

- `tests/test_distill_taxonomy.py` — 8 tests
- `tests/test_distill_pipeline.py` — 23 tests
- All 31 tests pass

## Phase B: SOP Production (COMPLETED)

### Pipeline Results

833 clipboard prompts matched against 15 operational patterns. All 15 patterns hit.

### SOPs Produced

**6 T2 System SOPs** (in `praxis-perpetua/standards/`):
1. `SOP--planning-and-roadmapping.md` — there-and-back-again phased planning
2. `SOP--ontological-renaming.md` — dense naming with etymological roots
3. `SOP--agent-seeding-and-workforce-planning.md` — parallel agent workstream decomposition
4. `SOP--readme-and-documentation.md` — portfolio-standard README generation
5. `SOP--business-organism-design.md` — phased activation and scenario modeling
6. `SOP--completeness-verification.md` — end-to-end completeness sweep

**2 T3 Organ Directives** (in `meta-organvm/.sops/`):
7. `commit-and-release-workflow.md` — git commit/push/release protocol
8. `session-state-management.md` — session state preservation

### METADOC Updates

`METADOC--sop-ecosystem.md` updated:
- §3.1 inventory: entries 21-27 added
- §4 cluster map: Cluster 5 (Planning & Design) added, new SOPs placed in clusters
- §5 upstream/downstream: 6 new relationship rows
- §6 coverage matrix: 6 new domain rows
- §7 gap register: G11-G16 added and resolved
- §10 skill mappings: 5 new T1↔T2 mappings
- §10 lifecycle phases: new SOPs placed in genesis/foundation/hardening

### Coverage

- Before: 2/15 patterns covered (13.3%)
- After: 13/15 patterns covered (86.7%)
- Remaining 2 intentionally uncovered (too granular: feature-expand=1 prompt, gh-issues=operational)

## Files Changed

### New Files (12)
- `src/organvm_engine/distill/__init__.py`
- `src/organvm_engine/distill/taxonomy.py`
- `src/organvm_engine/distill/matcher.py`
- `src/organvm_engine/distill/coverage.py`
- `src/organvm_engine/distill/scaffold.py`
- `tests/test_distill_taxonomy.py`
- `tests/test_distill_pipeline.py`
- `praxis-perpetua/standards/SOP--planning-and-roadmapping.md`
- `praxis-perpetua/standards/SOP--ontological-renaming.md`
- `praxis-perpetua/standards/SOP--agent-seeding-and-workforce-planning.md`
- `praxis-perpetua/standards/SOP--readme-and-documentation.md`
- `praxis-perpetua/standards/SOP--business-organism-design.md`
- `praxis-perpetua/standards/SOP--completeness-verification.md`

### Modified Files (4)
- `src/organvm_engine/cli/prompts.py` — added `cmd_prompts_distill()`
- `src/organvm_engine/cli/__init__.py` — wired distill subcommand
- `meta-organvm/.sops/commit-and-release-workflow.md` — new T3 directive
- `meta-organvm/.sops/session-state-management.md` — new T3 directive
- `praxis-perpetua/standards/METADOC--sop-ecosystem.md` — inventory/cluster/coverage updates
