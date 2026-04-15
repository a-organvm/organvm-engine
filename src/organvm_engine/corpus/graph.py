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
        for _uid, ndata in data.get("nodes", {}).items():
            graph.add_node(GraphNode(**ndata))
        for edata in data.get("edges", []):
            graph.add_edge(GraphEdge(**edata))
        return graph
