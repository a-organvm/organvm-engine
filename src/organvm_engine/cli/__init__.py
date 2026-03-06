"""Unified CLI for the organvm system.

Usage:
    organvm status
    organvm registry show <repo>
    organvm registry list [--organ X] [--status X] [--tier X]
    organvm registry search <query> [--field X] [--exact]
    organvm registry deps <repo> [--reverse] [--transitive]
    organvm registry stats [--json]
    organvm registry validate
    organvm registry update <repo> <field> <value>
    organvm governance audit
    organvm governance check-deps
    organvm governance promote <repo> <target-state>
    organvm seed discover
    organvm seed validate
    organvm seed graph
    organvm metrics calculate
    organvm metrics count-words [--workspace <path>]
    organvm metrics propagate [--cross-repo] [--dry-run]
    organvm metrics refresh [--cross-repo] [--dry-run]
    organvm dispatch validate <file>
    organvm git init-superproject --organ {I|II|III|IV|V|VI|VII|META|LIMINAL}
    organvm git add-submodule --organ X --repo <name> [--url <url>]
    organvm git sync-organ --organ X [--message "msg"]
    organvm git sync-all [--dry-run]
    organvm git status [--organ X]
    organvm git reproduce-workspace [--organ X] [--shallow] [--manifest <path>]
    organvm git diff-pinned [--organ X]
    organvm git install-hooks [--organ X]
    organvm omega status
    organvm omega check
    organvm pitch generate <repo> [--dry-run]
    organvm pitch sync [--organ X] [--dry-run] [--tier X]
    organvm context sync [--dry-run] [--organ X]
"""

import argparse
import os
import sys
from pathlib import Path

from organvm_engine.cli.ci import cmd_ci_triage
from organvm_engine.cli.context import cmd_context_sync
from organvm_engine.cli.deadlines import cmd_deadlines
from organvm_engine.cli.dispatch import cmd_dispatch_validate
from organvm_engine.cli.git_cmds import (
    cmd_git_add_submodule,
    cmd_git_diff_pinned,
    cmd_git_init_superproject,
    cmd_git_install_hooks,
    cmd_git_reproduce,
    cmd_git_status,
    cmd_git_sync_all,
    cmd_git_sync_organ,
)
from organvm_engine.cli.governance import (
    cmd_governance_audit,
    cmd_governance_checkdeps,
    cmd_governance_impact,
    cmd_governance_promote,
)
from organvm_engine.cli.metrics import (
    cmd_metrics_calculate,
    cmd_metrics_count_words,
    cmd_metrics_propagate,
    cmd_metrics_refresh,
)
from organvm_engine.cli.omega import cmd_omega_check, cmd_omega_status, cmd_omega_update
from organvm_engine.cli.organism import cmd_organism, cmd_organism_snapshot
from organvm_engine.cli.pitch import cmd_pitch_generate, cmd_pitch_sync
from organvm_engine.cli.registry import (
    cmd_registry_deps,
    cmd_registry_list,
    cmd_registry_search,
    cmd_registry_show,
    cmd_registry_stats,
    cmd_registry_update,
    cmd_registry_validate,
)
from organvm_engine.cli.seed import cmd_seed_discover, cmd_seed_graph, cmd_seed_validate
from organvm_engine.cli.session import (
    cmd_session_export,
    cmd_session_list,
    cmd_session_projects,
    cmd_session_show,
    cmd_session_transcript,
)
from organvm_engine.cli.status import cmd_status
from organvm_engine.paths import registry_path as _default_registry_path


