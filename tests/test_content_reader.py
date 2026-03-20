"""Tests for content pipeline reader."""

from __future__ import annotations

from pathlib import Path

import yaml

from organvm_engine.content.reader import ContentPost, discover_posts, filter_posts
from organvm_engine.paths import PathConfig


def test_content_dir_resolves_relative_to_corpus(tmp_path: Path):
    """content_dir should be corpus parent / praxis-perpetua / content-pipeline / posts."""
    corpus = tmp_path / "organvm-corpvs-testamentvm"
    corpus.mkdir()
    cfg = PathConfig(corpus_root=corpus)
    expected = tmp_path / "praxis-perpetua" / "content-pipeline" / "posts"
    assert cfg.content_dir() == expected


def _make_post(tmp_path: Path, slug: str, date: str = "2026-03-19",
               status: str = "draft", hook: str = "test hook",
               tags: list[str] | None = None) -> Path:
    """Helper: create a post directory with minimal meta.yaml."""
    post_dir = tmp_path / f"{date}-{slug}"
    post_dir.mkdir(parents=True)
    meta = {
        "title": slug.replace("-", " ").title(),
        "date": date,
        "slug": slug,
        "hook": hook,
        "source_session": "",
        "context": "",
        "status": status,
        "distribution": {},
        "engagement": {},
        "tags": tags or [],
        "redacted_items": [],
    }
    (post_dir / "meta.yaml").write_text(yaml.dump(meta, default_flow_style=False))
    return post_dir


def test_discover_posts_finds_valid_posts(tmp_path: Path):
    _make_post(tmp_path, "alpha", date="2026-03-10")
    _make_post(tmp_path, "beta", date="2026-03-15")
    posts = discover_posts(tmp_path)
    assert len(posts) == 2
    assert posts[0].slug == "beta"
    assert posts[1].slug == "alpha"


def test_discover_posts_skips_invalid_dirs(tmp_path: Path):
    _make_post(tmp_path, "valid", date="2026-03-19")
    (tmp_path / "2026-03-18-no-meta").mkdir()
    (tmp_path / "not-a-post").mkdir()
    posts = discover_posts(tmp_path)
    assert len(posts) == 1
    assert posts[0].slug == "valid"


def test_discover_posts_empty_dir(tmp_path: Path):
    posts = discover_posts(tmp_path)
    assert posts == []


def test_discover_posts_nonexistent_dir(tmp_path: Path):
    posts = discover_posts(tmp_path / "nope")
    assert posts == []


def test_discover_posts_sets_directory_field(tmp_path: Path):
    post_dir = _make_post(tmp_path, "check-dir", date="2026-03-19")
    posts = discover_posts(tmp_path)
    assert posts[0].directory == post_dir


def test_discover_posts_parses_all_fields(tmp_path: Path):
    _make_post(tmp_path, "full", date="2026-03-19",
               status="published", hook="the hook",
               tags=["tag1", "tag2"])
    posts = discover_posts(tmp_path)
    p = posts[0]
    assert p.slug == "full"
    assert p.date == "2026-03-19"
    assert p.status == "published"
    assert p.hook == "the hook"
    assert p.tags == ["tag1", "tag2"]


def test_filter_posts_by_status(tmp_path: Path):
    _make_post(tmp_path, "a", date="2026-03-10", status="draft")
    _make_post(tmp_path, "b", date="2026-03-11", status="published")
    _make_post(tmp_path, "c", date="2026-03-12", status="draft")
    posts = discover_posts(tmp_path)
    drafts = filter_posts(posts, status="draft")
    assert len(drafts) == 2
    assert all(p.status == "draft" for p in drafts)


def test_filter_posts_by_tag(tmp_path: Path):
    _make_post(tmp_path, "a", date="2026-03-10", tags=["art"])
    _make_post(tmp_path, "b", date="2026-03-11", tags=["tech", "art"])
    _make_post(tmp_path, "c", date="2026-03-12", tags=["tech"])
    posts = discover_posts(tmp_path)
    art = filter_posts(posts, tag="art")
    assert len(art) == 2


def test_filter_posts_no_match(tmp_path: Path):
    _make_post(tmp_path, "a", date="2026-03-10", status="draft")
    posts = discover_posts(tmp_path)
    result = filter_posts(posts, status="archived")
    assert result == []
