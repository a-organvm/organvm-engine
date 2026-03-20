"""Weekly content production cadence checker."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from organvm_engine.content.reader import ContentPost


@dataclass
class CadenceReport:
    """Weekly content cadence health report."""

    posts_this_week: list[ContentPost] = field(default_factory=list)
    weeks_since_last_post: int = 0
    streak: int = 0
    total_posts: int = 0
    published_count: int = 0
    draft_count: int = 0
    archived_count: int = 0
    last_post_date: str | None = None


def _iso_week(d: date) -> tuple[int, int]:
    """Return (ISO year, ISO week number) for a date."""
    cal = d.isocalendar()
    return (cal[0], cal[1])


def check_cadence(posts: list[ContentPost]) -> CadenceReport:
    """Evaluate weekly content production cadence.

    Uses ISO week boundaries (Monday-Sunday).
    Streak counts consecutive weeks (going backwards from current)
    with >= 1 post of any status.
    """
    if not posts:
        return CadenceReport()

    today = date.today()
    current_week = _iso_week(today)

    # Parse post dates
    dated: list[tuple[date, ContentPost]] = []
    for p in posts:
        try:
            d = date.fromisoformat(p.date)
            dated.append((d, p))
        except (ValueError, TypeError):
            continue

    if not dated:
        return CadenceReport(total_posts=len(posts))

    dated.sort(key=lambda x: x[0], reverse=True)

    # Posts this week
    this_week = [p for d, p in dated if _iso_week(d) == current_week]

    # Last post date
    last_date = dated[0][0]
    weeks_since = (today - last_date).days // 7

    # Streak: count consecutive weeks backwards from current
    weeks_with_posts: set[tuple[int, int]] = set()
    for d, _ in dated:
        weeks_with_posts.add(_iso_week(d))

    streak = 0
    check_date = today
    while True:
        week = _iso_week(check_date)
        if week in weeks_with_posts:
            streak += 1
            check_date -= timedelta(weeks=1)
        else:
            break

    # Status counts
    status_counts = {"draft": 0, "published": 0, "archived": 0}
    for p in posts:
        key = p.status if p.status in status_counts else "draft"
        status_counts[key] += 1

    return CadenceReport(
        posts_this_week=this_week,
        weeks_since_last_post=weeks_since,
        streak=streak,
        total_posts=len(posts),
        published_count=status_counts["published"],
        draft_count=status_counts["draft"],
        archived_count=status_counts["archived"],
        last_post_date=last_date.isoformat(),
    )
