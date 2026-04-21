"""Composition graph — DAG of primitive nodes and operator edges.

A composition graph declares how primitives are wired together.  The
``execution_order()`` method produces a topological sort into stages:
primitives in the same stage can run in parallel; stages execute
sequentially.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from organvm_engine.primitives.types import Frame


@dataclass
class PrimitiveNode:
    """A primitive in a composition graph."""

    primitive_name: str
    primitive_id: str
    frame: Frame | None = None
    node_id: str = ""
    config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.node_id:
            self.node_id = f"{self.primitive_name}_{id(self)}"


@dataclass
class CompositionEdge:
    """Directed edge between two primitive nodes."""

    source_node_id: str
    target_node_id: str
    operator: str  # chain, parallel, envelope, feedback


@dataclass
class CompositionGraph:
    """DAG of primitive nodes wired by composition operators."""

    nodes: list[PrimitiveNode] = field(default_factory=list)
    edges: list[CompositionEdge] = field(default_factory=list)
    name: str = ""
    formation_id: str = ""

    def node_by_id(self, node_id: str) -> PrimitiveNode | None:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None

    def predecessors(self, node_id: str) -> list[str]:
        """Return node_ids of direct predecessors."""
        return [e.source_node_id for e in self.edges if e.target_node_id == node_id]

    def successors(self, node_id: str) -> list[str]:
        """Return node_ids of direct successors."""
        return [e.target_node_id for e in self.edges if e.source_node_id == node_id]

    def execution_order(self) -> list[list[PrimitiveNode]]:
        """Topological sort into execution stages.

        Nodes with no unsatisfied dependencies are grouped into the same
        stage (parallel execution).  Returns a list of stages, each a
        list of PrimitiveNode.
        """
        # Build in-degree map
        in_degree: dict[str, int] = {n.node_id: 0 for n in self.nodes}
        for edge in self.edges:
            in_degree[edge.target_node_id] = (
                in_degree.get(edge.target_node_id, 0) + 1
            )

        node_map = {n.node_id: n for n in self.nodes}
        remaining = set(in_degree.keys())
        stages: list[list[PrimitiveNode]] = []

        while remaining:
            # Nodes with zero in-degree from remaining set
            ready = [
                nid for nid in remaining
                if in_degree.get(nid, 0) == 0
            ]
            if not ready:
                # cycle detected — break with remaining nodes
                stages.append([node_map[nid] for nid in remaining])
                break

            stage = [node_map[nid] for nid in ready]
            stages.append(stage)

            for nid in ready:
                remaining.discard(nid)
                for edge in self.edges:
                    if edge.source_node_id == nid and edge.target_node_id in remaining:
                        in_degree[edge.target_node_id] -= 1

        return stages
