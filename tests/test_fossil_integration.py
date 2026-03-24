"""Integration test: excavate a fixture workspace and verify the full pipeline."""

import subprocess

import pytest

from organvm_engine.fossil.excavator import excavate_repo
from organvm_engine.fossil.stratum import (
    Archetype,
    compute_record_hash,
    deserialize_record,
    serialize_record,
)


@pytest.fixture
def mini_workspace(tmp_path):
    """Create a workspace with 2 repos in different organs."""
    # ORGAN-I repo
    repo1 = tmp_path / "organvm-i-theoria" / "test-theory"
    repo1.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo1, capture_output=True, check=False)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo1, capture_output=True, check=False)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo1, capture_output=True, check=False)
    (repo1 / "a.py").write_text("x=1\n")
    subprocess.run(["git", "add", "."], cwd=repo1, capture_output=True, check=False)
    subprocess.run(["git", "commit", "-m", "feat: initial theory"], cwd=repo1, capture_output=True, check=False)

    # META repo
    repo2 = tmp_path / "meta-organvm" / "test-engine"
    repo2.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo2, capture_output=True, check=False)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo2, capture_output=True, check=False)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo2, capture_output=True, check=False)
    (repo2 / "b.py").write_text("y=1\n")
    subprocess.run(["git", "add", "."], cwd=repo2, capture_output=True, check=False)
    subprocess.run(["git", "commit", "-m", "feat: governance state machine"], cwd=repo2, capture_output=True, check=False)
    (repo2 / "b.py").write_text("y=2\n")
    subprocess.run(["git", "add", "."], cwd=repo2, capture_output=True, check=False)
    subprocess.run(["git", "commit", "-m", "fix: lint errors"], cwd=repo2, capture_output=True, check=False)

    return tmp_path


def test_full_excavation_pipeline(mini_workspace):
    """Excavate 2 repos, verify records, hash-link, serialize/deserialize."""
    all_records = []

    for git_dir in sorted(mini_workspace.rglob(".git")):
        if not git_dir.is_dir():
            continue
        repo_path = git_dir.parent
        records = list(excavate_repo(repo_path, workspace_root=mini_workspace))
        all_records.extend(records)

    # Should have 3 commits total (1 + 2)
    assert len(all_records) == 3

    # Sort chronologically and hash-link
    all_records.sort(key=lambda r: r.timestamp)
    prev_hash = ""
    for rec in all_records:
        rec.prev_hash = prev_hash
        prev_hash = compute_record_hash(rec)

    # Verify chain integrity
    prev = ""
    for rec in all_records:
        assert rec.prev_hash == prev
        prev = compute_record_hash(rec)

    # Verify organs detected
    organs = {r.organ for r in all_records}
    assert "I" in organs
    assert "META" in organs

    # Verify serialize/deserialize roundtrip
    for rec in all_records:
        json_str = serialize_record(rec)
        restored = deserialize_record(json_str)
        assert restored.commit_sha == rec.commit_sha
        assert restored.archetypes == rec.archetypes

    # The "fix: lint errors" commit should be Shadow
    lint_rec = [r for r in all_records if "lint" in r.message]
    assert len(lint_rec) == 1
    assert lint_rec[0].archetypes[0] == Archetype.SHADOW
