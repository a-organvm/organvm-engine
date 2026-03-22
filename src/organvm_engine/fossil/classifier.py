"""Jungian archetype classifier for commit messages.

Scores commit messages against 8 archetypes using keyword/regex matching,
repo context boosts, organ context boosts, and conventional type fallbacks.
Returns a ranked list of archetypes sorted by score descending.
"""

from __future__ import annotations

import re

from organvm_engine.fossil.stratum import Archetype

# ---------------------------------------------------------------------------
# Creative repos — presence boosts Anima
# ---------------------------------------------------------------------------
_CREATIVE_REPOS: frozenset[str] = frozenset(
    [
        "metasystem-master",
        "a-mavs-olevm",
        "krypto-velamen",
        "chthon-oneiros",
        "alchemical-synthesizer",
        "styx-behavioral-art",
        "vigiles-aeternae--theatrum-mundi",
        "vigiles-aeternae--corpus-mythicum",
        "materia-collider",
        "object-lessons",
    ],
)

# ---------------------------------------------------------------------------
# Archetype keyword / regex patterns
# ---------------------------------------------------------------------------
# Each entry is (pattern_str, flags, score_delta).
# Patterns are matched against the lower-cased commit message.

_SHADOW_PATTERNS: list[tuple[str, int, float]] = [
    (r"\bfix\b", re.IGNORECASE, 1.0),
    (r"\bsecurity\b", re.IGNORECASE, 1.5),
    (r"\bremediat", re.IGNORECASE, 2.0),
    (r"\bdebt\b", re.IGNORECASE, 1.5),
    (r"\blint\b", re.IGNORECASE, 1.2),
    (r"\berror\b", re.IGNORECASE, 0.8),
    (r"\berrors\b", re.IGNORECASE, 0.8),
    (r"\bvulnerab", re.IGNORECASE, 1.5),
    (r"\bremove\b", re.IGNORECASE, 0.6),
    (r"\bdelete\b", re.IGNORECASE, 0.6),
    (r"\bclean", re.IGNORECASE, 0.8),
    (r"\bpatch\b", re.IGNORECASE, 0.8),
    (r"\bhotfix\b", re.IGNORECASE, 1.2),
    (r"\bexploit\b", re.IGNORECASE, 1.5),
    (r"\bbug\b", re.IGNORECASE, 0.9),
    (r"\bregress", re.IGNORECASE, 1.0),
]

_ANIMA_PATTERNS: list[tuple[str, int, float]] = [
    (r"\bart\b", re.IGNORECASE, 1.5),
    (r"\bnarrative", re.IGNORECASE, 1.5),
    (r"\bgenerat", re.IGNORECASE, 1.0),
    (r"\bvisual", re.IGNORECASE, 1.0),
    (r"\baudio\b", re.IGNORECASE, 1.0),
    (r"\bessay\b", re.IGNORECASE, 1.0),
    (r"\bbestiary\b", re.IGNORECASE, 2.0),
    (r"\bworldbuild", re.IGNORECASE, 1.5),
    (r"\bcharacter\b", re.IGNORECASE, 1.2),
    (r"\bmytholog", re.IGNORECASE, 2.0),
    (r"\bcorpus\b", re.IGNORECASE, 0.8),
    (r"\bresearch\b", re.IGNORECASE, 0.8),
    (r"\bpaper\b", re.IGNORECASE, 0.8),
    (r"\bsynthesis\b", re.IGNORECASE, 1.0),
    (r"\bpoetic\b", re.IGNORECASE, 1.5),
    (r"\baesthetic\b", re.IGNORECASE, 1.5),
    (r"\bperformance\b", re.IGNORECASE, 0.8),
    (r"\bimaginal\b", re.IGNORECASE, 2.0),
]

