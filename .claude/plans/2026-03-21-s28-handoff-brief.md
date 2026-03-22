# S28 Handoff Brief — Engine Remediation Session

Date: 2026-03-21
Session: S28 (engine-remediation)
Project: meta-organvm/organvm-engine

## Session Summary

- **30 GitHub issues** implemented across organvm-engine
- **CI fully green** (was broken at session start)
- **4584 tests** (up from 4253), 0 pyright errors, ruff clean
- **67 GitHub labels** with precise descriptions
- **Omega 8/19** (up from 4/17, criterion #19 added)
- **6 new IRF items** from gap audit
- **28 DONE entries** in IRF (DONE-057–084)
- **13 open issues** with full handoff comments posted

## What Shipped

### CI/Infrastructure
- Fixed pip install (ontologia → optional dep)
- Resolved 206 ruff + 34 pyright violations
- Removed CodeQL workflow conflict (default setup active)
- Added permissions blocks to all 5 workflows
- Fixed URL sanitization (CWE-020) in scanner.py
- Bumped actions/checkout v4→v6, setup-python v5→v6
- Added monthly infrastructure audit workflow (#62)

### New Modules
- `debt/` — DEBT header detection and tracking (#23)
- `governance/temporal.py` — temporal versioning for dep graph (#8)
- `governance/individual_primacy.py` — HITL governance check (#21)
- `seed/signals.py` — signal I/O in seed.yaml (#20)
- `atoms/research.py` — research activation pipeline stage (#9)
- `ledger/rotation.py` — chain.jsonl rotation at 100MB (#56)
- `ledger/anchor.py` — chain anchor foundation for future L2 (#55)
- `ci/scaffold.py` — CI workflow YAML generation (#58-60)
- `ci/protect.py` — branch protection planning (#61)
- `cli/completion.py` — shell completion bash/zsh/fish (#4)

### Enhancements
- EventType enum 21→49 members (#57)
- Omega criterion #19 Network Testament (#67)
- registry list --json (#2)
- tomllib scanner replacing regex (#68)
- docs-only detection expanded (#63)
- content-based CodeQL/release detection (#64)
- parallel mirrors 27→127, kinship 11→61 (#65-66)
- promotion_history recording (#44)
- per-repo metrics propagation (#43)
- lifecycle dedup SPEC-013/014 (#36)
- testament play CLI + public API (#49, #54)
- audit.py type hints (#3)

## What Remains Open

### 13 GitHub Issues (all have handoff comments)
- #10: Conductor lifecycle (wrong repo, organ:IV)
- #20: AX-009 signal I/O (partially done, patch matrix remaining)
- #21: AX-003 individual primacy (partially done, enforcement remaining)
- #41: Soak-test LaunchAgent (human-config)
- #42: Conference talk proposals (human-submit)
- #49: Sonic bridge verification (needs OSC testing)
- #54: Portal /testament/ route (wrong repo)
- #55: Ring 4 blockchain anchoring (foundation shipped, horizon-3)
- #59: Add testing to 4 repos (tooling shipped, execution pending)
- #60: Add type-checking to 6 repos (tooling shipped, execution pending)
- #61: Branch protection expansion (tooling shipped, execution pending)
- #64: CodeQL detection (fully implemented — ready to close on review)
- #66: Kinship research (substantially done, human review needed)

### 6 New IRF Items from Gap Audit
- IRF-SYS-010 (P1): seed.yaml declares 5 contracts, actual is 30+
- IRF-CRP-005 (P1): concordance 1 month stale, 16+ types missing
- IRF-TST-002 (P1): testament chain self-referential blind spot
- IRF-CRP-004 (P2): registry entry understates capabilities
- IRF-IDX-004 (P2): no generator tooling for companion indices
- IRF-SGO-007 (P2): AX-003/AX-008 unrecorded in inquiry log

## P1 Agent Items — Quick Reference

See full handoff briefs in the IRF gap audit research. The 18 P1 agent items
each have: current state, what needs doing, key files, prerequisites, effort estimate,
and suggested first step.

## Verification

```bash
cd /Users/4jp/Workspace/meta-organvm && source .venv/bin/activate && cd organvm-engine
pytest tests/ --tb=short -q    # 4584 passed
ruff check src/ tests/         # All checks passed
pyright src/                   # 0 errors, 0 warnings
organvm omega status           # 8/19 MET
organvm irf stats              # 143 active, 91 completed
```
