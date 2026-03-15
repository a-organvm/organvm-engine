"""Neon PostgreSQL metrics sink — mirror pulse observations for portal queries.

Requires: psycopg[binary] (optional: pip install organvm-engine[neon])
Env var: ORGANVM_NEON_URL — silently skips if not set.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

try:
    import psycopg
except ImportError:
    psycopg = None  # type: ignore[assignment]

ENSURE_TABLES_SQL = """\
CREATE TABLE IF NOT EXISTS pulse_snapshots (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    density REAL NOT NULL,
    entities INTEGER NOT NULL,
    edges INTEGER NOT NULL,
    tensions INTEGER NOT NULL,
    clusters INTEGER NOT NULL,
    ammoi_text TEXT NOT NULL,
    gate_rates JSONB,
    organ_densities JSONB
);
CREATE TABLE IF NOT EXISTS metric_observations (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metric_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    value REAL NOT NULL,
    source TEXT NOT NULL DEFAULT 'pulse'
);
CREATE INDEX IF NOT EXISTS idx_observations_metric_ts
    ON metric_observations (metric_id, timestamp DESC);
"""

INSERT_SNAPSHOT = """\
INSERT INTO pulse_snapshots
    (density, entities, edges, tensions, clusters, ammoi_text, gate_rates, organ_densities)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""

INSERT_OBSERVATION = """\
INSERT INTO metric_observations (metric_id, entity_id, value, source)
VALUES (%s, %s, %s, %s)
"""


@dataclass
class NeonSyncResult:
    snapshots_written: int = 0
    observations_written: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshots_written": self.snapshots_written,
            "observations_written": self.observations_written,
            "errors": self.errors,
        }


def _build_snapshot_row(ammoi: Any) -> tuple:
    gate_rates: dict[str, int] = {}
    organ_densities: dict[str, float] = {}
    for oid, organ in getattr(ammoi, "organs", {}).items():
        gate_rates[oid] = getattr(organ, "avg_gate_pct", 0)
        organ_densities[oid] = getattr(organ, "density", 0.0)
    return (
        ammoi.system_density,
        ammoi.total_entities,
        ammoi.active_edges,
        ammoi.tension_count,
        ammoi.cluster_count,
        ammoi.compressed_text,
        json.dumps(gate_rates),
        json.dumps(organ_densities),
    )


def _default_connection_url() -> str:
    return os.environ.get("ORGANVM_NEON_URL", "")


def sync_to_neon(
    ammoi: Any,
    observations: list[Any],
    connection_url: str = "",
) -> NeonSyncResult:
    result = NeonSyncResult()
    url = connection_url or _default_connection_url()
    if not url:
        return result
    if psycopg is None:
        result.errors.append("psycopg not installed (pip install organvm-engine[neon])")
        return result
    try:
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(ENSURE_TABLES_SQL)
                row = _build_snapshot_row(ammoi)
                cur.execute(INSERT_SNAPSHOT, row)
                result.snapshots_written = 1
                for obs in observations:
                    try:
                        cur.execute(INSERT_OBSERVATION, (
                            obs.metric_id, obs.entity_id, obs.value,
                            getattr(obs, "source", "pulse"),
                        ))
                        result.observations_written += 1
                    except Exception as e:
                        result.errors.append(f"observation {getattr(obs, 'metric_id', '?')}: {e}")
            conn.commit()
    except Exception as e:
        result.errors.append(f"neon_sink: {e}")
        logger.debug("Neon sink failed (non-fatal)", exc_info=True)
    return result
