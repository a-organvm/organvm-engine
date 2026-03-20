"""Trivium CLI commands — Dialectica Universalis."""

from __future__ import annotations

import argparse
import json as _json
from pathlib import Path


def cmd_trivium_dialects(args: argparse.Namespace) -> int:
    """List all eight dialects with profiles."""
    from organvm_engine.trivium.dialects import all_dialects, dialect_profile

    as_json = getattr(args, "json", False)
    dialects = all_dialects()

    if as_json:
        data = []
        for d in dialects:
            p = dialect_profile(d)
            data.append({
                "dialect": d.value,
                "organ_key": p.organ_key,
                "organ_name": p.organ_name,
                "translation_role": p.translation_role,
                "formal_basis": p.formal_basis,
                "classical_parallel": p.classical_parallel,
            })
        print(_json.dumps(data, indent=2))
        return 0

    print("\n  Trivium — Dialectica Universalis")
    print(f"  {'═' * 52}")
    print(
        "\n  The structural isomorphism of thought, truth, and computation."
    )
    print(
        "  Eight organs. Eight dialects. One universal logic.\n"
    )
    print(
        f"  {'Organ':<8} {'Dialect':<26} {'Classical':<12} "
        f"Translation Role"
    )
    print(f"  {'─' * 80}")
    for d in dialects:
        p = dialect_profile(d)
        print(
            f"  {p.organ_key:<8} {d.name:<26} {p.classical_parallel:<12} "
            f"{p.translation_role}"
        )
    print()
    return 0


def cmd_trivium_matrix(args: argparse.Namespace) -> int:
    """Show the 28-pair translation evidence matrix."""
    from organvm_engine.trivium.synthesis import render_translation_matrix_markdown
    from organvm_engine.trivium.translator import translation_matrix

    as_json = getattr(args, "json", False)
    registry_path = _resolve_registry(args)

    matrix = translation_matrix(registry_path=registry_path)

    if as_json:
        data = []
        for (a, b), ev in sorted(
            matrix.items(), key=lambda x: -x[1].aggregate_strength,
        ):
            data.append({
                "source": ev.source_organ,
                "target": ev.target_organ,
                "correspondences": len(ev.correspondences),
                "strength": ev.aggregate_strength,
                "preservation": ev.preservation_assessment,
            })
        print(_json.dumps(data, indent=2))
        return 0

    print("\n  Translation Evidence Matrix")
    print(f"  {'═' * 48}\n")
    print(render_translation_matrix_markdown(matrix))
    print()
    return 0


def cmd_trivium_scan(args: argparse.Namespace) -> int:
    """Scan structural correspondences between two organs."""
    from organvm_engine.trivium.detector import scan_all_pairs, scan_organ_pair

    scan_all = getattr(args, "all", False)
    as_json = getattr(args, "json", False)
    registry_path = _resolve_registry(args)

    if scan_all:
        results = scan_all_pairs(registry_path=registry_path)
        if as_json:
            print(_json.dumps(results, indent=2))
            return 0

        print("\n  Trivium Scan — All 28 Pairs")
        print(f"  {'═' * 48}\n")
        for r in sorted(results, key=lambda x: -x["avg_strength"]):
            print(
                f"  {r['organ_a']:>4}↔{r['organ_b']:<4}  "
                f"{r['count']:>3} correspondences  "
                f"strength {r['avg_strength']:.2f}"
            )
        print()
        return 0

    organ_a = getattr(args, "organ_a", None)
    organ_b = getattr(args, "organ_b", None)
    if not organ_a or not organ_b:
        print("  Error: specify two organ keys or --all")
        return 1

    report = scan_organ_pair(
        organ_a, organ_b, registry_path=registry_path,
    )

    if as_json:
        print(_json.dumps(report, indent=2))
        return 0

    print(f"\n  Trivium Scan: {organ_a} ↔ {organ_b}")
    print(f"  {'═' * 48}")
    print(f"\n  {report['summary']}\n")
    if report["by_type"]:
        print("  By type:")
        for t, count in sorted(report["by_type"].items()):
            print(f"    {t:<12} {count}")
    if report["correspondences"]:
        print(f"\n  {'Type':<12} {'Strength':>8}  Evidence")
        print(f"  {'─' * 60}")
        for c in report["correspondences"]:
            print(
                f"  {c['type']:<12} {c['strength']:>8.2f}  "
                f"{c['evidence'][:50]}"
            )
    print()
    return 0


