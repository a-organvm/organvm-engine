"""Tests for ontology.capabilities — SPEC-002, PRIM-007 (Capability)."""

from datetime import datetime, timezone

import pytest

from organvm_engine.ontology.capabilities import (
    CI_PIPELINE,
    DEPLOY,
    GOVERN,
    PREDEFINED_CAPABILITIES,
    PROMOTE,
    PUBLISH,
    Capability,
    CapabilityRegistry,
)


# ---------------------------------------------------------------------------
# Capability dataclass
# ---------------------------------------------------------------------------

class TestCapability:
    def test_create_with_defaults(self):
        cap = Capability(capability_type="DEPLOY", entity_uid="ent_repo_001")
        assert cap.capability_type == "DEPLOY"
        assert cap.entity_uid == "ent_repo_001"
        assert cap.evidence == {}
        assert isinstance(cap.declared_at, datetime)

    def test_create_with_evidence(self):
        evidence = {"workflow_file": ".github/workflows/deploy.yml"}
        cap = Capability(
            capability_type="CI_PIPELINE",
            entity_uid="ent_repo_002",
            evidence=evidence,
        )
        assert cap.evidence == evidence

    def test_frozen(self):
        cap = Capability(capability_type="DEPLOY", entity_uid="ent_001")
        with pytest.raises(AttributeError):
            cap.capability_type = "PUBLISH"  # type: ignore[misc]

    def test_to_dict(self):
        cap = Capability(
            capability_type="DEPLOY",
            entity_uid="ent_001",
            evidence={"key": "val"},
        )
        d = cap.to_dict()
        assert d["capability_type"] == "DEPLOY"
        assert d["entity_uid"] == "ent_001"
        assert d["evidence"] == {"key": "val"}
        assert isinstance(d["declared_at"], str)

    def test_from_dict_roundtrip(self):
        cap = Capability(
            capability_type="PUBLISH",
            entity_uid="ent_003",
            evidence={"channel": "npm"},
        )
        d = cap.to_dict()
        restored = Capability.from_dict(d)
        assert restored.capability_type == cap.capability_type
        assert restored.entity_uid == cap.entity_uid
        assert restored.evidence == cap.evidence

    def test_from_dict_missing_fields(self):
        cap = Capability.from_dict({})
        assert cap.capability_type == ""
        assert cap.entity_uid == ""
        assert cap.evidence == {}

    def test_from_dict_with_datetime_object(self):
        now = datetime.now(timezone.utc)
        cap = Capability.from_dict({
            "capability_type": "GOVERN",
            "entity_uid": "ent_004",
            "declared_at": now,
        })
        assert cap.declared_at == now


# ---------------------------------------------------------------------------
# Predefined types
# ---------------------------------------------------------------------------

class TestPredefinedTypes:
    def test_all_predefined_types_exist(self):
        assert DEPLOY in PREDEFINED_CAPABILITIES
        assert CI_PIPELINE in PREDEFINED_CAPABILITIES
        assert PUBLISH in PREDEFINED_CAPABILITIES
        assert PROMOTE in PREDEFINED_CAPABILITIES
        assert GOVERN in PREDEFINED_CAPABILITIES

    def test_predefined_count(self):
        assert len(PREDEFINED_CAPABILITIES) == 5

    def test_predefined_is_frozenset(self):
        assert isinstance(PREDEFINED_CAPABILITIES, frozenset)


# ---------------------------------------------------------------------------
# CapabilityRegistry — declare
# ---------------------------------------------------------------------------

class TestRegistryDeclare:
    def test_declare_basic(self):
        reg = CapabilityRegistry()
        cap = reg.declare("ent_001", "DEPLOY")
        assert cap.entity_uid == "ent_001"
        assert cap.capability_type == "DEPLOY"
        assert reg.count == 1

    def test_declare_with_evidence(self):
        reg = CapabilityRegistry()
        evidence = {"workflow": "ci.yml"}
        cap = reg.declare("ent_001", "CI_PIPELINE", evidence=evidence)
        assert cap.evidence == evidence

    def test_declare_replaces_existing(self):
        reg = CapabilityRegistry()
        reg.declare("ent_001", "DEPLOY", evidence={"v": 1})
        reg.declare("ent_001", "DEPLOY", evidence={"v": 2})
        caps = reg.query(entity_uid="ent_001", capability_type="DEPLOY")
        assert len(caps) == 1
        assert caps[0].evidence == {"v": 2}
        assert reg.count == 1

    def test_declare_empty_uid_raises(self):
        reg = CapabilityRegistry()
        with pytest.raises(ValueError, match="entity_uid"):
            reg.declare("", "DEPLOY")

    def test_declare_empty_type_raises(self):
        reg = CapabilityRegistry()
        with pytest.raises(ValueError, match="capability_type"):
            reg.declare("ent_001", "")

    def test_declare_multiple_types(self):
        reg = CapabilityRegistry()
        reg.declare("ent_001", "DEPLOY")
        reg.declare("ent_001", "CI_PIPELINE")
        assert reg.count == 2

    def test_declare_multiple_entities(self):
        reg = CapabilityRegistry()
        reg.declare("ent_001", "DEPLOY")
        reg.declare("ent_002", "DEPLOY")
        assert reg.count == 2


