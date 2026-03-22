"""CLI handler for the fossil command group.

Commands:
    fossil excavate   -- Crawl git history and produce fossil-record.jsonl
    fossil chronicle  -- Generate Jungian-voiced epoch narratives
    fossil epochs     -- List all declared epochs
    fossil stratum    -- Query the fossil record
"""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path


def cmd_fossil_excavate(args) -> int:
    """Crawl git history and produce fossil-record.jsonl."""
    from organvm_engine.fossil.excavator import detect_organ_from_path, excavate_repo
    from organvm_engine.fossil.stratum import deserialize_record, serialize_record
    from organvm_engine.paths import fossil_record_path, workspace_root

    workspace = Path(args.workspace).expanduser() if getattr(args, "workspace", None) else None
    if workspace is None:
        workspace = workspace_root()
    if workspace is None or not workspace.is_dir():
        print(f"Workspace not found: {workspace}", file=sys.stderr)
        return 1

    since = getattr(args, "since", None)
    organ_filter = getattr(args, "organ", None)
    write = getattr(args, "write", False)

    record_path = fossil_record_path()

    # Load existing SHAs for idempotent re-runs
    existing_shas: set[str] = set()
    if record_path.exists():
        with contextlib.suppress(OSError), record_path.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    with contextlib.suppress(Exception):
                        rec = deserialize_record(line)
                        existing_shas.add(rec.commit_sha)

    # Find all .git directories up to depth 4
    git_dirs: list[Path] = []
    try:
        for candidate in workspace.rglob(".git"):
            # Check depth: workspace/a/b/c/d/.git → depth from workspace = 5 parts
            try:
                rel = candidate.relative_to(workspace)
            except ValueError:
                continue
            if len(rel.parts) <= 5 and candidate.is_dir():
                git_dirs.append(candidate.parent)
    except OSError as exc:
        print(f"Error scanning workspace: {exc}", file=sys.stderr)
        return 1

    # Apply organ filter
    if organ_filter:
        filtered = []
        for repo_path in git_dirs:
            detected = detect_organ_from_path(repo_path, workspace)
            if detected == organ_filter.upper():
                filtered.append(repo_path)
        git_dirs = filtered

    if not git_dirs:
        print("No git repositories found.")
        return 0

    # Collect new records
    new_records: list[str] = []
    for repo_path in sorted(git_dirs):
        for record in excavate_repo(
            repo_path,
            workspace_root=workspace,
            since=since,
            existing_shas=frozenset(existing_shas),
        ):
            new_records.append(serialize_record(record))

    if not new_records:
        print(f"No new records found (skipped {len(existing_shas)} existing SHAs).")
        return 0

    if write:
        record_path.parent.mkdir(parents=True, exist_ok=True)
        with record_path.open("a") as fh:
            for line in new_records:
                fh.write(line + "\n")
        print(f"Appended {len(new_records)} record(s) to {record_path}")
    else:
        print(f"Dry-run: {len(new_records)} new record(s) found across {len(git_dirs)} repo(s).")
        print(f"  Existing SHAs skipped: {len(existing_shas)}")
        print(f"  Target path: {record_path}")
        print("  Use --write to persist.")

    return 0


def cmd_fossil_chronicle(args) -> int:
    """Generate Jungian-voiced epoch narratives from the fossil record."""
    from organvm_engine.fossil.narrator import generate_all_chronicles
    from organvm_engine.fossil.stratum import deserialize_record
    from organvm_engine.paths import fossil_dir, fossil_record_path

    record_path = fossil_record_path()
    if not record_path.exists():
        print(f"Fossil record not found: {record_path}", file=sys.stderr)
        print("Run: organvm fossil excavate --write", file=sys.stderr)
        return 1

    write = getattr(args, "write", False)
    regenerate = getattr(args, "regenerate", False)
    epoch_filter = getattr(args, "epoch", None)

    # Load all records
    records = []
    with record_path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                with contextlib.suppress(Exception):
                    records.append(deserialize_record(line))

    if not records:
        print("Fossil record is empty.")
        return 0

    # Filter to specific epoch if requested
    if epoch_filter:
        records = [r for r in records if r.epoch == epoch_filter.upper()]
        if not records:
            print(f"No records found for epoch {epoch_filter}")
            return 1

    output_dir = fossil_dir() / "chronicle"

    if write:
        paths = generate_all_chronicles(records, output_dir, regenerate=regenerate)
        print(f"Generated {len(paths)} chronicle(s) in {output_dir}/")
        for p in paths:
            print(f"  {p.name}")
    else:
        # Dry run: count how many would be generated
        from organvm_engine.fossil.epochs import DECLARED_EPOCHS
        from organvm_engine.fossil.narrator import compute_epoch_stats

        epoch_ids = {r.epoch for r in records if r.epoch}
        matching = [e for e in DECLARED_EPOCHS if e.id in epoch_ids]
        print(f"Dry-run: would generate {len(matching)} chronicle(s) in {output_dir}/")
        for e in matching:
            stats = compute_epoch_stats(e, [r for r in records if r.epoch == e.id])
            print(f"  {e.id}  {e.name} ({stats.commit_count} commits, {stats.dominant_archetype.value})")
        print("Use --write to generate.")

    return 0


