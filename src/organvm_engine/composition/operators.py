"""Composition operators (INST-COMPOSITION §3).

Four operators form a complete algebra for primitive composition:
  CHAIN (→)    — sequential, output feeds forward
  PARALLEL (||) — same context, outputs merged
  ENVELOPE (⊃) — outer constrains inner
  FEEDBACK (↻) — iterative until convergence
"""

from __future__ import annotations

from typing import Any

from organvm_engine.primitives.base import InstitutionalPrimitive
from organvm_engine.primitives.types import (
    AuditEntry,
    ExecutionMode,
    Frame,
    InstitutionalContext,
    PrimitiveOutput,
    PrincipalPosition,
    StakesLevel,
)


def chain_execute(
    primitives: list[InstitutionalPrimitive],
    initial_context: InstitutionalContext,
    frames: list[Frame],
    principal_position: PrincipalPosition,
) -> PrimitiveOutput:
    """CHAIN (→): Sequential execution, output feeds forward.

    Each primitive's output becomes the next primitive's context.data.
    Halts on escalation — returns partial output with continuation metadata.
    """
    if not primitives:
        return PrimitiveOutput()

    context = initial_context
    all_audit: list[AuditEntry] = []
    min_confidence = 1.0
    last_output: PrimitiveOutput | None = None

    for i, prim in enumerate(primitives):
        frame = frames[i] if i < len(frames) else frames[-1]
        result = prim.invoke(context, frame, principal_position)

        all_audit.extend(result.audit_trail)
        min_confidence = min(min_confidence, result.confidence)
        last_output = result

        # Halts on escalation
        if result.escalation_flag:
            return PrimitiveOutput(
                output=result.output,
                confidence=min_confidence,
                escalation_flag=True,
                audit_trail=all_audit,
                execution_mode=result.execution_mode,
                stakes=result.stakes,
                context_id=initial_context.context_id,
                primitive_id=prim.PRIMITIVE_ID,
                metadata={
                    "chain_halted_at": i,
                    "chain_total": len(primitives),
                    "remaining_primitives": [
                        p.PRIMITIVE_NAME for p in primitives[i + 1:]
                    ],
                },
            )

        # Feed output forward as next context
        context = InstitutionalContext(
            context_id=initial_context.context_id,
            timestamp=initial_context.timestamp,
            situation=initial_context.situation,
            data=result.output if isinstance(result.output, dict) else {"output": result.output},
            source=prim.PRIMITIVE_NAME,
            tags=initial_context.tags,
            parent_context_id=initial_context.context_id,
        )

    assert last_output is not None
    return PrimitiveOutput(
        output=last_output.output,
        confidence=min_confidence,
        escalation_flag=False,
        audit_trail=all_audit,
        execution_mode=last_output.execution_mode,
        stakes=last_output.stakes,
        context_id=initial_context.context_id,
        primitive_id=last_output.primitive_id,
    )


def parallel_execute(
    primitives: list[InstitutionalPrimitive],
    context: InstitutionalContext,
    frames: list[Frame],
    principal_position: PrincipalPosition,
) -> PrimitiveOutput:
    """PARALLEL (||): All receive same context, outputs merged.

    Confidence = min() across branches.  Any escalation propagates.
    Outputs merged into a dict keyed by primitive name (with frame suffix
    for disambiguation).
    """
    if not primitives:
        return PrimitiveOutput()

    merged_output: dict[str, Any] = {}
    all_audit: list[AuditEntry] = []
    min_confidence = 1.0
    any_escalation = False
    max_stakes = StakesLevel.ROUTINE

    for i, prim in enumerate(primitives):
        frame = frames[i] if i < len(frames) else frames[-1]
        result = prim.invoke(context, frame, principal_position)

        # Key: primitive_name_frametype for disambiguation
        key = f"{prim.PRIMITIVE_NAME}_{frame.frame_type.value}"
        merged_output[key] = result.output

        all_audit.extend(result.audit_trail)
        min_confidence = min(min_confidence, result.confidence)
        if result.escalation_flag:
            any_escalation = True
        if _stakes_rank(result.stakes) > _stakes_rank(max_stakes):
            max_stakes = result.stakes

    return PrimitiveOutput(
        output=merged_output,
        confidence=min_confidence,
        escalation_flag=any_escalation,
        audit_trail=all_audit,
        execution_mode=ExecutionMode.AI_PERFORMED,  # determined per-result
        stakes=max_stakes,
        context_id=context.context_id,
        primitive_id="parallel",
    )


