"""Sonic renderer — system metrics as synthesizer parameters.

Converts ORGANVM's operational data into parameter sets for the
alchemical-synthesizer (SuperCollider). The system plays itself.

Output format: YAML readable by BrahmaModBus.sc via OSC bridge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class OscillatorVoice:
    """A single voice in the sonic self-portrait."""

    organ: str
    frequency: float  # Hz — derived from organ density
    amplitude: float  # 0-1 — derived from repo count / total
    waveform: str  # sine|saw|square|tri — derived from promotion status mix
    detune: float  # cents — derived from dependency depth
    pan: float  # -1 to 1 — position in stereo field


@dataclass
class EnvelopeParams:
    """ADSR envelope derived from system velocity."""

    attack: float  # seconds — inverse of promotion velocity
    decay: float  # seconds — time since last omega change
    sustain: float  # 0-1 — ratio of graduated repos
    release: float  # seconds — archive rate


@dataclass
class FilterParams:
    """Filter derived from system health."""

    cutoff: float  # Hz — test pass rate maps to openness
    resonance: float  # 0-1 — AMMOI density
    type: str  # lowpass|bandpass|highpass


@dataclass
class RhythmParams:
    """Rhythmic parameters from system cadence."""

    bpm: float  # beats per minute — event rate
    time_signature: str  # based on organ count
    swing: float  # 0-1 — distribution asymmetry


@dataclass
class SonicTestament:
    """Complete sonic self-portrait of the system."""

    generated: str
    voices: list[OscillatorVoice] = field(default_factory=list)
    envelope: EnvelopeParams | None = None
    filter: FilterParams | None = None
    rhythm: RhythmParams | None = None
    master_amplitude: float = 0.5
    note: str = ""


# ---------------------------------------------------------------------------
# Mapping constants
# ---------------------------------------------------------------------------

# Base frequencies for organ voices (pentatonic-ish, spanning 2 octaves)
ORGAN_BASE_FREQUENCIES: dict[str, float] = {
    "META": 220.0,   # A3 — constitutional substrate, root
    "I": 261.63,     # C4 — theory, middle ground
    "II": 293.66,    # D4 — art/creation
    "III": 329.63,   # E4 — commerce
    "IV": 392.0,     # G4 — orchestration
    "V": 440.0,      # A4 — discourse, the concert pitch
    "VI": 493.88,    # B4 — community
    "VII": 523.25,   # C5 — distribution, octave above theory
}

WAVEFORM_MAP: dict[str, str] = {
    "GRADUATED": "sine",       # smooth, resolved
    "PUBLIC_PROCESS": "tri",   # transitional
    "CANDIDATE": "saw",        # raw, rich harmonics
    "LOCAL": "square",         # angular, unrefined
    "ARCHIVED": "sine",        # quiet, resolved differently
}


def render_sonic_params(
    organ_densities: dict[str, float] | None = None,
    organ_repo_counts: dict[str, int] | None = None,
    status_distribution: dict[str, int] | None = None,
    met_ratio: float | None = None,
    dep_depth: int | None = None,
    total_repos: int | None = None,
    event_rate: float | None = None,
) -> SonicTestament:
    """Render system metrics as synthesizer parameters.

    Each organ becomes a voice. System health shapes the filter.
    Promotion velocity shapes the envelope. Event rate drives rhythm.
    """
    densities = organ_densities or {}
    counts = organ_repo_counts or {}
    statuses = status_distribution or {}
    total = total_repos or sum(counts.values()) or 113
    omega_ratio = met_ratio if met_ratio is not None else 0.47
    depth = dep_depth or 3
    rate = event_rate or 60.0

    # Build voices — one per organ
    voices: list[OscillatorVoice] = []
    organ_keys = ["META", "I", "II", "III", "IV", "V", "VI", "VII"]

    for i, key in enumerate(organ_keys):
        density = densities.get(key, 0.5)
        count = counts.get(key, 10)
        base_freq = ORGAN_BASE_FREQUENCIES.get(key, 440.0)

        # Frequency: base + density-driven deviation (±1 semitone)
        freq = base_freq * (2 ** (density * 0.08 - 0.04))

        # Amplitude: proportional to repo count
        amp = min(1.0, count / total * 3) * 0.7

        # Waveform: dominant status in this organ
        waveform = _dominant_waveform(statuses)

        # Detune: dependency depth adds slight detuning
        detune = depth * 2.5

        # Pan: spread across stereo field
        pan = -1.0 + (2.0 * i / (len(organ_keys) - 1))

        voices.append(OscillatorVoice(
            organ=key,
            frequency=round(freq, 2),
            amplitude=round(amp, 3),
            waveform=waveform,
            detune=round(detune, 1),
            pan=round(pan, 2),
        ))

    # Envelope from system velocity
    graduated = statuses.get("GRADUATED", 0)
    graduated_ratio = graduated / total if total else 0.5
    envelope = EnvelopeParams(
        attack=max(0.01, 1.0 - omega_ratio),  # faster attack = healthier
        decay=0.5,
        sustain=round(graduated_ratio, 3),
        release=2.0,
    )

    # Filter from system health
    test_health = omega_ratio  # proxy for overall health
    filter_params = FilterParams(
        cutoff=round(200 + test_health * 8000, 1),  # healthy = open filter
        resonance=round(min(1.0, sum(densities.values()) / 8), 3),
        type="lowpass",
    )

    # Rhythm from event rate
    bpm = max(40, min(200, rate * 2))
    rhythm = RhythmParams(
        bpm=round(bpm, 1),
        time_signature="7/8" if len(organ_keys) == 8 else "4/4",
        swing=round(0.5 + (graduated_ratio - 0.5) * 0.3, 3),
    )

    # Master amplitude from AMMOI
    avg_density = sum(densities.values()) / len(densities) if densities else 0.5
    master = round(min(0.9, avg_density * 1.2), 3)

    return SonicTestament(
        generated=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        voices=voices,
        envelope=envelope,
        filter=filter_params,
        rhythm=rhythm,
        master_amplitude=master,
        note=(
            f"Sonic self-portrait: {total} repos across {len(organ_keys)} organs. "
            f"Omega {omega_ratio:.0%}. AMMOI avg {avg_density:.0%}."
        ),
    )


def render_sonic_yaml(testament: SonicTestament) -> str:
    """Render SonicTestament as YAML for BrahmaModBus.sc consumption."""
    lines = [
        "# ORGANVM Sonic Testament",
        f"# Generated: {testament.generated}",
        f"# {testament.note}",
        "",
        "testament:",
        f"  master_amplitude: {testament.master_amplitude}",
        f"  generated: \"{testament.generated}\"",
        "",
        "  voices:",
    ]

    for v in testament.voices:
        lines.extend([
            f"    - organ: {v.organ}",
            f"      frequency: {v.frequency}",
            f"      amplitude: {v.amplitude}",
            f"      waveform: {v.waveform}",
            f"      detune: {v.detune}",
            f"      pan: {v.pan}",
        ])

    if testament.envelope:
        e = testament.envelope
        lines.extend([
            "",
            "  envelope:",
            f"    attack: {e.attack}",
            f"    decay: {e.decay}",
            f"    sustain: {e.sustain}",
            f"    release: {e.release}",
        ])

    if testament.filter:
        f = testament.filter
        lines.extend([
            "",
            "  filter:",
            f"    cutoff: {f.cutoff}",
            f"    resonance: {f.resonance}",
            f"    type: {f.type}",
        ])

    if testament.rhythm:
        r = testament.rhythm
        lines.extend([
            "",
            "  rhythm:",
            f"    bpm: {r.bpm}",
            f"    time_signature: \"{r.time_signature}\"",
            f"    swing: {r.swing}",
        ])

    lines.append("")
    return "\n".join(lines)


def render_osc_messages(testament: SonicTestament) -> list[str]:
    """Render as OSC message commands for SuperCollider."""
    msgs: list[str] = []
    msgs.append(f"/testament/master {testament.master_amplitude}")

    if testament.rhythm:
        msgs.append(f"/testament/bpm {testament.rhythm.bpm}")

    if testament.envelope:
        e = testament.envelope
        msgs.append(f"/testament/env {e.attack} {e.decay} {e.sustain} {e.release}")

    if testament.filter:
        f = testament.filter
        msgs.append(f"/testament/filter {f.cutoff} {f.resonance}")

    for i, v in enumerate(testament.voices):
        msgs.append(
            f"/testament/voice/{i} {v.frequency} {v.amplitude} "
            f"{v.waveform} {v.detune} {v.pan}",
        )

    return msgs


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dominant_waveform(status_dist: dict[str, int]) -> str:
    """Determine waveform from the most common promotion status."""
    if not status_dist:
        return "saw"
    dominant = max(status_dist, key=lambda k: status_dist[k])
    return WAVEFORM_MAP.get(dominant, "saw")
