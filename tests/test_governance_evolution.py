"""Tests for governance.evolution — SPEC-008, EVOL-001 through EVOL-003."""

import pytest

from organvm_engine.governance.evolution import (
    ChangeMode,
    classify_change,
    create_migration_record,
    evaluate_evolution_policy,
    validate_migration_record,
)


# ---------------------------------------------------------------------------
# ChangeMode enum
# ---------------------------------------------------------------------------

class TestChangeMode:
    def test_values(self):
        assert ChangeMode.CONSERVATIVE.value == "CONSERVATIVE"
        assert ChangeMode.CONSTRAINED.value == "CONSTRAINED"
        assert ChangeMode.BREAKING.value == "BREAKING"

    def test_is_str_enum(self):
        assert isinstance(ChangeMode.CONSERVATIVE, str)
        assert ChangeMode.CONSERVATIVE == "CONSERVATIVE"

    def test_members_count(self):
        assert len(ChangeMode) == 3


# ---------------------------------------------------------------------------
# classify_change
# ---------------------------------------------------------------------------

class TestClassifyChange:
    def test_empty_before_is_conservative(self):
        result = classify_change({}, {"new_key": "value"})
        assert result == ChangeMode.CONSERVATIVE

    def test_identical_states_conservative(self):
        state = {"a": 1, "b": "x"}
        result = classify_change(state, state.copy())
        assert result == ChangeMode.CONSERVATIVE

    def test_additive_only_conservative(self):
        before = {"a": 1}
        after = {"a": 1, "b": 2}
        result = classify_change(before, after)
        assert result == ChangeMode.CONSERVATIVE

    def test_value_change_constrained(self):
        before = {"a": 1}
        after = {"a": 2}
        result = classify_change(before, after)
        assert result == ChangeMode.CONSTRAINED

    def test_value_change_with_addition_constrained(self):
        before = {"a": 1}
        after = {"a": 2, "b": 3}
        result = classify_change(before, after)
        assert result == ChangeMode.CONSTRAINED

    def test_removed_key_breaking(self):
        before = {"a": 1, "b": 2}
        after = {"a": 1}
        result = classify_change(before, after)
        assert result == ChangeMode.BREAKING

    def test_type_change_breaking(self):
        before = {"a": "string"}
        after = {"a": 42}
        result = classify_change(before, after)
        assert result == ChangeMode.BREAKING

    def test_list_to_dict_breaking(self):
        before = {"a": [1, 2]}
        after = {"a": {"x": 1}}
        result = classify_change(before, after)
        assert result == ChangeMode.BREAKING

    def test_deep_value_change_constrained(self):
        before = {"a": {"nested": 1}}
        after = {"a": {"nested": 2}}
        result = classify_change(before, after)
        assert result == ChangeMode.CONSTRAINED

    def test_both_empty_conservative(self):
        result = classify_change({}, {})
        assert result == ChangeMode.CONSERVATIVE


# ---------------------------------------------------------------------------
# evaluate_evolution_policy
# ---------------------------------------------------------------------------

class TestEvaluatePolicy:
    def test_conservative_always_permitted(self):
        ok, msgs = evaluate_evolution_policy(ChangeMode.CONSERVATIVE, ["SPEC-000"])
        assert ok
        assert any("Conservative" in m for m in msgs)

    def test_constrained_non_core_permitted(self):
        ok, msgs = evaluate_evolution_policy(ChangeMode.CONSTRAINED, ["SPEC-099"])
        assert ok
        assert any("permitted" in m for m in msgs)

    def test_constrained_core_advisory(self):
        ok, msgs = evaluate_evolution_policy(ChangeMode.CONSTRAINED, ["SPEC-004"])
        assert ok
        assert any("Advisory" in m for m in msgs)
        assert any("SPEC-004" in m for m in msgs)

    def test_constrained_multiple_core_specs(self):
        ok, msgs = evaluate_evolution_policy(
            ChangeMode.CONSTRAINED, ["SPEC-001", "SPEC-003"],
        )
        assert ok
        assert len([m for m in msgs if "Advisory" in m]) == 2

    def test_breaking_core_blocked(self):
        ok, msgs = evaluate_evolution_policy(ChangeMode.BREAKING, ["SPEC-004"])
        assert not ok
        assert any("Blocked" in m for m in msgs)
        assert any("EVOL-004" in m for m in msgs)

    def test_breaking_non_core_permitted(self):
        ok, msgs = evaluate_evolution_policy(ChangeMode.BREAKING, ["SPEC-099"])
        assert ok
        assert any("permitted" in m for m in msgs)

    def test_breaking_mixed_specs_blocked(self):
        ok, msgs = evaluate_evolution_policy(
            ChangeMode.BREAKING, ["SPEC-099", "SPEC-000"],
        )
        assert not ok
        assert any("SPEC-000" in m for m in msgs)

    def test_breaking_empty_specs_permitted(self):
        ok, msgs = evaluate_evolution_policy(ChangeMode.BREAKING, [])
        assert ok

    def test_conservative_empty_specs(self):
        ok, msgs = evaluate_evolution_policy(ChangeMode.CONSERVATIVE, [])
        assert ok


