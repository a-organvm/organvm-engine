"""Multi-agent session discovery and parsing.

Supports Claude Code, Gemini CLI, and Codex session formats.
All three are normalized to a common SessionMeta + rendering pipeline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


# ── Storage locations ──────────────────────────────────────────────

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
GEMINI_TMP_DIR = Path.home() / ".gemini" / "tmp"
CODEX_SESSIONS_DIR = Path.home() / ".codex" / "sessions"
CODEX_ARCHIVED_DIR = Path.home() / ".codex" / "archived_sessions"


# ── Agent enum ─────────────────────────────────────────────────────

AGENTS = ("claude", "gemini", "codex")


@dataclass
class AgentSession:
    """Unified session descriptor across all agents."""

    agent: str  # claude | gemini | codex
    session_id: str
    file_path: Path
    project_dir: str  # decoded project path or best guess
    started: datetime | None
    ended: datetime | None
    size_bytes: int

    @property
    def date_str(self) -> str:
        if self.started:
            return self.started.strftime("%Y-%m-%d")
        return "unknown"

    @property
    def duration_minutes(self) -> int | None:
        if self.started and self.ended:
            delta = self.ended - self.started
            return int(delta.total_seconds() / 60)
        return None

    @property
    def size_human(self) -> str:
        if self.size_bytes >= 1_048_576:
            return f"{self.size_bytes / 1_048_576:.1f}MB"
        if self.size_bytes >= 1024:
            return f"{self.size_bytes / 1024:.0f}KB"
        return f"{self.size_bytes}B"


# ── Discovery ──────────────────────────────────────────────────────


def discover_claude_sessions(project_filter: str | None = None) -> list[AgentSession]:
    """Find all Claude Code sessions."""
    if not CLAUDE_PROJECTS_DIR.exists():
        return []

    results = []
    for proj_dir in CLAUDE_PROJECTS_DIR.iterdir():
        if not proj_dir.is_dir():
            continue
        if project_filter and project_filter not in proj_dir.name:
            continue

        # Read actual cwd from first session file
        decoded_path = _read_cwd_from_claude_project(proj_dir)

        for jsonl in proj_dir.glob("*.jsonl"):
            meta = _quick_parse_claude(jsonl, decoded_path)
            if meta:
                results.append(meta)

    return results


def discover_gemini_sessions(project_filter: str | None = None) -> list[AgentSession]:
    """Find all Gemini CLI sessions."""
    if not GEMINI_TMP_DIR.exists():
        return []

    results = []
    for proj_dir in GEMINI_TMP_DIR.iterdir():
        if not proj_dir.is_dir():
            continue
        chats_dir = proj_dir / "chats"
        if not chats_dir.is_dir():
            continue
        if project_filter and project_filter not in proj_dir.name:
            continue

        for session_file in chats_dir.glob("session-*.json"):
            meta = _quick_parse_gemini(session_file, proj_dir.name)
            if meta:
                results.append(meta)

    return results


def discover_codex_sessions(project_filter: str | None = None) -> list[AgentSession]:
    """Find all Codex sessions (active + archived)."""
    results = []

    # Active sessions: ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl
    if CODEX_SESSIONS_DIR.exists():
        for jsonl in CODEX_SESSIONS_DIR.rglob("rollout-*.jsonl"):
            meta = _quick_parse_codex(jsonl, project_filter)
            if meta:
                results.append(meta)

    # Archived: ~/.codex/archived_sessions/rollout-*.jsonl
    if CODEX_ARCHIVED_DIR.exists():
        for jsonl in CODEX_ARCHIVED_DIR.glob("rollout-*.jsonl"):
            meta = _quick_parse_codex(jsonl, project_filter)
            if meta:
                results.append(meta)

    return results


def discover_all_sessions(
    agent: str | None = None,
    project_filter: str | None = None,
) -> list[AgentSession]:
    """Discover sessions across all agents, sorted newest first."""
    results: list[AgentSession] = []

    if agent is None or agent == "claude":
        results.extend(discover_claude_sessions(project_filter))
    if agent is None or agent == "gemini":
        results.extend(discover_gemini_sessions(project_filter))
    if agent is None or agent == "codex":
        results.extend(discover_codex_sessions(project_filter))

    results.sort(
        key=lambda s: s.started or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return results


# ── Quick parsers (metadata only, no full content scan) ────────────


def _read_cwd_from_claude_project(proj_dir: Path) -> str:
    """Read actual cwd from the first Claude session file."""
    for jsonl in proj_dir.glob("*.jsonl"):
        try:
            with jsonl.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        cwd = msg.get("cwd")
                        if cwd:
                            return cwd
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue
    return proj_dir.name


def _quick_parse_claude(jsonl_path: Path, project_dir: str) -> AgentSession | None:
    """Extract minimal metadata from a Claude JSONL without full parse."""
    try:
        size = jsonl_path.stat().st_size
    except OSError:
        return None

    timestamps: list[datetime] = []
    try:
        with jsonl_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts_str = msg.get("timestamp")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        timestamps.append(ts)
                    except (ValueError, TypeError):
                        pass
                # Only need first and last — stop scanning after we have a few
                # but we need to reach the end for the last timestamp
    except OSError:
        return None

    if not timestamps:
        return None

    return AgentSession(
        agent="claude",
        session_id=jsonl_path.stem,
        file_path=jsonl_path,
        project_dir=project_dir,
        started=min(timestamps),
        ended=max(timestamps),
        size_bytes=size,
    )


def _quick_parse_gemini(session_file: Path, project_slug: str) -> AgentSession | None:
    """Extract minimal metadata from a Gemini session JSON."""
    try:
        size = session_file.stat().st_size
    except OSError:
        return None

    try:
        with session_file.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    session_id = data.get("sessionId", session_file.stem)
    start_str = data.get("startTime")
    end_str = data.get("lastUpdated")

    started = _parse_iso(start_str)
    ended = _parse_iso(end_str)

    return AgentSession(
        agent="gemini",
        session_id=session_id,
        file_path=session_file,
        project_dir=project_slug,
        started=started,
        ended=ended,
        size_bytes=size,
    )


def _quick_parse_codex(jsonl_path: Path, project_filter: str | None) -> AgentSession | None:
    """Extract minimal metadata from a Codex rollout JSONL."""
    try:
        size = jsonl_path.stat().st_size
    except OSError:
        return None

    session_id = ""
    cwd = ""
    started: datetime | None = None
    timestamps: list[datetime] = []

    try:
        with jsonl_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts_str = entry.get("timestamp")
                if ts_str:
                    ts = _parse_iso(ts_str)
                    if ts:
                        timestamps.append(ts)

                if entry.get("type") == "session_meta":
                    payload = entry.get("payload", {})
                    session_id = payload.get("id", jsonl_path.stem)
                    cwd = payload.get("cwd", "")
                    ts_str2 = payload.get("timestamp")
                    if ts_str2:
                        started = _parse_iso(ts_str2)
    except OSError:
        return None

    # Apply project filter on cwd
    if project_filter and project_filter not in cwd:
        return None

    if not timestamps and not started:
        return None

    return AgentSession(
        agent="codex",
        session_id=session_id or jsonl_path.stem,
        file_path=jsonl_path,
        project_dir=cwd or jsonl_path.parent.name,
        started=started or (min(timestamps) if timestamps else None),
        ended=max(timestamps) if timestamps else None,
        size_bytes=size,
    )


def _parse_iso(ts_str: str | None) -> datetime | None:
    """Parse an ISO timestamp string, tolerant of Z suffix."""
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


# ── Summary statistics ─────────────────────────────────────────────


def agent_summary() -> dict[str, dict]:
    """Return per-agent session counts and total size."""
    summary = {}
    for agent in AGENTS:
        if agent == "claude":
            sessions = discover_claude_sessions()
        elif agent == "gemini":
            sessions = discover_gemini_sessions()
        elif agent == "codex":
            sessions = discover_codex_sessions()
        else:
            continue

        total_size = sum(s.size_bytes for s in sessions)
        dates = [s.started for s in sessions if s.started]
        summary[agent] = {
            "count": len(sessions),
            "total_bytes": total_size,
            "total_human": _human_size(total_size),
            "earliest": min(dates).strftime("%Y-%m-%d") if dates else None,
            "latest": max(dates).strftime("%Y-%m-%d") if dates else None,
        }

    return summary


def _human_size(nbytes: int) -> str:
    if nbytes >= 1_073_741_824:
        return f"{nbytes / 1_073_741_824:.1f}GB"
    if nbytes >= 1_048_576:
        return f"{nbytes / 1_048_576:.1f}MB"
    if nbytes >= 1024:
        return f"{nbytes / 1024:.0f}KB"
    return f"{nbytes}B"
