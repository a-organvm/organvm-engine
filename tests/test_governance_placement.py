"""Tests for governance placement scoring and audit."""

import json
from pathlib import Path

import pytest

from organvm_engine.governance.placement import (
    PlacementAudit,
    PlacementRecommendation,
    PlacementScore,
    audit_all_placements,
    compute_affinity,
    load_organ_definitions,
    recommend_placement,
)

FIXTURES = Path(__file__).parent / "fixtures"

# Minimal organ definitions for testing
MINIMAL_DEFS = {
    "schema_version": "1.0",
    "organs": {
        "ORGAN-I": {
            "name": "Theoria",
            "domain_boundary": "Foundational theory",
            "inclusion_criteria": ["Produces frameworks consumed by others"],
            "exclusion_criteria": [
                {"condition": "Has revenue", "redirect": "ORGAN-III"},
            ],
            "canonical_repo_types": ["engine", "framework", "theory"],
            "boundary_tests": [
                {"question": "Pure theory?", "expected": True},
            ],
        },
        "ORGAN-III": {
            "name": "Ergon",
            "domain_boundary": "Commercial products",
            "inclusion_criteria": ["Has revenue model"],
            "exclusion_criteria": [
                {"condition": "Pure theory", "redirect": "ORGAN-I"},
            ],
            "canonical_repo_types": ["saas", "tool", "product"],
            "boundary_tests": [
                {"question": "Has revenue?", "expected": True},
            ],
        },
        "META-ORGANVM": {
            "name": "Meta",
            "domain_boundary": "System infrastructure",
            "inclusion_criteria": ["System-wide tooling"],
            "exclusion_criteria": [
                {"condition": "Serves customers", "redirect": "ORGAN-III"},
            ],
            "canonical_repo_types": ["engine", "schema", "dashboard"],
            "boundary_tests": [
                {"question": "System infrastructure?", "expected": True},
            ],
        },
    },
}


def _make_repo(
    name: str,
    org: str = "organvm-i-theoria",
    revenue_model: str | None = None,
    impl_status: str = "ACTIVE",
    tier: str = "standard",
    **extra,
) -> dict:
    repo = {
        "name": name,
        "org": org,
        "implementation_status": impl_status,
        "public": True,
        "description": f"Test repo {name}",
        "promotion_status": "CANDIDATE",
        "tier": tier,
    }
    if revenue_model:
        repo["revenue_model"] = revenue_model
    repo.update(extra)
    return repo


class TestComputeAffinity:
    def test_theory_repo_in_organ_i(self):
        repo = _make_repo("recursive-engine", description="A recursive engine for theory")
        score = compute_affinity(repo, "ORGAN-I", MINIMAL_DEFS)
        assert score.organ == "ORGAN-I"
        assert score.score >= 50

    def test_revenue_repo_in_organ_iii(self):
        repo = _make_repo(
            "product-app",
            org="organvm-iii-ergon",
            revenue_model="subscription",
        )
        score = compute_affinity(repo, "ORGAN-III", MINIMAL_DEFS)
        assert score.score >= 60
        assert any("revenue" in inc.lower() for inc in score.matched_inclusion)

    def test_revenue_repo_penalized_in_organ_i(self):
        repo = _make_repo("my-product", revenue_model="subscription")
        score = compute_affinity(repo, "ORGAN-I", MINIMAL_DEFS)
        assert score.score < 50
        assert len(score.triggered_exclusion) > 0

    def test_no_definition_returns_neutral(self):
        repo = _make_repo("anything")
        defs = {"organs": {}}
        score = compute_affinity(repo, "ORGAN-I", defs)
        assert score.score == 50
        assert "No definition found" in score.notes

    def test_matching_type_boosts_score(self):
        repo = _make_repo("my-engine", type="engine")
        score = compute_affinity(repo, "ORGAN-I", MINIMAL_DEFS)
        assert any("type" in inc.lower() for inc in score.matched_inclusion)

    def test_score_clamped_to_0_100(self):
        repo = _make_repo("mega-product", revenue_model="subscription")
        score = compute_affinity(repo, "ORGAN-I", MINIMAL_DEFS)
        assert 0 <= score.score <= 100