def envelope_execute(
    outer: InstitutionalPrimitive,
    inner: InstitutionalPrimitive,
    context: InstitutionalContext,
    outer_frame: Frame,
    inner_frame: Frame,
    principal_position: PrincipalPosition,
) -> PrimitiveOutput:
    """ENVELOPE (⊃): Outer constrains inner's execution.

    The outer primitive runs first, producing constraints.  The inner
    primitive runs with those constraints injected into its context.
    """
    # Run outer to get constraints
    outer_result = outer.invoke(context, outer_frame, principal_position)

    # Inject outer's output as constraints for inner
    constrained_context = InstitutionalContext(
        context_id=context.context_id,
        timestamp=context.timestamp,
        situation=context.situation,
        data={
            **context.data,
            "envelope_constraints": outer_result.output,
        },
        source=outer.PRIMITIVE_NAME,
        tags=context.tags,
        parent_context_id=context.context_id,
    )

    inner_result = inner.invoke(
        constrained_context, inner_frame, principal_position,
    )

    # Merge audit trails
    all_audit = list(outer_result.audit_trail) + list(inner_result.audit_trail)
    min_confidence = min(outer_result.confidence, inner_result.confidence)

    return PrimitiveOutput(
        output=inner_result.output,
        confidence=min_confidence,
        escalation_flag=outer_result.escalation_flag or inner_result.escalation_flag,
        audit_trail=all_audit,
        execution_mode=inner_result.execution_mode,
        stakes=max(
            outer_result.stakes, inner_result.stakes,
            key=_stakes_rank,
        ),
        context_id=context.context_id,
        primitive_id=inner.PRIMITIVE_ID,
        metadata={"envelope_outer": outer.PRIMITIVE_NAME},
    )


def feedback_execute(
    primitives: list[InstitutionalPrimitive],
    initial_context: InstitutionalContext,
    frames: list[Frame],
    principal_position: PrincipalPosition,
    *,
    max_iterations: int = 5,
    epsilon: float = 0.01,
) -> PrimitiveOutput:
    """FEEDBACK (↻): Iterative refinement until convergence.

    Runs the primitive chain repeatedly, feeding output back as input.
    Stops when confidence change < epsilon or max_iterations reached.
    """
    context = initial_context
    prev_confidence = 0.0
    last_result: PrimitiveOutput | None = None
    all_audit: list[AuditEntry] = []

    for iteration in range(max_iterations):
        result = chain_execute(primitives, context, frames, principal_position)
        all_audit.extend(result.audit_trail)
        last_result = result

        if result.escalation_flag:
            result.metadata["feedback_iteration"] = iteration
            result.audit_trail = all_audit
            return result

        # Check convergence
        delta = abs(result.confidence - prev_confidence)
        if iteration > 0 and delta < epsilon:
            break

        prev_confidence = result.confidence

        # Feed back
        context = InstitutionalContext(
            context_id=initial_context.context_id,
            timestamp=initial_context.timestamp,
            situation=initial_context.situation,
            data=result.output if isinstance(result.output, dict) else {"output": result.output},
            source="feedback",
            tags=initial_context.tags,
            parent_context_id=initial_context.context_id,
        )

    assert last_result is not None
    last_result.audit_trail = all_audit
    last_result.metadata["feedback_iterations"] = min(
        iteration + 1, max_iterations,
    )
    return last_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stakes_rank(stakes: StakesLevel) -> int:
    return {
        StakesLevel.ROUTINE: 0,
        StakesLevel.SIGNIFICANT: 1,
        StakesLevel.CRITICAL: 2,
    }.get(stakes, 0)
