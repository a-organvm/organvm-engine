"""CLI commands for network testament — external mirror mapping and engagement.

Subcommands:
    organvm network scan [--organ X] [--repo X] [--dry-run]
    organvm network map [--organ X] [--repo X] [--json]
    organvm network log <repo> <project> --action <type> --detail "..."
    organvm network status [--organ X] [--json]
    organvm network synthesize [--period weekly|monthly] [--write]
    organvm network suggest [--organ X] [--repo X]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from organvm_engine.network import ENGAGEMENT_FORMS, MIRROR_LENSES, NETWORK_MAP_FILENAME


def _workspace_root(args: argparse.Namespace) -> Path:
    from organvm_engine.paths import workspace_root

    ws = getattr(args, "workspace", None)
    return Path(ws) if ws else workspace_root()


def _count_active_repos(workspace: Path) -> int:
    """Count active repos from registry if available, else estimate from workspace."""
    try:
        from organvm_engine.registry.loader import load_registry
        from organvm_engine.registry.query import list_repos

        registry = load_registry()
        all_repos = list_repos(registry)
        return sum(
            1 for r in all_repos
            if r.get("status") not in ("ARCHIVED", "DEPRECATED")
        )
    except Exception:
        # Fallback: count directories with seed.yaml
        count = 0
        for organ_dir in workspace.iterdir():
            if not organ_dir.is_dir() or organ_dir.name.startswith("."):
                continue
            for repo_dir in organ_dir.iterdir():
                if repo_dir.is_dir() and (repo_dir / "seed.yaml").exists():
                    count += 1
        return count or 1  # avoid division by zero


def _resolve_organ_key(dir_name: str) -> str:
    """Resolve organ key from directory name using organ_config if available."""
    try:
        from organvm_engine.organ_config import dir_to_registry_key

        mapping = dir_to_registry_key()
        return mapping.get(dir_name, dir_name.upper())
    except (ImportError, Exception):
        return dir_name.upper()


def cmd_network_scan(args: argparse.Namespace) -> int:
    """Scan repos for potential mirrors and suggest additions."""
    from organvm_engine.network.mapper import (
        merge_mirrors,
        read_network_map,
        write_network_map,
    )
    from organvm_engine.network.scanner import scan_repo_dependencies
    from organvm_engine.network.schema import NetworkMap

    workspace = _workspace_root(args)
    repo_filter = getattr(args, "repo", None)
    do_write = getattr(args, "write", False)

    scanned = 0
    total_mirrors = 0
    written = 0

    for organ_dir in sorted(workspace.iterdir()):
        if not organ_dir.is_dir() or organ_dir.name.startswith("."):
            continue
        organ_name = getattr(args, "organ", None)
        if organ_name and organ_dir.name != organ_name:
            continue

        for repo_dir in sorted(organ_dir.iterdir()):
            if not repo_dir.is_dir() or repo_dir.name.startswith("."):
                continue
            if repo_filter and repo_dir.name != repo_filter:
                continue

            mirrors = scan_repo_dependencies(repo_dir)
            if mirrors:
                scanned += 1
                total_mirrors += len(mirrors)
                print(f"\n{organ_dir.name}/{repo_dir.name}: {len(mirrors)} technical mirrors")
                for m in mirrors:
                    print(f"  - {m.project} ({m.relevance})")

                if do_write:
                    nmap_path = repo_dir / NETWORK_MAP_FILENAME
                    if nmap_path.exists():
                        existing = read_network_map(nmap_path)
                        existing.technical = merge_mirrors(existing.technical, mirrors)
                        existing.last_scanned = datetime.now(timezone.utc).isoformat()
                        write_network_map(existing, nmap_path)
                    else:
                        organ_key = _resolve_organ_key(organ_dir.name)
                        nmap = NetworkMap(
                            schema_version="1.0",
                            repo=repo_dir.name,
                            organ=organ_key,
                            technical=mirrors,
                            last_scanned=datetime.now(timezone.utc).isoformat(),
                        )
                        write_network_map(nmap, nmap_path)
                    written += 1

    if do_write:
        print(f"\nWritten: {written} network-map.yaml files ({total_mirrors} mirrors)")
    else:
        print(f"\n[dry-run] Scanned repos with findings: {scanned}, mirrors: {total_mirrors}")
        print("Run with --write to update network-map.yaml files")
    return 0


def cmd_network_map(args: argparse.Namespace) -> int:
    """Show the network map for a repo or organ."""
    from organvm_engine.network.mapper import discover_network_maps

    workspace = _workspace_root(args)
    repo_filter = getattr(args, "repo", None)
    as_json = getattr(args, "json", False)

    pairs = discover_network_maps(workspace)

    if repo_filter:
        pairs = [(p, m) for p, m in pairs if m.repo == repo_filter]

    if not pairs:
        print("No network maps found.")
        return 0

    if as_json:
        data = [m.to_dict() for _, m in pairs]
        print(json.dumps(data, indent=2))
    else:
        for _path, nmap in pairs:
            print(f"\n{nmap.organ}/{nmap.repo} ({nmap.mirror_count} mirrors)")
            for lens in ("technical", "parallel", "kinship"):
                entries = nmap.mirrors_by_lens(lens)
                if entries:
                    print(f"  {lens}:")
                    for e in entries:
                        print(f"    - {e.project} [{e.platform}] — {e.relevance}")

    return 0


def cmd_network_log(args: argparse.Namespace) -> int:
    """Record an engagement action to the ledger."""
    from organvm_engine.network.ledger import create_engagement, log_engagement

    repo = args.repo
    project = args.project
    lens = args.lens
    action_type = args.action
    detail = args.detail
    url = getattr(args, "url", None)
    outcome = getattr(args, "outcome", None)
    tags_raw = getattr(args, "tags", None)
    tags = tags_raw.split(",") if tags_raw else []

    if lens not in MIRROR_LENSES:
        print(f"Invalid lens: {lens}. Must be one of: {', '.join(sorted(MIRROR_LENSES))}")
        return 1
    if action_type not in ENGAGEMENT_FORMS:
        print(
            f"Invalid action: {action_type}. Must be one of: {', '.join(sorted(ENGAGEMENT_FORMS))}",
        )
        return 1

    entry = create_engagement(
        organvm_repo=repo,
        external_project=project,
        lens=lens,
        action_type=action_type,
        action_detail=detail,
        url=url,
        outcome=outcome,
        tags=tags,
    )
    log_engagement(entry)
    print(f"Logged: {action_type} on {project} (lens={lens})")
    print(f"  Detail: {detail}")
    if url:
        print(f"  URL: {url}")
    return 0


def cmd_network_status(args: argparse.Namespace) -> int:
    """Show network health: coverage, density, velocity."""
    from organvm_engine.network.ledger import ledger_summary
    from organvm_engine.network.mapper import discover_network_maps
    from organvm_engine.network.metrics import (
        convergence_points,
        mirror_coverage,
        network_density,
    )

    workspace = _workspace_root(args)
    as_json = getattr(args, "json", False)

    pairs = discover_network_maps(workspace)
    maps = [m for _, m in pairs]
    summary = ledger_summary()
    active = _count_active_repos(workspace)
    density = network_density(maps, active)
    coverage = mirror_coverage(maps)
    convergences = convergence_points(maps)

    if as_json:
        print(json.dumps({
            "density": density,
            "coverage": coverage,
            "maps_count": len(maps),
            "total_mirrors": sum(m.mirror_count for m in maps),
            "active_repos": active,
            "ledger": summary,
            "convergence_points": len(convergences),
        }, indent=2))
    else:
        print("Network Testament Status")
        print(f"  Maps: {len(maps)} repos with network-map.yaml")
        print(f"  Mirrors: {sum(m.mirror_count for m in maps)} total")
        print(f"  Active repos: {active}")
        print(f"  Density: {density:.1%}")
        print(f"  Coverage — technical: {coverage['technical']:.0%}"
              f" | parallel: {coverage['parallel']:.0%}"
              f" | kinship: {coverage['kinship']:.0%}")
        print(f"  Convergence points: {len(convergences)}")
        print(f"  Ledger: {summary['total_actions']} actions"
              f" across {summary['unique_projects']} projects")

    return 0


def cmd_network_synthesize(args: argparse.Namespace) -> int:
    """Generate narrative testament."""
    from organvm_engine.network.synthesizer import synthesize_testament, write_testament

    workspace = _workspace_root(args)
    period = getattr(args, "period", "monthly")
    write = getattr(args, "write", False)

    active = _count_active_repos(workspace)
    content = synthesize_testament(workspace, period=period, total_active_repos=active)
    print(content)

    if write:
        testament_dir = workspace / "meta-organvm" / "praxis-perpetua" / "testament"
        out = write_testament(content, testament_dir, period)
        print(f"\nWritten to: {out}")

    return 0


def cmd_network_suggest(args: argparse.Namespace) -> int:
    """Generate actionable engagement suggestions from network state."""
    from organvm_engine.network.ledger import ledger_summary, read_ledger
    from organvm_engine.network.mapper import discover_network_maps
    from organvm_engine.network.metrics import (
        convergence_points,
        form_balance,
        lens_balance,
        mirror_coverage,
    )
    from organvm_engine.network.query import blind_spots

    workspace = _workspace_root(args)
    pairs = discover_network_maps(workspace)
    maps = [m for _, m in pairs]
    entries = read_ledger()
    summary = ledger_summary()

    suggestions: list[str] = []

    # 1. Convergence points — high-value targets
    convergences = convergence_points(maps)
    if convergences:
        suggestions.append("## Convergence Points (high-value targets)")
        for project, repos in sorted(convergences.items(), key=lambda x: -len(x[1])):
            suggestions.append(f"  {project} ← {', '.join(repos)}")
        suggestions.append("  → Deepen engagement here: multiple repos connect.")
        suggestions.append("")

    # 2. Blind spots — repos with no mirrors
    all_repo_names: list[str] = []
    for organ_dir in sorted(workspace.iterdir()):
        if not organ_dir.is_dir() or organ_dir.name.startswith("."):
            continue
        for repo_dir in sorted(organ_dir.iterdir()):
            if repo_dir.is_dir() and (repo_dir / "seed.yaml").exists():
                all_repo_names.append(repo_dir.name)

    spots = blind_spots(maps, all_repo_names)
    if spots:
        suggestions.append(f"## Blind Spots ({len(spots)} repos with no mirrors)")
        for repo in spots[:10]:
            suggestions.append(f"  - {repo}")
        if len(spots) > 10:
            suggestions.append(f"  ... and {len(spots) - 10} more")
        suggestions.append("  → Run `organvm network scan` to discover technical mirrors.")
        suggestions.append("")

    # 3. Lens imbalance
    coverage = mirror_coverage(maps)
    if maps:
        weakest = min(coverage, key=coverage.get)  # type: ignore[arg-type]
        if coverage[weakest] < 0.3:
            suggestions.append(f"## Underrepresented Lens: {weakest} ({coverage[weakest]:.0%})")
            suggestions.append(f"  → Actively seek {weakest} mirrors for mapped repos.")
            suggestions.append("")

    # 4. Engagement form imbalance
    if entries:
        forms = form_balance(entries)
        lenses = lens_balance(entries)
        absent_forms = [f for f, v in forms.items() if v == 0.0]
        if absent_forms:
            suggestions.append(f"## Unused Engagement Forms: {', '.join(absent_forms)}")
            suggestions.append("  → Diversify engagement: all four forms are equal.")
            suggestions.append("")
        absent_lenses = [l for l, v in lenses.items() if v == 0.0]
        if absent_lenses:
            suggestions.append(f"## Silent Lenses: {', '.join(absent_lenses)}")
            suggestions.append("  → No engagement logged for these lenses.")
            suggestions.append("")

    # 5. Overall momentum
    if summary["total_actions"] == 0:
        suggestions.append("## Getting Started")
        suggestions.append("  No engagement actions logged yet.")
        suggestions.append("  → Start with `organvm network scan --write` to populate maps.")
        suggestions.append("  → Then log your first action: `organvm network log <repo> <project> ...`")
        suggestions.append("")

    if suggestions:
        print("Network Testament — Suggestions\n")
        print("\n".join(suggestions))
    else:
        print("Network looks healthy. All lenses covered, all forms active.")

    return 0
