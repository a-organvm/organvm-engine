"""Bridge: indexer → ontologia entity registration.

Registers atomic components discovered by the deep structural indexer
as MODULE entities in the ontologia structural registry.  Each component
gets a permanent UID that survives renames and reorganizations.

Idempotent: skips components already registered (matched by repo+path
in entity metadata).  Creates hierarchy edges from repo→component so
the ontologia graph reflects the actual structural hierarchy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from organvm_engine.indexer.types import SystemIndex

logger = logging.getLogger(__name__)


@dataclass
class BridgeResult:
    """Summary of an indexer→ontologia sync run."""

    components_created: int = 0
    components_skipped: int = 0
    edges_created: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        return self.components_created + self.components_skipped

    def to_dict(self) -> dict[str, Any]:
        return {
            "components_created": self.components_created,
            "components_skipped": self.components_skipped,
            "edges_created": self.edges_created,
            "total_processed": self.total_processed,
            "errors": self.errors,
        }


def _existing_component_tags(store: Any) -> set[str]:
    """Collect repo/path tags from existing MODULE entities."""
    from ontologia.entity.identity import EntityType

    tags: set[str] = set()
    for entity in store.list_entities(entity_type=EntityType.MODULE):
        repo = entity.metadata.get("parent_repo", "")
        path = entity.metadata.get("path", "")
        if repo and path:
            tags.add(f"{repo}:{path}")
    return tags


def _repo_uid_map(store: Any) -> dict[str, str]:
    """Build repo_name → entity UID mapping from existing REPO entities."""
    from ontologia.entity.identity import EntityType

    uids: dict[str, str] = {}
    for entity in store.list_entities(entity_type=EntityType.REPO):
        name = entity.metadata.get("name", "")
        if name:
            uids[name] = entity.uid
    return uids


def _existing_hierarchy_pairs(store: Any) -> set[tuple[str, str]]:
    """Collect existing hierarchy edge (parent, child) pairs."""
    pairs: set[tuple[str, str]] = set()
    for edge in store.edge_index.all_hierarchy_edges():
        if edge.is_active():
            pairs.add((edge.parent_id, edge.child_id))
    return pairs


def register_components(
    system_index: SystemIndex,
    store: Any | None = None,
    created_by: str = "indexer-bridge",
) -> BridgeResult:
    """Register all indexed components as ontologia MODULE entities.

    For each component in the system index:
    1. Skip if already registered (matched by repo:path tag)
    2. Create a MODULE entity with structural metadata
    3. Create a hierarchy edge from the repo entity to the component

    Args:
        system_index: The deep structural index to register.
        store: An ontologia RegistryStore. Opened from default if None.
        created_by: Attribution string for created entities.

    Returns:
        BridgeResult with counts and any errors.
    """
    result = BridgeResult()

    try:
        from ontologia.entity.identity import EntityType
        from ontologia.registry.store import open_store
    except ImportError:
        result.errors.append("ontologia package not installed")
        return result

    if store is None:
        store = open_store()

    existing_tags = _existing_component_tags(store)
    repo_uids = _repo_uid_map(store)
    existing_edges = _existing_hierarchy_pairs(store)

    for repo_index in system_index.repos:
        repo_uid = repo_uids.get(repo_index.repo)

        for component in repo_index.components:
            tag = f"{component.repo}:{component.path}"

            if tag in existing_tags:
                result.components_skipped += 1
                continue

            # Build a display name from the component path
            display_name = component.path.replace("/", "::")

            try:
                entity = store.create_entity(
                    entity_type=EntityType.MODULE,
                    display_name=display_name,
                    created_by=created_by,
                    metadata={
                        "parent_repo": component.repo,
                        "organ_key": component.organ,
                        "path": component.path,
                        "cohesion_type": component.cohesion_type,
                        "dominant_language": component.dominant_language,
                        "depth": component.depth,
                        "file_count": component.file_count,
                        "line_count": component.line_count,
                        "imports_from": component.imports_from,
                        "source": "deep-structural-indexer",
                    },
                )
                result.components_created += 1

                # Create hierarchy edge: repo → component
                if repo_uid and (repo_uid, entity.uid) not in existing_edges:
                    store.add_hierarchy_edge(
                        parent_id=repo_uid,
                        child_id=entity.uid,
                        metadata={
                            "source": created_by,
                            "component_path": component.path,
                        },
                    )
                    existing_edges.add((repo_uid, entity.uid))
                    result.edges_created += 1

            except Exception as exc:
                result.errors.append(f"Failed to register {tag}: {exc}")

    # Persist
    try:
        store.save()
    except Exception as exc:
        result.errors.append(f"Failed to save store: {exc}")

    return result


def sync_index_to_ontologia(
    workspace: Any | None = None,
    registry: dict | None = None,
    repo_filter: str | None = None,
    organ_filter: str | None = None,
) -> BridgeResult:
    """Convenience: run deep index then register in ontologia.

    Combines run_deep_index + register_components in a single call.
    """
    from organvm_engine.indexer import run_deep_index
    from organvm_engine.paths import workspace_root
    from organvm_engine.registry.loader import load_registry

    ws = workspace or workspace_root()
    reg = registry or load_registry()

    system_index = run_deep_index(ws, reg, repo_filter, organ_filter)
    return register_components(system_index)
