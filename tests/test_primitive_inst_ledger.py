"""Tests for the Institutional Ledger primitive."""

from organvm_engine.primitives.inst_ledger import (
    InstitutionalLedger,
    LedgerStore,
)
from organvm_engine.primitives.types import (
    ExecutionMode,
    Frame,
    FrameType,
    InstitutionalContext,
    PrincipalPosition,
)


def test_ledger_record_entry(tmp_path):
    store = LedgerStore(base_path=tmp_path)
    ledger = InstitutionalLedger(store=store)

    context = InstitutionalContext(
        situation="Record salary",
        data={
            "mode": "record",
            "category": "income",
            "amount": 5000,
            "direction": "inflow",
            "description": "April salary",
            "recurring": True,
            "frequency": "monthly",
        },
    )
    result = ledger.invoke(context, Frame(FrameType.FINANCIAL), PrincipalPosition())

    assert result.confidence == 1.0
    assert result.execution_mode == ExecutionMode.PROTOCOL_STRUCTURED
    assert result.output["category"] == "income"
    assert result.output["amount"] == 5000


def test_ledger_snapshot(tmp_path):
    store = LedgerStore(base_path=tmp_path)
    ledger = InstitutionalLedger(store=store)

    # Record some entries
    for data in [
        {"mode": "record", "category": "income", "amount": 5000, "direction": "inflow", "recurring": True, "frequency": "monthly"},
        {"mode": "record", "category": "expense", "amount": 2000, "direction": "outflow", "recurring": True, "frequency": "monthly"},
        {"mode": "record", "category": "asset", "amount": 10000, "direction": "neutral"},
    ]:
        ctx = InstitutionalContext(data=data)
        ledger.invoke(ctx, Frame(FrameType.FINANCIAL), PrincipalPosition())

    # Get snapshot
    ctx = InstitutionalContext(data={"mode": "snapshot"})
    result = ledger.invoke(ctx, Frame(FrameType.FINANCIAL), PrincipalPosition())
    snap = result.output

    assert snap["monthly_inflow"] == 5000
    assert snap["monthly_outflow"] == 2000
    assert snap["total_assets"] > 0


def test_ledger_empty_snapshot(tmp_path):
    store = LedgerStore(base_path=tmp_path)
    ledger = InstitutionalLedger(store=store)

    ctx = InstitutionalContext(data={"mode": "snapshot"})
    result = ledger.invoke(ctx, Frame(FrameType.FINANCIAL), PrincipalPosition())

    assert result.output["net_position"] == 0.0
    assert result.output["runway_months"] == float("inf")


def test_ledger_negative_runway_alert(tmp_path):
    store = LedgerStore(base_path=tmp_path)
    ledger = InstitutionalLedger(store=store)

    # More outflow than inflow with small assets
    for data in [
        {"mode": "record", "category": "income", "amount": 1000, "direction": "inflow", "recurring": True, "frequency": "monthly"},
        {"mode": "record", "category": "expense", "amount": 3000, "direction": "outflow", "recurring": True, "frequency": "monthly"},
        {"mode": "record", "category": "asset", "amount": 4000, "direction": "neutral"},
    ]:
        ctx = InstitutionalContext(data=data)
        ledger.invoke(ctx, Frame(FrameType.FINANCIAL), PrincipalPosition())

    ctx = InstitutionalContext(data={"mode": "snapshot"})
    result = ledger.invoke(ctx, Frame(FrameType.FINANCIAL), PrincipalPosition())

    assert result.escalation_flag is True
    assert any("RUNWAY" in a or "OUTFLOW" in a for a in result.output["alerts"])
