"""Tests for cross-agent work coordination (punch-in/punch-out)."""

from __future__ import annotations

import json
import time
from unittest.mock import patch

import pytest

from organvm_engine.coordination.claims import (
    ClaimConflict,
    WorkClaim,
    _build_active_claims,
    active_claims,
    check_conflicts,
    punch_in,
    punch_out,
    work_board,
)


@pytest.fixture(autouse=True)
def isolated_claims_file(tmp_path, monkeypatch):
    """Route all claims to a temp file."""
    claims_file = tmp_path / "claims.jsonl"
    monkeypatch.setenv("ORGANVM_CLAIMS_FILE", str(claims_file))
    return claims_file


class TestWorkClaim:
    def test_is_active_fresh(self):
        claim = WorkClaim(
            claim_id="abc", agent="claude", session_id="s1",
            timestamp=time.time(), organs=["ORGAN-I"],
        )
        assert claim.is_active
        assert not claim.is_expired
        assert not claim.released

    def test_is_expired(self):
        claim = WorkClaim(
            claim_id="abc", agent="claude", session_id="s1",
            timestamp=time.time() - 20000, ttl_seconds=100,
        )
        assert claim.is_expired
        assert not claim.is_active

    def test_is_released(self):
        claim = WorkClaim(
            claim_id="abc", agent="claude", session_id="s1",
            timestamp=time.time(), released=True,
        )
        assert not claim.is_active

    def test_areas(self):
        claim = WorkClaim(
            claim_id="abc", agent="claude", session_id="s1",
            timestamp=time.time(),
            organs=["ORGAN-I"], repos=["my-repo"],
            files=["src/main.py"], modules=["governance"],
        )
        areas = claim.areas
        assert "organ:ORGAN-I" in areas
        assert "repo:my-repo" in areas
        assert "file:src/main.py" in areas
        assert "module:governance" in areas

    def test_roundtrip(self):
        claim = WorkClaim(
            claim_id="abc", agent="gemini", session_id="s2",
            timestamp=12345.0, organs=["META"],
        )
        d = claim.to_dict()
        restored = WorkClaim.from_dict(d)
        assert restored.claim_id == "abc"
        assert restored.agent == "gemini"
        assert restored.organs == ["META"]


class TestBuildActiveClaims:
    def test_empty(self):
        assert _build_active_claims([]) == []

    def test_punch_in_creates_claim(self):
        events = [
            {
                "event_type": "claim.punch_in",
                "claim_id": "c1", "agent": "claude",
                "session_id": "s1", "timestamp": time.time(),
                "organs": ["ORGAN-I"], "repos": [], "files": [],
                "modules": [], "scope": "test", "ttl_seconds": 14400,
            },
        ]
        claims = _build_active_claims(events)
        assert len(claims) == 1
        assert claims[0].claim_id == "c1"

    def test_punch_out_releases(self):
        now = time.time()
        events = [
            {
                "event_type": "claim.punch_in",
                "claim_id": "c1", "agent": "claude",
                "session_id": "s1", "timestamp": now,
                "organs": [], "repos": [], "files": [],
                "modules": [], "ttl_seconds": 14400,
            },
            {
                "event_type": "claim.punch_out",
                "claim_id": "c1", "timestamp": now + 60,
            },
        ]
        claims = _build_active_claims(events)
        assert len(claims) == 0

    def test_expired_claim_filtered(self):
        events = [
            {
                "event_type": "claim.punch_in",
                "claim_id": "c1", "agent": "claude",
                "session_id": "s1", "timestamp": time.time() - 20000,
                "organs": [], "repos": [], "files": [],
                "modules": [], "ttl_seconds": 100,
            },
        ]
        claims = _build_active_claims(events)
        assert len(claims) == 0


class TestPunchIn:
    def test_basic_punch_in(self):
        result = punch_in(
            agent="claude", session_id="s1",
            organs=["ORGAN-I"], scope="working on theory",
        )
        assert "claim_id" in result
        assert result["conflict_count"] == 0
        assert "organ:ORGAN-I" in result["areas"]

    def test_conflict_detection(self):
        # First punch in
        punch_in(
            agent="claude", session_id="s1",
            repos=["organvm-engine"], scope="engine refactor",
        )
        # Second punch in on same repo
        result = punch_in(
            agent="gemini", session_id="s2",
            repos=["organvm-engine"], scope="engine tests",
        )
        assert result["conflict_count"] == 1
        assert result["conflicts"][0]["with_agent"] == "claude"
        assert result["conflicts"][0]["overlap_type"] == "repo"

    def test_no_conflict_different_areas(self):
        punch_in(
            agent="claude", session_id="s1",
            organs=["ORGAN-I"],
        )
        result = punch_in(
            agent="gemini", session_id="s2",
            organs=["ORGAN-III"],
        )
        assert result["conflict_count"] == 0


class TestPunchOut:
    def test_basic_punch_out(self):
        result = punch_in(
            agent="claude", session_id="s1",
            organs=["ORGAN-I"],
        )
        claim_id = result["claim_id"]
        release = punch_out(claim_id)
        assert release["released"] is True
        assert release["claim_id"] == claim_id

    def test_punch_out_nonexistent(self):
        result = punch_out("nonexistent")
        assert "error" in result

    def test_double_punch_out(self):
        result = punch_in(
            agent="claude", session_id="s1",
            organs=["ORGAN-I"],
        )
        claim_id = result["claim_id"]
        punch_out(claim_id)
        second = punch_out(claim_id)
        assert "already released" in second.get("note", "")

    def test_punch_out_clears_conflict(self):
        r1 = punch_in(agent="claude", session_id="s1", repos=["engine"])
        punch_out(r1["claim_id"])
        r2 = punch_in(agent="gemini", session_id="s2", repos=["engine"])
        assert r2["conflict_count"] == 0


class TestCheckConflicts:
    def test_organ_conflict(self):
        punch_in(agent="claude", session_id="s1", organs=["ORGAN-I"])
        conflicts = check_conflicts(organs=["ORGAN-I"])
        assert len(conflicts) == 1
        assert conflicts[0].overlap_type == "organ"

    def test_file_conflict(self):
        punch_in(agent="claude", session_id="s1", files=["src/main.py"])
        conflicts = check_conflicts(files=["src/main.py", "src/other.py"])
        assert len(conflicts) == 1
        assert "src/main.py" in conflicts[0].overlap_values

    def test_no_conflicts_when_empty(self):
        assert check_conflicts(organs=["ORGAN-I"]) == []


class TestWorkBoard:
    def test_empty_board(self):
        board = work_board()
        assert board["active_claims"] == 0
        assert board["agents_working"] == 0

    def test_board_with_claims(self):
        punch_in(agent="claude", session_id="s1", organs=["ORGAN-I"], scope="theory work")
        punch_in(agent="gemini", session_id="s2", repos=["styx"], scope="research")
        board = work_board()
        assert board["active_claims"] == 2
        assert board["agents_working"] == 2
        assert "claude" in board["by_agent"]
        assert "gemini" in board["by_agent"]

    def test_board_excludes_released(self):
        r = punch_in(agent="claude", session_id="s1", organs=["ORGAN-I"])
        punch_out(r["claim_id"])
        board = work_board()
        assert board["active_claims"] == 0


class TestActiveClaims:
    def test_returns_only_active(self):
        punch_in(agent="claude", session_id="s1", organs=["ORGAN-I"])
        r2 = punch_in(agent="gemini", session_id="s2", organs=["ORGAN-II"])
        punch_out(r2["claim_id"])
        claims = active_claims()
        assert len(claims) == 1
        assert claims[0].agent == "claude"
