"""Engine-specific event type constants for the unified event bus.

These extend ontologia's event types with engine-domain events.
All engine modules emit through these constants via the emitter.
"""

# Governance
PROMOTION_CHANGED = "governance.promotion_changed"
GATE_EVALUATED = "governance.gate_evaluated"
DEPENDENCY_VIOLATION = "governance.dependency_violation"
AUDIT_COMPLETED = "governance.audit_completed"

# Registry
REGISTRY_UPDATED = "registry.updated"
REGISTRY_LOADED = "registry.loaded"

# Coordination
AGENT_PUNCHED_IN = "coordination.punch_in"
AGENT_PUNCHED_OUT = "coordination.punch_out"
CAPACITY_WARNING = "coordination.capacity_warning"

# Metrics / Organism
ORGANISM_COMPUTED = "metrics.organism_computed"
STALENESS_DETECTED = "metrics.staleness_detected"

# Seeds
SEED_EDGE_ADDED = "seed.edge_added"
SEED_EDGE_REMOVED = "seed.edge_removed"
SEED_UNRESOLVED = "seed.unresolved_consumer"

# Context
CONTEXT_SYNCED = "context.synced"
CONTEXT_AMMOI_DISTRIBUTED = "context.ammoi_distributed"

# Sensors
SENSOR_SCAN_COMPLETED = "sensor.scan_completed"
SENSOR_CHANGE_DETECTED = "sensor.change_detected"

# Pulse / AMMOI
PULSE_HEARTBEAT = "pulse.heartbeat"
AMMOI_COMPUTED = "pulse.ammoi_computed"

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
]
