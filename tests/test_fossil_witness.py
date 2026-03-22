"""Tests for the Witness — real-time capture layer."""

from __future__ import annotations

import subprocess
from pathlib import Path

from organvm_engine.fossil.stratum import Provenance
from organvm_engine.fossil.witness import (
    generate_hook_script,
    install_hooks,
    record_witnessed_commit,
    witness_status,
)


def test_generate_hook_script(tmp_path: Path) -> None:
    script = generate_hook_script(tmp_path / "fossil-record.jsonl", tmp_path)
    assert "#!/usr/bin/env bash" in script
    assert "set -euo pipefail" in script
    assert "organvm" in script or "fossil" in script
    # The script IS the hook; it should not reference "post-commit" as a filename
    assert "post-commit" not in script


def test_generate_hook_script_contains_git_log(tmp_path: Path) -> None:
    script = generate_hook_script(tmp_path / "fossil-record.jsonl", tmp_path)
    assert "git log" in script


def test_record_witnessed_commit(tmp_path: Path) -> None:
    # Create a fixture repo with one commit
    repo = tmp_path / "meta-organvm" / "test-repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "T"], cwd=repo, capture_output=True, check=True,
    )
    (repo / "a.py").write_text("x=1\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: initial"], cwd=repo, capture_output=True, check=True,
    )

    fossil_path = tmp_path / "fossil-record.jsonl"
    record = record_witnessed_commit(repo, tmp_path, fossil_path)
    assert record is not None
    assert record.provenance == Provenance.WITNESSED
    assert record.organ == "META"
    assert fossil_path.exists()

    # Verify the JSONL line was written
    content = fossil_path.read_text().strip()
    assert len(content.splitlines()) == 1


def test_record_witnessed_commit_hash_links(tmp_path: Path) -> None:
    """Second witnessed commit should hash-link to the first."""
    repo = tmp_path / "meta-organvm" / "test-repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "T"], cwd=repo, capture_output=True, check=True,
    )
    (repo / "a.py").write_text("x=1\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: first"], cwd=repo, capture_output=True, check=True,
    )

    fossil_path = tmp_path / "fossil-record.jsonl"
    rec1 = record_witnessed_commit(repo, tmp_path, fossil_path)
    assert rec1 is not None
    assert rec1.prev_hash == ""

    # Second commit
    (repo / "b.py").write_text("y=2\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "fix: second"], cwd=repo, capture_output=True, check=True,
    )

    rec2 = record_witnessed_commit(repo, tmp_path, fossil_path)
    assert rec2 is not None
    assert rec2.prev_hash != ""
    assert len(fossil_path.read_text().strip().splitlines()) == 2


def test_record_witnessed_commit_no_repo(tmp_path: Path) -> None:
    """Non-git directory returns None."""
    result = record_witnessed_commit(tmp_path / "nope", tmp_path, tmp_path / "f.jsonl")
    assert result is None


def test_install_hooks_dry_run(tmp_path: Path) -> None:
    repo = tmp_path / "meta-organvm" / "test-repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)

    result = install_hooks(tmp_path, tmp_path / "fossil.jsonl", dry_run=True)
    assert isinstance(result, list)
    # Dry run: no files written
    hook_path = repo / ".git" / "hooks" / "post-commit"
    assert not hook_path.exists()


def test_install_hooks_write(tmp_path: Path) -> None:
    repo = tmp_path / "meta-organvm" / "test-repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)

    result = install_hooks(tmp_path, tmp_path / "fossil.jsonl", dry_run=False)
    assert len(result) >= 1
    hook_path = repo / ".git" / "hooks" / "post-commit"
    assert hook_path.exists()
    content = hook_path.read_text()
    assert "organvm" in content


def test_install_hooks_respects_existing(tmp_path: Path) -> None:
    """If a post-commit hook exists, our script is appended rather than overwriting."""
    repo = tmp_path / "meta-organvm" / "test-repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)

    hook_dir = repo / ".git" / "hooks"
    hook_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hook_dir / "post-commit"
    hook_path.write_text("#!/bin/bash\necho existing\n")

    install_hooks(tmp_path, tmp_path / "fossil.jsonl", dry_run=False)
    content = hook_path.read_text()
    assert "echo existing" in content
    assert "organvm" in content


def test_witness_status_empty(tmp_path: Path) -> None:
    result = witness_status(tmp_path)
    assert result["total_repos"] == 0
    assert result["witnessed"] == 0
    assert result["dark"] == 0


def test_witness_status_with_repos(tmp_path: Path) -> None:
    repo = tmp_path / "meta-organvm" / "test-repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)

    result = witness_status(tmp_path)
    assert result["total_repos"] == 1
    assert result["dark"] == 1
    assert result["witnessed"] == 0
    assert "repos" in result
