"""CLI commands for the contribution engine.

Commands:
    organvm contrib list          — List all contribution repos and their targets
    organvm contrib status        — Check upstream PR status for all contrib repos
    organvm contrib backflow      — Generate backflow signal report
    organvm contrib backflow --write — Write backflow manifest to atoms dir
"""

from __future__ import annotations

import argparse
import sys

from organvm_engine.contrib.discover import discover_contrib_repos
from organvm_engine.contrib.status import check_pr_status, PRState


def cmd_contrib_list(args: argparse.Namespace) -> int:
    """List all contribution repos."""
    repos = discover_contrib_repos()

    if not repos:
        print("No contribution repos found.")
        return 0

    print(f"{'Name':<40} {'Target':<35} {'PR':<8} {'Status':<12}")
    print("-" * 95)
    for repo in repos:
        pr_str = f"#{repo.target_pr}" if repo.target_pr else "—"
        print(f"{repo.name:<40} {repo.target_repo:<35} {pr_str:<8} {repo.promotion_status:<12}")

    print(f"\n{len(repos)} contribution repos found.")
    return 0


def cmd_contrib_status(args: argparse.Namespace) -> int:
    """Check upstream PR status for all contrib repos."""
    repos = discover_contrib_repos()
    repos_with_prs = [r for r in repos if r.target_pr is not None]

    if not repos_with_prs:
        print("No contribution repos with PR numbers found.")
        return 0

    print(f"Checking {len(repos_with_prs)} upstream PRs...\n")
    print(f"{'Target':<35} {'PR':<8} {'State':<10} {'Title':<45}")
    print("-" * 98)

    merged_count = 0
    open_count = 0
    closed_count = 0

    for repo in repos_with_prs:
        status = check_pr_status(repo)
        state_str = status.state.value.upper()

        # Color-code state for terminal
        if status.state == PRState.MERGED:
            state_display = f"\033[32m{state_str}\033[0m"
            merged_count += 1
        elif status.state == PRState.OPEN:
            state_display = f"\033[33m{state_str}\033[0m"
            open_count += 1
        elif status.state == PRState.CLOSED:
            state_display = f"\033[31m{state_str}\033[0m"
            closed_count += 1
        else:
            state_display = state_str

        title = (status.title[:42] + "...") if len(status.title) > 45 else status.title
        print(f"{repo.target_repo:<35} #{repo.target_pr:<6} {state_display:<19} {title}")

    print(f"\nSummary: {merged_count} merged, {open_count} open, {closed_count} closed")
    return 0


def cmd_contrib_backflow(args: argparse.Namespace) -> int:
    """Generate backflow signal report from contribution statuses."""
    from organvm_engine.contrib.backflow import (
        classify_contribution,
        generate_backflow_report,
        write_backflow_manifest,
        SIGNAL_ORGAN_MAP,
    )
    from organvm_engine.contrib.status import check_all_statuses
    from organvm_engine.paths import workspace_root

    repos = discover_contrib_repos()
    repos_with_prs = [r for r in repos if r.target_pr is not None]

    if not repos_with_prs:
        print("No contribution repos with PR numbers found.")
        return 0

    print(f"Checking {len(repos_with_prs)} contributions for backflow signals...\n")
    statuses = check_all_statuses(repos_with_prs)

    report = generate_backflow_report(statuses)

    # Display report
    total = sum(len(signals) for signals in report.values())
    print(f"Backflow report: {total} signals across {sum(1 for s in report.values() if s)} organs\n")

    for organ, signals in report.items():
        if signals:
            print(f"  ORGAN-{organ}: {len(signals)} signals")
            for sig in signals[:3]:
                print(f"    [{sig.signal_type.value}] {sig.content[:60]}")
            if len(signals) > 3:
                print(f"    ... and {len(signals) - 3} more")
            print()

    # Write manifest if --write flag
    if getattr(args, "write", False):
        ws = workspace_root()
        atoms_dir = ws / "meta-organvm" / "organvm-corpvs-testamentvm" / "data" / "atoms"
        manifest_path = write_backflow_manifest(report, atoms_dir)
        print(f"Manifest written: {manifest_path}")
    else:
        print("(dry-run — use --write to persist manifest)")

    return 0
