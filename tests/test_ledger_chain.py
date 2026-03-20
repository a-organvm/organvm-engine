"""Tests for the Testament Protocol chain operations."""

from __future__ import annotations

import json

from organvm_engine.ledger.chain import (
    GENESIS_PREV_HASH,
    ChainVerificationResult,
    compute_event_hash,
    verify_chain,
    verify_chain_link,
    verify_hash,
)


class TestHashComputation:

    def test_compute_hash_deterministic(self):
        event = {
            "event_id": "test-001",
            "sequence": 0,
            "timestamp": "2026-03-19T00:00:00+00:00",
            "event_type": "testament.genesis",
            "source_organ": "META-ORGANVM",
            "source_repo": "organvm-engine",
            "entity_uid": "",
            "actor": "human:4jp",
            "payload": {},
            "source_spec": "",
            "causal_predecessor": "",
            "prev_hash": GENESIS_PREV_HASH,
        }
        h1 = compute_event_hash(event)
        h2 = compute_event_hash(event)
        assert h1 == h2
        assert h1.startswith("sha256:")
        assert len(h1) == 71  # "sha256:" + 64 hex chars

    def test_compute_hash_excludes_hash_field(self):
        event = {
            "event_id": "test-001",
            "sequence": 0,
            "timestamp": "2026-03-19T00:00:00+00:00",
            "event_type": "test",
            "prev_hash": GENESIS_PREV_HASH,
        }
        h1 = compute_event_hash(event)
        event_with_hash = {**event, "hash": "sha256:bogus"}
        h2 = compute_event_hash(event_with_hash)
        assert h1 == h2

    def test_any_field_change_changes_hash(self):
        base = {
            "event_id": "test-001",
            "sequence": 0,
            "timestamp": "2026-03-19T00:00:00+00:00",
            "event_type": "test",
            "prev_hash": GENESIS_PREV_HASH,
        }
        h_base = compute_event_hash(base)
        for key in base:
            modified = {**base, key: "MODIFIED"}
            assert compute_event_hash(modified) != h_base, (
                f"Changing {key} should change hash"
            )

    def test_verify_hash_valid(self):
        event = {
            "event_id": "test-001",
            "sequence": 0,
            "timestamp": "2026-03-19T00:00:00+00:00",
            "event_type": "test",
            "prev_hash": GENESIS_PREV_HASH,
        }
        event["hash"] = compute_event_hash(event)
        assert verify_hash(event) is True

    def test_verify_hash_tampered(self):
        event = {
            "event_id": "test-001",
            "sequence": 0,
            "timestamp": "2026-03-19T00:00:00+00:00",
            "event_type": "test",
            "prev_hash": GENESIS_PREV_HASH,
            "hash": "sha256:" + "0" * 64,
        }
        assert verify_hash(event) is False

    def test_verify_hash_empty_returns_false(self):
        assert verify_hash({"hash": ""}) is False
        assert verify_hash({}) is False

    def test_genesis_prev_hash_is_all_zeros(self):
        assert GENESIS_PREV_HASH == "sha256:" + "0" * 64

    def test_verify_chain_link(self):
        prev = {"hash": "sha256:abc123"}
        curr = {"prev_hash": "sha256:abc123"}
        assert verify_chain_link(prev, curr) is True

    def test_verify_chain_link_broken(self):
        prev = {"hash": "sha256:abc123"}
        curr = {"prev_hash": "sha256:different"}
        assert verify_chain_link(prev, curr) is False


class TestChainVerification:

    def test_verify_empty_chain(self, tmp_path):
        result = verify_chain(tmp_path / "empty.jsonl")
        assert result.valid is True
        assert result.event_count == 0

    def test_verify_nonexistent_file(self, tmp_path):
        result = verify_chain(tmp_path / "nope.jsonl")
        assert result.valid is True
        assert result.event_count == 0

    def test_verify_valid_chain(self, tmp_path):
        from organvm_engine.events.spine import EventSpine

        spine = EventSpine(tmp_path / "events.jsonl")
        for i in range(10):
            spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")
        result = verify_chain(tmp_path / "events.jsonl")
        assert result.valid is True
        assert result.event_count == 10
        assert result.errors == []

    def test_detect_tampered_hash(self, tmp_path):
        from organvm_engine.events.spine import EventSpine

        spine = EventSpine(tmp_path / "events.jsonl")
        for i in range(5):
            spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")

        lines = (tmp_path / "events.jsonl").read_text().splitlines()
        event = json.loads(lines[2])
        event["payload"]["tampered"] = True
        lines[2] = json.dumps(event, separators=(",", ":"))
        (tmp_path / "events.jsonl").write_text("\n".join(lines) + "\n")

        result = verify_chain(tmp_path / "events.jsonl")
        assert result.valid is False
        assert len(result.errors) >= 1
        assert any("hash mismatch" in e.lower() for e in result.errors)

    def test_detect_broken_chain_link(self, tmp_path):
        from organvm_engine.events.spine import EventSpine

        spine = EventSpine(tmp_path / "events.jsonl")
        for i in range(5):
            spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")

        lines = (tmp_path / "events.jsonl").read_text().splitlines()
        event = json.loads(lines[3])
        event["prev_hash"] = "sha256:" + "f" * 64
        event["hash"] = compute_event_hash(event)
        lines[3] = json.dumps(event, separators=(",", ":"))
        (tmp_path / "events.jsonl").write_text("\n".join(lines) + "\n")

        result = verify_chain(tmp_path / "events.jsonl")
        assert result.valid is False
        assert any("chain link" in e.lower() for e in result.errors)

    def test_result_tracks_last_sequence_and_hash(self, tmp_path):
        from organvm_engine.events.spine import EventSpine

        spine = EventSpine(tmp_path / "events.jsonl")
        records = [spine.emit(event_type="test", entity_uid="e", actor="t") for _ in range(3)]
        result = verify_chain(tmp_path / "events.jsonl")
        assert result.last_sequence == 2
        assert result.last_hash == records[-1].hash
