"""Tests for organvm_engine.pulse.neon_sink."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from organvm_engine.pulse.neon_sink import (
    ENSURE_TABLES_SQL,
    NeonSyncResult,
    _build_snapshot_row,
    sync_to_neon,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_organ(avg_gate_pct: int = 50, density: float = 0.5) -> MagicMock:
    organ = MagicMock()
    organ.avg_gate_pct = avg_gate_pct
    organ.density = density
    return organ


def _make_ammoi(
    system_density: float = 0.42,
    total_entities: int = 100,
    active_edges: int = 200,
    tension_count: int = 3,
    cluster_count: int = 5,
    compressed_text: str = "8o/100e/200ed",
    organs: dict | None = None,
) -> MagicMock:
    ammoi = MagicMock()
    ammoi.system_density = system_density
    ammoi.total_entities = total_entities
    ammoi.active_edges = active_edges
    ammoi.tension_count = tension_count
    ammoi.cluster_count = cluster_count
    ammoi.compressed_text = compressed_text
    ammoi.organs = organs or {}
    return ammoi


def _make_observation(metric_id: str = "density", entity_id: str = "ent_001", value: float = 0.5) -> MagicMock:
    obs = MagicMock()
    obs.metric_id = metric_id
    obs.entity_id = entity_id
    obs.value = value
    obs.source = "pulse"
    return obs


# ---------------------------------------------------------------------------
# NeonSyncResult tests
# ---------------------------------------------------------------------------


def test_neon_sync_result_defaults() -> None:
    result = NeonSyncResult()
    assert result.snapshots_written == 0
    assert result.observations_written == 0
    assert result.errors == []


def test_neon_sync_result_to_dict() -> None:
    result = NeonSyncResult(snapshots_written=1, observations_written=3, errors=["oops"])
    d = result.to_dict()
    assert d["snapshots_written"] == 1
    assert d["observations_written"] == 3
    assert d["errors"] == ["oops"]


def test_neon_sync_result_to_dict_empty() -> None:
    result = NeonSyncResult()
    d = result.to_dict()
    assert d == {"snapshots_written": 0, "observations_written": 0, "errors": []}


# ---------------------------------------------------------------------------
# _build_snapshot_row tests
# ---------------------------------------------------------------------------


def test_build_snapshot_row_length() -> None:
    ammoi = _make_ammoi()
    row = _build_snapshot_row(ammoi)
    assert len(row) == 8


def test_build_snapshot_row_values_no_organs() -> None:
    ammoi = _make_ammoi(
        system_density=0.42,
        total_entities=100,
        active_edges=200,
        tension_count=3,
        cluster_count=5,
        compressed_text="8o/100e/200ed",
    )
    row = _build_snapshot_row(ammoi)
    assert row[0] == 0.42
    assert row[1] == 100
    assert row[2] == 200
    assert row[3] == 3
    assert row[4] == 5
    assert row[5] == "8o/100e/200ed"
    # gate_rates and organ_densities are JSON strings of empty dicts
    import json
    assert json.loads(row[6]) == {}
    assert json.loads(row[7]) == {}


def test_build_snapshot_row_with_organs() -> None:
    import json
    organs = {
        "ORGAN-I": _make_organ(avg_gate_pct=60, density=0.6),
        "ORGAN-II": _make_organ(avg_gate_pct=40, density=0.4),
    }
    ammoi = _make_ammoi(organs=organs)
    row = _build_snapshot_row(ammoi)
    gate_rates = json.loads(row[6])
    organ_densities = json.loads(row[7])
    assert gate_rates["ORGAN-I"] == 60
    assert gate_rates["ORGAN-II"] == 40
    assert organ_densities["ORGAN-I"] == pytest.approx(0.6)
    assert organ_densities["ORGAN-II"] == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# sync_to_neon — empty URL skips silently
# ---------------------------------------------------------------------------


def test_sync_to_neon_no_url_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ORGANVM_NEON_URL", raising=False)
    ammoi = _make_ammoi()
    result = sync_to_neon(ammoi, [], connection_url="")
    assert result.snapshots_written == 0
    assert result.observations_written == 0
    assert result.errors == []


def test_sync_to_neon_env_url_empty_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORGANVM_NEON_URL", "")
    ammoi = _make_ammoi()
    result = sync_to_neon(ammoi, [])
    assert result.snapshots_written == 0
    assert result.errors == []


# ---------------------------------------------------------------------------
# sync_to_neon — psycopg missing
# ---------------------------------------------------------------------------


def test_sync_to_neon_no_psycopg_records_error() -> None:
    with patch("organvm_engine.pulse.neon_sink.psycopg", None):
        ammoi = _make_ammoi()
        result = sync_to_neon(ammoi, [], connection_url="postgresql://fake/db")
    assert result.snapshots_written == 0
    assert len(result.errors) == 1
    assert "psycopg not installed" in result.errors[0]


# ---------------------------------------------------------------------------
# sync_to_neon — successful write with mocked psycopg
# ---------------------------------------------------------------------------


def _setup_mock_psycopg() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Returns (mock_psycopg, mock_conn, mock_cursor)."""
    mock_psycopg = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_psycopg.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_psycopg.connect.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_psycopg, mock_conn, mock_cursor


def test_sync_to_neon_writes_snapshot() -> None:
    mock_psycopg, mock_conn, mock_cursor = _setup_mock_psycopg()
    with patch("organvm_engine.pulse.neon_sink.psycopg", mock_psycopg):
        ammoi = _make_ammoi()
        result = sync_to_neon(ammoi, [], connection_url="postgresql://fake/db")
    assert result.snapshots_written == 1
    assert result.observations_written == 0
    assert result.errors == []
    # Verify ENSURE_TABLES_SQL was executed
    assert mock_cursor.execute.call_count >= 2  # ensure tables + insert snapshot


