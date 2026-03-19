"""Event spine — append-only JSONL event bus for constitutional observability.

Implements: INST-EVENT-SPINE, EVT-001 through EVT-005
Invariants enforced: INV-000-005 (Observability)

Every system-significant action (promotion, dependency change, entity lifecycle,
governance audit, metric update) emits an EventRecord to the spine. The spine
is the single, canonical, append-only event log for the ORGANVM system.

The pulse/events.py module is the engine's internal event emitter. This module
sits one layer above it: it provides the constitutional event types defined by
the SPEC ladder and a typed query interface suitable for cross-system consumers.
"""

from organvm_engine.events.spine import (
    EventRecord,
    EventSpine,
    EventType,
)

__all__ = [
    "EventRecord",
    "EventSpine",
    "EventType",
]