class TestRecommendPlacement:
    def test_returns_ranked_scores(self):
        repo = _make_repo("my-engine")
        rec = recommend_placement(repo, MINIMAL_DEFS)
        assert len(rec.scores) > 0
        # Scores should be descending
        for i in range(len(rec.scores) - 1):
            assert rec.scores[i].score >= rec.scores[i + 1].score

    def test_revenue_repo_flagged_in_organ_i(self):
        repo = _make_repo("money-maker", revenue_model="subscription")
        rec = recommend_placement(repo, MINIMAL_DEFS)
        assert rec.flagged

    def test_well_placed_not_flagged(self):
        repo = _make_repo(
            "product-app",
            org="organvm-iii-ergon",
            revenue_model="subscription",
        )
        rec = recommend_placement(repo, MINIMAL_DEFS)
        # Should not be flagged — ORGAN-III is natural for revenue repos
        assert not rec.flagged or rec.current_organ == "ORGAN-III"

    def test_to_dict(self):
        repo = _make_repo("test-repo")
        rec = recommend_placement(repo, MINIMAL_DEFS)
        d = rec.to_dict()
        assert "repo_name" in d
        assert "scores" in d
        assert isinstance(d["scores"], list)


class TestAuditAllPlacements:
    def test_audit_with_minimal_registry(self, registry):
        audit = audit_all_placements(registry, MINIMAL_DEFS)
        assert audit.total_repos > 0
        assert audit.well_placed + len(audit.questionable) + len(audit.misplaced) == audit.total_repos

    def test_audit_to_dict(self, registry):
        audit = audit_all_placements(registry, MINIMAL_DEFS)
        d = audit.to_dict()
        assert "total_repos" in d
        assert "well_placed" in d
        assert "questionable" in d
        assert "misplaced" in d

    def test_archived_repos_skipped(self):
        reg = {
            "organs": {
                "ORGAN-I": {
                    "name": "Theory",
                    "repositories": [
                        _make_repo("archived-repo", impl_status="ARCHIVED"),
                    ],
                },
            },
        }
        audit = audit_all_placements(reg, MINIMAL_DEFS)
        assert audit.total_repos == 0

    def test_empty_registry(self):
        reg = {"organs": {}}
        audit = audit_all_placements(reg, MINIMAL_DEFS)
        assert audit.total_repos == 0
        assert audit.well_placed == 0


class TestLoadOrganDefinitions:
    def test_loads_from_path(self, tmp_path):
        defs_path = tmp_path / "organ-definitions.json"
        defs_path.write_text(json.dumps(MINIMAL_DEFS))
        result = load_organ_definitions(defs_path)
        assert result["schema_version"] == "1.0"
        assert "ORGAN-I" in result["organs"]

    def test_missing_file_returns_empty(self, tmp_path):
        result = load_organ_definitions(tmp_path / "nonexistent.json")
        assert result == {}


class TestDataclasses:
    def test_placement_score_to_dict(self):
        ps = PlacementScore(organ="ORGAN-I", score=75, matched_inclusion=["test"])
        d = ps.to_dict()
        assert d["organ"] == "ORGAN-I"
        assert d["score"] == 75

    def test_placement_recommendation_to_dict(self):
        pr = PlacementRecommendation(
            repo_name="test", current_organ="ORGAN-I", flagged=True,
        )
        d = pr.to_dict()
        assert d["flagged"] is True

    def test_placement_audit_to_dict(self):
        pa = PlacementAudit(total_repos=10, well_placed=8)
        d = pa.to_dict()
        assert d["total_repos"] == 10
