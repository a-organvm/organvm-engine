"""Match clipboard prompts against operational patterns.

Scoring: regex hit = +0.3, keyword hit = +0.1, category affinity = +0.2.
Threshold: >= 0.3 to count as a match.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from organvm_engine.distill.taxonomy import OPERATIONAL_PATTERNS, OperationalPattern
from organvm_engine.prompts.clipboard.schema import ClipboardPrompt

SCORE_REGEX = 0.3
SCORE_KEYWORD = 0.1
SCORE_CATEGORY = 0.2
MATCH_THRESHOLD = 0.3


@dataclass
class PatternMatch:
    """A scored match between a prompt and an operational pattern."""

    pattern_id: str
    score: float
    regex_hits: list[str] = field(default_factory=list)
    keyword_hits: list[str] = field(default_factory=list)
    category_match: bool = False

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "score": round(self.score, 3),
            "regex_hits": self.regex_hits,
            "keyword_hits": self.keyword_hits,
            "category_match": self.category_match,
        }


def _score_prompt(
    text: str,
    category: str,
    pattern: OperationalPattern,
) -> PatternMatch:
    """Score a single prompt against a single pattern."""
    text_lower = text.lower()
    score = 0.0
    regex_hits: list[str] = []
    keyword_hits: list[str] = []
    category_match = False

    for rx in pattern.regex_signals:
        if rx.search(text):
            score += SCORE_REGEX
            regex_hits.append(rx.pattern)

    for kw in pattern.keyword_signals:
        if kw.lower() in text_lower:
            score += SCORE_KEYWORD
            keyword_hits.append(kw)

    if category in pattern.category_affinity:
        score += SCORE_CATEGORY
        category_match = True

    return PatternMatch(
        pattern_id=pattern.id,
        score=score,
        regex_hits=regex_hits,
        keyword_hits=keyword_hits,
        category_match=category_match,
    )


def match_prompt(
    prompt: ClipboardPrompt,
    patterns: dict[str, OperationalPattern] | None = None,
    threshold: float = MATCH_THRESHOLD,
) -> list[PatternMatch]:
    """Match a single prompt against all patterns.

    Returns matches above threshold, sorted by score descending.
    """
    patterns = patterns or OPERATIONAL_PATTERNS
    matches: list[PatternMatch] = []

    for pattern in patterns.values():
        m = _score_prompt(prompt.text, prompt.category, pattern)
        if m.score >= threshold:
            matches.append(m)

    return sorted(matches, key=lambda x: x.score, reverse=True)


def match_batch(
    prompts: list[ClipboardPrompt],
    patterns: dict[str, OperationalPattern] | None = None,
    threshold: float = MATCH_THRESHOLD,
) -> dict[str, list[tuple[ClipboardPrompt, PatternMatch]]]:
    """Match a batch of prompts, grouped by pattern ID.

    Returns:
        Dict mapping pattern_id → list of (prompt, match) tuples,
        sorted by match score descending within each group.
    """
    patterns = patterns or OPERATIONAL_PATTERNS
    by_pattern: dict[str, list[tuple[ClipboardPrompt, PatternMatch]]] = {}

    for prompt in prompts:
        for m in match_prompt(prompt, patterns, threshold):
            by_pattern.setdefault(m.pattern_id, []).append((prompt, m))

    # Sort each group by score descending
    for _pid, entries in by_pattern.items():
        entries.sort(key=lambda x: x[1].score, reverse=True)

    return by_pattern
