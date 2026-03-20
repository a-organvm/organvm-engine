"""Parse and discover content pipeline posts."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Directory name pattern: YYYY-MM-DD-{slug}
_POST_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-.+$")

_log = logging.getLogger(__name__)


@dataclass
class ContentPost:
    """A content pipeline post parsed from meta.yaml."""

    slug: str
    title: str
    date: str
    hook: str
    status: str
    source_session: str
    context: str
    tags: list[str]
    distribution: dict[str, Any]
    engagement: dict[str, Any]
    redacted_items: list[str]
    directory: Path


def discover_posts(content_dir: Path) -> list[ContentPost]:
    """Find all post directories matching YYYY-MM-DD-{slug}/ pattern.

    Reads meta.yaml from each, returns sorted by date descending.
    Skips directories without valid meta.yaml (logs warning, continues).
    Returns empty list if content_dir does not exist.
    """
    if not content_dir.is_dir():
        return []

    posts: list[ContentPost] = []
    for child in content_dir.iterdir():
        if not child.is_dir():
            continue
        if not _POST_DIR_RE.match(child.name):
            continue
        meta_path = child / "meta.yaml"
        if not meta_path.exists():
            _log.warning("Post directory %s has no meta.yaml, skipping", child.name)
            continue
        try:
            with meta_path.open() as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                _log.warning("meta.yaml in %s is not a mapping, skipping", child.name)
                continue
            posts.append(ContentPost(
                slug=str(data.get("slug", child.name.split("-", 3)[-1])),
                title=str(data.get("title", "")),
                date=str(data.get("date", "")),
                hook=str(data.get("hook", "")),
                status=str(data.get("status", "draft")),
                source_session=str(data.get("source_session", "")),
                context=str(data.get("context", "")),
                tags=data.get("tags") or [],
                distribution=data.get("distribution") or {},
                engagement=data.get("engagement") or {},
                redacted_items=data.get("redacted_items") or [],
                directory=child,
            ))
        except (yaml.YAMLError, OSError) as exc:
            _log.warning("Error reading %s: %s", meta_path, exc)
            continue

    posts.sort(key=lambda p: p.date, reverse=True)
    return posts


def filter_posts(
    posts: list[ContentPost],
    status: str | None = None,
    tag: str | None = None,
) -> list[ContentPost]:
    """Filter posts by status and/or tag."""
    result = posts
    if status:
        result = [p for p in result if p.status == status]
    if tag:
        result = [p for p in result if tag in p.tags]
    return result
