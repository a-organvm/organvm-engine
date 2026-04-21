"""PRIM-INST-020 — The Mandator.

Formalizes counselor recommendations into executable directives.  The
mandator is the action layer — it converts judgment into warrant for
action.  In the AEGIS formation, the mandator ALWAYS escalates: the
principal approves all defense directives.

Storage: append-only JSONL at ~/.organvm/institutional/mandator/
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from organvm_engine.primitives.base import InstitutionalPrimitive
from organvm_engine.primitives.types import (
    ExecutionMode,
    Frame,
    InstitutionalContext,
    PrimitiveOutput,
    PrincipalPosition,
    StakesLevel,
)

_DEFAULT_BASE = Path.home() / ".organvm" / "institutional" / "mandator"


# ---------------------------------------------------------------------------
# Mandator-specific types
# ---------------------------------------------------------------------------


@dataclass
class Directive:
    directive_id: str = field(
        default_factory=lambda: f"DIR-{uuid.uuid4().hex[:12]}",
    )
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    action: str = ""
    authority: str = ""  # who/what authorized this
    scope: str = ""
    completion_criteria: list[str] = field(default_factory=list)
    expiry: str | None = None
    priority: str = "normal"  # urgent, normal, deferred
    status: str = "pending"  # pending, approved, active, completed, expired, revoked
    source_recommendation: str = ""
    assigned_to: str = ""  # primitive, formation, or "human"
    constraints: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


class MandatorStore:
    """Append-only directive log."""

    def __init__(self, base_path: Path | None = None) -> None:
        self._base = base_path or _DEFAULT_BASE
        self._directives_path = self._base / "directives.jsonl"

    def _ensure_dirs(self) -> None:
        self._base.mkdir(parents=True, exist_ok=True)

    def record(self, directive: Directive) -> None:
        self._ensure_dirs()
        with self._directives_path.open("a") as f:
            f.write(json.dumps(asdict(directive)) + "\n")

    def load_directives(self, status: str = "") -> list[Directive]:
        if not self._directives_path.exists():
            return []
        directives: list[Directive] = []
        with self._directives_path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    d = Directive(**json.loads(line))
                    if not status or d.status == status:
                        directives.append(d)
        return directives


# ---------------------------------------------------------------------------
# The Mandator primitive
# ---------------------------------------------------------------------------


class Mandator(InstitutionalPrimitive):
    """PRIM-INST-020 — formalizes decisions into executable directives."""

    PRIMITIVE_ID = "PRIM-INST-020"
    PRIMITIVE_NAME = "mandator"
    CLUSTER = "structural"
    DEFAULT_STAKES = StakesLevel.CRITICAL

    def __init__(self, store: MandatorStore | None = None) -> None:
        self._store = store or MandatorStore()

    @property
    def store(self) -> MandatorStore:
        return self._store

    def invoke(
        self,
        context: InstitutionalContext,
        frame: Frame,
        principal_position: PrincipalPosition,
    ) -> PrimitiveOutput:
        rec_data = context.data
        # May receive a Recommendation dict directly, or nested
        if "recommended_action" not in rec_data and "recommendation" in rec_data:
            rec_data = rec_data["recommendation"]

        directive = self._build_directive(rec_data, principal_position)
        self._store.record(directive)

        # Mandator ALWAYS escalates — principal approves all directives
        confidence = rec_data.get("confidence", 0.7)
        confidence = float(confidence) if isinstance(confidence, (int, float)) else 0.7

        exe_mode = ExecutionMode.HUMAN_ROUTED  # always human-reviewed
        stakes = StakesLevel.CRITICAL

        audit = self._make_audit_entry(
            operation="mandate",
            rationale="Formalizing recommendation into directive",
            inputs_summary=f"action={rec_data.get('recommended_action', '')[:80]}",
            output_summary=f"directive_id={directive.directive_id}, "
                           f"priority={directive.priority}",
            execution_mode=exe_mode,
            confidence=confidence,
        )

        return PrimitiveOutput(
            output=asdict(directive),
            confidence=confidence,
            escalation_flag=True,  # ALWAYS escalate
            audit_trail=[audit],
            execution_mode=exe_mode,
            stakes=stakes,
            context_id=context.context_id,
            primitive_id=self.PRIMITIVE_ID,
        )

    # ------------------------------------------------------------------
    # Directive construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_directive(
        rec: dict[str, Any],
        position: PrincipalPosition,
    ) -> Directive:
        action = rec.get("recommended_action", "")
        urgency = rec.get("urgency", "medium_term")
        reversibility = rec.get("reversibility", "reversible")

        # Map urgency to priority
        priority_map = {
            "immediate": "urgent",
            "short_term": "normal",
            "medium_term": "normal",
            "long_term": "deferred",
        }
        priority = priority_map.get(urgency, "normal")

        # Build completion criteria from trade-offs
        criteria: list[str] = []
        trade_offs = rec.get("trade_offs", [])
        if trade_offs and isinstance(trade_offs[0], dict):
            top = trade_offs[0]
            criteria.extend(top.get("pros", []))

        # Build constraints from principal position
        constraints = list(position.constraints) if position.constraints else []
        if reversibility == "irreversible":
            constraints.append("IRREVERSIBLE — requires explicit principal confirmation")

        return Directive(
            action=action,
            authority="counselor-recommendation",
            scope=rec.get("frame_applied", "unscoped"),
            completion_criteria=criteria or [f"Complete: {action}"],
            priority=priority,
            status="pending",
            source_recommendation=rec.get("recommendation_id", ""),
            assigned_to="human",  # default: human executes
            constraints=constraints,
        )
