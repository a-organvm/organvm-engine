"""Heartbeat engine — system-wide gestalt health assessment.

Implements: INST-HEARTBEAT, BEAT-001 through BEAT-004

Computes a single GestaltState (THRIVING, COHERENT, STRAINED, BRITTLE)
from gate evaluation results. The gestalt is the minimum across all
evaluated dimensions — a chain-is-as-strong-as-its-weakest-link model.

BEAT-001  THRIVING  — all dimensions above 0.75
BEAT-002  COHERENT  — all dimensions above 0.50
BEAT-003  STRAINED  — all dimensions above 0.25
BEAT-004  BRITTLE   — any dimension below 0.25
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Gestalt states
# ---------------------------------------------------------------------------


class GestaltState(str, enum.Enum):
    """System-wide health gestalt."""

    THRIVING = "THRIVING"
    COHERENT = "COHERENT"
    STRAINED = "STRAINED"
    BRITTLE = "BRITTLE"


# Thresholds: minimum score for each state
_GESTALT_THRESHOLDS: list[tuple[float, GestaltState]] = [
    (0.75, GestaltState.THRIVING),
    (0.50, GestaltState.COHERENT),
    (0.25, GestaltState.STRAINED),
    (0.00, GestaltState.BRITTLE),
]


# ---------------------------------------------------------------------------
# Heartbeat report
# ---------------------------------------------------------------------------


@dataclass
class HeartbeatReport:
    """Snapshot of system health at a point in time.

    Fields:
        timestamp: ISO-8601 UTC timestamp of measurement.
        gestalt: The overall GestaltState.
        dimension_scores: Per-dimension scores (0.0 to 1.0).
        min_dimension: The dimension with the lowest score.
        min_score: The lowest score across all dimensions.
    """

    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    gestalt: GestaltState = GestaltState.BRITTLE
    dimension_scores: dict[str, float] = field(default_factory=dict)
    min_dimension: str = ""
    min_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "gestalt": self.gestalt.value,
            "dimension_scores": {
                k: round(v, 4) for k, v in self.dimension_scores.items()
            },
            "min_dimension": self.min_dimension,
            "min_score": round(self.min_score, 4),
        }

    def summary(self) -> str:
        lines = [
            "Heartbeat Report",
            "=" * 40,
            f"  Gestalt: {self.gestalt.value}",
            f"  Weakest: {self.min_dimension} ({self.min_score:.2%})",
        ]
        for dim, score in sorted(self.dimension_scores.items()):
            lines.append(f"  {dim}: {score:.2%}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------


def compute_gestalt(dimension_scores: dict[str, float]) -> GestaltState:
    """Compute GestaltState from per-dimension scores.

    The gestalt is determined by the minimum score across all dimensions.
    If no dimensions are provided, returns BRITTLE.

    Args:
        dimension_scores: Dict of dimension_name -> score (0.0 to 1.0).

    Returns:
        GestaltState based on the weakest dimension.
    """
    if not dimension_scores:
        return GestaltState.BRITTLE

    min_score = min(dimension_scores.values())

    for threshold, state in _GESTALT_THRESHOLDS:
        if min_score >= threshold:
            return state

    return GestaltState.BRITTLE


def compute_heartbeat(
    dimension_scores: dict[str, float],
) -> HeartbeatReport:
    """Compute a full heartbeat report from dimension scores.

    Args:
        dimension_scores: Dict of dimension_name -> score (0.0 to 1.0).

    Returns:
        HeartbeatReport with gestalt, scores, and weakest dimension.
    """
    gestalt = compute_gestalt(dimension_scores)

    min_dim = ""
    min_score = 1.0
    if dimension_scores:
        min_dim = min(dimension_scores, key=dimension_scores.get)  # type: ignore[arg-type]
        min_score = dimension_scores[min_dim]

    return HeartbeatReport(
        gestalt=gestalt,
        dimension_scores=dict(dimension_scores),
        min_dimension=min_dim,
        min_score=min_score,
    )


def heartbeat_from_gate_results(
    gate_results: dict[str, Any],
) -> HeartbeatReport:
    """Build a heartbeat from gate evaluation output.

    Expects gate_results to be a dict where each key is a gate name
    and each value has a "score" field (float 0.0-1.0) or a "passed"
    bool field (converted to 1.0/0.0).

    Args:
        gate_results: Dict of gate_name -> {score: float} or {passed: bool}.

    Returns:
        HeartbeatReport.
    """
    scores: dict[str, float] = {}
    for gate_name, result in gate_results.items():
        if isinstance(result, dict):
            if "score" in result:
                scores[gate_name] = float(result["score"])
            elif "passed" in result:
                scores[gate_name] = 1.0 if result["passed"] else 0.0
        elif isinstance(result, (int, float)):
            scores[gate_name] = float(result)
        elif isinstance(result, bool):
            scores[gate_name] = 1.0 if result else 0.0

    return compute_heartbeat(scores)
