"""Tests for validate_signal_closure (AX-6)."""

import json
from pathlib import Path
from unittest import mock

import pytest


@pytest.fixture
def mock_registry_with_active_repos():
    """Registry with active repos in ORGAN-I and ORGAN-II."""
    return {
        "version": "2.0",
        "organs": {
            "ORGAN-I": {
                "name": "Theory",
                "repositories": [
                    {
                        "name": "test-repo",
                        "org": "organvm-i-theoria",
                        "implementation_status": "ACTIVE",
                    },
                ],
            },
            "ORGAN-II": {
                "name": "Art",
                "repositories": [
                    {
                        "name": "art-repo",
                        "org": "organvm-ii-poiesis",
                        "implementation_status": "ACTIVE",
                    },
                ],
            },
            "ORGAN-III": {
                "name": "Commerce",
                "repositories": [],
            },
        },
    }


@pytest.fixture
def mock_rules_with_entailments():
    """Governance rules with entailment flows."""
    return {
        "entailment_flows": {
            "organ_entailments": [
                {
                    "source": "ORGAN-I",
                    "activity": "theoretical_research",
                    "entails": [
                        {"target": "ORGAN-II", "signal": "creative-derivation"},
                        {"target": "ORGAN-V", "signal": "public-discourse"},
                    ],
                },
                {
                    "source": "ORGAN-II",
                    "activity": "creative_production",
                    "entails": [
                        {"target": "ORGAN-III", "signal": "commercialization"},
                    ],
                },
            ],
        },
    }


def test_validate_signal_closure_no_workspace():
    """Test that validator returns empty list when workspace is None."""
    from organvm_engine.governance.dictums import validate_signal_closure

    registry = {"organs": {}}
    rules = {"entailment_flows": {"organ_entailments": []}}

    violations = validate_signal_closure(registry, rules, None)
    assert violations == []


def test_validate_signal_closure_no_entailments():
    """Test that validator returns empty list when no entailments defined."""
    from organvm_engine.governance.dictums import validate_signal_closure

    registry = {"organs": {}}
    rules = {}

    with mock.patch("pathlib.Path.exists", return_value=False):
        violations = validate_signal_closure(registry, rules, Path("/tmp"))
        assert violations == []


def test_validate_signal_closure_missing_edges(
    tmp_path, mock_registry_with_active_repos, mock_rules_with_entailments
):
    """Test that validator catches missing produces edges."""
    from organvm_engine.governance.dictums import validate_signal_closure

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    (workspace / "organvm-i-theoria" / "test-repo").mkdir(parents=True)
    (workspace / "organvm-ii-poiesis" / "art-repo").mkdir(parents=True)

    (workspace / "organvm-i-theoria" / "test-repo" / "seed.yaml").write_text("produces: []")
    (workspace / "organvm-ii-poiesis" / "art-repo" / "seed.yaml").write_text("produces: []")

    violations = validate_signal_closure(
        mock_registry_with_active_repos,
        mock_rules_with_entailments,
        workspace,
    )

    assert len(violations) > 0
    ax6_violations = [v for v in violations if v.dictum_id == "AX-6"]
    assert len(ax6_violations) > 0


def test_validate_signal_closure_satisfied(
    tmp_path, mock_registry_with_active_repos, mock_rules_with_entailments
):
    """Test that validator passes when produces edges exist."""
    from organvm_engine.governance.dictums import validate_signal_closure

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    (workspace / "organvm-i-theoria" / "test-repo").mkdir(parents=True)
    (workspace / "organvm-ii-poiesis" / "art-repo").mkdir(parents=True)

    (workspace / "organvm-i-theoria" / "test-repo" / "seed.yaml").write_text(
        "produces:\n  - ORGAN-II\n  - ORGAN-V"
    )
    (workspace / "organvm-ii-poiesis" / "art-repo" / "seed.yaml").write_text(
        "produces:\n  - ORGAN-III"
    )

    violations = validate_signal_closure(
        mock_registry_with_active_repos,
        mock_rules_with_entailments,
        workspace,
    )

    ax6_violations = [v for v in violations if v.dictum_id == "AX-6"]
    assert len(ax6_violations) == 0


def test_validate_signal_closure_archived_repos_excluded(tmp_path, mock_rules_with_entailments):
    """Test that archived repos are excluded from validation."""
    from organvm_engine.governance.dictums import validate_signal_closure

    registry = {
        "organs": {
            "ORGAN-I": {
                "repositories": [
                    {
                        "name": "archived-repo",
                        "org": "organvm-i-theoria",
                        "implementation_status": "ARCHIVED",
                    },
                ],
            },
        },
    }

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    violations = validate_signal_closure(
        registry,
        mock_rules_with_entailments,
        workspace,
    )

    organ_i_violations = [v for v in violations if v.organ == "ORGAN-I"]
    assert len(organ_i_violations) == 0


def test_validate_signal_closure_with_org_format(
    tmp_path, mock_registry_with_active_repos, mock_rules_with_entailments
):
    """Test that validator handles org/repo format in produces."""
    from organvm_engine.governance.dictums import validate_signal_closure

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    (workspace / "organvm-i-theoria" / "test-repo").mkdir(parents=True)

    (workspace / "organvm-i-theoria" / "test-repo" / "seed.yaml").write_text(
        "produces:\n  - organvm-ii-poiesis/art产出\n  - organvm-v-logos/blog"
    )

    violations = validate_signal_closure(
        mock_registry_with_active_repos,
        mock_rules_with_entailments,
        workspace,
    )

    organ_i_violations = [v for v in violations if v.organ == "ORGAN-I"]
    missing_v = [v for v in organ_i_violations if "ORGAN-V" in v.message]
    assert len(missing_v) == 0


def test_get_entailment_flows():
    """Test extraction of entailment flows from rules."""
    from organvm_engine.governance.dictums import get_entailment_flows

    rules = {
        "entailment_flows": {
            "organ_entailments": [
                {"source": "ORGAN-I", "entails": [{"target": "ORGAN-II"}]},
            ]
        }
    }

    flows = get_entailment_flows(rules)
    assert len(flows) == 1
    assert flows[0]["source"] == "ORGAN-I"


def test_extract_organ_from_produces_entry():
    """Test extraction of organ from produces entry."""
    from organvm_engine.governance.dictums import _extract_organ_from_produces_entry

    assert _extract_organ_from_produces_entry("ORGAN-V") == "ORGAN-V"
    assert _extract_organ_from_produces_entry("organvm-ii-poiesis/repo") == "ORGAN-II"
    assert _extract_organ_from_produces_entry("organvm-v-logos") == "ORGAN-V"
    assert _extract_organ_from_produces_entry("unknown-format") is None
    assert _extract_organ_from_produces_entry("") is None
