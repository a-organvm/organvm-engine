"""Tests for the Assessor primitive."""

from organvm_engine.primitives.assessor import Assessor, AssessmentProfile
from organvm_engine.primitives.types import (
    Frame,
    FrameType,
    InstitutionalContext,
    PrincipalPosition,
)


def test_assessor_legal_risk_detection():
    assessor = Assessor()
    context = InstitutionalContext(
        situation="Eviction notice received, deadline approaching",
        data={"deadline": "2026-05-01"},
    )
    frame = Frame(FrameType.LEGAL)
    position = PrincipalPosition()

    result = assessor.invoke(context, frame, position)
    profile = result.output

    assert isinstance(profile, dict)
    assert len(profile["risk_factors"]) > 0
    assert profile["frame_applied"] == "legal"
    assert result.escalation_flag is True  # eviction = severity > 0.8


def test_assessor_financial_risk_detection():
    assessor = Assessor()
    context = InstitutionalContext(
        situation="Account shows negative balance and overdue payments",
    )
    frame = Frame(FrameType.FINANCIAL)
    position = PrincipalPosition()

    result = assessor.invoke(context, frame, position)
    profile = result.output

    assert len(profile["risk_factors"]) > 0
    categories = {rf["category"] for rf in profile["risk_factors"]}
    assert "cashflow" in categories or "receivable" in categories


def test_assessor_no_risks():
    assessor = Assessor()
    context = InstitutionalContext(
        situation="Everything is going smoothly today",
    )
    frame = Frame(FrameType.OPERATIONAL)
    position = PrincipalPosition()

    result = assessor.invoke(context, frame, position)
    profile = result.output

    assert profile["novel_situation"] is True
    assert result.confidence <= 0.4


def test_assessor_opportunity_detection():
    assessor = Assessor()
    context = InstitutionalContext(
        situation="New contracts opportunity available for freelance work",
    )
    frame = Frame(FrameType.STRATEGIC)
    position = PrincipalPosition(
        objectives=["Secure new contracts"],
    )

    result = assessor.invoke(context, frame, position)
    profile = result.output

    assert len(profile["opportunity_factors"]) > 0


def test_assessor_stakes_escalation():
    assessor = Assessor()
    context = InstitutionalContext(
        situation="Bankruptcy filing deadline missed",
    )
    frame = Frame(FrameType.FINANCIAL)
    position = PrincipalPosition()

    result = assessor.invoke(context, frame, position)
    assert result.stakes.value in ("significant", "critical")
