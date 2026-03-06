"""CLI command: organvm lint-vars — check for unbound metric references."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_lint_vars(args: argparse.Namespace) -> int:
    from organvm_engine.cli import _resolve_workspace
    from organvm_engine.metrics.lint_vars import lint_workspace
    from organvm_engine.metrics.vars import build_vars, load_vars

    corpus_root = Path(args.registry).parent
    vars_path = corpus_root / "system-vars.json"

    # Load or build variables
    if vars_path.exists():
        variables = load_vars(vars_path)
    else:
        from organvm_engine.metrics.calculator import compute_metrics
        from organvm_engine.registry.loader import load_registry

        registry = load_registry(args.registry)
        workspace = _resolve_workspace(args)
        metrics_path = corpus_root / "system-metrics.json"

        if metrics_path.exists():
            with metrics_path.open() as f:
                metrics = json.load(f)
        else:
            computed = compute_metrics(registry, workspace=workspace)
            metrics = {"computed": computed, "manual": {}}

        variables = build_vars(metrics, registry)

    # Determine scan root
    workspace = _resolve_workspace(args)
    if workspace is None:
        print("ERROR: Could not determine workspace.", file=sys.stderr)
        return 1

    report = lint_workspace(workspace, variables)

    if report.violations:
        print(f"Found {report.total_violations} unbound metric(s) "
              f"in {report.files_scanned} files:")
        print()
        for v in report.violations:
            print(f"  {v.file}:{v.line}")
            print(f"    {v.key} = {v.value}")
            print(f"    {v.context}")
            print()

        if getattr(args, "strict", False):
            return 1
    else:
        print(f"All clean. {report.files_scanned} files scanned, "
              f"{report.files_clean} clean.")

    return 0