def cmd_trivium_synthesize(args: argparse.Namespace) -> int:
    """Generate trivium testament narrative synthesis."""
    from organvm_engine.trivium.synthesis import (
        synthesize_trivium_testament,
        write_testament,
    )

    dry_run = not getattr(args, "write", False)
    registry_path = _resolve_registry(args)

    content = synthesize_trivium_testament(registry_path=registry_path)

    if dry_run:
        print(f"\n  [dry-run] Would generate trivium testament synthesis")
        print(f"  {len(content)} bytes, {content.count(chr(10))} lines")
        print(f"\n  Run with --write to produce.\n")
        return 0

    testament_dir = _resolve_testament_dir(args)
    out_path = write_testament(content, testament_dir)
    print(f"\n  Trivium testament written to {out_path}\n")
    return 0


def cmd_trivium_status(args: argparse.Namespace) -> int:
    """Show trivium subsystem health."""
    from organvm_engine.trivium.dialects import all_dialects
    from organvm_engine.trivium.sources import dialect_data, isomorphism_data
    from organvm_engine.trivium.taxonomy import (
        TranslationTier,
        pairs_by_tier,
    )

    as_json = getattr(args, "json", False)
    registry_path = _resolve_registry(args)

    d_data = dialect_data()
    tier_counts = {
        tier.value: len(pairs_by_tier(tier))
        for tier in TranslationTier
    }

    if as_json:
        print(_json.dumps({
            "dialects": d_data["count"],
            "translation_pairs": 28,
            "tier_counts": tier_counts,
        }, indent=2))
        return 0

    print("\n  Trivium — Dialectica Universalis")
    print(f"  {'═' * 48}")
    print(f"\n  Dialects:           {d_data['count']}")
    print(f"  Translation pairs:  28")
    print(f"\n  By tier:")
    for tier_name, count in tier_counts.items():
        print(f"    {tier_name:<14} {count}")
    print()
    return 0


def cmd_trivium_essays(args: argparse.Namespace) -> int:
    """Generate essay catalog from the translation matrix."""
    from organvm_engine.trivium.content import (
        generate_all_outlines,
        render_essay_catalog,
    )
    from organvm_engine.trivium.taxonomy import TranslationTier

    as_json = getattr(args, "json", False)
    tier_map = {
        "formal": TranslationTier.FORMAL,
        "structural": TranslationTier.STRUCTURAL,
        "analogical": TranslationTier.ANALOGICAL,
        "all": TranslationTier.EMERGENT,
    }
    min_tier = tier_map.get(
        getattr(args, "tier", "analogical"), TranslationTier.ANALOGICAL,
    )

    essays = generate_all_outlines(min_tier=min_tier)

    if as_json:
        data = [
            {
                "title": e.title,
                "subtitle": e.subtitle,
                "thesis": e.thesis,
                "tier": e.pair.tier.value,
                "source": e.pair.source.value,
                "target": e.pair.target.value,
                "outline": e.outline,
            }
            for e in essays
        ]
        print(_json.dumps(data, indent=2))
        return 0

    dry_run = not getattr(args, "write", False)
    if dry_run:
        print(f"\n  Trivium Essay Catalog — {len(essays)} essays")
        print(f"  {'═' * 48}\n")
        for e in essays:
            print(f"  [{e.pair.tier.value:>10}] {e.title}")
            print(f"               {e.subtitle}")
            print()
        print(f"  Run with --write to generate full catalog.\n")
        return 0

    catalog = render_essay_catalog(essays)
    output_dir = Path(getattr(args, "output_dir", None) or ".")
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "trivium-essay-catalog.md"
    out_path.write_text(catalog)
    print(f"\n  Essay catalog written to {out_path}")
    print(f"  {len(essays)} essays, {len(catalog)} bytes.\n")
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_registry(args: argparse.Namespace) -> Path | None:
    registry = getattr(args, "registry", None)
    return Path(registry) if registry else None


def _resolve_testament_dir(args: argparse.Namespace) -> Path:
    output = getattr(args, "output_dir", None)
    if output:
        return Path(output)
    return Path.home() / ".organvm" / "testament" / "trivium"
