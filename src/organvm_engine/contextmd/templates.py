"""Markdown templates for auto-generated context file sections.

Templates use str.format() with named placeholders. Each template
targets a specific file type (CLAUDE.md, GEMINI.md, AGENTS.md)
and level (workspace, organ, or repo).
"""

from __future__ import annotations

# ruff: noqa: E501

# ── Repo-level template (CLAUDE.md / GEMINI.md) ───────────────────

REPO_SECTION = """\
<!-- ORGANVM:AUTO:START -->
## System Context (auto-generated — do not edit)

**Organ:** {organ_key} ({organ_name}) | **Tier:** {tier} | **Status:** {promotion_status}
**Org:** `{org}` | **Repo:** `{repo_name}`

### Edges
{edges_block}

### Siblings in {organ_name}
{siblings_block}

### Governance
{governance_block}

*Last synced: {timestamp}*
<!-- ORGANVM:AUTO:END -->"""

# ── Agents-level template (AGENTS.md) ─────────────────────────────

AGENTS_SECTION = """\
<!-- ORGANVM:AUTO:START -->
## Agent Context (auto-generated — do not edit)

This repo participates in the **{organ_key} ({organ_name})** swarm.

### Active Subscriptions
{subscriptions_block}

### Production Responsibilities
{produces_block}

### External Dependencies
{consumes_block}

### Governance Constraints
{governance_block}

*Last synced: {timestamp}*
<!-- ORGANVM:AUTO:END -->"""

# ── Organ-level template ──────────────────────────────────────────

ORGAN_SECTION = """\
<!-- ORGANVM:AUTO:START -->
## Organ Map (auto-generated — do not edit)

**{organ_key}: {organ_name}** | {repo_count} repos | {flagship_count} flagship | {standard_count} standard | {infra_count} infrastructure

### Inter-Organ Edges
{organ_edges_block}

### Repos
{repo_list_block}

### Promotion Pipeline
{promotion_block}

*Last synced: {timestamp}*
<!-- ORGANVM:AUTO:END -->"""

# ── Workspace-level template ──────────────────────────────────────

WORKSPACE_SECTION = """\
<!-- ORGANVM:AUTO:START -->
## System Overview (auto-generated — do not edit)

**{total_repos} repos** across **{organ_count} organs** + personal workspace

| Organ | Repos | Flagship | Status |
|-------|-------|----------|--------|
{organ_table_rows}

### System Health
- Seed coverage: {seed_coverage}
- CI workflows: {ci_count}
- Omega progress: {omega_met}/{omega_total} criteria met

*Last synced: {timestamp}*
<!-- ORGANVM:AUTO:END -->"""


# ── Edge formatting helpers ───────────────────────────────────────


def format_produces_edge(target: str, artifact: str, event: str = "") -> str:
    """Format a single produces edge as a markdown line."""
    event_str = f" (event: `{event}`)" if event else ""
    return f"- **Produces** → `{target}`: {artifact}{event_str}"


def format_consumes_edge(source: str, artifact: str, event: str = "") -> str:
    """Format a single consumes edge as a markdown line."""
    event_str = f" (event: `{event}`)" if event else ""
    return f"- **Consumes** ← `{source}`: {artifact}{event_str}"


def format_no_edges() -> str:
    """Placeholder when no edges exist."""
    return "- *No inter-repo edges declared in seed.yaml*"


# ── Session review protocol (injected into repo-level context) ────

SESSION_REVIEW_SECTION = """\

## Session Review Protocol

At the end of each session that produces or modifies files:
1. Run `organvm session review --latest` to get a session summary
2. Check for unimplemented plans: `organvm session plans --project .`
3. Export significant sessions: `organvm session export <id> --slug <slug>`
4. Run `organvm prompts distill --dry-run` to detect uncovered operational patterns

Transcripts are on-demand (never committed):
- `organvm session transcript <id>` — conversation summary
- `organvm session transcript <id> --unabridged` — full audit trail
- `organvm session prompts <id>` — human prompts only
"""

# ── Plan context (injected into repo-level context) ───────────────

PLAN_CONTEXT_SECTION = """\

## Active Plans

{plan_list}

### Related Plans (other repos/agents)
{related_plans}
"""

# ── Atoms pipeline context (injected when pipeline-manifest.json exists) ──

ATOMS_PIPELINE_SECTION = """\

## Atomization Pipeline

Last run: {last_run}

| Metric | Count |
|--------|-------|
| Plans parsed | {plans_parsed} |
| Tasks atomized | {tasks} |
| Prompts narrated | {prompts} |
| Threads | {threads} |
| Cross-system links | {links} |

Top domains: {top_domains}

Run: `organvm atoms pipeline --write`
"""

# ── Per-repo task queue (from fanout rollup) ─────────────────────

ATOMS_REPO_QUEUE_SECTION = """\

## Task Queue (from pipeline)

**{pending_count}** pending tasks | Last pipeline: {last_run}

{task_list}

Cross-organ links: {cross_link_count} | Top tags: {top_tags}

Run: `organvm atoms pipeline --write && organvm atoms fanout --write`
"""

SOP_DIRECTIVES_SECTION = """\

## Active Directives

{directives_table}

{linked_skills_line}
"""

ECOSYSTEM_STATUS_SECTION = """\

## Ecosystem Status

{pillar_summary}

Run: `organvm ecosystem show {repo_name}` | `organvm ecosystem validate --organ {organ_short}`
"""

ATOMS_NOT_RUN_HINT = """\

## Atomization Pipeline

Run `organvm atoms pipeline --write && organvm atoms fanout --write` to generate task queue.
"""

AMMOI_SECTION = """\

## System Density (auto-generated)

AMMOI: {density_pct} | Edges: {edges} | Tensions: {tensions} | Events(24h): {events_24h}
Organ density: {organ_density_line}
Last pulse: {last_pulse} | Δ24h: {delta_24h} | Δ7d: {delta_7d}
"""

ONTOLOGIA_STATUS_SECTION = """\

## Entity Identity (Ontologia)

**UID:** `{entity_uid}` | **Matched by:** {matched_by}

Resolve: `organvm ontologia resolve {repo_name}` | History: `organvm ontologia history {entity_uid}`
"""
