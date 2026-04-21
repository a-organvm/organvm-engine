"""Formation registry — load and enumerate crystallized formations.

Each formation module registers itself by providing a ``build_graph()``
function and metadata.  The registry collects these for the composition
engine and CLI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from organvm_engine.composition.graph import CompositionGraph


@dataclass
class FormationSpec:
    """Metadata for a registered formation."""

    formation_id: str
    name: str
    formation_type: str  # GENERATOR, TRANSFORMER, ROUTER, RESERVOIR, INTERFACE, LABORATORY, SYNTHESIZER
    description: str = ""
    trigger_description: str = ""
    escalation_policy: dict[str, str] = field(default_factory=dict)
    build_graph: Callable[[], CompositionGraph] | None = None
    primitives_used: list[str] = field(default_factory=list)


class FormationRegistry:
    """Collect and retrieve formation specifications."""

    def __init__(self) -> None:
        self._specs: dict[str, FormationSpec] = {}

    def register(self, spec: FormationSpec) -> None:
        self._specs[spec.name] = spec

    def get(self, name: str) -> FormationSpec | None:
        return self._specs.get(name)

    def list_all(self) -> list[FormationSpec]:
        return list(self._specs.values())

    def __len__(self) -> int:
        return len(self._specs)
