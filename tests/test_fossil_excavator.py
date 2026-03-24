"""Tests for the git history excavator."""

import subprocess

import pytest

from organvm_engine.fossil.excavator import (
    detect_organ_from_path,
    excavate_repo,
    parse_commit_type,
    parse_numstat,
)
from organvm_engine.fossil.stratum import Archetype, Provenance


def test_parse_commit_type():
    assert parse_commit_type("feat: add something") == "feat"
    assert parse_commit_type("fix: resolve bug") == "fix"
    assert parse_commit_type("chore(deps): bump version") == "chore"
    assert parse_commit_type("Merge pull request #1") == "merge"
    assert parse_commit_type("onnwards+upwards;") == ""


def test_parse_numstat():
    lines = "3\t1\tsrc/foo.py\n10\t0\tsrc/bar.py\n"
    files, ins, dels = parse_numstat(lines)
    assert files == 2
    assert ins == 13
    assert dels == 1


def test_parse_numstat_empty():
    files, ins, dels = parse_numstat("")
    assert files == 0
    assert ins == 0
    assert dels == 0


def test_detect_organ_from_path(tmp_path):
    organ_dir = tmp_path / "organvm-i-theoria" / "some-repo"
    organ_dir.mkdir(parents=True)
    result = detect_organ_from_path(organ_dir, tmp_path)
    assert result == "I"


def test_detect_organ_meta(tmp_path):
    organ_dir = tmp_path / "meta-organvm" / "organvm-engine"
    organ_dir.mkdir(parents=True)
    result = detect_organ_from_path(organ_dir, tmp_path)
    assert result == "META"


def test_detect_organ_liminal(tmp_path):
    organ_dir = tmp_path / "4444J99" / "portfolio"
    organ_dir.mkdir(parents=True)
    result = detect_organ_from_path(organ_dir, tmp_path)
    assert result == "LIMINAL"


@pytest.fixture
def fixture_repo(tmp_path):
    """Create a tiny git repo with 3 commits for testing."""
    repo = tmp_path / "organvm-i-theoria" / "test-repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=False)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=False)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=False)

    (repo / "foo.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=False)
    subprocess.run(["git", "commit", "-m", "feat: initial"], cwd=repo, capture_output=True, check=False)

    (repo / "foo.py").write_text("x = 2\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=False)
    subprocess.run(["git", "commit", "-m", "fix: correct value"], cwd=repo, capture_output=True, check=False)

    (repo / "bar.py").write_text("y = 1\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=False)
    subprocess.run(["git", "commit", "-m", "yolo"], cwd=repo, capture_output=True, check=False)

    return repo


def test_excavate_repo(fixture_repo, tmp_path):
    records = list(excavate_repo(fixture_repo, workspace_root=tmp_path))
    assert len(records) == 3
    assert all(r.provenance == Provenance.RECONSTRUCTED for r in records)
    assert records[0].timestamp <= records[1].timestamp <= records[2].timestamp
    assert all(r.organ == "I" for r in records)
    assert all(len(r.archetypes) >= 1 for r in records)

    yolo = [r for r in records if "yolo" in r.message]
    assert len(yolo) == 1
    assert yolo[0].archetypes[0] == Archetype.TRICKSTER
