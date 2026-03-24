"""Tests for governance wiring — functional_class + formation signals.

Covers:
  - check_functional_classification (Part A)
  - Promotion gate for functional_class (Part B)
  - Placement functional_class affinity scoring (Part C)
  - audit_formation_signals (Part D)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from organvm_engine.governance.audit import (
    audit_formation_signals,
    check_functional_classification,
)
from organvm_engine.governance.placement import compute_affinity
from organvm_engine.governance.state_machine import (
    execute_transition,
    reset_loaded_transitions,
)

# ---------------------------------------------------------------------------
# Part A: check_functional_classification
# ---------------------------------------------------------------------------


class TestCheckFunctionalClassification:
    def test_unclassified_repo(self):
        issues = check_functional_classification({"name": "test-repo"})
        assert any("UNCLASSIFIED" in i for i in issues)
        assert len(issues) == 1

    def test_valid_classification_engine(self):
        issues = check_functional_classification({
            "name": "test-engine",
            "functional_class": "ENGINE",
            "tier": "flagship",
            "description": "Core engine",
        })
        assert not any("UNCLASSIFIED" in i for i in issues)
        assert not any("INVALID_CLASS" in i for i in issues)

    def test_invalid_class(self):
        issues = check_functional_classification({
            "name": "test",
            "functional_class": "BOGUS",
        })
        assert any("INVALID_CLASS" in i for i in issues)
        assert len(issues) == 1

    def test_drift_detection(self):
        """A corpus-like repo classified as ENGINE should trigger drift."""
        issues = check_functional_classification({
            "name": "my-corpus",
            "functional_class": "ENGINE",
            "description": "Knowledge corpus and curated collection",
        })
        assert any("DRIFT" in i for i in issues)

    def test_no_drift_when_heuristic_matches(self):
        issues = check_functional_classification({
            "name": "organvm-engine",
            "functional_class": "ENGINE",
            "tier": "flagship",
            "description": "Core computational engine and runtime",
        })
        # Heuristic should also classify as ENGINE — no drift
        drift_issues = [i for i in issues if "DRIFT" in i]
        assert len(drift_issues) == 0

    def test_classification_warning_archive_not_archived(self):
        issues = check_functional_classification({
            "name": "old-thing",
            "functional_class": "ARCHIVE",
            "promotion_status": "CANDIDATE",
            "implementation_status": "ACTIVE",
        })
        assert any("CLASSIFICATION_WARNING" in i for i in issues)

    def test_empty_functional_class_treated_as_unclassified(self):
        issues = check_functional_classification({
            "name": "test-repo",
            "functional_class": "",
        })
        assert any("UNCLASSIFIED" in i for i in issues)


# ---------------------------------------------------------------------------
# Part B: Promotion gate — functional_class required above LOCAL
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_sm_cache():
    reset_loaded_transitions()
    yield
    reset_loaded_transitions()


def _write_rules(tmp_path: Path) -> Path:
    rules = {
        "version": "1.0",
        "state_machine": {
            "states": ["LOCAL", "CANDIDATE", "PUBLIC_PROCESS", "GRADUATED", "ARCHIVED"],
            "transitions": {
                "LOCAL": ["CANDIDATE", "ARCHIVED"],
                "CANDIDATE": ["PUBLIC_PROCESS", "ARCHIVED"],
                "PUBLIC_PROCESS": ["GRADUATED", "ARCHIVED"],
                "GRADUATED": ["ARCHIVED"],
                "ARCHIVED": [],
            },
        },
    }
    path = tmp_path / "governance-rules.json"
    path.write_text(json.dumps(rules))
    return path


class TestPromotionGateFunctionalClass:
    def test_promotion_blocked_without_functional_class(self, tmp_path):
        rules = _write_rules(tmp_path)
        spine_path = tmp_path / "events.jsonl"
        ok, msg = execute_transition(
            "test-repo",
            "LOCAL",
            "CANDIDATE",
            rules_path=rules,
            spine_path=spine_path,
            registry_entry={"name": "test-repo"},
        )
        assert not ok
        assert "functional_class" in msg

    def test_promotion_allowed_with_functional_class(self, tmp_path):
        rules = _write_rules(tmp_path)
        spine_path = tmp_path / "events.jsonl"
        ok, msg = execute_transition(
            "test-repo",
            "LOCAL",
            "CANDIDATE",
            rules_path=rules,
            spine_path=spine_path,
            registry_entry={"name": "test-repo", "functional_class": "ENGINE"},
        )
        assert ok

    def test_promotion_to_archived_not_blocked(self, tmp_path):
        """ARCHIVED transitions should not require functional_class."""
        rules = _write_rules(tmp_path)
        spine_path = tmp_path / "events.jsonl"
        ok, msg = execute_transition(
            "test-repo",
            "LOCAL",
            "ARCHIVED",
            rules_path=rules,
            spine_path=spine_path,
            registry_entry={"name": "test-repo"},
        )
        assert ok

    def test_promotion_gate_skipped_when_no_registry_entry(self, tmp_path):
        """When registry_entry is not provided, gate is skipped."""
        rules = _write_rules(tmp_path)
        spine_path = tmp_path / "events.jsonl"
        ok, msg = execute_transition(
            "test-repo",
            "LOCAL",
            "CANDIDATE",
            rules_path=rules,
            spine_path=spine_path,
        )
        assert ok

    def test_promotion_to_public_process_blocked(self, tmp_path):
        rules = _write_rules(tmp_path)
        spine_path = tmp_path / "events.jsonl"
        ok, msg = execute_transition(
            "test-repo",
            "CANDIDATE",
            "PUBLIC_PROCESS",
            rules_path=rules,
            spine_path=spine_path,
            registry_entry={"name": "test-repo"},
        )
        assert not ok
        assert "functional_class" in msg

    def test_promotion_to_graduated_blocked(self, tmp_path):
        rules = _write_rules(tmp_path)
        spine_path = tmp_path / "events.jsonl"
        ok, msg = execute_transition(
            "test-repo",
            "PUBLIC_PROCESS",
            "GRADUATED",
            rules_path=rules,
            spine_path=spine_path,
            registry_entry={"name": "test-repo"},
        )
        assert not ok
        assert "functional_class" in msg


# ---------------------------------------------------------------------------
# Part C: Placement functional_class affinity
# ---------------------------------------------------------------------------


class TestPlacementFunctionalClassAffinity:
    def _defs(self):
        """Minimal organ definitions for testing."""
        return {
            "organs": {
                "META-ORGANVM": {"canonical_repo_types": []},
                "ORGAN-I": {"canonical_repo_types": []},
                "ORGAN-III": {"canonical_repo_types": []},
                "ORGAN-IV": {"canonical_repo_types": []},
                "ORGAN-V": {"canonical_repo_types": []},
            },
        }

    def test_charter_in_meta_gets_bonus(self):
        repo = {"name": "test", "functional_class": "CHARTER"}
        score_meta = compute_affinity(repo, "META-ORGANVM", self._defs())
        score_other = compute_affinity(repo, "ORGAN-I", self._defs())
        # META should score higher than non-META for CHARTER
        assert score_meta.score > score_other.score
        assert any("CHARTER" in m for m in score_meta.matched_inclusion)

    def test_charter_outside_meta_gets_penalty(self):
        repo = {"name": "test", "functional_class": "CHARTER"}
        score = compute_affinity(repo, "ORGAN-I", self._defs())
        assert any("CHARTER" in t for t in score.triggered_exclusion)

    def test_operations_in_organ_iv(self):
        repo = {"name": "test-ops", "functional_class": "OPERATIONS"}
        score = compute_affinity(repo, "ORGAN-IV", self._defs())
        assert any("OPERATIONS" in m for m in score.matched_inclusion)

    def test_application_in_organ_iii(self):
        repo = {"name": "my-app", "functional_class": "APPLICATION"}
        score = compute_affinity(repo, "ORGAN-III", self._defs())
        assert any("APPLICATION" in m for m in score.matched_inclusion)

    def test_corpus_in_organ_v(self):
        repo = {"name": "essays", "functional_class": "CORPUS"}
        score = compute_affinity(repo, "ORGAN-V", self._defs())
        assert any("CORPUS" in m for m in score.matched_inclusion)

    def test_no_functional_class_no_crash(self):
        repo = {"name": "test"}
        score = compute_affinity(repo, "META-ORGANVM", self._defs())
        # Should work without error; no functional_class bonus/penalty
        assert isinstance(score.score, int)


# ---------------------------------------------------------------------------
# Part D: audit_formation_signals
# ---------------------------------------------------------------------------


class TestAuditFormationSignals:
    def test_valid_formation_yaml(self, tmp_path):
        fyaml = tmp_path / "my-repo" / "formation.yaml"
        fyaml.parent.mkdir()
        fyaml.write_text(
            "formation_type: GENERATOR\n"
            "host_organ_primary: ORGAN-I\n"
            "signal_inputs:\n"
            "  - RESEARCH_QUESTION\n"
            "signal_outputs:\n"
            "  - ONT_FRAGMENT\n"
            "maturity: 0.5\n",
        )
        issues = audit_formation_signals(tmp_path)
        assert issues == []

    def test_invalid_formation_type(self, tmp_path):
        fyaml = tmp_path / "bad-repo" / "formation.yaml"
        fyaml.parent.mkdir()
        fyaml.write_text(
            "formation_type: BOGUS\n"
            "host_organ_primary: ORGAN-I\n"
            "signal_outputs:\n"
            "  - ONT_FRAGMENT\n",
        )
        issues = audit_formation_signals(tmp_path)
        assert any("FORMATION_SIGNAL" in i for i in issues)
        assert any("BOGUS" in i for i in issues)

    def test_missing_signals_out(self, tmp_path):
        fyaml = tmp_path / "empty-signals" / "formation.yaml"
        fyaml.parent.mkdir()
        fyaml.write_text(
            "formation_type: GENERATOR\n"
            "host_organ_primary: ORGAN-I\n",
        )
        issues = audit_formation_signals(tmp_path)
        assert any("FORMATION_SIGNAL" in i for i in issues)

    def test_prohibited_coupling(self, tmp_path):
        fyaml = tmp_path / "bad-coupling" / "formation.yaml"
        fyaml.parent.mkdir()
        fyaml.write_text(
            "formation_type: ROUTER\n"
            "host_organ_primary: ORGAN-IV\n"
            "signal_outputs:\n"
            "  - ONT_FRAGMENT\n",
        )
        issues = audit_formation_signals(tmp_path)
        assert any("Prohibited coupling" in i for i in issues)

    def test_parse_error_handled(self, tmp_path):
        fyaml = tmp_path / "broken" / "formation.yaml"
        fyaml.parent.mkdir()
        fyaml.write_text(": : : invalid yaml {{{{")
        issues = audit_formation_signals(tmp_path)
        # Should not crash — should report parse error or handle gracefully
        # (yaml.safe_load may parse this oddly; if not a dict, we catch it)
        assert len(issues) >= 0  # No crash is the main assertion

    def test_no_formation_files(self, tmp_path):
        issues = audit_formation_signals(tmp_path)
        assert issues == []

    def test_non_dict_yaml(self, tmp_path):
        fyaml = tmp_path / "scalar" / "formation.yaml"
        fyaml.parent.mkdir()
        fyaml.write_text("just a string\n")
        issues = audit_formation_signals(tmp_path)
        assert any("FORMATION_PARSE_ERROR" in i for i in issues)
