"""Tests for multi-scale relation query (G4).

Verifies the unified graph traversal that spans seed graph (inter-repo),
indexer import graph (intra-repo), and ontologia edges (entity-level).
"""

from __future__ import annotations

import json

import pytest

from organvm_engine.pulse.graph import (
    RelationEdgeDTO,
    RelationMap,
    _gather_indexer_edges,
    _gather_seed_edges,
    query_relations,
)


# ---------------------------------------------------------------------------
# RelationEdgeDTO
# ---------------------------------------------------------------------------


class TestRelationEdgeDTO:
    def test_to_dict(self):
        edge = RelationEdgeDTO(
            source="repo-a",
            target="repo-b",
            relation_type="produces",
            scale="inter_repo",
            metadata={"artifact_type": "schema"},
        )
        d = edge.to_dict()
        assert d["source"] == "repo-a"
        assert d["target"] == "repo-b"
        assert d["relation_type"] == "produces"
        assert d["scale"] == "inter_repo"
        assert d["metadata"]["artifact_type"] == "schema"


# ---------------------------------------------------------------------------
# RelationMap
# ---------------------------------------------------------------------------


class TestRelationMap:
    def test_empty_map(self):
        rmap = RelationMap(entity="test")
        assert rmap.total_edges == 0

    def test_total_edges(self):
        rmap = RelationMap(entity="test")
        rmap.seed_produces.append(
            RelationEdgeDTO("a", "b", "produces", "inter_repo"),
        )
        rmap.imports_from.append(
            RelationEdgeDTO("c", "d", "imports", "intra_repo"),
        )
        rmap.hierarchy_parents.append(
            RelationEdgeDTO("e", "f", "hierarchy", "entity"),
        )
        assert rmap.total_edges == 3

    def test_to_dict_structure(self):
        rmap = RelationMap(entity="test-repo", entity_uid="ent_repo_123")
        rmap.seed_produces.append(
            RelationEdgeDTO("test-repo", "other", "produces", "inter_repo"),
        )
        d = rmap.to_dict()
        assert d["entity"] == "test-repo"
        assert d["entity_uid"] == "ent_repo_123"
        assert d["total_edges"] == 1
        assert len(d["inter_repo"]["produces"]) == 1
        assert d["intra_repo"]["imports_from"] == []
        assert d["entity_level"]["hierarchy_parents"] == []


# ---------------------------------------------------------------------------
# Indexer edge gathering
# ---------------------------------------------------------------------------


class TestGatherIndexerEdges:
    def test_gathers_from_deep_index(self, tmp_path, monkeypatch):
        """Import edges are extracted from cached deep-index.json."""
        index_data = {
            "repos": [
                {
                    "repo": "test-repo",
                    "components": [
                        {
                            "path": "src/core",
                            "imports_from": ["src/utils"],
                            "imported_by": [],
                        },
                        {
                            "path": "src/utils",
                            "imports_from": [],
                            "imported_by": ["src/core"],
                        },
                    ],
                },
            ],
        }

        idx_dir = tmp_path / "corpus" / "data" / "index"
        idx_dir.mkdir(parents=True)
        (idx_dir / "deep-index.json").write_text(json.dumps(index_data))

        monkeypatch.setattr(
            "organvm_engine.paths.corpus_dir",
            lambda: tmp_path / "corpus",
        )

        rmap = RelationMap(entity="test-repo")
        _gather_indexer_edges("test-repo", rmap)

        assert len(rmap.imports_from) == 1
        assert rmap.imports_from[0].target == "src/utils"
        assert len(rmap.imported_by) == 1
        assert rmap.imported_by[0].source == "src/core"

    def test_no_match_returns_empty(self, tmp_path, monkeypatch):
        index_data = {"repos": [{"repo": "other-repo", "components": []}]}
        idx_dir = tmp_path / "corpus" / "data" / "index"
        idx_dir.mkdir(parents=True)
        (idx_dir / "deep-index.json").write_text(json.dumps(index_data))

        monkeypatch.setattr(
            "organvm_engine.paths.corpus_dir",
            lambda: tmp_path / "corpus",
        )

        rmap = RelationMap(entity="nonexistent")
        _gather_indexer_edges("nonexistent", rmap)
        assert rmap.imports_from == []

    def test_missing_index_file_graceful(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "organvm_engine.paths.corpus_dir",
            lambda: tmp_path / "no-such-dir",
        )
        rmap = RelationMap(entity="test")
        _gather_indexer_edges("test", rmap)
        assert rmap.imports_from == []

    def test_component_path_query(self, tmp_path, monkeypatch):
        """Can query by component path, not just repo name."""
        index_data = {
            "repos": [
                {
                    "repo": "test-repo",
                    "components": [
                        {
                            "path": "src/core",
                            "imports_from": ["src/utils"],
                            "imported_by": [],
                        },
                    ],
                },
            ],
        }
        idx_dir = tmp_path / "corpus" / "data" / "index"
        idx_dir.mkdir(parents=True)
        (idx_dir / "deep-index.json").write_text(json.dumps(index_data))

        monkeypatch.setattr(
            "organvm_engine.paths.corpus_dir",
            lambda: tmp_path / "corpus",
        )

        rmap = RelationMap(entity="src/core")
        _gather_indexer_edges("src/core", rmap)
        assert len(rmap.imports_from) == 1


# ---------------------------------------------------------------------------
# Full query_relations
# ---------------------------------------------------------------------------


class TestQueryRelations:
    def test_returns_relation_map(self):
        """query_relations returns a RelationMap even with no data."""
        rmap = query_relations(
            "nonexistent-repo",
            include_seed=False,
            include_indexer=False,
            include_ontologia=False,
        )
        assert isinstance(rmap, RelationMap)
        assert rmap.entity == "nonexistent-repo"
        assert rmap.total_edges == 0

    def test_selective_inclusion(self, tmp_path, monkeypatch):
        """Can disable individual graph sources."""
        monkeypatch.setattr(
            "organvm_engine.paths.corpus_dir",
            lambda: tmp_path / "no-such-dir",
        )
        rmap = query_relations(
            "test",
            include_seed=False,
            include_indexer=True,
            include_ontologia=False,
        )
        assert isinstance(rmap, RelationMap)

    def test_to_dict_serializable(self):
        rmap = query_relations(
            "test",
            include_seed=False,
            include_indexer=False,
            include_ontologia=False,
        )
        d = rmap.to_dict()
        # Should be JSON-serializable
        json_str = json.dumps(d)
        assert "test" in json_str
