"""Core data structures for institutional primitives (SPEC-025).

Every institutional primitive — regardless of cluster — conforms to the
unified interface contract::

    PRIM-INST(context, frame, principal_position)
        → (output, confidence, escalation_flag, audit_trail)

The types here encode that contract in Python dataclasses.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StakesLevel(str, enum.Enum):
    """How much is at risk in this invocation."""

    ROUTINE = "routine"
    SIGNIFICANT = "significant"
    CRITICAL = "critical"


class ExecutionMode(str, enum.Enum):
    """Per-invocation execution mode (SPEC-025 Section 3).

    Mode is determined by confidence × stakes, not by primitive type.
    """

    AI_PERFORMED = "ai_performed"
    AI_PREPARED_HUMAN_REVIEWED = "ai_prepared_human_reviewed"
    HUMAN_ROUTED = "human_routed"
    PROTOCOL_STRUCTURED = "protocol_structured"


class FrameType(str, enum.Enum):
    """Normative frame applied to a primitive invocation."""

    LEGAL = "legal"
    FINANCIAL = "financial"
    RELATIONAL = "relational"
    REPUTATIONAL = "reputational"
    STRATEGIC = "strategic"
    OPERATIONAL = "operational"


# ---------------------------------------------------------------------------
# Input types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Frame:
    """Normative/strategic frame applied to a primitive invocation.

    The frame determines which evaluation criteria matter — a legal frame
    checks liability, jurisdiction, deadlines; a financial frame checks
    exposure, liquidity, solvency.
    """

    frame_type: FrameType
    parameters: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass
class PrincipalPosition:
    """Current state, interests, and objectives of the principal."""

    interests: list[str] = field(default_factory=list)
    objectives: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    current_state: dict[str, Any] = field(default_factory=dict)


@dataclass
class InstitutionalContext:
    """The situation, data, and environmental state under consideration."""

    context_id: str = field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    situation: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    tags: list[str] = field(default_factory=list)
    parent_context_id: str = ""


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------


@dataclass
class AuditEntry:
    """What was done, why, and on what basis."""

    entry_id: str = field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    primitive_id: str = ""
    primitive_name: str = ""
    operation: str = ""
    rationale: str = ""
    inputs_summary: str = ""
    output_summary: str = ""
    execution_mode: str = ""
    confidence: float = 0.0
    duration_ms: float = 0.0


@dataclass
class PrimitiveOutput:
    """Unified output from any institutional primitive invocation."""

    output: Any = None
    confidence: float = 0.0
    escalation_flag: bool = False
    audit_trail: list[AuditEntry] = field(default_factory=list)
    execution_mode: ExecutionMode = ExecutionMode.AI_PERFORMED
    stakes: StakesLevel = StakesLevel.ROUTINE
    context_id: str = ""
    primitive_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
