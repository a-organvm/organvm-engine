"""Query operations on the registry."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from typing import Any, Iterable, Iterator

from organvm_engine.organ_config import organ_aliases

# Organ key aliases — derived from canonical organ_config
ORGAN_ALIASES = organ_aliases()

DEFAULT_SEARCH_FIELDS = (
    "name",
    "org",
    "description",
    "implementation_status",
    "promotion_status",
    "tier",
    "documentation_status",
    "type",
    "revenue_model",
    "revenue_status",
    "dependencies",
)


@dataclass(frozen=True)
class RegistryStats:
    """Computed registry-wide statistics."""

    total_repos: int
    organ_count: int
    public_repos: int
    private_repos: int
    platinum_repos: int
    archived_repos: int
    repos_with_dependencies: int
    dependency_edges: int
    by_organ: dict[str, int]
    by_status: dict[str, int]
    by_tier: dict[str, int]
    by_promotion_status: dict[str, int]

    def to_dict(self) -> dict[str, int | dict[str, int]]:
        """Return a JSON-serializable representation."""
        return {
            "total_repos": self.total_repos,
            "organ_count": self.organ_count,
            "public_repos": self.public_repos,
            "private_repos": self.private_repos,
            "platinum_repos": self.platinum_repos,
            "archived_repos": self.archived_repos,
            "repos_with_dependencies": self.repos_with_dependencies,
            "dependency_edges": self.dependency_edges,
            "by_organ": self.by_organ,
            "by_status": self.by_status,
            "by_tier": self.by_tier,
            "by_promotion_status": self.by_promotion_status,
        }


def resolve_organ_key(organ: str) -> str:
    """Resolve an organ alias to its registry key.

    Accepts CLI shorthand (e.g., "META", "I") and returns the
    registry key (e.g., "META-ORGANVM", "ORGAN-I"). If the input
    is already a valid registry key, it passes through unchanged.
    """
    return ORGAN_ALIASES.get(organ, organ)


def _normalize_dependency_name(dep: str) -> str:
    value = dep.strip()
    if not value:
        return ""
    if "/" in value:
        return value.rsplit("/", maxsplit=1)[-1]
    return value


def _dependency_set(repo: dict) -> set[str]:
    deps = set()
    for dep in repo.get("dependencies", []):
        dep_name = _normalize_dependency_name(str(dep))
        if dep_name:
            deps.add(dep_name)
    return deps


def _iter_repo_field_values(repo: dict, fields: Iterable[str]) -> Iterator[str]:
    for field in fields:
        value = repo.get(field)
        if value is None:
            continue
        if isinstance(value, list):
            for item in value:
                if item is not None:
                    yield str(item)
        else:
            yield str(value)


def all_repos(registry: dict) -> Iterator[tuple[str, dict]]:
    """Yield (organ_key, repo_dict) for every repo in the registry."""
    for organ_key, organ in registry.get("organs", {}).items():
        for repo in organ.get("repositories", []):
            yield organ_key, repo


def find_repo(registry: dict, name: str) -> tuple[str, dict] | None:
    """Find a repo entry by name.

    Args:
        registry: Loaded registry dict.
        name: Repository name (e.g., "recursive-engine--generative-entity").

    Returns:
        (organ_key, repo_dict) or None if not found.
    """
    for organ_key, repo in all_repos(registry):
        if repo.get("name") == name:
            return organ_key, repo
    return None


def resolve_entity(
    name_or_id: str,
    registry: dict | None = None,
) -> dict[str, Any] | None:
    """Resolve an entity by name or UID using ontologia if available.

    Checks the ontologia structural registry first (UID, name, slug, alias),
    then falls back to the name-based registry lookup.

    Args:
        name_or_id: Entity UID, display name, slug, or alias.
        registry: Loaded registry dict (for fallback). If None, only ontologia is checked.

    Returns:
        Dict with uid, entity_type, display_name, matched_by, and optional
        registry_entry. Returns None if not found anywhere.
    """
    # Try ontologia first
    try:
        from ontologia.registry.store import open_store

        store = open_store()
        resolver = store.resolver()
        resolved = resolver.resolve(name_or_id)
        if resolved is not None:
            name = store.current_name(resolved.identity.uid)
            result: dict[str, Any] = {
                "uid": resolved.identity.uid,
                "entity_type": resolved.identity.entity_type.value,
                "lifecycle_status": resolved.identity.lifecycle_status.value,
                "display_name": name.display_name if name else None,
                "matched_by": resolved.matched_by,
                "source": "ontologia",
            }
            # Enrich with registry data if available
            if registry and name:
                reg_match = find_repo(registry, name.display_name)
                if reg_match:
                    result["organ_key"] = reg_match[0]
                    result["registry_entry"] = reg_match[1]
            return result
    except ImportError:
        pass
    except Exception:
        pass  # ontologia store might not exist yet

    # Fallback to name-based lookup
    if registry is not None:
        match = find_repo(registry, name_or_id)
        if match:
            return {
                "uid": None,
                "entity_type": "repo",
                "lifecycle_status": "active",
                "display_name": name_or_id,
                "matched_by": "name",
                "source": "registry",
                "organ_key": match[0],
                "registry_entry": match[1],
            }

    return None


def list_repos(
    registry: dict,
    organ: str | None = None,
    status: str | None = None,
    tier: str | None = None,
    public_only: bool = False,
    promotion_status: str | None = None,
    name_contains: str | None = None,
    depends_on: str | None = None,
    dependency_of: str | None = None,
    platinum_only: bool = False,
    archived: bool | None = None,
) -> list[tuple[str, dict]]:
    """List repos with optional filters.

    Args:
        registry: Loaded registry dict.
        organ: Filter by organ key (e.g., "ORGAN-I").
        status: Filter by implementation_status.
        tier: Filter by tier.
        public_only: Only include public repos.
        promotion_status: Filter by promotion_status.
        name_contains: Case-insensitive substring match on repository name.
        depends_on: Include repos that list this repo as a dependency.
        dependency_of: Include repos that are direct dependencies of this repo.
        platinum_only: Include only repositories with platinum_status=true.
        archived: Filter archived flag (True/False). None disables filter.

    Returns:
        List of (organ_key, repo_dict) tuples matching filters.
    """
    results = []
    resolved_organ = resolve_organ_key(organ) if organ else None
    normalized_name_contains = name_contains.lower() if name_contains else None
    normalized_depends_on = _normalize_dependency_name(depends_on) if depends_on else None
    dependency_of_targets: set[str] | None = None
    if dependency_of:
        dep_source = find_repo(registry, dependency_of)
        dependency_of_targets = _dependency_set(dep_source[1]) if dep_source else set()

    for organ_key, repo in all_repos(registry):
        if resolved_organ and organ_key != resolved_organ:
            continue
        if status and repo.get("implementation_status") != status:
            continue
        if tier and repo.get("tier") != tier:
            continue
        if public_only and not repo.get("public"):
            continue
        if promotion_status and repo.get("promotion_status") != promotion_status:
            continue
        if platinum_only and not repo.get("platinum_status"):
            continue
        if archived is not None and bool(repo.get("archived", False)) != archived:
            continue
        if (
            normalized_name_contains
            and normalized_name_contains not in str(repo.get("name", "")).lower()
        ):
            continue

        dependencies = _dependency_set(repo)
        if normalized_depends_on and normalized_depends_on not in dependencies:
            continue
        if dependency_of_targets is not None and repo.get("name") not in dependency_of_targets:
            continue

        results.append((organ_key, repo))
    return results


def sort_repo_results(
    results: Iterable[tuple[str, dict]],
    field: str = "name",
    descending: bool = False,
) -> list[tuple[str, dict]]:
    """Return a sorted copy of list/search results."""

    def _key(item: tuple[str, dict]) -> str:
        organ_key, repo = item
        if field == "organ":
            return organ_key
        value = repo.get(field, "")
        return str(value).lower()

    return sorted(results, key=_key, reverse=descending)


def search_repos(
    registry: dict,
    query: str,
    fields: Iterable[str] | None = None,
    case_sensitive: bool = False,
    exact: bool = False,
    limit: int | None = None,
    organ: str | None = None,
    status: str | None = None,
    tier: str | None = None,
    public_only: bool = False,
    promotion_status: str | None = None,
) -> list[tuple[str, dict]]:
    """Search repositories by text query across selected fields."""
    text = query.strip()
    if not text:
        return []

    lookup_fields = tuple(fields) if fields else DEFAULT_SEARCH_FIELDS
    candidates = list_repos(
        registry,
        organ=organ,
        status=status,
        tier=tier,
        public_only=public_only,
        promotion_status=promotion_status,
    )

    if case_sensitive:
        normalized_query = text
        tokens = [token for token in text.split() if token]
    else:
        normalized_query = text.lower()
        tokens = [token.lower() for token in text.split() if token]

    matches: list[tuple[str, dict]] = []
    for item in candidates:
        _, repo = item
        values = list(_iter_repo_field_values(repo, lookup_fields))
        if not values:
            continue
        haystack = values if case_sensitive else [value.lower() for value in values]

        if exact:
            matched = any(value == normalized_query for value in haystack)
        else:
            matched = all(any(token in value for value in haystack) for token in tokens)

        if matched:
            matches.append(item)
            if limit is not None and len(matches) >= max(limit, 0):
                break

    return matches


def build_dependency_maps(registry: dict) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Build outbound and inbound dependency maps keyed by repo name."""
    outbound: dict[str, set[str]] = {}
    inbound: dict[str, set[str]] = {}

    for _, repo in all_repos(registry):
        name = repo.get("name")
        if name:
            outbound[name] = set()
            inbound[name] = set()

    for _, repo in all_repos(registry):
        name = repo.get("name")
        if not name:
            continue
        for dep in _dependency_set(repo):
            outbound[name].add(dep)
            if dep in inbound:
                inbound[dep].add(name)

    return outbound, inbound


