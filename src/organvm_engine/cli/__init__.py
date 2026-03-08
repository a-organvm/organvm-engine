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
    organvm prompts narrate [--agent claude|gemini|codex] [--project FILTER] [--output FILE] [--summary FILE] [--dry-run] [--gap-hours 24]
    organvm plans atomize [--plans-dir DIR] [--output FILE] [--summary FILE] [--dry-run]
    organvm atoms link [--threshold 0.25] [--by-thread] [--json] [--output FILE]
"""

import argparse
import os
import sys
from pathlib import Path

from organvm_engine.cli.atoms import (
    cmd_atoms_fanout,
    cmd_atoms_link,
    cmd_atoms_pipeline,
    cmd_atoms_reconcile,
)
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
from organvm_engine.cli.lint_vars import cmd_lint_vars
from organvm_engine.cli.metrics import (
    cmd_metrics_calculate,
    cmd_metrics_count_words,
    cmd_metrics_propagate,
    cmd_metrics_refresh,
)
from organvm_engine.cli.omega import cmd_omega_check, cmd_omega_status, cmd_omega_update
from organvm_engine.cli.organism import cmd_organism, cmd_organism_snapshot
from organvm_engine.cli.pitch import cmd_pitch_generate, cmd_pitch_sync
from organvm_engine.cli.plans import (
    cmd_plans_atomize,
    cmd_plans_audit,
    cmd_plans_index,
    cmd_plans_overlaps,
    cmd_plans_sweep,
    cmd_plans_tidy,
)
from organvm_engine.cli.prompts import (
    cmd_prompts_audit,
    cmd_prompts_clipboard,
    cmd_prompts_distill,
    cmd_prompts_narrate,
)
from organvm_engine.cli.refresh import cmd_refresh
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
from organvm_engine.cli.sop import (
    cmd_sop_audit,
    cmd_sop_check,
    cmd_sop_discover,
    cmd_sop_init,
    cmd_sop_resolve,
)
from organvm_engine.cli.session import (
    cmd_session_agents,
    cmd_session_analyze,
    cmd_session_export,
    cmd_session_list,
    cmd_session_plans,
    cmd_session_projects,
    cmd_session_prompts,
    cmd_session_review,
    cmd_session_show,
    cmd_session_transcript,
)
from organvm_engine.cli.status import cmd_status
from organvm_engine.cli.study import (
    cmd_study_audit_report,
    cmd_study_consilience,
    cmd_study_feedback,
)
from organvm_engine.paths import registry_path as _default_registry_path
from organvm_engine.paths import resolve_workspace as _resolve_workspace


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

    # refresh
    ref = sub.add_parser(
        "refresh",
        help="Unified refresh: metrics + variables + propagation + context + organism",
    )
    ref.add_argument(
        "--workspace",
        default=None,
        help="Workspace root directory",
    )
    ref.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing",
    )
    ref.add_argument(
        "--skip-context",
        action="store_true",
        help="Skip context file sync",
    )
    ref.add_argument(
        "--skip-organism",
        action="store_true",
        help="Skip organism snapshot",
    )
    ref.add_argument(
        "--skip-legacy",
        action="store_true",
        help="Skip legacy regex propagation",
    )
    ref.add_argument(
        "--skip-plans",
        action="store_true",
        help="Skip plan hygiene check",
    )
    ref.add_argument(
        "--skip-sop",
        action="store_true",
        help="Skip SOP inventory check",
    )
    ref.add_argument(
        "--skip-atoms",
        action="store_true",
        help="Skip atoms pipeline + fanout",
    )

    # lint-vars
    lv = sub.add_parser(
        "lint-vars",
        help="Check for unbound metric references in markdown",
    )
    lv.add_argument(
        "--workspace",
        default=None,
        help="Workspace root directory",
    )
    lv.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if violations found",
    )

    # session
    sess = sub.add_parser(
        "session",
        help="Session transcript management and export",
    )
    sess_sub = sess.add_subparsers(dest="subcommand")

    sess_sub.add_parser("projects", help="List Claude Code project directories")
    sess_sub.add_parser("agents", help="Show session inventory across all agents")

    sess_list = sess_sub.add_parser("list", help="List sessions with metadata")
    sess_list.add_argument(
        "--project",
        default=None,
        help="Filter to specific project directory name or path substring",
    )
    sess_list.add_argument(
        "--agent",
        default=None,
        choices=["claude", "gemini", "codex"],
        help="Filter to specific agent (default: all)",
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
        help="Render session transcript (ephemeral view, not committed)",
    )
    sess_transcript.add_argument("session_id", help="Session ID (full or prefix)")
    sess_transcript.add_argument(
        "--unabridged",
        action="store_true",
        help="Full audit trail: thinking blocks, tool I/O, generated code",
    )
    sess_transcript.add_argument(
        "--output",
        default=None,
        help="Write to file instead of stdout",
    )

    sess_prompts = sess_sub.add_parser(
        "prompts",
        help="Extract prompts only — for drift detection and pattern analysis",
    )
    sess_prompts.add_argument("session_id", help="Session ID (full or prefix)")
    sess_prompts.add_argument(
        "--output",
        default=None,
        help="Write to file instead of stdout",
    )

    # plans
    sess_plans = sess_sub.add_parser(
        "plans",
        help="List or audit plan files across the workspace",
    )
    sess_plans.add_argument(
        "--project",
        default=None,
        help="Filter by project path substring",
    )
    sess_plans.add_argument(
        "--since",
        default=None,
        help="Only plans on or after this date (YYYY-MM-DD)",
    )
    sess_plans.add_argument(
        "--audit",
        action="store_true",
        help="Render plan-vs-reality audit scaffold",
    )
    sess_plans.add_argument(
        "--agent",
        default=None,
        choices=["claude", "gemini", "codex", "governance"],
        help="Filter by agent",
    )
    sess_plans.add_argument(
        "--organ",
        default=None,
        help="Filter by organ key (I, II, ..., META)",
    )
    sess_plans.add_argument(
        "--matrix",
        action="store_true",
        help="Show agent × organ count matrix",
    )

    # analyze
    sess_analyze = sess_sub.add_parser(
        "analyze",
        help="Cross-session prompt analysis",
    )
    sess_analyze.add_argument(
        "--agent",
        default=None,
        choices=["claude", "gemini", "codex"],
        help="Filter to specific agent",
    )
    sess_analyze.add_argument(
        "--full",
        action="store_true",
        help="Analyze all sessions (slow)",
    )
    sess_analyze.add_argument(
        "--output",
        default=None,
        help="Write report to file",
    )

    # review
    sess_review = sess_sub.add_parser(
        "review",
        help="Review a session: summary, prompts, related plans",
    )
    sess_review.add_argument(
        "session_id",
        nargs="?",
        default=None,
        help="Session ID (full or prefix)",
    )
    sess_review.add_argument(
        "--latest",
        action="store_true",
        help="Review the most recent session",
    )
    sess_review.add_argument(
        "--project",
        default=None,
        help="Filter to project when using --latest",
    )

    # prompts
    prompts = sub.add_parser("prompts", help="Prompt narrative analysis")
    prompts_sub = prompts.add_subparsers(dest="subcommand")

    prompts_narrate = prompts_sub.add_parser(
        "narrate",
        help="Extract, classify, and thread prompts into narrative arcs",
    )
    prompts_narrate.add_argument(
        "--agent",
        default=None,
        choices=["claude", "gemini", "codex"],
        help="Filter to specific agent",
    )
    prompts_narrate.add_argument(
        "--project",
        default=None,
        help="Filter to specific project directory name or path substring",
    )
    prompts_narrate.add_argument(
        "--output",
        default=None,
        help="Output JSONL file path (default: ~/.claude/prompts/annotated-prompts.jsonl)",
    )
    prompts_narrate.add_argument(
        "--summary",
        default=None,
        help="Output summary .md path (default: ~/.claude/prompts/NARRATIVE-SUMMARY.md)",
    )
    prompts_narrate.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse all sessions, print stats, write nothing",
    )
    prompts_narrate.add_argument(
        "--gap-hours",
        type=float,
        default=24.0,
        help="Hours gap to split episodes (default 24)",
    )

    prompts_clipboard = prompts_sub.add_parser(
        "clipboard",
        help="Extract and classify AI prompts from Paste.app clipboard history",
    )
    prompts_clipboard.add_argument(
        "--db-path",
        default=None,
        help="Path to Paste.app SQLite database (default: standard macOS location)",
    )
    prompts_clipboard.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for export files",
    )
    prompts_clipboard.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and classify but write nothing",
    )
    prompts_clipboard.add_argument(
        "--json-only",
        action="store_true",
        help="Only write JSON export",
    )
    prompts_clipboard.add_argument(
        "--md-only",
        action="store_true",
        help="Only write Markdown export",
    )

    prompts_audit = prompts_sub.add_parser(
        "audit",
        help="Run prompt & pipeline data audit — noise, completion, linking quality",
    )
    prompts_audit.add_argument(
        "--output",
        default=None,
        help="Output file path (default: <atoms-dir>/AUDIT-REPORT.md)",
    )
    prompts_audit.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON instead of writing report",
    )
    prompts_audit.add_argument(
        "--noise-only",
        action="store_true",
        help="Run only the noise analysis",
    )

    prompts_distill = prompts_sub.add_parser(
        "distill",
        help="Distill clipboard prompts into operational patterns and SOP coverage",
    )
    prompts_distill.add_argument(
        "--input",
        default=None,
        help="Input clipboard prompts JSON file (default: <atoms-dir>/clipboard-prompts.json)",
    )
    prompts_distill.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for generated SOP scaffolds (default: .sops/)",
    )
    prompts_distill.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Analyze but write nothing (default)",
    )
    prompts_distill.add_argument(
        "--write",
        action="store_true",
        help="Actually write scaffold files",
    )
    prompts_distill.add_argument(
        "--json",
        action="store_true",
        help="Output coverage report as JSON",
    )
    prompts_distill.add_argument(
        "--scaffold",
        action="store_true",
        help="Generate SOP scaffold files for uncovered patterns",
    )

    # plans
    plans = sub.add_parser("plans", help="Plan file analysis and atomization")
    plans_sub = plans.add_subparsers(dest="subcommand")

    plans_atomize = plans_sub.add_parser(
        "atomize",
        help="Atomize plan files into atomic tasks with rich metadata",
    )
    plans_atomize.add_argument(
        "--plans-dir",
        default=None,
        help="Root directory containing plan .md files (default: ~/.claude/plans)",
    )
    plans_atomize.add_argument(
        "--output",
        default=None,
        help="Output JSONL file path (default: <plans-dir>/atomized-tasks.jsonl)",
    )
    plans_atomize.add_argument(
        "--summary",
        default=None,
        help="Output summary .md path (default: <plans-dir>/ATOMIZED-SUMMARY.md)",
    )
    plans_atomize.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse all files, print stats, write nothing",
    )
    plans_atomize.add_argument(
        "--all",
        action="store_true",
        help="Discover from entire workspace (multi-agent) instead of single --plans-dir",
    )
    plans_atomize.add_argument(
        "--agent",
        default=None,
        choices=["claude", "gemini", "codex"],
        help="Filter source plans by agent (requires --all)",
    )
    plans_atomize.add_argument(
        "--organ",
        default=None,
        help="Filter source plans by organ key (requires --all)",
    )

    plans_index = plans_sub.add_parser(
        "index",
        help="Build and display plan index (machine-readable snapshot)",
    )
    plans_index.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of table",
    )
    plans_index.add_argument(
        "--write",
        action="store_true",
        help="Write plan-index.json to corpus data/plans/",
    )
    plans_index.add_argument(
        "--agent",
        default=None,
        choices=["claude", "gemini", "codex"],
        help="Filter by agent",
    )
    plans_index.add_argument(
        "--organ",
        default=None,
        help="Filter by organ key",
    )

    plans_audit = plans_sub.add_parser(
        "audit",
        help="Flag stale plans, duplicates, and orphans",
    )
    plans_audit.add_argument(
        "--organ",
        default=None,
        help="Filter by organ key",
    )
    plans_audit.add_argument(
        "--stale-days",
        type=int,
        default=30,
        help="Days threshold for stale detection (default 30)",
    )

    plans_overlaps = plans_sub.add_parser(
        "overlaps",
        help="Show overlapping plan clusters",
    )
    plans_overlaps.add_argument(
        "--severity",
        default=None,
        choices=["conflict", "warning", "info"],
        help="Filter by severity level",
    )
    plans_overlaps.add_argument(
        "--organ",
        default=None,
        help="Filter by organ key",
    )

    plans_sweep = plans_sub.add_parser(
        "sweep",
        help="List archival candidates (read-only)",
    )
    plans_sweep.add_argument(
        "--stale-days",
        type=int,
        default=14,
        help="Days threshold for stale detection (default 14)",
    )
    plans_sweep.add_argument(
        "--agent",
        default=None,
        choices=["claude", "gemini", "codex"],
        help="Filter by agent",
    )
    plans_sweep.add_argument(
        "--organ",
        default=None,
        help="Filter by organ key",
    )
    plans_sweep.add_argument(
        "--json",
        action="store_true",
        help="Output JSON",
    )

    plans_tidy = plans_sub.add_parser(
        "tidy",
        help="Archive eligible plans (dry-run by default)",
    )
    plans_tidy.add_argument(
        "--stale-days",
        type=int,
        default=14,
        help="Days threshold for stale detection (default 14)",
    )
    plans_tidy.add_argument(
        "--include-review",
        action="store_true",
        help="Include stale plans (review confidence) in archival",
    )
    plans_tidy.add_argument(
        "--agent",
        default=None,
        choices=["claude", "gemini", "codex"],
        help="Filter by agent",
    )
    plans_tidy.add_argument(
        "--organ",
        default=None,
        help="Filter by organ key",
    )
    plans_tidy.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview without moving files (default)",
    )
    plans_tidy.add_argument(
        "--write",
        action="store_true",
        help="Actually move files (overrides --dry-run)",
    )

    # sop
    sop = sub.add_parser("sop", help="SOP discovery and inventory tracking")
    sop.add_argument(
        "--workspace",
        default=None,
        help="Workspace root directory",
    )
    sop.add_argument(
        "--organ",
        default=None,
        help="Filter to specific organ",
    )
    sop_sub = sop.add_subparsers(dest="subcommand")

    sop_discover = sop_sub.add_parser("discover", help="Find all SOP/METADOC files")
    sop_discover.add_argument("--json", action="store_true", help="Output JSON")

    sop_sub.add_parser("audit", help="Compare discovered SOPs against METADOC inventory")

    sop_check = sop_sub.add_parser(
        "check",
        help="Exit non-zero if untracked SOPs exist",
    )
    sop_check.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 on any untracked or missing SOPs",
    )

    sop_resolve = sop_sub.add_parser(
        "resolve",
        help="Show active SOPs for a given context",
    )
    sop_resolve.add_argument("name", nargs="?", default=None, help="SOP name to resolve")
    sop_resolve.add_argument("--repo", default=None, help="Filter to specific repo")
    sop_resolve.add_argument(
        "--phase",
        default=None,
        choices=["genesis", "foundation", "hardening", "graduation", "sustaining", "any"],
        help="Filter to lifecycle phase",
    )

    sop_init = sop_sub.add_parser(
        "init",
        help="Scaffold a .sops/ directory with template",
    )
    sop_init.add_argument(
        "--scope",
        choices=["repo", "organ"],
        default="repo",
        help="Scope of the new SOP (default: repo)",
    )
    sop_init.add_argument("--name", default=None, help="SOP name (default: new-procedure)")

    # study
    study = sub.add_parser(
        "study",
        help="Study Suite — feedback loops, consilience index, combined audit",
    )
    study_sub = study.add_subparsers(dest="subcommand")

    study_feedback = study_sub.add_parser(
        "feedback",
        help="Show the feedback loop inventory (positive and negative)",
    )
    study_feedback.add_argument("--json", action="store_true", help="Output JSON")
    study_feedback.add_argument(
        "--polarity",
        choices=["positive", "negative"],
        default=None,
        help="Filter by loop polarity",
    )

    study_consilience = study_sub.add_parser(
        "consilience",
        help="Compute and display the consilience index for derived principles",
    )
    study_consilience.add_argument("--json", action="store_true", help="Output JSON")

    study_audit = study_sub.add_parser(
        "audit",
        help="Combined governance + feedback + consilience audit report",
    )
    study_audit.add_argument("--json", action="store_true", help="Output JSON")
    study_audit.add_argument(
        "--output",
        default=None,
        help="Write report to file instead of stdout",
    )

    # atoms
    atoms = sub.add_parser("atoms", help="Cross-system atom linking")
    atoms_sub = atoms.add_subparsers(dest="subcommand")

    atoms_link = atoms_sub.add_parser(
        "link",
        help="Link atomized tasks to annotated prompts by content similarity",
    )
    atoms_link.add_argument(
        "--threshold",
        type=float,
        default=0.30,
        help="Minimum Jaccard similarity (default 0.30)",
    )
    atoms_link.add_argument(
        "--by-thread",
        action="store_true",
        help="Aggregate prompts per thread before comparison (higher recall)",
    )
    atoms_link.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of table",
    )
    atoms_link.add_argument(
        "--output",
        default=None,
        help="Write output to file",
    )
    atoms_link.add_argument(
        "--tasks",
        default=None,
        help="Path to atomized-tasks.jsonl (default: ~/.claude/plans/atomized-tasks.jsonl)",
    )
    atoms_link.add_argument(
        "--prompts",
        default=None,
        help="Path to annotated-prompts.jsonl",
    )

    atoms_pipeline = atoms_sub.add_parser(
        "pipeline",
        help="Run the full atomization pipeline (atomize → narrate → link → index)",
    )
    atoms_pipeline.add_argument(
        "--write",
        action="store_true",
        help="Execute pipeline and write files (default is dry-run)",
    )
    atoms_pipeline.add_argument(
        "--skip-narrate",
        action="store_true",
        help="Skip prompt narration step",
    )
    atoms_pipeline.add_argument(
        "--skip-link",
        action="store_true",
        help="Skip cross-system linking step",
    )
    atoms_pipeline.add_argument(
        "--agent",
        default=None,
        choices=["claude", "gemini", "codex"],
        help="Filter by agent",
    )
    atoms_pipeline.add_argument(
        "--organ",
        default=None,
        help="Filter by organ key",
    )
    atoms_pipeline.add_argument(
        "--threshold",
        type=float,
        default=0.30,
        help="Minimum Jaccard similarity for linking (default 0.30)",
    )
    atoms_pipeline.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: corpus data/atoms/)",
    )
    atoms_pipeline.add_argument(
        "--reconcile",
        action="store_true",
        default=True,
        help="Run git-based task reconciliation after pipeline (default: on)",
    )
    atoms_pipeline.add_argument(
        "--skip-reconcile",
        action="store_true",
        help="Skip git-based reconciliation step",
    )

    atoms_reconcile = atoms_sub.add_parser(
        "reconcile",
        help="Cross-reference tasks against git history to detect completed work",
    )
    atoms_reconcile.add_argument(
        "--write",
        action="store_true",
        help="Rewrite tasks JSONL with updated statuses",
    )
    atoms_reconcile.add_argument(
        "--since",
        default=None,
        help="Only check git log since this date (default: plan date)",
    )
    atoms_reconcile.add_argument(
        "--workspace",
        default=None,
        help="Workspace root directory",
    )

    atoms_fanout = atoms_sub.add_parser(
        "fanout",
        help="Fan out atom data to per-organ rollup JSON files",
    )
    atoms_fanout.add_argument(
        "--write",
        action="store_true",
        help="Execute fanout (default is dry-run)",
    )
    atoms_fanout.add_argument(
        "--atoms-dir",
        default=None,
        help="Path to centralized atoms directory (default: corpus data/atoms/)",
    )
    atoms_fanout.add_argument(
        "--workspace",
        default=None,
        help="Workspace root directory",
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
    if args.command == "refresh":
        return cmd_refresh(args)
    if args.command == "lint-vars":
        return cmd_lint_vars(args)
    if args.command == "organism":
        if getattr(args, "subcommand", None) == "snapshot":
            return cmd_organism_snapshot(args)
        return cmd_organism(args)
    if args.command == "atoms":
        atoms_dispatch = {
            "link": cmd_atoms_link,
            "pipeline": cmd_atoms_pipeline,
            "reconcile": cmd_atoms_reconcile,
            "fanout": cmd_atoms_fanout,
        }
        handler = atoms_dispatch.get(getattr(args, "subcommand", "") or "")
        if handler:
            return handler(args)
        parser.parse_args(["atoms", "--help"])
        return 0
    if args.command == "prompts":
        prompts_dispatch = {
            "narrate": cmd_prompts_narrate,
            "clipboard": cmd_prompts_clipboard,
            "audit": cmd_prompts_audit,
            "distill": cmd_prompts_distill,
        }
        handler = prompts_dispatch.get(getattr(args, "subcommand", "") or "")
        if handler:
            return handler(args)
        parser.parse_args(["prompts", "--help"])
        return 0
    if args.command == "plans":
        plans_dispatch = {
            "atomize": cmd_plans_atomize,
            "index": cmd_plans_index,
            "audit": cmd_plans_audit,
            "overlaps": cmd_plans_overlaps,
            "sweep": cmd_plans_sweep,
            "tidy": cmd_plans_tidy,
        }
        handler = plans_dispatch.get(getattr(args, "subcommand", "") or "")
        if handler:
            return handler(args)
        parser.parse_args(["plans", "--help"])
        return 0
    if args.command == "study":
        study_dispatch = {
            "feedback": cmd_study_feedback,
            "consilience": cmd_study_consilience,
            "audit": cmd_study_audit_report,
        }
        handler = study_dispatch.get(getattr(args, "subcommand", "") or "")
        if handler:
            return handler(args)
        parser.parse_args(["study", "--help"])
        return 0
    if args.command == "sop":
        sop_dispatch = {
            "discover": cmd_sop_discover,
            "audit": cmd_sop_audit,
            "check": cmd_sop_check,
            "resolve": cmd_sop_resolve,
            "init": cmd_sop_init,
        }
        handler = sop_dispatch.get(getattr(args, "subcommand", "") or "")
        if handler:
            return handler(args)
        parser.parse_args(["sop", "--help"])
        return 0
    if args.command == "session":
        session_dispatch = {
            "projects": cmd_session_projects,
            "agents": cmd_session_agents,
            "list": cmd_session_list,
            "show": cmd_session_show,
            "export": cmd_session_export,
            "transcript": cmd_session_transcript,
            "prompts": cmd_session_prompts,
            "plans": cmd_session_plans,
            "analyze": cmd_session_analyze,
            "review": cmd_session_review,
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
