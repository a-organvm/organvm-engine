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


**Prompting (Google)**: context 1M tokens (Gemini 1.5 Pro), format: markdown, thinking: thinking mode (thinkingConfig)


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


## ⚡ Conductor OS Integration
This repository is a managed component of the ORGANVM meta-workspace.
- **Orchestration:** Use `conductor patch` for system status and work queue.
- **Lifecycle:** Follow the `FRAME -> SHAPE -> BUILD -> PROVE` workflow.
- **Governance:** Promotions are managed via `conductor wip promote`.
- **Intelligence:** Conductor MCP tools are available for routing and mission synthesis.
