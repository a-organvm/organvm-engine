"""Punch-in/punch-out claim registry for multi-agent coordination.

When an AI stream starts working on a set of files, modules, or organs,
it "punches in" by writing a claim to the shared registry. Other streams
can query the registry to see what areas are currently claimed, and avoid
collisions. When work is done, the stream "punches out" to release its claims.

Claims auto-expire after a configurable TTL (default: 4 hours) to prevent
stale claims from blocking work indefinitely.

The claim registry lives at ~/.organvm/claims.jsonl — a shared, append-only
log. Active claims are computed by reading all entries and filtering by
punch-in/punch-out pairs and TTL expiry.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Default TTL for claims: 4 hours
DEFAULT_CLAIM_TTL_SECONDS = 4 * 60 * 60

_CLAIMS_DIR = Path.home() / ".organvm"
_CLAIMS_FILE = _CLAIMS_DIR / "claims.jsonl"


def _claims_file() -> Path:
    """Return the path to the claims registry file."""
    env = os.environ.get("ORGANVM_CLAIMS_FILE")
    if env:
        return Path(env)
    return _CLAIMS_FILE


@dataclass
class WorkClaim:
    """A claim on an area of influence by an AI stream."""

    claim_id: str
    agent: str  # claude, gemini, codex, human
    session_id: str
    timestamp: float
    organs: list[str] = field(default_factory=list)
    repos: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    scope: str = ""  # free-text description
    ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS
    released: bool = False
    release_timestamp: float = 0.0

    @property
    def is_expired(self) -> bool:
        return time.time() > (self.timestamp + self.ttl_seconds)

    @property
    def is_active(self) -> bool:
        return not self.released and not self.is_expired

    @property
    def areas(self) -> list[str]:
        """All claimed areas as a flat list for display."""
        parts = []
        for o in self.organs:
            parts.append(f"organ:{o}")
        for r in self.repos:
            parts.append(f"repo:{r}")
        for f in self.files:
            parts.append(f"file:{f}")
        for m in self.modules:
            parts.append(f"module:{m}")
        return parts

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "agent": self.agent,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "organs": self.organs,
            "repos": self.repos,
            "files": self.files,
            "modules": self.modules,
            "scope": self.scope,
            "ttl_seconds": self.ttl_seconds,
            "released": self.released,
            "release_timestamp": self.release_timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> WorkClaim:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in known}
        return cls(**filtered)


@dataclass
class ClaimConflict:
    """A detected conflict between a proposed claim and an existing one."""

    existing_claim: WorkClaim
    overlap_type: str  # organ, repo, file, module
    overlap_values: list[str]


def _append_event(event: dict) -> None:
    """Append a JSON event to the claims file."""
    path = _claims_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(event) + "\n")


def _read_events() -> list[dict]:
    """Read all events from the claims file."""
    path = _claims_file()
    if not path.is_file():
        return []
    events = []
    for raw_line in path.read_text().splitlines():
        stripped = raw_line.strip()
        if stripped:
            try:
                events.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue
    return events


def _build_active_claims(events: list[dict]) -> list[WorkClaim]:
    """Build list of active claims from event log."""
    claims: dict[str, WorkClaim] = {}

    for event in events:
        etype = event.get("event_type")
        if etype == "claim.punch_in":
            claim = WorkClaim.from_dict(event)
            claims[claim.claim_id] = claim
        elif etype == "claim.punch_out":
            cid = event.get("claim_id", "")
            if cid in claims:
                claims[cid].released = True
                claims[cid].release_timestamp = event.get("timestamp", time.time())

    return [c for c in claims.values() if c.is_active]


def active_claims() -> list[WorkClaim]:
    """Return all currently active (non-expired, non-released) claims."""
    events = _read_events()
    return _build_active_claims(events)


def check_conflicts(
    organs: list[str] | None = None,
    repos: list[str] | None = None,
    files: list[str] | None = None,
    modules: list[str] | None = None,
) -> list[ClaimConflict]:
    """Check if proposed areas of influence conflict with active claims."""
    conflicts = []
    current = active_claims()

    organs_set = set(organs or [])
    repos_set = set(repos or [])
    files_set = set(files or [])
    modules_set = set(modules or [])

    for claim in current:
        # Check organ overlap
        organ_overlap = organs_set & set(claim.organs)
        if organ_overlap:
            conflicts.append(ClaimConflict(
                existing_claim=claim,
                overlap_type="organ",
                overlap_values=sorted(organ_overlap),
            ))
            continue  # One conflict per claim is enough

        # Check repo overlap
        repo_overlap = repos_set & set(claim.repos)
        if repo_overlap:
            conflicts.append(ClaimConflict(
                existing_claim=claim,
                overlap_type="repo",
                overlap_values=sorted(repo_overlap),
            ))
            continue

        # Check file overlap
        file_overlap = files_set & set(claim.files)
        if file_overlap:
            conflicts.append(ClaimConflict(
                existing_claim=claim,
                overlap_type="file",
                overlap_values=sorted(file_overlap),
            ))
            continue

        # Check module overlap
        module_overlap = modules_set & set(claim.modules)
        if module_overlap:
            conflicts.append(ClaimConflict(
                existing_claim=claim,
                overlap_type="module",
                overlap_values=sorted(module_overlap),
            ))

    return conflicts


def punch_in(
    agent: str,
    session_id: str,
    organs: list[str] | None = None,
    repos: list[str] | None = None,
    files: list[str] | None = None,
    modules: list[str] | None = None,
    scope: str = "",
    ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS,
) -> dict[str, Any]:
    """Punch in: declare areas of influence for this work session.

    Returns a dict with:
    - claim_id: unique ID for this claim (use to punch out)
    - conflicts: any detected conflicts with existing claims
    - active_claims: count of other active claims
    """
    import hashlib

    now = time.time()
    raw = f"{agent}:{session_id}:{now}"
    claim_id = hashlib.sha256(raw.encode()).hexdigest()[:12]

    organs = organs or []
    repos = repos or []
    files = files or []
    modules = modules or []

    # Check for conflicts first
    conflicts = check_conflicts(organs, repos, files, modules)

    event = {
        "event_type": "claim.punch_in",
        "claim_id": claim_id,
        "agent": agent,
        "session_id": session_id,
        "timestamp": now,
        "iso_time": datetime.now(timezone.utc).isoformat(),
        "organs": organs,
        "repos": repos,
        "files": files,
        "modules": modules,
        "scope": scope,
        "ttl_seconds": ttl_seconds,
    }
    _append_event(event)

    return {
        "claim_id": claim_id,
        "conflicts": [
            {
                "with_agent": c.existing_claim.agent,
                "with_session": c.existing_claim.session_id,
                "overlap_type": c.overlap_type,
                "overlap_values": c.overlap_values,
                "claimed_scope": c.existing_claim.scope,
            }
            for c in conflicts
        ],
        "conflict_count": len(conflicts),
        "active_claims": len(active_claims()),
        "areas": [
            *[f"organ:{o}" for o in organs],
            *[f"repo:{r}" for r in repos],
            *[f"file:{f}" for f in files],
            *[f"module:{m}" for m in modules],
        ],
    }


def punch_out(claim_id: str) -> dict[str, Any]:
    """Punch out: release a claim on areas of influence.

    Args:
        claim_id: The claim_id returned from punch_in.

    Returns:
        Dict with release confirmation.
    """
    # Verify claim exists and is active
    events = _read_events()
    claims = _build_active_claims(events)
    found = None
    for c in claims:
        if c.claim_id == claim_id:
            found = c
            break

    if found is None:
        # Check if it was already released or expired
        all_claims: dict[str, WorkClaim] = {}
        for event in events:
            if event.get("event_type") == "claim.punch_in":
                all_claims[event.get("claim_id", "")] = WorkClaim.from_dict(event)

        if claim_id in all_claims:
            claim = all_claims[claim_id]
            if claim.is_expired:
                return {"released": True, "note": "Claim had already expired"}
            return {"released": True, "note": "Claim was already released"}
        return {"error": f"No claim found with id '{claim_id}'"}

    event = {
        "event_type": "claim.punch_out",
        "claim_id": claim_id,
        "timestamp": time.time(),
        "iso_time": datetime.now(timezone.utc).isoformat(),
        "agent": found.agent,
        "session_id": found.session_id,
    }
    _append_event(event)

    return {
        "released": True,
        "claim_id": claim_id,
        "agent": found.agent,
        "areas_released": found.areas,
        "remaining_active": len(active_claims()) - 1,
    }


def work_board() -> dict[str, Any]:
    """Get the current work board — all active claims across all agents.

    This is the "who's working on what" view that any AI stream can query
    before starting work.
    """
    claims = active_claims()

    by_agent: dict[str, list[dict]] = {}
    for c in claims:
        entry = {
            "claim_id": c.claim_id,
            "session_id": c.session_id,
            "scope": c.scope,
            "areas": c.areas,
            "since": datetime.fromtimestamp(c.timestamp, tz=timezone.utc).isoformat(),
            "minutes_active": int((time.time() - c.timestamp) / 60),
            "ttl_remaining_minutes": max(
                0,
                int((c.timestamp + c.ttl_seconds - time.time()) / 60),
            ),
        }
        by_agent.setdefault(c.agent, []).append(entry)

    return {
        "active_claims": len(claims),
        "agents_working": len(by_agent),
        "by_agent": by_agent,
        "claims": [c.to_dict() for c in claims],
    }
