"""PRIM-INST-001 — The Assessor.

Evaluates a situation against a normative frame and produces a structured
risk/opportunity profile.  The assessor is the primary sensing primitive —
it translates raw environmental data into actionable risk intelligence.

Phase 0 uses rule-based pattern matching against frame-specific criteria
dictionaries.  Phase 1 will add LLM-powered analysis.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from organvm_engine.primitives.base import InstitutionalPrimitive
from organvm_engine.primitives.types import (
    Frame,
    FrameType,
    InstitutionalContext,
    PrimitiveOutput,
    PrincipalPosition,
    StakesLevel,
)

# ---------------------------------------------------------------------------
# Assessor-specific types
# ---------------------------------------------------------------------------


@dataclass
class RiskFactor:
    category: str
    description: str
    severity: float  # 0.0 to 1.0
    likelihood: float  # 0.0 to 1.0
    exposure: float = 0.0  # severity * likelihood (computed)
    mitigations: list[str] = field(default_factory=list)
    deadline: str | None = None

    def __post_init__(self) -> None:
        self.exposure = self.severity * self.likelihood


@dataclass
class OpportunityFactor:
    category: str
    description: str
    potential_value: float  # 0.0 to 1.0
    effort_required: float  # 0.0 to 1.0
    time_sensitivity: str = ""


@dataclass
class AssessmentProfile:
    risk_factors: list[RiskFactor] = field(default_factory=list)
    opportunity_factors: list[OpportunityFactor] = field(default_factory=list)
    net_exposure: float = 0.0
    action_vectors: list[str] = field(default_factory=list)
    frame_applied: str = ""
    novel_situation: bool = False


# ---------------------------------------------------------------------------
# Frame-specific criteria
# ---------------------------------------------------------------------------

# Each frame maps indicator keywords to (severity_weight, category) tuples.
# The assessor scans context.situation + stringified context.data for these.

_LEGAL_INDICATORS: dict[str, tuple[float, str]] = {
    "lawsuit": (0.9, "litigation"),
    "eviction": (0.95, "housing"),
    "notice": (0.6, "procedural"),
    "deadline": (0.7, "procedural"),
    "overdue": (0.7, "compliance"),
    "violation": (0.8, "compliance"),
    "expired": (0.7, "compliance"),
    "penalty": (0.8, "financial_legal"),
    "lien": (0.85, "encumbrance"),
    "garnish": (0.85, "enforcement"),
    "subpoena": (0.8, "litigation"),
    "default": (0.85, "breach"),
    "breach": (0.8, "breach"),
    "liability": (0.7, "exposure"),
    "statute of limitations": (0.9, "procedural"),
    "court": (0.7, "litigation"),
    "filing": (0.5, "procedural"),
    "annual report": (0.6, "compliance"),
    "registration": (0.5, "compliance"),
    "dissolution": (0.7, "entity"),
    "revocation": (0.8, "compliance"),
}

_FINANCIAL_INDICATORS: dict[str, tuple[float, str]] = {
    "overdue": (0.7, "receivable"),
    "negative": (0.8, "cashflow"),
    "deficit": (0.8, "cashflow"),
    "debt": (0.6, "obligation"),
    "collection": (0.7, "enforcement"),
    "insufficient": (0.7, "liquidity"),
    "exposure": (0.6, "risk"),
    "loss": (0.6, "loss"),
    "penalty": (0.7, "fee"),
    "interest": (0.4, "cost"),
    "late fee": (0.5, "fee"),
    "billing": (0.4, "cost"),
    "delinquent": (0.8, "enforcement"),
    "bankruptcy": (0.95, "insolvency"),
    "insolvent": (0.95, "insolvency"),
    "unpaid": (0.7, "receivable"),
    "grace period": (0.6, "deadline"),
    "cancellation": (0.6, "termination"),
}

_STRATEGIC_INDICATORS: dict[str, tuple[float, str]] = {
    "opportunity": (0.3, "growth"),
    "partnership": (0.3, "alliance"),
    "deadline": (0.6, "timing"),
    "expir": (0.6, "timing"),
    "competi": (0.5, "market"),
    "risk": (0.5, "exposure"),
    "pivot": (0.4, "direction"),
    "consolidat": (0.4, "restructure"),
    "scale": (0.3, "growth"),
    "revenue": (0.4, "income"),
    "contract": (0.5, "agreement"),
}

_OPERATIONAL_INDICATORS: dict[str, tuple[float, str]] = {
    "outage": (0.8, "availability"),
    "failure": (0.7, "reliability"),
    "broken": (0.6, "reliability"),
    "expired": (0.6, "maintenance"),
    "credential": (0.7, "security"),
    "leak": (0.9, "security"),
    "exposed": (0.8, "security"),
    "rotation": (0.5, "maintenance"),
    "backup": (0.5, "resilience"),
    "disk": (0.4, "capacity"),
    "memory": (0.4, "capacity"),
    "timeout": (0.5, "performance"),
}

_RELATIONAL_INDICATORS: dict[str, tuple[float, str]] = {
    "conflict": (0.6, "dispute"),
    "complaint": (0.5, "dissatisfaction"),
    "unresponsive": (0.5, "communication"),
    "deadline": (0.5, "obligation"),
    "trust": (0.4, "relationship"),
    "reputation": (0.5, "standing"),
    "referral": (0.3, "opportunity"),
    "recommendation": (0.3, "opportunity"),
    "introduction": (0.3, "networking"),
}

_FRAME_INDICATORS: dict[FrameType, dict[str, tuple[float, str]]] = {
    FrameType.LEGAL: _LEGAL_INDICATORS,
    FrameType.FINANCIAL: _FINANCIAL_INDICATORS,
    FrameType.STRATEGIC: _STRATEGIC_INDICATORS,
    FrameType.OPERATIONAL: _OPERATIONAL_INDICATORS,
    FrameType.RELATIONAL: _RELATIONAL_INDICATORS,
    FrameType.REPUTATIONAL: _RELATIONAL_INDICATORS,  # reuse relational
}


# ---------------------------------------------------------------------------
# The Assessor primitive
# ---------------------------------------------------------------------------


class Assessor(InstitutionalPrimitive):
    """PRIM-INST-001 — evaluates situation against normative frame."""

    PRIMITIVE_ID = "PRIM-INST-001"
    PRIMITIVE_NAME = "assessor"
    CLUSTER = "protective"
    DEFAULT_STAKES = StakesLevel.ROUTINE

    def invoke(
        self,
        context: InstitutionalContext,
        frame: Frame,
        principal_position: PrincipalPosition,
    ) -> PrimitiveOutput:
        # Build searchable text from context
        search_text = self._build_search_text(context)
        indicators = _FRAME_INDICATORS.get(frame.frame_type, {})

        # Scan for risk factors
        risk_factors = self._scan_risks(search_text, indicators, context)

        # Scan for opportunities
        opportunity_factors = self._scan_opportunities(
            search_text, frame, principal_position,
        )

        # Compute net exposure
        net_exposure = (
            max(rf.exposure for rf in risk_factors)
            if risk_factors else 0.0
        )

        # Build action vectors
        action_vectors = self._derive_actions(
            risk_factors, opportunity_factors, frame,
        )

        # Determine if novel
        novel = len(risk_factors) == 0 and len(opportunity_factors) == 0

        profile = AssessmentProfile(
            risk_factors=risk_factors,
            opportunity_factors=opportunity_factors,
            net_exposure=net_exposure,
            action_vectors=action_vectors,
            frame_applied=frame.frame_type.value,
            novel_situation=novel,
        )

        # Confidence: higher when more indicators matched
        match_count = len(risk_factors) + len(opportunity_factors)
        confidence = min(0.95, 0.4 + match_count * 0.1) if match_count else 0.3

        # Escalation: low confidence or high severity
        escalate = confidence < 0.6 or any(
            rf.severity > 0.8 for rf in risk_factors
        )

        stakes = self._determine_stakes(risk_factors)
        exe_mode = self.determine_execution_mode(confidence, stakes)

        audit = self._make_audit_entry(
            operation="assess",
            rationale=f"Frame={frame.frame_type.value}, {len(risk_factors)} risks, "
                      f"{len(opportunity_factors)} opportunities",
            inputs_summary=f"situation={context.situation[:100]}",
            output_summary=f"net_exposure={net_exposure:.2f}, novel={novel}",
            execution_mode=exe_mode,
            confidence=confidence,
        )

        return PrimitiveOutput(
            output=asdict(profile),
            confidence=confidence,
            escalation_flag=escalate,
            audit_trail=[audit],
            execution_mode=exe_mode,
            stakes=stakes,
            context_id=context.context_id,
            primitive_id=self.PRIMITIVE_ID,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_search_text(context: InstitutionalContext) -> str:
        parts = [context.situation]
        for v in context.data.values():
            if isinstance(v, str):
                parts.append(v)
            elif isinstance(v, (list, tuple)):
                parts.extend(str(item) for item in v)
        return " ".join(parts).lower()

    @staticmethod
    def _scan_risks(
        text: str,
        indicators: dict[str, tuple[float, str]],
        context: InstitutionalContext,
    ) -> list[RiskFactor]:
        found: list[RiskFactor] = []
        for keyword, (severity, category) in indicators.items():
            if keyword.lower() in text:
                # likelihood heuristic: multiple mentions = higher
                mentions = len(re.findall(re.escape(keyword.lower()), text))
                likelihood = min(1.0, 0.5 + mentions * 0.15)

                found.append(RiskFactor(
                    category=category,
                    description=f"Indicator '{keyword}' detected in context",
                    severity=severity,
                    likelihood=likelihood,
                    deadline=context.data.get("deadline"),
                ))
        return found

    @staticmethod
    def _scan_opportunities(
        text: str,
        frame: Frame,
        principal_position: PrincipalPosition,
    ) -> list[OpportunityFactor]:
        opportunities: list[OpportunityFactor] = []
        # Check if any objectives align with context
        for obj in principal_position.objectives:
            obj_lower = obj.lower()
            if any(word in text for word in obj_lower.split() if len(word) > 3):
                opportunities.append(OpportunityFactor(
                    category="objective_alignment",
                    description=f"Context relates to objective: {obj}",
                    potential_value=0.6,
                    effort_required=0.5,
                ))
        return opportunities

    @staticmethod
    def _derive_actions(
        risks: list[RiskFactor],
        opportunities: list[OpportunityFactor],
        frame: Frame,
    ) -> list[str]:
        actions: list[str] = []
        # High-exposure risks get immediate action vectors
        for rf in sorted(risks, key=lambda r: r.exposure, reverse=True)[:3]:
            if rf.exposure > 0.5:
                actions.append(
                    f"[{frame.frame_type.value}] Address {rf.category}: "
                    f"{rf.description} (exposure={rf.exposure:.2f})",
                )
            if rf.deadline:
                actions.append(
                    f"[{frame.frame_type.value}] Deadline-sensitive: "
                    f"{rf.category} by {rf.deadline}",
                )
        for opp in opportunities[:2]:
            actions.append(
                f"[{frame.frame_type.value}] Pursue: {opp.description}",
            )
        return actions

    @staticmethod
    def _determine_stakes(risks: list[RiskFactor]) -> StakesLevel:
        if any(rf.severity >= 0.9 for rf in risks):
            return StakesLevel.CRITICAL
        if any(rf.severity >= 0.7 for rf in risks):
            return StakesLevel.SIGNIFICANT
        return StakesLevel.ROUTINE
