"""Tests for ontologia/inference_bridge.py — tension, blast radius, cluster, health.

Uses mocked ontologia internals so tests are deterministic regardless of
whether the real ontologia store has data. Verifies helper serialization,
error paths, and the combined health aggregation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from organvm_engine.ontologia.inference_bridge import (
    HAS_ONTOLOGIA,
    _cluster_to_dict,
    _path_to_dict,
    _tension_to_dict,
    compute_blast_radius,
    detect_entity_clusters,
    detect_tensions,
    infer_health,
)


# ─── Skip guard ───────────────────────────────────────────────────────────

pytestmark = pytest.mark.skipif(
    not HAS_ONTOLOGIA, reason="ontologia package not installed",
)


# ─── Fake ontologia types ────────────────────────────────────────────────

@dataclass
class FakeTensionType:
    value: str


@dataclass
class FakeTension:
    tension_type: FakeTensionType
    entity_ids: list[str]
    severity: float
    description: str


@dataclass
class FakePropPath:
    source_id: str
    target_id: str
    direction: str
    distance: int
    path: list[str]


@dataclass
class FakeCluster:
    entity_ids: list[str]
    cohesion: float
    label: str = ""


@dataclass
class FakeNameRecord:
    display_name: str


@dataclass
class FakeEntityType:
    value: str


@dataclass
class FakeLifecycleStatus:
    value: str


@dataclass
class FakeIdentity:
    uid: str
    entity_type: FakeEntityType
    lifecycle_status: FakeLifecycleStatus
    metadata: dict = field(default_factory=dict)
    created_at: str = "2026-01-01T00:00:00"


@dataclass
class FakeResolved:
    identity: FakeIdentity


class FakeResolver:
    def __init__(self, entities: dict[str, FakeIdentity]):
        self._entities = entities

    def resolve(self, query: str) -> FakeResolved | None:
        ident = self._entities.get(query)
        if ident:
            return FakeResolved(identity=ident)
        return None


class FakeStore:
    def __init__(
        self,
        entities: list[FakeIdentity] | None = None,
        names: dict[str, str] | None = None,
    ):
        self._entity_list = entities or []
        self._names = names or {}
        self._name_index: dict = {}
        self._entities: dict = {e.uid: e for e in self._entity_list}

    @property
    def entity_count(self) -> int:
        return len(self._entity_list)

    def list_entities(self, entity_type=None) -> list[FakeIdentity]:
        if entity_type is None:
            return list(self._entity_list)
        return [e for e in self._entity_list if e.entity_type.value == entity_type]

    def current_name(self, uid: str) -> FakeNameRecord | None:
        name = self._names.get(uid)
        return FakeNameRecord(display_name=name) if name else None

    def resolver(self) -> FakeResolver:
        return FakeResolver({self._names.get(e.uid, e.uid): e for e in self._entity_list})


# ─── Helper serialization tests ──────────────────────────────────────────


class TestTensionToDict:
    def test_basic_serialization(self):
        t = FakeTension(
            tension_type=FakeTensionType("orphan"),
            entity_ids=["uid-1", "uid-2"],
            severity=0.7,
            description="Two orphans detected",
        )
        d = _tension_to_dict(t)
        assert d["type"] == "orphan"
        assert d["severity"] == 0.7
        assert d["entity_ids"] == ["uid-1", "uid-2"]
        assert d["description"] == "Two orphans detected"
        assert "entity_names" not in d

    def test_with_store_resolves_names(self):
        t = FakeTension(
            tension_type=FakeTensionType("naming_conflict"),
            entity_ids=["uid-a"],
            severity=0.3,
            description="Conflict",
        )
        store = FakeStore(names={"uid-a": "my-repo"})
        d = _tension_to_dict(t, store=store)
        assert d["entity_names"] == ["my-repo"]

    def test_with_store_unresolved_uid_falls_back(self):
        t = FakeTension(
            tension_type=FakeTensionType("orphan"),
            entity_ids=["uid-unknown"],
            severity=0.1,
            description="Unknown",
        )
        store = FakeStore(names={})
        d = _tension_to_dict(t, store=store)
        assert d["entity_names"] == ["uid-unknown"]


class TestPathToDict:
    def test_basic_serialization(self):
        p = FakePropPath(
            source_id="src", target_id="tgt",
            direction="downward", distance=2,
            path=["src", "mid", "tgt"],
        )
        d = _path_to_dict(p)
        assert d["target_id"] == "tgt"
        assert d["direction"] == "downward"
        assert d["distance"] == 2
        assert d["path"] == ["src", "mid", "tgt"]
        assert "target_name" not in d

    def test_with_store_resolves_name(self):
        p = FakePropPath(
            source_id="s", target_id="t",
            direction="upward", distance=1, path=["s", "t"],
        )
        store = FakeStore(names={"t": "target-repo"})
        d = _path_to_dict(p, store=store)
        assert d["target_name"] == "target-repo"


class TestClusterToDict:
    def test_basic_serialization(self):
        c = FakeCluster(entity_ids=["e1", "e2", "e3"], cohesion=0.85)
        d = _cluster_to_dict(c)
        assert d["size"] == 3
        assert d["cohesion"] == 0.85
        assert d["entity_ids"] == ["e1", "e2", "e3"]

    def test_with_store(self):
        c = FakeCluster(entity_ids=["e1", "e2"], cohesion=0.5)
        store = FakeStore(names={"e1": "repo-a", "e2": "repo-b"})
        d = _cluster_to_dict(c, store=store)
        assert d["entity_names"] == ["repo-a", "repo-b"]


# ─── detect_tensions (mocked) ────────────────────────────────────────────


class TestDetectTensionsMocked:
    def _mock_store(self):
        organ_e = FakeIdentity(
            uid="org-1",
            entity_type=FakeEntityType("organ"),
            lifecycle_status=FakeLifecycleStatus("active"),
            metadata={"organ_key": "META"},
        )
        repo_e = FakeIdentity(
            uid="repo-1",
            entity_type=FakeEntityType("repo"),
            lifecycle_status=FakeLifecycleStatus("active"),
            metadata={"organ_key": "META"},
        )
        return FakeStore(
            entities=[organ_e, repo_e],
            names={"org-1": "META-ORGANVM", "repo-1": "engine"},
        )

    @patch("organvm_engine.ontologia.inference_bridge.open_store")
    @patch("organvm_engine.ontologia.inference_bridge.detect_orphans", return_value=[])
    @patch("organvm_engine.ontologia.inference_bridge.detect_naming_conflicts", return_value=[])
    @patch("organvm_engine.ontologia.inference_bridge.detect_overcoupling", return_value=[])
    def test_zero_tensions(self, mock_oc, mock_nc, mock_orph, mock_open):
        mock_open.return_value = self._mock_store()
        result = detect_tensions(store_dir="/tmp/fake")
        assert result["total_tensions"] == 0
        assert result["orphans"] == []
        assert result["naming_conflicts"] == []
        assert result["overcoupled"] == []

    @patch("organvm_engine.ontologia.inference_bridge.open_store")
    @patch("organvm_engine.ontologia.inference_bridge.detect_naming_conflicts", return_value=[])
    @patch("organvm_engine.ontologia.inference_bridge.detect_overcoupling", return_value=[])
    @patch("organvm_engine.ontologia.inference_bridge.detect_orphans")
    def test_counts_orphans(self, mock_orph, mock_oc, mock_nc, mock_open):
        mock_open.return_value = self._mock_store()
        mock_orph.return_value = [
            FakeTension(FakeTensionType("orphan"), ["repo-1"], 0.5, "Orphan repo"),
        ]
        result = detect_tensions(store_dir="/tmp/fake")
        assert result["total_tensions"] == 1
        assert len(result["orphans"]) == 1
        assert result["summary"] == "1 orphans, 0 naming conflicts, 0 overcoupled"


# ─── compute_blast_radius (mocked) ───────────────────────────────────────


class TestComputeBlastRadiusMocked:
    @patch("organvm_engine.ontologia.inference_bridge.full_blast_radius")
    @patch("organvm_engine.ontologia.inference_bridge.open_store")
    def test_with_paths(self, mock_open, mock_fbr):
        entity = FakeIdentity(
            uid="r1", entity_type=FakeEntityType("repo"),
            lifecycle_status=FakeLifecycleStatus("active"),
        )
        store = FakeStore(entities=[entity], names={"r1": "engine"})
        mock_open.return_value = store
        mock_fbr.return_value = [
            FakePropPath("r1", "r2", "downward", 1, ["r1", "r2"]),
            FakePropPath("r1", "o1", "upward", 1, ["r1", "o1"]),
        ]

        result = compute_blast_radius("engine", store_dir="/tmp/fake")
        assert result["total_affected"] == 2
        assert len(result["downward"]) == 1
        assert len(result["upward"]) == 1
        assert result["source"]["uid"] == "r1"
        assert result["source"]["name"] == "engine"

    @patch("organvm_engine.ontologia.inference_bridge.open_store")
    def test_entity_not_found(self, mock_open):
        store = FakeStore(entities=[], names={})
        mock_open.return_value = store
        result = compute_blast_radius("nonexistent", store_dir="/tmp/fake")
        assert "error" in result
        assert "not found" in result["error"].lower()


# ─── detect_entity_clusters (mocked) ─────────────────────────────────────


class TestDetectClustersMocked:
    @patch("organvm_engine.ontologia.inference_bridge.detect_clusters_from_relations")
    @patch("organvm_engine.ontologia.inference_bridge.open_store")
    def test_returns_clusters(self, mock_open, mock_detect):
        store = FakeStore(
            entities=[FakeIdentity("e1", FakeEntityType("repo"),
                                   FakeLifecycleStatus("active"))],
            names={"e1": "repo-a"},
        )
        mock_open.return_value = store
        mock_detect.return_value = [
            FakeCluster(entity_ids=["e1", "e2"], cohesion=0.9, label="cluster-1"),
        ]

        result = detect_entity_clusters(store_dir="/tmp/fake")
        assert result["total_clusters"] == 1
        assert result["clusters"][0]["size"] == 2


# ─── infer_health (mocked) ───────────────────────────────────────────────


class TestInferHealthMocked:
    @patch("organvm_engine.ontologia.inference_bridge.detect_entity_clusters")
    @patch("organvm_engine.ontologia.inference_bridge.detect_tensions")
    @patch("organvm_engine.ontologia.inference_bridge.open_store")
    def test_combined_health(self, mock_open, mock_tensions, mock_clusters):
        entity = FakeIdentity(
            uid="r1", entity_type=FakeEntityType("repo"),
            lifecycle_status=FakeLifecycleStatus("active"),
        )
        store = FakeStore(entities=[entity], names={"r1": "engine"})
        mock_open.return_value = store

        mock_tensions.return_value = {
            "orphans": [], "naming_conflicts": [], "overcoupled": [],
            "total_tensions": 0, "summary": "0 orphans, 0 naming, 0 overcoupled",
        }
        mock_clusters.return_value = {
            "clusters": [], "total_clusters": 0,
        }

        result = infer_health(store_dir="/tmp/fake")
        assert result["entity_count"] == 1
        assert "tensions" in result
        assert "clusters" in result

    @patch("organvm_engine.ontologia.inference_bridge.compute_blast_radius")
    @patch("organvm_engine.ontologia.inference_bridge.detect_entity_clusters")
    @patch("organvm_engine.ontologia.inference_bridge.detect_tensions")
    @patch("organvm_engine.ontologia.inference_bridge.open_store")
    def test_with_entity_query_found(self, mock_open, mock_t, mock_c, mock_blast):
        entity = FakeIdentity(
            uid="r1", entity_type=FakeEntityType("repo"),
            lifecycle_status=FakeLifecycleStatus("active"),
        )
        store = FakeStore(entities=[entity], names={"r1": "engine"})
        mock_open.return_value = store
        mock_t.return_value = {"total_tensions": 0}
        mock_c.return_value = {"total_clusters": 0}
        mock_blast.return_value = {"total_affected": 0}

        result = infer_health(store_dir="/tmp/fake", entity_query="engine")
        assert "entity" in result
        assert result["entity"]["uid"] == "r1"
        assert result["entity"]["name"] == "engine"
        assert result["entity"]["type"] == "repo"

    @patch("organvm_engine.ontologia.inference_bridge.detect_entity_clusters")
    @patch("organvm_engine.ontologia.inference_bridge.detect_tensions")
    @patch("organvm_engine.ontologia.inference_bridge.open_store")
    def test_with_entity_query_not_found(self, mock_open, mock_t, mock_c):
        store = FakeStore(entities=[], names={})
        mock_open.return_value = store
        mock_t.return_value = {"total_tensions": 0}
        mock_c.return_value = {"total_clusters": 0}

        result = infer_health(store_dir="/tmp/fake", entity_query="nonexistent")
        assert "entity" in result
        assert "error" in result["entity"]


# ─── Fallback when ontologia unavailable ──────────────────────────────────


class TestOntologiaUnavailable:
    def test_check_returns_error_when_missing(self, monkeypatch):
        from organvm_engine.ontologia import inference_bridge as mod
        monkeypatch.setattr(mod, "HAS_ONTOLOGIA", False)
        result = mod._check()
        assert result is not None
        assert "error" in result

    def test_detect_tensions_returns_error(self, monkeypatch):
        from organvm_engine.ontologia import inference_bridge as mod
        monkeypatch.setattr(mod, "HAS_ONTOLOGIA", False)
        result = mod.detect_tensions()
        assert "error" in result

    def test_compute_blast_radius_returns_error(self, monkeypatch):
        from organvm_engine.ontologia import inference_bridge as mod
        monkeypatch.setattr(mod, "HAS_ONTOLOGIA", False)
        result = mod.compute_blast_radius("anything")
        assert "error" in result

    def test_detect_clusters_returns_error(self, monkeypatch):
        from organvm_engine.ontologia import inference_bridge as mod
        monkeypatch.setattr(mod, "HAS_ONTOLOGIA", False)
        result = mod.detect_entity_clusters()
        assert "error" in result

    def test_infer_health_returns_error(self, monkeypatch):
        from organvm_engine.ontologia import inference_bridge as mod
        monkeypatch.setattr(mod, "HAS_ONTOLOGIA", False)
        result = mod.infer_health()
        assert "error" in result
