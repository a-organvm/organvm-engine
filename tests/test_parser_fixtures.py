"""Integration tests: parse real-format session fixtures (SYS-071).

Proves prompt extraction handles production data formats.
Prevents parser format drift.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from organvm_engine.prompts.extractor import extract_prompts
from organvm_engine.session.agents import AgentSession

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sessions"


def _make_session(path: Path, agent: str) -> AgentSession:
    return AgentSession(
        session_id="fixture-test",
        agent=agent,
        file_path=path,
        project_dir="/Workspace/test-project",
        started=None,
        ended=None,
        size_bytes=path.stat().st_size,
    )


# ── Claude fixture ────────────────────────────────────────────


class TestClaudeFixture:
    """Parse the Claude JSONL fixture and verify extraction rules."""

    @pytest.fixture()
    def prompts(self):
        session = _make_session(FIXTURES_DIR / "claude-sample.jsonl", "claude")
        result = extract_prompts(session)
        assert result is not None
        return result

    def test_extracts_user_messages_only(self, prompts):
        # 4 user lines total, but "ok" (2 chars) is skipped -> 3 prompts
        assert len(prompts) == 3

    def test_skips_short_message(self, prompts):
        texts = [p.text for p in prompts]
        assert not any(t == "ok" for t in texts)

    def test_handles_string_content(self, prompts):
        assert prompts[0].text == "Create a data model for the inventory tracking module"

    def test_handles_list_content(self, prompts):
        # Second user message uses list-of-dicts content format
        assert prompts[1].text == "Add validation constraints to the quantity field"

    def test_preserves_timestamps(self, prompts):
        assert prompts[0].timestamp == "2026-04-10T09:00:00Z"
        assert prompts[2].timestamp == "2026-04-10T09:12:00Z"

    def test_sequential_indices(self, prompts):
        assert [p.index for p in prompts] == [0, 1, 2]

    def test_skips_system_and_assistant(self, prompts):
        # System message and assistant messages produce no prompts
        texts = [p.text for p in prompts]
        assert "Session initialized with project context" not in texts
        assert "I will design the data model" not in " ".join(texts)


# ── Gemini fixture ────────────────────────────────────────────


class TestGeminiFixture:
    """Parse the Gemini JSON fixture.

    This format was previously broken by wrong field names.
    The fixture validates the corrected parser reads 'content'
    (list of dicts with 'text' key) and 'type' == 'user'.
    """

    @pytest.fixture()
    def prompts(self):
        session = _make_session(FIXTURES_DIR / "gemini-sample.json", "gemini")
        result = extract_prompts(session)
        assert result is not None
        return result

    def test_extracts_user_messages_only(self, prompts):
        # 4 user messages, but "yes" (3 chars) is skipped -> 3 prompts
        assert len(prompts) == 3

    def test_skips_short_message(self, prompts):
        texts = [p.text for p in prompts]
        assert not any(t == "yes" for t in texts)

    def test_correct_field_names(self, prompts):
        # The prior bug used wrong field names. This proves 'content'
        # as list-of-dicts with 'text' key works correctly.
        assert prompts[0].text == (
            "Refactor the authentication middleware to support JWT rotation"
        )

    def test_per_message_timestamp(self, prompts):
        assert prompts[0].timestamp == "2026-04-10T14:01:00Z"
        assert prompts[1].timestamp == "2026-04-10T14:05:00Z"

    def test_falls_back_to_session_timestamp(self, prompts):
        # Last user message has no timestamp; should fall back to startTime
        assert prompts[2].timestamp == "2026-04-10T14:00:00Z"

    def test_skips_gemini_type_messages(self, prompts):
        texts = [p.text for p in prompts]
        assert not any("restructure the middleware" in t for t in texts)

    def test_sequential_indices(self, prompts):
        assert [p.index for p in prompts] == [0, 1, 2]


# ── Codex fixture ─────────────────────────────────────────────


class TestCodexFixture:
    """Parse the Codex JSONL fixture."""

    @pytest.fixture()
    def prompts(self):
        session = _make_session(FIXTURES_DIR / "codex-sample.jsonl", "codex")
        result = extract_prompts(session)
        assert result is not None
        return result

    def test_extracts_session_meta_only(self, prompts):
        # 2 session_meta entries, both with instructions > 5 chars
        assert len(prompts) == 2

    def test_skips_non_session_meta(self, prompts):
        texts = [p.text for p in prompts]
        assert not any("Starting implementation" in t for t in texts)
        assert not any("write_file" in t for t in texts)

    def test_preserves_payload_timestamp(self, prompts):
        assert prompts[0].timestamp == "2026-04-10T16:00:00Z"
        assert prompts[1].timestamp == "2026-04-10T16:15:00Z"

    def test_extracts_instructions_text(self, prompts):
        assert "caching layer" in prompts[0].text
        assert "LRU eviction" in prompts[1].text

    def test_sequential_indices(self, prompts):
        assert [p.index for p in prompts] == [0, 1]


# ── Cross-format parametrized ─────────────────────────────────


@pytest.mark.parametrize(
    ("fixture_file", "agent", "expected_count"),
    [
        ("claude-sample.jsonl", "claude", 3),
        ("gemini-sample.json", "gemini", 3),
        ("codex-sample.jsonl", "codex", 2),
    ],
    ids=["claude", "gemini", "codex"],
)
class TestCrossFormat:
    """Parametrized checks that apply to all three formats."""

    def test_prompt_count(self, fixture_file, agent, expected_count):
        session = _make_session(FIXTURES_DIR / fixture_file, agent)
        prompts = extract_prompts(session)
        assert prompts is not None
        assert len(prompts) == expected_count

    def test_all_prompts_have_text(self, fixture_file, agent, expected_count):
        session = _make_session(FIXTURES_DIR / fixture_file, agent)
        prompts = extract_prompts(session)
        assert prompts is not None
        for p in prompts:
            assert p.text
            assert len(p.text) > 5

    def test_all_prompts_have_timestamps(self, fixture_file, agent, expected_count):
        session = _make_session(FIXTURES_DIR / fixture_file, agent)
        prompts = extract_prompts(session)
        assert prompts is not None
        for p in prompts:
            assert p.timestamp is not None

    def test_indices_are_sequential(self, fixture_file, agent, expected_count):
        session = _make_session(FIXTURES_DIR / fixture_file, agent)
        prompts = extract_prompts(session)
        assert prompts is not None
        assert [p.index for p in prompts] == list(range(expected_count))
