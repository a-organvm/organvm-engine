"""CLI commands for the ontologia structural registry.

Provides entity resolution, bootstrap, history, and governance
operations via the `organvm ontologia` command group.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from ontologia.bootstrap import bootstrap_from_registry
    from ontologia.entity.identity import EntityType
    from ontologia.registry.store import open_store

    HAS_ONTOLOGIA = True
except ImportError:
    HAS_ONTOLOGIA = False


def _check_available() -> bool:
    if not HAS_ONTOLOGIA:
        print("Error: organvm-ontologia is not installed.", file=sys.stderr)
        print("  Install with: pip install -e ../organvm-ontologia/", file=sys.stderr)
        return False
    return True


def cmd_ontologia_resolve(args: argparse.Namespace) -> int:
    """Resolve an entity by name or UID."""
    if not _check_available():
        return 1

    store = open_store()
    resolver = store.resolver()
    result = resolver.resolve(args.query)

    if result is None:
        print(f"No entity found for: {args.query}")
        return 1

    name = store.current_name(result.identity.uid)
    output = {
        "uid": result.identity.uid,
        "entity_type": result.identity.entity_type.value,
        "lifecycle_status": result.identity.lifecycle_status.value,
        "display_name": name.display_name if name else None,
        "matched_by": result.matched_by,
        "created_at": result.identity.created_at,
    }

    if getattr(args, "json", False):
        print(json.dumps(output, indent=2))
    else:
        print(f"  UID:        {output['uid']}")
        print(f"  Name:       {output['display_name']}")
        print(f"  Type:       {output['entity_type']}")
        print(f"  Status:     {output['lifecycle_status']}")
        print(f"  Matched by: {output['matched_by']}")
        print(f"  Created:    {output['created_at']}")
    return 0


def cmd_ontologia_list(args: argparse.Namespace) -> int:
    """List entities with optional type filter."""
    if not _check_available():
        return 1

    store = open_store()
    entity_type = None
    if args.type:
        try:
            entity_type = EntityType(args.type)
        except ValueError:
            print(f"Unknown entity type: {args.type}", file=sys.stderr)
            return 1

    entities = store.list_entities(entity_type=entity_type)

    if getattr(args, "json", False):
        rows = []
        for e in entities:
            name = store.current_name(e.uid)
            rows.append({
                "uid": e.uid,
                "entity_type": e.entity_type.value,
                "lifecycle_status": e.lifecycle_status.value,
                "display_name": name.display_name if name else None,
            })
        print(json.dumps(rows, indent=2))
    else:
        for e in entities:
            name = store.current_name(e.uid)
            display = name.display_name if name else "(unnamed)"
            print(f"  {e.uid}  {e.entity_type.value:<8}  {e.lifecycle_status.value:<10}  {display}")
        print(f"\n  Total: {len(entities)}")
    return 0


def cmd_ontologia_bootstrap(args: argparse.Namespace) -> int:
    """Bootstrap entities from registry-v2.json."""
    if not _check_available():
        return 1

    registry_path = Path(args.registry)
    if not registry_path.is_file():
        print(f"Registry not found: {registry_path}", file=sys.stderr)
        return 1

    store_dir = Path(args.store_dir) if args.store_dir else None
    store = open_store(store_dir)
    result = bootstrap_from_registry(store, registry_path)

    print(f"  Organs created:  {result.organs_created}")
    print(f"  Repos created:   {result.repos_created}")
    print(f"  Organs skipped:  {result.organs_skipped}")
    print(f"  Repos skipped:   {result.repos_skipped}")
    print(f"  Errors:          {len(result.errors)}")
    if result.errors:
        for err in result.errors:
            print(f"    - {err}")
    return 0 if not result.errors else 1


def cmd_ontologia_history(args: argparse.Namespace) -> int:
    """Show name history for an entity."""
    if not _check_available():
        return 1

    store = open_store()
    resolver = store.resolver()
    resolved = resolver.resolve(args.entity)

    if resolved is None:
        print(f"Entity not found: {args.entity}")
        return 1

    names = store.name_history(resolved.identity.uid)
    if not names:
        print("  No name history found.")
        return 0

    print(f"  Name history for {resolved.identity.uid}:")
    for n in names:
        status = "active" if n.valid_to is None else f"retired {n.valid_to}"
        primary = " [primary]" if n.is_primary else ""
        print(f"    {n.valid_from}  {n.display_name}{primary}  ({status})")
    return 0


def cmd_ontologia_events(args: argparse.Namespace) -> int:
    """Show recent ontologia events."""
    if not _check_available():
        return 1

    store = open_store()
    limit = getattr(args, "limit", 20)
    events = store.events(limit=limit)

    if not events:
        print("  No events recorded.")
        return 0

    for e in events:
        entity = e.subject_entity or ""
        print(f"  {e.timestamp}  {e.event_type:<25}  {entity}")
    return 0


def cmd_ontologia_status(args: argparse.Namespace) -> int:
    """Show ontologia store status."""
    if not _check_available():
        return 1

    store = open_store()
    entities = store.list_entities()
    events = store.events(limit=1)

    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for e in entities:
        by_type[e.entity_type.value] = by_type.get(e.entity_type.value, 0) + 1
        by_status[e.lifecycle_status.value] = by_status.get(e.lifecycle_status.value, 0) + 1

    print(f"  Store:    {store.store_dir}")
    print(f"  Entities: {len(entities)}")
    for t, c in sorted(by_type.items()):
        print(f"    {t}: {c}")
    print("  By status:")
    for s, c in sorted(by_status.items()):
        print(f"    {s}: {c}")
    if events:
        print(f"  Last event: {events[-1].timestamp} ({events[-1].event_type})")
    return 0


# ---------------------------------------------------------------------------
# Systema Sentiens commands — sensors, tensions, policies, snapshots, health
# ---------------------------------------------------------------------------

def cmd_ontologia_sense(args: argparse.Namespace) -> int:
    """Run sensors and show detected changes."""
    from organvm_engine.ontologia.sensors import scan_all

    sensor_filter = getattr(args, "sensor", None)
    results = scan_all(sensor_filter=sensor_filter)

    if getattr(args, "json", False):
        # Serialize signals to dicts
        out: dict[str, list] = {}
        for name, signals in results.items():
            out[name] = [_signal_to_dict(s) for s in signals]
        print(json.dumps(out, indent=2, default=str))
        return 0

    total = 0
    for sensor_name, signals in sorted(results.items()):
        if not signals:
            print(f"  {sensor_name}: no signals")
            continue
        print(f"  {sensor_name}: {len(signals)} signals")
        for s in signals:
            sig_type = s.signal_type if hasattr(s, "signal_type") else s.get("type", "")
            entity = s.entity_id if hasattr(s, "entity_id") else s.get("entity", "")
            print(f"    {sig_type:<25} {entity}")
        total += len(signals)
    print(f"\n  Total: {total} signals")
    return 0


def cmd_ontologia_tensions(args: argparse.Namespace) -> int:
    """Run tension detection across all entities."""
    from organvm_engine.ontologia.inference_bridge import detect_tensions

    result = detect_tensions()

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps(result, indent=2, default=str))
        return 0

    print(f"  Tensions: {result['summary']}")
    for category in ("orphans", "naming_conflicts", "overcoupled"):
        items = result.get(category, [])
        if items:
            print(f"\n  {category.replace('_', ' ').title()} ({len(items)}):")
            for t in items:
                names = ", ".join(t.get("entity_names", t.get("entity_ids", [])))
                print(f"    [{t['severity']:.1f}] {t['description']}  ({names})")
    return 0


def cmd_ontologia_policies(args: argparse.Namespace) -> int:
    """List or evaluate governance policies."""
    from organvm_engine.ontologia.policies import (
        evaluate_all_policies,
        load_policies,
    )

    if getattr(args, "evaluate", False):
        result = evaluate_all_policies(
            write_revisions=getattr(args, "write", False),
        )
        if "error" in result:
            print(f"Error: {result['error']}", file=sys.stderr)
            return 1

        if getattr(args, "json", False):
            print(json.dumps(result, indent=2, default=str))
            return 0

        print(f"  Evaluated: {result['evaluated']} entities")
        print(f"  Triggered: {len(result['triggered'])} policy matches")
        if result.get("revisions_created"):
            print(f"  Revisions: {result['revisions_created']} created")
        for t in result["triggered"]:
            print(f"    [{t['action']:<8}] {t['policy_name']}: {t['entity']}")
        return 0

    # List policies
    policies = load_policies()
    if getattr(args, "json", False):
        print(json.dumps(policies, indent=2))
        return 0

    print(f"  Governance Policies ({len(policies)}):")
    for p in policies:
        enabled = "ON" if p.get("enabled", True) else "OFF"
        print(f"    [{enabled}] {p['policy_id']}: {p['name']} → {p['action']}")
    return 0


def cmd_ontologia_snapshot(args: argparse.Namespace) -> int:
    """Create a state snapshot, optionally compare with previous."""
    from organvm_engine.ontologia.snapshots import (
        create_system_snapshot,
        detect_drift,
    )

    if getattr(args, "compare", False):
        result = detect_drift()
        if "error" in result:
            print(f"Error: {result['error']}", file=sys.stderr)
            return 1

        if getattr(args, "json", False):
            print(json.dumps(result, indent=2, default=str))
            return 0

        if result["has_drift"]:
            print(f"  Drift detected ({result['from_date']} → {result['to_date']}):")
            for c in result["changed_entities"]:
                fields = ", ".join(c.get("fields", [])) if c.get("fields") else ""
                print(f"    {c['change']:<10} {c['entity_id']}  {fields}")
        else:
            print("  No drift detected.")
        return 0

    # Create snapshot
    result = create_system_snapshot()
    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps(result, indent=2, default=str))
        return 0

    print(f"  Snapshot created: {result['date']}")
    print(f"  Entities: {result['entity_count']}")
    print(f"  Path: {result['snapshot_path']}")
    return 0


def cmd_ontologia_revisions(args: argparse.Namespace) -> int:
    """Show the revision log."""
    from organvm_engine.ontologia.policies import load_revisions

    status_filter = getattr(args, "status", None)
    revisions = load_revisions(status=status_filter)

    if getattr(args, "json", False):
        print(json.dumps(revisions, indent=2, default=str))
        return 0

    if not revisions:
        print("  No revisions recorded.")
        return 0

    print(f"  Revisions ({len(revisions)}):")
    for r in revisions:
        print(
            f"    [{r.get('status', '?'):<12}] "
            f"{r.get('title', '?'):<40} "
            f"by {r.get('triggered_by', '?')}",
        )
    return 0


def cmd_ontologia_health(args: argparse.Namespace) -> int:
    """Show composite entity health view."""
    from organvm_engine.ontologia.inference_bridge import infer_health

    entity = getattr(args, "entity", None)
    result = infer_health(entity_query=entity)

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps(result, indent=2, default=str))
        return 0

    print(f"  Entities: {result.get('entity_count', '?')}")

    tensions = result.get("tensions", {})
    if isinstance(tensions, dict) and "summary" in tensions:
        print(f"  Tensions: {tensions['summary']}")

    clusters = result.get("clusters", {})
    if isinstance(clusters, dict):
        print(f"  Clusters: {clusters.get('total_clusters', 0)}")

    if "entity" in result and isinstance(result["entity"], dict):
        e = result["entity"]
        if "error" not in e:
            print(f"\n  Entity: {e.get('name', e.get('uid', '?'))}")
            print(f"  Type: {e.get('type', '?')}")
            print(f"  Status: {e.get('status', '?')}")

    blast = result.get("blast_radius", {})
    if blast and "total_affected" in blast:
        print(f"  Blast radius: {blast['total_affected']} entities")
    return 0


def cmd_ontologia_runbooks(args: argparse.Namespace) -> int:
    """Generate or verify operational runbooks."""
    from organvm_engine.ontologia.runbooks import (
        generate_all_runbooks,
        verify_runbooks,
    )

    output_dir = Path(args.output) if getattr(args, "output", None) else None

    if getattr(args, "verify", False):
        result = verify_runbooks(output_dir)
        if getattr(args, "json", False):
            print(json.dumps(result, indent=2))
            return 0
        if result["valid"]:
            print(f"  All {result['total_expected']} runbooks present.")
        else:
            print(f"  Missing: {', '.join(result['missing'])}")
        if result.get("stale"):
            print(f"  Stale (>30d): {', '.join(result['stale'])}")
        return 0 if result["valid"] else 1

    if getattr(args, "generate", False):
        result = generate_all_runbooks(output_dir)
        if getattr(args, "json", False):
            print(json.dumps(result, indent=2, default=str))
            return 0
        print(f"  Generated {result['count']} runbooks:")
        for rb in result["runbooks"]:
            print(f"    {rb['id']}: {rb['title']}")
        return 0

    # Default: verify
    result = verify_runbooks(output_dir)
    if result["valid"]:
        print(f"  All {result['total_expected']} runbooks present.")
    else:
        print(f"  Missing: {', '.join(result['missing'])}")
        print("  Run `organvm ontologia runbooks --generate` to create them.")
    return 0


# ---------------------------------------------------------------------------
# Mutation commands — relocate, reclassify, merge, split
# ---------------------------------------------------------------------------

def cmd_ontologia_relocate(args: argparse.Namespace) -> int:
    """Move an entity to a new parent."""
    if not _check_available():
        return 1

    from ontologia.registry.mutations import relocate_entity

    store = open_store()
    result = relocate_entity(store, args.entity, args.new_parent)

    if not result.success:
        for err in result.errors:
            print(f"Error: {err}", file=sys.stderr)
        return 1

    store.save()

    if getattr(args, "json", False):
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"  Relocated: {args.entity} → parent {args.new_parent}")
        print(f"  Edges closed:  {result.edges_closed}")
        print(f"  Edges created: {result.edges_created}")
        print(f"  Modified:      {', '.join(result.entities_modified)}")
    return 0


def cmd_ontologia_reclassify(args: argparse.Namespace) -> int:
    """Change an entity's type classification."""
    if not _check_available():
        return 1

    from ontologia.registry.mutations import reclassify_entity

    try:
        new_type = EntityType(args.new_type)
    except ValueError:
        valid = ", ".join(t.value for t in EntityType)
        print(f"Invalid entity type: {args.new_type}. Valid: {valid}", file=sys.stderr)
        return 1

    store = open_store()
    result = reclassify_entity(store, args.entity, new_type)

    if not result.success:
        for err in result.errors:
            print(f"Error: {err}", file=sys.stderr)
        return 1

    store.save()

    if getattr(args, "json", False):
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"  Reclassified: {args.entity} → type {args.new_type}")
        print(f"  Modified:     {', '.join(result.entities_modified)}")
    return 0


