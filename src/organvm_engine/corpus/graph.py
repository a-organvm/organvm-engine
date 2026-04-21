"""Corpus knowledge graph data structure and operations."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class GraphNode:
    """A node in the corpus knowledge graph."""

    uid: str
    node_type: str  # concept | transcript | document | spec | repo
    title: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """An edge in the corpus knowledge graph."""

    source: str
    target: str
    edge_type: str  # DEFINES | EXTRACTED_FROM | IMPLEMENTS | REFERENCES | COMPILES
    metadata: dict[str, Any] = field(default_factory=dict)


class CorpusGraph:
    """The corpus knowledge graph — nodes and edges with query operations."""

    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.uid] = node

    def add_edge(self, edge: GraphEdge) -> None:
        self.edges.append(edge)

    def get_node(self, uid: str) -> GraphNode | None:
        return self.nodes.get(uid)

    def edges_from(self, uid: str) -> list[GraphEdge]:
        return [e for e in self.edges if e.source == uid]

    def edges_to(self, uid: str) -> list[GraphEdge]:
        return [e for e in self.edges if e.target == uid]

    def nodes_by_type(self, node_type: str) -> list[GraphNode]:
        return [n for n in self.nodes.values() if n.node_type == node_type]

    def concepts_without_implementation(self) -> list[GraphNode]:
        """Find concepts with no IMPLEMENTS edge targeting them."""
        implemented = {e.target for e in self.edges if e.edge_type == "IMPLEMENTS"}
        return [
            n for n in self.nodes.values()
            if n.node_type == "concept" and n.uid not in implemented
        ]

    def trace_concept(self, concept_id: str) -> dict[str, Any]:
        """Full provenance chain for a concept.

        Returns transcript origins, spec definitions, document extractions,
        and implementing repos with their aspects.
        """
        uid = concept_id if concept_id.startswith("concept:") else f"concept:{concept_id}"
        node = self.get_node(uid)
        if not node:
            return {"error": f"concept '{concept_id}' not found", "concept": concept_id}

        # Transcripts and specs that DEFINE this concept
        definitions: list[dict[str, Any]] = []
        for edge in self.edges_to(uid):
            if edge.edge_type == "DEFINES":
                source = self.get_node(edge.source)
                if source:
                    definitions.append({
                        "uid": source.uid,
                        "type": source.node_type,
                        "title": source.title,
                    })

        # Documents extracted from transcripts that reference this concept
        documents: list[dict[str, Any]] = []
        for edge in self.edges:
            if edge.edge_type == "REFERENCES" and edge.target == uid:
                source = self.get_node(edge.source)
                if source:
                    documents.append({
                        "uid": source.uid,
                        "type": source.node_type,
                        "title": source.title,
                    })

        # Repos that IMPLEMENT this concept
        implementations: list[dict[str, Any]] = []
        for edge in self.edges_to(uid):
            if edge.edge_type == "IMPLEMENTS":
                source = self.get_node(edge.source)
                if source:
                    implementations.append({
                        "uid": source.uid,
                        "repo": source.title,
                        "organ": source.metadata.get("organ", ""),
                        "aspect": edge.metadata.get("aspect", ""),
                    })

        return {
            "concept": concept_id,
            "title": node.title,
            "metadata": node.metadata,
            "definitions": definitions,
            "documents": documents,
            "implementations": implementations,
            "implementation_count": len(implementations),
            "organ_spread": sorted({
                i["organ"] for i in implementations if i["organ"]
            }),
        }

    def coverage_depth(self) -> list[dict[str, Any]]:
        """Per-concept implementation depth and organ distribution.

        Returns all concepts sorted by fragility (fewest implementations first).
        """
        concepts = self.nodes_by_type("concept")
        results = []
        for concept in concepts:
            impls = [
                e for e in self.edges_to(concept.uid)
                if e.edge_type == "IMPLEMENTS"
            ]
            organs: set[str] = set()
            repos: list[str] = []
            for impl in impls:
                repo_node = self.get_node(impl.source)
                if repo_node:
                    repos.append(repo_node.title)
                    organ = repo_node.metadata.get("organ", "")
                    if organ:
                        organs.add(organ)
            results.append({
                "concept": concept.uid.removeprefix("concept:"),
                "title": concept.title,
                "implementations": len(impls),
                "repos": repos,
                "organs": sorted(organs),
                "organ_count": len(organs),
                "fragile": len(impls) <= 1,
            })
        results.sort(key=lambda r: (r["implementations"], r["organ_count"]))
        return results

    def repo_concepts(self, repo_name: str) -> list[dict[str, Any]]:
        """Reverse lookup: what concepts does a repo implement?"""
        results = []
        for edge in self.edges:
            if edge.edge_type != "IMPLEMENTS":
                continue
            source = self.get_node(edge.source)
            if not source or repo_name not in (source.title, source.uid):
                continue
            concept = self.get_node(edge.target)
            if concept:
                results.append({
                    "concept": concept.uid.removeprefix("concept:"),
                    "title": concept.title,
                    "aspect": edge.metadata.get("aspect", ""),
                })
        return results

    def stats(self) -> dict[str, Any]:
        type_counts = {}
        for n in self.nodes.values():
            type_counts[n.node_type] = type_counts.get(n.node_type, 0) + 1
        edge_counts = {}
        for e in self.edges:
            edge_counts[e.edge_type] = edge_counts.get(e.edge_type, 0) + 1
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": type_counts,
            "edge_types": edge_counts,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated": datetime.now(timezone.utc).isoformat(),
            "statistics": self.stats(),
            "nodes": {uid: asdict(n) for uid, n in self.nodes.items()},
            "edges": [asdict(e) for e in self.edges],
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> CorpusGraph:
        data = json.loads(path.read_text(encoding="utf-8"))
        graph = cls()
        for ndata in data.get("nodes", {}).values():
            graph.add_node(GraphNode(**ndata))
        for edata in data.get("edges", []):
            graph.add_edge(GraphEdge(**edata))
        return graph
