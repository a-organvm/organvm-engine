"""Ecosystem universality — extend ecosystem awareness beyond commercial repos.

ORGAN-III products have ecosystem.yaml files declaring business pillars.
Other organs lack this context, creating a blind spot in system self-awareness.
This bridge infers lightweight ecosystem contexts from seed.yaml metadata
so every repo has some level of ecosystem awareness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Organ ecosystem archetypes
# ---------------------------------------------------------------------------

# Each organ has different "pillars" that constitute its ecosystem.
# These are the dimensions of value each organ type can produce.
ORGAN_ARCHETYPES: dict[str, dict[str, str]] = {
    "ORGAN-I": {
        "archetype": "research",
        "pillars": "theory, frameworks, engines, proofs-of-concept",
        "value_flow": "downstream to ORGAN-II and ORGAN-III",
    },
    "ORGAN-II": {
        "archetype": "creative",
        "pillars": "artworks, performances, exhibitions, generative systems",
        "value_flow": "parallel to ORGAN-III, feeds ORGAN-V narratives",
    },
    "ORGAN-III": {
        "archetype": "commercial",
        "pillars": "products, customers, revenue, market share",
        "value_flow": "external market, feeds ORGAN-VII distribution",
    },
    "ORGAN-IV": {
        "archetype": "orchestration",
        "pillars": "governance, agents, skills, coordination",
        "value_flow": "system-wide, enables all other organs",
    },
    "ORGAN-V": {
        "archetype": "discourse",
        "pillars": "essays, publications, readership, analytics",
        "value_flow": "external audience, informs ORGAN-VI community",
    },
    "ORGAN-VI": {
        "archetype": "community",
        "pillars": "events, reading groups, engagement, learning",
        "value_flow": "inbound from audience, feeds ORGAN-V content",
    },
    "ORGAN-VII": {
        "archetype": "distribution",
        "pillars": "channels, announcements, reach, automation",
        "value_flow": "outbound to all audiences, consumes from all organs",
    },
    "META-ORGANVM": {
        "archetype": "meta",
        "pillars": "health, schemas, tooling, documentation, governance corpus",
        "value_flow": "system-wide infrastructure, consumed by all organs",
    },
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RepoEcosystemContext:
    """Ecosystem awareness for a single repo, regardless of organ."""

    repo: str
    organ: str
    has_ecosystem_yaml: bool
    archetype: str
    pillars: str
    value_flow: str
    edge_count: int = 0         # produces + consumes edges
    subscription_count: int = 0  # event subscriptions declared
    cross_organ_edges: int = 0   # edges to/from other organs

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "organ": self.organ,
            "has_ecosystem_yaml": self.has_ecosystem_yaml,
            "archetype": self.archetype,
            "pillars": self.pillars,
            "value_flow": self.value_flow,
            "edge_count": self.edge_count,
            "subscription_count": self.subscription_count,
            "cross_organ_edges": self.cross_organ_edges,
        }


@dataclass
class EcosystemCoverage:
    """System-wide ecosystem coverage profile."""

    total_repos: int = 0
    repos_with_ecosystem_yaml: int = 0
    repos_with_context: int = 0   # all repos get inferred context
    by_archetype: dict[str, int] = field(default_factory=dict)
    by_organ: dict[str, dict[str, int]] = field(default_factory=dict)
    coverage_pct: float = 0.0
    universal_coverage_pct: float = 0.0  # with inferred contexts = 100%

    def to_dict(self) -> dict:
        return {
            "total_repos": self.total_repos,
            "repos_with_ecosystem_yaml": self.repos_with_ecosystem_yaml,
            "repos_with_context": self.repos_with_context,
            "by_archetype": self.by_archetype,
            "by_organ": self.by_organ,
            "coverage_pct": round(self.coverage_pct, 2),
            "universal_coverage_pct": round(self.universal_coverage_pct, 2),
        }


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def _resolve_organ_key(organ_id: str) -> str:
    """Normalize organ identifiers to registry keys."""
    if organ_id.startswith("ORGAN-") or organ_id.startswith("META"):
        return organ_id
    from organvm_engine.organ_config import organ_aliases
    aliases = organ_aliases()
    return aliases.get(organ_id, organ_id)


def infer_repo_context(
    repo_name: str,
    organ_key: str,
    has_ecosystem_yaml: bool = False,
    edge_count: int = 0,
    subscription_count: int = 0,
    cross_organ_edges: int = 0,
) -> RepoEcosystemContext:
    """Build an ecosystem context for any repo, regardless of organ.

    Args:
        repo_name: Repository name.
        organ_key: Registry organ key (e.g. "ORGAN-I", "META-ORGANVM").
        has_ecosystem_yaml: Whether the repo has an ecosystem.yaml file.
        edge_count: Total produces + consumes edges.
        subscription_count: Event subscriptions declared in seed.yaml.
        cross_organ_edges: Edges to/from repos in other organs.

    Returns:
        RepoEcosystemContext with inferred or declared context.
    """
    archetype_info = ORGAN_ARCHETYPES.get(organ_key, {
        "archetype": "unknown",
        "pillars": "general",
        "value_flow": "unspecified",
    })

    return RepoEcosystemContext(
        repo=repo_name,
        organ=organ_key,
        has_ecosystem_yaml=has_ecosystem_yaml,
        archetype=archetype_info["archetype"],
        pillars=archetype_info["pillars"],
        value_flow=archetype_info["value_flow"],
        edge_count=edge_count,
        subscription_count=subscription_count,
        cross_organ_edges=cross_organ_edges,
    )


def compute_ecosystem_coverage(
    workspace: Path | str | None = None,
) -> EcosystemCoverage:
    """Compute ecosystem coverage across all organs.

    Combines discovered ecosystem.yaml files with inferred contexts
    from seed.yaml metadata to produce universal ecosystem awareness.

    Args:
        workspace: Workspace root. None = default.

    Returns:
        EcosystemCoverage with explicit + inferred coverage stats.
    """
    from organvm_engine.ecosystem.discover import discover_ecosystems
    from organvm_engine.registry.loader import load_registry
    from organvm_engine.registry.query import all_repos

    # Find repos with explicit ecosystem.yaml
    eco_paths = discover_ecosystems(workspace)
    eco_repos: set[str] = set()
    for p in eco_paths:
        # Path structure: workspace/org-dir/repo-name/ecosystem.yaml
        eco_repos.add(p.parent.name)

    # Load registry for total repo count and organ mapping
    registry = load_registry()
    total = 0
    by_organ: dict[str, dict[str, int]] = {}
    by_archetype: dict[str, int] = {}

    for organ_key, repo in all_repos(registry):
        repo_name = repo.get("name", "")
        if not repo_name:
            continue
        total += 1
        has_eco = repo_name in eco_repos
        ctx = infer_repo_context(repo_name, organ_key, has_ecosystem_yaml=has_eco)

        # Count by archetype
        by_archetype[ctx.archetype] = by_archetype.get(ctx.archetype, 0) + 1

        # Count by organ
        if organ_key not in by_organ:
            by_organ[organ_key] = {"total": 0, "with_ecosystem_yaml": 0}
        by_organ[organ_key]["total"] += 1
        if has_eco:
            by_organ[organ_key]["with_ecosystem_yaml"] += 1

    eco_count = len(eco_repos)

    return EcosystemCoverage(
        total_repos=total,
        repos_with_ecosystem_yaml=eco_count,
        repos_with_context=total,  # all repos get inferred context
        by_archetype=by_archetype,
        by_organ=by_organ,
        coverage_pct=(eco_count / total * 100) if total > 0 else 0.0,
        universal_coverage_pct=100.0 if total > 0 else 0.0,
    )
