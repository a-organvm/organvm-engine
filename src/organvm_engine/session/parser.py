"""Parse Claude Code session transcripts (.jsonl) into structured metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


@dataclass
class SessionMeta:
    """Metadata extracted from a Claude Code session transcript."""

    session_id: str
    file_path: Path
    slug: str
    cwd: str
    git_branch: str
    started: datetime | None
    ended: datetime | None
    message_count: int
    human_messages: int
    assistant_messages: int
    tools_used: dict[str, int]
    first_human_message: str
    project_dir: str

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


def _read_cwd_from_project(proj_dir: Path) -> str:
    """Read actual cwd from the first session file in a project directory.

    The encoded directory name is lossy (hyphens in paths are not escaped),
    so we extract the real path from session metadata.
    """
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
    return proj_dir.name  # fallback to encoded name


def list_projects() -> list[dict]:
    """List all Claude Code project directories with session counts."""
    if not CLAUDE_PROJECTS_DIR.exists():
        return []

    results = []
    for proj_dir in sorted(CLAUDE_PROJECTS_DIR.iterdir()):
        if not proj_dir.is_dir():
            continue
        sessions = list(proj_dir.glob("*.jsonl"))
        if not sessions:
            continue

        decoded = _read_cwd_from_project(proj_dir)
        results.append({
            "project_dir": proj_dir.name,
            "decoded_path": decoded,
            "session_count": len(sessions),
            "path": str(proj_dir),
        })

    return results


def list_sessions(project_dir: str | None = None) -> list[SessionMeta]:
    """List all sessions, optionally filtered to a project directory."""
    if project_dir:
        search_dir = CLAUDE_PROJECTS_DIR / project_dir
        if not search_dir.exists():
            return []
        jsonl_files = sorted(search_dir.glob("*.jsonl"))
    else:
        jsonl_files = sorted(CLAUDE_PROJECTS_DIR.rglob("*.jsonl"))

    results = []
    for f in jsonl_files:
        meta = parse_session(f)
        if meta:
            results.append(meta)

    # Sort by start time, newest first
    results.sort(key=lambda m: m.started or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return results


def parse_session(jsonl_path: Path) -> SessionMeta | None:
    """Parse a session .jsonl file into structured metadata."""
    if not jsonl_path.exists():
        return None

    session_id = jsonl_path.stem
    slug = cwd = git_branch = ""
    project_dir = jsonl_path.parent.name
    timestamps: list[datetime] = []
    human_count = assistant_count = total = 0
    tools: dict[str, int] = {}
    first_human = ""

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

                msg_type = msg.get("type", "")

                # Extract session metadata from first user/assistant message
                if not slug and msg.get("slug"):
                    slug = msg["slug"]
                if not cwd and msg.get("cwd"):
                    cwd = msg["cwd"]
                if not git_branch and msg.get("gitBranch"):
                    git_branch = msg["gitBranch"]

                # Track timestamps
                ts_str = msg.get("timestamp")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        timestamps.append(ts)
                    except (ValueError, TypeError):
                        pass

                if msg_type == "user":
                    total += 1
                    human_count += 1
                    if not first_human:
                        content = msg.get("message", {}).get("content", "")
                        if isinstance(content, str):
                            first_human = content[:300]
                        elif isinstance(content, list):
                            for part in content:
                                if isinstance(part, dict) and part.get("type") == "text":
                                    text = part.get("text", "")
                                    if text and len(text) > 20:
                                        first_human = text[:300]
                                        break

                elif msg_type == "assistant":
                    total += 1
                    assistant_count += 1
                    # Extract tool usage
                    content = msg.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "tool_use":
                                name = block.get("name", "unknown")
                                tools[name] = tools.get(name, 0) + 1

    except OSError:
        return None

    if total == 0:
        return None

    started = min(timestamps) if timestamps else None
    ended = max(timestamps) if timestamps else None

    return SessionMeta(
        session_id=session_id,
        file_path=jsonl_path,
        slug=slug,
        cwd=cwd,
        git_branch=git_branch,
        started=started,
        ended=ended,
        message_count=total,
        human_messages=human_count,
        assistant_messages=assistant_count,
        tools_used=tools,
        first_human_message=first_human,
        project_dir=project_dir,
    )


@dataclass
class SessionExport:
    """A session exported as a praxis-perpetua session review."""

    meta: SessionMeta
    slug: str
    output_path: Path

    def render(self) -> str:
        """Render as a session review markdown file."""
        duration = f"~{self.meta.duration_minutes} min" if self.meta.duration_minutes else "unknown"
        date = self.meta.date_str

        # Top tools
        top_tools = sorted(self.meta.tools_used.items(), key=lambda x: x[1], reverse=True)[:10]
        tools_table = "\n".join(f"| {name} | {count} |" for name, count in top_tools)

        first_msg = self.meta.first_human_message
        if len(first_msg) > 200:
            first_msg = first_msg[:200] + "..."

        return f"""# Session Review: {date} -- {self.slug}

