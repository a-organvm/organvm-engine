"""Density layer — measure how well the system describes itself.

Interconnectedness is a first-class health signal.  This module counts
declared edges, cross-organ wiring, and coverage of infrastructure
concerns (seeds, CI, tests, docs, ecosystem) to produce a composite
density score.  Low density = the system is under-wired and fragile.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from organvm_engine.metrics.organism import SystemOrganism
from organvm_engine.seed.graph import SeedGraph

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class DensityProfile:
    """Quantitative interconnection profile of the system."""

    # Edge metrics
    declared_edges: int = 0
    possible_edges: int = 0
    edge_saturation: float = 0.0
    unresolved_edges: int = 0

    # Coverage metrics
    total_repos: int = 0
    repos_with_seeds: int = 0
    repos_with_ci: int = 0
    repos_with_tests: int = 0
    repos_with_docs: int = 0
    repos_with_ecosystem: int = 0

    # Cross-organ wiring
    cross_organ_edges: int = 0
    organs_with_outbound: int = 0
    organs_with_inbound: int = 0

    # Composite
    interconnection_score: float = 0.0
    organ_density: dict[str, float] = field(default_factory=dict)

    @property
    def seed_coverage(self) -> float:
        if self.total_repos == 0:
            return 0.0
        return self.repos_with_seeds / self.total_repos

    @property
    def ci_coverage(self) -> float:
        if self.total_repos == 0:
            return 0.0
        return self.repos_with_ci / self.total_repos

    @property
    def coverage_completeness(self) -> float:
        """Average coverage across all tracked dimensions."""
        if self.total_repos == 0:
            return 0.0
        dimensions = [
            self.repos_with_seeds,
            self.repos_with_ci,
            self.repos_with_tests,
            self.repos_with_docs,
        ]
        return sum(d / self.total_repos for d in dimensions) / len(dimensions)

    def to_dict(self) -> dict:
        return {
            "declared_edges": self.declared_edges,
            "possible_edges": self.possible_edges,
            "edge_saturation": self.edge_saturation,
            "unresolved_edges": self.unresolved_edges,
            "total_repos": self.total_repos,
            "repos_with_seeds": self.repos_with_seeds,
            "repos_with_ci": self.repos_with_ci,
            "repos_with_tests": self.repos_with_tests,
            "repos_with_docs": self.repos_with_docs,
            "repos_with_ecosystem": self.repos_with_ecosystem,
            "cross_organ_edges": self.cross_organ_edges,
            "organs_with_outbound": self.organs_with_outbound,
            "organs_with_inbound": self.organs_with_inbound,
            "interconnection_score": self.interconnection_score,
            "seed_coverage": self.seed_coverage,
            "ci_coverage": self.ci_coverage,
            "coverage_completeness": self.coverage_completeness,
            "organ_density": self.organ_density,
        }


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def _organ_from_identity(identity: str) -> str:
    """Extract the org prefix from a 'org/repo' identity string."""
    return identity.split("/", maxsplit=1)[0] if "/" in identity else identity


def compute_density(
    graph: SeedGraph,
    organism: SystemOrganism,
    unresolved_count: int = 0,
) -> DensityProfile:
    """Compute the density profile from the seed graph and organism.

    Args:
        graph: Pre-built SeedGraph with nodes and edges.
        organism: Current SystemOrganism for gate/coverage data.
        unresolved_count: Number of unresolved consumes edges (from validate_edge_resolution).

    Returns:
        DensityProfile with edge, coverage, cross-organ, and composite metrics.
    """
    n = len(graph.nodes)
    possible = n * (n - 1) if n > 1 else 0
    declared = len(graph.edges)
    saturation = declared / possible if possible > 0 else 0.0

    # Cross-organ edges: source and target belong to different orgs
    outbound_orgs: set[str] = set()
    inbound_orgs: set[str] = set()
    cross_count = 0
    for src, tgt, _ in graph.edges:
        src_org = _organ_from_identity(src)
        tgt_org = _organ_from_identity(tgt)
        if src_org != tgt_org:
            cross_count += 1
            outbound_orgs.add(src_org)
            inbound_orgs.add(tgt_org)

    # Coverage from organism gate stats
    repos = organism.all_repos
    total = len(repos)
    seeds = sum(
        1 for r in repos
        if any(g.name == "SEED" and g.passed for g in r.gates)
    )
    ci = sum(
        1 for r in repos
        if any(g.name == "CI" and g.passed for g in r.gates)
    )
    tests = sum(
        1 for r in repos
        if any(g.name == "TESTS" and g.passed for g in r.gates)
    )
    docs = sum(
        1 for r in repos
        if any(g.name == "DOCS" and g.passed for g in r.gates)
    )
    # Ecosystem coverage: repos that have ecosystem profiles are tracked by
    # the ecosystem module, but we approximate via non-archived status here
    eco = sum(
        1 for r in repos if r.promo not in ("ARCHIVED",)
        and any(g.name == "PROTO" and g.passed for g in r.gates)
    )

    # Per-organ density: count edges involving each organ's repos
    organ_edge_counts: dict[str, int] = {}
    for src, tgt, _ in graph.edges:
        src_org = _organ_from_identity(src)
        tgt_org = _organ_from_identity(tgt)
        organ_edge_counts[src_org] = organ_edge_counts.get(src_org, 0) + 1
        if tgt_org != src_org:
            organ_edge_counts[tgt_org] = organ_edge_counts.get(tgt_org, 0) + 1

    # Normalize per-organ density to 0-100 scale (max = total edges)
    max_edges = max(organ_edge_counts.values()) if organ_edge_counts else 1
    organ_density = {
        org: round(count / max_edges * 100, 1)
        for org, count in sorted(organ_edge_counts.items())
    }

    # Composite score: 30% edge + 40% coverage + 30% cross-organ
    # Edge component: normalize saturation against a 5% target (realistic for 100+ repos)
    edge_component = min(saturation / 0.05, 1.0) * 100
    coverage_component = (
        (seeds + ci + tests + docs) / (total * 4) * 100 if total > 0 else 0.0
    )
    # Cross-organ: fraction of organs participating in cross-wiring
    all_orgs = set(_organ_from_identity(node) for node in graph.nodes)
    participating = outbound_orgs | inbound_orgs
    cross_component = (
        len(participating) / len(all_orgs) * 100 if all_orgs else 0.0
    )
    composite = 0.3 * edge_component + 0.4 * coverage_component + 0.3 * cross_component

    return DensityProfile(
        declared_edges=declared,
        possible_edges=possible,
        edge_saturation=round(saturation, 4),
        unresolved_edges=unresolved_count,
        total_repos=total,
        repos_with_seeds=seeds,
        repos_with_ci=ci,
        repos_with_tests=tests,
        repos_with_docs=docs,
        repos_with_ecosystem=eco,
        cross_organ_edges=cross_count,
        organs_with_outbound=len(outbound_orgs),
        organs_with_inbound=len(inbound_orgs),
        interconnection_score=round(composite, 1),
        organ_density=organ_density,
    )
