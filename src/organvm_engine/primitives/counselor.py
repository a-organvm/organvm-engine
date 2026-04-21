"""PRIM-INST-014 — The Counselor.

Synthesizes multiple assessments into an integrated recommendation with
explicit trade-offs.  The counselor sits between sensing (assessor/guardian)
and action (mandator) — it is the judgment layer.

Expects upstream AssessmentProfile(s) in context.data, optionally with
archivist precedent.  Produces a Recommendation with action, rationale,
trade-offs, and reversibility assessment.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from organvm_engine.primitives.base import InstitutionalPrimitive
from organvm_engine.primitives.types import (
    Frame,
    InstitutionalContext,
    PrimitiveOutput,
    PrincipalPosition,
    StakesLevel,
)

# ---------------------------------------------------------------------------
# Counselor-specific types
# ---------------------------------------------------------------------------


@dataclass
class TradeOff:
    option: str = ""
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    second_order_effects: list[str] = field(default_factory=list)
    estimated_confidence: float = 0.0


@dataclass
class Recommendation:
    recommendation_id: str = field(
        default_factory=lambda: f"REC-{uuid.uuid4().hex[:12]}",
    )
    recommended_action: str = ""
    rationale: str = ""
    trade_offs: list[TradeOff] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    urgency: str = "medium_term"  # immediate, short_term, medium_term, long_term
    reversibility: str = "reversible"  # reversible, partially_reversible, irreversible
    precedent_used: str = ""
    second_order_effects: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Synthesis helpers
# ---------------------------------------------------------------------------


def _extract_assessments(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull assessment profiles from context data."""
    # Direct list of assessments
    if "assessments" in data:
        val = data["assessments"]
        return val if isinstance(val, list) else [val]
    # Single upstream output (from chain)
    if "risk_factors" in data:
        return [data]
    # Parallel merge — keys like "assessor_legal", "assessor_financial"
    found: list[dict[str, Any]] = []
    for _key, val in data.items():
        if isinstance(val, dict) and "risk_factors" in val:
            found.append(val)
    return found


def _urgency_from_risks(risks: list[dict[str, Any]]) -> str:
    """Derive urgency from highest-exposure risk factors."""
    max_exposure = 0.0
    has_deadline = False
    for rf in risks:
        exp = rf.get("exposure", 0.0)
        max_exposure = max(max_exposure, exp)
        if rf.get("deadline"):
            has_deadline = True

    if max_exposure > 0.7 or has_deadline:
        return "immediate"
    if max_exposure > 0.4:
        return "short_term"
    if max_exposure > 0.2:
        return "medium_term"
    return "long_term"


def _reversibility_from_actions(action_vectors: list[str]) -> str:
    """Heuristic: actions involving legal, financial penalties, or entity
    changes are less reversible."""
    irreversible_signals = [
        "dissolution", "filing", "lawsuit", "lien", "eviction",
        "bankruptcy", "garnish", "foreclosure",
    ]
    partial_signals = [
        "penalty", "fee", "late", "interest", "default",
        "cancellation", "termination",
    ]
    text = " ".join(action_vectors).lower()
    if any(s in text for s in irreversible_signals):
        return "irreversible"
    if any(s in text for s in partial_signals):
        return "partially_reversible"
    return "reversible"


# ---------------------------------------------------------------------------
# The Counselor primitive
# ---------------------------------------------------------------------------