# ---------------------------------------------------------------------------
# CapabilityRegistry — revoke
# ---------------------------------------------------------------------------

class TestRegistryRevoke:
    def test_revoke_existing(self):
        reg = CapabilityRegistry()
        reg.declare("ent_001", "DEPLOY")
        assert reg.revoke("ent_001", "DEPLOY") is True
        assert reg.count == 0

    def test_revoke_nonexistent_entity(self):
        reg = CapabilityRegistry()
        assert reg.revoke("ent_999", "DEPLOY") is False

    def test_revoke_nonexistent_type(self):
        reg = CapabilityRegistry()
        reg.declare("ent_001", "DEPLOY")
        assert reg.revoke("ent_001", "PUBLISH") is False
        assert reg.count == 1

    def test_revoke_cleans_empty_entity(self):
        reg = CapabilityRegistry()
        reg.declare("ent_001", "DEPLOY")
        reg.revoke("ent_001", "DEPLOY")
        assert "ent_001" not in reg.entities

    def test_revoke_preserves_other_caps(self):
        reg = CapabilityRegistry()
        reg.declare("ent_001", "DEPLOY")
        reg.declare("ent_001", "CI_PIPELINE")
        reg.revoke("ent_001", "DEPLOY")
        assert reg.count == 1
        assert reg.has_capability("ent_001", "CI_PIPELINE")


# ---------------------------------------------------------------------------
# CapabilityRegistry — query
# ---------------------------------------------------------------------------

class TestRegistryQuery:
    def test_query_all(self):
        reg = CapabilityRegistry()
        reg.declare("ent_001", "DEPLOY")
        reg.declare("ent_002", "PUBLISH")
        results = reg.query()
        assert len(results) == 2

    def test_query_by_entity(self):
        reg = CapabilityRegistry()
        reg.declare("ent_001", "DEPLOY")
        reg.declare("ent_001", "CI_PIPELINE")
        reg.declare("ent_002", "PUBLISH")
        results = reg.query(entity_uid="ent_001")
        assert len(results) == 2
        assert all(c.entity_uid == "ent_001" for c in results)

    def test_query_by_type(self):
        reg = CapabilityRegistry()
        reg.declare("ent_001", "DEPLOY")
        reg.declare("ent_002", "DEPLOY")
        reg.declare("ent_003", "PUBLISH")
        results = reg.query(capability_type="DEPLOY")
        assert len(results) == 2
        assert all(c.capability_type == "DEPLOY" for c in results)

    def test_query_by_entity_and_type(self):
        reg = CapabilityRegistry()
        reg.declare("ent_001", "DEPLOY")
        reg.declare("ent_001", "PUBLISH")
        results = reg.query(entity_uid="ent_001", capability_type="DEPLOY")
        assert len(results) == 1
        assert results[0].capability_type == "DEPLOY"

    def test_query_no_match(self):
        reg = CapabilityRegistry()
        reg.declare("ent_001", "DEPLOY")
        results = reg.query(entity_uid="ent_999")
        assert results == []

    def test_query_empty_registry(self):
        reg = CapabilityRegistry()
        assert reg.query() == []


# ---------------------------------------------------------------------------
# CapabilityRegistry — has_capability
# ---------------------------------------------------------------------------

class TestRegistryHasCapability:
    def test_has_existing(self):
        reg = CapabilityRegistry()
        reg.declare("ent_001", "DEPLOY")
        assert reg.has_capability("ent_001", "DEPLOY") is True

    def test_has_nonexistent(self):
        reg = CapabilityRegistry()
        assert reg.has_capability("ent_001", "DEPLOY") is False


# ---------------------------------------------------------------------------
# CapabilityRegistry — properties and snapshot
# ---------------------------------------------------------------------------

class TestRegistryProperties:
    def test_count_empty(self):
        reg = CapabilityRegistry()
        assert reg.count == 0

    def test_entities_empty(self):
        reg = CapabilityRegistry()
        assert reg.entities == []

    def test_entities_populated(self):
        reg = CapabilityRegistry()
        reg.declare("ent_001", "DEPLOY")
        reg.declare("ent_002", "PUBLISH")
        assert set(reg.entities) == {"ent_001", "ent_002"}

    def test_snapshot_structure(self):
        reg = CapabilityRegistry()
        reg.declare("ent_001", "DEPLOY", evidence={"target": "prod"})
        reg.declare("ent_001", "CI_PIPELINE")
        snap = reg.snapshot()
        assert "ent_001" in snap
        assert len(snap["ent_001"]) == 2
        types = {c["capability_type"] for c in snap["ent_001"]}
        assert types == {"DEPLOY", "CI_PIPELINE"}

    def test_snapshot_empty(self):
        reg = CapabilityRegistry()
        assert reg.snapshot() == {}
