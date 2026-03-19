"""Bridge excavation findings into ontologia MODULE entities.

Converts BuriedEntity findings (sub-packages detected by the excavation
scanner) into permanent MODULE entities in the ontologia structural
registry. Each sub-package gets a UID that survives renames, relocations,
and extraction into independent repos.

Follows the edge_bridge.py pattern: idempotent, skips existing entities,
creates hierarchy edges from parent repo → sub-package module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ModuleBridgeResult:
    """Summary of excavation → ontologia module sync."""

    modules_created: int = 0
    modules_skipped: int = 0
    hierarchy_edges_created: int = 0
    unresolved_parents: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "modules_created": self.modules_created,
            "modules_skipped": self.modules_skipped,
            "hierarchy_edges_created": self.hierarchy_edges_created,
            "unresolved_parents": self.unresolved_parents,
            "errors": self.errors,
        }


def _module_tag(repo_name: str, entity_path: str) -> str:
    """Build a dedup tag for a module: repo_name/entity_path."""
    return f"{repo_name}/{entity_path}"


def _existing_module_tags(store: Any) -> set[str]:
    """Collect module tags from existing MODULE entities."""
    from ontologia.entity.identity import EntityType

    tags: set[str] = set()
    for entity in store.list_entities(entity_type=EntityType.MODULE):
        repo = entity.metadata.get("parent_repo", "")
        path = entity.metadata.get("entity_path", "")
        if repo and path:
            tags.add(f"{repo}/{path}")
    return tags


def _repo_uid_map(store: Any) -> dict[str, str]:
    """Build repo name → entity UID mapping from ontologia store."""
    from ontologia.entity.identity import EntityType

    mapping: dict[str, str] = {}
    for entity in store.list_entities(entity_type=EntityType.REPO):
        name = entity.metadata.get("name", "")
        if name:
            mapping[name] = entity.uid
    return mapping


def sync_modules_from_excavation(
    findings: list,
    store: Any | None = None,
    created_by: str = "module-bridge",
) -> ModuleBridgeResult:
    """Register excavation sub-package findings as ontologia MODULE entities.

    For each BuriedEntity with entity_type="sub_package", creates a MODULE
    entity in ontologia and a hierarchy edge from the parent repo.

    Idempotent: skips modules whose repo/path tag already exists.

    Args:
        findings: List of BuriedEntity from excavation scanners.
        store: Optional RegistryStore. If None, opens the default store.
        created_by: Attribution string.

    Returns:
        ModuleBridgeResult with counts.
    """
    from ontologia.entity.identity import EntityType

    result = ModuleBridgeResult()

    if store is None:
        from ontologia.registry.store import open_store
        store = open_store()

    # Filter to sub_package findings only
    sub_packages = [f for f in findings if f.entity_type == "sub_package"]
    if not sub_packages:
        return result

    existing_tags = _existing_module_tags(store)
    repo_uids = _repo_uid_map(store)

    # Existing hierarchy edges for dedup
    existing_edges: set[tuple[str, str]] = set()
    for edge in store.edge_index.all_hierarchy_edges():
        if edge.is_active():
            existing_edges.add((edge.parent_id, edge.child_id))

    for finding in sub_packages:
        tag = _module_tag(finding.repo, finding.entity_path)

        if tag in existing_tags:
            result.modules_skipped += 1
            continue

        # Build metadata from the finding
        metadata = {
            "parent_repo": finding.repo,
            "organ_key": finding.organ,
            "entity_path": finding.entity_path,
            "pattern": finding.pattern,
            "severity": finding.severity,
        }
        if finding.scale:
            metadata["scale"] = finding.scale

        try:
            entity = store.create_entity(
                entity_type=EntityType.MODULE,
                display_name=f"{finding.repo}/{finding.entity_path}",
                created_by=created_by,
                metadata=metadata,
            )
            result.modules_created += 1
            existing_tags.add(tag)

            # Create hierarchy edge: parent repo → this module
            parent_uid = repo_uids.get(finding.repo)
            if parent_uid:
                if (parent_uid, entity.uid) not in existing_edges:
                    store.add_hierarchy_edge(
                        parent_id=parent_uid,
                        child_id=entity.uid,
                        metadata={
                            "source": created_by,
                            "pattern": finding.pattern,
                        },
                    )
                    result.hierarchy_edges_created += 1
                    existing_edges.add((parent_uid, entity.uid))
            else:
                result.unresolved_parents += 1
                logger.warning("No ontologia UID for parent repo %s", finding.repo)

        except Exception as exc:
            result.errors.append(f"Failed to create module {tag}: {exc}")

    store.save()
    return result
