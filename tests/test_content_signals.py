"""Tests for content moment signal detection."""

from __future__ import annotations

from organvm_engine.content.signals import ContentSignal, detect_content_signals


def test_detect_signals_empty_messages():
    signals = detect_content_signals([])
    assert signals == []


def test_detect_voice_shift():
    """A message 3x longer than median should trigger voice_shift."""
    messages = [
        "do X",
        "fix Y",
        "run tests",
        "I've been thinking about this architecture all week. The way the organs "
        "connect reminds me of something I read about cathedral builders — they never "
        "saw the finished product either. But they kept laying stones. That's what "
        "this feels like. Every repo is a stone and the cathedral is taking shape even "
        "if I can't see the whole thing yet.",
    ]
    signals = detect_content_signals(messages)
    voice_shifts = [s for s in signals if s.signal_type == "voice_shift"]
    assert len(voice_shifts) >= 1
    assert voice_shifts[0].prompt_index == 4


def test_detect_standalone_power():
    """Short metaphorical sentences should trigger standalone_power."""
    messages = [
        "Trash and church exist in the same space.",
        "run the tests",
    ]
    signals = detect_content_signals(messages)
    standalone = [s for s in signals if s.signal_type == "standalone_power"]
    assert len(standalone) >= 1


def test_detect_emotional_resonance():
    """First-person emotional language should trigger emotional_resonance."""
    messages = [
        "I feel like this is the first time the system actually represents what I'm trying to build.",
    ]
    signals = detect_content_signals(messages)
    emotional = [s for s in signals if s.signal_type == "emotional_resonance"]
    assert len(emotional) >= 1


def test_detect_architectural_connection():
    """Mentioning multiple organs/repos should trigger architectural_connection."""
    messages = [
        "The way ORGAN-I feeds into ORGAN-II and then ORGAN-III picks up the "
        "commercial output — that's the real pipeline. It's not just code.",
    ]
    signals = detect_content_signals(messages)
    arch = [s for s in signals if s.signal_type == "architectural_connection"]
    assert len(arch) >= 1


def test_signals_sorted_by_strength():
    """High signals should come before medium and low."""
    messages = [
        "do X",
        "do Y",
        "do Z",
        "I've been thinking about this all week and I feel like the connection "
        "between ORGAN-I and ORGAN-II is actually the heart of the whole system. "
        "This is what matters. Not the code but the soul of it.",
    ]
    signals = detect_content_signals(messages)
    if len(signals) >= 2:
        strengths = [s.strength for s in signals]
        strength_order = {"high": 0, "medium": 1, "low": 2}
        ordered = sorted(strengths, key=lambda s: strength_order.get(s, 3))
        assert strengths == ordered


def test_no_false_positives_on_directives():
    """Short directive messages should not trigger signals."""
    messages = ["run tests", "fix the bug", "commit", "push to main"]
    signals = detect_content_signals(messages)
    assert signals == []


def test_signal_has_excerpt():
    messages = [
        "Trash and church exist in the same space.",
    ]
    signals = detect_content_signals(messages)
    if signals:
        assert signals[0].excerpt
        assert len(signals[0].excerpt) <= 120