def _walk_graph(
    start: str,
    edges: dict[str, set[str]],
    max_depth: int | None = None,
) -> set[str]:
    if max_depth is not None and max_depth < 1:
        return set()

    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(start, 0)])

    while queue:
        node, depth = queue.popleft()
        if max_depth is not None and depth >= max_depth:
            continue
        for nxt in edges.get(node, set()):
            if nxt in visited:
                continue
            visited.add(nxt)
            queue.append((nxt, depth + 1))
    return visited


def get_repo_dependencies(
    registry: dict,
    repo_name: str,
    transitive: bool = False,
    max_depth: int | None = None,
) -> list[str]:
    """Return direct or transitive dependencies for a repository."""
    result = find_repo(registry, repo_name)
    if not result:
        return []

    canonical_name = str(result[1].get("name"))
    outbound, _ = build_dependency_maps(registry)
    if transitive:
        names = _walk_graph(canonical_name, outbound, max_depth=max_depth)
    else:
        if max_depth is not None and max_depth < 1:
            return []
        names = set(outbound.get(canonical_name, set()))
    return sorted(names)


def get_repo_dependents(
    registry: dict,
    repo_name: str,
    transitive: bool = False,
    max_depth: int | None = None,
) -> list[str]:
    """Return direct or transitive dependents for a repository."""
    result = find_repo(registry, repo_name)
    if not result:
        return []

    canonical_name = str(result[1].get("name"))
    _, inbound = build_dependency_maps(registry)
    if transitive:
        names = _walk_graph(canonical_name, inbound, max_depth=max_depth)
    else:
        if max_depth is not None and max_depth < 1:
            return []
        names = set(inbound.get(canonical_name, set()))
    return sorted(names)