_ANIMUS_PATTERNS: list[tuple[str, int, float]] = [
    (r"\bgovernance\b", re.IGNORECASE, 1.0),
    (r"\bproof\b", re.IGNORECASE, 1.2),
    (r"\bformal\b", re.IGNORECASE, 1.0),
    (r"\bstate.machine\b", re.IGNORECASE, 1.5),
    (r"\bschema\b", re.IGNORECASE, 1.2),
    (r"\bvalidat", re.IGNORECASE, 1.0),
    (r"\btype\b", re.IGNORECASE, 0.6),
    (r"\bdependency.graph\b", re.IGNORECASE, 2.0),
    (r"\btemporal\b", re.IGNORECASE, 1.5),
    (r"\bversioning\b", re.IGNORECASE, 1.5),
    (r"\btaxonomy\b", re.IGNORECASE, 1.2),
    (r"\barchitect", re.IGNORECASE, 1.0),
    (r"\bstructure\b", re.IGNORECASE, 0.8),
    (r"\bmodel\b", re.IGNORECASE, 0.6),
    (r"\bspecif", re.IGNORECASE, 0.8),
    (r"\bcontract\b", re.IGNORECASE, 1.0),
    (r"\bclassif", re.IGNORECASE, 0.8),
    (r"\bsystem\b", re.IGNORECASE, 0.5),
]

_SELF_PATTERNS: list[tuple[str, int, float]] = [
    (r"\btestament\b", re.IGNORECASE, 2.0),
    (r"\bself.referent", re.IGNORECASE, 3.0),
    (r"\bself-referent", re.IGNORECASE, 3.0),
    (r"\bcontext.sync\b", re.IGNORECASE, 3.0),
    (r"\bcontext sync\b", re.IGNORECASE, 3.0),
    (r"\bscorecard\b", re.IGNORECASE, 1.5),
    (r"\bregistry.update\b", re.IGNORECASE, 1.5),
    (r"\bomega\b", re.IGNORECASE, 1.5),
    (r"\bsystem.density\b", re.IGNORECASE, 2.0),
    (r"\bauto-refresh\b", re.IGNORECASE, 2.0),
    (r"\bauto.generated\b", re.IGNORECASE, 2.0),
    (r"\bauto-generated\b", re.IGNORECASE, 2.0),
    (r"\bsoak.test\b", re.IGNORECASE, 1.5),
    (r"\bnetwork.map\b", re.IGNORECASE, 1.5),
    (r"\bself-witness", re.IGNORECASE, 2.0),
    (r"\brefresh.*context\b", re.IGNORECASE, 2.0),
    (r"\bcontext.*refresh\b", re.IGNORECASE, 2.0),
]

_TRICKSTER_PATTERNS: list[tuple[str, int, float]] = [
    # Short chaotic messages (handled separately as heuristic)
    (r"[!;+]{2,}", 0, 1.5),
    (r"\byolo\b", re.IGNORECASE, 3.0),
    (r"\blol\b", re.IGNORECASE, 2.0),
    (r"\bwip\b", re.IGNORECASE, 1.5),
    (r"\btest\s+commit\b", re.IGNORECASE, 1.5),
    (r"\bquick\s+fix\b", re.IGNORECASE, 0.8),
    (r"\boops\b", re.IGNORECASE, 2.0),
    (r"\btemp\b", re.IGNORECASE, 1.0),
]

_MOTHER_PATTERNS: list[tuple[str, int, float]] = [
    (r"\b[Cc][Ii]\b", 0, 2.0),  # CI (case-sensitive as acronym)
    (r"\btest\b", re.IGNORECASE, 0.8),
    (r"\binfra\b", re.IGNORECASE, 1.5),
    (r"\bdocker\b", re.IGNORECASE, 1.5),
    (r"\bdeploy", re.IGNORECASE, 1.2),
    (r"\benvironment\b", re.IGNORECASE, 1.0),
    (r"\bdotfile\b", re.IGNORECASE, 1.5),
    (r"\bdocker\b", re.IGNORECASE, 1.5),
    (r"\blaunchagent\b", re.IGNORECASE, 2.0),
    (r"\bworkflow\b", re.IGNORECASE, 1.2),
    (r"\bdependabot\b", re.IGNORECASE, 1.5),
    (r"\bpipeline\b", re.IGNORECASE, 0.8),
    (r"\bbuild\b", re.IGNORECASE, 0.8),
    (r"\bnurtur", re.IGNORECASE, 1.5),
    (r"\bsupport\b", re.IGNORECASE, 0.6),
    (r"\bhealth\b", re.IGNORECASE, 0.8),
    (r"\bmaintain", re.IGNORECASE, 1.0),
    (r"\bfailure\b", re.IGNORECASE, 0.8),
    (r"\bfailures\b", re.IGNORECASE, 0.8),
    (r"\bbats\b", re.IGNORECASE, 1.5),
]

