"""Tests for organvm_engine.pulse.flow — dependency flow visualization."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest

from organvm_engine.pulse.events import Event, emit
from organvm_engine.pulse.flow import (
    EdgeActivity,
    FlowProfile,
    _event_age_days,
    _node_matches_claim,
    _node_matches_event,
    compute_flow,
    flow_to_dict,
)


@pytest.fixture(autouse=True)
def _isolated_events(tmp_path, monkeypatch):
    """Route the event log to a temp directory."""
    events_file = tmp_path / "events.jsonl"
    monkeypatch.setattr(
        "organvm_engine.pulse.events._events_path",
        lambda: events_file,
    )
    return events_file


@pytest.fixture()
def claims_file(tmp_path, monkeypatch):
    """Route the claims log to a temp directory."""
    path = tmp_path / "claims.jsonl"
    monkeypatch.setattr(
        "organvm_engine.pulse.flow._claims_path",
        lambda: path,
    )
    return path


# ---------------------------------------------------------------------------
# Minimal SeedGraph stand-in
# ---------------------------------------------------------------------------

@dataclass
class MockSeedGraph:
    """Lightweight mock of SeedGraph for testing."""

    nodes: list[str] = field(default_factory=list)
    edges: list[tuple[str, str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# EdgeActivity dataclass
# ---------------------------------------------------------------------------

class TestEdgeActivity:
    def test_creation(self):
        """EdgeActivity holds all fields."""
        ea = EdgeActivity(
            source="orgA/r1",
            target="orgB/r2",
            edge_type="produces",
            activity_level="active",
            recent_events=3,
            last_event_age_days=0.5,
            sessions_touching_both=1,
        )
        assert ea.source == "orgA/r1"
        assert ea.activity_level == "active"
        assert ea.recent_events == 3

    def test_to_dict(self):
        """to_dict serializes all fields."""
        ea = EdgeActivity(
            source="orgA/r1",
            target="orgB/r2",
            edge_type="produces",
            activity_level="dormant",
        )
        d = ea.to_dict()
        assert d["source"] == "orgA/r1"
        assert d["activity_level"] == "dormant"
        assert d["last_event_age_days"] is None


# ---------------------------------------------------------------------------
# FlowProfile dataclass
# ---------------------------------------------------------------------------

class TestFlowProfile:
    def test_empty_profile(self):
        """Empty profile has zero counts and score."""
        fp = FlowProfile()
        assert fp.active_count == 0
        assert fp.flow_score == 0.0
        assert fp.hotspots == []

    def test_to_dict(self):
        """to_dict serializes profile with nested edges."""
        ea = EdgeActivity("a", "b", "produces", "active")
        fp = FlowProfile(
            edges=[ea],
            active_count=1,
            warm_count=0,
            dormant_count=0,
            flow_score=100.0,
            hotspots=["a"],
        )
        d = fp.to_dict()
        assert d["active_count"] == 1
        assert d["flow_score"] == 100.0
        assert len(d["edges"]) == 1
        assert d["hotspots"] == ["a"]


# ---------------------------------------------------------------------------
# Node matching helpers
# ---------------------------------------------------------------------------

class TestNodeMatchesEvent:
    def test_direct_match(self):
        """Direct string match works."""
        assert _node_matches_event("orgA/r1", "orgA/r1") is True

    def test_repo_part_match(self):
        """Node 'orgA/r1' matches source 'r1'."""
        assert _node_matches_event("orgA/r1", "r1") is True

    def test_source_repo_match(self):
        """Bare node 'r1' matches source 'orgA/r1'."""
        assert _node_matches_event("r1", "orgA/r1") is True

    def test_no_match(self):
        """Non-matching strings return False."""
        assert _node_matches_event("orgA/r1", "orgB/r2") is False

    def test_empty_source(self):
        """Empty event source never matches."""
        assert _node_matches_event("orgA/r1", "") is False


class TestNodeMatchesClaim:
    def test_direct_match(self):
        """Claim with matching organ/repo matches."""
        claim = {"organ": "orgA", "repo": "r1"}
        assert _node_matches_claim("orgA/r1", claim) is True

    def test_repo_only_match(self):
        """Node 'orgA/r1' matches claim with repo='r1'."""
        claim = {"organ": "", "repo": "r1"}
        assert _node_matches_claim("orgA/r1", claim) is True

    def test_no_match(self):
        """Non-matching claim returns False."""
        claim = {"organ": "orgB", "repo": "r2"}
        assert _node_matches_claim("orgA/r1", claim) is False

    def test_empty_claim(self):
        """Claim with no organ/repo never matches."""
        claim = {"organ": "", "repo": ""}
        assert _node_matches_claim("orgA/r1", claim) is False


# ---------------------------------------------------------------------------
# Event age calculation
# ---------------------------------------------------------------------------

class TestEventAgeDays:
    def test_recent_event(self):
        """A just-created timestamp has age near zero."""
        ts = datetime.now(timezone.utc).isoformat()
        age = _event_age_days(ts)
        assert age is not None
        assert age < 0.01  # less than ~15 minutes

    def test_old_event(self):
        """A 3-day-old timestamp has age around 3."""
        old = datetime.now(timezone.utc) - timedelta(days=3)
        age = _event_age_days(old.isoformat())
        assert age is not None
        assert 2.9 < age < 3.1

    def test_invalid_timestamp(self):
        """Invalid timestamp returns None."""
        assert _event_age_days("not-a-date") is None

    def test_z_suffix(self):
        """Z-suffix timezone format is handled."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        age = _event_age_days(ts)
        assert age is not None
        assert age < 0.01