def test_sync_to_neon_writes_observations() -> None:
    mock_psycopg, mock_conn, mock_cursor = _setup_mock_psycopg()
    obs = [_make_observation("density", "ent_001", 0.5), _make_observation("edges", "ent_002", 100.0)]
    with patch("organvm_engine.pulse.neon_sink.psycopg", mock_psycopg):
        ammoi = _make_ammoi()
        result = sync_to_neon(ammoi, obs, connection_url="postgresql://fake/db")
    assert result.snapshots_written == 1
    assert result.observations_written == 2
    assert result.errors == []


def test_sync_to_neon_calls_commit() -> None:
    mock_psycopg, mock_conn, mock_cursor = _setup_mock_psycopg()
    with patch("organvm_engine.pulse.neon_sink.psycopg", mock_psycopg):
        ammoi = _make_ammoi()
        sync_to_neon(ammoi, [], connection_url="postgresql://fake/db")
    mock_conn.commit.assert_called_once()


def test_sync_to_neon_passes_url_to_connect() -> None:
    mock_psycopg, mock_conn, mock_cursor = _setup_mock_psycopg()
    url = "postgresql://user:pass@host/db"
    with patch("organvm_engine.pulse.neon_sink.psycopg", mock_psycopg):
        ammoi = _make_ammoi()
        sync_to_neon(ammoi, [], connection_url=url)
    mock_psycopg.connect.assert_called_once_with(url)


# ---------------------------------------------------------------------------
# sync_to_neon — connection error captured, doesn't raise
# ---------------------------------------------------------------------------


def test_sync_to_neon_connection_error_captured() -> None:
    mock_psycopg = MagicMock()
    mock_psycopg.connect.side_effect = Exception("connection refused")
    with patch("organvm_engine.pulse.neon_sink.psycopg", mock_psycopg):
        ammoi = _make_ammoi()
        result = sync_to_neon(ammoi, [], connection_url="postgresql://bad/db")
    assert result.snapshots_written == 0
    assert len(result.errors) == 1
    assert "neon_sink" in result.errors[0]
    assert "connection refused" in result.errors[0]


def test_sync_to_neon_observation_error_partial_write() -> None:
    """Observation-level errors are captured without stopping snapshot write."""
    mock_psycopg, mock_conn, mock_cursor = _setup_mock_psycopg()
    # Make the observation insert raise by patching INSERT_OBSERVATION specifically:
    # First two calls (ENSURE_TABLES + INSERT_SNAPSHOT) succeed; third raises.
    call_count = [0]

    def execute_side_effect(sql, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] >= 3:  # 3rd call = first observation insert
            raise Exception("bad value")
        # Return None (normal MagicMock return) for earlier calls

    mock_cursor.execute.side_effect = execute_side_effect

    obs = [_make_observation()]
    with patch("organvm_engine.pulse.neon_sink.psycopg", mock_psycopg):
        ammoi = _make_ammoi()
        result = sync_to_neon(ammoi, obs, connection_url="postgresql://fake/db")

    # Snapshot was written (errors only at observation level)
    assert result.snapshots_written == 1
    assert result.observations_written == 0
    assert len(result.errors) == 1
    assert "observation" in result.errors[0]


# ---------------------------------------------------------------------------
# ENSURE_TABLES_SQL content checks
# ---------------------------------------------------------------------------


def test_ensure_tables_sql_contains_pulse_snapshots() -> None:
    assert "CREATE TABLE IF NOT EXISTS pulse_snapshots" in ENSURE_TABLES_SQL


def test_ensure_tables_sql_contains_metric_observations() -> None:
    assert "CREATE TABLE IF NOT EXISTS metric_observations" in ENSURE_TABLES_SQL


def test_ensure_tables_sql_contains_index() -> None:
    assert "CREATE INDEX IF NOT EXISTS" in ENSURE_TABLES_SQL
    assert "idx_observations_metric_ts" in ENSURE_TABLES_SQL


def test_ensure_tables_sql_contains_jsonb_columns() -> None:
    assert "JSONB" in ENSURE_TABLES_SQL


# ---------------------------------------------------------------------------
# sync_to_neon uses env var ORGANVM_NEON_URL
# ---------------------------------------------------------------------------


def test_sync_to_neon_uses_env_url(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_psycopg, mock_conn, mock_cursor = _setup_mock_psycopg()
    env_url = "postgresql://env-user:env-pass@env-host/env-db"
    monkeypatch.setenv("ORGANVM_NEON_URL", env_url)
    with patch("organvm_engine.pulse.neon_sink.psycopg", mock_psycopg):
        ammoi = _make_ammoi()
        result = sync_to_neon(ammoi, [])  # no explicit connection_url
    mock_psycopg.connect.assert_called_once_with(env_url)
    assert result.snapshots_written == 1


def test_sync_to_neon_explicit_url_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_psycopg, mock_conn, mock_cursor = _setup_mock_psycopg()
    monkeypatch.setenv("ORGANVM_NEON_URL", "postgresql://env-host/env-db")
    explicit_url = "postgresql://explicit-host/explicit-db"
    with patch("organvm_engine.pulse.neon_sink.psycopg", mock_psycopg):
        ammoi = _make_ammoi()
        sync_to_neon(ammoi, [], connection_url=explicit_url)
    mock_psycopg.connect.assert_called_once_with(explicit_url)
