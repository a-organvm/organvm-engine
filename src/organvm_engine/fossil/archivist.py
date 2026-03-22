"""The Archivist — captures unique prompts as intentions.

First-time articulations of creative will are fingerprinted, scored for
uniqueness against existing intentions via Jaccard similarity, and
classified by Jungian archetype.

Serialization uses hand-written YAML (no PyYAML dependency).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from organvm_engine.fossil.classifier import classify_commit
from organvm_engine.fossil.stratum import Archetype, Provenance

# Filler phrases stripped during normalization, ordered longest-first
# so "okay so" is removed before "okay" would be (if it were listed).
_FILLER_PHRASES: list[str] = [
    "okay so",
    "can you",
    "could you",
    "i want to",
    "i'd like to",
    "i would like to",
    "please",
    "let's",
    "lets",
    "okay",
]


@dataclass
class Intention:
    """A unique prompt captured as an intention."""

    id: str  # INT-YYYY-MM-DD-NNN
    timestamp: datetime
    raw_text: str  # exact prompt, verbatim
    fingerprint: str  # SHA256 of normalized text
    uniqueness_score: float  # 0.0-1.0
    archetypes: list[Archetype]  # from classifier
    session_id: str | None
    epoch: str | None
    provenance: Provenance
    source_file: str | None  # path to session file
    tags: list[str]


# ---------------------------------------------------------------------------
# Normalization and fingerprinting
# ---------------------------------------------------------------------------


def normalize_prompt(text: str) -> str:
    """Lowercase, collapse whitespace, strip filler words/phrases.

    Returns cleaned text suitable for fingerprinting.
    """
    cleaned = text.lower().strip()
    # Strip filler phrases (longest first to avoid partial matches)
    for phrase in _FILLER_PHRASES:
        cleaned = cleaned.replace(phrase, " ")
    # Collapse whitespace
    return re.sub(r"\s+", " ", cleaned).strip()


def fingerprint_prompt(text: str) -> str:
    """SHA256 hex digest of the normalized prompt text."""
    normalized = normalize_prompt(text)
    return hashlib.sha256(normalized.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Uniqueness scoring
# ---------------------------------------------------------------------------


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Jaccard similarity of two word sets."""
    if not a and not b:
        return 1.0
    intersection = a & b
    union = a | b
    if not union:
        return 1.0
    return len(intersection) / len(union)


def compute_uniqueness(
    fingerprint: str,
    text: str,
    existing: list[Intention],
) -> float:
    """Score how unique this prompt is vs all existing intentions.

    Uses Jaccard similarity of word sets.  Returns 1.0 - max_similarity.
    If no existing intentions, returns 1.0.
    """
    if not existing:
        return 1.0
    words_new = set(normalize_prompt(text).split())
    max_sim = 0.0
    for intention in existing:
        words_existing = set(normalize_prompt(intention.raw_text).split())
        sim = _jaccard_similarity(words_new, words_existing)
        max_sim = max(max_sim, sim)
    return 1.0 - max_sim


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_intention(text: str) -> list[Archetype]:
    """Classify an intention prompt into ranked Jungian archetypes.

    Reuses the commit classifier — creative prompts trigger Anima,
    structural prompts trigger Animus, self-referential prompts trigger
    Self, etc.
    """
    return classify_commit(
        message=text,
        conventional_type="",
        repo="",
        organ="",
    )


# ---------------------------------------------------------------------------
# Session extraction
# ---------------------------------------------------------------------------


def extract_intentions(
    session_dir: Path,
    existing: list[Intention],
) -> list[Intention]:
    """Scan a session log directory for JSONL files and extract intentions.

    For each human message with >50 characters, compute uniqueness.
    If uniqueness > 0.7, create an Intention with auto-incrementing ID
    per day: INT-YYYY-MM-DD-001, INT-YYYY-MM-DD-002, etc.
    """
    results: list[Intention] = []
    # Track per-day counters for ID generation
    day_counters: dict[str, int] = {}

    # Count existing intentions per day to avoid ID collisions
    for intention in existing:
        day_key = intention.timestamp.strftime("%Y-%m-%d")
        current = day_counters.get(day_key, 0)
        # Parse the NNN suffix from the existing ID
        parts = intention.id.rsplit("-", 1)
        if len(parts) == 2:
            try:
                num = int(parts[1])
                current = max(current, num)
            except ValueError:
                pass
        day_counters[day_key] = current

    if not session_dir.is_dir():
        return results

    for path in sorted(session_dir.glob("*.jsonl")):
        _extract_from_jsonl(path, existing + results, day_counters, results)

    return results


def _extract_from_jsonl(
    path: Path,
    all_existing: list[Intention],
    day_counters: dict[str, int],
    results: list[Intention],
) -> None:
    """Extract intentions from a single JSONL session file."""
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
    except (OSError, UnicodeDecodeError):
        return

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Look for human messages in common session formats
        role = entry.get("role", "")
        content = entry.get("content", "")
        if role not in ("human", "user") or not isinstance(content, str):
            continue
        if len(content) <= 50:
            continue

        fp = fingerprint_prompt(content)
        uniqueness = compute_uniqueness(fp, content, all_existing)
        if uniqueness <= 0.7:
            continue

        # Generate timestamp — use entry timestamp if available, else now
        ts_str = entry.get("timestamp")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                ts = datetime.now(timezone.utc)
        else:
            ts = datetime.now(timezone.utc)

        # Auto-increment ID per day
        day_key = ts.strftime("%Y-%m-%d")
        counter = day_counters.get(day_key, 0) + 1
        day_counters[day_key] = counter
        intention_id = f"INT-{day_key}-{counter:03d}"

        archetypes = classify_intention(content)

        intention = Intention(
            id=intention_id,
            timestamp=ts,
            raw_text=content,
            fingerprint=fp,
            uniqueness_score=uniqueness,
            archetypes=archetypes,
            session_id=None,
            epoch=None,
            provenance=Provenance.RECONSTRUCTED,
            source_file=str(path),
            tags=[],
        )
        results.append(intention)
        all_existing.append(intention)


