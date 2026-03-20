"""Feedback network — renderers as nodes in a directed graph.

Each renderer declares what it produces and what it consumes from other
renderers. The cascade runs in topological order, feeding outputs forward.
This is the perpetuity mechanism: every render cycle feeds the next.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RenderNode:
    """A node in the testament feedback graph."""

    name: str
    modality: str
    produces: list[str] = field(default_factory=list)
    consumes: list[str] = field(default_factory=list)
    renderer: str = ""  # module.function path
    description: str = ""


# The canonical feedback graph.
# Each node produces named data shapes consumable by other nodes.
FEEDBACK_GRAPH: list[RenderNode] = [
    RenderNode(
        name="topology",
        modality="visual",
        produces=["organ_positions", "repo_counts", "edge_list"],
        consumes=[],
        renderer="svg.render_constellation",
        description="System topology as stellar constellation",
    ),
    RenderNode(
        name="omega",
        modality="visual",
        produces=["criteria_status", "met_ratio"],
        consumes=[],
        renderer="svg.render_omega_mandala",
        description="Omega scorecard as radial mandala",
    ),
    RenderNode(
        name="density",
        modality="statistical",
        produces=["organ_densities", "density_ranking"],
        consumes=[],
        renderer="svg.render_density_bars",
        description="Per-organ AMMOI density portrait",
    ),
    RenderNode(
        name="status",
        modality="statistical",
        produces=["status_distribution", "total_repos"],
        consumes=[],
        renderer="statistical.render_status_distribution",
        description="Promotion status distribution",
    ),
    RenderNode(
        name="dependency",
        modality="schematic",
        produces=["dep_edges", "dep_depth", "layer_structure"],
        consumes=[],
        renderer="svg.render_dependency_flow",
        description="Unidirectional dependency architecture",
    ),
    RenderNode(
        name="sonic",
        modality="sonic",
        produces=["sonic_params", "voice_config", "rhythm_profile"],
        consumes=[
            "organ_densities", "met_ratio", "status_distribution",
            "dep_depth", "total_repos",
        ],
        renderer="sonic.render_sonic_params",
        description="System metrics as synthesizer parameters",
    ),
    RenderNode(
        name="prose",
        modality="philosophical",
        produces=["self_portrait_text", "axiom_list"],
        consumes=["total_repos", "status_distribution", "met_ratio"],
        renderer="prose.render_self_portrait",
        description="System self-portrait in prose",
    ),
    RenderNode(
        name="social",
        modality="social",
        produces=["pulse_text", "hashtags"],
        consumes=[
            "total_repos", "met_ratio", "organ_densities",
            "density_ranking", "self_portrait_text",
        ],
        renderer="social.render_pulse",
        description="Social-ready system pulse",
    ),
]


def topological_order(nodes: list[RenderNode] | None = None) -> list[RenderNode]:
    """Sort nodes in dependency order (producers before consumers)."""
    graph = nodes or FEEDBACK_GRAPH
    name_to_node = {n.name: n for n in graph}
    produces_map: dict[str, str] = {}
    for n in graph:
        for shape in n.produces:
            produces_map[shape] = n.name

    # Build adjacency: node A must run before node B if B consumes something A produces
    deps: dict[str, set[str]] = {n.name: set() for n in graph}
    for n in graph:
        for shape in n.consumes:
            producer = produces_map.get(shape)
            if producer and producer != n.name:
                deps[n.name].add(producer)

    # Kahn's algorithm
    in_degree = {name: len(d) for name, d in deps.items()}
    queue = [name for name, deg in in_degree.items() if deg == 0]
    order: list[str] = []

    while queue:
        queue.sort()
        current = queue.pop(0)
        order.append(current)
        for name, d in deps.items():
            if current in d:
                d.discard(current)
                in_degree[name] -= 1
                if in_degree[name] == 0:
                    queue.append(name)

    # Append any remaining (cycle-breaking: just add them)
    for n in graph:
        if n.name not in order:
            order.append(n.name)

    return [name_to_node[name] for name in order]


def cascade(
    system_data: dict[str, Any],
    nodes: list[RenderNode] | None = None,
) -> dict[str, dict[str, Any]]:
    """Run all nodes in topological order, accumulating shared state.

    Returns dict mapping node name → its produced data shapes.
    Each node's renderer can read from the shared state (all shapes
    produced by prior nodes) and writes its own shapes back.
    """
    ordered = topological_order(nodes)
    shared_state: dict[str, Any] = dict(system_data)
    results: dict[str, dict[str, Any]] = {}

    for node in ordered:
        # Collect inputs this node needs
        inputs = {shape: shared_state.get(shape) for shape in node.consumes}
        inputs["_system"] = system_data

        # The actual rendering happens in pipeline.py — here we just
        # track the data flow and produce the cascade manifest
        node_result = {
            "name": node.name,
            "modality": node.modality,
            "renderer": node.renderer,
            "inputs_available": {k: v is not None for k, v in inputs.items()},
            "produces": node.produces,
        }
        results[node.name] = node_result

        # Mark shapes as "produced" (actual values filled by pipeline)
        for shape in node.produces:
            if shape not in shared_state:
                shared_state[shape] = f"<produced_by:{node.name}>"

    return results


def network_summary() -> dict[str, Any]:
    """Summary of the feedback network for status display."""
    ordered = topological_order()
    all_shapes = set()
    for n in FEEDBACK_GRAPH:
        all_shapes.update(n.produces)

    return {
        "nodes": len(FEEDBACK_GRAPH),
        "data_shapes": len(all_shapes),
        "execution_order": [n.name for n in ordered],
        "feedback_edges": sum(len(n.consumes) for n in FEEDBACK_GRAPH),
        "source_nodes": [n.name for n in FEEDBACK_GRAPH if not n.consumes],
        "sink_nodes": [
            n.name for n in FEEDBACK_GRAPH
            if not any(
                shape in n.produces
                for other in FEEDBACK_GRAPH
                if other.name != n.name
                for shape in other.consumes
            )
        ],
    }
