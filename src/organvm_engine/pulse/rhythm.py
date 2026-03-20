"""Pulse rhythm — orchestrate a complete proprioceptive cycle.

One pulse cycle:
  1. Run all sensors → emit change events
  2. Compute AMMOI from current state
  3. Store AMMOI snapshot to history
  4. Emit PULSE_HEARTBEAT event
  5. Return AMMOI
"""

from __future__ import annotations

import json
import logging
import signal
import sys
import time
from dataclasses import asdict, dataclass
from dataclasses import field as dc_field
from pathlib import Path
from typing import Any

from organvm_engine.pulse.ammoi import AMMOI, _append_history, compute_ammoi

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HeartbeatState — lightweight state for cross-pulse diffing
# ---------------------------------------------------------------------------

def _heartbeat_path() -> Path:
    return Path.home() / ".organvm" / "pulse" / "last-heartbeat.json"


@dataclass
class HeartbeatState:
    """Minimal organism state snapshot for heartbeat diffing."""

    sys_pct: int = 0
    gate_rates: dict[str, int] = dc_field(default_factory=dict)
    repo_states: dict[str, dict] = dc_field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> HeartbeatState:
        return cls(
            sys_pct=data.get("sys_pct", 0),
            gate_rates=data.get("gate_rates", {}),
            repo_states=data.get("repo_states", {}),
        )

    @classmethod
    def from_ammoi(cls, ammoi: AMMOI) -> HeartbeatState:
        """Build a HeartbeatState from an AMMOI snapshot."""
        gate_rates: dict[str, int] = {}
        repo_states: dict[str, dict] = {}
        for oid, organ in ammoi.organs.items():
            gate_rates[oid] = organ.avg_gate_pct
            # Per-organ density acts as a proxy for repo-level tracking
            repo_states[oid] = {
                "pct": organ.avg_gate_pct,
                "density": organ.density,
                "repo_count": organ.repo_count,
            }
        return cls(
            sys_pct=int(ammoi.system_density * 100),
            gate_rates=gate_rates,
            repo_states=repo_states,
        )


def _save_heartbeat(state: HeartbeatState) -> None:
    path = _heartbeat_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), separators=(",", ":")))


def _load_heartbeat() -> HeartbeatState | None:
    path = _heartbeat_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
        return HeartbeatState.from_dict(data)
    except (json.JSONDecodeError, TypeError):
        return None


def _compute_heartbeat_diff(
    prev: HeartbeatState,
    curr: HeartbeatState,
) -> dict | None:
    """Compute differences between two heartbeat states.

    Returns None if no significant changes detected.
    """
    changes: dict = {}

    # System-level change
    pct_delta = curr.sys_pct - prev.sys_pct
    if abs(pct_delta) > 0:
        changes["sys_pct_delta"] = pct_delta

    # Gate rate changes
    gate_deltas = {}
    all_gates = set(prev.gate_rates) | set(curr.gate_rates)
    for gate in all_gates:
        old = prev.gate_rates.get(gate, 0)
        new = curr.gate_rates.get(gate, 0)
        if old != new:
            gate_deltas[gate] = new - old
    if gate_deltas:
        changes["gate_deltas"] = gate_deltas

    # New/removed organs
    prev_organs = set(prev.repo_states)
    curr_organs = set(curr.repo_states)
    if curr_organs - prev_organs:
        changes["new_organs"] = list(curr_organs - prev_organs)
    if prev_organs - curr_organs:
        changes["removed_organs"] = list(prev_organs - curr_organs)

    return changes if changes else None


