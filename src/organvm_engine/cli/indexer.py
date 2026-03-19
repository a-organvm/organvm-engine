"""Index CLI commands — deep structural indexer."""

import argparse
import json


def cmd_index_scan(args: argparse.Namespace) -> int:
    """Run the deep structural index across the workspace."""
    from pathlib import Path

    from organvm_engine.indexer import run_deep_index
    from organvm_engine.paths import workspace_root
    from organvm_engine.registry.loader import load_registry

    registry = load_registry(args.registry)
    workspace = Path(args.workspace) if getattr(args, "workspace", None) else workspace_root()
    repo_filter = getattr(args, "repo", None)
    organ_filter = getattr(args, "organ", None)

    index = run_deep_index(workspace, registry, repo_filter, organ_filter)

    if getattr(args, "json", False):
        print(json.dumps(index.to_dict(), indent=2))
        return 0

    print("Deep Structural Index")
    print("=" * 70)
    print(f"  Scanned repos: {index.scanned_repos}")
    print(f"  Total components: {index.total_components}")

    if index.by_organ:
        print("\n  By organ:")
        for organ, count in sorted(index.by_organ.items()):
            print(f"    {organ:14s}  {count}")

    if index.by_cohesion:
        print("\n  By cohesion type:")
        for ctype, count in sorted(index.by_cohesion.items(), key=lambda x: -x[1]):
            print(f"    {ctype:20s}  {count}")

    if index.by_language:
        print("\n  By language:")
        for lang, count in sorted(index.by_language.items(), key=lambda x: -x[1]):
            print(f"    {lang:15s}  {count}")

    if getattr(args, "write", False):
        from organvm_engine.paths import corpus_dir

        out_dir = corpus_dir() / "data" / "index"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "deep-index.json"
        out_path.write_text(json.dumps(index.to_dict(), indent=2))
        print(f"\n  Written to: {out_path}")

    return 0


def cmd_index_show(args: argparse.Namespace) -> int:
    """Show component tree for a single repo."""
    from pathlib import Path

    from organvm_engine.indexer import index_repo
    from organvm_engine.organ_config import registry_key_to_dir
    from organvm_engine.paths import workspace_root
    from organvm_engine.registry.loader import load_registry
    from organvm_engine.registry.query import find_repo

    registry = load_registry(args.registry)
    result = find_repo(registry, args.repo)
    if not result:
        print(f"ERROR: Repo '{args.repo}' not found")
        return 1

    organ_key, repo = result
    r2d = registry_key_to_dir()
    organ_dir = r2d.get(organ_key, "")
    workspace = Path(args.workspace) if getattr(args, "workspace", None) else workspace_root()
    repo_path = workspace / organ_dir / repo["name"]

    idx = index_repo(repo_path, repo["name"], organ_key)

    if getattr(args, "json", False):
        print(json.dumps(idx.to_dict(), indent=2))
        return 0

    print(f"  Repo: {idx.repo} ({idx.organ})")
    print(f"  Total files: {idx.total_files}")
    print(f"  Total lines: {idx.total_lines}")
    print(f"  Max depth: {idx.max_depth}")
    print(f"  Components: {len(idx.components)}")

    if idx.components:
        print(
            f"\n  {'Path':40s} {'Type':18s} {'Files':>5s}"
            f" {'Lines':>6s} {'Lang':>10s}",
        )
        print("  " + "-" * 82)
        for comp in sorted(idx.components, key=lambda c: c.path):
            print(
                f"  {comp.path:40s} {comp.cohesion_type:18s} "
                f"{comp.file_count:5d} {comp.line_count:6d} "
                f"{comp.dominant_language:>10s}",
            )

        has_imports = any(c.imports_from for c in idx.components)
        if has_imports:
            print("\n  Import Graph:")
            for comp in idx.components:
                if comp.imports_from:
                    comp_name = comp.path.rstrip("/").split("/")[-1]
                    for imp in comp.imports_from:
                        imp_name = imp.rstrip("/").split("/")[-1]
                        print(f"    {comp_name} -> {imp_name}")

    return 0


def cmd_index_bridge(args: argparse.Namespace) -> int:
    """Register indexed components as ontologia entities."""
    from pathlib import Path

    from organvm_engine.indexer import run_deep_index
    from organvm_engine.indexer.bridge import register_components
    from organvm_engine.paths import workspace_root
    from organvm_engine.registry.loader import load_registry

    registry = load_registry(args.registry)
    workspace = Path(args.workspace) if getattr(args, "workspace", None) else workspace_root()
    repo_filter = getattr(args, "repo", None)
    organ_filter = getattr(args, "organ", None)

    index = run_deep_index(workspace, registry, repo_filter, organ_filter)

    if getattr(args, "json", False):
        result = register_components(index)
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    result = register_components(index)

    print("Indexer → Ontologia Bridge")
    print("=" * 50)
    print(f"  Components created: {result.components_created}")
    print(f"  Components skipped: {result.components_skipped}")
    print(f"  Hierarchy edges:    {result.edges_created}")
    if result.errors:
        print(f"\n  Errors ({len(result.errors)}):")
        for err in result.errors[:10]:
            print(f"    {err}")

    return 0


def cmd_index_stats(args: argparse.Namespace) -> int:
    """Show system-wide component statistics from cached scan."""
    from pathlib import Path

    out_path_check: Path | None = None
    try:
        from organvm_engine.paths import corpus_dir

        out_path_check = corpus_dir() / "data" / "index" / "deep-index.json"
    except Exception:
        pass

    if out_path_check and out_path_check.is_file():
        data = json.loads(out_path_check.read_text())
        print("Deep Index Statistics (from cached scan)")
        print("=" * 50)
        print(f"  Scanned repos: {data.get('scanned_repos', 0)}")
        print(f"  Total components: {data.get('total_components', 0)}")
        print(f"  Scan timestamp: {data.get('scan_timestamp', 'unknown')}")

        if data.get("by_organ"):
            print("\n  By organ:")
            for organ, count in sorted(data["by_organ"].items()):
                print(f"    {organ:14s}  {count}")

        if data.get("by_cohesion"):
            print("\n  By cohesion type:")
            for ctype, count in sorted(
                data["by_cohesion"].items(), key=lambda x: -x[1],
            ):
                print(f"    {ctype:20s}  {count}")

        if data.get("by_language"):
            print("\n  By language:")
            for lang, count in sorted(
                data["by_language"].items(), key=lambda x: -x[1],
            ):
                print(f"    {lang:15s}  {count}")

        repos = data.get("repos", [])
        if repos:
            by_count = sorted(
                repos, key=lambda r: len(r.get("components", [])), reverse=True,
            )
            print("\n  Top repos by component count:")
            for r in by_count[:10]:
                comp_count = len(r.get("components", []))
                if comp_count > 0:
                    print(f"    {r['repo']:30s}  {comp_count}")

        return 0

    print("No cached deep-index.json found. Run 'organvm index scan --write' first.")
    return 1
