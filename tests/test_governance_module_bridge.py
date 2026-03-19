"""Tests for governance module_bridge — excavation→ontologia MODULE entity sync."""

import pytest

from organvm_engine.governance.excavation import BuriedEntity
from organvm_engine.governance.module_bridge import (
    ModuleBridgeResult,
    _module_tag,
    sync_modules_from_excavation,
)


def _sub_package(
    repo: str = "my-repo",
    organ: str = "ORGAN-I",
    path: str = "inner",
    pattern: str = "embedded_app",
    severity: str = "warning",
) -> BuriedEntity:
    return BuriedEntity(
        repo=repo,
        organ=organ,
        entity_path=path,
        entity_type="sub_package",
        evidence=["test"],
        pattern=pattern,
        severity=severity,
    )


class TestModuleTag:
    def test_basic(self):
        assert _module_tag("repo-a", "packages/core") == "repo-a/packages/core"

    def test_uniqueness(self):
        assert _module_tag("repo-a", "x") != _module_tag("repo-b", "x")


class TestSyncModulesFromExcavation:
    @pytest.fixture()
    def store(self, tmp_path):
        """Create a temporary ontologia store with one repo entity."""
        from ontologia.entity.identity import EntityType
        from ontologia.registry.store import RegistryStore

        store_dir = tmp_path / "ontologia"
        store_dir.mkdir()
        store = RegistryStore(store_dir=store_dir)
        store.load()
        # Create a parent repo entity for hierarchy edge testing
        store.create_entity(
            entity_type=EntityType.REPO,
            display_name="my-repo",
            metadata={"name": "my-repo", "org": "organvm-i-theoria", "organ_key": "ORGAN-I"},
        )
        store.save()
        return store

    def test_creates_module_entity(self, store):
        findings = [_sub_package()]
        result = sync_modules_from_excavation(findings, store=store)

        assert result.modules_created == 1
        assert result.modules_skipped == 0

        from ontologia.entity.identity import EntityType

        modules = store.list_entities(entity_type=EntityType.MODULE)
        assert len(modules) == 1
        assert modules[0].metadata["parent_repo"] == "my-repo"
        assert modules[0].metadata["entity_path"] == "inner"
        assert modules[0].metadata["pattern"] == "embedded_app"

    def test_idempotent(self, store):
        findings = [_sub_package()]
        sync_modules_from_excavation(findings, store=store)
        result = sync_modules_from_excavation(findings, store=store)

        assert result.modules_created == 0
        assert result.modules_skipped == 1

    def test_creates_hierarchy_edge(self, store):
        findings = [_sub_package()]
        result = sync_modules_from_excavation(findings, store=store)

        assert result.hierarchy_edges_created == 1
        edges = list(store.edge_index.all_hierarchy_edges())
        # One from organ→repo bootstrap is not here since we created repo directly
        # but there should be at least the repo→module edge
        module_edges = [e for e in edges if "module-bridge" in (e.metadata.get("source", ""))]
        assert len(module_edges) == 1

    def test_unresolved_parent(self, store):
        # Create a finding for a repo not in ontologia
        findings = [_sub_package(repo="nonexistent-repo")]
        result = sync_modules_from_excavation(findings, store=store)

        assert result.modules_created == 1
        assert result.unresolved_parents == 1
        assert result.hierarchy_edges_created == 0

    def test_skips_non_sub_package(self, store):
        # Create a finding that's not a sub_package
        finding = BuriedEntity(
            repo="my-repo",
            organ="ORGAN-I",
            entity_path="governance",
            entity_type="misplaced_governance",
            evidence=["test"],
        )
        result = sync_modules_from_excavation([finding], store=store)

        assert result.modules_created == 0
        assert result.modules_skipped == 0

    def test_empty_findings(self, store):
        result = sync_modules_from_excavation([], store=store)
        assert result.modules_created == 0

    def test_multiple_sub_packages(self, store):
        findings = [
            _sub_package(path="pkg-a", pattern="workspace"),
            _sub_package(path="pkg-b", pattern="embedded_app"),
        ]
        result = sync_modules_from_excavation(findings, store=store)

        assert result.modules_created == 2
        assert result.hierarchy_edges_created == 2

    def test_result_to_dict(self):
        r = ModuleBridgeResult(modules_created=3, modules_skipped=1)
        d = r.to_dict()
        assert d["modules_created"] == 3
        assert d["modules_skipped"] == 1

    def test_preserves_scale_metadata(self, store):
        finding = _sub_package()
        finding.scale = {"files": 12, "lines": 3000}
        result = sync_modules_from_excavation([finding], store=store)

        from ontologia.entity.identity import EntityType

        modules = store.list_entities(entity_type=EntityType.MODULE)
        assert modules[0].metadata["scale"] == {"files": 12, "lines": 3000}
