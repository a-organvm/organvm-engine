"""Dependency graph validation — cycle detection, back-edge checking, DAG analysis."""

from collections import defaultdict
from dataclasses import dataclass, field

from organvm_engine.registry.query import all_repos

# Organ ordering for back-edge detection
# Flow: I -> II -> III. IV-VII + Meta can reference anything.
ORGAN_LEVELS = {
    "organvm-i-theoria": 1,
    "organvm-ii-poiesis": 2,
    "organvm-iii-ergon": 3,
    "organvm-iv-taxis": 4,
    "organvm-v-logos": 5,
    "organvm-vi-koinonia": 6,
    "organvm-vii-kerygma": 7,
    "meta-organvm": 8,
}
RESTRICTED_LEVELS = {1, 2, 3}


@dataclass
class DependencyResult:
    """Result of dependency graph validation."""

    total_edges: int = 0
    missing_targets: list[tuple[str, str]] = field(default_factory=list)
    self_deps: list[str] = field(default_factory=list)
    back_edges: list[tuple[str, str, str, str]] = field(default_factory=list)
    cycles: list[list[str]] = field(default_factory=list)
    cross_organ: dict[str, int] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return (
            len(self.missing_targets) == 0
            and len(self.self_deps) == 0
            and len(self.back_edges) == 0
            and len(self.cycles) == 0
        )

    @property
    def violations(self) -> list[str]:
        v = []
        for f, t in self.missing_targets:
            v.append(f"Missing target: {f} -> {t}")
        for s in self.self_deps:
            v.append(f"Self-dep: {s}")
        for f, t, fo, to in self.back_edges:
            v.append(f"Back-edge: {f} -> {t} ({fo} -> {to})")
        for c in self.cycles:
            v.append(f"Cycle: {' -> '.join(c)}")
        return v


def validate_dependencies(registry: dict) -> DependencyResult:
    """Validate the dependency graph from a registry.

    Checks:
    1. All dependency targets exist
    2. No self-dependencies
    3. No back-edges in I->II->III chain
    4. No circular dependencies

    Args:
        registry: Loaded registry dict.

    Returns:
        DependencyResult with all findings.
    """
    result = DependencyResult()

    # Build repo map and edge list
    repo_map: dict[str, dict] = {}
    edges: list[tuple[str, str]] = []

    for _organ_key, repo in all_repos(registry):
        key = f"{repo['org']}/{repo['name']}"
        repo_map[key] = repo
        for dep in repo.get("dependencies", []):
            edges.append((key, dep))
            result.total_edges += 1

    # Check 1: Targets exist
    for from_key, to_key in edges:
        if to_key not in repo_map:
            result.missing_targets.append((from_key, to_key))

    # Check 2: Self-deps
    for from_key, to_key in edges:
        if from_key == to_key:
            result.self_deps.append(from_key)

    # Check 3: Back-edges
    for from_key, to_key in edges:
        from_org = from_key.split("/")[0]
        to_org = to_key.split("/")[0]
        from_level = ORGAN_LEVELS.get(from_org)
        to_level = ORGAN_LEVELS.get(to_org)

        if from_level is None or to_level is None:
            continue

        if (
            from_level in RESTRICTED_LEVELS
            and to_level in RESTRICTED_LEVELS
            and from_level < to_level
        ):
            result.back_edges.append((from_key, to_key, from_org, to_org))

    # Check 4: Cycle detection (DFS with coloring)
    adj: dict[str, list[str]] = defaultdict(list)
    for from_key, to_key in edges:
        adj[from_key].append(to_key)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = defaultdict(lambda: WHITE)

    def dfs(node: str, path: list[str]) -> None:
        color[node] = GRAY
        path.append(node)
        for neighbor in adj[node]:
            if color[neighbor] == GRAY:
                cycle_start = path.index(neighbor)
                result.cycles.append(path[cycle_start:] + [neighbor])
            elif color[neighbor] == WHITE:
                dfs(neighbor, path)
        path.pop()
        color[node] = BLACK

    for node in repo_map:
        if color[node] == WHITE:
            dfs(node, [])

    # Cross-organ summary
    cross: dict[str, int] = defaultdict(int)
    for from_key, to_key in edges:
        from_org = from_key.split("/")[0]
        to_org = to_key.split("/")[0]
        if from_org != to_org:
            cross[f"{from_org} -> {to_org}"] += 1
    result.cross_organ = dict(cross)

    # Emit violation events if any found
    if not result.passed:
        try:
            from organvm_engine.pulse.emitter import emit_engine_event
            from organvm_engine.pulse.types import DEPENDENCY_VIOLATION

            emit_engine_event(
                event_type=DEPENDENCY_VIOLATION,
                source="governance",
                payload={
                    "back_edges": len(result.back_edges),
                    "cycles": len(result.cycles),
                    "missing_targets": len(result.missing_targets),
                    "violations": result.violations[:10],
                },
            )
        except Exception:
            pass

    return result
