"""CLAUDE.md section generator.

Takes registry data + seed data and produces the markdown content
for auto-generated sections at each level (repo, organ, workspace).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from organvm_engine.plans.index import PlanIndex

from organvm_engine.contextmd.templates import (
    AGENTS_SECTION,
    ATOMS_NOT_RUN_HINT,
    ATOMS_REPO_QUEUE_SECTION,
    ECOSYSTEM_STATUS_SECTION,
    ONTOLOGIA_STATUS_SECTION,
    ORGAN_SECTION,
    PLAN_CONTEXT_SECTION,
    REPO_SECTION,
    SESSION_REVIEW_SECTION,
    SOP_DIRECTIVES_SECTION,
    WORKSPACE_SECTION,
    format_consumes_edge,
    format_no_edges,
    format_produces_edge,
)
from organvm_engine.registry.query import find_repo, resolve_entity


def generate_repo_section(
    repo_name: str,
    org: str,
    registry: dict,
    seed: dict | None = None,
    plan_index: "PlanIndex | None" = None,
    sop_entries: list | None = None,
    agent: str | None = None,
) -> str:
    """Generate the auto-generated section for a repo-level CLAUDE.md / GEMINI.md."""

    resolved = resolve_entity(repo_name, registry=registry)
    if resolved and resolved.get("registry_entry"):
        organ_key, repo_data = resolved["organ_key"], resolved["registry_entry"]
    else:
        result = find_repo(registry, repo_name)
        if not result:
            return f"<!-- ERROR: Repo '{repo_name}' not found -->"
        organ_key, repo_data = result
    organ_data = registry.get("organs", {}).get(organ_key, {})

    # Format edges
    edges = []
    if seed:
        for p in seed.get("produces", []) or []:
            if isinstance(p, dict):
                target = p.get("target") or _format_consumers(p.get("consumers")) or "unspecified"
                artifact = p.get("artifact") or p.get("type") or "unspecified"
                edges.append(format_produces_edge(target, artifact, p.get("event", "")))
            else:
                edges.append(f"- **Produces** → `{p}`")
        for c in seed.get("consumes", []) or []:
            if isinstance(c, dict):
                source = c.get("source") or "unspecified"
                artifact = c.get("artifact") or c.get("type") or "unspecified"
                edges.append(format_consumes_edge(source, artifact, c.get("event", "")))
            else:
                edges.append(f"- **Consumes** ← `{c}`")

    edges_block = "\n".join(edges) if edges else format_no_edges()

    # Format siblings
    all_repos = organ_data.get("repositories", [])
    siblings = [r.get("name") for r in all_repos if r.get("name") != repo_name]
    siblings_block = ", ".join(f"`{s}`" for s in siblings[:15])
    if len(siblings) > 15:
        siblings_block += f" ... and {len(siblings) - 15} more"

    # Governance notes
    gov = []
    if organ_key == "ORGAN-III":
        gov.append("- Strictly unidirectional flow: I→II→III. No dependencies on Theory (I).")
    elif organ_key == "ORGAN-II":
        gov.append("- Consumes Theory (I) concepts, produces artifacts for Commerce (III).")
    elif organ_key == "ORGAN-I":
        gov.append("- Foundational theory layer. No upstream dependencies.")

    governance_block = "\n".join(gov) if gov else "- *Standard ORGANVM governance applies*"

    section = REPO_SECTION.format(
        organ_key=organ_key,
        organ_name=organ_data.get("name", organ_key),
        tier=repo_data.get("tier", "standard"),
        promotion_status=repo_data.get("promotion_status", "LOCAL"),
        org=org,
        repo_name=repo_name,
        edges_block=edges_block,
        siblings_block=siblings_block,
        governance_block=governance_block,
        timestamp=_timestamp(),
    )

    # Inject session review protocol before the AUTO:END marker
    end_marker = "<!-- ORGANVM:AUTO:END -->"
    if end_marker in section:
        # Build plan context if plan_index is provided
        plan_section = _build_plan_context(repo_name, organ_key, plan_index)
        atoms_section = _build_atoms_context(repo_name, organ_key)
        sop_section = _build_sop_directives(sop_entries)
        prompting_hint = _build_prompting_hint(agent)
        ecosystem_section = _build_ecosystem_context(repo_name, organ_key)
        ontologia_section = _build_ontologia_context(repo_name)
        injected = SESSION_REVIEW_SECTION
        if sop_section:
            injected += "\n" + sop_section
        if prompting_hint:
            injected += "\n" + prompting_hint
        if ecosystem_section:
            injected += "\n" + ecosystem_section
        if plan_section:
            injected += "\n" + plan_section
        if atoms_section:
            injected += "\n" + atoms_section
        if ontologia_section:
            injected += "\n" + ontologia_section
        section = section.replace(
            end_marker,
            injected + "\n" + end_marker,
        )

    return section


def generate_agents_section(
    repo_name: str,
    org: str,
    registry: dict,
    seed: dict | None = None,
) -> str:
    """Generate the auto-generated section for AGENTS.md."""

    result = find_repo(registry, repo_name)
    if not result:
        return f"<!-- ERROR: Repo '{repo_name}' not found -->"

    organ_key, _ = result
    organ_data = registry.get("organs", {}).get(organ_key, {})

    # Format subscriptions
    subs = []
    if seed:
        for s in seed.get("subscriptions", []) or []:
            if isinstance(s, dict):
                subs.append(f"- Event: `{s.get('event')}` → Action: {s.get('action')}")
            else:
                subs.append(f"- Event: `{s}`")
    subs_block = "\n".join(subs) if subs else "- *No active event subscriptions*"

    # Format produces/consumes for agents
    prod = []
    cons = []
    if seed:
        for p in seed.get("produces", []) or []:
            if isinstance(p, dict):
                art = p.get("artifact") or p.get("type") or "unknown"
                target = p.get("target")
                if not target and p.get("consumers"):
                    targets = []
                    for consumer in p.get("consumers") or []:
                        if isinstance(consumer, dict):
                            # Link to the consumer repo context if possible
                            repo_n = consumer.get("repo")
                            if repo_n:
                                targets.append(f"[`{repo_n}`](../{repo_n}/CLAUDE.md)")
                            else:
                                targets.append(consumer.get("organ") or "unknown")
                        else:
                            targets.append(str(consumer))
                    target = ", ".join(targets)
                target = target or "unspecified"
                prod.append(f"- **Produce** `{art}` for {target}")
            else:
                prod.append(f"- **Produce** `{p}`")
        for c in seed.get("consumes", []) or []:
            if isinstance(c, dict):
                art = c.get("artifact") or c.get("type") or "unknown"
                source = c.get("source") or "unspecified"
                # If source is org/repo, try to link it
                if "/" in source:
                    org_n, repo_n = source.split("/", 1)
                    source_link = f"[`{source}`](../../{org_n}/{repo_n}/CLAUDE.md)"
                else:
                    source_link = f"`{source}`"
                cons.append(f"- **Consume** `{art}` from {source_link}")
            else:
                cons.append(f"- **Consume** `{c}`")

    produces_block = "\n".join(prod) if prod else "- *No production responsibilities*"
    consumes_block = "\n".join(cons) if cons else "- *No external dependencies*"

    # Simple governance for agents
    gov = ["- Adhere to unidirectional flow: I→II→III", "- Never commit secrets or credentials"]

    return AGENTS_SECTION.format(
        organ_key=organ_key,
        organ_name=organ_data.get("name", organ_key),
        subscriptions_block=subs_block,
        produces_block=produces_block,
        consumes_block=consumes_block,
        governance_block="\n".join(gov),
        timestamp=_timestamp(),
    )


def generate_organ_section(
    organ_key: str,
    registry: dict,
    seeds: list[dict] | None = None,
) -> str:
    """Generate the auto-generated section for an organ-level CLAUDE.md."""

    organ_data = registry.get("organs", {}).get(organ_key, {})
    if not organ_data:
        return f"<!-- ERROR: Organ '{organ_key}' not found -->"

    repos = organ_data.get("repositories", [])

    # Format repo list
    repo_lines = []
    for r in repos[:20]:
        repo_lines.append(f"- `{r.get('name')}` ({r.get('tier')}, {r.get('promotion_status')})")
    repo_list_block = "\n".join(repo_lines)
    if len(repos) > 20:
        repo_list_block += f"\n- ... and {len(repos) - 20} more"

    # Aggregate promotion distribution
    dist = {}
    for r in repos:
        s = r.get("promotion_status", "LOCAL")
        dist[s] = dist.get(s, 0) + 1
    promotion_block = ", ".join(f"{k}: {v}" for k, v in sorted(dist.items()))

    return ORGAN_SECTION.format(
        organ_key=organ_key,
        organ_name=organ_data.get("name", organ_key),
        repo_count=len(repos),
        flagship_count=len([r for r in repos if r.get("tier") == "flagship"]),
        standard_count=len([r for r in repos if r.get("tier") == "standard"]),
        infra_count=len([r for r in repos if r.get("tier") == "infrastructure"]),
        organ_edges_block="- *Edges computed from system-wide seed graph*",
        repo_list_block=repo_list_block,
        promotion_block=promotion_block,
        timestamp=_timestamp(),
    )


def generate_workspace_section(
    registry: dict,
    seeds: list[dict] | None = None,
) -> str:
    """Generate the auto-generated section for the workspace-level CLAUDE.md."""

    organs = registry.get("organs", {})
    total_repos = 0
    rows = []

    for key, data in organs.items():
        repos = data.get("repositories", [])
        total_repos += len(repos)
        flagship = len([r for r in repos if r.get("tier") == "flagship"])
        # Status distribution
        s_dist = {}
        for r in repos:
            s = r.get("promotion_status", "LOCAL")
            s_dist[s] = s_dist.get(s, 0) + 1
        status_str = f"{s_dist.get('GRADUATED', 0)}G, {s_dist.get('PUBLIC_PROCESS', 0)}P"

        rows.append(f"| {key} | {len(repos)} | {flagship} | {status_str} |")

    omega_met, omega_total = _read_omega_counts()

    return WORKSPACE_SECTION.format(
        total_repos=total_repos,
        organ_count=len(organs),
        organ_table_rows="\n".join(rows),
        seed_coverage=f"{len(seeds) if seeds else 0}/{total_repos}",
        ci_count="TBD",
        omega_met=omega_met,
        omega_total=omega_total,
        timestamp=_timestamp(),
    )


def _build_sop_directives(sop_entries: list | None) -> str:
    """Build the Active Directives section from resolved SOP entries."""
    if not sop_entries:
        return ""

    rows = []
    all_complements: list[str] = []
    for e in sop_entries:
        desc = e.title or e.sop_name or e.filename
        rows.append(f"| {e.scope} | {e.phase} | {e.sop_name or e.filename} | {desc} |")
        all_complements.extend(e.complements or [])

    if not rows:
        return ""

    table = (
        "| Scope | Phase | Name | Description |\n"
        "|-------|-------|------|-------------|\n" + "\n".join(rows)
    )

    skills_line = ""
    if all_complements:
        unique = sorted(set(all_complements))
        skills_line = f"Linked skills: {', '.join(unique)}"

    return SOP_DIRECTIVES_SECTION.format(
        directives_table=table,
        linked_skills_line=skills_line,
    )


def _build_plan_context(
    repo_name: str,
    organ_key: str,
    plan_index: "PlanIndex | None",
) -> str:
    """Build the plan context section for a repo's CLAUDE.md.

    Shows up to 5 active plans in this repo + up to 5 related plans from
    other repos/agents that share the same organ.
    """
    if plan_index is None:
        return ""

    entries = plan_index.entries if hasattr(plan_index, "entries") else []
    if not entries:
        return ""

    # Plans in this repo
    repo_plans = [
        e for e in entries
        if e.repo == repo_name and e.status == "active"
    ]
    # Related plans: same organ, different repo or different agent
    related = [
        e for e in entries
        if e.organ == organ_key
        and e.repo != repo_name
        and e.status == "active"
    ]

    if not repo_plans and not related:
        return ""

    # Format repo plans (max 5)
    plan_lines = []
    for e in repo_plans[:5]:
        pct = f"{e.completed_count}/{e.task_count}" if e.task_count else "0/0"
        plan_lines.append(f"- `{e.slug}` ({e.agent}, {e.date}) — {pct} tasks complete")
    if len(repo_plans) > 5:
        plan_lines.append(f"- ... and {len(repo_plans) - 5} more")
    plan_list = "\n".join(plan_lines) if plan_lines else "- *No active plans in this repo*"

    # Format related plans (max 5)
    related_lines = []
    for e in related[:5]:
        related_lines.append(
            f"- `{e.repo}/{e.slug}` ({e.agent}) — {e.title[:50]}",
        )
    if len(related) > 5:
        related_lines.append(f"- ... and {len(related) - 5} more")
    no_related = "- *No related plans in this organ*"
    related_plans = "\n".join(related_lines) if related_lines else no_related

    return PLAN_CONTEXT_SECTION.format(
        plan_list=plan_list,
        related_plans=related_plans,
    )


def _build_atoms_context(repo_name: str, organ_key: str) -> str:
    """Build the atoms task queue section for a repo's CLAUDE.md.

    Reads pre-computed rollup JSON (not raw JSONL) so context sync stays fast.
    """
    from organvm_engine.atoms.rollup import load_repo_task_queue, load_rollup
    from organvm_engine.organ_config import registry_key_to_dir
    from organvm_engine.paths import workspace_root

    rk_to_dir = registry_key_to_dir()
    organ_dir_name = rk_to_dir.get(organ_key)
    if not organ_dir_name:
        return ""

    organ_dir = workspace_root() / organ_dir_name
    rollup = load_rollup(organ_dir)
    if rollup is None:
        return ATOMS_NOT_RUN_HINT

    queue = load_repo_task_queue(rollup, repo_name)
    if queue is None or queue["pending_count"] == 0:
        return ""

    # Format task list (max 8)
    task_lines = []
    for t in queue["tasks"][:8]:
        tags = ", ".join(t.get("tags", [])[:3])
        tag_str = f" [{tags}]" if tags else ""
        task_lines.append(f"- `{t.get('id', '?')}` {t.get('title', 'untitled')}{tag_str}")
    if queue["pending_count"] > 8:
        task_lines.append(f"- ... and {queue['pending_count'] - 8} more")
    task_list = "\n".join(task_lines)

    # Cross-organ link count
    cross_links = rollup.get("cross_organ_links", [])

    # Top tags from all pending tasks across all repos
    from collections import Counter
    tag_counter: Counter[str] = Counter()
    for repo_tasks in rollup.get("pending_by_repo", {}).values():
        for t in repo_tasks:
            tag_counter.update(t.get("tags", []))
    top_tags = ", ".join(f"`{t}`" for t, _ in tag_counter.most_common(5)) or "none"

    # Last run timestamp from manifest (if available)
    import json
    manifest_path = organ_dir / ".atoms" / "pipeline-manifest.json"
    last_run = "unknown"
    if manifest_path.exists():
        try:
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            last_run = m.get("generated", "unknown")[:19]
        except (json.JSONDecodeError, OSError):
            pass

    return ATOMS_REPO_QUEUE_SECTION.format(
        pending_count=queue["pending_count"],
        last_run=last_run,
        task_list=task_list,
        cross_link_count=len(cross_links),
        top_tags=top_tags,
    )


def _build_ecosystem_context(repo_name: str, organ_key: str) -> str:
    """Build ecosystem status snippet for a repo if ecosystem.yaml exists."""
    from organvm_engine.organ_config import registry_key_to_dir
    from organvm_engine.paths import workspace_root

    rk_to_dir = registry_key_to_dir()
    organ_dir_name = rk_to_dir.get(organ_key)
    if not organ_dir_name:
        return ""

    eco_path = workspace_root() / organ_dir_name / repo_name / "ecosystem.yaml"
    if not eco_path.is_file():
        return ""

    try:
        from organvm_engine.ecosystem.reader import get_pillars, read_ecosystem

        data = read_ecosystem(eco_path)
        pillars = get_pillars(data)
    except Exception:
        return ""

    if not pillars:
        return ""

    lines = []
    for pillar_name, arms in pillars.items():
        total = len(arms)
        live = sum(1 for a in arms if a.get("status") in ("live", "active"))
        planned = sum(1 for a in arms if a.get("status") == "planned")
        lines.append(f"- **{pillar_name}**: {live}/{total} live, {planned} planned")

    if not lines:
        return ""

    # Derive organ short key for CLI hint
    organ_short = organ_key.replace("ORGAN-", "").replace("META-ORGANVM", "META")

    return ECOSYSTEM_STATUS_SECTION.format(
        pillar_summary="\n".join(lines),
        repo_name=repo_name,
        organ_short=organ_short,
    )


def _build_ontologia_context(repo_name: str) -> str:
    """Resolve repo's ontologia UID and return a short status snippet."""
    try:
        from ontologia.registry.store import open_store
    except ImportError:
        return ""

    try:
        store = open_store()
        resolver = store.resolver()
        result = resolver.resolve(repo_name)
        if not result:
            return ""
        return ONTOLOGIA_STATUS_SECTION.format(
            entity_uid=result.identity.uid,
            matched_by=result.matched_by,
            repo_name=repo_name,
        )
    except Exception:
        return ""


