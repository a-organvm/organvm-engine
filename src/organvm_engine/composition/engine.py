"""Composition engine — wires and executes primitive compositions.

The engine takes a CompositionGraph, validates it against prohibited
compositions, resolves primitives from the registry, topologically sorts
into execution stages, and runs them with the appropriate operators.
"""

from __future__ import annotations

from organvm_engine.composition.graph import CompositionGraph, PrimitiveNode
from organvm_engine.composition.operators import (
    parallel_execute,
)
from organvm_engine.composition.prohibitions import validate_composition
from organvm_engine.primitives.base import InstitutionalPrimitive
from organvm_engine.primitives.registry import PrimitiveRegistry
from organvm_engine.primitives.types import (
    AuditEntry,
    Frame,
    FrameType,
    InstitutionalContext,
    PrimitiveOutput,
    PrincipalPosition,
    StakesLevel,
)


class CompositionError(Exception):
    """Raised when a composition is invalid or cannot execute."""


class CompositionEngine:
    """Wires and executes primitive compositions per INST-COMPOSITION."""

    def __init__(self, registry: PrimitiveRegistry) -> None:
        self._registry = registry
        self._formations: dict[str, CompositionGraph] = {}

    def register_formation(
        self,
        name: str,
        graph: CompositionGraph,
    ) -> None:
        """Register a named formation (pre-crystallized graph)."""
        self._formations[name] = graph

    def list_formations(self) -> list[str]:
        return list(self._formations.keys())

    def get_formation_graph(self, name: str) -> CompositionGraph | None:
        return self._formations.get(name)

    def execute_graph(
        self,
        graph: CompositionGraph,
        context: InstitutionalContext,
        principal_position: PrincipalPosition,
    ) -> PrimitiveOutput:
        """Execute a composition graph.

        1. Validate against prohibited compositions
        2. Topological sort into execution stages
        3. Execute stages: parallel within stage, chain between stages
        4. Propagate outputs and escalations
        """
        # Validate
        violations = validate_composition(graph)
        if violations:
            raise CompositionError(
                f"Prohibited composition(s): {'; '.join(violations)}",
            )

        stages = graph.execution_order()
        if not stages:
            return PrimitiveOutput(context_id=context.context_id)

        all_audit: list[AuditEntry] = []
        current_context = context
        min_confidence = 1.0
        last_output: PrimitiveOutput | None = None
        max_stakes = StakesLevel.ROUTINE

        for stage_idx, stage_nodes in enumerate(stages):
            if len(stage_nodes) == 1:
                # Single node — direct invoke
                node = stage_nodes[0]
                prim = self._resolve(node)
                frame = node.frame or Frame(FrameType.OPERATIONAL)
                result = prim.invoke(
                    current_context, frame, principal_position,
                )
            else:
                # Multiple nodes in stage — parallel execution
                prims = [self._resolve(n) for n in stage_nodes]
                frames = [
                    n.frame or Frame(FrameType.OPERATIONAL)
                    for n in stage_nodes
                ]
                result = parallel_execute(
                    prims, current_context, frames, principal_position,
                )

            all_audit.extend(result.audit_trail)
            min_confidence = min(min_confidence, result.confidence)
            if _stakes_rank(result.stakes) > _stakes_rank(max_stakes):
                max_stakes = result.stakes
            last_output = result

            # Check escalation
            if result.escalation_flag:
                return PrimitiveOutput(
                    output=result.output,
                    confidence=min_confidence,
                    escalation_flag=True,
                    audit_trail=all_audit,
                    execution_mode=result.execution_mode,
                    stakes=max_stakes,
                    context_id=context.context_id,
                    primitive_id=result.primitive_id,
                    metadata={
                        "formation": graph.name,
                        "halted_at_stage": stage_idx,
                        "total_stages": len(stages),
                    },
                )

            # Feed output to next stage
            output_data = (
                result.output
                if isinstance(result.output, dict)
                else {"output": result.output}
            )
            current_context = InstitutionalContext(
                context_id=context.context_id,
                timestamp=context.timestamp,
                situation=context.situation,
                data=output_data,
                source=f"stage_{stage_idx}",
                tags=context.tags,
                parent_context_id=context.context_id,
            )

        assert last_output is not None
        return PrimitiveOutput(
            output=last_output.output,
            confidence=min_confidence,
            escalation_flag=False,
            audit_trail=all_audit,
            execution_mode=last_output.execution_mode,
            stakes=max_stakes,
            context_id=context.context_id,
            primitive_id=last_output.primitive_id,
            metadata={"formation": graph.name, "stages_completed": len(stages)},
        )

    def execute_formation(
        self,
        formation_name: str,
        context: InstitutionalContext,
        principal_position: PrincipalPosition,
    ) -> PrimitiveOutput:
        """Look up a formation by name and execute its graph."""
        graph = self._formations.get(formation_name)
        if graph is None:
            raise CompositionError(f"Unknown formation: {formation_name}")
        return self.execute_graph(graph, context, principal_position)

    def _resolve(self, node: PrimitiveNode) -> InstitutionalPrimitive:
        """Resolve a graph node to a live primitive instance."""
        prim = self._registry.get_by_name(node.primitive_name)
        if prim is None:
            prim = self._registry.get_by_id(node.primitive_id)
        if prim is None:
            raise CompositionError(
                f"Primitive not found: {node.primitive_name} ({node.primitive_id})",
            )
        return prim


def _stakes_rank(stakes: StakesLevel) -> int:
    return {
        StakesLevel.ROUTINE: 0,
        StakesLevel.SIGNIFICANT: 1,
        StakesLevel.CRITICAL: 2,
    }.get(stakes, 0)
