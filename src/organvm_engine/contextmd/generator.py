"""CLAUDE.md section generator.

Takes registry data + seed data and produces the markdown content
for auto-generated sections at each level (repo, organ, workspace).
"""

from __future__ import annotations

from datetime import datetime, timezone

from organvm_engine.contextmd.templates import (
    AGENTS_SECTION,
    ORGAN_SECTION,
    REPO_SECTION,
    SESSION_REVIEW_SECTION,
    WORKSPACE_SECTION,
    format_consumes_edge,
    format_no_edges,
    format_produces_edge,
)
from organvm_engine.registry.query import find_repo


def generate_repo_section(
    repo_name: str,
    org: str,
    registry: dict,
    seed: dict | None = None,
) -> str:
    """Generate the auto-generated section for a repo-level CLAUDE.md / GEMINI.md."""

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
        section = section.replace(
            end_marker,
            SESSION_REVIEW_SECTION + "\n" + end_marker,
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
            subs.append(f"- Event: `{s.get('event')}` → Action: {s.get('action')}")
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
