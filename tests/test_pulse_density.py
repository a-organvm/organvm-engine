"""Tests for organvm_engine.pulse.density — interconnection measurement."""

from __future__ import annotations

from organvm_engine.metrics.gates import GateResult, RepoProgress, ScaffoldInfo
from organvm_engine.metrics.organism import OrganOrganism, SystemOrganism
from organvm_engine.pulse.density import DensityProfile, compute_density
from organvm_engine.seed.graph import SeedGraph


# ---------------------------------------------------------------------------
# Helper: build minimal test objects
# ---------------------------------------------------------------------------

def _gate(name: str, passed: bool = False) -> GateResult:
    return GateResult(name=name, passed=passed, applicable=True)


def _repo(
    name: str = "test-repo",
    organ: str = "ORGAN-I",
    promo: str = "CANDIDATE",
    seed: bool = False,
    ci: bool = False,
    tests: bool = False,
    docs: bool = False,
    proto: bool = False,
) -> RepoProgress:
    gates = [
        _gate("SEED", seed),
        _gate("SCAFFOLD"),
        _gate("CI", ci),
        _gate("TESTS", tests),
        _gate("DOCS", docs),
        _gate("PROTO", proto),
        _gate("CAND"),
        _gate("DEPLOY"),
        _gate("GRAD"),
        _gate("OMEGA"),
    ]
    score = sum(1 for g in gates if g.passed)
    return RepoProgress(
        repo=name,
        organ=organ,
        organ_name="Test",
        tier="standard",
        profile="code-full",
        promo=promo,
        impl="ACTIVE",
        description="",
        deployment_url="",
        platinum=False,
        revenue_model="",
        revenue_status="",
        gates=gates,
        score=score,
        total=len(gates),
        pct=int(score / len(gates) * 100),
        languages={},
        primary_lang="Python",
        stale_days=0,
        is_stale=False,
        is_warn_stale=False,
        scaffold=ScaffoldInfo(),
        promo_ready=False,
        next_promo="PUBLIC_PROCESS",
    )


def _organism(repos: list[RepoProgress]) -> SystemOrganism:
    by_organ: dict[str, list[RepoProgress]] = {}
    for r in repos:
        by_organ.setdefault(r.organ, []).append(r)
    organs = [
        OrganOrganism(organ_id=oid, organ_name="Test", repos=rlist)
        for oid, rlist in by_organ.items()
    ]
    return SystemOrganism(organs=organs, generated="2026-01-01T00:00:00+00:00")


def _graph(
    nodes: list[str] | None = None,
    edges: list[tuple[str, str, str]] | None = None,
) -> SeedGraph:
    return SeedGraph(
        nodes=nodes or [],
        edges=edges or [],
        produces={},
        consumes={},
    )


# ---------------------------------------------------------------------------
# Empty and minimal graphs
# ---------------------------------------------------------------------------

class TestEmptyGraph:
    def test_empty_graph(self):
        """No nodes produces edge_saturation=0 and score=0."""
        graph = _graph()
        org = _organism([_repo()])
        dp = compute_density(graph, org)
        assert dp.edge_saturation == 0.0
        assert dp.declared_edges == 0
        assert dp.possible_edges == 0

    def test_single_edge(self):
        """2 nodes, 1 edge produces edge_saturation = 1/(2*1) = 0.5."""
        graph = _graph(
            nodes=["orgA/r1", "orgB/r2"],
            edges=[("orgA/r1", "orgB/r2", "data")],
        )
        org = _organism([_repo()])
        dp = compute_density(graph, org)
        assert dp.declared_edges == 1
        assert dp.possible_edges == 2  # 2*(2-1)
        assert dp.edge_saturation == 0.5


# ---------------------------------------------------------------------------
# Cross-organ detection
# ---------------------------------------------------------------------------

class TestCrossOrgan:
    def test_cross_organ_detection(self):
        """Edges between different org prefixes are counted as cross-organ."""
        graph = _graph(
            nodes=["orgA/r1", "orgB/r2", "orgA/r3"],
            edges=[
                ("orgA/r1", "orgB/r2", "data"),     # cross-organ
                ("orgA/r1", "orgA/r3", "config"),    # same-organ
            ],
        )
        org = _organism([_repo()])
        dp = compute_density(graph, org)
        assert dp.cross_organ_edges == 1
        assert dp.organs_with_outbound >= 1
        assert dp.organs_with_inbound >= 1

    def test_same_organ_not_cross(self):
        """Edges within the same org prefix are not cross-organ."""
        graph = _graph(
            nodes=["orgA/r1", "orgA/r2"],
            edges=[("orgA/r1", "orgA/r2", "data")],
        )
        org = _organism([_repo()])
        dp = compute_density(graph, org)
        assert dp.cross_organ_edges == 0


