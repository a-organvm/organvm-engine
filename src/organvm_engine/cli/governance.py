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


def cmd_governance_authorize(args: argparse.Namespace) -> int:
    """Check if an actor is authorized to promote a repo."""
    from organvm_engine.governance.authorization import authorize_transition
    from organvm_engine.seed.discover import discover_seeds
    from organvm_engine.seed.reader import read_seed

    actor = args.actor
    target = args.target
    repo_name = args.repo

    # Find the seed.yaml for this repo
    seed_data = None
    seeds = discover_seeds(getattr(args, "workspace", None))
    for path in seeds:
        try:
            seed = read_seed(path)
            if seed.get("repo") == repo_name:
                seed_data = seed
                break
        except Exception:
            continue

    if seed_data is None:
        print(f"  No seed.yaml found for '{repo_name}' — using solo-operator defaults")
        seed_data = {}

    result = authorize_transition(actor, target, seed_data, enforce=getattr(args, "enforce", False))

    mode = "ENFORCING" if not result.advisory else "ADVISORY"
    status = "AUTHORIZED" if result.authorized else "DENIED"
    print(f"  [{mode}] {status}")
    print(f"  Actor: {result.actor}")
    print(f"  Target: {result.target_state}")
    print(f"  Reason: {result.reason}")
    if result.gates_required:
        print(f"  Gates required: {', '.join(result.gates_required)}")

    return 0 if result.authorized else 1


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

    from organvm_engine.ci.mandate import _resolve_repo_path
    from organvm_engine.governance.state_machine import execute_transition
    from organvm_engine.organ_config import registry_key_to_dir
    from organvm_engine.paths import workspace_root

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
    repo_name = repo.get("name", args.repo)
    org = repo.get("org", "")
    tier = repo.get("tier", "standard")

    # Resolve filesystem path for infrastructure audit
    key_to_dir = registry_key_to_dir()
    ws = workspace_root()
    repo_path = _resolve_repo_path(org, repo_name, organ_key, ws, key_to_dir)

    ok, msg = execute_transition(
        repo_name=repo_name,
        current_state=current,
        target_state=args.target,
        repo_path=repo_path,
        organ=organ_key,
        org=org,
        tier=tier,
    )
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


def cmd_governance_placement(args: argparse.Namespace) -> int:
    """Audit repo-to-organ placement affinity."""
    import json as json_mod

    from organvm_engine.governance.placement import (
        audit_all_placements,
        load_organ_definitions,
        recommend_placement,
    )

    registry = load_registry(args.registry)
    definitions = load_organ_definitions()
    if not definitions:
        print("ERROR: organ-definitions.json not found")
        return 1

    # Single-repo mode
    single_repo = getattr(args, "repo", None)
    if single_repo:
        resolved = resolve_entity(single_repo, registry=registry)
        if resolved and resolved.get("registry_entry"):
            repo = resolved["registry_entry"]
        else:
            result = find_repo(registry, single_repo)
            if not result:
                print(f"ERROR: Repo '{single_repo}' not found")
                return 1
            _, repo = result

        rec = recommend_placement(repo, definitions)
        if getattr(args, "json", False):
            print(json_mod.dumps(rec.to_dict(), indent=2))
        else:
            print(f"  Repo: {rec.repo_name}")
            print(f"  Current organ: {rec.current_organ}")
            print(f"  Flagged: {'YES' if rec.flagged else 'no'}")
            print()
            for s in rec.scores[:5]:
                marker = " <-- current" if s.organ == rec.current_organ else ""
                print(f"  {s.organ:14s}  score={s.score:3d}{marker}")
                for inc in s.matched_inclusion:
                    print(f"    + {inc}")
                for exc in s.triggered_exclusion:
                    print(f"    - {exc}")
                for n in s.notes:
                    print(f"    * {n}")
        return 0

    # Full audit mode
    audit = audit_all_placements(registry, definitions)

    if getattr(args, "json", False):
        print(json_mod.dumps(audit.to_dict(), indent=2))
        return 0

    audit_only = getattr(args, "audit", False)

    print("Organ Placement Audit")
    print("=" * 60)
    print(f"  Total repos: {audit.total_repos}")
    print(f"  Well-placed: {audit.well_placed}")
    print(f"  Questionable: {len(audit.questionable)}")
    print(f"  Misplaced: {len(audit.misplaced)}")

    if audit.misplaced:
        print(f"\n  MISPLACED ({len(audit.misplaced)}):")
        print("  " + "─" * 56)
        for rec in audit.misplaced:
            top = rec.scores[0] if rec.scores else None
            cur = next(
                (s for s in rec.scores if s.organ == rec.current_organ), None,
            )
            cur_score = cur.score if cur else 0
            top_info = f" → best: {top.organ} ({top.score})" if top else ""
            print(f"    {rec.repo_name:30s}  {rec.current_organ} ({cur_score}){top_info}")

    if audit.questionable and not audit_only:
        print(f"\n  QUESTIONABLE ({len(audit.questionable)}):")
        print("  " + "─" * 56)
        for rec in audit.questionable:
            top = rec.scores[0] if rec.scores else None
            cur = next(
                (s for s in rec.scores if s.organ == rec.current_organ), None,
            )
            cur_score = cur.score if cur else 0
            top_info = f" → best: {top.organ} ({top.score})" if top else ""
            print(f"    {rec.repo_name:30s}  {rec.current_organ} ({cur_score}){top_info}")

    return 0


