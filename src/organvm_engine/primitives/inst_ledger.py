"""PRIM-INST-006 — The Institutional Ledger.

Records the authoritative state of all value flows — income, expenses,
obligations, receivables, assets, equity.  This is NOT the Testament
Protocol hash chain (organvm_engine.ledger); this is the economic ground
truth for the principal.

Named ``inst_ledger`` to avoid import collision with the existing
``organvm_engine.ledger`` package.

Storage: append-only JSONL entries + computed snapshot JSON.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from organvm_engine.primitives.base import InstitutionalPrimitive
from organvm_engine.primitives.types import (
    ExecutionMode,
    Frame,
    InstitutionalContext,
    PrimitiveOutput,
    PrincipalPosition,
    StakesLevel,
)

_DEFAULT_BASE = Path.home() / ".organvm" / "institutional" / "ledger"


# ---------------------------------------------------------------------------
# Ledger-specific types
# ---------------------------------------------------------------------------


@dataclass
class LedgerEntry:
    entry_id: str = field(
        default_factory=lambda: f"LED-{uuid.uuid4().hex[:12]}",
    )
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    category: str = ""  # income, expense, obligation, receivable, equity, asset
    subcategory: str = ""
    amount: float | None = None
    currency: str = "USD"
    counterparty: str = ""
    description: str = ""
    direction: str = ""  # inflow, outflow, neutral
    recurring: bool = False
    frequency: str = ""  # monthly, weekly, one-time
    status: str = "active"  # active, pending, completed, disputed
    tags: list[str] = field(default_factory=list)


@dataclass
class EconomicSnapshot:
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    net_position: float = 0.0
    monthly_inflow: float = 0.0
    monthly_outflow: float = 0.0
    runway_months: float = 0.0
    entries_by_category: dict[str, int] = field(default_factory=dict)
    alerts: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


class LedgerStore:
    """Append-only JSONL entries + computed snapshot."""

    def __init__(self, base_path: Path | None = None) -> None:
        self._base = base_path or _DEFAULT_BASE
        self._entries_path = self._base / "economic-entries.jsonl"
        self._snapshot_path = self._base / "snapshot.json"

    def _ensure_dirs(self) -> None:
        self._base.mkdir(parents=True, exist_ok=True)

    def record(self, entry: LedgerEntry) -> None:
        """Append an entry to the ledger."""
        self._ensure_dirs()
        with self._entries_path.open("a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

    def load_entries(self) -> list[LedgerEntry]:
        if not self._entries_path.exists():
            return []
        entries: list[LedgerEntry] = []
        with self._entries_path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(LedgerEntry(**json.loads(line)))
        return entries

    def compute_snapshot(self) -> EconomicSnapshot:
        """Build current economic snapshot from all entries."""
        entries = self.load_entries()
        snap = EconomicSnapshot()

        category_counts: dict[str, int] = {}
        for entry in entries:
            cat = entry.category or "uncategorized"
            category_counts[cat] = category_counts.get(cat, 0) + 1

            amt = entry.amount or 0.0

            if cat == "asset":
                snap.total_assets += amt
            elif cat in ("obligation", "expense"):
                snap.total_liabilities += amt
            elif cat == "equity":
                snap.total_assets += amt

            # Cash flow: recurring entries contribute to monthly
            if entry.recurring and entry.status == "active":
                monthly = self._to_monthly(amt, entry.frequency)
                if entry.direction == "inflow":
                    snap.monthly_inflow += monthly
                elif entry.direction == "outflow":
                    snap.monthly_outflow += monthly
            elif entry.direction == "inflow" and entry.frequency == "one-time":
                # one-time inflows don't affect monthly
                snap.total_assets += amt
            elif entry.direction == "outflow" and entry.frequency == "one-time":
                snap.total_liabilities += amt

        snap.net_position = snap.total_assets - snap.total_liabilities
        snap.entries_by_category = category_counts

        # Runway
        net_monthly = snap.monthly_inflow - snap.monthly_outflow
        if net_monthly < 0 and snap.total_assets > 0:
            snap.runway_months = snap.total_assets / abs(net_monthly)
        elif net_monthly >= 0:
            snap.runway_months = float("inf")
        else:
            snap.runway_months = 0.0

        # Alerts
        if snap.runway_months < 3 and snap.runway_months != float("inf"):
            snap.alerts.append(
                f"LOW RUNWAY: {snap.runway_months:.1f} months at current burn",
            )
        if snap.net_position < 0:
            snap.alerts.append(
                f"NEGATIVE NET POSITION: {snap.net_position:.2f}",
            )
        if snap.monthly_outflow > snap.monthly_inflow * 1.2:
            snap.alerts.append(
                "OUTFLOW EXCEEDS INFLOW by >20%",
            )

        # Persist snapshot
        self._ensure_dirs()
        with self._snapshot_path.open("w") as f:
            json.dump(asdict(snap), f, indent=2)

        return snap

    @staticmethod
    def _to_monthly(amount: float, frequency: str) -> float:
        freq_map = {
            "monthly": 1.0,
            "weekly": 4.33,
            "biweekly": 2.17,
            "quarterly": 1 / 3,
            "annually": 1 / 12,
            "yearly": 1 / 12,
            "daily": 30.0,
        }
        return amount * freq_map.get(frequency.lower(), 1.0)


# ---------------------------------------------------------------------------
# The Institutional Ledger primitive
# ---------------------------------------------------------------------------


class InstitutionalLedger(InstitutionalPrimitive):
    """PRIM-INST-006 — authoritative record of all value flows."""

    PRIMITIVE_ID = "PRIM-INST-006"
    PRIMITIVE_NAME = "ledger"
    CLUSTER = "economic"
    DEFAULT_STAKES = StakesLevel.SIGNIFICANT

    def __init__(self, store: LedgerStore | None = None) -> None:
        self._store = store or LedgerStore()

    @property
    def store(self) -> LedgerStore:
        return self._store

    def invoke(
        self,
        context: InstitutionalContext,
        frame: Frame,
        principal_position: PrincipalPosition,
    ) -> PrimitiveOutput:
        mode = context.data.get("mode", "snapshot")

        if mode == "record":
            return self._record_entry(context)
        return self._snapshot(context)

    def _record_entry(
        self,
        context: InstitutionalContext,
    ) -> PrimitiveOutput:
        entry = LedgerEntry(
            category=context.data.get("category", ""),
            subcategory=context.data.get("subcategory", ""),
            amount=context.data.get("amount"),
            currency=context.data.get("currency", "USD"),
            counterparty=context.data.get("counterparty", ""),
            description=context.data.get("description", context.situation),
            direction=context.data.get("direction", ""),
            recurring=context.data.get("recurring", False),
            frequency=context.data.get("frequency", "one-time"),
            status=context.data.get("status", "active"),
            tags=context.data.get("tags", context.tags),
        )
        self._store.record(entry)

        exe_mode = ExecutionMode.PROTOCOL_STRUCTURED
        audit = self._make_audit_entry(
            operation="record",
            rationale="Economic entry recording",
            inputs_summary=f"category={entry.category}, amount={entry.amount}",
            output_summary=f"entry_id={entry.entry_id}",
            execution_mode=exe_mode,
            confidence=1.0,
        )
        return PrimitiveOutput(
            output=asdict(entry),
            confidence=1.0,
            escalation_flag=False,
            audit_trail=[audit],
            execution_mode=exe_mode,
            stakes=StakesLevel.ROUTINE,
            context_id=context.context_id,
            primitive_id=self.PRIMITIVE_ID,
        )

    def _snapshot(
        self,
        context: InstitutionalContext,
    ) -> PrimitiveOutput:
        snap = self._store.compute_snapshot()
        has_alerts = len(snap.alerts) > 0

        confidence = 0.95  # computed from deterministic data
        stakes = (
            StakesLevel.SIGNIFICANT if has_alerts
            else StakesLevel.ROUTINE
        )
        exe_mode = self.determine_execution_mode(confidence, stakes)

        audit = self._make_audit_entry(
            operation="snapshot",
            rationale="Economic position computation",
            inputs_summary=f"entries={sum(snap.entries_by_category.values())}",
            output_summary=f"net={snap.net_position:.2f}, runway={snap.runway_months:.1f}mo",
            execution_mode=exe_mode,
            confidence=confidence,
        )
        return PrimitiveOutput(
            output=asdict(snap),
            confidence=confidence,
            escalation_flag=has_alerts,
            audit_trail=[audit],
            execution_mode=exe_mode,
            stakes=stakes,
            context_id=context.context_id,
            primitive_id=self.PRIMITIVE_ID,
        )
