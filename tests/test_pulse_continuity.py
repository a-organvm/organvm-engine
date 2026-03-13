"""Tests for organvm_engine.pulse.continuity — session briefing layer."""

from __future__ import annotations

import json

import pytest

from organvm_engine.pulse.continuity import (
    SessionBriefing,
    _active_agents_from_claims,
    _compute_system_delta,
    _extract_key_changes,
    _read_recent_claims,
    briefing_to_markdown,
    build_briefing,
)
from organvm_engine.pulse.events import (
    GATE_CHANGED,
    MOOD_SHIFTED,
    REPO_PROMOTED,
    SESSION_ENDED,
    Event,
    emit,
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
        "organvm_engine.pulse.continuity._claims_path",
        lambda: path,
    )
    return path


# ---------------------------------------------------------------------------
# SessionBriefing dataclass
# ---------------------------------------------------------------------------

class TestSessionBriefing:
    def test_empty_briefing(self):
        """Empty briefing has sensible defaults."""
        b = SessionBriefing()
        assert b.recent_events == []
        assert b.recent_claims == []
        assert b.active_agents == []
        assert b.last_mood is None
        assert b.system_delta == "stable"
        assert b.key_changes == []

    def test_to_dict_empty(self):
        """to_dict works on an empty briefing."""
        b = SessionBriefing()
        d = b.to_dict()
        assert d["system_delta"] == "stable"
        assert d["recent_events"] == []
        assert d["last_mood"] is None

    def test_to_dict_with_mood(self):
        """to_dict includes mood when present."""
        from organvm_engine.pulse.affective import MoodFactors, MoodReading, SystemMood

        mood = MoodReading(mood=SystemMood.GROWING, factors=MoodFactors())
        b = SessionBriefing(last_mood=mood, system_delta="improving")
        d = b.to_dict()
        assert d["last_mood"]["mood"] == "growing"
        assert d["system_delta"] == "improving"

    def test_to_dict_with_events(self):
        """to_dict serializes Event objects in the list."""
        ev = Event(event_type="test.event", source="test")
        b = SessionBriefing(recent_events=[ev])
        d = b.to_dict()
        assert len(d["recent_events"]) == 1
        assert d["recent_events"][0]["event_type"] == "test.event"


# ---------------------------------------------------------------------------
# Claims reading
# ---------------------------------------------------------------------------

class TestReadRecentClaims:
    def test_no_claims_file(self, claims_file):
        """No claims file returns empty list."""
        claims = _read_recent_claims(24)
        assert claims == []

    def test_reads_recent_claims(self, claims_file):
        """Recent claims within the window are returned."""
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).isoformat()
        entry = {
            "agent_id": "claude-forge",
            "organ": "META-ORGANVM",
            "repo": "organvm-engine",
            "action": "punch_in",
            "timestamp": ts,
        }
        claims_file.write_text(json.dumps(entry) + "\n")
        claims = _read_recent_claims(24)
        assert len(claims) == 1
        assert claims[0]["agent_id"] == "claude-forge"

    def test_filters_old_claims(self, claims_file):
        """Claims older than the window are excluded."""
        entry = {
            "agent_id": "claude-forge",
            "action": "punch_in",
            "timestamp": "2020-01-01T00:00:00+00:00",
        }
        claims_file.write_text(json.dumps(entry) + "\n")
        claims = _read_recent_claims(24)
        assert claims == []


# ---------------------------------------------------------------------------
# Active agents detection
# ---------------------------------------------------------------------------

class TestActiveAgents:
    def test_no_claims(self):
        """No claims yields no active agents."""
        assert _active_agents_from_claims([]) == []

    def test_punch_in_only(self):
        """Agent that punched in but not out is active."""
        claims = [{"agent_id": "claude-forge", "action": "punch_in"}]
        assert _active_agents_from_claims(claims) == ["claude-forge"]

    def test_punch_in_and_out(self):
        """Agent that punched in and out is not active."""
        claims = [
            {"agent_id": "claude-forge", "action": "punch_in"},
            {"agent_id": "claude-forge", "action": "punch_out"},
        ]
        assert _active_agents_from_claims(claims) == []

    def test_multiple_agents(self):
        """Multiple agents tracked independently."""
        claims = [
            {"agent_id": "claude-forge", "action": "punch_in"},
            {"agent_id": "gemini-scout", "action": "punch_in"},
            {"agent_id": "claude-forge", "action": "punch_out"},
        ]
        result = _active_agents_from_claims(claims)
        assert result == ["gemini-scout"]


# ---------------------------------------------------------------------------
# System delta computation
# ---------------------------------------------------------------------------

class TestComputeSystemDelta:
    def test_empty_events(self):
        """No events means stable."""
        assert _compute_system_delta([]) == "stable"

    def test_promotions_improve(self):
        """Multiple promotions signal improving."""
        events = [
            Event(event_type=REPO_PROMOTED, source="e", payload={}),
            Event(event_type=REPO_PROMOTED, source="e", payload={}),
            Event(event_type=REPO_PROMOTED, source="e", payload={}),
        ]
        assert _compute_system_delta(events) == "improving"

    def test_gate_downs_decline(self):
        """Multiple gate-down events signal declining."""
        events = [
            Event(
                event_type=GATE_CHANGED,
                source="e",
                payload={"direction": "down"},
            ),
            Event(
                event_type=GATE_CHANGED,
                source="e",
                payload={"direction": "down"},
            ),
            Event(
                event_type=GATE_CHANGED,
                source="e",
                payload={"direction": "down"},
            ),
        ]
        assert _compute_system_delta(events) == "declining"

    def test_balanced_is_stable(self):
        """Equal promotions and regressions cancel out."""
        events = [
            Event(event_type=REPO_PROMOTED, source="e", payload={}),
            Event(
                event_type=GATE_CHANGED,
                source="e",
                payload={"direction": "down"},
            ),
        ]
        assert _compute_system_delta(events) == "stable"