def cmd_governance_excavate(args: argparse.Namespace) -> int:
    """Run buried entity excavation across the workspace."""
    import json as json_mod
    from pathlib import Path

    from organvm_engine.governance.excavation import run_full_excavation

    registry = load_registry(args.registry)
    workspace = Path(args.workspace) if getattr(args, "workspace", None) else None

    if workspace is None:
        from organvm_engine.paths import workspace_root

        workspace = workspace_root()

    entity_type = getattr(args, "type", None)
    severity = getattr(args, "severity", None)
    families_only = getattr(args, "families", False)

    report = run_full_excavation(workspace, registry)

    findings = report.findings
    if entity_type:
        findings = [f for f in findings if f.entity_type == entity_type]
    if severity:
        sev_order = {"info": 0, "warning": 1, "critical": 2}
        min_sev = sev_order.get(severity, 0)
        findings = [
            f for f in findings
            if sev_order.get(f.severity, 0) >= min_sev
        ]

    if getattr(args, "json", False):
        out = report.to_dict()
        out["findings"] = [f.to_dict() for f in findings]
        print(json_mod.dumps(out, indent=2))
        return 0

    if families_only:
        families = report.cross_organ_families
        if not families:
            print("No cross-organ families detected.")
            return 0
        print(f"Cross-Organ Families ({len(families)}):")
        print("=" * 60)
        for fam in families:
            print(f"\n  Family: {fam.get('stem', '?')}")
            for member in fam.get("members", []):
                print(f"    {member.get('organ', '?'):14s}  {member.get('repo', '?')}")
        return 0

    print("Excavation Report")
    print("=" * 60)
    print(f"  Scanned repos: {report.scanned_repos}")
    print(f"  Total findings: {len(findings)}")
    print(f"  By type: {report.by_type}")
    print(f"  By severity: {report.by_severity}")

    if findings:
        print(f"\n  {'Repo':25s} {'Organ':14s} {'Type':20s} {'Sev':8s} {'Pattern':13s} Path")
        print("  " + "─" * 90)
        for f in findings:
            pat = getattr(f, "pattern", "") or ""
            print(
                f"  {f.repo:25s} {f.organ:14s} {f.entity_type:20s} "
                f"{f.severity:8s} {pat:13s} {f.entity_path}",
            )

    # --register: create ontologia MODULE entities from sub-package findings
    if getattr(args, "register", False):
        from organvm_engine.governance.module_bridge import sync_modules_from_excavation

        sub_pkgs = [f for f in report.findings if f.entity_type == "sub_package"]
        if not sub_pkgs:
            print("\nNo sub-packages to register.")
        else:
            result = sync_modules_from_excavation(sub_pkgs)
            print("\nOntologia registration:")
            print(f"  Modules created: {result.modules_created}")
            print(f"  Modules skipped (existing): {result.modules_skipped}")
            print(f"  Hierarchy edges: {result.hierarchy_edges_created}")
            if result.unresolved_parents:
                print(f"  Unresolved parents: {result.unresolved_parents}")
            if result.errors:
                for err in result.errors:
                    print(f"  ERROR: {err}")

    return 0


def cmd_governance_impact(args: argparse.Namespace) -> int:
    from organvm_engine.governance.impact import calculate_impact

    registry = load_registry(args.registry)
    workspace = args.workspace if hasattr(args, "workspace") else None
    report = calculate_impact(args.repo, registry, workspace)

    print(report.summary())
    return 0