def find_missing_dependency_targets(registry: dict) -> dict[str, list[str]]:
    """Find unresolved dependency targets keyed by repository name."""
    outbound, _ = build_dependency_maps(registry)
    known_repos = set(outbound)
    missing: dict[str, list[str]] = {}
    for repo_name, deps in outbound.items():
        unresolved = sorted(dep for dep in deps if dep not in known_repos)
        if unresolved:
            missing[repo_name] = unresolved
    return missing


def summarize_registry(registry: dict) -> RegistryStats:
    """Compute registry-wide summary statistics."""
    by_organ: Counter[str] = Counter()
    by_status: Counter[str] = Counter()
    by_tier: Counter[str] = Counter()
    by_promotion_status: Counter[str] = Counter()

    total = 0
    public_count = 0
    private_count = 0
    platinum_count = 0
    archived_count = 0
    dependency_repo_count = 0
    dependency_edge_count = 0

    for organ_key, repo in all_repos(registry):
        total += 1
        by_organ[organ_key] += 1
        by_status[str(repo.get("implementation_status", "UNKNOWN"))] += 1
        by_tier[str(repo.get("tier", "UNKNOWN"))] += 1
        by_promotion_status[str(repo.get("promotion_status", "UNKNOWN"))] += 1

        if repo.get("public"):
            public_count += 1
        else:
            private_count += 1
        if repo.get("platinum_status"):
            platinum_count += 1
        if repo.get("archived", False):
            archived_count += 1

        deps = _dependency_set(repo)
        if deps:
            dependency_repo_count += 1
            dependency_edge_count += len(deps)

    return RegistryStats(
        total_repos=total,
        organ_count=len(by_organ),
        public_repos=public_count,
        private_repos=private_count,
        platinum_repos=platinum_count,
        archived_repos=archived_count,
        repos_with_dependencies=dependency_repo_count,
        dependency_edges=dependency_edge_count,
        by_organ=dict(sorted(by_organ.items())),
        by_status=dict(sorted(by_status.items())),
        by_tier=dict(sorted(by_tier.items())),
        by_promotion_status=dict(sorted(by_promotion_status.items())),
    )
