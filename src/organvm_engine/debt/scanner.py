"""DEBT header scanner — detect and extract debt markers from source files.

The Emergency Maintenance Protocol (v3 methodology, Section 1) requires code
changes outside the RFIV cycle to carry ``# DEBT: pre-SPEC-XXX`` headers.
This module scans Python source files for those markers and returns structured
DebtItem records.

Recognized patterns:
    # DEBT: <description>
    # DEBT: pre-SPEC-XXX <description>
    # DEBT(SPEC-XXX): <description>
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class DebtItem:
    """A single DEBT marker found in a source file."""

    file: str           # relative or absolute path to the file
    line: int           # 1-based line number
    raw: str            # full text of the comment line (stripped)
    spec: str           # extracted SPEC reference (e.g. "SPEC-001") or ""
    description: str    # human-readable description after the marker
    kind: str           # "pre-spec" | "spec-ref" | "untracked"


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches: # DEBT(SPEC-XXX): description
_DEBT_SPEC_PAREN_RE = re.compile(
    r"^#\s*DEBT\s*\(\s*(SPEC-\d+)\s*\)\s*:\s*(.+)$",
)

# Matches: # DEBT: pre-SPEC-XXX description
_DEBT_PRE_SPEC_RE = re.compile(
    r"^#\s*DEBT\s*:\s*pre-(SPEC-\d+)\s+(.+)$",
)

# Matches: # DEBT: description (no spec reference)
_DEBT_BARE_RE = re.compile(
    r"^#\s*DEBT\s*:\s*(.+)$",
)


def _parse_debt_line(line: str, file_path: str, lineno: int) -> DebtItem | None:
    """Try to parse a single line as a DEBT marker.

    Returns a DebtItem if the line matches any recognized pattern, else None.
    """
    stripped = line.strip()

    # Try parenthesized spec ref first: # DEBT(SPEC-042): ...
    m = _DEBT_SPEC_PAREN_RE.match(stripped)
    if m:
        return DebtItem(
            file=file_path,
            line=lineno,
            raw=stripped,
            spec=m.group(1),
            description=m.group(2).strip(),
            kind="spec-ref",
        )

    # Try pre-SPEC pattern: # DEBT: pre-SPEC-001 ...
    m = _DEBT_PRE_SPEC_RE.match(stripped)
    if m:
        return DebtItem(
            file=file_path,
            line=lineno,
            raw=stripped,
            spec=m.group(1),
            description=m.group(2).strip(),
            kind="pre-spec",
        )

    # Try bare DEBT marker: # DEBT: ...
    m = _DEBT_BARE_RE.match(stripped)
    if m:
        return DebtItem(
            file=file_path,
            line=lineno,
            raw=stripped,
            spec="",
            description=m.group(1).strip(),
            kind="untracked",
        )

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_file(path: Path) -> list[DebtItem]:
    """Scan a single file for DEBT markers.

    Returns an empty list if the file does not exist or cannot be read.
    """
    if not path.is_file():
        return []

    items: list[DebtItem] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    file_str = str(path)
    for lineno, line in enumerate(text.splitlines(), start=1):
        item = _parse_debt_line(line, file_str, lineno)
        if item is not None:
            items.append(item)

    return items


def scan_files(paths: list[Path]) -> list[DebtItem]:
    """Scan multiple files for DEBT markers.

    Concatenates results from all files, preserving file-then-line order.
    """
    items: list[DebtItem] = []
    for p in paths:
        items.extend(scan_file(p))
    return items


def scan_directory(directory: Path, suffix: str = ".py") -> list[DebtItem]:
    """Recursively scan a directory for DEBT markers in files matching suffix.

    Skips hidden directories and __pycache__.
    """
    if not directory.is_dir():
        return []

    files = sorted(
        f
        for f in directory.rglob(f"*{suffix}")
        if not any(part.startswith(".") or part == "__pycache__" for part in f.parts)
    )
    return scan_files(files)


def scan_workspace(
    workspace: Path,
    organ: str | None = None,
) -> list[DebtItem]:
    """Scan organ directories under a workspace for DEBT markers.

    Args:
        workspace: Root workspace directory (e.g. ~/Workspace).
        organ: Optional CLI organ key (e.g. "META", "I"). If given, only
            scan that organ's directory. If None, scan all organs.

    Returns:
        List of DebtItem records found across all scanned source files.
    """
    from organvm_engine.organ_config import get_organ_map

    organ_map = get_organ_map()

    if organ is not None:
        organ_upper = organ.upper()
        if organ_upper not in organ_map:
            return []
        dirs = [workspace / organ_map[organ_upper]["dir"]]
    else:
        dirs = [workspace / v["dir"] for v in organ_map.values()]

    items: list[DebtItem] = []
    for d in dirs:
        if d.is_dir():
            items.extend(scan_directory(d))
    return items


def debt_stats(items: list[DebtItem]) -> dict:
    """Compute summary statistics for a list of DebtItem records.

    Returns a dict with keys:
        total, by_kind (dict kind → count), by_spec (dict spec → count),
        by_file (dict file → count), untracked_count, specs_referenced
    """
    total = len(items)

    by_kind: dict[str, int] = {"pre-spec": 0, "spec-ref": 0, "untracked": 0}
    by_spec: dict[str, int] = {}
    by_file: dict[str, int] = {}

    for item in items:
        by_kind[item.kind] = by_kind.get(item.kind, 0) + 1
        if item.spec:
            by_spec[item.spec] = by_spec.get(item.spec, 0) + 1
        by_file[item.file] = by_file.get(item.file, 0) + 1

    return {
        "total": total,
        "by_kind": by_kind,
        "by_spec": by_spec,
        "by_file": by_file,
        "untracked_count": by_kind.get("untracked", 0),
        "specs_referenced": sorted(by_spec.keys()),
    }