def cmd_fossil_epochs(args) -> int:
    """List all declared epochs."""
    from organvm_engine.fossil.epochs import DECLARED_EPOCHS

    as_json = getattr(args, "json", False)

    if as_json:
        data = [
            {
                "id": e.id,
                "name": e.name,
                "start": e.start.isoformat(),
                "end": e.end.isoformat(),
                "dominant_archetype": e.dominant_archetype.value,
                "secondary_archetype": (
                    e.secondary_archetype.value if e.secondary_archetype else None
                ),
                "description": e.description,
            }
            for e in DECLARED_EPOCHS
        ]
        json.dump(data, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    col_id = 10
    col_dates = 25
    col_arch = 15
    col_name = 24

    header = (
        f"{'ID':<{col_id}} {'Dates':<{col_dates}} {'Archetype':<{col_arch}}"
        f" {'Name':<{col_name}} Description"
    )
    sep = (
        f"{'─' * col_id} {'─' * col_dates} {'─' * col_arch}"
        f" {'─' * col_name} {'─' * 40}"
    )
    print(header)
    print(sep)
    for e in DECLARED_EPOCHS:
        dates = f"{e.start.isoformat()} — {e.end.isoformat()}"
        arch = e.dominant_archetype.value
        if e.secondary_archetype:
            arch += f"/{e.secondary_archetype.value}"
        desc = e.description
        if len(desc) > 40:
            desc = desc[:39] + "…"
        print(
            f"{e.id:<{col_id}} {dates:<{col_dates}} {arch:<{col_arch}}"
            f" {e.name:<{col_name}} {desc}",
        )

    print()
    print(f"{len(DECLARED_EPOCHS)} epoch(s)")
    return 0


def cmd_fossil_stratum(args) -> int:
    """Query the fossil record."""
    from organvm_engine.fossil.stratum import Archetype, deserialize_record
    from organvm_engine.paths import fossil_record_path

    organ_filter = getattr(args, "organ", None)
    archetype_filter = getattr(args, "archetype", None)
    as_json = getattr(args, "json", False)

    record_path = fossil_record_path()
    if not record_path.exists():
        print(f"Fossil record not found: {record_path}", file=sys.stderr)
        print("Run: organvm fossil excavate --write", file=sys.stderr)
        return 1

    records = []
    try:
        with record_path.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                with contextlib.suppress(Exception):
                    records.append(deserialize_record(line))
    except OSError as exc:
        print(f"Error reading fossil record: {exc}", file=sys.stderr)
        return 1

    # Apply filters
    if organ_filter:
        records = [r for r in records if r.organ == organ_filter.upper()]
    if archetype_filter:
        try:
            arch = Archetype(archetype_filter.lower())
        except ValueError:
            valid = ", ".join(a.value for a in Archetype)
            print(f"Unknown archetype: {archetype_filter!r}. Valid: {valid}", file=sys.stderr)
            return 1
        records = [r for r in records if arch in r.archetypes]

    if as_json:
        data = []
        for r in records:
            d = {
                "commit_sha": r.commit_sha,
                "timestamp": r.timestamp.isoformat(),
                "author": r.author,
                "organ": r.organ,
                "repo": r.repo,
                "message": r.message,
                "conventional_type": r.conventional_type,
                "files_changed": r.files_changed,
                "insertions": r.insertions,
                "deletions": r.deletions,
                "archetypes": [a.value for a in r.archetypes],
                "provenance": r.provenance.value,
                "epoch": r.epoch,
                "tags": r.tags,
            }
            data.append(d)
        json.dump(data, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if not records:
        print("No records found.")
        return 0

    # Summary: count by archetype
    from collections import Counter

    arch_counts: Counter[str] = Counter()
    for r in records:
        for a in r.archetypes:
            arch_counts[a.value] += 1

    organ_counts: Counter[str] = Counter(r.organ for r in records)

    print(f"Fossil Stratum — {len(records)} record(s)")
    print("─" * 40)

    print("\nBy Archetype")
    print("─" * 40)
    for arch, count in sorted(arch_counts.items(), key=lambda x: -x[1]):
        bar = "█" * min(count, 30)
        print(f"  {arch:<16} {count:>5}  {bar}")

    print("\nBy Organ")
    print("─" * 40)
    for organ, count in sorted(organ_counts.items(), key=lambda x: -x[1]):
        print(f"  {organ:<14} {count:>5}")

    return 0
