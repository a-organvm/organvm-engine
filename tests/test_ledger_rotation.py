"""Tests for chain.jsonl rotation and index management (issue #56)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from organvm_engine.events.spine import EventSpine
from organvm_engine.ledger.chain import GENESIS_PREV_HASH, verify_chain
from organvm_engine.ledger.rotation import (
    DEFAULT_MAX_BYTES,
    ChainIndex,
    RotatedSegment,
    all_chain_files,
    load_index,
    needs_rotation,
    rebuild_index,
    rotate_chain,
    save_index,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _emit_events(path: Path, count: int, *, max_chain_bytes: int = 0) -> list:
    """Emit *count* events and return the records."""
    spine = EventSpine(path, max_chain_bytes=max_chain_bytes)
    records = []
    for i in range(count):
        r = spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")
        records.append(r)
    return records


def _chain_byte_size(path: Path) -> int:
    """Return the byte size of the chain file, or 0 if missing."""
    return path.stat().st_size if path.is_file() else 0


# ---------------------------------------------------------------------------
# RotatedSegment / ChainIndex dataclasses
# ---------------------------------------------------------------------------

class TestDataclasses:

    def test_rotated_segment_defaults(self):
        seg = RotatedSegment(filename="chain.20260321-120000.jsonl")
        assert seg.entry_count == 0
        assert seg.first_sequence == -1
        assert seg.last_hash == ""

    def test_chain_index_roundtrip(self, tmp_path):
        seg = RotatedSegment(
            filename="chain.20260321-120000.jsonl",
            entry_count=42,
            first_sequence=0,
            last_sequence=41,
            first_timestamp="2026-03-21T12:00:00+00:00",
            last_timestamp="2026-03-21T12:30:00+00:00",
            last_hash="sha256:abc",
            byte_size=1024,
        )
        idx = ChainIndex(segments=[seg], total_events=42)
        save_index(tmp_path, idx)

        loaded = load_index(tmp_path)
        assert len(loaded.segments) == 1
        assert loaded.segments[0].entry_count == 42
        assert loaded.segments[0].last_hash == "sha256:abc"
        assert loaded.total_events == 42

    def test_load_index_missing_returns_empty(self, tmp_path):
        idx = load_index(tmp_path)
        assert idx.segments == []
        assert idx.total_events == 0

    def test_load_index_corrupt_returns_empty(self, tmp_path):
        (tmp_path / "chain-index.json").write_text("NOT JSON")
        idx = load_index(tmp_path)
        assert idx.segments == []


# ---------------------------------------------------------------------------
# needs_rotation()
# ---------------------------------------------------------------------------

class TestNeedsRotation:

    def test_missing_file(self, tmp_path):
        assert needs_rotation(tmp_path / "chain.jsonl") is False

    def test_small_file(self, tmp_path):
        path = tmp_path / "chain.jsonl"
        path.write_text("small\n")
        assert needs_rotation(path) is False

    def test_over_threshold(self, tmp_path):
        path = tmp_path / "chain.jsonl"
        # Write just over 1 KB with a 1 KB threshold
        path.write_bytes(b"x" * 1025)
        assert needs_rotation(path, max_bytes=1024) is True

    def test_exact_threshold_triggers(self, tmp_path):
        path = tmp_path / "chain.jsonl"
        path.write_bytes(b"x" * 512)
        assert needs_rotation(path, max_bytes=512) is True

    def test_default_threshold_is_100mb(self):
        assert DEFAULT_MAX_BYTES == 100 * 1024 * 1024


# ---------------------------------------------------------------------------
# rotate_chain()
# ---------------------------------------------------------------------------

class TestRotateChain:

    def test_no_rotation_when_under_threshold(self, tmp_path):
        path = tmp_path / "chain.jsonl"
        _emit_events(path, 5, max_chain_bytes=0)
        result = rotate_chain(path, max_bytes=10 * 1024 * 1024)
        assert result is None

    def test_rotation_renames_and_creates_fresh(self, tmp_path):
        path = tmp_path / "chain.jsonl"
        _emit_events(path, 10, max_chain_bytes=0)

        # Use a very small threshold to force rotation
        original_size = path.stat().st_size
        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        seg = rotate_chain(path, max_bytes=1, now=now)

        assert seg is not None
        assert seg.filename == "chain.20260321-120000.jsonl"
        assert seg.entry_count == 10
        assert seg.byte_size == original_size
        assert seg.first_sequence == 0
        assert seg.last_sequence == 9

        # Active file should be empty (freshly created)
        assert path.is_file()
        assert path.stat().st_size == 0

        # Rotated file should exist
        rotated = tmp_path / "chain.20260321-120000.jsonl"
        assert rotated.is_file()
        assert rotated.stat().st_size == original_size

    def test_rotation_updates_index(self, tmp_path):
        path = tmp_path / "chain.jsonl"
        _emit_events(path, 5, max_chain_bytes=0)

        now = datetime(2026, 3, 21, 14, 30, 0, tzinfo=timezone.utc)
        rotate_chain(path, max_bytes=1, now=now)

        idx = load_index(tmp_path)
        assert len(idx.segments) == 1
        assert idx.segments[0].entry_count == 5
        assert idx.total_events == 5

    def test_collision_avoidance(self, tmp_path):
        """Two rotations at the same timestamp should not collide."""
        path = tmp_path / "chain.jsonl"
        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)

        _emit_events(path, 3, max_chain_bytes=0)
        rotate_chain(path, max_bytes=1, now=now)

        _emit_events(path, 3, max_chain_bytes=0)
        seg = rotate_chain(path, max_bytes=1, now=now)

        assert seg is not None
        assert seg.filename == "chain.20260321-120000-1.jsonl"

        idx = load_index(tmp_path)
        assert len(idx.segments) == 2

    def test_rotation_preserves_chain_integrity(self, tmp_path):
        """Events across rotation boundary should form a valid chain."""
        path = tmp_path / "chain.jsonl"

        # Emit 5 events, rotate, emit 5 more
        _emit_events(path, 5, max_chain_bytes=0)
        rotate_chain(path, max_bytes=1, now=datetime(2026, 1, 1, tzinfo=timezone.utc))

        # Emit 5 more — spine must continue sequence from index
        spine = EventSpine(path, max_chain_bytes=0)
        r = spine.emit(event_type="test", entity_uid="e5", actor="t")
        assert r.sequence == 5  # continues from 0-4

        for i in range(6, 10):
            spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")

        # Verify across all files
        result = verify_chain(path)
        assert result.valid is True
        assert result.event_count == 10
        assert result.last_sequence == 9


# ---------------------------------------------------------------------------
# Auto-rotation in EventSpine.emit()
# ---------------------------------------------------------------------------

class TestAutoRotation:

    def test_auto_rotation_on_emit(self, tmp_path):
        """EventSpine auto-rotates when chain exceeds max_chain_bytes."""
        path = tmp_path / "chain.jsonl"

        # Use a tiny threshold: each event is roughly 300-400 bytes,
        # so a 500-byte threshold should trigger rotation after ~1-2 events.
        spine = EventSpine(path, max_chain_bytes=500)
        records = []
        for i in range(10):
            r = spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")
            records.append(r)

        # Should have rotated at least once
        rotated_files = sorted(tmp_path.glob("chain.*.jsonl"))
        assert len(rotated_files) >= 1, "Expected at least one rotated segment"

        # All events should form a valid chain across segments
        result = verify_chain(path)
        assert result.valid is True
        assert result.event_count == 10
        assert result.last_sequence == 9

    def test_auto_rotation_disabled_with_zero(self, tmp_path):
        """max_chain_bytes=0 disables auto-rotation."""
        path = tmp_path / "chain.jsonl"
        spine = EventSpine(path, max_chain_bytes=0)
        for i in range(10):
            spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")

        rotated = list(tmp_path.glob("chain.*.jsonl"))
        assert len(rotated) == 0

    def test_rotation_chain_continuity(self, tmp_path):
        """Sequences and prev_hash are continuous across rotation boundaries."""
        path = tmp_path / "chain.jsonl"

        # Threshold of 1 byte = rotate after every event
        spine = EventSpine(path, max_chain_bytes=1)
        prev_hash = GENESIS_PREV_HASH
        for i in range(5):
            r = spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")
            assert r.sequence == i, f"Event {i} should have sequence {i}"
            assert r.prev_hash == prev_hash, f"Event {i} prev_hash mismatch"
            prev_hash = r.hash


# ---------------------------------------------------------------------------
# rebuild_index()
# ---------------------------------------------------------------------------

class TestRebuildIndex:

    def test_rebuild_from_scratch(self, tmp_path):
        path = tmp_path / "chain.jsonl"
        _emit_events(path, 5, max_chain_bytes=0)
        rotate_chain(path, max_bytes=1, now=datetime(2026, 1, 1, tzinfo=timezone.utc))

        _emit_events(path, 3, max_chain_bytes=0)
        rotate_chain(path, max_bytes=1, now=datetime(2026, 1, 2, tzinfo=timezone.utc))

        _emit_events(path, 2, max_chain_bytes=0)

        # Delete existing index
        idx_path = tmp_path / "chain-index.json"
        if idx_path.exists():
            idx_path.unlink()

        # Rebuild
        idx = rebuild_index(tmp_path)
        assert len(idx.segments) == 2
        assert idx.segments[0].entry_count == 5
        assert idx.segments[1].entry_count == 3
        assert idx.total_events == 10  # 5 + 3 + 2 active

    def test_rebuild_empty_dir(self, tmp_path):
        idx = rebuild_index(tmp_path)
        assert idx.segments == []
        assert idx.total_events == 0

    def test_rebuild_with_only_active_file(self, tmp_path):
        path = tmp_path / "chain.jsonl"
        _emit_events(path, 7, max_chain_bytes=0)

        idx = rebuild_index(tmp_path)
        assert len(idx.segments) == 0
        assert idx.total_events == 7


# ---------------------------------------------------------------------------
# all_chain_files()
# ---------------------------------------------------------------------------

class TestAllChainFiles:

    def test_only_active_file(self, tmp_path):
        path = tmp_path / "chain.jsonl"
        path.write_text('{"test": true}\n')
        files = all_chain_files(tmp_path)
        assert len(files) == 1
        assert files[0].name == "chain.jsonl"

    def test_rotated_plus_active(self, tmp_path):
        (tmp_path / "chain.20260101-000000.jsonl").write_text('{"a": 1}\n')
        (tmp_path / "chain.20260102-000000.jsonl").write_text('{"b": 2}\n')
        (tmp_path / "chain.jsonl").write_text('{"c": 3}\n')

        files = all_chain_files(tmp_path)
        assert len(files) == 3
        # Rotated files first (sorted), active last
        assert files[0].name == "chain.20260101-000000.jsonl"
        assert files[1].name == "chain.20260102-000000.jsonl"
        assert files[2].name == "chain.jsonl"

    def test_empty_active_excluded(self, tmp_path):
        """Empty active file is NOT included (nothing to verify)."""
        (tmp_path / "chain.20260101-000000.jsonl").write_text('{"a": 1}\n')
        (tmp_path / "chain.jsonl").touch()  # empty
        files = all_chain_files(tmp_path)
        assert len(files) == 1
        assert files[0].name == "chain.20260101-000000.jsonl"

    def test_no_files(self, tmp_path):
        files = all_chain_files(tmp_path)
        assert files == []


# ---------------------------------------------------------------------------
# verify_chain() across rotation boundaries
# ---------------------------------------------------------------------------

class TestVerifyChainAcrossRotations:

    def test_verify_rotated_chain(self, tmp_path):
        """verify_chain walks rotated segments then active file."""
        path = tmp_path / "chain.jsonl"

        # Build a valid chain, rotate, add more events
        _emit_events(path, 5, max_chain_bytes=0)
        rotate_chain(path, max_bytes=1, now=datetime(2026, 1, 1, tzinfo=timezone.utc))

        spine = EventSpine(path, max_chain_bytes=0)
        for i in range(5, 10):
            spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")

        result = verify_chain(path)
        assert result.valid is True
        assert result.event_count == 10
        assert result.last_sequence == 9

    def test_verify_detects_tampering_in_rotated_segment(self, tmp_path):
        """Tampering with a rotated segment is detected."""
        path = tmp_path / "chain.jsonl"
        _emit_events(path, 5, max_chain_bytes=0)

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rotate_chain(path, max_bytes=1, now=now)

        # Tamper with the rotated file
        rotated = tmp_path / "chain.20260101-000000.jsonl"
        lines = rotated.read_text().splitlines()
        event = json.loads(lines[2])
        event["payload"]["tampered"] = True
        lines[2] = json.dumps(event, separators=(",", ":"))
        rotated.write_text("\n".join(lines) + "\n")

        result = verify_chain(path)
        assert result.valid is False
        assert any("hash mismatch" in e.lower() for e in result.errors)

    def test_verify_with_no_chain_files(self, tmp_path):
        """Non-existent path still returns valid empty result."""
        result = verify_chain(tmp_path / "chain.jsonl")
        assert result.valid is True
        assert result.event_count == 0

    def test_verify_with_only_rotated_no_active(self, tmp_path):
        """If active file is empty, only rotated segments are verified."""
        path = tmp_path / "chain.jsonl"
        _emit_events(path, 5, max_chain_bytes=0)
        rotate_chain(path, max_bytes=1, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
        # Active file is now empty
        assert path.stat().st_size == 0

        result = verify_chain(path)
        assert result.valid is True
        assert result.event_count == 5


# ---------------------------------------------------------------------------
# Multiple rotation cycles (stress test)
# ---------------------------------------------------------------------------

class TestMultipleRotations:

    def test_three_rotation_cycles(self, tmp_path):
        """Three rounds of emit+rotate produce a valid 15-event chain."""
        path = tmp_path / "chain.jsonl"
        all_records = []

        for cycle in range(3):
            spine = EventSpine(path, max_chain_bytes=0)
            for i in range(5):
                r = spine.emit(
                    event_type="test",
                    entity_uid=f"c{cycle}_e{i}",
                    actor="t",
                )
                all_records.append(r)
            rotate_chain(
                path,
                max_bytes=1,
                now=datetime(2026, 1, cycle + 1, tzinfo=timezone.utc),
            )

        # Emit a final batch without rotation
        spine = EventSpine(path, max_chain_bytes=0)
        for i in range(5):
            r = spine.emit(event_type="test", entity_uid=f"final_{i}", actor="t")
            all_records.append(r)

        assert len(all_records) == 20

        result = verify_chain(path)
        assert result.valid is True
        assert result.event_count == 20
        assert result.last_sequence == 19

        idx = load_index(tmp_path)
        assert len(idx.segments) == 3
