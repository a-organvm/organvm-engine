"""Abstract base class for institutional primitives (SPEC-025 Section 2).

Every institutional primitive inherits from ``InstitutionalPrimitive`` and
implements ``invoke()``.  The ABC enforces the unified interface contract
at instantiation time — a primitive that forgets to implement ``invoke``
cannot be created.
"""

from __future__ import annotations

import abc
import time

from organvm_engine.primitives.execution import mode_for_invocation
from organvm_engine.primitives.types import (
    AuditEntry,
    ExecutionMode,
    Frame,
    InstitutionalContext,
    PrimitiveOutput,
    PrincipalPosition,
    StakesLevel,
)


class InstitutionalPrimitive(abc.ABC):
    """Abstract base for all institutional primitives."""

    PRIMITIVE_ID: str = ""
    PRIMITIVE_NAME: str = ""
    CLUSTER: str = ""
    DEFAULT_STAKES: StakesLevel = StakesLevel.ROUTINE

    @abc.abstractmethod
    def invoke(
        self,
        context: InstitutionalContext,
        frame: Frame,
        principal_position: PrincipalPosition,
    ) -> PrimitiveOutput:
        """Execute the primitive's irreducible operation."""

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def determine_execution_mode(
        self,
        confidence: float,
        stakes: StakesLevel,
        *,
        is_deterministic: bool = False,
    ) -> ExecutionMode:
        """Per-invocation execution mode (delegates to standalone fn)."""
        return mode_for_invocation(
            confidence, stakes, is_deterministic=is_deterministic,
        )

    def _make_audit_entry(
        self,
        operation: str,
        rationale: str,
        inputs_summary: str,
        output_summary: str,
        execution_mode: ExecutionMode,
        confidence: float,
        duration_ms: float = 0.0,
    ) -> AuditEntry:
        """Build an audit trail entry for this primitive."""
        return AuditEntry(
            primitive_id=self.PRIMITIVE_ID,
            primitive_name=self.PRIMITIVE_NAME,
            operation=operation,
            rationale=rationale,
            inputs_summary=inputs_summary,
            output_summary=output_summary,
            execution_mode=execution_mode.value,
            confidence=confidence,
            duration_ms=duration_ms,
        )

    def _timed_invoke(
        self,
        context: InstitutionalContext,
        frame: Frame,
        principal_position: PrincipalPosition,
    ) -> tuple[PrimitiveOutput, float]:
        """Invoke with wall-clock timing.  Returns (output, ms)."""
        t0 = time.monotonic()
        result = self.invoke(context, frame, principal_position)
        elapsed_ms = (time.monotonic() - t0) * 1000
        return result, elapsed_ms
