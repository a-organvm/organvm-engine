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
