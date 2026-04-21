"""PRIM-INST-002 — The Guardian.

Maintains a persistent watchlist of interests, rights, and deadlines.
Evaluates the watchlist against current environmental state and triggers
alerts when thresholds are crossed.  The guardian is the system's
perimeter sensor — it does not assess or recommend, only detects and
alerts.

Storage: append-only JSONL watchlist at ~/.organvm/institutional/guardian/
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
    Frame,
    InstitutionalContext,
    PrimitiveOutput,
    PrincipalPosition,
    StakesLevel,
)

_DEFAULT_BASE = Path.home() / ".organvm" / "institutional" / "guardian"


# ---------------------------------------------------------------------------
# Guardian-specific types
# ---------------------------------------------------------------------------


@dataclass
class WatchItem:
    item_id: str = field(
        default_factory=lambda: f"WATCH-{uuid.uuid4().hex[:8]}",
    )
    category: str = ""  # deadline, threshold, registration, benefit
    description: str = ""
    watched_value: str = ""
    threshold: str = ""  # string to support dates and numbers
    direction: str = "approaching"  # above, below, approaching, expired
    current_value: Any = None
    last_checked: str = ""
    alert_window_days: int = 7
    status: str = "active"  # active, triggered, resolved, expired


@dataclass
class Alert:
    alert_id: str = field(
        default_factory=lambda: f"ALERT-{uuid.uuid4().hex[:8]}",
    )
    watch_item_id: str = ""
    alert_type: str = ""  # threshold_crossed, deadline_approaching, expiry_imminent
    severity: str = "warning"  # info, warning, critical
    message: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    context_payload: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Persistent state
# ---------------------------------------------------------------------------


class GuardianState:
    """Manages the persistent watchlist."""

    def __init__(self, base_path: Path | None = None) -> None:
        self._base = base_path or _DEFAULT_BASE
        self._watchlist_path = self._base / "watchlist.jsonl"

    def _ensure_dirs(self) -> None:
        self._base.mkdir(parents=True, exist_ok=True)

    def add_watch(self, item: WatchItem) -> None:
        self._ensure_dirs()
        with self._watchlist_path.open("a") as f:
            f.write(json.dumps(asdict(item)) + "\n")

    def remove_watch(self, item_id: str) -> bool:
        """Remove by rewriting without the target.  Returns True if found."""
        items = self.get_watchlist()
        filtered = [i for i in items if i.item_id != item_id]
        if len(filtered) == len(items):
            return False
        self._ensure_dirs()
        with self._watchlist_path.open("w") as f:
            for item in filtered:
                f.write(json.dumps(asdict(item)) + "\n")
        return True

    def get_watchlist(self) -> list[WatchItem]:
        if not self._watchlist_path.exists():
            return []
        items: list[WatchItem] = []
        with self._watchlist_path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(WatchItem(**json.loads(line)))
        return items

    def check_all(
        self,
        current_state: dict[str, Any],
    ) -> list[Alert]:
        """Evaluate every active watch item against current state."""
        now = datetime.now(timezone.utc)
        alerts: list[Alert] = []

        for item in self.get_watchlist():
            if item.status != "active":
                continue
            alert = self._evaluate_item(item, current_state, now)
            if alert:
                alerts.append(alert)

        return alerts

    def _evaluate_item(
        self,
        item: WatchItem,
        current_state: dict[str, Any],
        now: datetime,
    ) -> Alert | None:
        # Deadline-type watches
        if item.category == "deadline" or item.direction in (
            "approaching", "expired",
        ):
            return self._check_deadline(item, now)

        # Threshold-type watches
        if item.direction in ("above", "below"):
            return self._check_threshold(item, current_state)

        return None

    def _check_deadline(
        self,
        item: WatchItem,
        now: datetime,
    ) -> Alert | None:
        try:
            deadline = datetime.fromisoformat(item.threshold)
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None

        days_remaining = (deadline - now).days

        if days_remaining < 0:
            return Alert(
                watch_item_id=item.item_id,
                alert_type="expired",
                severity="critical",
                message=f"EXPIRED: {item.description} "
                        f"(deadline was {item.threshold}, "
                        f"{abs(days_remaining)} days ago)",
                context_payload={
                    "item": asdict(item),
                    "days_remaining": days_remaining,
                },
            )

        if days_remaining <= item.alert_window_days:
            severity = "critical" if days_remaining <= 2 else "warning"
            return Alert(
                watch_item_id=item.item_id,
                alert_type="deadline_approaching",
                severity=severity,
                message=f"APPROACHING: {item.description} "
                        f"in {days_remaining} days ({item.threshold})",
                context_payload={
                    "item": asdict(item),
                    "days_remaining": days_remaining,
                },
            )

        return None

    @staticmethod
    def _check_threshold(
        item: WatchItem,
        current_state: dict[str, Any],
    ) -> Alert | None:
        current = current_state.get(item.watched_value)
        if current is None:
            return None

        try:
            threshold_val = float(item.threshold)
            current_val = float(current)
        except (ValueError, TypeError):
            return None

        crossed = False
        if item.direction == "above" and current_val > threshold_val or item.direction == "below" and current_val < threshold_val:
            crossed = True

        if crossed:
            return Alert(
                watch_item_id=item.item_id,
                alert_type="threshold_crossed",
                severity="warning",
                message=f"THRESHOLD: {item.description} — "
                        f"{item.watched_value}={current_val} "
                        f"crossed {item.direction} {threshold_val}",
                context_payload={
                    "item": asdict(item),
                    "current_value": current_val,
                    "threshold": threshold_val,
                },
            )

        return None


# ---------------------------------------------------------------------------
# The Guardian primitive
# ---------------------------------------------------------------------------


class Guardian(InstitutionalPrimitive):
    """PRIM-INST-002 — watchlist maintenance and threshold alerting."""

    PRIMITIVE_ID = "PRIM-INST-002"
    PRIMITIVE_NAME = "guardian"
    CLUSTER = "protective"
    DEFAULT_STAKES = StakesLevel.ROUTINE

    def __init__(self, state: GuardianState | None = None) -> None:
        self._state = state or GuardianState()

    @property
    def state(self) -> GuardianState:
        return self._state

    def invoke(
        self,
        context: InstitutionalContext,
        frame: Frame,
        principal_position: PrincipalPosition,
    ) -> PrimitiveOutput:
        """Run a full guardian check cycle against context.data."""
        current_state = context.data.get("current_state", context.data)
        alerts = self._state.check_all(current_state)

        # Determine confidence and stakes from results
        if alerts:
            has_critical = any(a.severity == "critical" for a in alerts)
            confidence = 0.9  # threshold checks are deterministic
            stakes = (
                StakesLevel.CRITICAL if has_critical
                else StakesLevel.SIGNIFICANT
            )
        else:
            confidence = 0.95
            stakes = StakesLevel.ROUTINE

        exe_mode = self.determine_execution_mode(confidence, stakes)

        audit = self._make_audit_entry(
            operation="check",
            rationale="Periodic watchlist evaluation",
            inputs_summary=f"watchlist_size={len(self._state.get_watchlist())}",
            output_summary=f"{len(alerts)} alerts triggered",
            execution_mode=exe_mode,
            confidence=confidence,
        )

        return PrimitiveOutput(
            output=[asdict(a) for a in alerts],
            confidence=confidence,
            escalation_flag=False,  # guardian never escalates (sensing layer)
            audit_trail=[audit],
            execution_mode=exe_mode,
            stakes=stakes,
            context_id=context.context_id,
            primitive_id=self.PRIMITIVE_ID,
        )
