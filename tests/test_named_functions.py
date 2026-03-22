"""Tests for governance.named_functions — physiological function registry and organ bridge."""

from __future__ import annotations

import pytest

from organvm_engine.governance.named_functions import (
    NAMED_FUNCTIONS,
    VALID_FUNCTION_NAMES,
    function_to_organ,
    get_function,
    list_functions,
    organ_to_function,
    validate_participation,
)


# ---------------------------------------------------------------------------
# Registry integrity
# ---------------------------------------------------------------------------


class TestNamedFunctions:
    def test_nine_functions(self):
        """8 physiological functions + 1 genome."""
        assert len(NAMED_FUNCTIONS) == 9

    def test_all_have_required_fields(self):
        for key, func in NAMED_FUNCTIONS.items():
            assert "display_name" in func, f"{key} missing display_name"
            assert "physiological_role" in func, f"{key} missing physiological_role"
            assert "greek" in func, f"{key} missing greek"

    def test_only_meta_is_genome(self):
        genomes = [k for k, v in NAMED_FUNCTIONS.items() if v.get("is_genome")]
        assert genomes == ["meta"]

    def test_valid_function_names_frozenset(self):
        assert isinstance(VALID_FUNCTION_NAMES, frozenset)
        assert len(VALID_FUNCTION_NAMES) == 9
        assert "theoria" in VALID_FUNCTION_NAMES
        assert "mneme" in VALID_FUNCTION_NAMES


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


class TestGetFunction:
    def test_known_function(self):
        result = get_function("theoria")
        assert result["display_name"] == "Theoria"
        assert result["key"] == "theoria"
        assert "physiological_role" in result

    def test_genome(self):
        result = get_function("meta")
        assert result["display_name"] == "Genome"
        assert result.get("is_genome") is True

    def test_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown function"):
            get_function("not_a_function")

    def test_all_retrievable(self):
        for name in VALID_FUNCTION_NAMES:
            result = get_function(name)
            assert result["key"] == name


class TestListFunctions:
    def test_returns_all(self):
        funcs = list_functions()
        assert len(funcs) == 9

    def test_each_has_key(self):
        for func in list_functions():
            assert "key" in func
            assert func["key"] in VALID_FUNCTION_NAMES

    def test_does_not_mutate_original(self):
        funcs = list_functions()
        funcs[0]["key"] = "tampered"
        # Original should be unchanged
        assert "tampered" not in NAMED_FUNCTIONS


# ---------------------------------------------------------------------------
# Participation validation
# ---------------------------------------------------------------------------


class TestValidateParticipation:
    def test_valid_primary_only(self):
        valid, errors = validate_participation({"primary": "theoria"})
        assert valid is True
        assert errors == []

    def test_valid_with_secondary(self):
        valid, errors = validate_participation({
            "primary": "theoria",
            "secondary": ["poiesis", "logos"],
        })
        assert valid is True
        assert errors == []

    def test_missing_primary(self):
        valid, errors = validate_participation({})
        assert valid is False
        assert any("primary" in e.lower() for e in errors)

    def test_unknown_primary(self):
        valid, errors = validate_participation({"primary": "bogus"})
        assert valid is False
        assert any("bogus" in e for e in errors)

    def test_unknown_secondary(self):
        valid, errors = validate_participation({
            "primary": "theoria",
            "secondary": ["poiesis", "fake"],
        })
        assert valid is False
        assert any("fake" in e for e in errors)

    def test_primary_in_secondary_is_error(self):
        valid, errors = validate_participation({
            "primary": "theoria",
            "secondary": ["theoria"],
        })
        assert valid is False
        assert any("should not also appear" in e for e in errors)

    def test_secondary_not_a_list(self):
        valid, errors = validate_participation({
            "primary": "theoria",
            "secondary": "poiesis",
        })
        assert valid is False
        assert any("must be a list" in e for e in errors)

    def test_all_functions_valid_as_primary(self):
        for name in VALID_FUNCTION_NAMES:
            valid, _ = validate_participation({"primary": name})
            assert valid is True, f"{name} should be valid as primary"


# ---------------------------------------------------------------------------
# Organ ↔ function bridge
# ---------------------------------------------------------------------------


class TestOrganBridge:
    def test_organ_i_to_theoria(self):
        assert organ_to_function("I") == "theoria"

    def test_organ_ii_to_poiesis(self):
        assert organ_to_function("II") == "poiesis"

    def test_organ_iii_to_ergon(self):
        assert organ_to_function("III") == "ergon"

    def test_organ_iv_to_taxis(self):
        assert organ_to_function("IV") == "taxis"

    def test_organ_v_to_logos(self):
        assert organ_to_function("V") == "logos"

    def test_organ_vi_to_koinonia(self):
        assert organ_to_function("VI") == "koinonia"

    def test_organ_vii_to_kerygma(self):
        assert organ_to_function("VII") == "kerygma"

    def test_meta_to_meta(self):
        assert organ_to_function("META") == "meta"

    def test_liminal_returns_none(self):
        assert organ_to_function("LIMINAL") is None

    def test_unknown_returns_none(self):
        assert organ_to_function("IX") is None


class TestFunctionToOrgan:
    def test_theoria_to_i(self):
        assert function_to_organ("theoria") == "I"

    def test_meta_to_meta(self):
        assert function_to_organ("meta") == "META"

    def test_mneme_has_no_organ(self):
        """mneme is new — no legacy organ maps to it."""
        assert function_to_organ("mneme") is None

    def test_unknown_returns_none(self):
        assert function_to_organ("nonexistent") is None

    def test_roundtrip_all_mapped_organs(self):
        for organ_key in ("I", "II", "III", "IV", "V", "VI", "VII", "META"):
            func = organ_to_function(organ_key)
            assert func is not None
            assert function_to_organ(func) == organ_key
