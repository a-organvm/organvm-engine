"""Pulse rhythm — orchestrate a complete proprioceptive cycle.

One pulse cycle:
  1. Run all sensors → emit change events
  2. Compute AMMOI from current state
  3. Store AMMOI snapshot to history
  4. Emit PULSE_HEARTBEAT event
  5. Return AMMOI
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from organvm_engine.pulse.ammoi import AMMOI, _append_history, compute_ammoi


def pulse_once(
    workspace: Path | None = None,
    registry: dict | None = None,
    run_sensors: bool = True,
) -> AMMOI:
    """Execute one full pulse cycle.

    Args:
        workspace: Workspace root. Defaults to ~/Workspace.
        registry: Pre-loaded registry. Loaded from default if None.
        run_sensors: Whether to run ontologia sensors before computing.

    Returns:
        The computed AMMOI snapshot.
    """
    ws = workspace or Path.home() / "Workspace"

    # 1. Run sensors (best-effort)
    sensor_count = 0
    if run_sensors:
        try:
            from ontologia.sensing.scanner import scan_and_emit

            sensor_count = scan_and_emit(ws)
        except ImportError:
            pass
        except Exception:
            pass

    # 2. Compute AMMOI
    ammoi = compute_ammoi(registry=registry, workspace=ws)

    # 3. Store to history
    _append_history(ammoi)

    # 4. Emit heartbeat event
    try:
        from organvm_engine.pulse.emitter import emit_engine_event
        from organvm_engine.pulse.types import AMMOI_COMPUTED, PULSE_HEARTBEAT

        emit_engine_event(
            event_type=AMMOI_COMPUTED,
            source="pulse",
            payload={
                "system_density": ammoi.system_density,
                "total_entities": ammoi.total_entities,
                "active_edges": ammoi.active_edges,
                "pulse_count": ammoi.pulse_count + 1,
            },
        )
        emit_engine_event(
            event_type=PULSE_HEARTBEAT,
            source="pulse",
            payload={
                "sensor_events": sensor_count,
                "density": ammoi.system_density,
            },
        )
    except Exception:
        pass

    return ammoi


def pulse_history(days: int = 30, limit: int = 200) -> list[dict[str, Any]]:
    """Read AMMOI history for temporal analysis.

    Args:
        days: Only return snapshots from the last N days.
        limit: Maximum snapshots to return.

    Returns:
        List of AMMOI snapshot dicts, most recent last.
    """
    from datetime import datetime, timedelta, timezone

    from organvm_engine.pulse.ammoi import _read_history

    snapshots = _read_history(limit=limit)
    if days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        snapshots = [s for s in snapshots if s.timestamp >= cutoff_str]

    return [s.to_dict() for s in snapshots]
