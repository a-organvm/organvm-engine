"""Engine-specific event type constants — aliases into the unified EventType enum.

All event types are canonically defined in ``organvm_engine.events.spine.EventType``.
This module re-exports the subset used by engine domain modules as module-level
constants so that existing ``from organvm_engine.pulse.types import X`` imports
continue to work without modification.

The string values are identical to ``EventType.<member>.value``, so code that
compares against these constants (``if event_type == REGISTRY_UPDATED``) is
fully backward-compatible.
"""

from organvm_engine.events.spine import EventType

# -- Governance ---------------------------------------------------------------
PROMOTION_CHANGED: str = EventType.PROMOTION_CHANGED
GATE_EVALUATED: str = EventType.GATE_EVALUATED
DEPENDENCY_VIOLATION: str = EventType.DEPENDENCY_VIOLATION
AUDIT_COMPLETED: str = EventType.AUDIT_COMPLETED

# -- Registry -----------------------------------------------------------------
REGISTRY_UPDATED: str = EventType.REGISTRY_UPDATED
REGISTRY_LOADED: str = EventType.REGISTRY_LOADED

# -- Coordination -------------------------------------------------------------
AGENT_PUNCHED_IN: str = EventType.AGENT_PUNCHED_IN
AGENT_PUNCHED_OUT: str = EventType.AGENT_PUNCHED_OUT
CAPACITY_WARNING: str = EventType.CAPACITY_WARNING

# -- Metrics / Organism -------------------------------------------------------
ORGANISM_COMPUTED: str = EventType.ORGANISM_COMPUTED
STALENESS_DETECTED: str = EventType.STALENESS_DETECTED

# -- Seeds --------------------------------------------------------------------
SEED_EDGE_ADDED: str = EventType.SEED_EDGE_ADDED
SEED_EDGE_REMOVED: str = EventType.SEED_EDGE_REMOVED
SEED_UNRESOLVED: str = EventType.SEED_UNRESOLVED

# -- Context ------------------------------------------------------------------
CONTEXT_SYNCED: str = EventType.CONTEXT_SYNCED
CONTEXT_AMMOI_DISTRIBUTED: str = EventType.CONTEXT_AMMOI_DISTRIBUTED

# -- Sensors ------------------------------------------------------------------
SENSOR_SCAN_COMPLETED: str = EventType.SENSOR_SCAN_COMPLETED
SENSOR_CHANGE_DETECTED: str = EventType.SENSOR_CHANGE_DETECTED

# -- Pulse / AMMOI ------------------------------------------------------------
PULSE_HEARTBEAT: str = EventType.PULSE_HEARTBEAT
AMMOI_COMPUTED: str = EventType.AMMOI_COMPUTED

# -- Inference / Advisories ---------------------------------------------------
INFERENCE_COMPLETED: str = EventType.INFERENCE_COMPLETED
ADVISORY_GENERATED: str = EventType.ADVISORY_GENERATED

# -- Heartbeat ----------------------------------------------------------------
HEARTBEAT_DIFF: str = EventType.HEARTBEAT_DIFF

# -- Edge sync ----------------------------------------------------------------
EDGES_SYNCED: str = EventType.EDGES_SYNCED

# -- Variable bridge ----------------------------------------------------------
VARIABLES_SYNCED: str = EventType.VARIABLES_SYNCED

# -- Self-referential (testament chain) ---------------------------------------
ARCHITECTURE_CHANGED: str = EventType.ARCHITECTURE_CHANGED
SCORECARD_EXPANDED: str = EventType.SCORECARD_EXPANDED
VOCABULARY_EXPANDED: str = EventType.VOCABULARY_EXPANDED
MODULE_ADDED: str = EventType.MODULE_ADDED
SESSION_RECORDED: str = EventType.SESSION_RECORDED

ALL_ENGINE_EVENT_TYPES: list[str] = [
    PROMOTION_CHANGED,
    GATE_EVALUATED,
    DEPENDENCY_VIOLATION,
    AUDIT_COMPLETED,
    REGISTRY_UPDATED,
    REGISTRY_LOADED,
    AGENT_PUNCHED_IN,
    AGENT_PUNCHED_OUT,
    CAPACITY_WARNING,
    ORGANISM_COMPUTED,
    STALENESS_DETECTED,
    SEED_EDGE_ADDED,
    SEED_EDGE_REMOVED,
    SEED_UNRESOLVED,
    CONTEXT_SYNCED,
    CONTEXT_AMMOI_DISTRIBUTED,
    SENSOR_SCAN_COMPLETED,
    SENSOR_CHANGE_DETECTED,
    PULSE_HEARTBEAT,
    AMMOI_COMPUTED,
    INFERENCE_COMPLETED,
    ADVISORY_GENERATED,
    HEARTBEAT_DIFF,
    EDGES_SYNCED,
    VARIABLES_SYNCED,
    ARCHITECTURE_CHANGED,
    SCORECARD_EXPANDED,
    VOCABULARY_EXPANDED,
    MODULE_ADDED,
    SESSION_RECORDED,
]
