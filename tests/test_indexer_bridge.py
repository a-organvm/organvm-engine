"""Tests for the indexer → ontologia bridge (G1).

Verifies that atomic components from the deep structural indexer
get registered as MODULE entities in the ontologia structural registry.
"""

from __future__ import annotations

import pytest

from organvm_engine.indexer.bridge import (
    BridgeResult,
    _existing_component_tags,
    _existing_hierarchy_pairs,
    _repo_uid_map,
    register_components,
)
from organvm_engine.indexer.types import Component, RepoIndex, SystemIndex


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_store(tmp_path):
    """Create a minimal ontologia store with a repo entity."""
    from ontologia.entity.identity import EntityType
    from ontologia.registry.store import RegistryStore

    store = RegistryStore(store_dir=tmp_path / "store")
    store.load()

    # Create a repo entity to act as parent
    store.create_entity(
        entity_type=EntityType.REPO,
        display_name="test-repo",
        created_by="test",
        metadata={"name": "test-repo", "org": "test-org", "organ_key": "ORGAN-I"},
    )
    store.save()
    return store


@pytest.fixture()
def sample_system_index():
    """Create a SystemIndex with known components."""
    components = [
        Component(
            repo="test-repo",
            organ="ORGAN-I",
            path="src/core",
            cohesion_type="python_package",
            depth=2,
            file_count=5,
            line_count=200,
            dominant_language="python",
            imports_from=["src/utils"],
        ),
        Component(
            repo="test-repo",
            organ="ORGAN-I",
            path="src/utils",
            cohesion_type="python_package",
            depth=2,
            file_count=3,
            line_count=100,
            dominant_language="python",
        ),
    ]
    repo_index = RepoIndex(
        repo="test-repo",
        organ="ORGAN-I",
        components=components,
        total_files=8,
        total_lines=300,
        max_depth=2,
    )
    return SystemIndex(
        scan_timestamp="2026-03-14T00:00:00Z",
        scanned_repos=1,
        total_components=2,
        repos=[repo_index],
        by_organ={"ORGAN-I": 2},
        by_language={"python": 2},
        by_cohesion={"python_package": 2},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBridgeResult:
    def test_to_dict(self):
        r = BridgeResult(components_created=3, components_skipped=1, edges_created=3)
        d = r.to_dict()
        assert d["components_created"] == 3
        assert d["total_processed"] == 4

    def test_total_processed(self):
        r = BridgeResult(components_created=5, components_skipped=2)
        assert r.total_processed == 7


class TestRegisterComponents:
    def test_creates_module_entities(self, mock_store, sample_system_index):
        result = register_components(sample_system_index, store=mock_store)
        assert result.components_created == 2
        assert result.components_skipped == 0
        assert result.edges_created == 2
        assert not result.errors

    def test_idempotent(self, mock_store, sample_system_index):
        register_components(sample_system_index, store=mock_store)
        # Second run should skip all
        result = register_components(sample_system_index, store=mock_store)
        assert result.components_created == 0
        assert result.components_skipped == 2

    def test_hierarchy_edges_created(self, mock_store, sample_system_index):
        register_components(sample_system_index, store=mock_store)

        edges = list(mock_store.edge_index.all_hierarchy_edges())
        # Should have repo→component edges
        component_edges = [
            e for e in edges
            if e.metadata.get("source") == "indexer-bridge"
        ]
        assert len(component_edges) == 2

    def test_component_metadata_preserved(self, mock_store, sample_system_index):
        register_components(sample_system_index, store=mock_store)

        from ontologia.entity.identity import EntityType

        modules = mock_store.list_entities(entity_type=EntityType.MODULE)
        assert len(modules) == 2

        core_mod = next(m for m in modules if m.metadata["path"] == "src/core")
        assert core_mod.metadata["cohesion_type"] == "python_package"
        assert core_mod.metadata["dominant_language"] == "python"
        assert core_mod.metadata["parent_repo"] == "test-repo"
        assert core_mod.metadata["organ_key"] == "ORGAN-I"
        assert "src/utils" in core_mod.metadata["imports_from"]

    def test_display_name_from_path(self, mock_store, sample_system_index):
        register_components(sample_system_index, store=mock_store)

        from ontologia.entity.identity import EntityType

        modules = mock_store.list_entities(entity_type=EntityType.MODULE)
        names = [mock_store.current_name(m.uid).display_name for m in modules]
        assert "src::core" in names
        assert "src::utils" in names

    def test_no_edge_without_repo_entity(self, tmp_path, sample_system_index):
        """When no repo entity exists, components are created but edges are skipped."""
        from ontologia.registry.store import RegistryStore

        store = RegistryStore(store_dir=tmp_path / "empty-store")
        store.load()

        result = register_components(sample_system_index, store=store)
        assert result.components_created == 2
        assert result.edges_created == 0

    def test_empty_index(self, mock_store):
        empty = SystemIndex()
        result = register_components(empty, store=mock_store)
        assert result.components_created == 0
        assert result.total_processed == 0


class TestHelpers:
    def test_existing_component_tags(self, mock_store, sample_system_index):
        register_components(sample_system_index, store=mock_store)
        tags = _existing_component_tags(mock_store)
        assert "test-repo:src/core" in tags
        assert "test-repo:src/utils" in tags

    def test_repo_uid_map(self, mock_store):
        uids = _repo_uid_map(mock_store)
        assert "test-repo" in uids
        assert uids["test-repo"].startswith("ent_repo_")

    def test_existing_hierarchy_pairs(self, mock_store, sample_system_index):
        register_components(sample_system_index, store=mock_store)
        pairs = _existing_hierarchy_pairs(mock_store)
        assert len(pairs) >= 2
