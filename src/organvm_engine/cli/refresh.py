"""CLI command: organvm refresh — unified metrics + variable binding refresh."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from organvm_engine.registry.loader import load_registry


def cmd_refresh(args: argparse.Namespace) -> int:
    from organvm_engine.cli import _resolve_workspace
    from organvm_engine.metrics.calculator import compute_metrics, write_metrics
    from organvm_engine.metrics.vars import build_vars, resolve_targets_from_manifest, write_vars

    dry_run = args.dry_run
    prefix = "[DRY RUN] " if dry_run else ""
    skip_context = getattr(args, "skip_context", False)
    skip_organism = getattr(args, "skip_organism", False)
    skip_legacy = getattr(args, "skip_legacy", False)

    registry = load_registry(args.registry)
    workspace = _resolve_workspace(args)
    corpus_root = Path(args.registry).parent

    # Step 1: Compute metrics
    computed = compute_metrics(registry, workspace=workspace)
    metrics_path = corpus_root / "system-metrics.json"

    if not dry_run:
        write_metrics(computed, metrics_path)

    print(f"{prefix}[1/7] Metrics calculated -> {metrics_path}")
    print(f"  Repos: {computed['total_repos']} ({computed['active_repos']} ACTIVE)")

    # Step 2: Build + write system-vars.json
    # Load metrics back (includes manual section)
    if metrics_path.exists():
        with metrics_path.open() as f:
            metrics = json.load(f)
    else:
        metrics = {"computed": computed, "manual": {}}

    variables = build_vars(metrics, registry)
    vars_path = corpus_root / "system-vars.json"

    if not dry_run:
        write_vars(variables, vars_path)

    print(f"{prefix}[2/7] Variables manifest -> {vars_path} ({len(variables)} vars)")

    # Step 3: Resolve variable bindings
    vars_targets_path = corpus_root / "vars-targets.yaml"
    if vars_targets_path.exists():
        result = resolve_targets_from_manifest(variables, vars_targets_path, dry_run=dry_run)
        print(
            f"{prefix}[3/7] Variables resolved: "
            f"{result.total_replacements} replacement(s) in "
            f"{result.files_changed}/{result.files_scanned} file(s)",
        )
        if result.unknown_keys:
            print(f"  WARNING: unknown keys: {', '.join(result.unknown_keys)}")
        for d in result.details[:10]:
            print(f"    {d}")
        if len(result.details) > 10:
            print(f"    ... and {len(result.details) - 10} more")
    else:
        print(f"{prefix}[3/7] No vars-targets.yaml found, skipping variable resolution")
        result = None

    # Step 4: Legacy regex propagation
    if not skip_legacy:
        from organvm_engine.metrics.propagator import (
            propagate_cross_repo,
            propagate_metrics,
        )

        manifest_path = corpus_root / "metrics-targets.yaml"
        if manifest_path.exists():
            legacy_result = propagate_cross_repo(
                metrics, manifest_path, corpus_root, dry_run=dry_run, registry=registry,
            )
            print(
                f"{prefix}[4/7] Legacy propagation: "
                f"{legacy_result.replacements} replacement(s) in "
                f"{legacy_result.files_changed} file(s), "
                f"{legacy_result.json_copies} JSON copies",
            )
        else:
            # Corpus-only fallback
            whitelist_globs = [
                "README.md", "CLAUDE.md",
                "applications/*.md", "applications/shared/*.md",
                "docs/applications/*.md",
                "docs/essays/09-ai-conductor-methodology.md",
                "docs/operations/*.md",
            ]
            files: list[Path] = []
            for pattern in whitelist_globs:
                files.extend(sorted(corpus_root.glob(pattern)))
            seen: set[Path] = set()
            unique = [f for f in files if f not in seen and not seen.add(f)]  # type: ignore[func-returns-value]
            legacy_result = propagate_metrics(metrics, unique, dry_run=dry_run)
            print(
                f"{prefix}[4/7] Legacy propagation (corpus-only): "
                f"{legacy_result.replacements} replacement(s)",
            )
    else:
        print(f"{prefix}[4/7] Legacy propagation skipped")

    # Step 5: JSON copies (portfolio)
    if not skip_legacy:
        # Already handled in step 4 if cross-repo
        print(f"{prefix}[5/7] JSON copies (included in step 4)")
    else:
        print(f"{prefix}[5/7] JSON copies skipped")

    # Step 6: Context sync
    if not skip_context:
        try:
            from organvm_engine.contextmd.sync import sync_all

            if workspace:
                sync_all(
                    registry, workspace, dry_run=dry_run, write=not dry_run,
                )
                print(f"{prefix}[6/7] Context sync complete")
            else:
                print(f"{prefix}[6/7] Context sync skipped (no workspace)")
        except Exception as e:
            print(f"{prefix}[6/7] Context sync error: {e}", file=sys.stderr)
    else:
        print(f"{prefix}[6/7] Context sync skipped")

    # Step 7: Organism snapshot
    if not skip_organism:
        try:
            from organvm_engine.metrics.organism import compute_organism

            compute_organism(registry, metrics, workspace=workspace)
            print(
                f"{prefix}[7/7] Organism computed "
                f"(use 'organvm organism snapshot --write' to persist)",
            )
        except Exception as e:
            print(f"{prefix}[7/7] Organism error: {e}", file=sys.stderr)
    else:
        print(f"{prefix}[7/7] Organism skipped")

    # Summary
    var_count = result.total_replacements if result else 0
    var_files = result.files_changed if result else 0
    print(f"\n{prefix}Done. {var_count} variables resolved in {var_files} files.")

    return 0
