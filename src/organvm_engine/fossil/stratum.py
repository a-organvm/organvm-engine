"""Stratum — data models for the fossil record.

FossilRecord is the atomic unit: one commit, normalized, classified,
and hash-linked to the previous record for tamper evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum


class Archetype(str, Enum):
    """Jungian archetypes for classifying system activity."""

    SHADOW = "shadow"
    ANIMA = "anima"
    ANIMUS = "animus"
    SELF = "self"
    TRICKSTER = "trickster"
    MOTHER = "mother"
    FATHER = "father"
    INDIVIDUATION = "individuation"


class Provenance(str, Enum):
    """How the record was obtained."""

    WITNESSED = "witnessed"
    RECONSTRUCTED = "reconstructed"
    ATTESTED = "attested"


@dataclass
class FossilRecord:
    """One commit, normalized and classified."""

    commit_sha: str
    timestamp: datetime
    author: str
    organ: str
    repo: str
    message: str
    conventional_type: str
    files_changed: int
    insertions: int
    deletions: int
    archetypes: list[Archetype]
    provenance: Provenance
    session_id: str | None
    epoch: str | None
    tags: list[str]
    prev_hash: str


def compute_record_hash(record: FossilRecord) -> str:
    """SHA256 of the record's content for chain linking."""
    content = (
        f"{record.commit_sha}|{record.timestamp.isoformat()}"
        f"|{record.organ}|{record.repo}|{record.message}"
        f"|{record.prev_hash}"
    )
    return hashlib.sha256(content.encode()).hexdigest()


def serialize_record(record: FossilRecord) -> str:
    """Serialize to a single JSON line."""
    d = asdict(record)
    d["timestamp"] = record.timestamp.isoformat()
    d["archetypes"] = [a.value for a in record.archetypes]
    d["provenance"] = record.provenance.value
    return json.dumps(d, separators=(",", ":"))


def deserialize_record(line: str) -> FossilRecord:
    """Deserialize from a JSON line."""
    d = json.loads(line)
    d["timestamp"] = datetime.fromisoformat(d["timestamp"])
    d["archetypes"] = [Archetype(a) for a in d["archetypes"]]
    d["provenance"] = Provenance(d["provenance"])
    return FossilRecord(**d)
