"""Multi-scale relation query — unified graph traversal.

Spans three scales of relation:
  1. Inter-repo (seed graph): produces/consumes edges between repos
  2. Intra-repo (indexer): import edges between atomic components
  3. Entity-level (ontologia): hierarchy + relation edges between UIDs

Returns a RelationMap that gives any entity a complete picture of
its connections at all scales — fulfilling the prime directive's
"sense its relations" capability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RelationEdgeDTO:
    """A single relation edge at any scale."""

    source: str
    target: str
    relation_type: str  # "produces", "consumes", "imports", "hierarchy", "relation"
    scale: str  # "inter_repo", "intra_repo", "entity"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation_type": self.relation_type,
            "scale": self.scale,
            "metadata": self.metadata,
        }


@dataclass
class RelationMap:
    """Complete multi-scale relation map for an entity."""

    entity: str  # name or UID that was queried
    entity_uid: str = ""
    entity_type: str = ""

    # Inter-repo scale (seed graph)
    seed_produces: list[RelationEdgeDTO] = field(default_factory=list)
    seed_consumes: list[RelationEdgeDTO] = field(default_factory=list)

    # Intra-repo scale (indexer import graph)
    imports_from: list[RelationEdgeDTO] = field(default_factory=list)
    imported_by: list[RelationEdgeDTO] = field(default_factory=list)

    # Entity scale (ontologia)
    hierarchy_parents: list[RelationEdgeDTO] = field(default_factory=list)
    hierarchy_children: list[RelationEdgeDTO] = field(default_factory=list)
    ontologia_relations: list[RelationEdgeDTO] = field(default_factory=list)

    @property
    def total_edges(self) -> int:
        return (
            len(self.seed_produces)
            + len(self.seed_consumes)
            + len(self.imports_from)
            + len(self.imported_by)
            + len(self.hierarchy_parents)
            + len(self.hierarchy_children)
            + len(self.ontologia_relations)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity": self.entity,
            "entity_uid": self.entity_uid,
            "entity_type": self.entity_type,
            "total_edges": self.total_edges,
            "inter_repo": {
                "produces": [e.to_dict() for e in self.seed_produces],
                "consumes": [e.to_dict() for e in self.seed_consumes],
            },
            "intra_repo": {
                "imports_from": [e.to_dict() for e in self.imports_from],
                "imported_by": [e.to_dict() for e in self.imported_by],
            },
            "entity_level": {
                "hierarchy_parents": [e.to_dict() for e in self.hierarchy_parents],
                "hierarchy_children": [e.to_dict() for e in self.hierarchy_children],
                "relations": [e.to_dict() for e in self.ontologia_relations],
            },
        }


def _gather_seed_edges(entity_name: str, rmap: RelationMap) -> None:
    """Populate inter-repo edges from the seed graph."""
    try:
        from organvm_engine.seed.graph import build_seed_graph

        graph = build_seed_graph()

        # Find matching node (repo name may appear as org/name or just name)
        matched_identity = ""
        for node in graph.nodes:
            if node == entity_name or node.endswith(f"/{entity_name}"):
                matched_identity = node
                break

        if not matched_identity:
            return

        # Produces edges: this entity → targets
        for src, tgt, artifact_type in graph.edges:
            if src == matched_identity:
                rmap.seed_produces.append(RelationEdgeDTO(
                    source=src,
                    target=tgt,
                    relation_type="produces",
                    scale="inter_repo",
                    metadata={"artifact_type": artifact_type},
                ))
            elif tgt == matched_identity:
                rmap.seed_consumes.append(RelationEdgeDTO(
                    source=src,
                    target=tgt,
                    relation_type="consumes",
                    scale="inter_repo",
                    metadata={"artifact_type": artifact_type},
                ))
    except Exception:
        logger.debug("Seed graph unavailable for relation query", exc_info=True)


def _gather_indexer_edges(entity_name: str, rmap: RelationMap) -> None:
    """Populate intra-repo edges from the cached deep-index.json."""
    import json

    try:
        from organvm_engine.paths import corpus_dir

        index_path = corpus_dir() / "data" / "index" / "deep-index.json"
        if not index_path.is_file():
            return

        idx_data = json.loads(index_path.read_text())

        for repo_data in idx_data.get("repos", []):
            repo_name = repo_data.get("repo", "")
            if repo_name != entity_name:
                continue

            # Found matching repo — extract component import edges
            for comp in repo_data.get("components", []):
                comp_path = comp.get("path", "")
                for imp in comp.get("imports_from", []):
                    rmap.imports_from.append(RelationEdgeDTO(
                        source=comp_path,
                        target=imp,
                        relation_type="imports",
                        scale="intra_repo",
                        metadata={"repo": repo_name},
                    ))
                for imp_by in comp.get("imported_by", []):
                    rmap.imported_by.append(RelationEdgeDTO(
                        source=imp_by,
                        target=comp_path,
                        relation_type="imported_by",
                        scale="intra_repo",
                        metadata={"repo": repo_name},
                    ))
            break

        # Also check if entity_name is a component path within any repo
        for repo_data in idx_data.get("repos", []):
            for comp in repo_data.get("components", []):
                if comp.get("path", "") == entity_name:
                    for imp in comp.get("imports_from", []):
                        rmap.imports_from.append(RelationEdgeDTO(
                            source=entity_name,
                            target=imp,
                            relation_type="imports",
                            scale="intra_repo",
                            metadata={"repo": repo_data.get("repo", "")},
                        ))
                    for imp_by in comp.get("imported_by", []):
                        rmap.imported_by.append(RelationEdgeDTO(
                            source=imp_by,
                            target=entity_name,
                            relation_type="imported_by",
                            scale="intra_repo",
                            metadata={"repo": repo_data.get("repo", "")},
                        ))
    except Exception:
        logger.debug("Indexer data unavailable for relation query", exc_info=True)


def _gather_ontologia_edges(entity_name: str, rmap: RelationMap) -> None:
    """Populate entity-level edges from ontologia store."""
    try:
        from ontologia.registry.store import open_store

        store = open_store()
        if store.entity_count == 0:
            return

        # Resolve entity
        resolver = store.resolver()
        result = resolver.resolve(entity_name)
        if not result:
            return

        uid = result.identity.uid
        rmap.entity_uid = uid
        rmap.entity_type = result.identity.entity_type.value

        edge_index = store.edge_index

        # Hierarchy: find parents (edges where this entity is the child)
        for edge in edge_index.all_hierarchy_edges():
            if not edge.is_active():
                continue
            if edge.child_id == uid:
                parent = store.get_entity(edge.parent_id)
                parent_name = ""
                if parent:
                    nr = store.current_name(parent.uid)
                    parent_name = nr.display_name if nr else parent.uid
                rmap.hierarchy_parents.append(RelationEdgeDTO(
                    source=parent_name or edge.parent_id,
                    target=entity_name,
                    relation_type="hierarchy",
                    scale="entity",
                    metadata={"parent_uid": edge.parent_id},
                ))
            elif edge.parent_id == uid:
                child = store.get_entity(edge.child_id)
                child_name = ""
                if child:
                    nr = store.current_name(child.uid)
                    child_name = nr.display_name if nr else child.uid
                rmap.hierarchy_children.append(RelationEdgeDTO(
                    source=entity_name,
                    target=child_name or edge.child_id,
                    relation_type="hierarchy",
                    scale="entity",
                    metadata={"child_uid": edge.child_id},
                ))

        # Relation edges
        for edge in edge_index.all_relation_edges():
            if not edge.is_active():
                continue
            if edge.source_id == uid:
                target = store.get_entity(edge.target_id)
                target_name = ""
                if target:
                    nr = store.current_name(target.uid)
                    target_name = nr.display_name if nr else target.uid
                rmap.ontologia_relations.append(RelationEdgeDTO(
                    source=entity_name,
                    target=target_name or edge.target_id,
                    relation_type=edge.relation_type,
                    scale="entity",
                    metadata={"target_uid": edge.target_id},
                ))
            elif edge.target_id == uid:
                source = store.get_entity(edge.source_id)
                source_name = ""
                if source:
                    nr = store.current_name(source.uid)
                    source_name = nr.display_name if nr else source.uid
                rmap.ontologia_relations.append(RelationEdgeDTO(
                    source=source_name or edge.source_id,
                    target=entity_name,
                    relation_type=edge.relation_type,
                    scale="entity",
                    metadata={"source_uid": edge.source_id},
                ))

    except ImportError:
        logger.debug("ontologia not available for relation query", exc_info=True)
    except Exception:
        logger.debug("Ontologia edge query failed (non-fatal)", exc_info=True)


def query_relations(
    entity_name: str,
    include_seed: bool = True,
    include_indexer: bool = True,
    include_ontologia: bool = True,
) -> RelationMap:
    """Query all relations for an entity across all scales.

    Assembles a complete picture from seed graph (inter-repo),
    deep index (intra-repo imports), and ontologia (entity-level
    hierarchy + relation edges).

    Args:
        entity_name: Repo name, component path, or entity UID.
        include_seed: Include inter-repo seed graph edges.
        include_indexer: Include intra-repo import edges.
        include_ontologia: Include ontologia entity edges.

    Returns:
        RelationMap with all discovered relations.
    """
    rmap = RelationMap(entity=entity_name)

    if include_seed:
        _gather_seed_edges(entity_name, rmap)

    if include_indexer:
        _gather_indexer_edges(entity_name, rmap)

    if include_ontologia:
        _gather_ontologia_edges(entity_name, rmap)

    return rmap
