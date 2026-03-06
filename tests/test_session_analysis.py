"""Tests for cross-session prompt analysis."""

import json
from pathlib import Path

import pytest

from organvm_engine.session.agents import AgentSession
from organvm_engine.session.analysis import (
    PromptStats,
    _content_to_text,
    _extract_claude_prompts,
    _extract_gemini_prompts,
    _find_repeated_phrases,
    analyze_prompts,
    render_analysis_report,
)


# ── _content_to_text ──────────────────────────────────────────────


def test_content_to_text_string():
    assert _content_to_text("hello world") == "hello world"


def test_content_to_text_block_list():
    blocks = [
        {"type": "text", "text": "first"},
        {"type": "image", "url": "x"},
        {"type": "text", "text": "second"},
    ]
    assert _content_to_text(blocks) == "first second"


def test_content_to_text_empty():
    assert _content_to_text("") == ""
    assert _content_to_text([]) == ""
    assert _content_to_text(None) == ""


def test_content_to_text_string_list():
    assert _content_to_text(["a", "b"]) == "a b"


# ── _extract_claude_prompts ───────────────────────────────────────


def test_extract_claude_prompts(tmp_path):
    jsonl = tmp_path / "session.jsonl"
    messages = [
        {"type": "user", "message": {"content": "This is a test prompt that is long enough"}},
        {"type": "assistant", "message": {"content": "response"}},
        {"type": "user", "message": {"content": "Another prompt with enough length"}},
    ]
    with jsonl.open("w") as f:
        for m in messages:
            f.write(json.dumps(m) + "\n")

    prompts = _extract_claude_prompts(jsonl)
    assert len(prompts) == 2
    assert "test prompt" in prompts[0]


def test_extract_claude_prompts_short_filtered(tmp_path):
    jsonl = tmp_path / "session.jsonl"
    messages = [
        {"type": "user", "message": {"content": "short"}},  # <10 chars, filtered
        {"type": "user", "message": {"content": "This is long enough to pass the filter"}},
    ]
    with jsonl.open("w") as f:
        for m in messages:
            f.write(json.dumps(m) + "\n")

    prompts = _extract_claude_prompts(jsonl)
    assert len(prompts) == 1


def test_extract_claude_prompts_block_content(tmp_path):
    jsonl = tmp_path / "session.jsonl"
    messages = [
        {"type": "user", "message": {"content": [
            {"type": "text", "text": "Block-based prompt that is long enough"},
        ]}},
    ]
    with jsonl.open("w") as f:
        for m in messages:
            f.write(json.dumps(m) + "\n")

    prompts = _extract_claude_prompts(jsonl)
    assert len(prompts) == 1
    assert "Block-based" in prompts[0]


# ── _extract_gemini_prompts ───────────────────────────────────────


def test_extract_gemini_prompts(tmp_path):
    session_file = tmp_path / "session.json"
    data = {
        "messages": [
            {"role": "user", "parts": [{"text": "Gemini prompt long enough to pass"}]},
            {"role": "model", "parts": [{"text": "response"}]},
            {"role": "user", "parts": [{"text": "Another gemini prompt here long"}]},
        ]
    }
    session_file.write_text(json.dumps(data))

    prompts = _extract_gemini_prompts(session_file)
    assert len(prompts) == 2


def test_extract_gemini_prompts_empty(tmp_path):
    session_file = tmp_path / "session.json"
    session_file.write_text(json.dumps({"messages": []}))

    prompts = _extract_gemini_prompts(session_file)
    assert prompts == []


# ── _find_repeated_phrases ────────────────────────────────────────


def test_find_repeated_phrases_basic():
    prompts = [
        "please implement the feature as discussed",
        "please implement the feature differently",
        "please implement the feature now",
    ]
    results = _find_repeated_phrases(prompts, min_count=3, min_words=3)
    phrases = [p for p, _ in results]
    assert any("please implement the" in p for p in phrases)