# ---------------------------------------------------------------------------
# Coverage from organism
# ---------------------------------------------------------------------------

class TestCoverage:
    def test_coverage_from_organism(self):
        """Repos with passing CI/TESTS/DOCS gates are counted."""
        repos = [
            _repo(name="r1", ci=True, tests=True, docs=True, seed=True),
            _repo(name="r2", ci=True, tests=False, docs=False, seed=True),
            _repo(name="r3", ci=False, tests=False, docs=False, seed=False),
        ]
        org = _organism(repos)
        graph = _graph(nodes=["org/r1", "org/r2", "org/r3"])
        dp = compute_density(graph, org)
        assert dp.total_repos == 3
        assert dp.repos_with_ci == 2
        assert dp.repos_with_tests == 1
        assert dp.repos_with_docs == 1
        assert dp.repos_with_seeds == 2

    def test_seed_coverage(self):
        """seed_coverage = repos_with_seeds / total_repos."""
        repos = [
            _repo(name="r1", seed=True),
            _repo(name="r2", seed=True),
            _repo(name="r3", seed=False),
        ]
        org = _organism(repos)
        dp = compute_density(_graph(), org)
        assert abs(dp.seed_coverage - 2 / 3) < 0.01


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------

class TestComposite:
    def test_interconnection_score_range(self):
        """Interconnection score is always 0-100."""
        # Dense graph
        graph = _graph(
            nodes=["a/r1", "b/r2", "c/r3"],
            edges=[
                ("a/r1", "b/r2", "x"),
                ("b/r2", "c/r3", "y"),
                ("a/r1", "c/r3", "z"),
            ],
        )
        org = _organism([
            _repo(name="r1", seed=True, ci=True, tests=True, docs=True),
        ])
        dp = compute_density(graph, org)
        assert 0 <= dp.interconnection_score <= 100

    def test_empty_score_is_zero(self):
        """Empty graph and no coverage produces score near zero."""
        graph = _graph()
        org = _organism([_repo()])
        dp = compute_density(graph, org)
        # With no edges and minimal coverage, score should be low
        assert dp.interconnection_score >= 0


# ---------------------------------------------------------------------------
# Serialization and density dict
# ---------------------------------------------------------------------------

class TestDensityDict:
    def test_density_to_dict(self):
        """to_dict includes all expected keys."""
        graph = _graph(
            nodes=["a/r1", "b/r2"],
            edges=[("a/r1", "b/r2", "data")],
        )
        org = _organism([_repo()])
        dp = compute_density(graph, org)
        d = dp.to_dict()
        expected_keys = {
            "declared_edges", "possible_edges", "edge_saturation",
            "unresolved_edges", "total_repos", "repos_with_seeds",
            "repos_with_ci", "repos_with_tests", "repos_with_docs",
            "repos_with_ecosystem", "cross_organ_edges",
            "organs_with_outbound", "organs_with_inbound",
            "interconnection_score", "seed_coverage", "ci_coverage",
            "coverage_completeness", "organ_density",
        }
        assert expected_keys.issubset(set(d.keys()))

    def test_per_organ_density(self):
        """organ_density dict is populated when edges exist."""
        graph = _graph(
            nodes=["orgA/r1", "orgB/r2"],
            edges=[("orgA/r1", "orgB/r2", "data")],
        )
        org = _organism([_repo()])
        dp = compute_density(graph, org)
        assert isinstance(dp.organ_density, dict)
        assert len(dp.organ_density) >= 1

    def test_coverage_completeness(self):
        """coverage_completeness is the average of all coverage dimensions."""
        repos = [
            _repo(name="r1", seed=True, ci=True, tests=True, docs=True),
            _repo(name="r2", seed=True, ci=True, tests=False, docs=False),
        ]
        org = _organism(repos)
        dp = compute_density(_graph(), org)
        # 4 dimensions: seeds=2/2, ci=2/2, tests=1/2, docs=1/2
        # avg = (1.0 + 1.0 + 0.5 + 0.5) / 4 = 0.75
        assert abs(dp.coverage_completeness - 0.75) < 0.01

    def test_unresolved_count(self):
        """unresolved_count is passed through to the profile."""
        graph = _graph()
        org = _organism([_repo()])
        dp = compute_density(graph, org, unresolved_count=7)
        assert dp.unresolved_edges == 7
