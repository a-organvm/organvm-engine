"""Cross-session prompt analysis.

Lightweight string-counting analysis of human prompts across sessions.
No NLP dependencies — just frequency counting and basic stats.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from organvm_engine.session.agents import AgentSession, discover_all_sessions


@dataclass
class PromptStats:
    """Aggregated statistics across analyzed sessions."""

    total_sessions: int = 0
    total_prompts: int = 0
    total_chars: int = 0
    avg_prompt_length: int = 0
    top_opening_words: dict[str, int] = field(default_factory=dict)
    repeated_phrases: list[tuple[str, int]] = field(default_factory=list)
    agent_breakdown: dict[str, int] = field(default_factory=dict)
    skipped_sessions: int = 0


def analyze_prompts(
    sessions: list[AgentSession] | None = None,
    agent: str | None = None,
    sample_limit: int = 200,
) -> PromptStats:
    """Analyze human prompts across sessions.

    Args:
        sessions: Pre-filtered session list, or None to discover.
        agent: Filter to a specific agent (claude/gemini/codex).
        sample_limit: Max sessions to analyze (0 = all).
    """
    if sessions is None:
        sessions = discover_all_sessions(agent=agent)

    if sample_limit > 0:
        sessions = sessions[:sample_limit]

    stats = PromptStats()
    all_prompts: list[str] = []
    opening_counter: Counter[str] = Counter()
    agent_counter: Counter[str] = Counter()

    for session in sessions:
        prompts = _extract_prompts_from_session(session)
        if prompts is None:
            stats.skipped_sessions += 1
            continue

        stats.total_sessions += 1
        agent_counter[session.agent] += len(prompts)

        for prompt_text in prompts:
            stats.total_prompts += 1
            stats.total_chars += len(prompt_text)
            all_prompts.append(prompt_text)

            # Track opening words (first 3 words, lowercased)
            words = prompt_text.split()[:3]
            if words:
                opening = " ".join(w.lower() for w in words)
                opening_counter[opening] += 1

    if stats.total_prompts > 0:
        stats.avg_prompt_length = stats.total_chars // stats.total_prompts

    stats.top_opening_words = dict(opening_counter.most_common(20))
    stats.agent_breakdown = dict(agent_counter)
    stats.repeated_phrases = _find_repeated_phrases(all_prompts, min_count=3, min_words=4)

    return stats


def _extract_prompts_from_session(session: AgentSession) -> list[str] | None:
    """Extract human prompt texts from a session file.

    Returns None if the session can't be parsed (vs empty list for no prompts).
    """
    import json

    path = session.file_path
    if not path.exists():
        return None

    try:
        if session.agent == "gemini":
            return _extract_gemini_prompts(path)
        if session.agent == "codex":
            return _extract_codex_prompts(path)
        return _extract_claude_prompts(path)
    except (OSError, json.JSONDecodeError):
        return None


def _extract_claude_prompts(path: Path) -> list[str]:
    """Extract human prompts from a Claude JSONL session."""
    import json

    prompts: list[str] = []
    with path.open(encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("type") != "user":
                continue
            content = msg.get("message", {}).get("content", "")
            text = _content_to_text(content)
            if text and len(text) > 10:
                prompts.append(text)
    return prompts


def _extract_gemini_prompts(path: Path) -> list[str]:
    """Extract human prompts from a Gemini JSON session."""
    import json

    prompts: list[str] = []
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    for msg in data.get("messages", []):
        if msg.get("role") != "user":
            continue
        parts = msg.get("parts", [])
        for part in parts:
            if isinstance(part, dict) and part.get("text"):
                text = part["text"].strip()
                if len(text) > 10:
                    prompts.append(text)
    return prompts


def _extract_codex_prompts(path: Path) -> list[str]:
    """Extract human prompts from a Codex JSONL session."""
    import json

    prompts: list[str] = []
    with path.open(encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "session_meta":
                # Codex user prompts are in session_meta.payload.instructions
                # or in the initial prompt field
                continue
            prompt = entry.get("payload", {}).get("instructions", "")
            if prompt and len(prompt) > 10:
                prompts.append(prompt)
    return prompts


def _content_to_text(content: str | list) -> str:
    """Extract plain text from Claude message content (string or block list)."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return " ".join(parts).strip()
    return ""


def _find_repeated_phrases(
    prompts: list[str],
    min_count: int = 3,
    min_words: int = 4,
    max_words: int = 8,
) -> list[tuple[str, int]]:
    """Find repeated multi-word phrases across all prompts.

    Uses a sliding window approach — no NLP required.
    """
    phrase_counter: Counter[str] = Counter()

    for text in prompts:
        # Normalize: lowercase, collapse whitespace, remove punctuation
        normalized = re.sub(r"[^\w\s]", "", text.lower())
        words = normalized.split()

        seen_in_prompt: set[str] = set()
        for window_size in range(min_words, min(max_words + 1, len(words) + 1)):
            for i in range(len(words) - window_size + 1):
                phrase = " ".join(words[i : i + window_size])
                if phrase not in seen_in_prompt:
                    seen_in_prompt.add(phrase)
                    phrase_counter[phrase] += 1

    # Filter by min_count and remove subphrases dominated by longer ones
    results = [(phrase, count) for phrase, count in phrase_counter.items() if count >= min_count]
    results.sort(key=lambda x: (-len(x[0].split()), -x[1]))

    # Keep top 30 longest/most-frequent
    return results[:30]


def render_analysis_report(stats: PromptStats) -> str:
    """Render a human-readable analysis report."""
    lines = [
        "# Cross-Session Prompt Analysis",
        "",
        f"Sessions analyzed: {stats.total_sessions} (skipped: {stats.skipped_sessions})",
        f"Total prompts: {stats.total_prompts}",
        f"Total characters: {stats.total_chars:,}",
        f"Average prompt length: {stats.avg_prompt_length} chars",
        "",
    ]

    if stats.agent_breakdown:
        lines.append("## Agent Breakdown")
        for agent, count in sorted(stats.agent_breakdown.items()):
            lines.append(f"  {agent}: {count} prompts")
        lines.append("")

    if stats.top_opening_words:
        lines.append("## Top Opening Phrases (first 3 words)")
        for phrase, count in sorted(stats.top_opening_words.items(), key=lambda x: -x[1])[:15]:
            lines.append(f"  {count:>4}x  {phrase}")
        lines.append("")

    if stats.repeated_phrases:
        lines.append("## Repeated Phrases (4+ words, 3+ occurrences)")
        for phrase, count in stats.repeated_phrases[:20]:
            lines.append(f"  {count:>4}x  \"{phrase}\"")
        lines.append("")

    return "\n".join(lines)