def _record_pulse_insights(
    ammoi: AMMOI,
    prev_ammoi: AMMOI | None,
    heartbeat_diff: dict | None,
) -> int:
    """Record auto-generated insights from the pulse cycle.

    Records insights for:
    - Trend shifts (temporal profile shows non-stable dominant trend)
    - Tension count increases
    - Heartbeat significant changes

    Returns the number of insights recorded.
    """
    from organvm_engine.pulse.shared_memory import record_insight

    count = 0

    # Temporal trend shift
    if ammoi.temporal:
        dominant = ammoi.temporal.get("dominant_trend", "stable")
        if dominant != "stable":
            record_insight(
                agent="pulse-daemon",
                category="finding",
                content=f"System dominant trend: {dominant} "
                f"(density={ammoi.system_density:.1%}, "
                f"momentum={ammoi.temporal.get('total_momentum', 0):.3f})",
                tags=["temporal", "trend", dominant],
            )
            count += 1

    # Tension change
    if prev_ammoi and ammoi.tension_count != prev_ammoi.tension_count:
        delta = ammoi.tension_count - prev_ammoi.tension_count
        direction = "increased" if delta > 0 else "decreased"
        record_insight(
            agent="pulse-daemon",
            category="warning" if delta > 0 else "finding",
            content=f"Tension count {direction} by {abs(delta)} "
            f"({prev_ammoi.tension_count} → {ammoi.tension_count})",
            tags=["tension", direction],
        )
        count += 1

    # Heartbeat diff significant changes
    if heartbeat_diff:
        pct_delta = heartbeat_diff.get("sys_pct_delta", 0)
        if abs(pct_delta) >= 2:
            direction = "improved" if pct_delta > 0 else "regressed"
            record_insight(
                agent="pulse-daemon",
                category="finding",
                content=f"System gate pass rate {direction} by {abs(pct_delta)}pp",
                tags=["heartbeat", "gate-rate", direction],
            )
            count += 1

    return count


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

    # 1b. Sync seed edges into ontologia (best-effort)
    edge_sync_result = None
    try:
        from organvm_engine.pulse.edge_bridge import sync_seed_edges

        # Auto-bootstrap: if ontologia has entities but no edges, bootstrap first
        try:
            from ontologia.registry.store import open_store as _open_store

            _store = _open_store()
            if (
                _store.entity_count > 0
                and not _store.edge_index.all_hierarchy_edges()
                and not _store.edge_index.all_relation_edges()
            ):
                from ontologia.bootstrap import bootstrap_from_registry

                from organvm_engine.paths import registry_path as _reg_path

                rp = _reg_path()
                if rp.is_file():
                    # Re-bootstrap triggers hierarchy edge creation
                    bootstrap_from_registry(_store, rp)
        except ImportError:
            pass

        edge_sync_result = sync_seed_edges(ws)
    except ImportError:
        pass
    except Exception:
        pass

    # 1c. Sync engine variables + metrics into ontologia (best-effort)
    var_sync_result = None
    try:
        from organvm_engine.metrics.vars import build_vars as _build_vars
        from organvm_engine.pulse.variable_bridge import sync_all as _sync_vars
        from organvm_engine.registry.loader import load_registry as _load_reg

        _reg = registry or _load_reg()
        _metrics_path = Path.home() / "Workspace" / "meta-organvm" / (
            "organvm-corpvs-testamentvm/system-metrics.json"
        )
        _metrics_data: dict = {}
        if _metrics_path.is_file():
            _metrics_data = json.loads(_metrics_path.read_text())

        _engine_vars = _build_vars(_metrics_data, _reg)

        # Build organ→entity_uid map from ontologia
        _organ_map: dict[str, str] = {}
        _st = None
        try:
            from ontologia.entity.identity import EntityType as _ET
            from ontologia.registry.store import open_store as _os

            _st = _os()
            # Build reverse map: registry organ name → registry key
            _name_to_rkey: dict[str, str] = {}
            for rkey, odata in _reg.get("organs", {}).items():
                oname = odata.get("name", "")
                if oname:
                    _name_to_rkey[oname.lower()] = rkey

            for ent in _st.list_entities(entity_type=_ET.ORGAN):
                name_rec = _st.current_name(ent.uid)
                if name_rec:
                    rkey = _name_to_rkey.get(name_rec.display_name.lower())
                    if rkey:
                        _organ_map[rkey] = ent.uid
        except ImportError:
            pass

        if _st is not None:
            var_sync_result = _sync_vars(
                _st,
                _engine_vars,
                organ_entity_map=_organ_map or None,
            )
            if var_sync_result:
                _st.save()
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
        from organvm_engine.pulse.types import (
            AMMOI_COMPUTED,
            EDGES_SYNCED,
            INFERENCE_COMPLETED,
            PULSE_HEARTBEAT,
            VARIABLES_SYNCED,
        )

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
        if ammoi.tension_count > 0 or ammoi.cluster_count > 0:
            emit_engine_event(
                event_type=INFERENCE_COMPLETED,
                source="pulse",
                payload={
                    "tension_count": ammoi.tension_count,
                    "cluster_count": ammoi.cluster_count,
                    "inference_score": ammoi.inference_score,
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
        if edge_sync_result and edge_sync_result.created > 0:
            emit_engine_event(
                event_type=EDGES_SYNCED,
                source="pulse",
                payload={
                    "created": edge_sync_result.created,
                    "skipped": edge_sync_result.skipped,
                    "unresolved": edge_sync_result.unresolved,
                },
            )
        if var_sync_result and var_sync_result.variables_set > 0:
            emit_engine_event(
                event_type=VARIABLES_SYNCED,
                source="pulse",
                payload=var_sync_result.to_dict(),
            )
    except Exception:
        pass

    # 4.5. Write to Neon (best-effort)
    try:
        from organvm_engine.pulse.neon_sink import sync_to_neon
        _neon_obs: list = []
        try:
            from ontologia.registry.store import open_store as _neon_os
            _neon_st = _neon_os()
            _neon_obs = _neon_st.observation_store.query(limit=20)
        except Exception:
            pass
        sync_to_neon(ammoi, _neon_obs)
    except ImportError:
        pass
    except Exception:
        pass

    # 5. Heartbeat diffing (best-effort)
    heartbeat_diff: dict | None = None
    try:
        from organvm_engine.pulse.emitter import emit_engine_event as _emit
        from organvm_engine.pulse.types import HEARTBEAT_DIFF

        prev_hb = _load_heartbeat()
        curr_hb = HeartbeatState.from_ammoi(ammoi)
        if prev_hb is not None:
            heartbeat_diff = _compute_heartbeat_diff(prev_hb, curr_hb)
            if heartbeat_diff:
                _emit(
                    event_type=HEARTBEAT_DIFF,
                    source="pulse",
                    payload=heartbeat_diff,
                )
        _save_heartbeat(curr_hb)
    except Exception:
        pass

    # 6. Auto-insight recording (best-effort)
    try:
        from organvm_engine.pulse.ammoi import _read_history

        prev_snapshots = _read_history(limit=2)
        prev_ammoi = prev_snapshots[-2] if len(prev_snapshots) >= 2 else None

        # On first pulse (no previous), seed a baseline insight (once only)
        if prev_ammoi is None:
            from organvm_engine.pulse.shared_memory import query_insights, record_insight

            existing_baselines = query_insights(agent="pulse-daemon", limit=100)
            has_baseline = any("baseline" in i.tags for i in existing_baselines)
            if not has_baseline:
                record_insight(
                    agent="pulse-daemon",
                    category="finding",
                    content=(
                        f"System baseline: density={ammoi.system_density:.1%}, "
                        f"entities={ammoi.total_entities}, edges={ammoi.active_edges}, "
                        f"tensions={ammoi.tension_count}, clusters={ammoi.cluster_count}"
                    ),
                    tags=["baseline", "system-state"],
                )

        _record_pulse_insights(ammoi, prev_ammoi, heartbeat_diff)
    except Exception:
        pass

    # 7. Evaluate governance policies and store advisories (best-effort)
    try:
        from organvm_engine.pulse.advisories import evaluate_all_policies, store_advisories
        from organvm_engine.pulse.types import ADVISORY_GENERATED

        advisories = evaluate_all_policies(ws)
        if advisories:
            store_advisories(advisories)
            emit_engine_event(
                event_type=ADVISORY_GENERATED,
                source="pulse",
                payload={
                    "advisory_count": len(advisories),
                    "severities": [a.severity for a in advisories],
                },
            )
    except Exception:
        pass

    return ammoi


def pulse_daemon(
    interval: int = 900,
    workspace: Path | None = None,
    max_cycles: int = 0,
) -> None:
    """Run continuous pulse loop.

    Args:
        interval: Seconds between pulses (default 900 = 15 minutes).
        workspace: Workspace root. Defaults to ~/Workspace.
        max_cycles: Stop after N cycles (0 = unlimited, for production).
    """
    ws = workspace or Path.home() / "Workspace"
    running = True

    def _handle_signal(signum: int, frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    cycle = 0
    while running:
        cycle += 1
        try:
            ammoi = pulse_once(workspace=ws)
            print(
                f"[pulse] cycle={cycle} density={ammoi.system_density:.1%}"
                f" entities={ammoi.total_entities} edges={ammoi.active_edges}",
                flush=True,
            )
        except Exception as exc:
            print(f"[pulse] cycle={cycle} error: {exc}", file=sys.stderr, flush=True)

        if max_cycles and cycle >= max_cycles:
            break

        # Sleep in 1-second increments for responsive shutdown
        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

    print(f"[pulse] stopped after {cycle} cycles", flush=True)


# ---------------------------------------------------------------------------
# LaunchAgent management
# ---------------------------------------------------------------------------

PLIST_LABEL = "com.4jp.organvm.pulse"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"
LOG_PATH = Path.home() / "System" / "Logs" / "organvm-pulse.log"
ERR_LOG_PATH = Path.home() / "System" / "Logs" / "organvm-pulse-stderr.log"


def _generate_plist(interval: int = 900) -> str:
    """Generate the LaunchAgent plist XML."""
    # Find the organvm executable — prefer venv, fall back to PATH
    venv_bin = Path.home() / "Workspace" / "meta-organvm" / ".venv" / "bin" / "organvm"
    organvm_bin = str(venv_bin) if venv_bin.exists() else "/opt/homebrew/bin/organvm"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>{organvm_bin}</string>
        <string>pulse</string>
        <string>scan</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/4jp/Workspace/meta-organvm</string>

    <key>StartInterval</key>
    <integer>{interval}</integer>

    <key>ProcessType</key>
    <string>Background</string>

    <key>Nice</key>
    <integer>10</integer>

    <key>LowPriorityIO</key>
    <true/>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/4jp/.local/bin</string>
        <key>HOME</key>
        <string>/Users/4jp</string>
    </dict>

    <key>StandardOutPath</key>
    <string>{LOG_PATH}</string>
    <key>StandardErrorPath</key>
    <string>{ERR_LOG_PATH}</string>
</dict>
</plist>
"""


def install_launchagent(interval: int = 900) -> str:
    """Install the pulse LaunchAgent plist. Returns the plist path."""
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(_generate_plist(interval))
    return str(PLIST_PATH)


def uninstall_launchagent() -> bool:
    """Remove the plist file. Returns True if it existed."""
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()
        return True
    return False


def launchagent_status() -> dict[str, Any]:
    """Query LaunchAgent status via launchctl."""
    import subprocess

    result: dict[str, Any] = {
        "installed": PLIST_PATH.exists(),
        "plist_path": str(PLIST_PATH),
        "log_path": str(LOG_PATH),
    }

    if not PLIST_PATH.exists():
        result["running"] = False
        return result

    try:
        proc = subprocess.run(
            ["launchctl", "list", PLIST_LABEL],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        result["running"] = proc.returncode == 0
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if "PID" in line and "=" in line:
                    result["pid"] = line.split("=")[-1].strip().rstrip(";")
    except Exception:
        result["running"] = False

    # Last log lines
    if LOG_PATH.exists():
        try:
            lines = LOG_PATH.read_text().strip().splitlines()
            result["last_log"] = lines[-1] if lines else ""
            result["log_lines"] = len(lines)
        except Exception:
            pass

    return result


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
