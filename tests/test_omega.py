"""Tests for the omega scorecard module."""

import json

import pytest

from organvm_engine.omega.scorecard import (
    analyze_soak_streak,
    diff_snapshots,
    evaluate,
    write_snapshot,
)


@pytest.fixture
def soak_dir(tmp_path):
    """Create a temporary soak-test directory with 8 days of data."""
    d = tmp_path / "soak-test"
    d.mkdir()
    for i in range(8):
        day = f"2026-02-{16 + i:02d}"
        snapshot = {
            "date": day,
            "validation": {
                "registry_pass": True,
                "dependency_pass": True,
            },
            "ci": {"total_checked": 77, "passing": 50, "failing": 25},
            "engagement": {"total_stars": 5, "total_forks": 3},
        }
        (d / f"daily-{day}.json").write_text(json.dumps(snapshot))
    return d


@pytest.fixture
def soak_dir_with_gap(tmp_path):
    """Soak dir with a gap on day 3."""
    d = tmp_path / "soak-test"
    d.mkdir()
    # Days: 16, 17, (gap 18), 19, 20, 21, 22, 23
    days = [16, 17, 19, 20, 21, 22, 23]
    for day_num in days:
        day = f"2026-02-{day_num:02d}"
        snapshot = {
            "date": day,
            "validation": {"registry_pass": True, "dependency_pass": True},
            "ci": {"total_checked": 77, "passing": 50, "failing": 25},
        }
        (d / f"daily-{day}.json").write_text(json.dumps(snapshot))
    return d


@pytest.fixture
def soak_dir_with_incident(tmp_path):
    """Soak dir with a critical incident."""
    d = tmp_path / "soak-test"
    d.mkdir()
    for i in range(3):
        day = f"2026-02-{16 + i:02d}"
        validation_pass = i != 1  # day 2 has an incident
        snapshot = {
            "date": day,
            "validation": {
                "registry_pass": validation_pass,
                "dependency_pass": True,
            },
            "ci": {"total_checked": 77, "passing": 50, "failing": 25},
        }
        (d / f"daily-{day}.json").write_text(json.dumps(snapshot))
    return d


@pytest.fixture
def registry():
    return {
        "version": "2.0",
        "organs": {
            "ORGAN-III": {
                "name": "Commerce",
                "launch_status": "OPERATIONAL",
                "repositories": [
                    {
                        "name": "product-app",
                        "org": "organvm-iii-ergon",
                        "implementation_status": "ACTIVE",
                        "public": True,
                        "description": "Test product",
                        "revenue_status": "pre-launch",
                    },
                ],
            },
        },
    }


@pytest.fixture
def registry_with_revenue():
    return {
        "version": "2.0",
        "organs": {
            "ORGAN-III": {
                "name": "Commerce",
                "launch_status": "OPERATIONAL",
                "repositories": [
                    {
                        "name": "product-app",
                        "org": "organvm-iii-ergon",
                        "implementation_status": "ACTIVE",
                        "public": True,
                        "description": "Test product",
                        "revenue_status": "live",
                    },
                ],
            },
        },
    }


class TestSoakStreak:
    def test_consecutive_streak(self, soak_dir):
        result = analyze_soak_streak(soak_dir)
        assert result.total_snapshots == 8
        assert result.streak_days == 8
        assert result.first_date == "2026-02-16"
        assert result.last_date == "2026-02-23"
        assert result.gaps == []
        assert result.critical_incidents == 0

    def test_streak_with_gap(self, soak_dir_with_gap):
        result = analyze_soak_streak(soak_dir_with_gap)
        assert result.total_snapshots == 7
        # Streak from latest back: 23,22,21,20,19 = 5 consecutive
        assert result.streak_days == 5
        assert "2026-02-18" in result.gaps

    def test_critical_incidents(self, soak_dir_with_incident):
        result = analyze_soak_streak(soak_dir_with_incident)
        assert result.critical_incidents == 1

    def test_empty_dir(self, tmp_path):
        empty = tmp_path / "empty-soak"
        empty.mkdir()
        result = analyze_soak_streak(empty)
        assert result.total_snapshots == 0
        assert result.streak_days == 0

    def test_nonexistent_dir(self, tmp_path):
        result = analyze_soak_streak(tmp_path / "nonexistent")
        assert result.total_snapshots == 0

    def test_days_remaining(self, soak_dir):
        result = analyze_soak_streak(soak_dir)
        assert result.days_remaining == 22  # 30 - 8

    def test_target_not_met_short_streak(self, soak_dir):
        result = analyze_soak_streak(soak_dir)
        assert not result.target_met

    def test_target_met_30_days(self, tmp_path):
        d = tmp_path / "soak-test"
        d.mkdir()
        for i in range(30):
            day = f"2026-02-{16 + i:02d}" if 16 + i <= 28 else f"2026-03-{16 + i - 28:02d}"
            snapshot = {
                "date": day,
                "validation": {"registry_pass": True, "dependency_pass": True},
            }
            (d / f"daily-{day}.json").write_text(json.dumps(snapshot))
        result = analyze_soak_streak(d)
        assert result.streak_days == 30
        assert result.target_met


