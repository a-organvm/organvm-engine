"""System context file sync — walks workspace, updates auto-generated sections.

The sync process:
1. Load registry + seeds once
2. Walk each organ directory looking for CLAUDE.md, GEMINI.md, and AGENTS.md files
3. For each file, inject or replace the auto-generated section
4. Optionally update the workspace-level context files

Preserves all manually-written content outside the AUTO markers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from organvm_engine.contextmd import AUTO_END, AUTO_START
from organvm_engine.contextmd.generator import (
    generate_agents_section,
    generate_organ_section,
    generate_repo_section,
    generate_workspace_section,
    precompute_ammoi,
)


def sync_all(
    workspace: Path | str | None = None,
    registry_path: str | None = None,
    dry_run: bool = False,
    organs: list[str] | None = None,
) -> dict[str, Any]:
    """Sync auto-generated sections across all context files."""
    from organvm_engine.git.superproject import REGISTRY_KEY_MAP
    from organvm_engine.registry.loader import load_registry
    from organvm_engine.registry.validator import validate_registry
    from organvm_engine.seed.discover import discover_seeds
    from organvm_engine.seed.reader import read_seed

    ws = Path(workspace) if workspace else Path.home() / "Workspace"
    reg = load_registry(registry_path)

    # Pre-flight: Validate registry before sync to prevent breaking 100+ files
    val_result = validate_registry(reg)
    if not val_result.passed:
        raise RuntimeError(
            f"Registry validation failed. Refusing to sync context files.\n{val_result.summary()}",
        )

    # 1. Discover all seeds to have edge data
    seed_paths = discover_seeds(ws)
    all_seeds = []
    repo_to_seed = {}
    for p in seed_paths:
        try:
            s = read_seed(p)
            all_seeds.append(s)
            repo_to_seed[s.get("repo")] = s
        except Exception:
            continue

    # 1b. Discover all SOPs for directive injection
    from organvm_engine.sop.discover import discover_sops
    from organvm_engine.sop.resolver import promotion_to_phase
    from organvm_engine.sop.resolver import resolve_all as resolve_all_sops

    all_sops = discover_sops(workspace=ws)

    # Pre-compute AMMOI once for all context files
    precompute_ammoi()

    updated = []
    created = []
    skipped = []
    errors = []

    target_organs = organs or list(REGISTRY_KEY_MAP.keys())

    for organ_key in target_organs:
        organ_dir_name = REGISTRY_KEY_MAP.get(organ_key)
        if not organ_dir_name:
            continue

        organ_path = ws / organ_dir_name
        if not organ_path.is_dir():
            continue

        # 2. Sync organ-level context files
        for filename in ["CLAUDE.md", "GEMINI.md", "AGENTS.md"]:
            try:
                organ_section = generate_organ_section(organ_key, reg, all_seeds)
                action = _inject_section(organ_path / filename, organ_section, dry_run)
                if action == "created":
                    created.append(str(organ_path / filename))
                elif action == "updated":
                    updated.append(str(organ_path / filename))
                else:
                    skipped.append(str(organ_path / filename))
            except Exception as e:
                errors.append({"path": str(organ_path / filename), "error": str(e)})

        # 3. Sync repo-level context files
        organ_data = reg.get("organs", {}).get(organ_key, {})

        for repo_entry in organ_data.get("repositories", []):
            repo_name = repo_entry.get("name")
            repo_path = organ_path / repo_name
            if not repo_path.is_dir():
                continue

            # Use repo's own org field, fall back to organ directory name
            org_name = repo_entry.get("org") or organ_dir_name

            # Resolve SOPs for this repo, filtered by lifecycle phase
            promo_status = repo_entry.get("promotion_status", "LOCAL")
            repo_phase = promotion_to_phase(promo_status)
            repo_sops = resolve_all_sops(
                all_sops, repo=repo_name, organ=organ_dir_name, phase=repo_phase,
            )

            # Sync CLAUDE.md and GEMINI.md
            for filename in ["CLAUDE.md", "GEMINI.md"]:
                try:
                    res = sync_repo(
                        repo_path,
                        repo_name,
                        org_name,
                        reg,
                        repo_to_seed.get(repo_name),
                        dry_run,
                        filename=filename,
                        sop_entries=repo_sops,
                    )
                    if res["action"] == "created":
                        created.append(res["path"])
                    elif res["action"] == "updated":
                        updated.append(res["path"])
                    else:
                        skipped.append(res["path"])
                except Exception as e:
                    errors.append({"path": str(repo_path / filename), "error": str(e)})

            # Sync AGENTS.md
            try:
                agents_section = generate_agents_section(
                    repo_name, org_name, reg, repo_to_seed.get(repo_name),
                )
                action = _inject_section(repo_path / "AGENTS.md", agents_section, dry_run)
                if action == "created":
                    created.append(str(repo_path / "AGENTS.md"))
                elif action == "updated":
                    updated.append(str(repo_path / "AGENTS.md"))
                else:
                    skipped.append(str(repo_path / "AGENTS.md"))
            except Exception as e:
                errors.append({"path": str(repo_path / "AGENTS.md"), "error": str(e)})

    # 4. Sync workspace-level context files
    for filename in ["CLAUDE.md", "GEMINI.md", "AGENTS.md"]:
        try:
            ws_section = generate_workspace_section(reg, all_seeds)
            action = _inject_section(ws / filename, ws_section, dry_run)
            if action == "created":
                created.append(str(ws / filename))
            elif action == "updated":
                updated.append(str(ws / filename))
            else:
                skipped.append(str(ws / filename))
        except Exception as e:
            errors.append({"path": str(ws / filename), "error": str(e)})

    result = {
        "updated": updated,
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "dry_run": dry_run,
    }

    # Emit context sync event
    if not dry_run:
        try:
            from organvm_engine.pulse.emitter import emit_engine_event
            from organvm_engine.pulse.types import CONTEXT_SYNCED

            emit_engine_event(
                event_type=CONTEXT_SYNCED,
                source="contextmd",
                payload={
                    "updated_count": len(updated),
                    "created_count": len(created),
                    "error_count": len(errors),
                },
            )
        except Exception:
            pass

        # Emit to Testament Chain
        from organvm_engine.ledger.emit import testament_emit
        testament_emit(
            event_type="context.sync",
            source_organ="META-ORGANVM",
            source_repo="organvm-engine",
            actor="cli",
            payload={
                "updated": len(updated),
                "created": len(created),
                "errors": len(errors),
            },
        )

    return result


def sync_repo(
    repo_path: Path,
    repo_name: str,
    org: str,
    registry: dict,
    seed: dict | None = None,
    dry_run: bool = False,
    filename: str = "CLAUDE.md",
    sop_entries: list | None = None,
) -> dict[str, Any]:
    """Sync a single repo's context file."""
    agent = filename.replace(".md", "").lower() if filename else None
    section = generate_repo_section(
        repo_name, org, registry, seed, sop_entries=sop_entries, agent=agent,
    )
    file_path = repo_path / filename
    action = _inject_section(file_path, section, dry_run)
    return {"path": str(file_path), "action": action, "dry_run": dry_run}


