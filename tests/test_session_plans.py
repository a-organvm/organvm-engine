"""Tests for session plan discovery and inventory."""

import textwrap
from pathlib import Path

import pytest

from organvm_engine.session.plans import (
    PlanFile,
    _parse_plan_file,
    discover_plans,
    render_plan_audit,
    render_plan_inventory,
)


# ── PlanFile dataclass ────────────────────────────────────────────


def test_planfile_filename():
    pf = PlanFile(
        path=Path("/tmp/plans/2026-03-06-my-plan.md"),
        project="test", slug="my-plan", date="2026-03-06",
        title="My Plan", size_bytes=1024, has_verification=False,
    )
    assert pf.filename == "2026-03-06-my-plan.md"


def test_planfile_defaults():
    pf = PlanFile(
        path=Path("/tmp/x.md"), project="p", slug="s", date="2026-01-01",
        title="T", size_bytes=0, has_verification=True,
    )
    assert pf.status == "unknown"
    assert pf.has_verification is True


# ── _parse_plan_file ──────────────────────────────────────────────


def test_parse_dated_plan(tmp_path):
    md = tmp_path / "2026-03-06-living-data-organism.md"
    md.write_text("# Living Data Organism\n\nSome content\n\n## Verification\n- Check 1\n")
    result = _parse_plan_file(md, "test-project")
    assert result is not None
    assert result.date == "2026-03-06"
    assert result.slug == "living-data-organism"
    assert result.title == "Living Data Organism"
    assert result.has_verification is True


def test_parse_dated_plan_with_version(tmp_path):
    md = tmp_path / "2026-03-06-my-plan-v2.md"
    md.write_text("# My Plan v2\n\nRevised.\n")
    result = _parse_plan_file(md, "proj")
    assert result is not None
    assert result.date == "2026-03-06"
    assert result.slug == "my-plan"  # -v2 stripped


def test_parse_undated_plan(tmp_path):
    md = tmp_path / "adhoc-notes.md"
    md.write_text("# Adhoc Notes\n\nSome notes.\n")
    result = _parse_plan_file(md, "proj")
    assert result is not None
    assert result.slug == "adhoc-notes"
    assert result.title == "Adhoc Notes"
    assert result.date != "unknown"  # should use mtime


def test_parse_plan_no_title(tmp_path):
    md = tmp_path / "2026-01-01-untitled.md"
    md.write_text("No heading here.\n")
    result = _parse_plan_file(md, "proj")
    assert result is not None
    assert result.title == "untitled"  # falls back to slug


def test_parse_plan_no_verification(tmp_path):
    md = tmp_path / "2026-01-01-plan.md"
    md.write_text("# Plan\n\nJust content.\n")
    result = _parse_plan_file(md, "proj")
    assert result is not None
    assert result.has_verification is False


def test_parse_plan_nonexistent():
    result = _parse_plan_file(Path("/nonexistent/file.md"), "proj")
    assert result is None


def test_parse_plan_empty(tmp_path):
    md = tmp_path / "2026-01-01-empty.md"
    md.write_text("")
    result = _parse_plan_file(md, "proj")
    assert result is not None
    assert result.title == "empty"  # falls back to slug
    assert result.size_bytes == 0


# ── discover_plans ────────────────────────────────────────────────


def test_discover_plans_project_level(tmp_path):
    """Plans in <workspace>/project/.claude/plans/ are found."""
    plans_dir = tmp_path / "project" / ".claude" / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "2026-03-01-alpha.md").write_text("# Alpha\n")
    (plans_dir / "2026-03-02-beta.md").write_text("# Beta\n")

    results = discover_plans(workspace=tmp_path)
    assert len(results) == 2
    # Sorted by date descending
    assert results[0].slug == "beta"
    assert results[1].slug == "alpha"


def test_discover_plans_nested_projects(tmp_path):
    """Plans in deeply nested project paths are found."""
    plans_dir = tmp_path / "org" / "repo" / ".claude" / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "2026-01-01-deep.md").write_text("# Deep Plan\n")

    results = discover_plans(workspace=tmp_path)
    assert len(results) == 1
    assert results[0].slug == "deep"


def test_discover_plans_project_filter(tmp_path):
    p1 = tmp_path / "projectA" / ".claude" / "plans"
    p1.mkdir(parents=True)
    (p1 / "2026-01-01-a.md").write_text("# A\n")

    p2 = tmp_path / "projectB" / ".claude" / "plans"
    p2.mkdir(parents=True)
    (p2 / "2026-01-01-b.md").write_text("# B\n")

    results = discover_plans(workspace=tmp_path, project_filter="projectA")
    assert len(results) == 1
    assert results[0].slug == "a"


