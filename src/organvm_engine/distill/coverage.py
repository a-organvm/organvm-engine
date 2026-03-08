"""Cross-reference operational patterns against discovered SOPs.

Produces a coverage report showing which patterns are covered,
partially covered, or uncovered by existing SOPs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from organvm_engine.distill.taxonomy import OPERATIONAL_PATTERNS, OperationalPattern
from organvm_engine.prompts.clipboard.schema import ClipboardPrompt
from organvm_engine.sop.discover import SOPEntry


@dataclass
class CoverageEntry:
    """Coverage status for a single operational pattern."""

    pattern_id: str
    pattern_label: str
    tier: str
    status: str  # "covered" | "partial" | "uncovered"
    matching_sops: list[str] = field(default_factory=list)
    prompt_count: int = 0
    sample_prompts: list[str] = field(default_factory=list)
    sop_name_hint: str = ""

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "pattern_label": self.pattern_label,
            "tier": self.tier,
            "status": self.status,
            "matching_sops": self.matching_sops,
            "prompt_count": self.prompt_count,
            "sample_prompts": self.sample_prompts[:3],
            "sop_name_hint": self.sop_name_hint,
        }


def _sop_matches_pattern(sop: SOPEntry, pattern: OperationalPattern) -> bool:
    """Check if an SOP name/title matches a pattern's hint, aliases, or keywords."""
    sop_name = (sop.sop_name or "").lower()
    sop_title = (sop.title or "").lower()
    hint = pattern.sop_name_hint.lower()

    # Direct hint match (partial string match)
    if hint and (hint in sop_name or hint in sop_title):
        return True

    # Alias match — check if SOP name matches any known alias
    for alias in pattern.sop_name_aliases:
        if alias.lower() in sop_name or alias.lower() in sop_title:
            return True

    # Check if any keyword signals appear in the SOP name or title
    combined = f"{sop_name} {sop_title}"
    keyword_hits = sum(
        1 for kw in pattern.keyword_signals
        if kw.lower() in combined
    )
    return keyword_hits >= 2


def analyze_coverage(
    matched_patterns: dict[str, list[tuple[ClipboardPrompt, object]]],
    prompts: list[ClipboardPrompt],
    sop_entries: list[SOPEntry],
    patterns: dict[str, OperationalPattern] | None = None,
) -> list[CoverageEntry]:
    """Analyze which operational patterns are covered by existing SOPs.

    Args:
        matched_patterns: Output from matcher.match_batch().
        prompts: All input prompts.
        sop_entries: Discovered SOPs from sop.discover.discover_sops().
        patterns: Pattern definitions (defaults to OPERATIONAL_PATTERNS).

    Returns:
        List of CoverageEntry objects for all patterns.
    """
    patterns = patterns or OPERATIONAL_PATTERNS
    coverage: list[CoverageEntry] = []

    for pid, pattern in patterns.items():
        matching_sops = [
            sop.sop_name or sop.filename
            for sop in sop_entries
            if _sop_matches_pattern(sop, pattern)
        ]

        prompt_matches = matched_patterns.get(pid, [])
        prompt_count = len(prompt_matches)

        # Extract sample prompt texts (first 3, truncated)
        sample_prompts = []
        for prompt_obj, _match in prompt_matches[:3]:
            text = prompt_obj.text[:200].replace("\n", " ").strip()
            if len(prompt_obj.text) > 200:
                text += "..."
            sample_prompts.append(text)

        if matching_sops:
            status = "covered"
        elif prompt_count > 0 and any(
            _partial_sop_match(sop, pattern) for sop in sop_entries
        ):
            status = "partial"
        else:
            status = "uncovered"

        coverage.append(CoverageEntry(
            pattern_id=pid,
            pattern_label=pattern.label,
            tier=pattern.tier,
            status=status,
            matching_sops=matching_sops,
            prompt_count=prompt_count,
            sample_prompts=sample_prompts,
            sop_name_hint=pattern.sop_name_hint,
        ))

    return coverage


def _partial_sop_match(sop: SOPEntry, pattern: OperationalPattern) -> bool:
    """Looser match: any single keyword or alias in the SOP name/title."""
    sop_name = (sop.sop_name or "").lower()
    sop_title = (sop.title or "").lower()
    combined = f"{sop_name} {sop_title}"
    if any(alias.lower() in combined for alias in pattern.sop_name_aliases):
        return True
    return any(kw.lower() in combined for kw in pattern.keyword_signals)


def coverage_summary(entries: list[CoverageEntry]) -> dict:
    """Produce a summary dict from coverage entries."""
    total = len(entries)
    covered = sum(1 for e in entries if e.status == "covered")
    partial = sum(1 for e in entries if e.status == "partial")
    uncovered = sum(1 for e in entries if e.status == "uncovered")
    return {
        "total_patterns": total,
        "covered": covered,
        "partial": partial,
        "uncovered": uncovered,
        "coverage_pct": round(100 * covered / total, 1) if total else 0.0,
        "uncovered_patterns": [
            e.pattern_id for e in entries if e.status == "uncovered"
        ],
    }
