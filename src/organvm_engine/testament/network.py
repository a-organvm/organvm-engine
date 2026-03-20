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
    execute: bool = False,
    registry_path: Any = None,
) -> dict[str, dict[str, Any]]:
    """Run all nodes in topological order, accumulating shared state.

    When execute=False (default), builds a manifest of what would be produced.
    When execute=True, actually invokes node executors and passes real data
    between nodes via the shared_state dict.

    Returns dict mapping node name → its produced data + rendered content.
    """
    ordered = topological_order(nodes)
    shared_state: dict[str, Any] = dict(system_data)
    results: dict[str, dict[str, Any]] = {}

    for node in ordered:
        # Collect inputs this node needs from shared state
        inputs = {shape: shared_state.get(shape) for shape in node.consumes}
        inputs["_system"] = system_data

        if execute:
            # Actually run the node executor and capture real data shapes
            node_output = _execute_node(node, shared_state, registry_path)
            # Merge produced shapes into shared state for downstream nodes
            for shape, value in node_output.get("shapes", {}).items():
                shared_state[shape] = value

            results[node.name] = {
                "name": node.name,
                "modality": node.modality,
                "renderer": node.renderer,
                "executed": True,
                "success": node_output.get("success", False),
                "content_length": len(node_output.get("content", "")),
                "shapes_produced": list(node_output.get("shapes", {}).keys()),
                "inputs_received": {
                    k: v is not None for k, v in inputs.items()
                    if k != "_system"
                },
                "error": node_output.get("error"),
            }
        else:
            # Manifest-only mode (original behavior)
            results[node.name] = {
                "name": node.name,
                "modality": node.modality,
                "renderer": node.renderer,
                "executed": False,
                "inputs_available": {
                    k: v is not None for k, v in inputs.items()
                    if k != "_system"
                },
                "produces": node.produces,
            }
            for shape in node.produces:
                if shape not in shared_state:
                    shared_state[shape] = f"<produced_by:{node.name}>"

    return results


def _execute_node(
    node: RenderNode,
    shared_state: dict[str, Any],
    registry_path: Any = None,
) -> dict[str, Any]:
    """Execute a single node, producing real data shapes and rendered content."""
    shapes: dict[str, Any] = {}
    content = ""

    try:
        if node.name == "topology":
            from organvm_engine.testament.sources import topology_data
            data = topology_data(registry_path)
            shapes["organ_positions"] = {
                k: i for i, k in enumerate(data.get("organ_repo_counts", {}).keys())
            }
            shapes["repo_counts"] = data.get("organ_repo_counts", {})
            shapes["edge_list"] = data.get("edges", [])
            shapes["total_repos"] = data.get("total_repos", 0)

            from organvm_engine.testament.renderers.svg import render_constellation
            content = render_constellation(organ_repo_counts=data["organ_repo_counts"])

        elif node.name == "omega":
            from organvm_engine.testament.sources import omega_data
            data = omega_data(registry_path)
            shapes["criteria_status"] = data.get("criteria", [])
            met = data.get("met_count", 0)
            total = data.get("total", 17)
            shapes["met_ratio"] = met / total if total else 0

            from organvm_engine.testament.renderers.svg import render_omega_mandala
            content = render_omega_mandala(
                criteria=data["criteria"], met_count=met, total=total,
            )

        elif node.name == "density":
            from organvm_engine.testament.sources import density_data
            data = density_data(registry_path)
            densities = data.get("organ_densities", {})
            shapes["organ_densities"] = densities
            shapes["density_ranking"] = sorted(
                densities, key=lambda k: densities.get(k, 0), reverse=True,
            )

            from organvm_engine.testament.renderers.svg import render_density_bars
            content = render_density_bars(organ_densities=densities)

        elif node.name == "status":
            from organvm_engine.testament.sources import system_summary
            data = system_summary(registry_path)
            shapes["status_distribution"] = data.get("status_counts", {})
            shapes["total_repos"] = data.get("total_repos", 0)

            from organvm_engine.testament.renderers.statistical import (
                render_status_distribution,
            )
            content = render_status_distribution(data["status_counts"])

        elif node.name == "dependency":
            shapes["dep_edges"] = []
            shapes["dep_depth"] = 3
            shapes["layer_structure"] = {
                "production": ["I", "II", "III"],
                "control": ["IV"],
                "interface": ["V", "VI", "VII"],
                "meta": ["META"],
            }

            from organvm_engine.testament.renderers.svg import render_dependency_flow
            content = render_dependency_flow()

        elif node.name == "sonic":
            from organvm_engine.testament.renderers.sonic import (
                render_sonic_params,
                render_sonic_yaml,
            )
            testament = render_sonic_params(
                organ_densities=shared_state.get("organ_densities", {}),
                status_distribution=shared_state.get("status_distribution", {}),
                met_ratio=shared_state.get("met_ratio", 0.5),
                total_repos=shared_state.get("total_repos", 0),
            )
            content = render_sonic_yaml(testament)
            shapes["sonic_params"] = {
                "voices": len(testament.voices),
                "bpm": testament.rhythm.bpm if testament.rhythm else 120,
                "master": testament.master_amplitude,
            }
            shapes["voice_config"] = [
                {"organ": v.organ, "freq": v.frequency, "amp": v.amplitude}
                for v in testament.voices
            ]
            shapes["rhythm_profile"] = {
                "bpm": testament.rhythm.bpm if testament.rhythm else 120,
                "time_sig": testament.rhythm.time_signature if testament.rhythm else "4/4",
            }

        elif node.name == "prose":
            from organvm_engine.testament.renderers.prose import render_self_portrait
            system_data_for_prose = {
                "total_repos": shared_state.get("total_repos", 0),
                "total_organs": 8,
                "total_public": 0,
                "status_counts": shared_state.get("status_distribution", {}),
            }
            content = render_self_portrait(system_data_for_prose)
            shapes["self_portrait_text"] = content
            shapes["axiom_list"] = [
                "Ontological Primacy", "Organizational Closure",
                "Individual Primacy", "Constitutional Governance",
                "Evolutionary Recursivity", "Topological Plasticity",
                "Alchemical Inheritance", "Multiplex Flow Governance",
                "Modular Alchemical Synthesis",
            ]

        elif node.name == "social":
            from organvm_engine.testament.renderers.social import render_pulse
            pulse = render_pulse(
                total_repos=shared_state.get("total_repos", 0),
                met_ratio=shared_state.get("met_ratio", 0),
                organ_densities=shared_state.get("organ_densities", {}),
                density_ranking=shared_state.get("density_ranking", []),
                self_portrait_text=shared_state.get("self_portrait_text"),
            )
            content = pulse.short
            shapes["pulse_text"] = pulse.short
            shapes["hashtags"] = pulse.hashtags

        return {
            "success": True,
            "content": content,
            "shapes": shapes,
        }

    except Exception as exc:
        return {
            "success": False,
            "content": "",
            "shapes": shapes,
            "error": str(exc),
        }


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
