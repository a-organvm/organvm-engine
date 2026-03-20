"""Artifact catalog — append-only JSONL registry of all rendered artifacts.

Every artifact the testament pipeline produces gets cataloged here.
The catalog is the historical record: what was rendered, when, from
which module, for which organ, in what format.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from organvm_engine.testament.manifest import ArtifactFormat, ArtifactModality

logger = logging.getLogger(__name__)

_DEFAULT_CATALOG_DIR = Path.home() / ".organvm" / "testament"


@dataclass
class TestamentArtifact:
    """A single rendered artifact in the testament catalog."""

    modality: ArtifactModality
    format: ArtifactFormat
    source_module: str
    title: str
    description: str
    path: str
    organ: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        d = asdict(self)
        d["modality"] = self.modality.value
        d["format"] = self.format.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> TestamentArtifact:
        """Deserialize from a JSON-compatible dict."""
        return cls(
            id=data.get("id", uuid.uuid4().hex[:12]),
            modality=ArtifactModality(data["modality"]),
            format=ArtifactFormat(data["format"]),
            source_module=data["source_module"],
            organ=data.get("organ"),
            title=data["title"],
            description=data["description"],
            path=data["path"],
            timestamp=data.get(
                "timestamp",
                datetime.now(timezone.utc).isoformat(),
            ),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class CatalogSummary:
    """Aggregate statistics over a set of catalog artifacts."""

    total: int
    by_modality: dict[str, int]
    by_organ: dict[str, int]
    by_format: dict[str, int]
    latest_timestamp: str | None


def _catalog_path(base_dir: Path | None = None) -> Path:
    """Return the path to the testament catalog JSONL file."""
    d = base_dir or _DEFAULT_CATALOG_DIR
    return d / "testament-catalog.jsonl"


def append_artifact(
    artifact: TestamentArtifact,
    base_dir: Path | None = None,
) -> None:
    """Append a single artifact record to the catalog JSONL."""
    path = _catalog_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(artifact.to_dict()) + "\n")
    logger.debug("Cataloged artifact %s at %s", artifact.id, path)


def load_catalog(base_dir: Path | None = None) -> list[TestamentArtifact]:
    """Read all artifacts from the catalog JSONL."""
    path = _catalog_path(base_dir)
    if not path.is_file():
        return []
    artifacts: list[TestamentArtifact] = []
    with path.open() as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                artifacts.append(TestamentArtifact.from_dict(data))
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                logger.warning(
                    "Skipping malformed catalog entry at line %d: %s",
                    line_num,
                    exc,
                )
    return artifacts


def catalog_summary(artifacts: list[TestamentArtifact]) -> CatalogSummary:
    """Compute aggregate counts over a list of catalog artifacts."""
    by_modality: dict[str, int] = {}
    by_organ: dict[str, int] = {}
    by_format: dict[str, int] = {}
    latest: str | None = None

    for a in artifacts:
        mod_key = a.modality.value
        by_modality[mod_key] = by_modality.get(mod_key, 0) + 1

        org_key = a.organ or "unassigned"
        by_organ[org_key] = by_organ.get(org_key, 0) + 1

        fmt_key = a.format.value
        by_format[fmt_key] = by_format.get(fmt_key, 0) + 1

        if latest is None or a.timestamp > latest:
            latest = a.timestamp

    return CatalogSummary(
        total=len(artifacts),
        by_modality=by_modality,
        by_organ=by_organ,
        by_format=by_format,
        latest_timestamp=latest,
    )