def _inject_section(file_path: Path, new_section: str, dry_run: bool = False) -> str:
    """Inject or replace the auto-generated section in a markdown file."""
    import re
    if not file_path.exists():
        if not dry_run:
            file_path.write_text(new_section + "\n")
        return "created"

    content = file_path.read_text()

    # Pre-emptive strike: remove redundant handoff blocks that were previously stacked
    # outside the auto-managed block. This heals files from the non-idempotent bug.
    # We remove ALL instances from the existing content; the new sync will re-inject
    # exactly one instance inside the AUTO markers.
    # We stop before the next header, the AUTO_END marker, or end of string.
    handoff_pattern = r"\n+## Active Handoff Protocol.*?(?=\n+##|" + re.escape(AUTO_END) + r"|$)"
    content = re.sub(handoff_pattern, "", content, flags=re.DOTALL)

    # Clean up any trailing whitespace left by the removal
    content = content.strip()

    if AUTO_START in content and AUTO_END in content:
        # Replace existing section. Using greedy match '.*' instead of '.*?' to ensure
        # that if multiple START/END blocks exist, the entire range is collapsed.
        pattern = re.escape(AUTO_START) + r".*" + re.escape(AUTO_END)
        new_content = re.sub(pattern, new_section, content, flags=re.DOTALL)
        if new_content == content:
            return "unchanged"
        if not dry_run:
            file_path.write_text(new_content)
        return "updated"
    # Append to end
    new_content = content.rstrip() + "\n\n" + new_section + "\n"
    if not dry_run:
        file_path.write_text(new_content)
    return "updated"
