"""Tests for the variable binding linter (metrics/lint_vars.py)."""

import pytest

from organvm_engine.metrics.lint_vars import (
    FROZEN_PATTERNS,
    LintReport,
    LintViolation,
    _is_frozen,
    _strip_var_markers,
    lint_file,
    lint_workspace,
)


@pytest.fixture
def variables():
    return {
        "total_repos": "103",
        "active_repos": "82",
        "total_organs": "8",
        "ci_workflows": "102",
        "total_words_short": "404K+",
        "total_words_formatted": "404,000",
        "published_essays": "48",
        "dependency_edges": "156",
        "sprints_completed": "33",
    }


# --- _is_frozen ---


def test_is_frozen_submissions(tmp_path):
    path = tmp_path / "pipeline" / "submissions" / "app.md"
    path.parent.mkdir(parents=True)
    path.touch()
    assert _is_frozen(path)


def test_is_frozen_node_modules(tmp_path):
    path = tmp_path / "node_modules" / "pkg" / "README.md"
    path.parent.mkdir(parents=True)
    path.touch()
    assert _is_frozen(path)


def test_is_frozen_regular_file(tmp_path):
    path = tmp_path / "docs" / "readme.md"
    path.parent.mkdir(parents=True)
    path.touch()
    assert not _is_frozen(path)


def test_is_frozen_plans(tmp_path):
    path = tmp_path / ".claude" / "plans" / "plan.md"
    path.parent.mkdir(parents=True)
    path.touch()
    assert _is_frozen(path)


# --- _strip_var_markers ---


def test_strip_var_markers():
    text = "We have <!-- v:total_repos -->103<!-- /v --> repositories"
    result = _strip_var_markers(text)
    assert "103" not in result
    assert "repositories" in result


def test_strip_var_markers_no_markers():
    text = "Just plain text"
    assert _strip_var_markers(text) == text


# --- lint_file ---


def test_lint_file_detects_bare_repos(tmp_path, variables):
    f = tmp_path / "test.md"
    f.write_text("We manage 103 repositories across 8 organs.\n")
    violations = lint_file(f, variables)
    keys = [v.key for v in violations]
    assert "total_repos" in keys


def test_lint_file_ignores_bound_value(tmp_path, variables):
    f = tmp_path / "test.md"
    f.write_text("We manage <!-- v:total_repos -->103<!-- /v --> repositories.\n")
    violations = lint_file(f, variables)
    assert len(violations) == 0


def test_lint_file_ignores_unrelated_numbers(tmp_path, variables):
    f = tmp_path / "test.md"
    f.write_text("The year is 2026 and there are 42 apples.\n")
    violations = lint_file(f, variables)
    assert len(violations) == 0


def test_lint_file_detects_bare_essays(tmp_path, variables):
    f = tmp_path / "test.md"
    f.write_text("We have written 48 published essays.\n")
    violations = lint_file(f, variables)
    keys = [v.key for v in violations]
    assert "published_essays" in keys


def test_lint_file_detects_bare_ci(tmp_path, variables):
    f = tmp_path / "test.md"
    f.write_text("Running 102 CI/CD workflows.\n")
    violations = lint_file(f, variables)
    keys = [v.key for v in violations]
    assert "ci_workflows" in keys


def test_lint_file_detects_bare_word_count(tmp_path, variables):
    f = tmp_path / "test.md"
    f.write_text("Over 404K+ words of documentation.\n")
    violations = lint_file(f, variables)
    keys = [v.key for v in violations]
    assert "total_words_short" in keys


def test_lint_file_nonexistent(tmp_path, variables):
    f = tmp_path / "does-not-exist.md"
    violations = lint_file(f, variables)
    assert violations == []


# --- lint_workspace ---


def test_lint_workspace_scans_markdown(tmp_path, variables):
    (tmp_path / "a.md").write_text("103 repositories across the system.\n")
    (tmp_path / "b.txt").write_text("103 repositories across the system.\n")

    report = lint_workspace(tmp_path, variables)

    assert report.files_scanned == 1  # only .md
    assert report.total_violations >= 1


def test_lint_workspace_skips_frozen(tmp_path, variables):
    sub = tmp_path / "node_modules" / "pkg"
    sub.mkdir(parents=True)
    (sub / "README.md").write_text("103 repositories across the system.\n")

    report = lint_workspace(tmp_path, variables)
    assert report.total_violations == 0


def test_lint_workspace_clean(tmp_path, variables):
    (tmp_path / "clean.md").write_text("Everything is great.\n")

    report = lint_workspace(tmp_path, variables)
    assert report.files_scanned == 1
    assert report.files_clean == 1
    assert report.total_violations == 0
