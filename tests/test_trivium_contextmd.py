"""Tests for trivium context injection into generated CLAUDE.md files."""

from organvm_engine.contextmd.generator import _build_trivium_context


def test_trivium_context_organ_i():
    result = _build_trivium_context("ORGAN-I")
    assert "FORMAL_LOGIC" in result
    assert "Logic" in result  # classical parallel
    assert "Grammar" in result  # translation role


def test_trivium_context_meta():
    result = _build_trivium_context("META-ORGANVM")
    assert "SELF_WITNESSING" in result
    assert "Eighth Art" in result


def test_trivium_context_organ_iii():
    result = _build_trivium_context("ORGAN-III")
    assert "EXECUTABLE_ALGORITHM" in result
    assert "Arithmetic" in result


def test_trivium_context_has_strongest_pairs():
    result = _build_trivium_context("ORGAN-I")
    # Should mention at least one translation partner
    assert "formal" in result.lower() or "structural" in result.lower()


def test_trivium_context_has_cli_commands():
    result = _build_trivium_context("ORGAN-I")
    assert "organvm trivium" in result


def test_trivium_context_unknown_organ():
    result = _build_trivium_context("NONEXISTENT")
    assert result == ""


def test_trivium_context_all_organs():
    organ_keys = [
        "ORGAN-I", "ORGAN-II", "ORGAN-III", "ORGAN-IV",
        "ORGAN-V", "ORGAN-VI", "ORGAN-VII", "META-ORGANVM",
    ]
    for key in organ_keys:
        result = _build_trivium_context(key)
        assert result, f"No trivium context for {key}"
        assert "Dialect" in result
