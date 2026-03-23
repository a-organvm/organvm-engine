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


# Per-epoch custom openings that override the generic template.
# These give each epoch a unique voice instead of repeating the archetype's
# default. Written as oracular present tense.
_EPOCH_OPENINGS: dict[str, str] = {
    "EPOCH-001": "Before naming, before organs, before the system knows it is a system — there is only raw creation",
    "EPOCH-002": "The Father speaks the names into existence. Eight organs. Eight Greek suffixes. The ontology is declared",
    "EPOCH-003": "The Mother lays foundations at speed — seven flagships documented in a single day",
    "EPOCH-004": "The Animus arrives with structure: 58 READMEs, 202,000 words, cross-validation against every link",
    "EPOCH-005": "The Anima adorns what the Animus built — essays, visual identity, the aesthetic layer that makes infrastructure feel alive",
    "EPOCH-006": "The organism becomes itself. All eight organs operational. The system crosses the threshold from collection to living thing",
    "EPOCH-007": "The Shadow surfaces the morning after launch. What was skipped, what was deferred, what was left hollow — it all demands attention now",
    "EPOCH-008": "Quiet. The Mother sustains. No sprints, no launches — just steady growth, day after day, the kind of work that doesn't announce itself",
    "EPOCH-009": "The Anima seizes the organism. For thirteen days the Work bleeds words — 170,000 of them. Sleep dissolves. Naming discipline fractures. The Trickster grins",
    "EPOCH-010": "The Self turns to face what the Anima produced. Twenty-two sessions. A reckoning with the distance between what was built and what was recorded",
    "EPOCH-011": "The Animus returns to make sense of what the Anima left behind. Forty-two modules. Omega expansion. CI remediation. The engine hardens",
    "EPOCH-012": "For the first time, the organism reaches outward. Contribution workspaces. A PR to a stranger's codebase. The system discovers it can give, not only build",
}


def _format_opening(arch: Archetype, stats: EpochStats) -> str:
    """Render the opening sentence for the dominant archetype.

    Uses per-epoch custom openings when available, falling back to
    the archetype vocabulary with verb selection varied by epoch hash
    to prevent repetition across epochs with the same dominant archetype.
    """
    # Custom opening overrides generic template
    if stats.epoch_id in _EPOCH_OPENINGS:
        return _EPOCH_OPENINGS[stats.epoch_id]

    template = ARCHETYPE_VOICE[arch]["opening"]
    # Vary verb by epoch hash so same-archetype epochs don't repeat
    verb_index = hash(stats.epoch_id) % len(ARCHETYPE_VOICE[arch]["verbs"])
    verb = _pick_verb(arch, verb_index)

    organ_str = ", ".join(stats.organs_touched[:3]) if stats.organs_touched else "the Work"

    return template.format(verb=verb, organ=organ_str)


def _format_presence(arch: Archetype, detail: str) -> str:
    """Render a presence sentence for a secondary archetype."""
    template = ARCHETYPE_VOICE[arch]["presence"]
    return template.format(detail=detail)


def _duration_phrase(stats: EpochStats) -> str:
    """Human-readable duration for the epoch."""
    days = (stats.end - stats.start).days
    if days == 0:
        return "in a single day"
    if days == 1:
        return "across two days"
    if days <= 7:
        return f"across {days + 1} days"
    return f"across {days + 1} days ({(days + 1) // 7} weeks)"


def _build_body_paragraph(stats: EpochStats) -> str:
    """Compose the descriptive body of the chronicle."""
    parts: list[str] = []

    duration = _duration_phrase(stats)

    # Volume and character — with temporal context
    if stats.commit_count == 1:
        parts.append("A single commit marks this epoch")
    elif stats.commit_count < 10:
        parts.append(
            f"In {stats.commit_count} deliberate acts {duration}, the Work advances",
        )
    elif stats.commit_count < 50:
        parts.append(
            f"Across {stats.commit_count} commits {duration}, the organism builds steadily",
        )
    elif stats.commit_count < 200:
        parts.append(
            f"{stats.commit_count} commits {duration} — a sustained current of work",
        )
    else:
        parts.append(
            f"A torrent of {stats.commit_count} commits {duration} floods the record",
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


_ARCHETYPE_CLOSINGS: dict[Archetype, list[str]] = {
    Archetype.SHADOW: [
        "The debt is not resolved — only acknowledged. The Shadow will return.",
        "What was confronted does not vanish. It transforms.",
    ],
    Archetype.ANIMA: [
        "The creative flood recedes, leaving new material the Animus must now shape.",
        "What emerged cannot be un-dreamed. The organism is larger than before.",
    ],
    Archetype.ANIMUS: [
        "The structure holds. What was fluid is now load-bearing.",
        "The blueprint is laid. Future epochs will build on these foundations.",
    ],
    Archetype.SELF: [
        "The mirror reflects clearly now. The organism knows what it is — and what it is not.",
        "Self-knowledge is not comfort. It is the beginning of the next transformation.",
    ],
    Archetype.TRICKSTER: [
        "The Trickster never explains. What was disrupted stays disrupted. The system must adapt.",
        "Chaos leaves gifts — but they're wrapped in confusion.",
    ],
    Archetype.MOTHER: [
        "The ground is firm. Whatever comes next has a foundation to stand on.",
        "The infrastructure hums. Quietly. As infrastructure should.",
    ],
    Archetype.FATHER: [
        "The law is spoken. The gates are set. Now the system must live within them.",
        "Authority has been exercised. The question is whether it was wise.",
    ],
    Archetype.INDIVIDUATION: [
        "The system is more whole than when this epoch began. Integration is irreversible.",
        "What was separate is now connected. The organism remembers this shape.",
    ],
}


def _build_closing(stats: EpochStats) -> str:
    """A sentence about what the epoch leaves for the next."""
    if stats.commit_count == 0:
        return "Silence. The organism waits."
    dominant = stats.dominant_archetype
    closings = _ARCHETYPE_CLOSINGS.get(dominant, ["The epoch closes."])
    # Vary by epoch hash
    idx = hash(stats.epoch_id) % len(closings)
    return closings[idx]


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
