"""Tests for prompts/extractor.py — prompt extraction from session files."""

import json
from pathlib import Path

from organvm_engine.prompts.extractor import extract_prompts
from organvm_engine.session.agents import AgentSession


def _make_session(path: Path, agent: str = "claude") -> AgentSession:
    return AgentSession(
        session_id="test-session",
        agent=agent,
        file_path=path,
        project_dir="/Workspace/test-project",
        started=None,
        ended=None,
        size_bytes=0,
    )


# ── Claude extraction ──────────────────────────────────────────


class TestExtractClaude:
    def test_basic_extraction(self, tmp_path):
        session_file = tmp_path / "session.jsonl"
        lines = [
            json.dumps({
                "type": "user",
                "timestamp": "2026-03-01T10:00:00Z",
                "message": {"content": "implement the feature"},
            }),
            json.dumps({
                "type": "assistant",
                "message": {"content": "Sure, let me work on that."},
            }),
            json.dumps({
                "type": "user",
                "timestamp": "2026-03-01T10:05:00Z",
                "message": {"content": "now add tests for it"},
            }),
        ]
        session_file.write_text("\n".join(lines))

        session = _make_session(session_file, "claude")
        prompts = extract_prompts(session)

        assert prompts is not None
        assert len(prompts) == 2
        assert prompts[0].text == "implement the feature"
        assert prompts[0].timestamp == "2026-03-01T10:00:00Z"
        assert prompts[0].index == 0
        assert prompts[1].text == "now add tests for it"
        assert prompts[1].index == 1

    def test_skips_short_text(self, tmp_path):
        session_file = tmp_path / "session.jsonl"
        lines = [
            json.dumps({
                "type": "user",
                "message": {"content": "ok"},
            }),
        ]
        session_file.write_text("\n".join(lines))

        session = _make_session(session_file, "claude")
        prompts = extract_prompts(session)
        assert prompts == []

    def test_handles_list_content(self, tmp_path):
        session_file = tmp_path / "session.jsonl"
        lines = [
            json.dumps({
                "type": "user",
                "message": {"content": [{"type": "text", "text": "implement the feature please"}]},
            }),
        ]
        session_file.write_text("\n".join(lines))

        session = _make_session(session_file, "claude")
        prompts = extract_prompts(session)
        assert prompts is not None
        assert len(prompts) == 1

    def test_skips_assistant_messages(self, tmp_path):
        session_file = tmp_path / "session.jsonl"
        lines = [
            json.dumps({
                "type": "assistant",
                "message": {"content": "I will help you with that task now"},
            }),
        ]
        session_file.write_text("\n".join(lines))

        session = _make_session(session_file, "claude")
        prompts = extract_prompts(session)
        assert prompts == []

    def test_empty_file(self, tmp_path):
        session_file = tmp_path / "session.jsonl"
        session_file.write_text("")

        session = _make_session(session_file, "claude")
        prompts = extract_prompts(session)
        assert prompts == []

    def test_nonexistent_file(self, tmp_path):
        session = _make_session(tmp_path / "missing.jsonl", "claude")
        prompts = extract_prompts(session)
        assert prompts is None

    def test_invalid_json(self, tmp_path):
        session_file = tmp_path / "session.jsonl"
        session_file.write_text("not valid json\n")

        session = _make_session(session_file, "claude")
        prompts = extract_prompts(session)
        assert prompts == []


# ── Gemini extraction ──────────────────────────────────────────


