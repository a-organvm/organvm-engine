# Agent Handoff: claude → opencode

**Session:** 2026-03-30-dispatch-signal-closure
**Phase:** BUILD
**Organ:** META-ORGANVM | **Repo:** organvm-engine
**Scope:** Build validate_signal_closure + fix essay-pipeline CI
**Timestamp:** 2026-03-30

## Summary

Two well-scoped code tasks. Both are infrastructure work with clear test requirements.

## Task 1: Build validate_signal_closure

Read these files first:
- `governance-rules.json` — the `entailment_flows` section
- `src/organvm_engine/governance/dictums.py` — existing validators

Implement `validate_signal_closure()`:
- For each organ with active repos (non-ARCHIVED in registry)
- Check that all entailed target organs per the entailment matrix have at least one `seed.yaml` `produces` edge pointing at them
- Emit audit findings for missing edges

Wire into CLI:
- `organvm governance audit --signal-closure`

Add tests:
- `tests/test_governance_signal_closure.py`

## Task 2: Fix essay-pipeline CI

**Repo:** `organvm-v-logos/essay-pipeline` (DIFFERENT repo — switch after Task 1)

- Branch `feat/ax6-signal-closure-edges` has a seed.yaml-only change
- Branch protection requires the test status check to pass
- Check what CI workflow runs the test check
- Ensure it passes on the branch
- Then merge PR #8

**Work Type:** debugging

**CROSS-VERIFICATION REQUIRED** — Do not trust the originating agent's self-assessment. Verify all output.

## Locked Constraints (DO NOT OVERRIDE)

- validate_signal_closure must read from registry-v2.json (production registry)
- Use existing validator patterns in dictums.py — don't invent new patterns
- Tests must use tmp_path fixtures, never write to production registry
- The entailment matrix is in governance-rules.json — don't hardcode organ relationships

## Locked Files (DO NOT MODIFY)

- `registry-v2.json` (read-only — never overwrite production data)
- `governance-rules.json` (read-only — the source of truth for entailment flows)

## Work Already Completed (DO NOT REPEAT)

- The entailment_flows section already exists in governance-rules.json
- Existing validators in dictums.py provide the pattern to follow
- seed.yaml schema is already defined — don't redesign it

## Active Conventions

- **python_style**: PEP 8, type hints, f-strings, ruff linting
- **testing**: pytest, tmp_path fixtures, never touch production data
- **naming**: snake_case functions, PascalCase classes

## Receiver Restrictions

Files you MUST NOT touch:
- `registry-v2.json`
- `governance-rules.json`
- `*.config.*`
- `.env*`
- `pyproject.toml` (unless adding a CLI entry point)