# ---------------------------------------------------------------------------
# create_migration_record
# ---------------------------------------------------------------------------

class TestCreateMigrationRecord:
    def test_basic_record(self):
        record = create_migration_record(
            ChangeMode.BREAKING,
            "Removed legacy field",
            ["ent_001", "ent_002"],
        )
        assert record["change_mode"] == "BREAKING"
        assert record["description"] == "Removed legacy field"
        assert record["affected_entities"] == ["ent_001", "ent_002"]
        assert record["status"] == "pending"
        assert record["spec_reference"] == "EVOL-004"
        assert "migration_id" in record
        assert "created_at" in record

    def test_string_change_mode(self):
        record = create_migration_record(
            "CONSTRAINED", "Updated field", ["ent_001"],
        )
        assert record["change_mode"] == "CONSTRAINED"

    def test_custom_actor(self):
        record = create_migration_record(
            ChangeMode.CONSERVATIVE, "Docs update", ["ent_001"], actor="human",
        )
        assert record["actor"] == "human"

    def test_default_actor(self):
        record = create_migration_record(
            ChangeMode.CONSERVATIVE, "Test", ["ent_001"],
        )
        assert record["actor"] == "cli"

    def test_unique_ids(self):
        r1 = create_migration_record(ChangeMode.BREAKING, "A", ["e1"])
        r2 = create_migration_record(ChangeMode.BREAKING, "B", ["e2"])
        assert r1["migration_id"] != r2["migration_id"]


# ---------------------------------------------------------------------------
# validate_migration_record
# ---------------------------------------------------------------------------

class TestValidateMigrationRecord:
    def test_valid_record(self):
        record = create_migration_record(
            ChangeMode.BREAKING, "Test change", ["ent_001"],
        )
        valid, errors = validate_migration_record(record)
        assert valid
        assert errors == []

    def test_missing_required_field(self):
        record = {"change_mode": "BREAKING"}
        valid, errors = validate_migration_record(record)
        assert not valid
        assert any("migration_id" in e for e in errors)

    def test_invalid_change_mode(self):
        record = create_migration_record(ChangeMode.BREAKING, "Test", ["e1"])
        record["change_mode"] = "INVALID"
        valid, errors = validate_migration_record(record)
        assert not valid
        assert any("invalid change_mode" in e for e in errors)

    def test_empty_affected_entities(self):
        record = create_migration_record(ChangeMode.BREAKING, "Test", ["e1"])
        record["affected_entities"] = []
        valid, errors = validate_migration_record(record)
        assert not valid
        assert any("must not be empty" in e for e in errors)

    def test_non_list_affected_entities(self):
        record = create_migration_record(ChangeMode.BREAKING, "Test", ["e1"])
        record["affected_entities"] = "not a list"
        valid, errors = validate_migration_record(record)
        assert not valid
        assert any("must be a list" in e for e in errors)

    def test_invalid_status(self):
        record = create_migration_record(ChangeMode.BREAKING, "Test", ["e1"])
        record["status"] = "completed"
        valid, errors = validate_migration_record(record)
        assert not valid
        assert any("invalid status" in e for e in errors)

    def test_valid_statuses(self):
        for status in ("pending", "applied", "rolled_back"):
            record = create_migration_record(ChangeMode.BREAKING, "Test", ["e1"])
            record["status"] = status
            valid, errors = validate_migration_record(record)
            assert valid, f"status '{status}' should be valid"
