"""Scaffold new content pipeline post directories."""

from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

import yaml

_META_TEMPLATE = {
    "title": "",
    "date": "",
    "slug": "",
    "hook": "",
    "source_session": "",
    "context": "",
    "status": "draft",
    "distribution": {
        "linkedin": {
            "version": "redacted",
            "file": "linkedin.md",
            "posted": False,
            "url": None,
        },
        "portfolio": {
            "version": "unredacted",
            "file": "full.md",
            "posted": False,
            "url": None,
        },
    },
    "engagement": {
        "linkedin": {
            "impressions": None,
            "reactions": None,
            "comments": None,
            "reposts": None,
        },
        "portfolio": {
            "views": None,
        },
    },
    "tags": [],
    "redacted_items": [],
}


def scaffold_post(
    content_dir: Path,
    slug: str,
    title: str | None = None,
    hook: str | None = None,
    session_id: str | None = None,
    dry_run: bool = False,
) -> Path:
    """Create a new post directory with template files.

    Creates: YYYY-MM-DD-{slug}/
        - meta.yaml (template with provided values)
        - linkedin.md (empty, redacted version placeholder)
        - full.md (empty, unredacted version placeholder)

    Returns path to created (or would-be) directory.
    Raises ValueError if directory already exists.
    Creates content_dir if it does not exist.
    """
    today = date.today().isoformat()
    dir_name = f"{today}-{slug}"
    post_dir = content_dir / dir_name

    if post_dir.exists():
        raise ValueError(f"Post directory already exists: {post_dir}")

    if dry_run:
        return post_dir

    content_dir.mkdir(parents=True, exist_ok=True)
    post_dir.mkdir()

    meta = copy.deepcopy(_META_TEMPLATE)
    meta["title"] = title or slug.replace("-", " ").title()
    meta["date"] = today
    meta["slug"] = slug
    meta["hook"] = hook or ""
    meta["source_session"] = session_id or ""

    with (post_dir / "meta.yaml").open("w") as f:
        yaml.dump(meta, f, default_flow_style=False, sort_keys=False)

    (post_dir / "linkedin.md").touch()
    (post_dir / "full.md").touch()

    return post_dir
