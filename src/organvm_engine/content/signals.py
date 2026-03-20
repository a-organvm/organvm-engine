"""Detect potential content moments in session conversations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import median

SIGNAL_STRENGTH = ("high", "medium", "low")

_ORGAN_RE = re.compile(r"ORGAN-[IVX]+|organ-[ivx]+|ORGAN-\w+", re.IGNORECASE)

_EMOTIONAL_PATTERNS = [
    re.compile(r"\bI feel\b", re.IGNORECASE),
    re.compile(r"\bI realized?\b", re.IGNORECASE),
    re.compile(r"\bthis matters\b", re.IGNORECASE),
    re.compile(r"\bI'?ve been thinking\b", re.IGNORECASE),
    re.compile(r"\bthis is what\b", re.IGNORECASE),
    re.compile(r"\bit hit me\b", re.IGNORECASE),
    re.compile(r"\bI need to\b", re.IGNORECASE),
    re.compile(r"\bI can'?t stop\b", re.IGNORECASE),
]

_METAPHOR_MARKERS = [
    "like", "as if", "reminds me", "feels like",
    "is a", "are the", "exist in", "the way",
]


@dataclass
class ContentSignal:
    """A detected content moment in a session conversation."""

    prompt_index: int
    signal_type: str
    description: str
    excerpt: str
    strength: str


def detect_content_signals(
    human_messages: list[str],
) -> list[ContentSignal]:
    """Scan session messages for potential content moments.

    Returns signals sorted by strength (high first).
    """
    if not human_messages:
        return []

    signals: list[ContentSignal] = []
    lengths = [len(m) for m in human_messages if m.strip()]
    med_len = median(lengths) if lengths else 0

    for i, msg in enumerate(human_messages):
        idx = i + 1
        text = msg.strip()
        if not text:
            continue
        excerpt = text[:120]

        # voice_shift: message length >3x median and >100 chars
        if med_len > 0 and len(text) > med_len * 3 and len(text) > 100:
            signals.append(ContentSignal(
                prompt_index=idx,
                signal_type="voice_shift",
                description="directive to reflective — message length >3x session median",
                excerpt=excerpt,
                strength="medium",
            ))

        # standalone_power: short sentence with metaphor markers
        sentences = re.split(r"[.!?]+", text)
        for sent in sentences:
            sent = sent.strip()
            words = sent.split()
            if 3 <= len(words) <= 15:
                has_marker = any(m in sent.lower() for m in _METAPHOR_MARKERS)
                if has_marker:
                    signals.append(ContentSignal(
                        prompt_index=idx,
                        signal_type="standalone_power",
                        description="short sentence with metaphorical weight",
                        excerpt=sent[:120],
                        strength="high",
                    ))
                    break

        # emotional_resonance: first-person emotional language
        emotional_hits = sum(1 for p in _EMOTIONAL_PATTERNS if p.search(text))
        if emotional_hits >= 2:
            signals.append(ContentSignal(
                prompt_index=idx,
                signal_type="emotional_resonance",
                description=f"first-person emotional language ({emotional_hits} markers)",
                excerpt=excerpt,
                strength="high" if emotional_hits >= 3 else "medium",
            ))
        elif emotional_hits == 1 and len(text) > 60:
            signals.append(ContentSignal(
                prompt_index=idx,
                signal_type="emotional_resonance",
                description="first-person emotional language in extended message",
                excerpt=excerpt,
                strength="low",
            ))

        # architectural_connection: references to 2+ organs
        organ_refs = set(_ORGAN_RE.findall(text))
        if len(organ_refs) >= 2:
            signals.append(ContentSignal(
                prompt_index=idx,
                signal_type="architectural_connection",
                description=f"references {len(organ_refs)} organs in a single message",
                excerpt=excerpt,
                strength="high" if len(organ_refs) >= 3 else "medium",
            ))

    order = {"high": 0, "medium": 1, "low": 2}
    signals.sort(key=lambda s: order.get(s.strength, 3))

    return signals
