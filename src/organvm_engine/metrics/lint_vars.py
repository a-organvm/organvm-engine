"""Lint for unbound metric references in markdown files.

Detects bare metric numbers that should be wrapped in <!-- v:KEY --> markers.
Numbers already inside markers are ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

from organvm_engine.metrics.vars import VAR_PATTERN

# Frozen file patterns — these are historical/submitted and should not be linted
FROZEN_PATTERNS = [
    "**/pipeline/submissions/**",
    "**/scripts/legacy-submission/**",
    "**/materials/resumes/**",
    "**/variants/cover-letters/*-alchemized.md",
    "**/docs/archive/**",
    "**/docs/planning/**",
    "**/.claude/plans/**",
    "**/node_modules/**",
    "**/intake/**",
    "**/.venv/**",
    "**/.git/**",
]


@dataclass
class LintViolation:
    """A bare metric number that should be bound to a variable."""

    file: Path
    line: int
    key: str
    value: str
    context: str  # the line text


@dataclass
class LintReport:
    """Aggregate lint results."""

    violations: list[LintViolation] = field(default_factory=list)
    files_scanned: int = 0
    files_clean: int = 0

    @property
    def total_violations(self) -> int:
        return len(self.violations)


# Context words that hint at which variable a bare number belongs to
_HINTS: list[tuple[str, list[str]]] = [
    ("total_repos", ["repositor", "repos"]),
    ("active_repos", ["active repo", "ACTIVE"]),
    ("archived_repos", ["archived", "ARCHIVED"]),
    ("total_organs", ["organs"]),
    ("ci_workflows", ["CI/CD", "CI workflow", "CI pipeline"]),
    ("dependency_edges", ["dependency edge", "tracked dependenc"]),
    ("published_essays", ["published essay", "meta-system essay", "essays explaining"]),
    ("sprints_completed", ["sprints completed"]),
    ("total_words_short", ["K+ words", "K words"]),
    ("total_words_formatted", [" words"]),
]


def _is_frozen(path: Path, frozen_patterns: list[str] | None = None) -> bool:
    """Check if a path matches any frozen pattern."""
    patterns = frozen_patterns or FROZEN_PATTERNS
    path_str = str(path)
    return any(fnmatch(path_str, pattern) for pattern in patterns)


def _strip_var_markers(text: str) -> str:
    """Remove content inside <!-- v:KEY --> markers so they don't trigger false positives."""
    return VAR_PATTERN.sub("", text)


def lint_file(path: Path, variables: dict[str, str]) -> list[LintViolation]:
    """Check a markdown file for bare metric numbers that should be bound.

    Only flags numbers that appear near context words suggesting they're
    metrics (not arbitrary numbers).
    """
    try:
        content = path.read_text()
    except OSError:
        return []

    violations: list[LintViolation] = []
    lines = content.splitlines()

    for line_num, line in enumerate(lines, 1):
        # Strip any existing markers from the line for analysis
        clean_line = _strip_var_markers(line)
        if not clean_line.strip():
            continue

        for key, hints in _HINTS:
            value = variables.get(key)
            if not value:
                continue

            # Check if the bare value appears near a hint word
            for hint in hints:
                if hint.lower() not in clean_line.lower():
                    continue
                # Look for the bare value — use word boundary on left,
                # but allow non-word chars (like +) on right edge
                escaped = re.escape(value)
                pattern = re.compile(rf"(?<!\w){escaped}(?!\w)")
                if pattern.search(clean_line):
                    violations.append(LintViolation(
                        file=path,
                        line=line_num,
                        key=key,
                        value=value,
                        context=line.rstrip(),
                    ))
                    break  # one violation per key per line

    return violations


def lint_workspace(
    workspace: Path,
    variables: dict[str, str],
    frozen_patterns: list[str] | None = None,
) -> LintReport:
    """Walk workspace, lint all non-frozen markdown files."""
    report = LintReport()
    patterns = frozen_patterns or FROZEN_PATTERNS

    for md_file in sorted(workspace.rglob("*.md")):
        if _is_frozen(md_file, patterns):
            continue

        report.files_scanned += 1
        violations = lint_file(md_file, variables)

        if violations:
            report.violations.extend(violations)
        else:
            report.files_clean += 1

    return report
