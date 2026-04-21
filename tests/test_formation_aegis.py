"""Tests for the AEGIS formation end-to-end."""

from datetime import datetime, timedelta, timezone

from organvm_engine.formations.aegis import (
    AEGIS_SPEC,
    build_aegis_graph,
    build_default_engine,
)
from organvm_engine.primitives.guardian import GuardianState, WatchItem
from organvm_engine.primitives.types import (
    InstitutionalContext,
    PrincipalPosition,
)


def test_aegis_graph_structure():
    graph = build_aegis_graph()
    assert graph.name == "aegis"
    assert graph.formation_id == "FORM-INST-001"
    assert len(graph.nodes) == 5
    assert len(graph.edges) == 5

    # Verify topological order
    stages = graph.execution_order()
    assert len(stages) >= 3  # guardian, [assessor||assessor], counselor, mandator


def test_aegis_spec():
    assert AEGIS_SPEC.formation_id == "FORM-INST-001"
    assert AEGIS_SPEC.formation_type == "SYNTHESIZER"
    assert "mandator" in AEGIS_SPEC.escalation_policy
    assert "ALWAYS" in AEGIS_SPEC.escalation_policy["mandator"]


def test_aegis_end_to_end(tmp_path):
    """Full AEGIS formation invocation."""
    guardian_state = GuardianState(base_path=tmp_path / "guardian")
    deadline = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    guardian_state.add_watch(WatchItem(
        category="deadline",
        description="Lease renewal deadline",
        threshold=deadline,
        direction="approaching",
        alert_window_days=7,
    ))

    engine = build_default_engine(guardian_state=guardian_state)

    context = InstitutionalContext(
        situation="Lease renewal deadline approaching",
        data={
            "deadline": deadline,
            "category": "housing",
        },
    )
    position = PrincipalPosition(
        interests=["Housing stability"],
        objectives=["Renew lease on favorable terms"],
    )

    result = engine.execute_formation("aegis", context, position)

    # AEGIS should produce a result (may halt due to escalation)
    assert result.output is not None
    assert len(result.audit_trail) > 0

    # The mandator should escalate (if we get that far)
    # or an earlier stage may escalate on high-severity risks
    # Either way, we expect the formation to process through stages


def test_aegis_builds_without_error():
    """Verify the default engine builds without import or wiring errors."""
    engine = build_default_engine()
    formations = engine.list_formations()
    assert "aegis" in formations
