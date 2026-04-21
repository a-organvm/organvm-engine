"""Tests for contribution engine — discovery, status, and backflow pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from organvm_engine.contrib.backflow import (
    BackflowSignal,
    SignalType,
    SIGNAL_ORGAN_MAP,
    classify_contribution,
    generate_backflow_report,
    write_backflow_manifest,
)
from organvm_engine.contrib.discover import ContribRepo, discover_contrib_repos
from organvm_engine.contrib.status import ContribStatus, PRState, check_pr_status


# ── Fixtures ──────────────────────────────────────────────


def _make_contrib_repo(
    tmp_path: Path,
    name: str = "contrib--grafana-k6",
    target_repo: str = "grafana/k6",
    target_pr: int | None = 42,
    organ_dir: str = "organvm-iv-taxis",
) -> Path:
    """Create a minimal contrib repo with seed.yaml."""
    org_dir = tmp_path / organ_dir
    org_dir.mkdir(exist_ok=True)
    repo_dir = org_dir / name
    repo_dir.mkdir()
    seed = {
        "schema_version": "1.0",
        "name": name,
        "organ": "IV",
        "tier": "contrib",
        "upstream": {
            "repo": target_repo,
            "pr": target_pr,
            "language": "go",
        },
        "description": f"Contribution to {target_repo}",
    }
    (repo_dir / "seed.yaml").write_text(yaml.dump(seed))
    return repo_dir


def _make_contrib_status(
    state: PRState = PRState.MERGED,
    title: str = "feat: add custom metric support",
    language: str | None = "go",
    target_pr: int = 42,
) -> ContribStatus:
    repo = ContribRepo(
        name="contrib--grafana-k6",
        path=Path("/fake"),
        target_repo="grafana/k6",
        target_pr=target_pr,
        language=language,
    )
    return ContribStatus(
        repo=repo,
        state=state,
        title=title,
        review_decision="APPROVED" if state == PRState.MERGED else "",
    )


# ── Discovery tests ──────────────────────────────────────


class TestDiscoverContribRepos:
    def test_finds_contrib_repos(self, tmp_path: Path) -> None:
        _make_contrib_repo(tmp_path)
        with patch("organvm_engine.contrib.discover.workspace_root", return_value=tmp_path), \
             patch("organvm_engine.contrib.discover.organ_org_dirs",
                   return_value=["organvm-iv-taxis"]):
            repos = discover_contrib_repos(workspace=tmp_path)
        assert len(repos) == 1
        assert repos[0].name == "contrib--grafana-k6"
        assert repos[0].target_repo == "grafana/k6"

    def test_ignores_non_contrib_repos(self, tmp_path: Path) -> None:
        org_dir = tmp_path / "organvm-iv-taxis"
        org_dir.mkdir()
        regular = org_dir / "regular-repo"
        regular.mkdir()
        (regular / "seed.yaml").write_text(yaml.dump({"name": "regular"}))
        with patch("organvm_engine.contrib.discover.organ_org_dirs",
                   return_value=["organvm-iv-taxis"]):
            repos = discover_contrib_repos(workspace=tmp_path)
        assert len(repos) == 0

    def test_skips_repos_without_seed(self, tmp_path: Path) -> None:
        org_dir = tmp_path / "organvm-iv-taxis"
        org_dir.mkdir()
        (org_dir / "contrib--no-seed").mkdir()
        with patch("organvm_engine.contrib.discover.organ_org_dirs",
                   return_value=["organvm-iv-taxis"]):
            repos = discover_contrib_repos(workspace=tmp_path)
        assert len(repos) == 0

    def test_sorted_by_name(self, tmp_path: Path) -> None:
        _make_contrib_repo(tmp_path, name="contrib--z-repo", target_repo="z/repo")
        _make_contrib_repo(tmp_path, name="contrib--a-repo", target_repo="a/repo")
        with patch("organvm_engine.contrib.discover.organ_org_dirs",
                   return_value=["organvm-iv-taxis"]):
            repos = discover_contrib_repos(workspace=tmp_path)
        assert repos[0].name == "contrib--a-repo"
        assert repos[1].name == "contrib--z-repo"


class TestContribRepo:
    def test_pr_url(self) -> None:
        repo = ContribRepo(
            name="test", path=Path("/"), target_repo="owner/repo", target_pr=99,
        )
        assert repo.pr_url == "https://github.com/owner/repo/pull/99"

    def test_pr_url_none_when_no_pr(self) -> None:
        repo = ContribRepo(
            name="test", path=Path("/"), target_repo="owner/repo",
        )
        assert repo.pr_url is None

    def test_target_owner_repo(self) -> None:
        repo = ContribRepo(
            name="test", path=Path("/"), target_repo="grafana/k6",
        )
        assert repo.target_owner_repo == "grafana/k6"


# ── Status tests ──────────────────────────────────────────


class TestContribStatus:
    def test_is_actionable_changes_requested(self) -> None:
        status = _make_contrib_status(state=PRState.OPEN)
        status.review_decision = "CHANGES_REQUESTED"
        assert status.is_actionable is True

    def test_not_actionable_when_merged(self) -> None:
        status = _make_contrib_status(state=PRState.MERGED)
        assert status.is_actionable is False

    def test_is_landed(self) -> None:
        status = _make_contrib_status(state=PRState.MERGED)
        assert status.is_landed is True

    def test_not_landed_when_open(self) -> None:
        status = _make_contrib_status(state=PRState.OPEN)
        assert status.is_landed is False


class TestCheckPRStatus:
    def test_returns_no_pr_when_no_pr_number(self) -> None:
        repo = ContribRepo(
            name="test", path=Path("/"), target_repo="o/r", target_pr=None,
        )
        status = check_pr_status(repo)
        assert status.state == PRState.NO_PR

    def test_returns_unknown_on_gh_failure(self) -> None:
        repo = ContribRepo(
            name="test", path=Path("/"), target_repo="o/r", target_pr=1,
        )
        with patch("subprocess.run", side_effect=FileNotFoundError):
            status = check_pr_status(repo)
        assert status.state == PRState.UNKNOWN


# ── Backflow tests ────────────────────────────────────────


class TestSignalOrganMap:
    def test_all_signal_types_mapped(self) -> None:
        for st in SignalType:
            assert st in SIGNAL_ORGAN_MAP


class TestClassifyContribution:
    def test_merged_generates_minimum_4_signals(self) -> None:
        status = _make_contrib_status(state=PRState.MERGED)
        signals = classify_contribution(status)
        types = {s.signal_type for s in signals}
        assert SignalType.COMMUNITY in types
        assert SignalType.DISTRIBUTION in types
        assert SignalType.SHIPPED_CODE in types
        assert SignalType.NARRATIVE in types
        assert len(signals) >= 4

    def test_open_generates_community_and_distribution(self) -> None:
        status = _make_contrib_status(state=PRState.OPEN)
        signals = classify_contribution(status)
        types = {s.signal_type for s in signals}
        assert SignalType.COMMUNITY in types
        assert SignalType.DISTRIBUTION in types
        assert SignalType.SHIPPED_CODE not in types

    def test_closed_generates_only_community(self) -> None:
        status = _make_contrib_status(state=PRState.CLOSED)
        signals = classify_contribution(status)
        types = {s.signal_type for s in signals}
        assert SignalType.COMMUNITY in types
        assert SignalType.DISTRIBUTION not in types

    def test_formal_language_adds_theory_signal(self) -> None:
        status = _make_contrib_status(state=PRState.OPEN, language="haskell")
        signals = classify_contribution(status)
        types = {s.signal_type for s in signals}
        assert SignalType.THEORY in types

    def test_governance_keyword_adds_orchestration(self) -> None:
        status = _make_contrib_status(
            state=PRState.OPEN,
            title="fix: governance workflow validation",
        )
        signals = classify_contribution(status)
        types = {s.signal_type for s in signals}
        assert SignalType.ORCHESTRATION in types

    def test_signal_destinations_match_organ_map(self) -> None:
        status = _make_contrib_status(state=PRState.MERGED)
        signals = classify_contribution(status)
        for signal in signals:
            expected_organ = SIGNAL_ORGAN_MAP[signal.signal_type]
            assert signal.destination_organ == expected_organ


class TestGenerateBackflowReport:
    def test_groups_by_organ(self) -> None:
        statuses = [_make_contrib_status(state=PRState.MERGED)]
        report = generate_backflow_report(statuses)
        assert len(report["III"]) >= 1  # shipped_code
        assert len(report["VI"]) >= 1  # community

    def test_all_organs_present(self) -> None:
        report = generate_backflow_report([])
        for organ in ("I", "II", "III", "IV", "V", "VI", "VII"):
            assert organ in report


class TestWriteBackflowManifest:
    def test_writes_yaml_file(self, tmp_path: Path) -> None:
        statuses = [_make_contrib_status(state=PRState.MERGED)]
        report = generate_backflow_report(statuses)
        path = write_backflow_manifest(report, tmp_path)
        assert path.exists()
        assert path.name == "backflow-manifest.yaml"

    def test_manifest_contains_signals(self, tmp_path: Path) -> None:
        statuses = [_make_contrib_status(state=PRState.MERGED)]
        report = generate_backflow_report(statuses)
        path = write_backflow_manifest(report, tmp_path)
        data = yaml.safe_load(path.read_text())
        assert data["total_signals"] >= 4
        assert "generated_at" in data
