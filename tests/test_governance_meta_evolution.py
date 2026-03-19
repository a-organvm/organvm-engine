"""Tests for meta-evolution engine (SPEC-011)."""

import pytest

from organvm_engine.governance.meta_evolution import (
    EvolutionClassification,
    EvolutionStratum,
    SafetyCheck,
    check_safety_constraints,
    classify_evolution,
    stratum_severity,
)

# ---------------------------------------------------------------------------
# Stratum severity
# ---------------------------------------------------------------------------


class TestStratumSeverity:
    def test_state_lowest(self):
        assert stratum_severity(EvolutionStratum.STATE) == 0

    def test_meta_highest(self):
        assert stratum_severity(EvolutionStratum.META_EVOLUTION) == 3

    def test_ordering(self):
        severities = [
            stratum_severity(EvolutionStratum.STATE),
            stratum_severity(EvolutionStratum.STRUCTURE),
            stratum_severity(EvolutionStratum.ONTOLOGY),
            stratum_severity(EvolutionStratum.META_EVOLUTION),
        ]
        assert severities == sorted(severities)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


class TestClassifyEvolution:
    def test_metric_update_is_state(self):
        result = classify_evolution("Updated metric value for test_files")
        assert result.stratum == EvolutionStratum.STATE

    def test_status_change_is_state(self):
        result = classify_evolution("Changed implementation_status to ACTIVE")
        assert result.stratum == EvolutionStratum.STATE

    def test_dependency_change_is_structure(self):
        result = classify_evolution("Added dependency from repo A to repo B")
        assert result.stratum == EvolutionStratum.STRUCTURE

    def test_module_split_is_structure(self):
        result = classify_evolution("Split module X into two new modules")
        assert result.stratum == EvolutionStratum.STRUCTURE

    def test_schema_change_is_ontology(self):
        result = classify_evolution("Changed schema definition for entity_type")
        assert result.stratum == EvolutionStratum.ONTOLOGY

    def test_taxonomy_change_is_ontology(self):
        result = classify_evolution("Updated taxonomy categories")
        assert result.stratum == EvolutionStratum.ONTOLOGY

    def test_governance_rule_is_meta(self):
        result = classify_evolution("Modified governance_rule for promotion")
        assert result.stratum == EvolutionStratum.META_EVOLUTION

    def test_constitutional_amendment_is_meta(self):
        result = classify_evolution("Constitutional amendment to axiom set")
        assert result.stratum == EvolutionStratum.META_EVOLUTION

    def test_empty_description_is_state(self):
        result = classify_evolution("")
        assert result.stratum == EvolutionStratum.STATE

    def test_unrecognized_is_state(self):
        result = classify_evolution("Fixed a typo in the readme")
        assert result.stratum == EvolutionStratum.STATE

    def test_matched_keywords_populated(self):
        result = classify_evolution("Renamed the module hierarchy")
        assert len(result.matched_keywords) > 0
        assert "hierarchy" in result.matched_keywords or "module" in result.matched_keywords

    def test_to_dict(self):
        result = classify_evolution("metric update")
        d = result.to_dict()
        assert "stratum" in d
        assert "severity" in d
        assert "matched_keywords" in d


# ---------------------------------------------------------------------------
# Safety constraints
# ---------------------------------------------------------------------------


class TestCheckSafetyConstraints:
    def test_state_is_safe(self):
        safe, constraints = check_safety_constraints(EvolutionStratum.STATE)
        assert safe is True
        assert constraints == []

    def test_structure_not_safe(self):
        safe, constraints = check_safety_constraints(EvolutionStratum.STRUCTURE)
        assert safe is False
        assert len(constraints) >= 2

    def test_ontology_requires_migration(self):
        safe, constraints = check_safety_constraints(EvolutionStratum.ONTOLOGY)
        assert safe is False
        assert any("migration" in c.lower() for c in constraints)

    def test_meta_evolution_requires_amendment(self):
        safe, constraints = check_safety_constraints(
            EvolutionStratum.META_EVOLUTION,
        )
        assert safe is False
        assert any("amendment" in c.lower() for c in constraints)
        assert len(constraints) >= 4

    def test_meta_strictest(self):
        _, state_c = check_safety_constraints(EvolutionStratum.STATE)
        _, struct_c = check_safety_constraints(EvolutionStratum.STRUCTURE)
        _, onto_c = check_safety_constraints(EvolutionStratum.ONTOLOGY)
        _, meta_c = check_safety_constraints(EvolutionStratum.META_EVOLUTION)
        assert len(state_c) < len(struct_c) < len(onto_c) < len(meta_c)
