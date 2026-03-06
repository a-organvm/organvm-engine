"""Plan file discovery and inventory across the workspace.

Discovers .claude/plans/*.md files at both project and global levels,
extracts metadata from filenames and content, and renders inventories.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

CLAUDE_PLANS_GLOBAL = Path.home() / ".claude" / "plans"
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


@dataclass
class PlanFile:
    """Metadata for a single plan file."""

    path: Path
    project: str  # decoded project path or "global"
    slug: str  # from filename after date
    date: str  # YYYY-MM-DD
    title: str  # first H1 from content
    size_bytes: int
    has_verification: bool  # contains "## Verification" section
    status: str = "unknown"  # annotatable by audit

    @property
    def filename(self) -> str:
        return self.path.name


def discover_plans(
    workspace: Path | None = None,
    project_filter: str | None = None,
    since: str | None = None,
    include_global: bool | None = None,
) -> list[PlanFile]:
    """Find all plan files across workspace and global dirs.

    Args:
        workspace: Workspace root (default ~/Workspace).
        project_filter: Substring filter on project path.
        since: Only include plans on or after this date (YYYY-MM-DD).
        include_global: Include ~/.claude/plans/ and ~/.claude/projects/ plans.
            Default True when workspace is None, False when explicit workspace given.
    """
    results: list[PlanFile] = []

    # When an explicit workspace is provided, skip global dirs by default
    if include_global is None:
        include_global = workspace is None

    # 1. Project-level plans: <workspace>/**/.claude/plans/*.md
    ws = workspace or Path.home() / "Workspace"
    if ws.is_dir():
        for plans_dir in ws.rglob(".claude/plans"):
            if not plans_dir.is_dir():
                continue
            project_path = str(plans_dir.parent.parent)
            if project_filter and project_filter not in project_path:
                continue
            for md in sorted(plans_dir.glob("*.md")):
                plan = _parse_plan_file(md, project_path)
                if plan:
                    results.append(plan)

    # 2. Project plans inside ~/.claude/projects/*/plans/
    if include_global and CLAUDE_PROJECTS_DIR.is_dir():
        for proj_dir in CLAUDE_PROJECTS_DIR.iterdir():
            if not proj_dir.is_dir():
                continue
            plans_dir = proj_dir / "plans"
            if not plans_dir.is_dir():
                continue
            project_path = proj_dir.name
            if project_filter and project_filter not in project_path:
                continue
            for md in sorted(plans_dir.glob("*.md")):
                plan = _parse_plan_file(md, project_path)
                if plan:
                    results.append(plan)

    # 3. Global plans: ~/.claude/plans/*.md
    if include_global and CLAUDE_PLANS_GLOBAL.is_dir():
        for md in sorted(CLAUDE_PLANS_GLOBAL.glob("*.md")):
            plan = _parse_plan_file(md, "global")
            if plan:
                results.append(plan)

    # Apply date filter
    if since:
        results = [p for p in results if p.date >= since]

    # Deduplicate by path
    seen: set[str] = set()
    deduped: list[PlanFile] = []
    for p in results:
        key = str(p.path.resolve())
        if key not in seen:
            seen.add(key)
            deduped.append(p)

    # Sort by date descending
    deduped.sort(key=lambda p: p.date, reverse=True)
    return deduped


_DATE_SLUG_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+?)(?:-v\d+)?\.md$")


def _parse_plan_file(md_path: Path, project: str) -> PlanFile | None:
    """Extract metadata from a plan markdown file."""
    try:
        size = md_path.stat().st_size
    except OSError:
        return None

    # Parse date and slug from filename
    m = _DATE_SLUG_RE.match(md_path.name)
    if m:
        date = m.group(1)
        slug = m.group(2)
    else:
        # Non-dated plan files — use mtime as date
        try:
            mtime = md_path.stat().st_mtime
            from datetime import datetime

            date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
        except OSError:
            date = "unknown"
        slug = md_path.stem

    # Extract title and verification section
    title = ""
    has_verification = False
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            stripped = line.strip()
            if not title and stripped.startswith("# "):
                title = stripped[2:].strip()
            if stripped.lower().startswith("## verification"):
                has_verification = True
            if title and has_verification:
                break
    except OSError:
        pass

    return PlanFile(
        path=md_path,
        project=project,
        slug=slug,
        date=date,
        title=title or slug,
        size_bytes=size,
        has_verification=has_verification,
    )


def render_plan_inventory(plans: list[PlanFile]) -> str:
    """Render a readable inventory of discovered plans."""
    if not plans:
        return "No plan files found."

    lines = [
        f"{'Date':<12} {'Size':>6} {'V':>1} {'Project':<35} {'Title'}",
        "-" * 90,
    ]
    for p in plans:
        size_str = f"{p.size_bytes / 1024:.0f}K" if p.size_bytes >= 1024 else f"{p.size_bytes}B"
        v = "Y" if p.has_verification else " "
        proj = p.project[-35:] if len(p.project) > 35 else p.project
        title = p.title[:40] if len(p.title) > 40 else p.title
        lines.append(f"{p.date:<12} {size_str:>6} {v:>1} {proj:<35} {title}")

    lines.append(f"\n{len(plans)} plans across {len(set(p.project for p in plans))} projects")
    verified = sum(1 for p in plans if p.has_verification)
    lines.append(f"Verification sections: {verified}/{len(plans)}")
    return "\n".join(lines)


def render_plan_audit(plans: list[PlanFile]) -> str:
    """Render a markdown audit scaffold for plan-vs-reality review."""
    if not plans:
        return "No plan files found."

    lines = ["# Plan Audit Report", "", f"Generated from {len(plans)} discovered plans.", ""]

    # Group by project
    by_project: dict[str, list[PlanFile]] = {}
    for p in plans:
        by_project.setdefault(p.project, []).append(p)

    for project, project_plans in sorted(by_project.items()):
        lines.append(f"## {project}")
        lines.append("")
        for p in sorted(project_plans, key=lambda x: x.date, reverse=True):
            lines.append(f"### {p.date} — {p.title}")
            lines.append(f"- **File:** `{p.path}`")
            lines.append(f"- **Slug:** {p.slug}")
            lines.append(f"- **Verification:** {'Yes' if p.has_verification else 'No'}")
            lines.append(f"- **Status:** {p.status}")
            lines.append("- **Reality:** _TODO: cross-reference with git log_")
            lines.append("")

    return "\n".join(lines)
