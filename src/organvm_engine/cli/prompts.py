"""CLI commands for prompt narrative analysis.

Usage:
    organvm prompts narrate [--agent claude|gemini|codex] [--project FILTER]
                            [--output FILE] [--summary FILE]
                            [--dry-run] [--gap-hours 24]
    organvm prompts clipboard [--db-path PATH] [--output-dir DIR]
                              [--dry-run] [--json-only] [--md-only]
    organvm prompts audit [--output FILE] [--json] [--noise-only]
    organvm prompts distill [--input FILE] [--output-dir DIR]
                            [--dry-run] [--json] [--scaffold] [--write]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def cmd_prompts_narrate(args: argparse.Namespace) -> int:
    """Narrate prompts across sessions into threaded narrative arcs."""
    from organvm_engine.prompts.narrator import narrate_prompts, write_jsonl
    from organvm_engine.prompts.summary import generate_narrative_summary

    agent = getattr(args, "agent", None)
    project_filter = getattr(args, "project", None)
    dry_run = getattr(args, "dry_run", False)
    gap_hours = getattr(args, "gap_hours", 24.0)

    from organvm_engine.paths import atoms_dir

    default_dir = atoms_dir()
    output_path = Path(getattr(args, "output", None) or (default_dir / "annotated-prompts.jsonl"))
    summary_path = Path(getattr(args, "summary", None) or (default_dir / "NARRATIVE-SUMMARY.md"))

    result = narrate_prompts(
        agent=agent,
        project_filter=project_filter,
        gap_hours=gap_hours,
    )

    # Print stats
    print(f"Sessions processed: {result.sessions_processed}")
    print(f"Sessions skipped: {result.sessions_skipped}")
    print(f"Noise skipped: {result.noise_skipped}")
    print(f"Prompts extracted: {len(result.prompts)}")
    print(f"Threads: {result.thread_count}")
    print(f"Errors: {len(result.errors)}")
    print()

    print("Type distribution:")
    for ptype, count in sorted(result.type_counts.items(), key=lambda x: -x[1]):
        print(f"  {ptype}: {count}")
    print()

    print("Size distribution:")
    for sclass, count in sorted(result.size_counts.items(), key=lambda x: -x[1]):
        print(f"  {sclass}: {count}")
    print()

    print("Arc patterns:")
    for pattern, count in sorted(result.arc_pattern_counts.items(), key=lambda x: -x[1]):
        print(f"  {pattern}: {count}")

    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for loc, err in result.errors[:10]:
            print(f"  {loc}: {err}")

    if dry_run:
        print("\n--dry-run: no files written")
        return 0

    write_jsonl(result.prompts, output_path)
    print(f"\nWrote {len(result.prompts)} prompts to {output_path}")

    summary = generate_narrative_summary(result)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary, encoding="utf-8")
    print(f"Wrote summary to {summary_path}")

    return 0


def cmd_prompts_audit(args: argparse.Namespace) -> int:
    """Run prompt & pipeline data audit."""
    import json as json_mod

    from organvm_engine.paths import atoms_dir
    from organvm_engine.prompts.audit import (
        audit_completion,
        audit_effectiveness,
        audit_links,
        audit_noise,
        audit_sessions,
        generate_recommendations,
    )
    from organvm_engine.prompts.audit_report import generate_audit_report

    data_dir = atoms_dir()
    noise_only = getattr(args, "noise_only", False)
    json_output = getattr(args, "json", False)
    output_path = Path(getattr(args, "output", None) or (data_dir / "AUDIT-REPORT.md"))

    # Load JSONL data
    def _load_jsonl(path: Path) -> list[dict]:
        if not path.exists():
            print(f"Warning: {path} not found")
            return []
        items = []
        with path.open(encoding="utf-8") as f:
            for raw in f:
                stripped = raw.strip()
                if stripped:
                    items.append(json_mod.loads(stripped))
        return items

    prompts = _load_jsonl(data_dir / "annotated-prompts.jsonl")
    if not prompts:
        print("No annotated prompts found. Run `organvm prompts narrate` first.")
        return 1

    noise = audit_noise(prompts)
    print(f"Noise analysis: {noise['signal_count']} signal / {noise['noise_count']} noise "
          f"({noise['noise_pct']}% noise)")

    if noise_only:
        if json_output:
            print(json_mod.dumps(noise, indent=2))
        else:
            for ntype, count in sorted(noise["noise_by_type"].items(), key=lambda x: -x[1]):
                print(f"  {ntype}: {count}")
        return 0

    tasks = _load_jsonl(data_dir / "atomized-tasks.jsonl")
    links = _load_jsonl(data_dir / "atom-links.jsonl")

    completion = audit_completion(tasks, prompts, links)
    effectiveness = audit_effectiveness(prompts, tasks, links)
    sessions = audit_sessions(prompts)
    links_audit = audit_links(links, tasks, prompts)
    recommendations = generate_recommendations(
        noise, completion, effectiveness, sessions, links_audit,
    )

    results = {
        "noise": noise,
        "completion": completion,
        "effectiveness": effectiveness,
        "sessions": sessions,
        "links": links_audit,
        "recommendations": recommendations,
    }

    if json_output:
        # Remove noise_ids for cleaner JSON (can be large)
        results["noise"] = {k: v for k, v in noise.items() if k != "noise_ids"}
        print(json_mod.dumps(results, indent=2))
        return 0

    # Print summary
    funnel = completion.get("funnel_summary", {})
    print(f"Tasks: {funnel.get('total_tasks', 0)} "
          f"(completed: {funnel.get('completed_tasks', 0)}, "
          f"rate: {funnel.get('completion_rate', 0)}%)")
    print(f"Links: {links_audit.get('total_links', 0)} "
          f"(empty-FP: {links_audit.get('empty_fp_pct', 0)}%)")
    print(f"Sessions: {sessions.get('total_sessions', 0)}")
    print(f"Recommendations: {len(recommendations)} "
          f"({sum(1 for r in recommendations if r.get('priority') == 'P0')} P0)")

    # Write report
    report = generate_audit_report(results)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"\nWrote audit report to {output_path}")

    return 0


def cmd_prompts_distill(args: argparse.Namespace) -> int:
    """Distill clipboard prompts into operational patterns and SOP coverage."""
    import json as json_mod

    from organvm_engine.distill.coverage import analyze_coverage, coverage_summary
    from organvm_engine.distill.matcher import match_batch
    from organvm_engine.distill.scaffold import generate_scaffolds
    from organvm_engine.distill.taxonomy import OPERATIONAL_PATTERNS

    input_path_str = getattr(args, "input", None)
    output_dir_str = getattr(args, "output_dir", None)
    dry_run = getattr(args, "dry_run", True)
    write = getattr(args, "write", False)
    as_json = getattr(args, "json", False)
    scaffold = getattr(args, "scaffold", False)

    if write:
        dry_run = False

    # Load prompts from clipboard export JSON
    if input_path_str:
        input_path = Path(input_path_str)
    else:
        from organvm_engine.paths import atoms_dir
        input_path = atoms_dir() / "clipboard-prompts.json"

    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        print("Run `organvm prompts clipboard` first to generate clipboard prompts.")
        return 1

    prompts = _load_clipboard_prompts(input_path)
    if not prompts:
        print("No prompts loaded from input file.")
        return 1

    print(f"Loaded {len(prompts)} prompts from {input_path}")

    # Match prompts against patterns
    matched = match_batch(prompts, OPERATIONAL_PATTERNS)

    # Print match summary
    print(f"\nPattern matches ({len(matched)} patterns hit):")
    for pid, matches in sorted(matched.items(), key=lambda x: -len(x[1])):
        pattern = OPERATIONAL_PATTERNS[pid]
        print(f"  {pattern.label:<45} {len(matches):>3} prompts")

    # Coverage analysis
    sop_entries: list = []
    try:
        from organvm_engine.sop.discover import discover_sops
        sop_entries = discover_sops()
    except Exception:
        print("\nWarning: Could not discover SOPs (continuing without coverage analysis)")

    coverage = analyze_coverage(matched, prompts, sop_entries, OPERATIONAL_PATTERNS)
    summary = coverage_summary(coverage)

    print(f"\nCoverage: {summary['covered']}/{summary['total_patterns']} covered, "
          f"{summary['partial']} partial, {summary['uncovered']} uncovered")

    if summary["uncovered_patterns"]:
        print("\nUncovered patterns:")
        for pid in summary["uncovered_patterns"]:
            p = OPERATIONAL_PATTERNS.get(pid)
            if p:
                print(f"  [{p.tier}] {p.label} → SOP--{p.sop_name_hint}.md")

    if as_json:
        data = {
            "summary": summary,
            "coverage": [e.to_dict() for e in coverage],
            "match_counts": {pid: len(ms) for pid, ms in matched.items()},
        }
        print(json_mod.dumps(data, indent=2))
        return 0

    # Scaffold generation
    if scaffold:
        out_dir = Path(output_dir_str) if output_dir_str else Path(".sops")

        written = generate_scaffolds(coverage, out_dir, dry_run=dry_run)
        if written:
            verb = "Would write" if dry_run else "Wrote"
            print(f"\n{verb} {len(written)} SOP scaffold(s):")
            for p in written:
                print(f"  {p}")
            if dry_run:
                print("\nUse --write to actually write files.")
        else:
            print("\nNo new SOP scaffolds needed.")

    return 0


def _load_clipboard_prompts(path: Path) -> list:
    """Load ClipboardPrompt objects from a JSON export file."""
    import json as json_mod

    from organvm_engine.prompts.clipboard.schema import ClipboardPrompt

    try:
        data = json_mod.loads(path.read_text(encoding="utf-8"))
    except (json_mod.JSONDecodeError, OSError) as exc:
        print(f"Error reading {path}: {exc}", file=sys.stderr)
        return []

    # Handle both array-of-prompts and {prompts: [...]} formats
    items = data if isinstance(data, list) else data.get("prompts", [])

    prompts = []
    for item in items:
        if not isinstance(item, dict) or "text" not in item:
            continue
        prompts.append(ClipboardPrompt(
            id=item.get("id", 0),
            content_hash=item.get("content_hash", ""),
            date=item.get("date", ""),
            time=item.get("time", ""),
            timestamp=item.get("timestamp", ""),
            source_app=item.get("source_app", ""),
            bundle_id=item.get("bundle_id", ""),
            category=item.get("category", "General AI Usage"),
            confidence=item.get("confidence", "low"),
            signals=item.get("signals", []),
            word_count=item.get("word_count", 0),
            char_count=item.get("char_count", 0),
            multi_turn=item.get("multi_turn", False),
            file_refs=item.get("file_refs", []),
            tech_mentions=item.get("tech_mentions", []),
            text=item.get("text", ""),
        ))
    return prompts


def cmd_prompts_clipboard(args: argparse.Namespace) -> int:
    """Extract and classify AI prompts from Paste.app clipboard history."""
    from organvm_engine.prompts.clipboard.pipeline import run_pipeline

    db_path_str = getattr(args, "db_path", None)
    db_path = Path(db_path_str) if db_path_str else None
    output_dir_str = getattr(args, "output_dir", None)
    output_dir = Path(output_dir_str) if output_dir_str else None
    dry_run = getattr(args, "dry_run", False)
    json_only = getattr(args, "json_only", False)
    md_only = getattr(args, "md_only", False)

    run_pipeline(
        db_path=db_path,
        output_dir=output_dir,
        dry_run=dry_run,
        json_only=json_only,
        md_only=md_only,
    )

    return 0
