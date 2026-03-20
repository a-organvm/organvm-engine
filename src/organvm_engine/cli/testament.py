"""Testament CLI commands — the system's generative self-portrait."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def cmd_testament_status(args: argparse.Namespace) -> int:
    """Show testament system status — what the system can and has produced."""
    from organvm_engine.testament.catalog import catalog_summary, load_catalog
    from organvm_engine.testament.manifest import (
        MODULE_SOURCES,
        ORGAN_OUTPUT_MATRIX,
        all_artifact_types,
    )

    as_json = getattr(args, "json", False)
    base_dir = _resolve_base_dir(args)

    types = all_artifact_types()
    catalog = load_catalog(base_dir)
    summary = catalog_summary(catalog)

    if as_json:
        print(json.dumps({
            "registered_types": len(types),
            "organ_profiles": len(ORGAN_OUTPUT_MATRIX),
            "source_modules": len(MODULE_SOURCES),
            "catalog": {
                "total": summary.total,
                "by_modality": summary.by_modality,
                "by_organ": summary.by_organ,
                "latest": summary.latest_timestamp,
            },
        }, indent=2))
        return 0

    print("\n  ORGANVM Testament — Generative Self-Portrait")
    print(f"  {'═' * 48}")
    print(f"\n  Registered artifact types:  {len(types)}")
    print(f"  Organ output profiles:     {len(ORGAN_OUTPUT_MATRIX)}")
    print(f"  Source modules:            {len(MODULE_SOURCES)}")
    print(f"\n  Catalog: {summary.total} artifacts produced")
    if summary.latest_timestamp:
        print(f"  Latest:  {summary.latest_timestamp[:19]}")
    if summary.by_modality:
        print("\n  By modality:")
        for mod, count in sorted(summary.by_modality.items()):
            print(f"    {mod:<16} {count}")
    print()
    return 0


def cmd_testament_render(args: argparse.Namespace) -> int:
    """Render testament artifacts from live system data."""
    from organvm_engine.testament.aesthetic import load_taste
    from organvm_engine.testament.pipeline import render_all, render_organ

    organ = getattr(args, "organ", None)
    dry_run = getattr(args, "dry_run", True)
    write = getattr(args, "write", False)
    if write:
        dry_run = False

    output_dir = _resolve_output_dir(args)
    registry_path = getattr(args, "registry", None)
    if registry_path:
        registry_path = Path(registry_path)

    load_taste()  # validates taste.yaml is parseable before rendering

    if organ:
        results = render_organ(
            organ, output_dir, dry_run=dry_run, registry_path=registry_path,
        )
    else:
        results = render_all(
            output_dir, dry_run=dry_run, registry_path=registry_path,
        )

    succeeded = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    if dry_run:
        print(f"\n  [dry-run] Would produce {len(results)} artifacts:")
        for r in results:
            organ_label = r.artifact.organ or "system"
            print(f"    {r.artifact.modality.value:<14} {organ_label:<8} {r.artifact.title}")
        print("\n  Run with --write to produce artifacts.\n")
    else:
        print(f"\n  Produced {len(succeeded)} artifacts" +
              (f" ({len(failed)} failed)" if failed else ""))
        for r in succeeded:
            print(f"    ✓ {r.artifact.path}")
        for r in failed:
            print(f"    ✗ {r.artifact.title}: {r.error}")
        print()

    return 1 if failed and not dry_run else 0


def cmd_testament_catalog(args: argparse.Namespace) -> int:
    """List all produced testament artifacts."""
    from organvm_engine.testament.catalog import load_catalog

    as_json = getattr(args, "json", False)
    organ = getattr(args, "organ", None)
    base_dir = _resolve_base_dir(args)
    catalog = load_catalog(base_dir)

    if organ:
        catalog = [a for a in catalog if a.organ == organ]

    if as_json:
        import dataclasses
        print(json.dumps([dataclasses.asdict(a) for a in catalog], indent=2, default=str))
        return 0

    if not catalog:
        print("\n  No testament artifacts found. Run `organvm testament render --write`.\n")
        return 0

    print(f"\n  Testament Catalog — {len(catalog)} artifacts")
    print(f"\n  {'Date':<12} {'Modality':<14} {'Organ':<8} {'Format':<8} Title")
    print(f"  {'─' * 75}")
    for a in catalog:
        date = a.timestamp[:10] if a.timestamp else "unknown"
        organ_label = a.organ or "system"
        mod = a.modality.value if hasattr(a.modality, 'value') else str(a.modality)
        fmt = a.format.value if hasattr(a.format, 'value') else str(a.format)
        print(f"  {date:<12} {mod:<14} {organ_label:<8} {fmt:<8} {a.title}")
    print()
    return 0


def cmd_testament_gallery(args: argparse.Namespace) -> int:
    """Generate a static HTML gallery of all testament artifacts."""
    from organvm_engine.testament.aesthetic import load_taste
    from organvm_engine.testament.catalog import load_catalog
    from organvm_engine.testament.renderers.html import render_gallery_page

    dry_run = not getattr(args, "write", False)
    output_dir = _resolve_output_dir(args)
    base_dir = _resolve_base_dir(args)

    catalog = load_catalog(base_dir)
    aesthetic = load_taste()

    palette = {
        "primary": aesthetic.palette.primary,
        "secondary": aesthetic.palette.secondary,
        "accent": aesthetic.palette.accent,
        "background": aesthetic.palette.background,
        "text": aesthetic.palette.text,
        "muted": aesthetic.palette.muted,
    }

    artifact_dicts = []
    for a in catalog:
        mod = a.modality.value if hasattr(a.modality, 'value') else str(a.modality)
        fmt = a.format.value if hasattr(a.format, 'value') else str(a.format)
        artifact_dicts.append({
            "title": a.title,
            "modality": mod,
            "format": fmt,
            "path": a.path,
            "timestamp": a.timestamp,
            "organ": a.organ or "system",
        })

    html = render_gallery_page(artifact_dicts, palette=palette)
    gallery_path = output_dir / "index.html"

    if dry_run:
        print(f"\n  [dry-run] Would write gallery to {gallery_path}")
        print(f"  {len(catalog)} artifacts, {len(html)} bytes")
        print("\n  Run with --write to generate.\n")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    gallery_path.write_text(html)
    print(f"\n  Gallery written to {gallery_path}")
    print(f"  {len(catalog)} artifacts indexed.\n")
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_output_dir(args: argparse.Namespace) -> Path:
    """Resolve the output directory for testament artifacts."""
    output = getattr(args, "output_dir", None)
    if output:
        return Path(output)
    return Path.home() / ".organvm" / "testament" / "artifacts"


def _resolve_base_dir(args: argparse.Namespace) -> Path | None:
    """Resolve the base directory for the testament catalog."""
    base = getattr(args, "base_dir", None)
    return Path(base) if base else None
