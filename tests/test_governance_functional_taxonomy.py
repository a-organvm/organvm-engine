"""Tests for functional taxonomy engine (INST-TAXONOMY)."""

import pytest

from organvm_engine.governance.functional_taxonomy import (
    FunctionalClass,
    classify_repo,
    validate_classification,
)

# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------


class TestFunctionalClass:
    def test_all_ten(self):
        assert len(FunctionalClass) == 10

    def test_values(self):
        assert FunctionalClass.CHARTER.value == "CHARTER"
        assert FunctionalClass.OPERATIONS.value == "OPERATIONS"


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


class TestClassifyRepo:
    def test_corpus(self):
        repo = {"name": "organvm-corpvs-testamentvm", "description": "Governance corpus"}
        assert classify_repo(repo) == FunctionalClass.CORPUS

    def test_engine(self):
        repo = {"name": "organvm-engine", "tier": "flagship"}
        assert classify_repo(repo) == FunctionalClass.ENGINE

    def test_dashboard_is_application(self):
        repo = {"name": "system-dashboard", "description": "Web dashboard UI"}
        assert classify_repo(repo) == FunctionalClass.APPLICATION

    def test_mcp_server_is_infrastructure(self):
        repo = {"name": "organvm-mcp-server", "tier": "infrastructure"}
        assert classify_repo(repo) == FunctionalClass.INFRASTRUCTURE

    def test_archive_tier(self):
        repo = {"name": "old-thing", "tier": "archive"}
        assert classify_repo(repo) == FunctionalClass.ARCHIVE

    def test_praxis_is_operations(self):
        repo = {"name": "praxis-perpetua", "description": "Process governance SOPs"}
        assert classify_repo(repo) == FunctionalClass.OPERATIONS

    def test_framework_keyword(self):
        repo = {"name": "ui-framework", "description": "Reusable component library"}
        assert classify_repo(repo) == FunctionalClass.FRAMEWORK

    def test_experiment_keyword(self):
        repo = {"name": "experiment-lab", "description": "Sandbox prototype"}
        assert classify_repo(repo) == FunctionalClass.EXPERIMENT

    def test_charter_keyword(self):
        repo = {"name": "system-charter", "description": "Constitutional manifesto"}
        assert classify_repo(repo) == FunctionalClass.CHARTER

    def test_fallback_is_application(self):
        repo = {"name": "some-random-project", "description": "Does things"}
        assert classify_repo(repo) == FunctionalClass.APPLICATION

    def test_empty_repo(self):
        result = classify_repo({})
        assert isinstance(result, FunctionalClass)

    def test_assurance_keyword(self):
        repo = {"name": "lint-checker", "description": "Audit tool for verification"}
        assert classify_repo(repo) == FunctionalClass.ASSURANCE


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidateClassification:
    def test_archive_with_archived_status(self):
        repo = {"promotion_status": "ARCHIVED"}
        valid, warnings = validate_classification(repo, FunctionalClass.ARCHIVE)
        assert valid is True

    def test_archive_without_archived_status(self):
        repo = {"promotion_status": "PUBLIC_PROCESS", "implementation_status": "ACTIVE"}
        valid, warnings = validate_classification(repo, FunctionalClass.ARCHIVE)
        assert valid is False
        assert any("ARCHIVED" in w for w in warnings)

    def test_engine_with_flagship_tier(self):
        repo = {"tier": "flagship"}
        valid, warnings = validate_classification(repo, FunctionalClass.ENGINE)
        assert valid is True

    def test_engine_with_wrong_tier(self):
        repo = {"tier": "infrastructure"}
        valid, warnings = validate_classification(repo, FunctionalClass.ENGINE)
        assert valid is False

    def test_charter_with_code(self):
        repo = {"code_files": 50}
        valid, warnings = validate_classification(repo, FunctionalClass.CHARTER)
        assert valid is False
        assert any("code files" in w.lower() for w in warnings)

    def test_charter_without_code(self):
        repo = {"code_files": 5}
        valid, warnings = validate_classification(repo, FunctionalClass.CHARTER)
        assert valid is True

    def test_experiment_graduated(self):
        repo = {"promotion_status": "GRADUATED"}
        valid, warnings = validate_classification(repo, FunctionalClass.EXPERIMENT)
        assert valid is False
        assert any("experiment" in w.lower() for w in warnings)

    def test_application_always_valid(self):
        repo = {"tier": "standard", "promotion_status": "LOCAL"}
        valid, warnings = validate_classification(repo, FunctionalClass.APPLICATION)
        assert valid is True
