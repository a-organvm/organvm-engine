"""Taxis Dispatch Receiver — secure, idempotent orchestration entry point.

Governed by: SOP--formal-methods-applied-protocols.md
Strata:
- Stratum I (Hoare Logic): Contract verification via contracts.py
- Stratum I (Linear Logic): Idempotency via idempotency.py
"""

from __future__ import annotations

import logging
from typing import Any

from organvm_engine.verification.contracts import verify_contract
from organvm_engine.verification.idempotency import DispatchLedger

logger = logging.getLogger(__name__)

class FormalVerificationError(Exception):
    """Raised when a Hoare Logic contract pre-condition fails."""
    pass

class IdempotencyError(Exception):
    """Raised when an attempt is made to re-process a consumed event."""
    pass

class WebhookReceiver:
    """Industrial-grade event receiver for the Taxis orchestration engine."""

    def __init__(self, ledger: DispatchLedger | None = None):
        self.ledger = ledger or DispatchLedger()

    def receive(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Process an incoming dispatch envelope with formal proofs.

        Invariant: {P} C {Q}
        P: Contract validation matches schema.
        C: Logic execution.
        Q: Dispatch marked as consumed in ledger.
        """
        dispatch_id = envelope.get("dispatch_id")
        event_type = envelope.get("event")
        source = envelope.get("source")
        target = envelope.get("target")
        payload = envelope.get("payload", {})

        if not all([dispatch_id, event_type, source, target]):
            raise FormalVerificationError("Malformed envelope: missing mandatory routing fields.")

        # 1. Stratum I: Pre-condition {P}
        contract_result = verify_contract(event_type, payload)
        if not contract_result.passed:
            # Manually record as rejected if it's not already in there
            if not self.ledger.is_known(dispatch_id):
                import time

                from organvm_engine.verification.idempotency import LedgerEntry
                entry = LedgerEntry(
                    dispatch_id=dispatch_id,
                    event=event_type,
                    source=source,
                    target=target,
                    timestamp=time.time(),
                    status="rejected",
                )
                self.ledger._ensure_loaded()[dispatch_id] = entry
                self.ledger._append(entry)
            else:
                self.ledger.reject(dispatch_id)

            raise FormalVerificationError(
                f"Contract pre-condition failed for {event_type}: {', '.join(contract_result.errors)}",
            )

        # 2. Stratum I: Linear Logic (Resource Consumption / Idempotency)
        # Attempt to record the dispatch. If it returns False, it's a duplicate.
        recorded = self.ledger.record(
            dispatch_id=dispatch_id,
            event=event_type,
            source=source,
            target=target,
        )

        if not recorded:
            status = self.ledger.get_status(dispatch_id)
            if status == "consumed":
                logger.info(f"Ignoring duplicate dispatch {dispatch_id} (already consumed).")
                return {"status": "ignored", "reason": "duplicate", "dispatch_id": dispatch_id}
            logger.warning(f"Re-processing pending/rejected dispatch {dispatch_id}.")

        # 3. Stratum II: Command {C} (Simulation of orchestration routing)
        # In a real scenario, this would trigger sub-agents or specific organ webhooks.
        logger.info(f"Orchestrating {event_type} from {source} to {target} [{dispatch_id}]")

        # 4. Stratum I: Post-condition {Q}
        consumed = self.ledger.consume(dispatch_id)
        if not consumed:
            raise IdempotencyError(f"Failed to finalize consumption for {dispatch_id}.")

        return {
            "status": "success",
            "dispatch_id": dispatch_id,
            "event": event_type,
            "verification": "formal_contract_pass",
        }

def handle_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Helper entry point for webhooks."""
    receiver = WebhookReceiver()
    return receiver.receive(payload)
