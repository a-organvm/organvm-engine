"""Data structures for network testament system."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MirrorEntry:
    """A single external project/community mirrored by an ORGANVM repo."""

    project: str
    platform: str  # github | community | forum | mailing-list | discord | etc.
    relevance: str  # why this mirror exists
    engagement: list[str] = field(default_factory=list)  # active engagement forms
    url: str | None = None  # explicit URL if not derivable from project+platform
    tags: list[str] = field(default_factory=list)
    notes: str | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "project": self.project,
            "platform": self.platform,
            "relevance": self.relevance,
            "engagement": self.engagement,
        }
        if self.url:
            d["url"] = self.url
        if self.tags:
            d["tags"] = self.tags
        if self.notes:
            d["notes"] = self.notes
        return d

    @classmethod
    def from_dict(cls, data: dict) -> MirrorEntry:
        return cls(
            project=data["project"],
            platform=data.get("platform", "github"),
            relevance=data.get("relevance", ""),
            engagement=data.get("engagement", []),
            url=data.get("url"),
            tags=data.get("tags", []),
            notes=data.get("notes"),
        )


@dataclass
class NetworkMap:
    """Full network map for a single ORGANVM repo."""

    schema_version: str
    repo: str
    organ: str
    technical: list[MirrorEntry] = field(default_factory=list)
    parallel: list[MirrorEntry] = field(default_factory=list)
    kinship: list[MirrorEntry] = field(default_factory=list)
    ledger: str = "~/.organvm/network/ledger.jsonl"
    last_scanned: str | None = None

    @property
    def all_mirrors(self) -> list[MirrorEntry]:
        return self.technical + self.parallel + self.kinship

    @property
    def mirror_count(self) -> int:
        return len(self.all_mirrors)

    def mirrors_by_lens(self, lens: str) -> list[MirrorEntry]:
        return getattr(self, lens, [])

    def to_dict(self) -> dict:
        d: dict = {
            "schema_version": self.schema_version,
            "repo": self.repo,
            "organ": self.organ,
            "mirrors": {
                "technical": [m.to_dict() for m in self.technical],
                "parallel": [m.to_dict() for m in self.parallel],
                "kinship": [m.to_dict() for m in self.kinship],
            },
            "ledger": self.ledger,
            "last_scanned": self.last_scanned,
        }
        return d

    @classmethod
    def from_dict(cls, data: dict) -> NetworkMap:
        mirrors = data.get("mirrors", {})
        return cls(
            schema_version=data.get("schema_version", "1.0"),
            repo=data["repo"],
            organ=data.get("organ", ""),
            technical=[MirrorEntry.from_dict(m) for m in mirrors.get("technical", [])],
            parallel=[MirrorEntry.from_dict(m) for m in mirrors.get("parallel", [])],
            kinship=[MirrorEntry.from_dict(m) for m in mirrors.get("kinship", [])],
            ledger=data.get("ledger", "~/.organvm/network/ledger.jsonl"),
            last_scanned=data.get("last_scanned"),
        )


@dataclass
class EngagementEntry:
    """A single engagement action recorded in the ledger."""

    timestamp: str  # ISO 8601
    organvm_repo: str  # which ORGANVM repo this relates to
    external_project: str  # the mirror target
    lens: str  # technical | parallel | kinship
    action_type: str  # presence | contribution | dialogue | invitation
    action_detail: str  # human-readable description
    url: str | None = None  # link to the action
    outcome: str | None = None  # response, merged, rejected, etc.
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict = {
            "timestamp": self.timestamp,
            "organvm_repo": self.organvm_repo,
            "external_project": self.external_project,
            "lens": self.lens,
            "action_type": self.action_type,
            "action_detail": self.action_detail,
        }
        if self.url:
            d["url"] = self.url
        if self.outcome:
            d["outcome"] = self.outcome
        if self.tags:
            d["tags"] = self.tags
        return d

    @classmethod
    def from_dict(cls, data: dict) -> EngagementEntry:
        return cls(
            timestamp=data["timestamp"],
            organvm_repo=data["organvm_repo"],
            external_project=data["external_project"],
            lens=data.get("lens", "technical"),
            action_type=data.get("action_type", "presence"),
            action_detail=data.get("action_detail", ""),
            url=data.get("url"),
            outcome=data.get("outcome"),
            tags=data.get("tags", []),
        )