class TestEvaluate:
    def test_returns_17_criteria(self, registry, soak_dir):
        scorecard = evaluate(registry=registry, soak_dir=soak_dir)
        assert len(scorecard.criteria) == 17
        assert scorecard.total == 17

    def test_criterion_6_always_met(self, registry, soak_dir):
        scorecard = evaluate(registry=registry, soak_dir=soak_dir)
        c6 = scorecard.criteria[5]  # 0-indexed
        assert c6.id == 6
        assert c6.status == "MET"

    def test_soak_in_progress(self, registry, soak_dir):
        scorecard = evaluate(registry=registry, soak_dir=soak_dir)
        c1 = scorecard.criteria[0]
        assert c1.status == "IN_PROGRESS"
        assert "8/30" in c1.value

    def test_soak_not_started(self, registry, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        scorecard = evaluate(registry=registry, soak_dir=empty)
        c1 = scorecard.criteria[0]
        assert c1.status == "NOT_MET"

    def test_revenue_not_met(self, registry, soak_dir):
        scorecard = evaluate(registry=registry, soak_dir=soak_dir)
        c9 = scorecard.criteria[8]
        assert c9.id == 9
        assert c9.status == "NOT_MET"

    def test_revenue_met(self, registry_with_revenue, soak_dir):
        scorecard = evaluate(registry=registry_with_revenue, soak_dir=soak_dir)
        c9 = scorecard.criteria[8]
        assert c9.status == "MET"

    def test_met_count(self, registry, soak_dir):
        scorecard = evaluate(registry=registry, soak_dir=soak_dir)
        # #5 (submitted), #6 (essay), #8 (products live), #13 (inbound link), #15 (portfolio validation) are MET
        assert scorecard.met_count == 5

    def test_summary_output(self, registry, soak_dir):
        scorecard = evaluate(registry=registry, soak_dir=soak_dir)
        summary = scorecard.summary()
        assert "5/17 MET" in summary
        assert "Soak Test Streak" in summary
        assert "8/30" in summary

    def test_to_dict(self, registry, soak_dir):
        scorecard = evaluate(registry=registry, soak_dir=soak_dir)
        d = scorecard.to_dict()
        assert d["score"] == 5
        assert d["total"] == 17
        assert len(d["criteria"]) == 17
        assert "soak" in d
        assert d["soak"]["streak_days"] == 8

    def test_auto_criteria_identified(self, registry, soak_dir):
        scorecard = evaluate(registry=registry, soak_dir=soak_dir)
        auto_ids = {c.id for c in scorecard.criteria if c.auto}
        assert auto_ids == {1, 3, 9, 17}


class TestWriteSnapshot:
    def test_writes_json_file(self, registry, soak_dir, tmp_path):
        scorecard = evaluate(registry=registry, soak_dir=soak_dir)
        path = write_snapshot(scorecard, corpus_dir=tmp_path)
        assert path.exists()
        assert path.name.startswith("omega-status-")
        assert path.suffix == ".json"

    def test_snapshot_content(self, registry, soak_dir, tmp_path):
        scorecard = evaluate(registry=registry, soak_dir=soak_dir)
        path = write_snapshot(scorecard, corpus_dir=tmp_path)
        data = json.loads(path.read_text())
        assert data["score"] == 5
        assert data["total"] == 17
        assert len(data["criteria"]) == 17

    def test_creates_omega_dir(self, registry, soak_dir, tmp_path):
        scorecard = evaluate(registry=registry, soak_dir=soak_dir)
        write_snapshot(scorecard, corpus_dir=tmp_path)
        assert (tmp_path / "data" / "omega").is_dir()

    def test_diff_no_previous(self, registry, soak_dir, tmp_path):
        scorecard = evaluate(registry=registry, soak_dir=soak_dir)
        changes = diff_snapshots(scorecard, corpus_dir=tmp_path)
        assert any("No previous" in c for c in changes)

    def test_diff_detects_change(self, registry, registry_with_revenue, soak_dir, tmp_path):
        # Write snapshot with no revenue
        sc1 = evaluate(registry=registry, soak_dir=soak_dir)
        write_snapshot(sc1, corpus_dir=tmp_path)

        # Evaluate with revenue → score changes
        sc2 = evaluate(registry=registry_with_revenue, soak_dir=soak_dir)
        changes = diff_snapshots(sc2, corpus_dir=tmp_path)
        assert any("Score changed" in c for c in changes)

    def test_diff_no_change(self, registry, soak_dir, tmp_path):
        scorecard = evaluate(registry=registry, soak_dir=soak_dir)
        write_snapshot(scorecard, corpus_dir=tmp_path)
        changes = diff_snapshots(scorecard, corpus_dir=tmp_path)
        assert any("No changes" in c for c in changes)
