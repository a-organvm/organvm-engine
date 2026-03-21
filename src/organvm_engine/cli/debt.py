"""CLI handler for the debt command group — DEBT header detection and tracking."""

from __future__ import annotations

import dataclasses
import json
import sys


def cmd_debt_scan(args) -> int:
    """Scan source files for DEBT markers and print a report."""
    from organvm_engine.debt import scan_directory, scan_workspace
    from organvm_engine.paths import resolve_workspace

    workspace = resolve_workspace(args)
    organ = getattr(args, "organ", None)
    path = getattr(args, "path", None)
    as_json = getattr(args, "json", False)

    # If an explicit path is given, scan that directory directly
    if path:
        from pathlib import Path

        items = scan_directory(Path(path))
    elif workspace is not None:
        items = scan_workspace(workspace, organ=organ)
    else:
        print("Cannot resolve workspace. Set ORGANVM_WORKSPACE_DIR or pass --path.", file=sys.stderr)
        return 1

    if as_json:
        json.dump([dataclasses.asdict(i) for i in items], sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if not items:
        print("No DEBT markers found.")
        return 0

    # Pretty table
    col_file = 45
    col_line = 6
    col_kind = 11
    col_spec = 10

    header = (
        f"{'File':<{col_file}} {'Line':<{col_line}} {'Kind':<{col_kind}}"
        f" {'Spec':<{col_spec}} Description"
    )
    sep = f"{'─' * col_file} {'─' * col_line} {'─' * col_kind} {'─' * col_spec} {'─' * 30}"
    print(header)
    print(sep)
    for item in items:
        file_display = item.file
        if len(file_display) > col_file:
            file_display = "…" + file_display[-(col_file - 1):]
        desc = item.description
        if len(desc) > 50:
            desc = desc[:49] + "…"
        print(
            f"{file_display:<{col_file}} {item.line:<{col_line}} {item.kind:<{col_kind}}"
            f" {item.spec or '—':<{col_spec}} {desc}",
        )

    print()
    print(f"{len(items)} DEBT marker(s) found")
    return 0


def cmd_debt_stats(args) -> int:
    """Show summary statistics for DEBT markers across the workspace."""
    from organvm_engine.debt import debt_stats, scan_directory, scan_workspace
    from organvm_engine.paths import resolve_workspace

    workspace = resolve_workspace(args)
    organ = getattr(args, "organ", None)
    path = getattr(args, "path", None)
    as_json = getattr(args, "json", False)

    if path:
        from pathlib import Path

        items = scan_directory(Path(path))
    elif workspace is not None:
        items = scan_workspace(workspace, organ=organ)
    else:
        print("Cannot resolve workspace. Set ORGANVM_WORKSPACE_DIR or pass --path.", file=sys.stderr)
        return 1

    stats = debt_stats(items)

    if as_json:
        json.dump(stats, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    print("DEBT Summary")
    print("─" * 40)
    print(f"  Total markers:     {stats['total']}")
    print(f"  Untracked:         {stats['untracked_count']}")

    if stats["by_kind"]:
        print()
        print("By Kind")
        print("─" * 40)
        for kind, count in sorted(stats["by_kind"].items()):
            print(f"  {kind:<14} {count}")

    if stats["specs_referenced"]:
        print()
        print("SPEC References")
        print("─" * 40)
        for spec in stats["specs_referenced"]:
            count = stats["by_spec"][spec]
            print(f"  {spec:<14} {count}")

    if stats["by_file"]:
        print()
        print(f"Files with DEBT ({len(stats['by_file'])})")
        print("─" * 40)
        for filepath, count in sorted(stats["by_file"].items(), key=lambda x: -x[1]):
            print(f"  {filepath}  ({count})")

    return 0
