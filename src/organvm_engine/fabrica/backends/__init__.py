"""Agent dispatch backends for the Cyclic Dispatch Protocol.

Each backend knows how to create work items for a specific agent type
and check their status. Backends are registered in the routing table
and selected by capability matching during HANDOFF.

Six backends:
- copilot: GitHub issue + @copilot assignment
- jules: GitHub issue + @jules assignment
- actions: workflow_dispatch event via gh CLI
- claude: worktree-isolated Claude Code subagent
- launchagent: macOS plist generation + launchctl load
- human: GitHub issue tagged needs-review
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from organvm_engine.fabrica.backends._protocol import BackendProtocol

# Backend name → module path for deferred import
_BACKEND_MODULES: dict[str, str] = {
    "copilot": "organvm_engine.fabrica.backends.copilot",
    "jules": "organvm_engine.fabrica.backends.jules",
    "actions": "organvm_engine.fabrica.backends.actions",
    "claude": "organvm_engine.fabrica.backends.claude",
    "launchagent": "organvm_engine.fabrica.backends.launchagent",
    "human": "organvm_engine.fabrica.backends.human",
}

VALID_BACKENDS = frozenset(_BACKEND_MODULES)


def get_backend(name: str) -> BackendProtocol:
    """Return the backend module for *name*.

    Raises KeyError if *name* is not a registered backend.
    """
    if name not in _BACKEND_MODULES:
        raise KeyError(
            f"Unknown backend {name!r}. Valid backends: {', '.join(sorted(VALID_BACKENDS))}",
        )
    import importlib

    return importlib.import_module(_BACKEND_MODULES[name])  # type: ignore[return-value]


__all__ = ["VALID_BACKENDS", "get_backend"]