# ---------------------------------------------------------------------------
# compute_flow
# ---------------------------------------------------------------------------

class TestComputeFlow:
    def test_empty_graph(self, claims_file):
        """Empty graph produces empty profile with zero score."""
        graph = MockSeedGraph()
        profile = compute_flow(graph, hours=168)
        assert profile.active_count == 0
        assert profile.warm_count == 0
        assert profile.dormant_count == 0
        assert profile.flow_score == 0.0
        assert profile.edges == []

    def test_all_dormant(self, claims_file):
        """Graph with no events or claims has all dormant edges."""
        graph = MockSeedGraph(
            nodes=["orgA/r1", "orgA/r2"],
            edges=[("orgA/r1", "orgA/r2", "produces")],
        )
        profile = compute_flow(graph, hours=168)
        assert profile.dormant_count == 1
        assert profile.active_count == 0
        assert profile.flow_score == 0.0

    def test_active_edge_from_event(self, claims_file):
        """An edge with a recent event is classified as active."""
        emit("registry.updated", "orgA/r1", {"key": "val"})

        graph = MockSeedGraph(
            nodes=["orgA/r1", "orgA/r2"],
            edges=[("orgA/r1", "orgA/r2", "produces")],
        )
        profile = compute_flow(graph, hours=168)
        assert profile.active_count == 1
        assert profile.edges[0].activity_level == "active"
        assert profile.flow_score == 100.0

    def test_warm_edge_from_old_event(self, claims_file, monkeypatch):
        """An edge with an old-but-within-window event is classified as warm."""
        # Emit an event, then make it appear 3 days old
        old_ts = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        ev = Event(
            event_type="registry.updated",
            source="orgA/r1",
            timestamp=old_ts,
        )
        from organvm_engine.pulse.events import _events_path

        path = _events_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(ev.to_json() + "\n")

        graph = MockSeedGraph(
            nodes=["orgA/r1", "orgA/r2"],
            edges=[("orgA/r1", "orgA/r2", "produces")],
        )
        profile = compute_flow(graph, hours=168)
        assert profile.warm_count == 1
        assert profile.edges[0].activity_level == "warm"

    def test_active_edge_from_claim(self, claims_file):
        """An edge with a recent claim on one side is classified as active."""
        ts = datetime.now(timezone.utc).isoformat()
        claim = {
            "agent_id": "claude-forge",
            "organ": "orgA",
            "repo": "r1",
            "action": "punch_in",
            "timestamp": ts,
        }
        claims_file.write_text(json.dumps(claim) + "\n")

        graph = MockSeedGraph(
            nodes=["orgA/r1", "orgA/r2"],
            edges=[("orgA/r1", "orgA/r2", "produces")],
        )
        profile = compute_flow(graph, hours=168)
        assert profile.active_count == 1

    def test_sessions_touching_both(self, claims_file):
        """sessions_touching_both counts agents that claimed both sides."""
        ts = datetime.now(timezone.utc).isoformat()
        claims = [
            {
                "agent_id": "claude-forge",
                "organ": "orgA",
                "repo": "r1",
                "action": "punch_in",
                "timestamp": ts,
            },
            {
                "agent_id": "claude-forge",
                "organ": "orgA",
                "repo": "r2",
                "action": "punch_in",
                "timestamp": ts,
            },
        ]
        claims_file.write_text(
            "\n".join(json.dumps(c) for c in claims) + "\n",
        )

        graph = MockSeedGraph(
            nodes=["orgA/r1", "orgA/r2"],
            edges=[("orgA/r1", "orgA/r2", "produces")],
        )
        profile = compute_flow(graph, hours=168)
        assert profile.edges[0].sessions_touching_both == 1

    def test_mixed_activity_levels(self, claims_file):
        """Graph with mixed event ages produces correct counts."""
        # Active edge: recent event
        emit("registry.updated", "orgA/r1")

        # Warm edge: old event
        old_ts = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        from organvm_engine.pulse.events import _events_path

        path = _events_path()
        ev = Event(event_type="seed.changed", source="orgB/r3", timestamp=old_ts)
        with path.open("a") as f:
            f.write(ev.to_json() + "\n")

        graph = MockSeedGraph(
            nodes=["orgA/r1", "orgA/r2", "orgB/r3", "orgB/r4"],
            edges=[
                ("orgA/r1", "orgA/r2", "produces"),
                ("orgB/r3", "orgB/r4", "consumes"),
                ("orgA/r2", "orgB/r3", "produces"),  # no events
            ],
        )
        profile = compute_flow(graph, hours=168)
        levels = {e.source + "->" + e.target: e.activity_level for e in profile.edges}
        assert levels["orgA/r1->orgA/r2"] == "active"
        assert levels["orgB/r3->orgB/r4"] == "warm"

    def test_flow_score_calculation(self, claims_file):
        """Flow score is computed correctly from active and warm counts."""
        # 2 edges: 1 active (recent event), 1 dormant (no events)
        emit("registry.updated", "orgA/r1")
        graph = MockSeedGraph(
            nodes=["orgA/r1", "orgA/r2", "orgC/r3"],
            edges=[
                ("orgA/r1", "orgA/r2", "produces"),
                ("orgA/r2", "orgC/r3", "consumes"),
            ],
        )
        profile = compute_flow(graph, hours=168)
        # 1 active + 0 warm out of 2 total = (1.0 + 0) / 2 * 100 = 50.0
        assert profile.flow_score == 50.0

    def test_hotspot_detection(self, claims_file):
        """Hotspots are nodes with the most active edges."""
        emit("registry.updated", "orgA/hub")
        graph = MockSeedGraph(
            nodes=["orgA/hub", "orgA/r1", "orgA/r2", "orgA/r3"],
            edges=[
                ("orgA/hub", "orgA/r1", "produces"),
                ("orgA/hub", "orgA/r2", "produces"),
                ("orgA/hub", "orgA/r3", "produces"),
            ],
        )
        profile = compute_flow(graph, hours=168)
        assert "orgA/hub" in profile.hotspots
        # Hub should be first (most active edges)
        assert profile.hotspots[0] == "orgA/hub"


# ---------------------------------------------------------------------------
# flow_to_dict
# ---------------------------------------------------------------------------

class TestFlowToDict:
    def test_serialization(self):
        """flow_to_dict produces valid dict from FlowProfile."""
        ea = EdgeActivity("a", "b", "produces", "dormant")
        fp = FlowProfile(
            edges=[ea],
            active_count=0,
            warm_count=0,
            dormant_count=1,
            flow_score=0.0,
            hotspots=[],
        )
        d = flow_to_dict(fp)
        assert d["dormant_count"] == 1
        assert d["flow_score"] == 0.0
        assert len(d["edges"]) == 1
        assert d["edges"][0]["activity_level"] == "dormant"

    def test_json_serializable(self, claims_file):
        """flow_to_dict output is JSON-serializable."""
        graph = MockSeedGraph(
            nodes=["a", "b"],
            edges=[("a", "b", "produces")],
        )
        profile = compute_flow(graph, hours=168)
        d = flow_to_dict(profile)
        # Should not raise
        raw = json.dumps(d)
        assert isinstance(raw, str)
