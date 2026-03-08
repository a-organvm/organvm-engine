"""CLI commands: organvm study feedback|consilience|audit-report."""

from __future__ import annotations

import argparse
import json


def cmd_study_feedback(args: argparse.Namespace) -> int:
    """Show the feedback loop inventory."""
    from organvm_engine.governance.feedback_loops import build_feedback_inventory

    as_json = getattr(args, "json", False)
    polarity = getattr(args, "polarity", None)

    inventory = build_feedback_inventory()

    if as_json:
        data = inventory.to_dict()
        if polarity:
            from organvm_engine.governance.feedback_loops import LoopPolarity
            p = LoopPolarity(polarity)
            data["loops"] = [lp for lp in data["loops"] if lp["polarity"] == polarity]
        print(json.dumps(data, indent=2))
        return 0

    if polarity:
        from organvm_engine.governance.feedback_loops import LoopPolarity
        p = LoopPolarity(polarity)
        loops = inventory.by_polarity(p)
        print(f"{polarity.upper()} Feedback Loops ({len(loops)})")
        print("=" * 60)
        for loop in loops:
            status_mark = {"mapped": "+", "observed": "~", "unmapped": "!"}
            mark = status_mark.get(loop.status.value, "?")
            print(f"  [{mark}] {loop.name} ({loop.stratum.value})")
            print(f"      {loop.description[:100]}...")
            if loop.risk:
                print(f"      Risk: {loop.risk[:80]}...")
            print()
    else:
        print(inventory.summary())

    ungov = inventory.ungoverned_positive()
    if ungov and not polarity:
        print(f"\nAction required: {len(ungov)} positive loops lack governing mechanisms.")

    return 0


def cmd_study_consilience(args: argparse.Namespace) -> int:
    """Compute and display the consilience index."""
    from organvm_engine.metrics.consilience import compute_consilience

    as_json = getattr(args, "json", False)

    report = compute_consilience()

    if as_json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0

    print(report.summary())
    return 0


def cmd_study_audit_report(args: argparse.Namespace) -> int:
    """Run a combined governance + feedback + consilience audit report.

    This is the Study Suite Auditor agent's manual invocation —
    a point-in-time snapshot that combines:
    - Governance audit (existing)
    - Feedback loop inventory
    - Consilience index
    - Drift detection (seed vs registry)
    """
    from datetime import datetime, timezone
    from pathlib import Path

    from organvm_engine.governance.audit import run_audit
    from organvm_engine.governance.feedback_loops import build_feedback_inventory
    from organvm_engine.metrics.consilience import compute_consilience
    from organvm_engine.paths import registry_path
    from organvm_engine.registry.loader import load_registry

    output = getattr(args, "output", None)
    as_json = getattr(args, "json", False)

    reg = load_registry(registry_path())

    # 1. Governance audit
    audit_result = run_audit(reg)

    # 2. Feedback loop inventory
    feedback = build_feedback_inventory()

    # 3. Consilience index
    consilience = compute_consilience()

    now = datetime.now(timezone.utc).isoformat()

    if as_json:
        combined = {
            "generated": now,
            "governance": {
                "passed": audit_result.passed,
                "critical": audit_result.critical,
                "warnings": audit_result.warnings[:10],
                "info_count": len(audit_result.info),
            },
            "feedback_loops": feedback.to_dict(),
            "consilience": consilience.to_dict(),
        }
        print(json.dumps(combined, indent=2))
        return 0

    lines = [
        "ORGANVM Study Suite — Auditor Report",
        f"Generated: {now}",
        "=" * 60,
        "",
        audit_result.summary(),
        "",
        feedback.summary(),
        "",
        consilience.summary(),
        "",
        "---",
        "This report combines governance audit, feedback loop inventory,",
        "and consilience index into a single Study Suite snapshot.",
        "See: praxis-perpetua/research/2026-03-08-ontological-topology-of-organvm.md",
    ]

    report = "\n".join(lines)

    if output:
        Path(output).write_text(report + "\n", encoding="utf-8")
        print(f"Report written to {output}")
    else:
        print(report)

    return 0 if audit_result.passed else 1
