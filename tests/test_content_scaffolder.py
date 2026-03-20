"""Tests for content pipeline scaffolder."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from organvm_engine.content.scaffolder import scaffold_post


def test_scaffold_creates_directory(tmp_path: Path):
    result = scaffold_post(tmp_path, "my-post")
    assert result.is_dir()
    assert result.name.endswith("-my-post")


def test_scaffold_creates_meta_yaml(tmp_path: Path):
    result = scaffold_post(tmp_path, "test-post", title="Test Post", hook="The hook")
    meta_path = result / "meta.yaml"
    assert meta_path.exists()
    data = yaml.safe_load(meta_path.read_text())
    assert data["title"] == "Test Post"
    assert data["slug"] == "test-post"
    assert data["hook"] == "The hook"
    assert data["status"] == "draft"


def test_scaffold_creates_placeholder_files(tmp_path: Path):
    result = scaffold_post(tmp_path, "test-post")
    assert (result / "linkedin.md").exists()
    assert (result / "full.md").exists()


def test_scaffold_dry_run_creates_nothing(tmp_path: Path):
    result = scaffold_post(tmp_path, "dry-run-post", dry_run=True)
    assert not result.exists()


def test_scaffold_raises_on_existing_directory(tmp_path: Path):
    scaffold_post(tmp_path, "duplicate")
    with pytest.raises(ValueError, match="already exists"):
        scaffold_post(tmp_path, "duplicate")


def test_scaffold_creates_base_dir_if_missing(tmp_path: Path):
    content_dir = tmp_path / "nested" / "content" / "posts"
    result = scaffold_post(content_dir, "new-post")
    assert result.is_dir()
    assert content_dir.is_dir()


def test_scaffold_includes_session_id(tmp_path: Path):
    result = scaffold_post(tmp_path, "with-session", session_id="abc123")
    data = yaml.safe_load((result / "meta.yaml").read_text())
    assert data["source_session"] == "abc123"


def test_scaffold_meta_has_distribution_block(tmp_path: Path):
    result = scaffold_post(tmp_path, "distrib")
    data = yaml.safe_load((result / "meta.yaml").read_text())
    assert "linkedin" in data["distribution"]
    assert "portfolio" in data["distribution"]
    assert data["distribution"]["linkedin"]["posted"] is False
