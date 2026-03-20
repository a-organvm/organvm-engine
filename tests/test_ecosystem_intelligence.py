"""Tests for ecosystem.intelligence — snapshot and intelligence I/O.

Covers write_snapshot, list_snapshots, read_snapshot, latest_snapshot,
write_intelligence, read_intelligence, and staleness_report.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import yaml

from organvm_engine.ecosystem.intelligence import (
    INTELLIGENCE_DIR,
    SNAPSHOTS_DIR,
    latest_snapshot,
    list_snapshots,
    read_intelligence,
    read_snapshot,
    staleness_report,
    write_intelligence,
    write_snapshot,
)


# ── write_snapshot ────────────────────────────────────────────────


class TestWriteSnapshot:
    def test_writes_yaml_file(self, tmp_path):
        data = {"competitors": ["acme", "globex"]}
        path = write_snapshot(tmp_path, "marketing", data)
        assert path.exists()
        assert path.suffix == ".yaml"
        loaded = yaml.safe_load(path.read_text())
        assert loaded == data

    def test_default_name_landscape(self, tmp_path):
        path = write_snapshot(tmp_path, "revenue", {"a": 1})
        assert "landscape" in path.name

    def test_custom_snapshot_name(self, tmp_path):
        path = write_snapshot(
            tmp_path, "delivery", {"b": 2}, snapshot_name="uptime-check",
        )
        assert "uptime-check" in path.name

    def test_date_in_filename(self, tmp_path):
        d = date(2026, 3, 15)
        path = write_snapshot(
            tmp_path, "marketing", {"c": 3}, snapshot_date=d,
        )
        assert "2026-03-15" in path.name

    def test_creates_subdirectories(self, tmp_path):
        write_snapshot(tmp_path, "content", {"x": 1})
        snap_dir = tmp_path / SNAPSHOTS_DIR / "content"
        assert snap_dir.is_dir()

    def test_append_only_no_overwrite(self, tmp_path):
        """Different dates produce different files."""
        write_snapshot(
            tmp_path, "marketing", {"v": 1},
            snapshot_date=date(2026, 1, 1),
        )
        write_snapshot(
            tmp_path, "marketing", {"v": 2},
            snapshot_date=date(2026, 1, 2),
        )
        snap_dir = tmp_path / SNAPSHOTS_DIR / "marketing"
        files = list(snap_dir.iterdir())
        assert len(files) == 2

    def test_returns_correct_path(self, tmp_path):
        d = date(2026, 6, 1)
        path = write_snapshot(
            tmp_path, "listings", {"z": 1},
            snapshot_name="store-ranking", snapshot_date=d,
        )
        expected = (
            tmp_path / SNAPSHOTS_DIR / "listings" / "2026-06-01--store-ranking.yaml"
        )
        assert path == expected


# ── list_snapshots ────────────────────────────────────────────────


class TestListSnapshots:
    def test_empty_when_no_dir(self, tmp_path):
        result = list_snapshots(tmp_path, "marketing")
        assert result == []

    def test_lists_in_date_descending(self, tmp_path):
        write_snapshot(tmp_path, "marketing", {"v": 1}, snapshot_date=date(2026, 1, 1))
        write_snapshot(tmp_path, "marketing", {"v": 2}, snapshot_date=date(2026, 3, 1))
        write_snapshot(tmp_path, "marketing", {"v": 3}, snapshot_date=date(2026, 2, 1))
        result = list_snapshots(tmp_path, "marketing")
        dates = [d for d, _ in result]
        assert dates == ["2026-03-01", "2026-02-01", "2026-01-01"]

    def test_returns_paths(self, tmp_path):
        write_snapshot(tmp_path, "revenue", {"a": 1}, snapshot_date=date(2026, 5, 1))
        result = list_snapshots(tmp_path, "revenue")
        assert len(result) == 1
        _, path = result[0]
        assert path.exists()
        assert path.suffix == ".yaml"

    def test_skips_non_yaml_files(self, tmp_path):
        write_snapshot(tmp_path, "content", {"a": 1}, snapshot_date=date(2026, 1, 1))
        # Drop a non-yaml file into the snapshots dir
        (tmp_path / SNAPSHOTS_DIR / "content" / "notes.txt").write_text("hi")
        result = list_snapshots(tmp_path, "content")
        assert len(result) == 1

    def test_handles_filename_without_double_dash(self, tmp_path):
        """Files without '--' in stem should use the whole stem as date."""
        snap_dir = tmp_path / SNAPSHOTS_DIR / "marketing"
        snap_dir.mkdir(parents=True)
        (snap_dir / "2026-04-01.yaml").write_text("key: val\n")
        result = list_snapshots(tmp_path, "marketing")
        assert len(result) == 1
        assert result[0][0] == "2026-04-01"


# ── read_snapshot ─────────────────────────────────────────────────


class TestReadSnapshot:
    def test_read_existing(self, tmp_path):
        data = {"competitors": ["a", "b"]}
        write_snapshot(tmp_path, "marketing", data, snapshot_date=date(2026, 2, 1))
        result = read_snapshot(tmp_path, "marketing", "2026-02-01")
        assert result == data

    def test_read_nonexistent_date(self, tmp_path):
        write_snapshot(tmp_path, "marketing", {"x": 1}, snapshot_date=date(2026, 1, 1))
        result = read_snapshot(tmp_path, "marketing", "2099-01-01")
        assert result is None

    def test_read_nonexistent_pillar(self, tmp_path):
        result = read_snapshot(tmp_path, "nonexistent", "2026-01-01")
        assert result is None

    def test_date_prefix_matching(self, tmp_path):
        """read_snapshot matches by startswith, so date prefix works."""
        data = {"info": "yes"}
        write_snapshot(
            tmp_path, "revenue", data,
            snapshot_name="pricing",
            snapshot_date=date(2026, 7, 15),
        )
        result = read_snapshot(tmp_path, "revenue", "2026-07-15")
        assert result == data


# ── latest_snapshot ───────────────────────────────────────────────


class TestLatestSnapshot:
    def test_returns_most_recent(self, tmp_path):
        write_snapshot(tmp_path, "delivery", {"v": 1}, snapshot_date=date(2026, 1, 1))
        write_snapshot(tmp_path, "delivery", {"v": 2}, snapshot_date=date(2026, 6, 1))
        write_snapshot(tmp_path, "delivery", {"v": 3}, snapshot_date=date(2026, 3, 1))
        result = latest_snapshot(tmp_path, "delivery")
        assert result == {"v": 2}

    def test_returns_none_when_empty(self, tmp_path):
        result = latest_snapshot(tmp_path, "nonexistent")
        assert result is None

    def test_single_snapshot(self, tmp_path):
        data = {"only": "one"}
        write_snapshot(tmp_path, "listings", data, snapshot_date=date(2026, 4, 1))
        result = latest_snapshot(tmp_path, "listings")
        assert result == data


# ── write_intelligence / read_intelligence ────────────────────────


class TestIntelligence:
    def test_write_and_read(self, tmp_path):
        data = {"competitors": ["x", "y"], "notes": "preliminary"}
        path = write_intelligence(tmp_path, "marketing", "competitor-profiles", data)
        assert path.exists()
        result = read_intelligence(tmp_path, "marketing", "competitor-profiles")
        assert result == data

    def test_creates_directories(self, tmp_path):
        write_intelligence(tmp_path, "revenue", "pricing-analysis", {"a": 1})
        intel_dir = tmp_path / INTELLIGENCE_DIR / "revenue"
        assert intel_dir.is_dir()

    def test_read_nonexistent(self, tmp_path):
        result = read_intelligence(tmp_path, "content", "missing-artifact")
        assert result is None

    def test_read_with_yml_extension(self, tmp_path):
        """read_intelligence checks both .yaml and .yml."""
        intel_dir = tmp_path / INTELLIGENCE_DIR / "community"
        intel_dir.mkdir(parents=True)
        (intel_dir / "health.yml").write_text("status: good\n")
        result = read_intelligence(tmp_path, "community", "health")
        assert result == {"status": "good"}

    def test_overwrite_intelligence(self, tmp_path):
        """Intelligence artifacts are living documents — overwrite allowed."""
        write_intelligence(tmp_path, "marketing", "profiles", {"v": 1})
        write_intelligence(tmp_path, "marketing", "profiles", {"v": 2})
        result = read_intelligence(tmp_path, "marketing", "profiles")
        assert result == {"v": 2}

    def test_returns_path(self, tmp_path):
        path = write_intelligence(tmp_path, "delivery", "pipeline", {"x": 1})
        expected = tmp_path / INTELLIGENCE_DIR / "delivery" / "pipeline.yaml"
        assert path == expected


# ── staleness_report ──────────────────────────────────────────────


class TestStalenessReport:
    def _write_pillar_dna(self, repo: Path, pillar: str, data: dict) -> None:
        """Write a pillar DNA file for testing."""
        dna_dir = repo / "ecosystem" / "pillar-dna"
        dna_dir.mkdir(parents=True, exist_ok=True)
        with (dna_dir / f"{pillar}.yaml").open("w") as f:
            yaml.dump(data, f)

    def test_no_dna_returns_empty(self, tmp_path):
        result = staleness_report(tmp_path)
        assert result == []

    def test_missing_snapshot_reported(self, tmp_path):
        self._write_pillar_dna(tmp_path, "marketing", {
            "artifacts": [
                {"name": "landscape-snapshot", "staleness_days": 30},
            ],
        })
        result = staleness_report(tmp_path)
        assert len(result) == 1
        assert result[0]["status"] == "missing"
        assert result[0]["pillar"] == "marketing"
        assert result[0]["artifact"] == "landscape-snapshot"
        assert result[0]["days_stale"] is None

    def test_stale_snapshot_reported(self, tmp_path):
        self._write_pillar_dna(tmp_path, "revenue", {
            "artifacts": [
                {"name": "pricing-comparison", "staleness_days": 30},
            ],
        })
        # Write a snapshot that is 60 days old
        old_date = date.today() - timedelta(days=60)
        write_snapshot(tmp_path, "revenue", {"a": 1}, snapshot_date=old_date)

        result = staleness_report(tmp_path)
        assert len(result) == 1
        assert result[0]["status"] == "stale"
        assert result[0]["days_stale"] >= 60

    def test_fresh_snapshot_not_reported(self, tmp_path):
        self._write_pillar_dna(tmp_path, "delivery", {
            "artifacts": [
                {"name": "uptime-monitoring", "staleness_days": 14},
            ],
        })
        # Write a recent snapshot
        write_snapshot(
            tmp_path, "delivery", {"ok": True},
            snapshot_date=date.today(),
        )
        result = staleness_report(tmp_path)
        assert result == []

    def test_no_staleness_days_skipped(self, tmp_path):
        """Artifacts without staleness_days should be ignored."""
        self._write_pillar_dna(tmp_path, "content", {
            "artifacts": [
                {"name": "calendar", "cadence": "monthly"},  # no staleness_days
            ],
        })
        result = staleness_report(tmp_path)
        assert result == []

    def test_non_int_staleness_days_skipped(self, tmp_path):
        self._write_pillar_dna(tmp_path, "marketing", {
            "artifacts": [
                {"name": "snapshot", "staleness_days": "thirty"},
            ],
        })
        result = staleness_report(tmp_path)
        assert result == []

    def test_non_list_artifacts_skipped(self, tmp_path):
        self._write_pillar_dna(tmp_path, "revenue", {
            "artifacts": "not a list",
        })
        result = staleness_report(tmp_path)
        assert result == []

    def test_non_dict_artifact_entry_skipped(self, tmp_path):
        self._write_pillar_dna(tmp_path, "revenue", {
            "artifacts": ["just-a-string"],
        })
        result = staleness_report(tmp_path)
        assert result == []

    def test_multiple_pillars(self, tmp_path):
        self._write_pillar_dna(tmp_path, "marketing", {
            "artifacts": [{"name": "snap", "staleness_days": 7}],
        })
        self._write_pillar_dna(tmp_path, "revenue", {
            "artifacts": [{"name": "pricing", "staleness_days": 7}],
        })
        result = staleness_report(tmp_path)
        # Both should be missing since no snapshots exist
        assert len(result) == 2
        pillars = {r["pillar"] for r in result}
        assert pillars == {"marketing", "revenue"}

    def test_invalid_date_in_snapshot_skipped(self, tmp_path):
        """Snapshots with unparseable date strings should be skipped."""
        self._write_pillar_dna(tmp_path, "marketing", {
            "artifacts": [{"name": "snap", "staleness_days": 7}],
        })
        # Create a snapshot with a malformed date in filename
        snap_dir = tmp_path / SNAPSHOTS_DIR / "marketing"
        snap_dir.mkdir(parents=True, exist_ok=True)
        (snap_dir / "BADDATE--landscape.yaml").write_text("x: 1\n")

        result = staleness_report(tmp_path)
        # Should report as missing (the bad date was skipped)
        assert len(result) == 1
        assert result[0]["status"] == "missing"

    def test_most_recent_snapshot_used(self, tmp_path):
        """Staleness should be measured from the newest snapshot."""
        self._write_pillar_dna(tmp_path, "delivery", {
            "artifacts": [{"name": "uptime", "staleness_days": 10}],
        })
        # Old snapshot (20 days ago) => stale
        write_snapshot(
            tmp_path, "delivery", {"v": 1},
            snapshot_date=date.today() - timedelta(days=20),
        )
        # Recent snapshot (2 days ago) => fresh
        write_snapshot(
            tmp_path, "delivery", {"v": 2},
            snapshot_date=date.today() - timedelta(days=2),
        )
        result = staleness_report(tmp_path)
        # The recent snapshot makes this fresh
        assert result == []
