"""Pulse module — the system's nervous system and self-awareness layer.

Twelve sub-layers:
    events      File-based event bus (append-only JSONL)
    types       Engine-specific event type constants
    emitter     Unified bridge to ontologia's event bus
    heartbeat   Organism diffing (what changed between snapshots)
    temporal    Time awareness (velocity, acceleration, trend detection)
    affective   System mood (qualitative health summary)
    density     Interconnectedness measurement (edge saturation, coverage)
    ammoi       Adaptive Macro-Micro Ontological Index (multi-scale density)
    rhythm      Pulse cycle orchestration (scan → compute → store → emit)
    nerve       Subscription wiring (seed-declared event subscriptions)
    continuity  Session briefing (what happened recently)
    shared_memory  Cross-agent knowledge store
    flow        Dependency flow visualization (active/warm/dormant edges)
"""

from organvm_engine.pulse.affective import (
    MoodFactors,
    MoodReading,
    SystemMood,
    compute_mood,
)
from organvm_engine.pulse.continuity import (
    SessionBriefing,
    briefing_to_markdown,
    build_briefing,
)
from organvm_engine.pulse.density import (
    DensityProfile,
    compute_density,
)
from organvm_engine.pulse.emitter import emit_engine_event
from organvm_engine.pulse.types import ALL_ENGINE_EVENT_TYPES
from organvm_engine.pulse.ecosystem_bridge import (
    ORGAN_ARCHETYPES,
    EcosystemCoverage,
    RepoEcosystemContext,
    compute_ecosystem_coverage,
    infer_repo_context,
)
from organvm_engine.pulse.events import (
    ALL_EVENT_TYPES,
    DENSITY_COMPUTED,
    GATE_CHANGED,
    MOOD_SHIFTED,
    ORGANISM_COMPUTED,
    PULSE_HEARTBEAT,
    REGISTRY_UPDATED,
    REPO_PROMOTED,
    SEED_CHANGED,
    SESSION_ENDED,
    SESSION_STARTED,
    Event,
    emit,
    event_counts,
    recent,
    replay,
)
from organvm_engine.pulse.flow import (
    EdgeActivity,
    FlowProfile,
    compute_flow,
    flow_to_dict,
)
from organvm_engine.pulse.heartbeat import (
    GateDelta,
    PulseSnapshot,
    RepoDelta,
    compute_pulse,
)
from organvm_engine.pulse.nerve import (
    NerveBundle,
    Subscription,
    propagate,
    resolve_subscriptions,
)
from organvm_engine.pulse.shared_memory import (
    Insight,
    insight_summary,
    query_insights,
    recent_insights,
    record_insight,
)
from organvm_engine.pulse.temporal import (
    TemporalMetric,
    TemporalProfile,
    TrendDirection,
    build_temporal_metric,
    compute_temporal_profile,
    compute_velocity,
)

__all__ = [
    # events
    "ALL_EVENT_TYPES",
    "DENSITY_COMPUTED",
    "Event",
    "GATE_CHANGED",
    "MOOD_SHIFTED",
    "ORGANISM_COMPUTED",
    "PULSE_HEARTBEAT",
    "REGISTRY_UPDATED",
    "REPO_PROMOTED",
    "SEED_CHANGED",
    "SESSION_ENDED",
    "SESSION_STARTED",
    "emit",
    "event_counts",
    "recent",
    "replay",
    # heartbeat
    "GateDelta",
    "PulseSnapshot",
    "RepoDelta",
    "compute_pulse",
    # temporal
    "TemporalMetric",
    "TemporalProfile",
    "TrendDirection",
    "build_temporal_metric",
    "compute_temporal_profile",
    "compute_velocity",
    # affective
    "MoodFactors",
    "MoodReading",
    "SystemMood",
    "compute_mood",
    # density
    "DensityProfile",
    "compute_density",
    # nerve
    "NerveBundle",
    "Subscription",
    "propagate",
    "resolve_subscriptions",
    # continuity
    "SessionBriefing",
    "briefing_to_markdown",
    "build_briefing",
    # flow
    "EdgeActivity",
    "FlowProfile",
    "compute_flow",
    "flow_to_dict",
    # shared_memory
    "Insight",
    "insight_summary",
    "query_insights",
    "recent_insights",
    "record_insight",
    # emitter
    "ALL_ENGINE_EVENT_TYPES",
    "emit_engine_event",
    # ecosystem_bridge
    "EcosystemCoverage",
    "ORGAN_ARCHETYPES",
    "RepoEcosystemContext",
    "compute_ecosystem_coverage",
    "infer_repo_context",
]