def test_discover_plans_since_filter(tmp_path):
    plans_dir = tmp_path / "proj" / ".claude" / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "2025-01-01-old.md").write_text("# Old\n")
    (plans_dir / "2026-03-01-new.md").write_text("# New\n")

    results = discover_plans(workspace=tmp_path, since="2026-01-01")
    assert len(results) == 1
    assert results[0].slug == "new"


def test_discover_plans_deduplicates(tmp_path):
    """Same plan file found via multiple paths is deduplicated."""
    plans_dir = tmp_path / "proj" / ".claude" / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "2026-01-01-plan.md").write_text("# Plan\n")

    results = discover_plans(workspace=tmp_path)
    # No duplicates even if the same directory is traversed multiple ways
    paths = [str(r.path.resolve()) for r in results]
    assert len(paths) == len(set(paths))


def test_discover_plans_empty_workspace(tmp_path):
    results = discover_plans(workspace=tmp_path)
    assert results == []


def test_discover_plans_nonexistent_workspace():
    results = discover_plans(workspace=Path("/nonexistent/workspace"))
    assert results == []


# ── render_plan_inventory ─────────────────────────────────────────


def test_render_inventory_empty():
    output = render_plan_inventory([])
    assert "No plan files" in output


def test_render_inventory_basic():
    plans = [
        PlanFile(
            path=Path("/tmp/2026-03-06-plan.md"),
            project="my-project", slug="plan", date="2026-03-06",
            title="My Plan", size_bytes=2048, has_verification=True,
        ),
        PlanFile(
            path=Path("/tmp/2026-03-05-other.md"),
            project="my-project", slug="other", date="2026-03-05",
            title="Other Plan", size_bytes=512, has_verification=False,
        ),
    ]
    output = render_plan_inventory(plans)
    assert "2026-03-06" in output
    assert "My Plan" in output
    assert "2 plans" in output
    assert "1 projects" in output
    assert "Verification sections: 1/2" in output


def test_render_inventory_size_formatting():
    plans = [
        PlanFile(
            path=Path("/tmp/p.md"), project="p", slug="s", date="2026-01-01",
            title="T", size_bytes=100, has_verification=False,
        ),
    ]
    output = render_plan_inventory(plans)
    assert "100B" in output


# ── render_plan_audit ─────────────────────────────────────────────


def test_render_audit_empty():
    output = render_plan_audit([])
    assert "No plan files" in output


def test_render_audit_structure():
    plans = [
        PlanFile(
            path=Path("/tmp/2026-03-06-plan.md"),
            project="proj-a", slug="plan", date="2026-03-06",
            title="Plan Title", size_bytes=1024, has_verification=True,
        ),
    ]
    output = render_plan_audit(plans)
    assert "# Plan Audit Report" in output
    assert "## proj-a" in output
    assert "### 2026-03-06" in output
    assert "Plan Title" in output
    assert "**Verification:** Yes" in output
    assert "**Status:** unknown" in output
    assert "Reality:" in output


def test_render_audit_groups_by_project():
    plans = [
        PlanFile(
            path=Path("/tmp/a.md"), project="alpha", slug="a", date="2026-01-01",
            title="A", size_bytes=100, has_verification=False,
        ),
        PlanFile(
            path=Path("/tmp/b.md"), project="beta", slug="b", date="2026-01-02",
            title="B", size_bytes=100, has_verification=False,
        ),
    ]
    output = render_plan_audit(plans)
    assert "## alpha" in output
    assert "## beta" in output


# ── Integration: discover + render ────────────────────────────────


def test_discover_and_render(tmp_path):
    """Full pipeline: discover plans in tmp workspace and render inventory."""
    plans_dir = tmp_path / "my-project" / ".claude" / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "2026-03-01-sprint-plan.md").write_text(
        "# Sprint Plan\n\nContent here.\n\n## Verification\n- All tests pass\n"
    )
    (plans_dir / "2026-03-02-bugfix-plan.md").write_text(
        "# Bugfix Plan\n\nFix the bug.\n"
    )

    plans = discover_plans(workspace=tmp_path)
    assert len(plans) == 2

    inventory = render_plan_inventory(plans)
    assert "Sprint Plan" in inventory
    assert "Bugfix Plan" in inventory
    assert "2 plans" in inventory

    audit = render_plan_audit(plans)
    assert "# Plan Audit Report" in audit
    assert "Sprint Plan" in audit
