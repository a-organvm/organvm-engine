"""Tests for the governance module."""

from pathlib import Path

from organvm_engine.governance.dependency_graph import validate_dependencies
from organvm_engine.governance.rules import (
    get_audit_thresholds,
    get_dependency_rules,
    get_organ_requirements,
    get_promotion_rules,
    load_governance_rules,
)
from organvm_engine.governance.state_machine import (
    check_transition,
    execute_transition,
    get_valid_transitions,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestStateMachine:
    def test_local_to_candidate(self):
        ok, msg = check_transition("LOCAL", "CANDIDATE")
        assert ok

    def test_local_to_graduated_invalid(self):
        ok, msg = check_transition("LOCAL", "GRADUATED")
        assert not ok

    def test_archived_is_terminal(self):
        ok, msg = check_transition("ARCHIVED", "LOCAL")
        assert not ok

    def test_get_valid_transitions(self):
        valid = get_valid_transitions("CANDIDATE")
        assert "PUBLIC_PROCESS" in valid
        assert "LOCAL" in valid
        assert "ARCHIVED" in valid

    def test_unknown_state(self):
        ok, msg = check_transition("BOGUS", "LOCAL")
        assert not ok

    def test_execute_transition_records_promotion_history(self):
        """F-002: execute_transition writes promotion_history when registry_entry given."""
        entry = {"name": "test-repo", "promotion_status": "LOCAL"}
        ok, msg = execute_transition(
            repo_name="test-repo",
            current_state="LOCAL",
            target_state="CANDIDATE",
            enforce_infrastructure=False,
            registry_entry=entry,
            reason="initial promotion",
        )
        assert ok
        history = entry.get("promotion_history", [])
        assert len(history) == 1
        assert history[0]["from_state"] == "LOCAL"
        assert history[0]["to_state"] == "CANDIDATE"
        assert history[0]["reason"] == "initial promotion"
        assert "timestamp" in history[0]

    def test_execute_transition_no_history_without_entry(self):
        """F-002: no error when registry_entry is None (backward compat)."""
        ok, msg = execute_transition(
            repo_name="test-repo",
            current_state="LOCAL",
            target_state="CANDIDATE",
            enforce_infrastructure=False,
        )
        assert ok

    def test_execute_transition_no_history_on_failure(self):
        """F-002: failed transitions do not record history."""
        entry = {"name": "test-repo", "promotion_status": "LOCAL"}
        ok, msg = execute_transition(
            repo_name="test-repo",
            current_state="LOCAL",
            target_state="GRADUATED",
            enforce_infrastructure=False,
            registry_entry=entry,
        )
        assert not ok
        assert "promotion_history" not in entry


class TestDependencyGraph:
    def test_valid_graph_passes(self, registry):
        result = validate_dependencies(registry)
        assert result.passed
        assert result.total_edges > 0

    def test_detects_self_dep(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "self-ref",
                            "org": "organvm-i-theoria",
                            "dependencies": ["organvm-i-theoria/self-ref"],
                        },
                    ],
                },
            },
        }
        result = validate_dependencies(registry)
        assert len(result.self_deps) == 1

    def test_detects_back_edge(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "theory",
                            "org": "organvm-i-theoria",
                            "dependencies": ["organvm-ii-poiesis/art"],
                        },
                    ],
                },
                "ORGAN-II": {
                    "repositories": [
                        {
                            "name": "art",
                            "org": "organvm-ii-poiesis",
                            "dependencies": [],
                        },
                    ],
                },
            },
        }
        result = validate_dependencies(registry)
        assert len(result.back_edges) == 1

    def test_detects_cycle(self):
        registry = {
            "organs": {
                "ORGAN-IV": {
                    "repositories": [
                        {
                            "name": "a",
                            "org": "organvm-iv-taxis",
                            "dependencies": ["organvm-iv-taxis/b"],
                        },
                        {
                            "name": "b",
                            "org": "organvm-iv-taxis",
                            "dependencies": ["organvm-iv-taxis/a"],
                        },
                    ],
                },
            },
        }
        result = validate_dependencies(registry)
        assert len(result.cycles) > 0


class TestRules:
    def test_load_test_rules(self):
        rules = load_governance_rules(FIXTURES / "governance-rules-test.json")
        assert rules["version"] == "1.0"
        assert rules["dependency_rules"]["no_circular_dependencies"] is True

    def test_get_dependency_rules_present(self):
        rules = load_governance_rules(FIXTURES / "governance-rules-test.json")
        dep_rules = get_dependency_rules(rules)
        assert dep_rules["no_circular_dependencies"] is True

    def test_get_dependency_rules_missing(self):
        assert get_dependency_rules({}) == {}

    def test_get_promotion_rules_present(self):
        rules = load_governance_rules(FIXTURES / "governance-rules-test.json")
        promo = get_promotion_rules(rules)
        assert "promote-to-art" in promo

    def test_get_audit_thresholds(self):
        rules = load_governance_rules(FIXTURES / "governance-rules-test.json")
        thresholds = get_audit_thresholds(rules)
        assert "critical" in thresholds
        assert "warning" in thresholds

    def test_get_organ_requirements_present(self):
        rules = load_governance_rules(FIXTURES / "governance-rules-test.json")
        reqs = get_organ_requirements(rules, "ORGAN-I")
        assert reqs["min_repos"] == 1

    def test_get_organ_requirements_missing(self):
        rules = load_governance_rules(FIXTURES / "governance-rules-test.json")
        reqs = get_organ_requirements(rules, "ORGAN-X")
        assert reqs == {}
