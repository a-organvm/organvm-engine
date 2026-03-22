"""Narrator — Jungian chronicle generator for fossil epochs.

Reads fossil records, computes statistics per epoch, and generates
oracular markdown narratives using archetype-specific vocabulary.
The system is "the organism"; archetypes are active forces that
stir, surface, structure, and integrate.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from organvm_engine.fossil.epochs import DECLARED_EPOCHS, Epoch
from organvm_engine.fossil.stratum import Archetype, FossilRecord

# ── Archetype vocabulary ──────────────────────────────────────────────

ARCHETYPE_VOICE: dict[Archetype, dict[str, Any]] = {
    Archetype.SHADOW: {
        "verbs": ["stirs", "surfaces", "demands acknowledgment", "confronts", "rises from"],
        "subjects": ["hidden debt", "the neglected", "what was avoided", "suppressed warnings"],
        "opening": "The Shadow {verb} in {organ}",
        "presence": "the Shadow appears \u2014 {detail}",
    },
    Archetype.ANIMA: {
        "verbs": [
            "seizes",
            "flows through",
            "emerges in",
            "dreams into being",
            "breathes life into",
        ],
        "subjects": ["creative emergence", "the unshaped", "raw material", "vision"],
        "opening": "The Anima {verb} the organism",
        "presence": "the Anima moves \u2014 {detail}",
    },
    Archetype.ANIMUS: {
        "verbs": ["structures", "formalizes", "orders", "codifies", "hardens"],
        "subjects": ["architecture", "the blueprint", "formal proof", "the schema"],
        "opening": "The Animus {verb} what was fluid",
        "presence": "the Animus asserts \u2014 {detail}",
    },
    Archetype.SELF: {
        "verbs": ["observes", "reflects", "witnesses", "turns inward", "contemplates"],
        "subjects": ["its own nature", "the mirror", "what it has become", "the pattern"],
        "opening": "The Self {verb}",
        "presence": "the Self recognizes \u2014 {detail}",
    },
    Archetype.TRICKSTER: {
        "verbs": ["disrupts", "slips through", "upends", "refuses", "laughs at"],
        "subjects": ["convention", "the boundary", "discipline", "the expected"],
        "opening": "The Trickster {verb} the order",
        "presence": "the Trickster marks the boundary \u2014 {detail}",
    },
    Archetype.MOTHER: {
        "verbs": ["nurtures", "builds", "sustains", "shelters", "provides for"],
        "subjects": ["the foundation", "infrastructure", "the environment", "the ground"],
        "opening": "The Mother {verb} the organism",
        "presence": "the Mother tends \u2014 {detail}",
    },
    Archetype.FATHER: {
        "verbs": ["decrees", "enforces", "gates", "constrains", "commands"],
        "subjects": ["the law", "promotion gates", "governance rules", "the boundary"],
        "opening": "The Father {verb}",
        "presence": "the Father speaks \u2014 {detail}",
    },
    Archetype.INDIVIDUATION: {
        "verbs": ["integrates", "synthesizes", "becomes", "reaches beyond", "unifies"],
        "subjects": ["the whole", "cross-organ flow", "the system itself", "completeness"],
        "opening": "Individuation {verb}",
        "presence": "the organism reaches toward wholeness \u2014 {detail}",
    },
}


# ── Data model ────────────────────────────────────────────────────────


@dataclass
class EpochStats:
    """Computed statistics for a single epoch."""

    epoch_id: str
    epoch_name: str
    start: date
    end: date
    commit_count: int
    repos_touched: list[str]
    organs_touched: list[str]
    archetype_counts: dict[Archetype, int]
    dominant_archetype: Archetype
    secondary_archetype: Archetype | None
    top_repos: list[tuple[str, int]]
    total_insertions: int
    total_deletions: int
    trickster_ratio: float
    authors: list[str]


# ── Statistics computation ────────────────────────────────────────────


def compute_epoch_stats(epoch: Epoch, records: list[FossilRecord]) -> EpochStats:
    """Compute aggregate statistics for records belonging to an epoch.

    Filters *records* to those whose ``epoch`` field matches ``epoch.id``,
    then computes archetype distributions, repo/organ sets, and volume totals.
    Returns a zeroed-out ``EpochStats`` if no matching records exist.
    """
    matched = [r for r in records if r.epoch == epoch.id]

    if not matched:
        return EpochStats(
            epoch_id=epoch.id,
            epoch_name=epoch.name,
            start=epoch.start,
            end=epoch.end,
            commit_count=0,
            repos_touched=[],
            organs_touched=[],
            archetype_counts={},
            dominant_archetype=epoch.dominant_archetype,
            secondary_archetype=None,
            top_repos=[],
            total_insertions=0,
            total_deletions=0,
            trickster_ratio=0.0,
            authors=[],
        )

    # Archetype distribution: primary archetype (first in list) per record
    primary_counts: Counter[Archetype] = Counter()
    for r in matched:
        if r.archetypes:
            primary_counts[r.archetypes[0]] += 1

    ranked = primary_counts.most_common()
    dominant = ranked[0][0] if ranked else epoch.dominant_archetype
    secondary = ranked[1][0] if len(ranked) > 1 else None

    # Repo frequency
    repo_counts: Counter[str] = Counter(r.repo for r in matched)
    top_repos = repo_counts.most_common(5)

    # Unique repos, organs, authors (sorted for determinism)
    repos_touched = sorted(set(r.repo for r in matched))
    organs_touched = sorted(set(r.organ for r in matched))
    authors = sorted(set(r.author for r in matched))

    total_ins = sum(r.insertions for r in matched)
    total_dels = sum(r.deletions for r in matched)

    trickster_count = primary_counts.get(Archetype.TRICKSTER, 0)
    trickster_ratio = trickster_count / len(matched)

    return EpochStats(
        epoch_id=epoch.id,
        epoch_name=epoch.name,
        start=epoch.start,
        end=epoch.end,
        commit_count=len(matched),
        repos_touched=repos_touched,
        organs_touched=organs_touched,
        archetype_counts=dict(primary_counts),
        dominant_archetype=dominant,
        secondary_archetype=secondary,
        top_repos=top_repos,
        total_insertions=total_ins,
        total_deletions=total_dels,
        trickster_ratio=trickster_ratio,
        authors=authors,
    )


# ── Narrative generation ──────────────────────────────────────────────


def _pick_verb(arch: Archetype, index: int = 0) -> str:
    """Select a verb from the archetype vocabulary, cycling by index."""
    verbs = ARCHETYPE_VOICE[arch]["verbs"]
    return verbs[index % len(verbs)]


def _pick_subject(arch: Archetype, index: int = 0) -> str:
    """Select a subject noun-phrase from the archetype vocabulary."""
    subjects = ARCHETYPE_VOICE[arch]["subjects"]
    return subjects[index % len(subjects)]


def _format_opening(arch: Archetype, stats: EpochStats) -> str:
    """Render the opening sentence for the dominant archetype."""
    template = ARCHETYPE_VOICE[arch]["opening"]
    verb = _pick_verb(arch, 0)

    # Provide organ context for templates that reference {organ}
    organ_str = ", ".join(stats.organs_touched[:3]) if stats.organs_touched else "the Work"

    return template.format(verb=verb, organ=organ_str)


def _format_presence(arch: Archetype, detail: str) -> str:
    """Render a presence sentence for a secondary archetype."""
    template = ARCHETYPE_VOICE[arch]["presence"]
    return template.format(detail=detail)


def _build_body_paragraph(stats: EpochStats) -> str:
    """Compose the descriptive body of the chronicle."""
    parts: list[str] = []

    # Volume and character
    if stats.commit_count == 1:
        parts.append("A single commit marks this epoch")
    elif stats.commit_count < 10:
        parts.append(
            f"In {stats.commit_count} deliberate acts, the Work advances",
        )
    elif stats.commit_count < 50:
        parts.append(
            f"Across {stats.commit_count} commits, the organism builds steadily",
        )
    else:
        parts.append(
            f"A torrent of {stats.commit_count} commits floods the record",
        )

    # Top repos
    if stats.top_repos:
        repo_phrases = []
        for repo_name, count in stats.top_repos[:3]:
            repo_phrases.append(f"*{repo_name}* ({count})")
        parts.append(
            "The labor concentrates in " + ", ".join(repo_phrases),
        )

    # Insertions/deletions as creative/destructive balance
    if stats.total_insertions > 0 or stats.total_deletions > 0:
        ratio = (
            stats.total_insertions / max(stats.total_deletions, 1)
        )
        if ratio > 10:
            parts.append(
                f"+{stats.total_insertions} lines conjured against only "
                f"-{stats.total_deletions} dissolved \u2014 creation overwhelms erasure",
            )
        elif ratio > 2:
            parts.append(
                f"+{stats.total_insertions} lines written, -{stats.total_deletions} removed "
                "\u2014 the organism grows more than it sheds",
            )
        else:
            parts.append(
                f"+{stats.total_insertions} lines added, -{stats.total_deletions} removed "
                "\u2014 a near-equilibrium of creation and destruction",
            )

    # Secondary archetype
    if stats.secondary_archetype:
        secondary = stats.secondary_archetype
        detail = _pick_subject(secondary, 1)
        presence = _format_presence(secondary, detail)
        parts.append(f"Alongside the dominant force, {presence}")

    return ". ".join(parts) + "."


def _build_trickster_note(stats: EpochStats) -> str:
    """Compose a Trickster note if the ratio exceeds the threshold."""
    if stats.trickster_ratio <= 0.10:
        return ""
    verb = _pick_verb(Archetype.TRICKSTER, 1)
    subject = _pick_subject(Archetype.TRICKSTER, 0)
    pct = int(stats.trickster_ratio * 100)
    return (
        f"The Trickster {verb} {subject} \u2014 "
        f"{pct}% of this epoch's commits defy conventional form."
    )


def _build_shadow_note(stats: EpochStats) -> str:
    """Compose a Shadow note if Shadow is among the top 3 archetypes."""
    ranked = sorted(stats.archetype_counts.items(), key=lambda x: x[1], reverse=True)
    top_3 = [arch for arch, _count in ranked[:3]]
    if Archetype.SHADOW not in top_3:
        return ""
    verb = _pick_verb(Archetype.SHADOW, 2)
    subject = _pick_subject(Archetype.SHADOW, 0)
    count = stats.archetype_counts.get(Archetype.SHADOW, 0)
    return (
        f"The Shadow {verb} \u2014 {subject} surfaces in "
        f"{count} commit{'s' if count != 1 else ''}, "
        "a reminder that what is ignored will return."
    )


def _build_closing(stats: EpochStats) -> str:
    """A sentence about what the epoch leaves for the next."""
    if stats.commit_count == 0:
        return "Silence. The organism waits."
    dominant = stats.dominant_archetype
    subject = _pick_subject(dominant, 2)
    return (
        f"What remains: {subject}. "
        f"The epoch closes with {stats.commit_count} marks in the record, "
        f"and the organism carries forward what it has become."
    )


def _build_archetype_table(stats: EpochStats) -> str:
    """Format archetype distribution as a markdown table."""
    if not stats.archetype_counts:
        return "| Archetype | Count |\n|-----------|-------|\n| (none) | 0 |"

    ranked = sorted(stats.archetype_counts.items(), key=lambda x: x[1], reverse=True)
    lines = ["| Archetype | Count |", "|-----------|-------|"]
    for arch, count in ranked:
        lines.append(f"| {arch.value.title()} | {count} |")
    return "\n".join(lines)


def generate_epoch_chronicle(stats: EpochStats, records: list[FossilRecord]) -> str:
    """Produce a markdown chronicle for one epoch.

    Returns a complete markdown document with a Jungian narrative section
    and a data summary.
    """
    # Header
    n_repos = len(stats.repos_touched)
    dominant_label = stats.dominant_archetype.value.title()
    header = (
        f"# {stats.epoch_name}\n\n"
        f"*{stats.start} \u2014 {stats.end} | "
        f"{stats.commit_count} commits across {n_repos} repos | "
        f"Dominant: {dominant_label}*\n"
    )

    # Narrative paragraphs
    paragraphs: list[str] = []

    # 1. Opening
    opening = _format_opening(stats.dominant_archetype, stats)
    paragraphs.append(opening + ".")

    # 2. Body
    if stats.commit_count > 0:
        body = _build_body_paragraph(stats)
        paragraphs.append(body)

    # 3. Trickster note
    trickster = _build_trickster_note(stats)
    if trickster:
        paragraphs.append(trickster)

    # 4. Shadow note
    shadow = _build_shadow_note(stats)
    if shadow:
        paragraphs.append(shadow)

    # 5. Closing
    closing = _build_closing(stats)
    paragraphs.append(closing)

    narrative = "\n\n".join(paragraphs)

    # Data section
    repos_list = ", ".join(stats.repos_touched) if stats.repos_touched else "(none)"
    top_repos_list = (
        ", ".join(f"{name} ({count})" for name, count in stats.top_repos)
        if stats.top_repos
        else "(none)"
    )
    arch_table = _build_archetype_table(stats)

    data = (
        f"## Data\n\n"
        f"- **Commits:** {stats.commit_count}\n"
        f"- **Repos touched:** {repos_list}\n"
        f"- **Insertions/Deletions:** +{stats.total_insertions} / -{stats.total_deletions}\n"
        f"- **Top repos:** {top_repos_list}\n"
        f"- **Authors:** {', '.join(stats.authors) if stats.authors else '(none)'}\n\n"
        f"### Archetype distribution\n\n"
        f"{arch_table}\n"
    )

    return f"{header}\n{narrative}\n\n{data}"


# ── Batch generation ──────────────────────────────────────────────────


def _epoch_slug(epoch: Epoch) -> str:
    """Derive a filesystem-safe slug from the epoch name."""
    slug = epoch.name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return f"{epoch.id}-{slug}"


def generate_all_chronicles(
    records: list[FossilRecord],
    output_dir: Path,
    regenerate: bool = False,
) -> list[Path]:
    """Generate markdown chronicles for all epochs with records.

    Groups *records* by epoch, computes stats, and writes one markdown
    file per epoch to *output_dir*. Returns paths of files actually
    written. Skips existing files unless *regenerate* is True.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build epoch lookup
    epoch_by_id = {e.id: e for e in DECLARED_EPOCHS}

    # Group records by epoch
    epoch_records: dict[str, list[FossilRecord]] = {}
    for r in records:
        if r.epoch and r.epoch in epoch_by_id:
            epoch_records.setdefault(r.epoch, []).append(r)

    written: list[Path] = []
    for epoch_id, epoch_recs in sorted(epoch_records.items()):
        epoch = epoch_by_id[epoch_id]
        slug = _epoch_slug(epoch)
        path = output_dir / f"{slug}.md"

        if path.exists() and not regenerate:
            continue

        stats = compute_epoch_stats(epoch, epoch_recs)
        chronicle = generate_epoch_chronicle(stats, epoch_recs)
        path.write_text(chronicle, encoding="utf-8")
        written.append(path)

    return written