class Counselor(InstitutionalPrimitive):
    """PRIM-INST-014 — synthesizes assessments into recommendations."""

    PRIMITIVE_ID = "PRIM-INST-014"
    PRIMITIVE_NAME = "counselor"
    CLUSTER = "epistemic"
    DEFAULT_STAKES = StakesLevel.SIGNIFICANT

    def invoke(
        self,
        context: InstitutionalContext,
        frame: Frame,
        principal_position: PrincipalPosition,
    ) -> PrimitiveOutput:
        assessments = _extract_assessments(context.data)
        precedent = context.data.get("precedent", {})

        # Gather all risk factors across assessments
        all_risks: list[dict[str, Any]] = []
        all_opportunities: list[dict[str, Any]] = []
        all_actions: list[str] = []
        upstream_confidences: list[float] = []

        for assess in assessments:
            all_risks.extend(assess.get("risk_factors", []))
            all_opportunities.extend(assess.get("opportunity_factors", []))
            all_actions.extend(assess.get("action_vectors", []))
            # Track upstream confidence if present
            if "confidence" in assess:
                upstream_confidences.append(assess["confidence"])

        # Sort risks by exposure descending
        all_risks.sort(key=lambda r: r.get("exposure", 0.0), reverse=True)

        # Build recommendation
        rec = self._synthesize(
            all_risks, all_opportunities, all_actions,
            precedent, principal_position,
        )

        # Confidence: min of upstream minus synthesis penalty
        if upstream_confidences:
            confidence = max(0.1, min(upstream_confidences) - 0.05)
        elif assessments:
            confidence = 0.6
        else:
            confidence = 0.3

        # Escalation: irreversible actions or conflicting frames
        frame_types = {
            a.get("frame_applied", "") for a in assessments if a.get("frame_applied")
        }
        frame_conflict = len(frame_types) > 1 and any(
            r.get("exposure", 0) > 0.5 for r in all_risks
        )
        escalate = (
            rec.reversibility == "irreversible"
            or frame_conflict
            or confidence < 0.5
        )

        stakes = self._determine_stakes(all_risks, rec)
        exe_mode = self.determine_execution_mode(confidence, stakes)

        audit = self._make_audit_entry(
            operation="synthesize",
            rationale=f"Synthesized {len(assessments)} assessments, "
                      f"{len(all_risks)} risks, {len(all_opportunities)} opportunities",
            inputs_summary=f"frames={frame_types}, precedent={'yes' if precedent else 'no'}",
            output_summary=f"action={rec.recommended_action[:80]}, "
                           f"urgency={rec.urgency}, reversibility={rec.reversibility}",
            execution_mode=exe_mode,
            confidence=confidence,
        )

        return PrimitiveOutput(
            output=asdict(rec),
            confidence=confidence,
            escalation_flag=escalate,
            audit_trail=[audit],
            execution_mode=exe_mode,
            stakes=stakes,
            context_id=context.context_id,
            primitive_id=self.PRIMITIVE_ID,
        )

    # ------------------------------------------------------------------
    # Synthesis logic
    # ------------------------------------------------------------------

    def _synthesize(
        self,
        risks: list[dict[str, Any]],
        opportunities: list[dict[str, Any]],
        action_vectors: list[str],
        precedent: dict[str, Any],
        principal_position: PrincipalPosition,
    ) -> Recommendation:
        # Primary action: highest-exposure risk gets addressed first
        if risks:
            top_risk = risks[0]
            primary_action = (
                f"Address {top_risk.get('category', 'risk')}: "
                f"{top_risk.get('description', 'unspecified risk')}"
            )
            if top_risk.get("deadline"):
                primary_action += f" (deadline: {top_risk['deadline']})"
        elif opportunities:
            top_opp = opportunities[0]
            primary_action = (
                f"Pursue {top_opp.get('category', 'opportunity')}: "
                f"{top_opp.get('description', 'unspecified opportunity')}"
            )
        else:
            primary_action = "No actionable risks or opportunities detected"

        # Build trade-offs
        trade_offs: list[TradeOff] = []
        if risks:
            # Option A: address the top risk
            trade_offs.append(TradeOff(
                option=f"Address top risk: {risks[0].get('category', '')}",
                pros=["Reduces highest exposure", "Prevents escalation"],
                cons=["May require immediate resources", "Diverts from other work"],
                second_order_effects=self._second_order(risks[0], principal_position),
                estimated_confidence=0.7,
            ))
            # Option B: defer if not critical
            if risks[0].get("exposure", 0) < 0.7:
                trade_offs.append(TradeOff(
                    option="Defer and monitor",
                    pros=["Preserves current resources", "More information may emerge"],
                    cons=["Risk may escalate", "Deadline pressure increases"],
                    second_order_effects=["Exposure may compound if unaddressed"],
                    estimated_confidence=0.5,
                ))

        # Alternatives from action vectors
        alternatives = action_vectors[1:4] if len(action_vectors) > 1 else []

        # Build rationale
        rationale_parts = []
        if risks:
            rationale_parts.append(
                f"{len(risks)} risk factors identified "
                f"(max exposure: {risks[0].get('exposure', 0):.2f})",
            )
        if opportunities:
            rationale_parts.append(f"{len(opportunities)} opportunities noted")
        if precedent:
            rationale_parts.append(
                f"Precedent: {precedent.get('summary', 'available')}",
            )
        rationale = ". ".join(rationale_parts) or "Insufficient data for analysis"

        urgency = _urgency_from_risks(risks)
        reversibility = _reversibility_from_actions(action_vectors)
        precedent_used = precedent.get("record_id", "")

        return Recommendation(
            recommended_action=primary_action,
            rationale=rationale,
            trade_offs=trade_offs,
            alternatives=alternatives,
            urgency=urgency,
            reversibility=reversibility,
            precedent_used=precedent_used,
            second_order_effects=self._aggregate_second_order(
                trade_offs, principal_position,
            ),
        )

    @staticmethod
    def _second_order(
        risk: dict[str, Any],
        position: PrincipalPosition,
    ) -> list[str]:
        effects: list[str] = []
        cat = risk.get("category", "")
        if cat in ("housing", "eviction"):
            effects.append("Housing instability affects all other operations")
        if cat in ("cashflow", "insolvency"):
            effects.append("Financial stress propagates to legal and relational domains")
        if cat in ("litigation", "compliance"):
            effects.append("Legal exposure may restrict operational freedom")
        return effects or ["Monitor for cascading impact"]

    @staticmethod
    def _aggregate_second_order(
        trade_offs: list[TradeOff],
        position: PrincipalPosition,
    ) -> list[str]:
        seen: set[str] = set()
        effects: list[str] = []
        for to in trade_offs:
            for e in to.second_order_effects:
                if e not in seen:
                    seen.add(e)
                    effects.append(e)
        return effects

    @staticmethod
    def _determine_stakes(
        risks: list[dict[str, Any]],
        rec: Recommendation,
    ) -> StakesLevel:
        if rec.reversibility == "irreversible":
            return StakesLevel.CRITICAL
        if risks and risks[0].get("exposure", 0) > 0.7:
            return StakesLevel.CRITICAL
        if rec.urgency == "immediate":
            return StakesLevel.SIGNIFICANT
        return StakesLevel.SIGNIFICANT  # counselor is always at least significant
