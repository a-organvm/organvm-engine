"""Omega scorecard CLI commands."""

import argparse
import json

from organvm_engine.registry.loader import load_registry


def cmd_omega_status(args: argparse.Namespace) -> int:
    from organvm_engine.omega.scorecard import evaluate

    registry = load_registry(args.registry)
    scorecard = evaluate(registry=registry)
    print(f"\n{scorecard.summary()}\n")

    # IRF P0 check
    try:
        from organvm_engine.irf import parse_irf, query_irf
        from organvm_engine.paths import irf_path
        irf_items = parse_irf(irf_path())
        p0 = query_irf(irf_items, priority="P0", status="open")
        if p0:
            print(f"\n⚠  {len(p0)} P0 IRF items require immediate action:")
            for item in p0:
                print(f"   {item.id}: {item.action[:60]}")
    except Exception:
        pass  # IRF integration is advisory, not blocking

    return 0


def cmd_omega_check(args: argparse.Namespace) -> int:
    from organvm_engine.omega.scorecard import evaluate

    registry = load_registry(args.registry)
    scorecard = evaluate(registry=registry)
    print(json.dumps(scorecard.to_dict(), indent=2))
    return 0


def cmd_omega_update(args: argparse.Namespace) -> int:
    from organvm_engine.omega.scorecard import diff_snapshots, evaluate, write_snapshot

    registry = load_registry(args.registry)
    scorecard = evaluate(registry=registry)

    # --write overrides the default dry_run=True
    dry_run = not getattr(args, "write", False)

    # Show what changed
    changes = diff_snapshots(scorecard)
    print(f"\n  Omega Update — {scorecard.met_count}/{scorecard.total} MET")
    print(f"  {'─' * 50}")
    for change in changes:
        print(f"  {change}")

    if dry_run:
        print("\n  [DRY RUN] Would write snapshot to data/omega/")
        print("  Re-run with --write to apply.")
    else:
        path = write_snapshot(scorecard)
        print(f"\n  Snapshot written: {path}")

    return 0