_FATHER_PATTERNS: list[tuple[str, int, float]] = [
    (r"\bgovernance\b", re.IGNORECASE, 1.0),
    (r"\bpromot", re.IGNORECASE, 1.5),
    (r"\bgate\b", re.IGNORECASE, 2.0),
    (r"\benforce", re.IGNORECASE, 1.5),
    (r"\bconstraint\b", re.IGNORECASE, 1.5),
    (r"\brule\b", re.IGNORECASE, 1.2),
    (r"\bprotect", re.IGNORECASE, 1.2),
    (r"\bpermission\b", re.IGNORECASE, 1.2),
    (r"\bdescent.protocol\b", re.IGNORECASE, 2.0),
    (r"\bprimacy\b", re.IGNORECASE, 2.0),
    (r"\bauthorit", re.IGNORECASE, 1.5),
    (r"\bsanction\b", re.IGNORECASE, 1.5),
    (r"\baudit\b", re.IGNORECASE, 1.0),
    (r"\bcompliance\b", re.IGNORECASE, 1.5),
    (r"\bpolic", re.IGNORECASE, 1.0),
    (r"\bindividual", re.IGNORECASE, 1.2),
    (r"\binvariant", re.IGNORECASE, 1.5),
]

_INDIVIDUATION_PATTERNS: list[tuple[str, int, float]] = [
    (r"\bcross.organ\b", re.IGNORECASE, 3.0),
    (r"\bcross-organ\b", re.IGNORECASE, 3.0),
    (r"\bcontrib", re.IGNORECASE, 1.5),
    (r"\batoms.pipeline\b", re.IGNORECASE, 2.0),
    (r"\bnetwork.testament\b", re.IGNORECASE, 2.0),
    (r"\boutbound\b", re.IGNORECASE, 2.5),
    (r"\bsyndication\b", re.IGNORECASE, 2.0),
    (r"\bintegrat", re.IGNORECASE, 0.8),
    (r"\bharvest\b", re.IGNORECASE, 1.0),
    (r"\btransmut", re.IGNORECASE, 1.5),
    (r"\bunif", re.IGNORECASE, 0.8),
    (r"\bholistic\b", re.IGNORECASE, 1.5),
]

# Map archetype → patterns list
_ARCHETYPE_PATTERNS: dict[Archetype, list[tuple[str, int, float]]] = {
    Archetype.SHADOW: _SHADOW_PATTERNS,
    Archetype.ANIMA: _ANIMA_PATTERNS,
    Archetype.ANIMUS: _ANIMUS_PATTERNS,
    Archetype.SELF: _SELF_PATTERNS,
    Archetype.TRICKSTER: _TRICKSTER_PATTERNS,
    Archetype.MOTHER: _MOTHER_PATTERNS,
    Archetype.FATHER: _FATHER_PATTERNS,
    Archetype.INDIVIDUATION: _INDIVIDUATION_PATTERNS,
}


def _score_message(message: str) -> dict[Archetype, float]:
    """Score a commit message against all archetypes using pattern matching."""
    scores: dict[Archetype, float] = {a: 0.0 for a in Archetype}
    for archetype, patterns in _ARCHETYPE_PATTERNS.items():
        for pattern, flags, weight in patterns:
            if flags:
                if re.search(pattern, message, flags):
                    scores[archetype] += weight
            elif re.search(pattern, message):
                scores[archetype] += weight
    return scores


