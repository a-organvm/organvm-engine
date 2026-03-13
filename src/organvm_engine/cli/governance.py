"""Governance CLI commands."""

import argparse

from organvm_engine.registry.loader import load_registry
from organvm_engine.registry.query import find_repo, resolve_entity


def cmd_governance_audit(args: argparse.Namespace) -> int:
    from organvm_engine.governance.audit import run_audit

    registry = load_registry(args.registry)
    rules_path = args.rules if hasattr(args, "rules") and args.rules else None

    if rules_path:
        from organvm_engine.governance.rules import load_governance_rules

        rules = load_governance_rules(rules_path)
    else:
        rules = None

    result = run_audit(registry, rules)
    print(result.summary())
    return 0 if result.passed else 1


def cmd_governance_checkdeps(args: argparse.Namespace) -> int:
    from organvm_engine.governance.dependency_graph import validate_dependencies

    registry = load_registry(args.registry)
    result = validate_dependencies(registry)

    print("Dependency Graph Validation")
    print("─" * 40)
    print(f"  Total edges: {result.total_edges}")
    print(f"  Missing targets: {len(result.missing_targets)}")
    print(f"  Self-dependencies: {len(result.self_deps)}")
    print(f"  Back-edges: {len(result.back_edges)}")
    print(f"  Cycles: {len(result.cycles)}")

    if result.cross_organ:
        print("\n  Cross-organ directions:")
        for direction, count in sorted(result.cross_organ.items()):
            print(f"    {direction}: {count}")

    if result.violations:
        print("\n  Violations:")
        for v in result.violations:
            print(f"    {v}")

    print(f"\n  Result: {'PASS' if result.passed else 'FAIL'}")
    return 0 if result.passed else 1


def cmd_governance_promote(args: argparse.Namespace) -> int:
    from organvm_engine.governance.state_machine import check_transition

    registry = load_registry(args.registry)
    resolved = resolve_entity(args.repo, registry=registry)
    if resolved and resolved.get("registry_entry"):
        organ_key, repo = resolved["organ_key"], resolved["registry_entry"]
    else:
        result = find_repo(registry, args.repo)
        if not result:
            print(f"ERROR: Repo '{args.repo}' not found")
            return 1
        organ_key, repo = result
    current = repo.get("promotion_status", "LOCAL")
    ok, msg = check_transition(current, args.target)
    print(f"  {msg}")

    if ok:
        print("  Transition is valid. Use 'organvm registry update' to apply.")
    return 0 if ok else 1


def cmd_governance_dictums(args: argparse.Namespace) -> int:
    import json

    from organvm_engine.governance.dictums import (
        check_all_dictums,
        get_dictums,
        list_all_dictums,
    )
    from organvm_engine.governance.rules import load_governance_rules

    rules_path = args.rules if hasattr(args, "rules") and args.rules else None
    rules = load_governance_rules(rules_path) if rules_path else load_governance_rules()

    dictums_data = get_dictums(rules)
    if not dictums_data:
        print("No dictums section found in governance-rules.json")
        return 0

    # --check: run compliance validators
    if getattr(args, "check", False):
        registry = load_registry(args.registry)
        workspace = getattr(args, "workspace", None)
        from pathlib import Path
        ws = Path(workspace) if workspace else None
        report = check_all_dictums(registry, rules, ws)
        if getattr(args, "json", False):
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(report.summary())
        return 0 if report.all_passed else 1

    # List dictums
    all_dicts = list_all_dictums(rules)
    level_filter = getattr(args, "level", None)
    dictum_id = getattr(args, "id", None)

    if dictum_id:
        matches = [d for d in all_dicts if d["id"] == dictum_id]
        if not matches:
            print(f"Dictum '{dictum_id}' not found")
            return 1
        if getattr(args, "json", False):
            print(json.dumps(matches[0], indent=2))
        else:
            d = matches[0]
            print(f"  ID:          {d['id']}")
            print(f"  Name:        {d['name']}")
            print(f"  Level:       {d['level']}")
            print(f"  Severity:    {d['severity']}")
            print(f"  Enforcement: {d['enforcement']}")
            if d.get("organ"):
                print(f"  Organ:       {d['organ']}")
            print(f"  Statement:   {d['statement']}")
            if d.get("validator"):
                print(f"  Validator:   {d['validator']}")
            if d.get("references"):
                print(f"  References:  {', '.join(d['references'])}")
        return 0

    if level_filter:
        all_dicts = [d for d in all_dicts if d["level"] == level_filter]

    if getattr(args, "json", False):
        print(json.dumps(all_dicts, indent=2))
        return 0

    # Group by level
    by_level: dict[str, list[dict]] = {}
    for d in all_dicts:
        by_level.setdefault(d["level"], []).append(d)

    for level in ("axiom", "organ", "repo"):
        items = by_level.get(level, [])
        if not items:
            continue
        print(f"\n{level.upper()} DICTUMS ({len(items)}):")
        print("─" * 60)
        for d in items:
            sev = d["severity"][0].upper()
            enf = d["enforcement"][:4]
            organ = f" [{d['organ']}]" if d.get("organ") else ""
            print(f"  {d['id']:8s} {sev}  {enf:4s}  {d['name']}{organ}")

    print(f"\nTotal: {len(all_dicts)} dictums")
    return 0


def cmd_governance_impact(args: argparse.Namespace) -> int:
    from organvm_engine.governance.impact import calculate_impact

    registry = load_registry(args.registry)
    workspace = args.workspace if hasattr(args, "workspace") else None
    report = calculate_impact(args.repo, registry, workspace)

    print(report.summary())
    return 0
