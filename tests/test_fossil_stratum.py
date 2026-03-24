"""Tests for fossil stratum data models."""

from datetime import datetime, timezone

from organvm_engine.fossil.stratum import (
    Archetype,
    FossilRecord,
    Provenance,
    compute_record_hash,
    deserialize_record,
    serialize_record,
)


def test_archetype_enum_has_eight_members():
    assert len(Archetype) == 8
    assert Archetype.SHADOW in Archetype
    assert Archetype.ANIMA in Archetype
    assert Archetype.ANIMUS in Archetype
    assert Archetype.SELF in Archetype
    assert Archetype.TRICKSTER in Archetype
    assert Archetype.MOTHER in Archetype
    assert Archetype.FATHER in Archetype
    assert Archetype.INDIVIDUATION in Archetype


def test_provenance_enum():
    assert Provenance.WITNESSED.value == "witnessed"
    assert Provenance.RECONSTRUCTED.value == "reconstructed"
    assert Provenance.ATTESTED.value == "attested"


def test_fossil_record_creation():
    record = FossilRecord(
        commit_sha="abc1234",
        timestamp=datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc),
        author="test",
        organ="META",
        repo="organvm-engine",
        message="feat: add omega criterion #19",
        conventional_type="feat",
        files_changed=3,
        insertions=120,
        deletions=5,
        archetypes=[Archetype.SELF, Archetype.ANIMUS],
        provenance=Provenance.RECONSTRUCTED,
        session_id=None,
        epoch=None,
        tags=["omega", "testament"],
        prev_hash="",
    )
    assert record.organ == "META"
    assert record.archetypes[0] == Archetype.SELF


def test_serialize_deserialize_roundtrip():
    record = FossilRecord(
        commit_sha="abc1234",
        timestamp=datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc),
        author="test",
        organ="I",
        repo="recursive-engine",
        message="fix: lint errors",
        conventional_type="fix",
        files_changed=1,
        insertions=2,
        deletions=2,
        archetypes=[Archetype.SHADOW],
        provenance=Provenance.RECONSTRUCTED,
        session_id="S28",
        epoch="EPOCH-011",
        tags=["lint"],
        prev_hash="0000",
    )
    json_str = serialize_record(record)
    restored = deserialize_record(json_str)
    assert restored.commit_sha == record.commit_sha
    assert restored.archetypes == record.archetypes
    assert restored.timestamp == record.timestamp


def test_hash_linking():
    r1 = FossilRecord(
        commit_sha="aaa",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        author="test", organ="I", repo="test-repo",
        message="first", conventional_type="feat",
        files_changed=1, insertions=1, deletions=0,
        archetypes=[Archetype.ANIMA],
        provenance=Provenance.RECONSTRUCTED,
        session_id=None, epoch=None, tags=[], prev_hash="",
    )
    h1 = compute_record_hash(r1)
    assert len(h1) == 64  # SHA256 hex

    r2 = FossilRecord(
        commit_sha="bbb",
        timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
        author="test", organ="I", repo="test-repo",
        message="second", conventional_type="fix",
        files_changed=1, insertions=1, deletions=1,
        archetypes=[Archetype.SHADOW],
        provenance=Provenance.RECONSTRUCTED,
        session_id=None, epoch=None, tags=[], prev_hash=h1,
    )
    h2 = compute_record_hash(r2)
    assert h2 != h1
    assert r2.prev_hash == h1
