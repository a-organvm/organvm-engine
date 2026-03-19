"""Tests for structural interrogation engine (SPEC-009)."""

import pytest

from organvm_engine.governance.interrogation import (
    InterrogationReport,
    check_existence,
    check_identity,
    check_law,
    check_process,
    check_relation,
    check_structure,
    check_teleology,
    fast_tension_scan,
    interrogate_repo,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def complete_repo():
    """A repo with all fields populated."""
    return {
        "name": "organvm-engine",
        "org": "meta-organvm",
        "implementation_status": "ACTIVE",
        "promotion_status": "PUBLIC_PROCESS",
        "description": "Core computational engine for the ORGANVM system",
        "code_files": 50,
        "test_files": 20,
        "tier": "flagship",
        "dependencies": ["meta-organvm/schema-definitions"],
        "ci_workflow": True,
        "platinum_status": True,
        "last_validated": "2026-03-15",
        "note": "Primary engine for registry and governance",
    }


@pytest.fixture
def empty_repo():
    """A repo with minimal/missing fields."""
    return {"name": "stub-repo"}


@pytest.fixture
def scan_registry():
    """Registry with two repos for tension scan testing."""
    return {
        "organs": {
            "ORGAN-I": {
                "repositories": [
                    {
                        "name": "theory-core",
                        "org": "organvm-i-theoria",
                        "implementation_status": "ACTIVE",
                        "promotion_status": "PUBLIC_PROCESS",
                        "description": "Foundational theory",
                        "code_files": 10,
                        "test_files": 5,
                        "tier": "flagship",
                        "dependencies": [],
                        "ci_workflow": True,
                        "platinum_status": True,
                        "last_validated": "2026-03-15",
                        "note": "Core theory repo",
                    },
                ],
            },
            "META-ORGANVM": {
                "repositories": [
                    {
                        "name": "organvm-engine",
                        "org": "meta-organvm",
                        "implementation_status": "ACTIVE",
                        "promotion_status": "PUBLIC_PROCESS",
                        "description": "Core engine",
                        "code_files": 50,
                        "test_files": 20,
                        "tier": "flagship",
                        "dependencies": ["organvm-i-theoria/theory-core"],
                        "ci_workflow": True,
                        "platinum_status": True,
                        "last_validated": "2026-03-15",
                        "note": "Engine repo",
                    },
                ],
            },
        },
    }


# ---------------------------------------------------------------------------
# DIAG-001: Existence
# ---------------------------------------------------------------------------


class TestCheckExistence:
    def test_complete_repo_scores_1(self, complete_repo):
        score, findings = check_existence(complete_repo)
        assert score == 1.0
        assert findings == []

    def test_empty_repo_partial(self, empty_repo):
        score, findings = check_existence(empty_repo)
        assert score < 1.0
        assert any("org" in f.lower() for f in findings)

    def test_no_name(self):
        score, findings = check_existence({"org": "test"})
        assert score < 1.0
        assert any("name" in f.lower() for f in findings)


# ---------------------------------------------------------------------------
# DIAG-002: Identity
# ---------------------------------------------------------------------------


class TestCheckIdentity:
    def test_complete_repo(self, complete_repo):
        score, findings = check_identity(complete_repo)
        assert score == 1.0

    def test_no_description(self):
        repo = {"name": "x", "promotion_status": "LOCAL"}
        score, findings = check_identity(repo)
        assert score == pytest.approx(2 / 3)
        assert any("description" in f.lower() for f in findings)

    def test_no_promotion(self):
        repo = {"name": "x", "description": "A test repo"}
        score, findings = check_identity(repo)
        assert score < 1.0


# ---------------------------------------------------------------------------
# DIAG-003: Structure
# ---------------------------------------------------------------------------


class TestCheckStructure:
    def test_complete(self, complete_repo):
        score, findings = check_structure(complete_repo)
        assert score == 1.0

    def test_no_code_files(self):
        repo = {"tier": "standard", "dependencies": []}
        score, findings = check_structure(repo)
        assert score == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# DIAG-004: Law
# ---------------------------------------------------------------------------


class TestCheckLaw:
    def test_fully_governed(self, complete_repo):
        score, findings = check_law(complete_repo)
        assert score == 1.0

    def test_no_ci(self):
        repo = {"promotion_status": "LOCAL", "platinum_status": False}
        score, findings = check_law(repo)
        assert score == pytest.approx(2 / 3)
        assert any("ci_workflow" in f for f in findings)


# ---------------------------------------------------------------------------
# DIAG-005: Process
# ---------------------------------------------------------------------------


class TestCheckProcess:
    def test_active_process(self, complete_repo):
        score, findings = check_process(complete_repo)
        assert score == 1.0

    def test_design_only(self):
        repo = {"implementation_status": "DESIGN_ONLY"}
        score, findings = check_process(repo)
        assert score < 1.0


# ---------------------------------------------------------------------------
# DIAG-006: Relation
# ---------------------------------------------------------------------------


class TestCheckRelation:
    def test_connected(self, complete_repo):
        score, findings = check_relation(complete_repo)
        assert score == 1.0

    def test_isolated_non_flagship(self):
        repo = {"org": "test", "dependencies": [], "tier": "standard"}
        score, findings = check_relation(repo)
        assert score < 1.0
        assert any("dependencies" in f.lower() for f in findings)

    def test_flagship_no_deps_ok(self):
        repo = {"org": "test", "dependencies": [], "tier": "flagship"}
        score, findings = check_relation(repo)
        assert score == 1.0


# ---------------------------------------------------------------------------
# DIAG-007: Teleology
# ---------------------------------------------------------------------------


class TestCheckTeleology:
    def test_purposeful(self, complete_repo):
        score, findings = check_teleology(complete_repo)
        assert score == 1.0

    def test_no_purpose(self):
        repo = {"description": "", "tier": "", "note": ""}
        score, findings = check_teleology(repo)
        assert score == 0.0
        assert len(findings) == 3


# ---------------------------------------------------------------------------
# Full interrogation
# ---------------------------------------------------------------------------


class TestInterrogateRepo:
    def test_complete_repo_high_score(self, complete_repo):
        report = interrogate_repo(complete_repo)
        assert isinstance(report, InterrogationReport)
        assert len(report.dimensions) == 7
        assert report.overall_score > 0.9

    def test_empty_repo_low_score(self, empty_repo):
        report = interrogate_repo(empty_repo)
        assert report.overall_score < 0.5

    def test_summary_output(self, complete_repo):
        report = interrogate_repo(complete_repo)
        summary = report.summary()
        assert "Structural Interrogation" in summary
        assert "Overall:" in summary


# ---------------------------------------------------------------------------
# Fast tension scan
# ---------------------------------------------------------------------------


class TestFastTensionScan:
    def test_healthy_registry(self, scan_registry):
        scores = fast_tension_scan(scan_registry)
        assert len(scores) == 7
        assert all(0.0 <= s <= 1.0 for s in scores.values())
        assert scores["existence"] == 1.0

    def test_empty_registry(self):
        scores = fast_tension_scan({"organs": {}})
        assert all(s == 1.0 for s in scores.values())

    def test_archived_repos_excluded(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "old",
                            "implementation_status": "ARCHIVED",
                        },
                    ],
                },
            },
        }
        scores = fast_tension_scan(registry)
        # No active repos — all dimensions default to 1.0
        assert all(s == 1.0 for s in scores.values())
