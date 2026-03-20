"""Tests for trivium testament integration."""

from organvm_engine.testament.manifest import MODULE_SOURCES, ArtifactModality


def test_trivium_in_module_sources():
    assert "trivium" in MODULE_SOURCES


def test_trivium_modality_is_philosophical():
    arts = MODULE_SOURCES["trivium"]
    assert any(a.modality == ArtifactModality.PHILOSOPHICAL for a in arts)


def test_trivium_has_one_artifact_type():
    arts = MODULE_SOURCES["trivium"]
    assert len(arts) == 1


def test_trivium_artifact_source_module():
    art = MODULE_SOURCES["trivium"][0]
    assert art.source_module == "trivium"


def test_trivium_artifact_description():
    art = MODULE_SOURCES["trivium"][0]
    assert "Dialectica" in art.description or "isomorphism" in art.description


def test_dispatch_table_has_trivium_entry():
    from organvm_engine.testament.pipeline import _DISPATCH

    assert ("trivium", "philosophical") in _DISPATCH


def test_isomorphism_data_adapter():
    from organvm_engine.testament.sources import isomorphism_data

    result = isomorphism_data()
    assert isinstance(result, dict)
    assert "total_pairs" in result
    assert result["total_pairs"] == 28