# ---------------------------------------------------------------------------
# Key changes extraction
# ---------------------------------------------------------------------------

class TestExtractKeyChanges:
    def test_promotion_change(self):
        """Promotion events produce change descriptions."""
        events = [
            Event(
                event_type=REPO_PROMOTED,
                source="engine",
                payload={"repo": "my-repo", "new_status": "CANDIDATE"},
            ),
        ]
        changes = _extract_key_changes(events)
        assert len(changes) == 1
        assert "my-repo" in changes[0]
        assert "CANDIDATE" in changes[0]

    def test_mood_shift_change(self):
        """Mood-shifted events produce change descriptions."""
        events = [
            Event(
                event_type=MOOD_SHIFTED,
                source="affective",
                payload={"mood": "THRIVING"},
            ),
        ]
        changes = _extract_key_changes(events)
        assert len(changes) == 1
        assert "THRIVING" in changes[0]

    def test_session_ended_change(self):
        """Session-ended events produce change descriptions."""
        events = [
            Event(
                event_type=SESSION_ENDED,
                source="cli",
                payload={"agent": "claude-forge"},
            ),
        ]
        changes = _extract_key_changes(events)
        assert len(changes) == 1
        assert "claude-forge" in changes[0]

    def test_empty_events(self):
        """No events means no changes."""
        assert _extract_key_changes([]) == []


# ---------------------------------------------------------------------------
# build_briefing integration
# ---------------------------------------------------------------------------

class TestBuildBriefing:
    def test_empty_state(self, claims_file):
        """Briefing from completely empty state."""
        briefing = build_briefing(hours=24)
        assert briefing.system_delta == "stable"
        assert briefing.recent_events == []
        assert briefing.active_agents == []
        assert briefing.last_mood is None

    def test_with_events(self, claims_file):
        """Briefing includes emitted events."""
        emit(REPO_PROMOTED, "engine", {"repo": "r1", "new_status": "CANDIDATE"})
        emit(REPO_PROMOTED, "engine", {"repo": "r2", "new_status": "CANDIDATE"})
        emit(REPO_PROMOTED, "engine", {"repo": "r3", "new_status": "CANDIDATE"})
        briefing = build_briefing(hours=24)
        assert len(briefing.recent_events) == 3
        assert briefing.system_delta == "improving"
        assert len(briefing.key_changes) == 3

    def test_with_mood_event(self, claims_file):
        """Briefing picks up the last mood-shifted event."""
        emit(MOOD_SHIFTED, "affective", {"mood": "growing"})
        briefing = build_briefing(hours=24)
        assert briefing.last_mood is not None
        assert briefing.last_mood.mood.value == "growing"

    def test_with_claims(self, claims_file):
        """Briefing includes active agents from claims."""
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).isoformat()
        entry = {
            "agent_id": "claude-forge",
            "organ": "META-ORGANVM",
            "repo": "engine",
            "action": "punch_in",
            "timestamp": ts,
        }
        claims_file.write_text(json.dumps(entry) + "\n")
        briefing = build_briefing(hours=24)
        assert "claude-forge" in briefing.active_agents


# ---------------------------------------------------------------------------
# briefing_to_markdown
# ---------------------------------------------------------------------------

class TestBriefingToMarkdown:
    def test_empty_briefing(self):
        """Empty briefing produces valid markdown."""
        b = SessionBriefing()
        md = briefing_to_markdown(b)
        assert "## Session Briefing" in md
        assert "Stable" in md

    def test_with_key_changes(self):
        """Markdown includes key changes section."""
        b = SessionBriefing(
            key_changes=["repo-x promoted to CANDIDATE"],
            system_delta="improving",
        )
        md = briefing_to_markdown(b)
        assert "### Recent Changes" in md
        assert "repo-x promoted to CANDIDATE" in md
        assert "Improving" in md

    def test_with_active_agents(self):
        """Markdown includes active agents."""
        b = SessionBriefing(active_agents=["claude-forge", "gemini-scout"])
        md = briefing_to_markdown(b)
        assert "claude-forge" in md
        assert "gemini-scout" in md

    def test_with_events(self):
        """Markdown includes events section."""
        events = [
            Event(event_type="test.event", source="test"),
        ]
        b = SessionBriefing(recent_events=events)
        md = briefing_to_markdown(b)
        assert "### Events" in md
        assert "test.event" in md

    def test_with_mood(self):
        """Markdown includes mood when present."""
        from organvm_engine.pulse.affective import MoodFactors, MoodReading, SystemMood

        mood = MoodReading(mood=SystemMood.THRIVING, factors=MoodFactors())
        b = SessionBriefing(last_mood=mood)
        md = briefing_to_markdown(b)
        assert "thriving" in md

    def test_events_truncation(self):
        """Events beyond 10 show a truncation notice."""
        events = [
            Event(event_type=f"type.{i}", source="test")
            for i in range(15)
        ]
        b = SessionBriefing(recent_events=events)
        md = briefing_to_markdown(b)
        assert "... and 5 more" in md

    def test_claims_in_markdown(self):
        """Markdown includes agent activity claims."""
        claims = [
            {
                "agent_id": "claude-forge",
                "action": "punch_in",
                "organ": "META-ORGANVM",
                "repo": "engine",
                "timestamp": "2026-01-01T00:00:00+00:00",
            },
        ]
        b = SessionBriefing(recent_claims=claims)
        md = briefing_to_markdown(b)
        assert "Agent Activity" in md
        assert "claude-forge" in md