def test_find_repeated_phrases_below_threshold():
    prompts = [
        "unique phrase one here today",
        "different content entirely here today",
    ]
    results = _find_repeated_phrases(prompts, min_count=3, min_words=4)
    assert results == []


def test_find_repeated_phrases_empty():
    assert _find_repeated_phrases([], min_count=3) == []


# ── PromptStats ───────────────────────────────────────────────────


def test_prompt_stats_defaults():
    stats = PromptStats()
    assert stats.total_sessions == 0
    assert stats.total_prompts == 0
    assert stats.agent_breakdown == {}


# ── analyze_prompts (with mock sessions) ──────────────────────────


def _make_claude_session(tmp_path: Path, name: str, prompts: list[str]) -> AgentSession:
    """Create a mock Claude session JSONL with given prompts."""
    from datetime import datetime, timezone

    jsonl = tmp_path / f"{name}.jsonl"
    with jsonl.open("w") as f:
        for i, prompt in enumerate(prompts):
            f.write(json.dumps({
                "type": "user",
                "timestamp": f"2026-03-06T10:{i:02d}:00Z",
                "message": {"content": prompt},
            }) + "\n")
            f.write(json.dumps({
                "type": "assistant",
                "timestamp": f"2026-03-06T10:{i:02d}:30Z",
                "message": {"content": "ok"},
            }) + "\n")

    return AgentSession(
        agent="claude",
        session_id=name,
        file_path=jsonl,
        project_dir="test-project",
        started=datetime(2026, 3, 6, 10, 0, tzinfo=timezone.utc),
        ended=datetime(2026, 3, 6, 10, 30, tzinfo=timezone.utc),
        size_bytes=jsonl.stat().st_size,
    )


def test_analyze_prompts_basic(tmp_path):
    sessions = [
        _make_claude_session(tmp_path, "s1", [
            "Implement the new feature for the dashboard",
            "Fix the bug in the registry validator",
        ]),
        _make_claude_session(tmp_path, "s2", [
            "Add tests for the new feature we just built",
        ]),
    ]

    stats = analyze_prompts(sessions=sessions)
    assert stats.total_sessions == 2
    assert stats.total_prompts == 3
    assert stats.total_chars > 0
    assert stats.avg_prompt_length > 0
    assert "claude" in stats.agent_breakdown


def test_analyze_prompts_empty():
    stats = analyze_prompts(sessions=[])
    assert stats.total_sessions == 0
    assert stats.total_prompts == 0


def test_analyze_prompts_missing_file(tmp_path):
    from datetime import datetime, timezone

    session = AgentSession(
        agent="claude",
        session_id="missing",
        file_path=tmp_path / "nonexistent.jsonl",
        project_dir="test",
        started=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ended=datetime(2026, 1, 1, tzinfo=timezone.utc),
        size_bytes=0,
    )
    stats = analyze_prompts(sessions=[session])
    assert stats.total_sessions == 0
    assert stats.skipped_sessions == 1


# ── render_analysis_report ────────────────────────────────────────


def test_render_report_empty():
    stats = PromptStats()
    report = render_analysis_report(stats)
    assert "Cross-Session Prompt Analysis" in report
    assert "Sessions analyzed: 0" in report


def test_render_report_with_data():
    stats = PromptStats(
        total_sessions=10,
        total_prompts=50,
        total_chars=5000,
        avg_prompt_length=100,
        top_opening_words={"please fix the": 5, "implement the new": 3},
        agent_breakdown={"claude": 40, "gemini": 10},
        repeated_phrases=[("please fix the bug", 5), ("implement the feature", 3)],
    )
    report = render_analysis_report(stats)
    assert "Sessions analyzed: 10" in report
    assert "Agent Breakdown" in report
    assert "claude: 40" in report
    assert "Opening Phrases" in report
    assert "Repeated Phrases" in report
