"""Capability declarations — typed evidence-backed abilities per entity.

Implements: SPEC-002, PRIM-007 (Capability)
Resolves: engine #27

A Capability records that a specific entity has a named ability, backed by
evidence (e.g. "CI_PIPELINE" supported by {"workflow_file": ".github/workflows/ci.yml"}).
The CapabilityRegistry is an in-memory dict-based store with declare/revoke/query
operations.  It does not persist to disk — callers are responsible for
serialization if needed.

Predefined capability types:
  DEPLOY, CI_PIPELINE, PUBLISH, PROMOTE, GOVERN
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Predefined capability types
# ---------------------------------------------------------------------------

DEPLOY = "DEPLOY"
CI_PIPELINE = "CI_PIPELINE"
PUBLISH = "PUBLISH"
PROMOTE = "PROMOTE"
GOVERN = "GOVERN"

PREDEFINED_CAPABILITIES: frozenset[str] = frozenset({
    DEPLOY,
    CI_PIPELINE,
    PUBLISH,
    PROMOTE,
    GOVERN,
})


# ---------------------------------------------------------------------------
# Capability record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Capability:
    """A single declared capability for an entity.

    Fields:
        capability_type: The type of capability (e.g. "DEPLOY", "CI_PIPELINE").
        entity_uid:      The ontologia entity UID this capability belongs to.
        evidence:        Structured evidence supporting this capability.
        declared_at:     UTC timestamp when the capability was declared.
    """

    capability_type: str
    entity_uid: str
    evidence: dict[str, Any] = field(default_factory=dict)
    declared_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (datetime → ISO string)."""
        d = asdict(self)
        d["declared_at"] = self.declared_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Capability:
        """Reconstruct from a serialized dict."""
        declared_at = data.get("declared_at")
        if isinstance(declared_at, str):
            declared_at = datetime.fromisoformat(declared_at)
        elif declared_at is None:
            declared_at = datetime.now(timezone.utc)
        return cls(
            capability_type=data.get("capability_type", ""),
            entity_uid=data.get("entity_uid", ""),
            evidence=data.get("evidence", {}),
            declared_at=declared_at,
        )


# ---------------------------------------------------------------------------
# CapabilityRegistry
# ---------------------------------------------------------------------------

class CapabilityRegistry:
    """In-memory registry of entity capabilities.

    Internal structure: ``{entity_uid: {capability_type: Capability}}``.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Capability]] = {}

    # -- Mutators -----------------------------------------------------------

    def declare(
        self,
        entity_uid: str,
        capability_type: str,
        evidence: dict[str, Any] | None = None,
    ) -> Capability:
        """Register a capability for an entity.

        If the capability already exists for this entity, it is replaced
        (evidence and timestamp are updated).

        Args:
            entity_uid:      The entity UID.
            capability_type: Capability type string.
            evidence:        Supporting evidence dict.

        Returns:
            The newly created Capability.

        Raises:
            ValueError: If entity_uid or capability_type is empty.
        """
        if not entity_uid:
            raise ValueError("entity_uid must not be empty")
        if not capability_type:
            raise ValueError("capability_type must not be empty")

        cap = Capability(
            capability_type=capability_type,
            entity_uid=entity_uid,
            evidence=evidence or {},
        )
        self._store.setdefault(entity_uid, {})[capability_type] = cap
        return cap

    def revoke(self, entity_uid: str, capability_type: str) -> bool:
        """Remove a capability from an entity.

        Args:
            entity_uid:      The entity UID.
            capability_type: Capability type to revoke.

        Returns:
            True if the capability existed and was removed, False otherwise.
        """
        entity_caps = self._store.get(entity_uid)
        if entity_caps is None:
            return False
        if capability_type not in entity_caps:
            return False
        del entity_caps[capability_type]
        # Clean up empty entity entries
        if not entity_caps:
            del self._store[entity_uid]
        return True

    # -- Queries ------------------------------------------------------------

    def query(
        self,
        entity_uid: str | None = None,
        capability_type: str | None = None,
    ) -> list[Capability]:
        """Filter capabilities by entity and/or type.

        Both filters are AND-combined.  Pass None for either to skip
        that filter.

        Args:
            entity_uid:      Filter by entity UID.
            capability_type: Filter by capability type.

        Returns:
            List of matching Capability objects (arbitrary order).
        """
        results: list[Capability] = []

        if entity_uid is not None:
            # Scoped to one entity
            entity_caps = self._store.get(entity_uid, {})
            if capability_type is not None:
                cap = entity_caps.get(capability_type)
                if cap is not None:
                    results.append(cap)
            else:
                results.extend(entity_caps.values())
        else:
            # Scan all entities
            for entity_caps in self._store.values():
                for cap in entity_caps.values():
                    if capability_type is not None and cap.capability_type != capability_type:
                        continue
                    results.append(cap)

        return results

    def has_capability(self, entity_uid: str, capability_type: str) -> bool:
        """Check whether an entity has a specific capability.

        Args:
            entity_uid:      The entity UID.
            capability_type: Capability type to check.

        Returns:
            True if the entity has the capability, False otherwise.
        """
        return capability_type in self._store.get(entity_uid, {})

    @property
    def count(self) -> int:
        """Total number of registered capabilities."""
        return sum(len(caps) for caps in self._store.values())

    @property
    def entities(self) -> list[str]:
        """List of entity UIDs that have at least one capability."""
        return list(self._store.keys())

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        """Return a serializable snapshot of the entire registry.

        Returns:
            Dict mapping entity_uid to list of serialized Capability dicts.
        """
        return {
            uid: [cap.to_dict() for cap in caps.values()]
            for uid, caps in self._store.items()
        }