def _build_prompting_hint(agent: str | None) -> str:
    """Build a one-line prompting standards hint for the given agent."""
    if not agent:
        return ""
    try:
        from organvm_engine.prompting.loader import format_guidelines_hint, load_guidelines
        guidelines = load_guidelines(agent)
        if guidelines:
            return "\n" + format_guidelines_hint(guidelines) + "\n"
    except ImportError:
        pass
    return ""


def _format_consumers(consumers: list | None) -> str:
    """Format a list of consumer entries into a comma-separated string."""
    if not consumers:
        return ""
    parts = []
    for c in consumers:
        if isinstance(c, dict):
            parts.append(c.get("repo") or c.get("organ") or str(c))
        else:
            parts.append(str(c))
    return ", ".join(parts)


def _read_omega_counts() -> tuple[int, int]:
    """Read omega criteria met/total from the evidence map.

    Parses the summary table in omega-evidence-map.md looking for
    '| MET | N |', '| IN PROGRESS | N |', '| NOT STARTED | N |' rows.
    Falls back to (0, 17) if the file is unreadable.
    """
    import re

    from organvm_engine.paths import corpus_dir

    evidence_path = corpus_dir() / "docs" / "evaluation" / "omega-evidence-map.md"
    try:
        text = evidence_path.read_text()
    except (FileNotFoundError, OSError):
        return 0, 17

    counts = {}
    for line in text.splitlines():
        m = re.match(r"\|\s*(MET|IN PROGRESS|NOT STARTED)\s*\|\s*(\d+)\s*\|", line)
        if m:
            counts[m.group(1)] = int(m.group(2))

    met = counts.get("MET", 0)
    total = met + counts.get("IN PROGRESS", 0) + counts.get("NOT STARTED", 0)
    return met, total if total > 0 else 17


def _timestamp() -> str:
    """Return ISO 8601 timestamp for sync tracking."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
