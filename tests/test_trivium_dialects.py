"""Tests for trivium dialect enumeration and organ mapping."""

import pytest

from organvm_engine.trivium.dialects import (
    Dialect,
    DialectProfile,
    all_dialects,
    classical_parallel,
    dialect_for_organ,
    dialect_profile,
    organ_for_dialect,
)


def test_dialect_enum_has_eight_members():
    assert len(Dialect) == 8


def test_dialect_names_match_organs():
    expected = {
        "FORMAL_LOGIC",
        "AESTHETIC_FORM",
        "EXECUTABLE_ALGORITHM",
        "GOVERNANCE_LOGIC",
        "NATURAL_RHETORIC",
        "PEDAGOGICAL_DIALECTIC",
        "SIGNAL_PROPAGATION",
        "SELF_WITNESSING",
    }
    assert {d.name for d in Dialect} == expected


def test_dialect_for_organ_all_eight():
    for key in ["I", "II", "III", "IV", "V", "VI", "VII", "META"]:
        d = dialect_for_organ(key)
        assert isinstance(d, Dialect)


def test_dialect_for_organ_round_trip():
    for organ_key in ["I", "II", "III", "IV", "V", "VI", "VII", "META"]:
        dialect = dialect_for_organ(organ_key)
        assert organ_for_dialect(dialect) == organ_key


def test_organ_for_dialect_round_trip():
    for dialect in Dialect:
        organ_key = organ_for_dialect(dialect)
        assert dialect_for_organ(organ_key) == dialect


def test_dialect_profile_has_required_fields():
    for dialect in Dialect:
        p = dialect_profile(dialect)
        assert isinstance(p, DialectProfile)
        assert p.dialect == dialect
        assert p.translation_role
        assert p.formal_basis
        assert p.classical_parallel
        assert p.description
        assert p.organ_key
        assert p.organ_name


def test_dialect_profile_organ_keys_match_mapping():
    for dialect in Dialect:
        p = dialect_profile(dialect)
        assert dialect_for_organ(p.organ_key) == dialect


def test_classical_parallel_covers_trivium_and_quadrivium():
    parallels = {classical_parallel(d) for d in Dialect}
    assert "Logic" in parallels
    assert "Music" in parallels
    assert "Arithmetic" in parallels
    assert "Rhetoric" in parallels
    assert "Grammar" in parallels
    assert "Geometry" in parallels
    assert "Astronomy" in parallels
    assert "The Eighth Art" in parallels


def test_classical_parallel_all_unique():
    parallels = [classical_parallel(d) for d in Dialect]
    assert len(parallels) == len(set(parallels))


def test_all_dialects_returns_eight():
    result = all_dialects()
    assert len(result) == 8
    assert all(isinstance(d, Dialect) for d in result)


def test_all_dialects_in_organ_order():
    result = all_dialects()
    expected_order = [
        Dialect.FORMAL_LOGIC,
        Dialect.AESTHETIC_FORM,
        Dialect.EXECUTABLE_ALGORITHM,
        Dialect.GOVERNANCE_LOGIC,
        Dialect.NATURAL_RHETORIC,
        Dialect.PEDAGOGICAL_DIALECTIC,
        Dialect.SIGNAL_PROPAGATION,
        Dialect.SELF_WITNESSING,
    ]
    assert result == expected_order


def test_unknown_organ_raises():
    with pytest.raises(KeyError):
        dialect_for_organ("NONEXISTENT")


def test_specific_mappings():
    assert dialect_for_organ("I") == Dialect.FORMAL_LOGIC
    assert dialect_for_organ("III") == Dialect.EXECUTABLE_ALGORITHM
    assert dialect_for_organ("META") == Dialect.SELF_WITNESSING


def test_dialect_values_are_snake_case():
    for d in Dialect:
        assert d.value == d.value.lower()
        assert " " not in d.value


def test_profiles_frozen():
    p = dialect_profile(Dialect.FORMAL_LOGIC)
    with pytest.raises(AttributeError):
        p.organ_key = "changed"  # type: ignore[misc]
