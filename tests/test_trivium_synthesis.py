"""Tests for trivium narrative synthesis."""

import json
from pathlib import Path

from organvm_engine.trivium.dialects import Dialect
from organvm_engine.trivium.synthesis import (
    render_dialect_portrait,
    render_translation_matrix_markdown,
    synthesize_trivium_testament,
    write_testament,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "registry-trivium.json"


def test_synthesize_testament_returns_markdown():
    result = synthesize_trivium_testament(registry_path=FIXTURE_PATH)
    assert isinstance(result, str)
    assert "# Trivium Testament" in result


def test_synthesize_testament_has_dialect_table():
    result = synthesize_trivium_testament(registry_path=FIXTURE_PATH)
    assert "Eight Dialects" in result
    assert "Theoria" in result
    assert "Ergon" in result


def test_synthesize_testament_has_tier_breakdown():
    result = synthesize_trivium_testament(registry_path=FIXTURE_PATH)
    assert "Formal" in result
    assert "Structural" in result


def test_synthesize_testament_has_thesis():
    result = synthesize_trivium_testament(registry_path=FIXTURE_PATH)
    assert "structural isomorphism" in result


def test_synthesize_testament_no_registry():
    result = synthesize_trivium_testament()
    assert isinstance(result, str)
    assert "Trivium" in result


def test_translation_matrix_markdown_empty():
    result = render_translation_matrix_markdown({})
    assert "No translation evidence" in result


def test_translation_matrix_markdown_with_data():
    from organvm_engine.trivium.translator import (
        TranslationEvidence,
        translation_matrix,
    )
    with FIXTURE_PATH.open() as f:
        registry = json.load(f)
    matrix = translation_matrix(registry=registry)
    result = render_translation_matrix_markdown(matrix)
    assert "Source" in result
    assert "Target" in result
    assert "|" in result


def test_dialect_portrait_formal_logic():
    result = render_dialect_portrait(Dialect.FORMAL_LOGIC)
    assert isinstance(result, str)
    assert "Theoria" in result
    assert "Logic" in result


def test_dialect_portrait_self_witnessing():
    result = render_dialect_portrait(Dialect.SELF_WITNESSING)
    assert "Meta" in result
    assert "Eighth Art" in result


def test_dialect_portrait_all_dialects():
    for d in Dialect:
        result = render_dialect_portrait(d)
        assert len(result) > 50


def test_write_testament(tmp_path):
    content = "# Test testament"
    out_dir = tmp_path / "testament" / "trivium"
    result = write_testament(content, out_dir)
    assert result.exists()
    assert result.read_text() == content
    assert "trivium-synthesis" in result.name


def test_write_testament_creates_dirs(tmp_path):
    deep = tmp_path / "a" / "b" / "c"
    result = write_testament("test", deep)
    assert result.exists()
