"""CLI commands for session transcript management.

Usage:
    organvm session list [--project X] [--limit N]
    organvm session projects
    organvm session show <session-id>
    organvm session export <session-id> --slug <slug> [--output <dir>]
    organvm session transcript <session-id> [--output <file>]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from organvm_engine.session.parser import (
    SessionExport,
    find_session,
    list_projects,
    list_sessions,
    parse_session,
    render_transcript,
)


def cmd_session_projects(args: argparse.Namespace) -> int:
    """List all Claude Code project directories."""
    projects = list_projects()
    if not projects:
        print("No Claude Code projects found.")
        return 0

    print(f"{'Project':<60} {'Sessions':>8}")
    print("-" * 70)
    for p in projects:
        print(f"{p['decoded_path']:<60} {p['session_count']:>8}")

    print(f"\n{len(projects)} projects, {sum(p['session_count'] for p in projects)} total sessions")
    return 0


def cmd_session_list(args: argparse.Namespace) -> int:
    """List sessions with summary metadata."""
    project = getattr(args, "project", None)
    limit = getattr(args, "limit", 20)

    sessions = list_sessions(project)

    if not sessions:
        print("No sessions found.")
        return 0

    if limit:
        sessions = sessions[:limit]

    print(f"{'Date':<12} {'Msgs':>5} {'Dur':>6} {'Branch':<15} {'ID (first 8)':<10} {'First message'}")
    print("-" * 100)
    for s in sessions:
        date = s.date_str
        dur = f"{s.duration_minutes}m" if s.duration_minutes else "?"
        branch = (s.git_branch or "?")[:15]
        short_id = s.session_id[:8]
        preview = s.first_human_message[:50].replace("\n", " ")
        if len(s.first_human_message) > 50:
            preview += "..."
        print(f"{date:<12} {s.message_count:>5} {dur:>6} {branch:<15} {short_id:<10} {preview}")

    shown = len(sessions)
    print(f"\nShowing {shown} sessions" + (f" (use --limit to see more)" if limit and shown == limit else ""))
    return 0


def cmd_session_show(args: argparse.Namespace) -> int:
    """Show detailed metadata for a specific session."""
    session_id = args.session_id
    jsonl_path = find_session(session_id)

    if not jsonl_path:
        print(f"Session not found: {session_id}")
        print("Use 'organvm session list' to see available sessions.")
        return 1

    meta = parse_session(jsonl_path)
    if not meta:
        print(f"Could not parse session: {jsonl_path}")
        return 1

    print(f"Session: {meta.session_id}")
    print(f"Slug:    {meta.slug}")
    print(f"CWD:     {meta.cwd}")
    print(f"Branch:  {meta.git_branch}")
    print(f"Project: {meta.project_dir}")
    print(f"File:    {meta.file_path}")
    print()
    print(f"Started: {meta.started}")
    print(f"Ended:   {meta.ended}")
    dur = f"{meta.duration_minutes} minutes" if meta.duration_minutes else "unknown"
    print(f"Duration: {dur}")
    print()
    print(f"Messages: {meta.message_count} ({meta.human_messages} human, {meta.assistant_messages} assistant)")
    print()

    if meta.tools_used:
        print("Tool usage:")
        for name, count in sorted(meta.tools_used.items(), key=lambda x: x[1], reverse=True):
            print(f"  {name:<30} {count:>4}")

    print()
    print("First human message:")
    print(f"  {meta.first_human_message[:200]}")
    return 0


def cmd_session_export(args: argparse.Namespace) -> int:
    """Export a session as a praxis-perpetua session review."""
    session_id = args.session_id
    slug = args.slug
    output_dir = Path(args.output).expanduser().resolve() if args.output else _default_praxis_sessions()
    dry_run = getattr(args, "dry_run", False)

    jsonl_path = find_session(session_id)
    if not jsonl_path:
        print(f"Session not found: {session_id}")
        print("Use 'organvm session list' to see available sessions.")
        return 1

    meta = parse_session(jsonl_path)
    if not meta:
        print(f"Could not parse session: {jsonl_path}")
        return 1

    filename = f"{meta.date_str}--{slug}.md"
    output_path = output_dir / filename

    export = SessionExport(meta=meta, slug=slug, output_path=output_path)
    content = export.render()

    if dry_run:
        print(f"Would write to: {output_path}")
        print(f"Content length: {len(content)} chars")
        print()
        print(content[:500])
        print("...")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        print(f"File already exists: {output_path}")
        print("Use a different --slug or remove the existing file.")
        return 1

    output_path.write_text(content, encoding="utf-8")
    print(f"Exported session review to: {output_path}")
    print(f"  Session: {meta.session_id}")
    print(f"  Date: {meta.date_str}")
    print(f"  Messages: {meta.message_count}")
    dur = f"{meta.duration_minutes} min" if meta.duration_minutes else "unknown"
    print(f"  Duration: {dur}")
    print()
    print("Next steps:")
    print("  1. Open the file and fill in the TODO sections")
    print("  2. Complete the self-critique phases (inventory, triage, audit, lessons)")
    print("  3. Update lessons/derived-principles.md if new patterns emerged")
    return 0


def cmd_session_transcript(args: argparse.Namespace) -> int:
    """Render full session transcript as readable markdown."""
    session_id = args.session_id
    output = getattr(args, "output", None)

    jsonl_path = find_session(session_id)
    if not jsonl_path:
        print(f"Session not found: {session_id}")
        print("Use 'organvm session list' to see available sessions.")
        return 1

    content = render_transcript(jsonl_path)
    if not content:
        print(f"Could not parse session: {jsonl_path}")
        return 1

    if output:
        out_path = Path(output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        lines = content.count("\n")
        size_kb = len(content.encode("utf-8")) / 1024
        print(f"Transcript written to: {out_path}")
        print(f"  {lines} lines, {size_kb:.0f} KB")
    else:
        print(content)

    return 0


def _default_praxis_sessions() -> Path:
    """Default output directory for session exports."""
    from organvm_engine.paths import workspace_root

    return workspace_root() / "meta-organvm" / "praxis-perpetua" / "sessions"