class TestExtractGemini:
    def test_basic_extraction(self, tmp_path):
        session_file = tmp_path / "session.json"
        data = {
            "startTime": "2026-03-01T10:00:00Z",
            "messages": [
                {
                    "type": "user",
                    "timestamp": "2026-03-01T10:01:00Z",
                    "content": [{"text": "implement the feature for me"}],
                },
                {
                    "type": "gemini",
                    "content": [{"text": "Working on it..."}],
                },
                {
                    "type": "user",
                    "timestamp": "2026-03-01T10:05:00Z",
                    "content": [{"text": "add tests for it too"}],
                },
            ],
        }
        session_file.write_text(json.dumps(data))

        session = _make_session(session_file, "gemini")
        prompts = extract_prompts(session)

        assert prompts is not None
        assert len(prompts) == 2
        assert prompts[0].text == "implement the feature for me"
        assert prompts[0].timestamp == "2026-03-01T10:01:00Z"
        assert prompts[1].text == "add tests for it too"
        assert prompts[1].timestamp == "2026-03-01T10:05:00Z"
        assert prompts[1].index == 1

    def test_falls_back_to_session_timestamp(self, tmp_path):
        session_file = tmp_path / "session.json"
        data = {
            "startTime": "2026-03-01T10:00:00Z",
            "messages": [
                {
                    "type": "user",
                    "content": [{"text": "no per-message timestamp here"}],
                },
            ],
        }
        session_file.write_text(json.dumps(data))

        session = _make_session(session_file, "gemini")
        prompts = extract_prompts(session)
        assert len(prompts) == 1
        assert prompts[0].timestamp == "2026-03-01T10:00:00Z"

    def test_skips_non_user_types(self, tmp_path):
        session_file = tmp_path / "session.json"
        data = {
            "startTime": "2026-03-01T10:00:00Z",
            "messages": [
                {"type": "info", "content": "MCP issues detected."},
                {"type": "error", "content": "Server name required."},
                {"type": "gemini", "content": [{"text": "assistant response text here"}]},
            ],
        }
        session_file.write_text(json.dumps(data))

        session = _make_session(session_file, "gemini")
        prompts = extract_prompts(session)
        assert prompts == []

    def test_skips_short_text(self, tmp_path):
        session_file = tmp_path / "session.json"
        data = {
            "startTime": "2026-03-01T10:00:00Z",
            "messages": [{"type": "user", "content": [{"text": "yes"}]}],
        }
        session_file.write_text(json.dumps(data))

        session = _make_session(session_file, "gemini")
        prompts = extract_prompts(session)
        assert prompts == []

    def test_no_messages(self, tmp_path):
        session_file = tmp_path / "session.json"
        data = {"startTime": "2026-03-01T10:00:00Z", "messages": []}
        session_file.write_text(json.dumps(data))

        session = _make_session(session_file, "gemini")
        prompts = extract_prompts(session)
        assert prompts == []


# ── Codex extraction ───────────────────────────────────────────


class TestExtractCodex:
    def test_basic_extraction(self, tmp_path):
        session_file = tmp_path / "session.jsonl"
        lines = [
            json.dumps({
                "type": "session_meta",
                "payload": {
                    "instructions": "implement the feature for the system",
                    "timestamp": "2026-03-01T10:00:00Z",
                },
            }),
            json.dumps({
                "type": "response_item",
                "payload": {"text": "response data"},
            }),
        ]
        session_file.write_text("\n".join(lines))

        session = _make_session(session_file, "codex")
        prompts = extract_prompts(session)

        assert prompts is not None
        assert len(prompts) == 1
        assert prompts[0].text == "implement the feature for the system"
        assert prompts[0].timestamp == "2026-03-01T10:00:00Z"

    def test_skips_non_session_meta(self, tmp_path):
        session_file = tmp_path / "session.jsonl"
        lines = [
            json.dumps({
                "type": "response_item",
                "payload": {"text": "some response data here for the system"},
            }),
        ]
        session_file.write_text("\n".join(lines))

        session = _make_session(session_file, "codex")
        prompts = extract_prompts(session)
        assert prompts == []

    def test_short_instructions_skipped(self, tmp_path):
        session_file = tmp_path / "session.jsonl"
        lines = [
            json.dumps({
                "type": "session_meta",
                "payload": {"instructions": "ok"},
            }),
        ]
        session_file.write_text("\n".join(lines))

        session = _make_session(session_file, "codex")
        prompts = extract_prompts(session)
        assert prompts == []


# ── Unknown agent ────────────────────────────────────────────


class TestUnknownAgent:
    def test_returns_none(self, tmp_path):
        session_file = tmp_path / "session.jsonl"
        session_file.write_text("{}\n")

        session = _make_session(session_file, "unknown-agent")
        prompts = extract_prompts(session)
        assert prompts is None