def _apply_trickster_heuristics(message: str, conventional_type: str, scores: dict[Archetype, float]) -> None:
    """Apply Trickster heuristics: short messages and missing conventional prefix."""
    stripped = message.strip()
    # Short chaotic message (≤ 5 printable chars after stripping punctuation noise)
    if len(stripped) <= 16 and not conventional_type:
        scores[Archetype.TRICKSTER] += 3.0
    # No conventional prefix (and not Merge/Revert/version bump)
    if not conventional_type:
        is_merge = re.match(r"^Merge\b", stripped)
        is_revert = re.match(r"^Revert\b", stripped)
        is_version = re.match(r"^v?\d+\.\d+", stripped)
        if not (is_merge or is_revert or is_version):
            scores[Archetype.TRICKSTER] += 2.0


def _apply_conventional_type_boosts(conventional_type: str, scores: dict[Archetype, float]) -> None:
    """Apply boosts based on the conventional commit type."""
    ct = conventional_type.lower()
    if ct == "fix":
        scores[Archetype.SHADOW] += 1.0
    elif ct == "test":
        scores[Archetype.MOTHER] += 1.0
    elif ct == "chore":
        scores[Archetype.MOTHER] += 0.5
    elif ct == "feat":
        # Small bump to ANIMUS for new features that may be structural
        scores[Archetype.ANIMUS] += 0.3
    elif ct == "refactor":
        scores[Archetype.SHADOW] += 0.5
    elif ct in ("docs", "doc"):
        scores[Archetype.SELF] += 0.5
    elif ct == "ci":
        scores[Archetype.MOTHER] += 1.5


def _apply_repo_boosts(repo: str, scores: dict[Archetype, float]) -> None:
    """Apply boosts based on the repo name."""
    if repo in _CREATIVE_REPOS:
        scores[Archetype.ANIMA] += 2.0
    # domus / dotfiles repos → Mother
    if "domus" in repo.lower():
        scores[Archetype.MOTHER] += 1.5
    # governance / engine repos → slight Animus
    if "engine" in repo.lower() or "governance" in repo.lower():
        scores[Archetype.ANIMUS] += 0.5


def _apply_organ_boosts(organ: str, scores: dict[Archetype, float]) -> None:
    """Apply boosts based on the organ short key."""
    org = organ.upper()
    if org == "META":
        scores[Archetype.SELF] += 0.8
        scores[Archetype.ANIMUS] += 0.5
    elif org == "IV":
        scores[Archetype.INDIVIDUATION] += 1.0
    elif org == "II":
        scores[Archetype.ANIMA] += 0.5
    elif org == "I":
        scores[Archetype.ANIMUS] += 0.3
    elif org in ("LIMINAL", "LIMINAL_ALT"):
        scores[Archetype.MOTHER] += 0.5


def classify_commit(
    message: str,
    conventional_type: str,
    repo: str,
    organ: str,
) -> list[Archetype]:
    """Classify a commit message into a ranked list of Jungian archetypes.

    Args:
        message: The full commit message.
        conventional_type: The conventional commit type prefix (e.g. "feat", "fix"), or "".
        repo: Repository name (used for context boosts).
        organ: Organ short key (e.g. "I", "II", "META", "LIMINAL").

    Returns:
        Ranked list of Archetype values sorted by score descending.
        Falls back to [Archetype.MOTHER] if nothing scores above zero.
    """
    scores = _score_message(message)
    _apply_trickster_heuristics(message, conventional_type, scores)
    _apply_conventional_type_boosts(conventional_type, scores)
    _apply_repo_boosts(repo, scores)
    _apply_organ_boosts(organ, scores)

    # Rank: sort archetypes by score descending, keep those with score > 0
    ranked = sorted(
        [a for a, s in scores.items() if s > 0],
        key=lambda a: scores[a],
        reverse=True,
    )
    return ranked if ranked else [Archetype.MOTHER]
