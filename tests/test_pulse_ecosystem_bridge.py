"""Tests for organvm_engine.pulse.ecosystem_bridge — ecosystem universality."""

from __future__ import annotations

from organvm_engine.pulse.ecosystem_bridge import (
    EcosystemCoverage,
    ORGAN_ARCHETYPES,
    RepoEcosystemContext,
    infer_repo_context,
)


# ---------------------------------------------------------------------------
# Organ archetypes
# ---------------------------------------------------------------------------

class TestOrganArchetypes:
    def test_all_organs_have_archetypes(self):
        """Every organ key has an archetype entry."""
        expected = {
            "ORGAN-I", "ORGAN-II", "ORGAN-III", "ORGAN-IV",
            "ORGAN-V", "ORGAN-VI", "ORGAN-VII", "META-ORGANVM",
        }
        assert expected.issubset(set(ORGAN_ARCHETYPES.keys()))

    def test_archetype_fields(self):
        """Each archetype has archetype, pillars, and value_flow."""
        for organ, info in ORGAN_ARCHETYPES.items():
            assert "archetype" in info, f"{organ} missing archetype"
            assert "pillars" in info, f"{organ} missing pillars"
            assert "value_flow" in info, f"{organ} missing value_flow"
            assert len(info["archetype"]) > 0
            assert len(info["pillars"]) > 0

    def test_unique_archetypes(self):
        """Each organ has a distinct archetype name."""
        archetypes = [info["archetype"] for info in ORGAN_ARCHETYPES.values()]
        assert len(set(archetypes)) == len(archetypes)


# ---------------------------------------------------------------------------
# Repo context inference
# ---------------------------------------------------------------------------

class TestInferRepoContext:
    def test_organ_i_context(self):
        """ORGAN-I repo gets research archetype."""
        ctx = infer_repo_context("sema-metra", "ORGAN-I")
        assert ctx.archetype == "research"
        assert "theory" in ctx.pillars
        assert ctx.has_ecosystem_yaml is False

    def test_organ_iii_with_ecosystem(self):
        """ORGAN-III repo with ecosystem.yaml is flagged."""
        ctx = infer_repo_context("product-a", "ORGAN-III", has_ecosystem_yaml=True)
        assert ctx.archetype == "commercial"
        assert ctx.has_ecosystem_yaml is True

    def test_meta_context(self):
        """META-ORGANVM repos get meta archetype."""
        ctx = infer_repo_context("organvm-engine", "META-ORGANVM")
        assert ctx.archetype == "meta"
        assert "tooling" in ctx.pillars

    def test_unknown_organ(self):
        """Unknown organ key gets graceful fallback."""
        ctx = infer_repo_context("mystery", "ORGAN-IX")
        assert ctx.archetype == "unknown"

    def test_edge_counts_passed_through(self):
        """Edge and subscription counts are stored."""
        ctx = infer_repo_context(
            "repo", "ORGAN-IV",
            edge_count=5, subscription_count=3, cross_organ_edges=2,
        )
        assert ctx.edge_count == 5
        assert ctx.subscription_count == 3
        assert ctx.cross_organ_edges == 2

    def test_to_dict(self):
        """to_dict includes all expected keys."""
        ctx = infer_repo_context("r", "ORGAN-I")
        d = ctx.to_dict()
        expected = {
            "repo", "organ", "has_ecosystem_yaml", "archetype",
            "pillars", "value_flow", "edge_count",
            "subscription_count", "cross_organ_edges",
        }
        assert expected.issubset(set(d.keys()))


# ---------------------------------------------------------------------------
# Ecosystem coverage
# ---------------------------------------------------------------------------

class TestEcosystemCoverage:
    def test_coverage_to_dict(self):
        """EcosystemCoverage.to_dict includes expected keys."""
        cov = EcosystemCoverage(
            total_repos=10,
            repos_with_ecosystem_yaml=3,
            repos_with_context=10,
            coverage_pct=30.0,
            universal_coverage_pct=100.0,
        )
        d = cov.to_dict()
        assert d["total_repos"] == 10
        assert d["repos_with_ecosystem_yaml"] == 3
        assert d["repos_with_context"] == 10
        assert d["coverage_pct"] == 30.0
        assert d["universal_coverage_pct"] == 100.0

    def test_empty_coverage(self):
        """Empty coverage has zero values."""
        cov = EcosystemCoverage()
        assert cov.total_repos == 0
        assert cov.coverage_pct == 0.0
        assert cov.universal_coverage_pct == 0.0

    def test_by_archetype_tracking(self):
        """by_archetype dict is populated correctly."""
        cov = EcosystemCoverage(
            total_repos=5,
            by_archetype={"research": 2, "commercial": 3},
        )
        d = cov.to_dict()
        assert d["by_archetype"]["research"] == 2
        assert d["by_archetype"]["commercial"] == 3