**Date:** {date}
**Agent(s):** Claude Code
**Session ID:** `{self.meta.session_id}`
**Slug:** `{self.meta.slug}`
**Duration:** {duration}
**Working directory:** `{self.meta.cwd}`
**Branch:** `{self.meta.git_branch}`
**Messages:** {self.meta.message_count} ({self.meta.human_messages} human, {self.meta.assistant_messages} assistant)

---

## Opening Prompt

> {first_msg}

---

## Tool Usage

| Tool | Count |
|------|-------|
{tools_table}

---

## Phase I: Inventory

### Goals
- [ ] [TODO: summarize goals from opening prompt]

### Files Produced/Modified
<!-- TODO: fill from git log or session content -->

| File | Action | Repo | Tracked? |
|------|--------|------|----------|
| — | — | — | — |

---

## Phase II: Structural Triage

- [ ] Git tracking: all files tracked
- [ ] File placement: correct repos and directories
- [ ] Naming conventions: followed
- [ ] Data integrity: no protected files modified
- [ ] Cross-references: all links resolve
- [ ] Version integrity: no destructive overwrites

---

## Phase III: Content Audit

| Deliverable | Standard | Compliance | Gaps |
|-------------|----------|------------|------|
| — | — | — | — |

---

## Phase IV: Lessons Extracted

1. [TODO: extract lessons]

---

## Phase V: Reconciliation

- [ ] Structural issues fixed
- [ ] Content gaps expanded
- [ ] Session log written
- [ ] `derived-principles.md` updated
- [ ] Fixes committed

---

## Outcome

**Summary:** [TODO]
**Net quality delta:** [TODO]
"""


def render_transcript(jsonl_path: Path) -> str:
    """Render a full session transcript as readable markdown."""
    meta = parse_session(jsonl_path)
    if not meta:
        return ""

    lines: list[str] = []
    duration = f"~{meta.duration_minutes} min" if meta.duration_minutes else "unknown"

    lines.append(f"# Session Transcript: {meta.date_str}")
    lines.append("")
    lines.append(f"**Session ID:** `{meta.session_id}`")
    lines.append(f"**Slug:** `{meta.slug}`")
    lines.append(f"**Duration:** {duration}")
    lines.append(f"**Working directory:** `{meta.cwd}`")
    lines.append(f"**Branch:** `{meta.git_branch}`")
    lines.append(f"**Messages:** {meta.message_count} ({meta.human_messages} human, {meta.assistant_messages} assistant)")
    lines.append("")
    lines.append("---")
    lines.append("")

    turn = 0
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type", "")

            if msg_type == "user":
                turn += 1
                ts = msg.get("timestamp", "")
                ts_short = ts[:19].replace("T", " ") if ts else ""
                lines.append(f"## [{turn}] Human — {ts_short}")
                lines.append("")

                content = msg.get("message", {}).get("content", "")
                if isinstance(content, str):
                    lines.append(content)
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict):
                            if part.get("type") == "text":
                                lines.append(part.get("text", ""))
                            elif part.get("type") == "tool_result":
                                tool_id = part.get("tool_use_id", "")
                                lines.append(f"*Tool result for `{tool_id}`*")
                                result_content = part.get("content", "")
                                if isinstance(result_content, str):
                                    lines.append(f"```\n{result_content[:2000]}\n```")
                                elif isinstance(result_content, list):
                                    for rc in result_content:
                                        if isinstance(rc, dict) and rc.get("type") == "text":
                                            lines.append(f"```\n{rc.get('text', '')[:2000]}\n```")
                lines.append("")
                lines.append("---")
                lines.append("")

            elif msg_type == "assistant":
                turn += 1
                ts = msg.get("timestamp", "")
                ts_short = ts[:19].replace("T", " ") if ts else ""
                lines.append(f"## [{turn}] Assistant — {ts_short}")
                lines.append("")

                content = msg.get("message", {}).get("content", [])
                if isinstance(content, str):
                    lines.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                lines.append(block.get("text", ""))
                                lines.append("")
                            elif block.get("type") == "tool_use":
                                name = block.get("name", "unknown")
                                inp = block.get("input", {})
                                lines.append(f"**Tool: `{name}`**")
                                # Render key input params concisely
                                if isinstance(inp, dict):
                                    for k, v in inp.items():
                                        v_str = str(v)
                                        if len(v_str) > 500:
                                            v_str = v_str[:500] + "..."
                                        lines.append(f"- `{k}`: {v_str}")
                                lines.append("")
                lines.append("---")
                lines.append("")

    return "\n".join(lines)


def find_session(session_id: str) -> Path | None:
    """Find a session .jsonl by full or partial ID."""
    # Try exact match first
    for jsonl in CLAUDE_PROJECTS_DIR.rglob("*.jsonl"):
        if jsonl.stem == session_id:
            return jsonl

    # Try prefix match
    matches = []
    for jsonl in CLAUDE_PROJECTS_DIR.rglob("*.jsonl"):
        if jsonl.stem.startswith(session_id):
            matches.append(jsonl)

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return None  # Ambiguous

    return None
