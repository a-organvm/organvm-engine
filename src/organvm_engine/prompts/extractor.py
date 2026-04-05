"""Enhanced prompt extraction with per-prompt timestamps."""

from __future__ import annotations

import json
from pathlib import Path

from organvm_engine.prompts.schema import RawPrompt
from organvm_engine.session.agents import AgentSession
from organvm_engine.session.analysis import _content_to_text


def extract_prompts(session: AgentSession) -> list[RawPrompt] | None:
    """Extract prompts with timestamps from a session.

    Returns None if session can't be parsed (vs empty list for no prompts).
    """
    path = session.file_path
    if not path.exists():
        return None

    try:
        if session.agent == "claude":
            return _extract_claude(path)
        if session.agent == "gemini":
            return _extract_gemini(path)
        if session.agent == "codex":
            return _extract_codex(path)
    except (OSError, json.JSONDecodeError):
        return None

    return None


def _extract_claude(path: Path) -> list[RawPrompt]:
    """Extract prompts with timestamps from Claude JSONL."""
    prompts: list[RawPrompt] = []
    index = 0

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
            if not text or len(text) <= 5:
                continue

            timestamp = msg.get("timestamp")

            prompts.append(RawPrompt(
                text=text,
                timestamp=timestamp,
                index=index,
            ))
            index += 1

    return prompts


def _extract_gemini(path: Path) -> list[RawPrompt]:
    """Extract prompts from Gemini JSON with per-message timestamps."""
    prompts: list[RawPrompt] = []

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    session_ts = data.get("startTime")
    index = 0

    for msg in data.get("messages", []):
        if msg.get("type") != "user":
            continue
        timestamp = msg.get("timestamp") or session_ts
        parts = msg.get("content", [])
        for part in parts:
            if isinstance(part, dict) and part.get("text"):
                text = part["text"].strip()
                if len(text) > 5:
                    prompts.append(RawPrompt(
                        text=text,
                        timestamp=timestamp,
                        index=index,
                    ))
                    index += 1

    return prompts


def _extract_codex(path: Path) -> list[RawPrompt]:
    """Extract prompts from Codex JSONL."""
    prompts: list[RawPrompt] = []
    index = 0

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
                continue

            payload = entry.get("payload", {})
            text = payload.get("instructions", "")
            timestamp = payload.get("timestamp") or entry.get("timestamp")

            if text and len(text) > 5:
                prompts.append(RawPrompt(
                    text=text,
                    timestamp=timestamp,
                    index=index,
                ))
                index += 1

    return prompts