# ---------------------------------------------------------------------------
# YAML serialization (hand-written, no PyYAML dependency)
# ---------------------------------------------------------------------------


def serialize_intention(intention: Intention) -> str:
    """Serialize an Intention to a YAML string (no PyYAML required)."""
    lines: list[str] = []
    lines.append(f"id: {intention.id}")
    lines.append(f"timestamp: {intention.timestamp.isoformat()}")

    # raw_text: use YAML block scalar for multi-line, quoted for single-line
    if "\n" in intention.raw_text:
        lines.append("raw_text: |")
        for raw_line in intention.raw_text.splitlines():
            lines.append(f"  {raw_line}")
    else:
        lines.append(f"raw_text: {_yaml_quote(intention.raw_text)}")

    lines.append(f"fingerprint: {intention.fingerprint}")
    lines.append(f"uniqueness_score: {intention.uniqueness_score}")
    lines.append(
        f"archetypes: [{', '.join(a.value for a in intention.archetypes)}]",
    )
    lines.append(
        f"session_id: {_yaml_null_or_val(intention.session_id)}",
    )
    lines.append(f"epoch: {_yaml_null_or_val(intention.epoch)}")
    lines.append(f"provenance: {intention.provenance.value}")
    lines.append(
        f"source_file: {_yaml_null_or_val(intention.source_file)}",
    )
    lines.append(f"tags: [{', '.join(intention.tags)}]")
    return "\n".join(lines) + "\n"


def _yaml_quote(s: str) -> str:
    """Quote a string if it contains special YAML characters."""
    if any(c in s for c in (":", "#", "'", '"', "[", "]", "{", "}", ",")):
        escaped = s.replace('"', '\\"')
        return f'"{escaped}"'
    return s


def _yaml_null_or_val(val: str | None) -> str:
    """Return 'null' for None, otherwise the value."""
    if val is None:
        return "null"
    return val


def deserialize_intention(yaml_str: str) -> Intention:
    """Deserialize an Intention from a hand-written YAML string."""
    data: dict[str, str] = {}
    raw_text_lines: list[str] = []
    in_block_scalar = False

    for line in yaml_str.splitlines():
        if in_block_scalar:
            # Block scalar lines are indented with 2 spaces
            if line.startswith("  "):
                raw_text_lines.append(line[2:])
                continue
            # End of block scalar
            data["raw_text"] = "\n".join(raw_text_lines)
            in_block_scalar = False

        if ": |" in line and line.strip().endswith("|"):
            key = line.split(":")[0].strip()
            if key == "raw_text":
                in_block_scalar = True
                continue

        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            data[key] = val

    # Handle case where block scalar reaches end of string
    if in_block_scalar:
        data["raw_text"] = "\n".join(raw_text_lines)

    # Parse fields
    timestamp = datetime.fromisoformat(data["timestamp"])

    # Parse raw_text: strip surrounding quotes if present
    raw_text = data.get("raw_text", "")
    if raw_text.startswith('"') and raw_text.endswith('"'):
        raw_text = raw_text[1:-1].replace('\\"', '"')

    # Parse archetypes list: "[animus, self]" -> [Archetype.ANIMUS, Archetype.SELF]
    archetypes_str = data.get("archetypes", "[]")
    archetypes_str = archetypes_str.strip("[]")
    archetypes: list[Archetype] = []
    if archetypes_str.strip():
        for part in archetypes_str.split(","):
            part = part.strip()
            if part:
                archetypes.append(Archetype(part))

    # Parse tags list
    tags_str = data.get("tags", "[]")
    tags_str = tags_str.strip("[]")
    tags: list[str] = []
    if tags_str.strip():
        tags = [t.strip() for t in tags_str.split(",") if t.strip()]

    # Parse nullable fields
    session_id = _parse_nullable(data.get("session_id", "null"))
    epoch = _parse_nullable(data.get("epoch", "null"))
    source_file = _parse_nullable(data.get("source_file", "null"))

    return Intention(
        id=data["id"],
        timestamp=timestamp,
        raw_text=raw_text,
        fingerprint=data.get("fingerprint", ""),
        uniqueness_score=float(data.get("uniqueness_score", "0.0")),
        archetypes=archetypes,
        session_id=session_id,
        epoch=epoch,
        provenance=Provenance(data.get("provenance", "reconstructed")),
        source_file=source_file,
        tags=tags,
    )


def _parse_nullable(val: str) -> str | None:
    """Parse a YAML nullable value."""
    if val in ("null", "~", ""):
        return None
    return val


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def load_intentions(intentions_dir: Path) -> list[Intention]:
    """Load all .yaml files from the intentions directory."""
    if not intentions_dir.is_dir():
        return []
    results: list[Intention] = []
    for path in sorted(intentions_dir.glob("*.yaml")):
        try:
            text = path.read_text(encoding="utf-8")
            results.append(deserialize_intention(text))
        except (OSError, KeyError, ValueError):
            continue
    return results


def save_intention(intention: Intention, intentions_dir: Path) -> Path:
    """Write one Intention as a YAML file, return the file path."""
    intentions_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{intention.id}.yaml"
    path = intentions_dir / filename
    path.write_text(serialize_intention(intention), encoding="utf-8")
    return path
