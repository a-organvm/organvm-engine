"""Tests for AX-5 Organ Placement dictum validator."""

import json
from pathlib import Path

import pytest

from organvm_engine.governance.dictums import validate_organ_placement

FIXTURES = Path(__file__).parent / "fixtures"


# Minimal organ definitions for the validator
MINIMAL_DEFS = {
    "schema_version": "1.0",
    "organs": {
        "ORGAN-I": {
            "name": "Theoria",
            "domain_boundary": "Foundational theory",
            "inclusion_criteria": ["Produces frameworks"],
            "exclusion_criteria": [{"condition": "Revenue", "redirect": "III"}],
            "canonical_repo_types": ["engine"],
            "boundary_tests": [],
        },
        "ORGAN-III": {
            "name": "Ergon",
            "domain_boundary": "Commercial products",
            "inclusion_criteria": ["Has revenue"],
            "exclusion_criteria": [],
            "canonical_repo_types": ["saas"],
            "boundary_tests": [],
        },
    },
}


def _make_registry(*organ_repos):
    """Build a minimal registry from (organ_key, repo_dict) pairs."""
    organs = {}
    for organ_key, repo in organ_repos:
        organs.setdefault(organ_key, {"name": organ_key, "repositories": []})
        organs[organ_key]["repositories"].append(repo)
    return {"organs": organs}


def _repo(
    name: str,
    org: str = "organvm-i-theoria",
    revenue_model: str | None = None,
    impl_status: str = "ACTIVE",
    promo_status: str = "CANDIDATE",
    **kw,
) -> dict:
    r = {
        "name": name,
        "org": org,
        "implementation_status": impl_status,
        "public": True,
        "description": f"Test {name}",
        "promotion_status": promo_status,
        "dependencies": [],
    }
    if revenue_model:
        r["revenue_model"] = revenue_model
    r.update(kw)
    return r


class TestValidateOrganPlacement:
    def test_revenue_outside_organ_iii_flagged(self, monkeypatch, tmp_path):
        """Revenue repo in ORGAN-I should be flagged."""
        defs_path = tmp_path / "organ-definitions.json"
        defs_path.write_text(json.dumps(MINIMAL_DEFS))

        # Monkeypatch the loader to use our test definitions
        import organvm_engine.governance.placement as pm
        monkeypatch.setattr(pm, "load_organ_definitions", lambda path=None: MINIMAL_DEFS)

        reg = _make_registry(
            ("ORGAN-I", _repo("money-repo", revenue_model="subscription")),
        )
        violations = validate_organ_placement(reg)
        assert len(violations) >= 1
        assert any("revenue" in v.message.lower() for v in violations)
        assert all(v.dictum_id == "AX-5" for v in violations)
        assert all(v.severity == "warning" for v in violations)

    def test_revenue_in_organ_iii_ok(self, monkeypatch):
        """Revenue repo in ORGAN-III should NOT be flagged for revenue."""
        import organvm_engine.governance.placement as pm
        monkeypatch.setattr(pm, "load_organ_definitions", lambda path=None: MINIMAL_DEFS)

        reg = _make_registry(
            ("ORGAN-III", _repo("product", org="organvm-iii-ergon", revenue_model="subscription")),
        )
        violations = validate_organ_placement(reg)
        revenue_violations = [v for v in violations if "revenue" in v.message.lower()]
        assert len(revenue_violations) == 0

    def test_archived_repos_skipped(self, monkeypatch):
        """Archived repos should not be checked."""
        import organvm_engine.governance.placement as pm
        monkeypatch.setattr(pm, "load_organ_definitions", lambda path=None: MINIMAL_DEFS)

        reg = _make_registry(
            ("ORGAN-I", _repo("old-repo", impl_status="ARCHIVED", revenue_model="subscription")),
        )
        violations = validate_organ_placement(reg)
        assert len(violations) == 0

    def test_none_revenue_not_flagged(self, monkeypatch):
        """revenue_model='none' should not trigger the revenue check."""
        import organvm_engine.governance.placement as pm
        monkeypatch.setattr(pm, "load_organ_definitions", lambda path=None: MINIMAL_DEFS)

        reg = _make_registry(
            ("ORGAN-I", _repo("free-repo", revenue_model="none")),
        )
        violations = validate_organ_placement(reg)
        revenue_violations = [v for v in violations if "revenue" in v.message.lower()]
        assert len(revenue_violations) == 0

    def test_internal_revenue_not_flagged(self, monkeypatch):
        """revenue_model='internal' should not trigger the revenue check."""
        import organvm_engine.governance.placement as pm
        monkeypatch.setattr(pm, "load_organ_definitions", lambda path=None: MINIMAL_DEFS)

        reg = _make_registry(
            ("ORGAN-I", _repo("internal-tool", revenue_model="internal")),
        )
        violations = validate_organ_placement(reg)
        revenue_violations = [v for v in violations if "revenue" in v.message.lower()]
        assert len(revenue_violations) == 0

    def test_graceful_when_definitions_missing(self, monkeypatch):
        """Should return no violations when organ-definitions.json is missing."""
        import organvm_engine.governance.placement as pm
        monkeypatch.setattr(pm, "load_organ_definitions", lambda path=None: {})

        reg = _make_registry(
            ("ORGAN-I", _repo("any-repo", revenue_model="subscription")),
        )
        violations = validate_organ_placement(reg)
        assert len(violations) == 0

    def test_organ_i_no_consumers_flagged(self, monkeypatch):
        """ORGAN-I repo with no consumers beyond LOCAL should be flagged."""
        import organvm_engine.governance.placement as pm
        monkeypatch.setattr(pm, "load_organ_definitions", lambda path=None: MINIMAL_DEFS)

        reg = _make_registry(
            ("ORGAN-I", _repo("lonely-theory", promo_status="PUBLIC_PROCESS")),
        )
        violations = validate_organ_placement(reg)
        consumer_violations = [v for v in violations if "consumer" in v.message.lower()]
        assert len(consumer_violations) >= 1

    def test_organ_i_with_consumers_ok(self, monkeypatch):
        """ORGAN-I repo consumed by another organ should not be flagged."""
        import organvm_engine.governance.placement as pm
        monkeypatch.setattr(pm, "load_organ_definitions", lambda path=None: MINIMAL_DEFS)

        reg = _make_registry(
            ("ORGAN-I", _repo("used-theory")),
            ("ORGAN-III", _repo(
                "consumer", org="organvm-iii-ergon",
                dependencies=["organvm-i-theoria/used-theory"],
            )),
        )
        violations = validate_organ_placement(reg)
        consumer_violations = [v for v in violations if "consumer" in v.message.lower()]
        assert len(consumer_violations) == 0