def cmd_ontologia_merge(args: argparse.Namespace) -> int:
    """Merge multiple entities into a single successor."""
    if not _check_available():
        return 1

    from ontologia.registry.mutations import merge_entities

    store = open_store()
    result = merge_entities(store, args.sources, args.name)

    if not result.success:
        for err in result.errors:
            print(f"Error: {err}", file=sys.stderr)
        return 1

    store.save()

    if getattr(args, "json", False):
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"  Merged {len(args.sources)} entities into: {args.name}")
        print(f"  Created:         {', '.join(result.entities_created)}")
        print(f"  Modified:        {', '.join(result.entities_modified)}")
        print(f"  Lineage records: {result.lineage_records}")
        print(f"  Edges created:   {result.edges_created}")
        print(f"  Edges closed:    {result.edges_closed}")
    return 0


def cmd_ontologia_split(args: argparse.Namespace) -> int:
    """Split one entity into multiple descendants."""
    if not _check_available():
        return 1

    from ontologia.registry.mutations import split_entity

    specs = [{"name": n} for n in args.descendants]
    store = open_store()
    result = split_entity(store, args.source, specs, deprecate_source=args.deprecate)

    if not result.success:
        for err in result.errors:
            print(f"Error: {err}", file=sys.stderr)
        return 1

    store.save()

    if getattr(args, "json", False):
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"  Split {args.source} into {len(result.entities_created)} descendants")
        print(f"  Created:         {', '.join(result.entities_created)}")
        if result.entities_modified:
            print(f"  Modified:        {', '.join(result.entities_modified)}")
        print(f"  Lineage records: {result.lineage_records}")
        print(f"  Edges created:   {result.edges_created}")
        if result.edges_closed:
            print(f"  Edges closed:    {result.edges_closed}")
    return 0


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _signal_to_dict(signal) -> dict:
    """Convert a signal (RawSignal or dict) to a plain dict."""
    if hasattr(signal, "sensor_name"):
        return {
            "sensor": signal.sensor_name,
            "type": signal.signal_type,
            "entity": signal.entity_id,
            "details": signal.details,
            "timestamp": signal.timestamp,
        }
    return signal