def _resolve_workspace(args: argparse.Namespace) -> Path | None:
    """Resolve workspace path from args or environment."""
    raw = getattr(args, "workspace", None)
    if raw:
        return Path(raw).expanduser().resolve()
    env = os.environ.get("ORGANVM_WORKSPACE_DIR")
    if env:
        return Path(env).expanduser().resolve()
    default = Path.home() / "Workspace"
    return default if default.is_dir() else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="organvm",
        description="Unified CLI for the organvm eight-organ system",
    )
    parser.add_argument(
        "--registry",
        default=str(_default_registry_path()),
        help="Path to registry-v2.json",
    )
    sub = parser.add_subparsers(dest="command")

    # registry
    reg = sub.add_parser("registry", help="Registry operations")
    reg_sub = reg.add_subparsers(dest="subcommand")

    show = reg_sub.add_parser("show", help="Show a registry entry")
    show.add_argument("repo")

    ls = reg_sub.add_parser("list", help="List repos with filters")
    ls.add_argument("--organ", default=None)
    ls.add_argument("--status", default=None)
    ls.add_argument("--tier", default=None)
    ls.add_argument("--promotion-status", default=None)
    ls.add_argument("--public", action="store_true")
    ls.add_argument("--platinum", action="store_true")
    ls.add_argument("--name-contains", default=None)
    ls.add_argument("--depends-on", default=None, help="Filter repos that depend on this repo")
    ls.add_argument(
        "--dependency-of",
        default=None,
        help="Filter repos that are dependencies of this repo",
    )
    ls.add_argument(
        "--sort-by",
        default="name",
        help="Sort field (name, organ, status, tier, promotion_status, ...)",
    )
    ls.add_argument("--desc", action="store_true", help="Sort descending")
    ls_archived = ls.add_mutually_exclusive_group()
    ls_archived.add_argument("--archived", action="store_true")
    ls_archived.add_argument("--unarchived", action="store_true")

    search = reg_sub.add_parser("search", help="Search repos by text query")
    search.add_argument("query")
    search.add_argument(
        "--field",
        action="append",
        default=None,
        help="Field(s) to search (repeatable). Defaults to standard text fields.",
    )
    search.add_argument("--exact", action="store_true")
    search.add_argument("--case-sensitive", action="store_true")
    search.add_argument("--limit", type=int, default=None)
    search.add_argument("--organ", default=None)
    search.add_argument("--status", default=None)
    search.add_argument("--tier", default=None)
    search.add_argument("--promotion-status", default=None)
    search.add_argument("--public", action="store_true")
    search.add_argument("--sort-by", default="name")
    search.add_argument("--desc", action="store_true")
    search.add_argument("--json", action="store_true")

    deps = reg_sub.add_parser("deps", help="Show repo dependencies/dependents")
    deps.add_argument("repo")
    deps.add_argument("--reverse", action="store_true", help="Show dependents")
    deps.add_argument("--both", action="store_true", help="Show dependencies and dependents")
    deps.add_argument("--transitive", action="store_true", help="Include transitive graph")
    deps.add_argument("--max-depth", type=int, default=None)
    deps.add_argument("--json", action="store_true")

    stats = reg_sub.add_parser("stats", help="Show registry summary statistics")
    stats.add_argument("--json", action="store_true")

    reg_sub.add_parser("validate", help="Validate registry")

    upd = reg_sub.add_parser("update", help="Update a registry field")
    upd.add_argument("repo")
    upd.add_argument("field")
    upd.add_argument("value")

    # governance
    gov = sub.add_parser("governance", help="Governance operations")
    gov_sub = gov.add_subparsers(dest="subcommand")
    aud = gov_sub.add_parser("audit", help="Full governance audit")
    aud.add_argument(
        "--rules",
        default=None,
        help="Path to governance-rules.json",
    )

    gov_sub.add_parser("check-deps", help="Validate dependency graph")

    prom = gov_sub.add_parser("promote", help="Check promotion eligibility")
    prom.add_argument("repo")
    prom.add_argument("target", help="Target promotion state")

    imp = gov_sub.add_parser(
        "impact",
        help="Calculate blast radius of a repo change",
    )
    imp.add_argument("repo", help="Repository name")

    # seed
    seed = sub.add_parser("seed", help="Seed.yaml operations")
    seed.add_argument(
        "--workspace",
        default=None,
        help="Workspace root directory",
    )
    seed_sub = seed.add_subparsers(dest="subcommand")
    seed_sub.add_parser("discover", help="Find all seed.yaml files")
    seed_sub.add_parser("validate", help="Validate all seed.yaml files")
    seed_sub.add_parser("graph", help="Build produces/consumes graph")

    # metrics
    met = sub.add_parser("metrics", help="Metrics operations")
    met.add_argument(
        "--workspace",
        default=None,
        help="Workspace root directory",
    )
    met_sub = met.add_subparsers(dest="subcommand")
    calc = met_sub.add_parser("calculate", help="Compute current metrics")
    calc.add_argument("--output", default=None, help="Output file path")

    met_sub.add_parser(
        "count-words",
        help="Count words across the workspace",
    )

    prop = met_sub.add_parser(
        "propagate",
        help="Propagate metrics to documentation files",
    )
    prop.add_argument(
        "--cross-repo",
        action="store_true",
        help="Read metrics-targets.yaml and propagate to all consumers",
    )
    prop.add_argument(
        "--targets",
        default=None,
        help="Path to metrics-targets.yaml (default: corpus root)",
    )
    prop.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing",
    )

    refresh = met_sub.add_parser(
        "refresh",
        help="Calculate + propagate in one step",
    )
    refresh.add_argument(
        "--cross-repo",
        action="store_true",
        help="Propagate to all registered consumers",
    )
    refresh.add_argument(
        "--targets",
        default=None,
        help="Path to metrics-targets.yaml",
    )
    refresh.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing",
    )

    # dispatch
    dis = sub.add_parser("dispatch", help="Dispatch operations")
    dis_sub = dis.add_subparsers(dest="subcommand")
    val = dis_sub.add_parser("validate", help="Validate a dispatch payload")
    val.add_argument("file", help="Path to dispatch payload JSON")

    # git
    git = sub.add_parser(
        "git",
        help="Hierarchical superproject management",
    )
    git.add_argument(
        "--workspace",
        default=None,
        help="Workspace root directory",
    )
    git_sub = git.add_subparsers(dest="subcommand")

    git_init = git_sub.add_parser(
        "init-superproject",
        help="Initialize organ superproject",
    )
    git_init.add_argument(
        "--organ",
        required=True,
        help="Organ key (I, II, ..., META, LIMINAL)",
    )
    git_init.add_argument(
        "--dry-run",
        action="store_true",
        help="Report without making changes",
    )

    git_add = git_sub.add_parser(
        "add-submodule",
        help="Add submodule to organ superproject",
    )
    git_add.add_argument("--organ", required=True, help="Organ key")
    git_add.add_argument("--repo", required=True, help="Repository name")
    git_add.add_argument(
        "--url",
        default=None,
        help="Git URL (auto-derived if omitted)",
    )

    git_sync = git_sub.add_parser(
        "sync-organ",
        help="Sync submodule pointers",
    )
    git_sync.add_argument("--organ", required=True, help="Organ key")
    git_sync.add_argument("--message", default=None, help="Commit message")
    git_sync.add_argument(
        "--dry-run",
        action="store_true",
        help="Report without committing",
    )

    git_sync_all = git_sub.add_parser(
        "sync-all",
        help="Sync all organ superprojects",
    )
    git_sync_all.add_argument(
        "--dry-run",
        action="store_true",
        help="Report without committing",
    )

    git_status = git_sub.add_parser("status", help="Show submodule drift")
    git_status.add_argument(
        "--organ",
        default=None,
        help="Specific organ (default: all)",
    )

    git_reproduce = git_sub.add_parser(
        "reproduce-workspace",
        help="Clone workspace from superprojects",
    )
    git_reproduce.add_argument(
        "--target",
        required=True,
        help="Target directory",
    )
    git_reproduce.add_argument(
        "--organ",
        default=None,
        help="Single organ to clone",
    )
    git_reproduce.add_argument(
        "--shallow",
        action="store_true",
        help="Shallow clone",
    )
    git_reproduce.add_argument(
        "--manifest",
        default=None,
        help="Path to workspace-manifest.json",
    )

    git_diff = git_sub.add_parser(
        "diff-pinned",
        help="Show detailed diff between pinned and current",
    )
    git_diff.add_argument(
        "--organ",
        default=None,
        help="Specific organ (default: all)",
    )

    git_hooks = git_sub.add_parser(
        "install-hooks",
        help="Install git context sync hooks",
    )
    git_hooks.add_argument(
        "--organ",
        default=None,
        help="Specific organ (default: all)",
    )

    # deadlines
    dl = sub.add_parser(
        "deadlines",
        help="Show upcoming deadlines from rolling-todo",
    )
    dl.add_argument(
        "--days",
        type=int,
        default=30,
        help="Show deadlines within N days (default 30)",
    )
    dl.add_argument(
        "--all",
        action="store_true",
        help="Show all deadlines regardless of date",
    )

    # ci
    ci = sub.add_parser("ci", help="CI health operations")
    ci_sub = ci.add_subparsers(dest="subcommand")
    ci_triage = ci_sub.add_parser(
        "triage",
        help="Categorize CI failures from soak data",
    )
    ci_triage.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON",
    )

    # omega
    om = sub.add_parser("omega", help="Omega scorecard operations")
    om_sub = om.add_subparsers(dest="subcommand")
    om_sub.add_parser("status", help="Display omega scorecard summary")
    om_sub.add_parser("check", help="Machine-readable omega status (JSON)")
    om_update = om_sub.add_parser(
        "update",
        help="Evaluate and write omega snapshot",
    )
    om_update.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview without writing (default)",
    )
    om_update.add_argument(
        "--write",
        action="store_true",
        help="Actually write snapshot (overrides --dry-run)",
    )

    # pitch
    pitch = sub.add_parser("pitch", help="Pitch deck generation")
    pitch.add_argument(
        "--workspace",
        default=None,
        help="Workspace root directory",
    )
    pitch_sub = pitch.add_subparsers(dest="subcommand")

    pitch_gen = pitch_sub.add_parser(
        "generate",
        help="Generate pitch deck for a single repo",
    )
    pitch_gen.add_argument("repo", help="Repository name")
    pitch_gen.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing",
    )

    pitch_sync = pitch_sub.add_parser(
        "sync",
        help="Sync pitch decks across workspace",
    )
    pitch_sync.add_argument(
        "--organ",
        default=None,
        help="Filter to specific organ",
    )
    pitch_sync.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing",
    )
    pitch_sync.add_argument(
        "--tier",
        default=None,
        help="Filter by tier (flagship, standard, all)",
    )

    # status (top-level)
    sub.add_parser("status", help="One-command system health pulse")

    # context
    ctx = sub.add_parser(
        "context",
        help="System context file management",
    )
    ctx.add_argument(
        "--workspace",
        default=None,
        help="Workspace root directory",
    )
    ctx_sub = ctx.add_subparsers(dest="subcommand")
    c_sync = ctx_sub.add_parser(
        "sync",
        help="Sync CLAUDE.md, GEMINI.md, and AGENTS.md",
    )
    c_sync.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Report changes without writing (default)",
    )
    c_sync.add_argument(
        "--write",
        action="store_true",
        help="Actually write changes (overrides --dry-run)",
    )
    c_sync.add_argument(
        "--organ",
        default=None,
        help="Filter to specific organ",
    )

    # organism
    org_cmd = sub.add_parser(
        "organism",
        help="Living data organism — unified system snapshot",
    )
    org_cmd.add_argument(
        "--workspace",
        default=None,
        help="Workspace root directory",
    )
    org_cmd.add_argument(
        "--organ",
        default=None,
        help="Zoom to specific organ",
    )
    org_cmd.add_argument(
        "--repo",
        default=None,
        help="Zoom to specific repo",
    )
    org_cmd.add_argument(
        "--json",
        action="store_true",
        help="Output JSON",
    )
    org_cmd.add_argument(
        "--omega",
        action="store_true",
        help="Include omega scorecard",
    )
    org_sub = org_cmd.add_subparsers(dest="subcommand")
    org_snap = org_sub.add_parser(
        "snapshot",
        help="Write system-organism.json snapshot to corpus",
    )
    org_snap.add_argument(
        "--workspace",
        default=None,
        help="Workspace root directory",
    )
    org_snap.add_argument(
        "--omega",
        action="store_true",
        help="Include omega scorecard",
    )
    org_snap.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview without writing (default)",
    )
    org_snap.add_argument(
        "--write",
        action="store_true",
        help="Actually write snapshot (overrides --dry-run)",
    )

    # session
    sess = sub.add_parser(
        "session",
        help="Session transcript management and export",
    )
    sess_sub = sess.add_subparsers(dest="subcommand")

    sess_sub.add_parser("projects", help="List Claude Code project directories")

    sess_list = sess_sub.add_parser("list", help="List sessions with metadata")
    sess_list.add_argument(
        "--project",
        default=None,
        help="Filter to specific project directory name",
    )
    sess_list.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max sessions to show (default 20, 0=all)",
    )

    sess_show = sess_sub.add_parser("show", help="Show session details")
    sess_show.add_argument("session_id", help="Session ID (full or prefix)")

    sess_export = sess_sub.add_parser(
        "export",
        help="Export session as praxis-perpetua review",
    )
    sess_export.add_argument("session_id", help="Session ID (full or prefix)")
    sess_export.add_argument(
        "--slug",
        required=True,
        help="Descriptive slug for the filename (e.g., 'gemini-styx-research')",
    )
    sess_export.add_argument(
        "--output",
        default=None,
        help="Output directory (default: praxis-perpetua/sessions/)",
    )
    sess_export.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing",
    )

    sess_transcript = sess_sub.add_parser(
        "transcript",
        help="Render full session transcript as readable markdown",
    )
    sess_transcript.add_argument("session_id", help="Session ID (full or prefix)")
    sess_transcript.add_argument(
        "--output",
        default=None,
        help="Write to file instead of stdout",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    dispatch = {
        ("registry", "show"): cmd_registry_show,
        ("registry", "list"): cmd_registry_list,
        ("registry", "search"): cmd_registry_search,
        ("registry", "deps"): cmd_registry_deps,
        ("registry", "stats"): cmd_registry_stats,
        ("registry", "validate"): cmd_registry_validate,
        ("registry", "update"): cmd_registry_update,
        ("governance", "audit"): cmd_governance_audit,
        ("governance", "check-deps"): cmd_governance_checkdeps,
        ("governance", "promote"): cmd_governance_promote,
        ("governance", "impact"): cmd_governance_impact,
        ("seed", "discover"): cmd_seed_discover,
        ("seed", "validate"): cmd_seed_validate,
        ("seed", "graph"): cmd_seed_graph,
        ("metrics", "calculate"): cmd_metrics_calculate,
        ("metrics", "count-words"): cmd_metrics_count_words,
        ("metrics", "propagate"): cmd_metrics_propagate,
        ("metrics", "refresh"): cmd_metrics_refresh,
        ("dispatch", "validate"): cmd_dispatch_validate,
        ("git", "init-superproject"): cmd_git_init_superproject,
        ("git", "add-submodule"): cmd_git_add_submodule,
        ("git", "sync-organ"): cmd_git_sync_organ,
        ("git", "sync-all"): cmd_git_sync_all,
        ("git", "status"): cmd_git_status,
        ("git", "reproduce-workspace"): cmd_git_reproduce,
        ("git", "diff-pinned"): cmd_git_diff_pinned,
        ("git", "install-hooks"): cmd_git_install_hooks,
        ("ci", "triage"): cmd_ci_triage,
        ("pitch", "generate"): cmd_pitch_generate,
        ("pitch", "sync"): cmd_pitch_sync,
        ("context", "sync"): cmd_context_sync,
        ("omega", "status"): cmd_omega_status,
        ("omega", "check"): cmd_omega_check,
        ("omega", "update"): cmd_omega_update,
    }

    # Handle top-level commands (no subcommand)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "deadlines":
        return cmd_deadlines(args)
    if args.command == "organism":
        if getattr(args, "subcommand", None) == "snapshot":
            return cmd_organism_snapshot(args)
        return cmd_organism(args)
    if args.command == "session":
        session_dispatch = {
            "projects": cmd_session_projects,
            "list": cmd_session_list,
            "show": cmd_session_show,
            "export": cmd_session_export,
            "transcript": cmd_session_transcript,
        }
        handler = session_dispatch.get(getattr(args, "subcommand", "") or "")
        if handler:
            return handler(args)
        parser.parse_args(["session", "--help"])
        return 0

    subcommand: str | None = getattr(args, "subcommand", None)
    handler = dispatch.get((args.command, subcommand or ""))
    if handler:
        return handler(args)

    parser.parse_args([args.command, "--help"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
