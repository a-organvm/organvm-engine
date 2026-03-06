"""Workspace-wide pitch deck sync — walks repos, generates, writes.

Follows the contextmd/sync.py pattern: load registry + seeds once,
walk organ directories, generate pitch decks, write to docs/pitch/index.html.

Skips:
- Bespoke decks (no PITCH_MARKER in existing file)
- Infrastructure tier repos
- Archive tier repos
- Repos matching the EXCLUDED_REPOS set
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from organvm_engine.pitchdeck import PITCH_MARKER
from organvm_engine.pitchdeck.data import assemble
from organvm_engine.pitchdeck.generator import generate_pitch_deck
from organvm_engine.pitchdeck.themes import resolve_theme

# Tiers that are excluded from pitch deck generation
EXCLUDED_TIERS = {"infrastructure", "archive"}

# Repos with known bespoke decks (double-check via PITCH_MARKER too)
BESPOKE_REPOS = {
    "peer-audited--behavioral-blockchain",
    "parlor-games--ephemera-engine",
    "nexus--babel-alexandria",
}


def sync_pitchdecks(
    workspace: Path | str | None = None,
    registry_path: str | None = None,
    dry_run: bool = False,
    organs: list[str] | None = None,
    tier_filter: str | None = None,
) -> dict[str, Any]:
    """Sync pitch decks across the workspace.

    Args:
        workspace: Workspace root (default: ~/Workspace).
        registry_path: Path to registry-v2.json.
        dry_run: If True, report changes without writing files.
        organs: Filter to specific organ keys (e.g., ["ORGAN-I"]).
        tier_filter: Only generate for this tier ("flagship", "standard", "all").

    Returns:
        Summary dict with generated, skipped, bespoke, and error lists.
    """
    from organvm_engine.git.superproject import REGISTRY_KEY_MAP
    from organvm_engine.registry.loader import load_registry
    from organvm_engine.seed.discover import discover_seeds
    from organvm_engine.seed.reader import read_seed

    ws = Path(workspace) if workspace else Path.home() / "Workspace"
    reg = load_registry(registry_path)

    # Discover seeds for edge data
    seed_paths = discover_seeds(ws)
    repo_to_seed: dict[str, dict] = {}
    for p in seed_paths:
        try:
            s = read_seed(p)
            repo_to_seed[s.get("repo", "")] = s
        except Exception:
            continue

    generated = []
    skipped = []
    bespoke = []
    errors = []

    target_organs = organs or list(REGISTRY_KEY_MAP.keys())

    for organ_key in target_organs:
        organ_dir_name = REGISTRY_KEY_MAP.get(organ_key)
        if not organ_dir_name:
            continue

        organ_path = ws / organ_dir_name
        if not organ_path.is_dir():
            continue

        organ_data = reg.get("organs", {}).get(organ_key, {})

        # Collect sibling names for this organ
        sibling_names = [r.get("name", "") for r in organ_data.get("repositories", [])]

        for repo_entry in organ_data.get("repositories", []):
            repo_name = repo_entry.get("name", "")
            repo_tier = repo_entry.get("tier", "standard")
            repo_path = organ_path / repo_name

            if not repo_path.is_dir():
                skipped.append({"repo": repo_name, "reason": "directory not found"})
                continue

            # Skip excluded tiers
            if repo_tier in EXCLUDED_TIERS:
                skipped.append({"repo": repo_name, "reason": f"tier={repo_tier}"})
                continue

            # Apply tier filter
            if tier_filter and tier_filter not in ("all", repo_tier):
                skipped.append(
                    {"repo": repo_name, "reason": f"tier={repo_tier} (filter={tier_filter})"},
                )
                continue

            # Check for existing bespoke deck
            pitch_dir = repo_path / "docs" / "pitch"
            pitch_file = pitch_dir / "index.html"

            # Also check the alternative path used by some repos
            alt_pitch_file = repo_path / "docs" / "pitch-deck" / "index.html"

            if _is_bespoke(pitch_file) or _is_bespoke(alt_pitch_file):
                bespoke.append(repo_name)
                continue

            try:
                # Assemble data
                seed = repo_to_seed.get(repo_name)
                siblings = [s for s in sibling_names if s != repo_name]
                data = assemble(
                    repo_name=repo_name,
                    organ_key=organ_key,
                    repo_entry=repo_entry,
                    repo_path=repo_path,
                    seed=seed,
                )
                data.siblings = siblings

                # Resolve theme
                theme = resolve_theme(organ_key)

                # Generate HTML
                html_content = generate_pitch_deck(data, theme)

                # Write
                if not dry_run:
                    pitch_dir.mkdir(parents=True, exist_ok=True)
                    pitch_file.write_text(html_content, encoding="utf-8")

                generated.append(
                    {
                        "repo": repo_name,
                        "organ": organ_key,
                        "tier": repo_tier,
                        "path": str(pitch_file),
                    },
                )
            except Exception as e:
                errors.append(
                    {
                        "repo": repo_name,
                        "error": f"{type(e).__name__}: {e}",
                    },
                )

    return {
        "generated": generated,
        "skipped": skipped,
        "bespoke": bespoke,
        "errors": errors,
        "dry_run": dry_run,
    }


def generate_single(
    repo_name: str,
    workspace: Path | str | None = None,
    registry_path: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Generate a pitch deck for a single repo.

    Args:
        repo_name: Repository name.
        workspace: Workspace root.
        registry_path: Path to registry-v2.json.
        dry_run: If True, return HTML without writing to disk.

    Returns:
        {"repo": str, "action": str, "path": str, "html": str (if dry_run)}
    """
    from organvm_engine.git.superproject import REGISTRY_KEY_MAP
    from organvm_engine.registry.loader import load_registry
    from organvm_engine.registry.query import find_repo

    ws = Path(workspace) if workspace else Path.home() / "Workspace"
    reg = load_registry(registry_path)

    result = find_repo(reg, repo_name)
    if not result:
        return {
            "repo": repo_name,
            "action": "error",
            "error": f"Repo '{repo_name}' not found in registry",
        }

    organ_key, repo_entry = result
    organ_dir_name = REGISTRY_KEY_MAP.get(organ_key, "")
    repo_path = ws / organ_dir_name / repo_name

    if not repo_path.is_dir():
        return {"repo": repo_name, "action": "error", "error": f"Directory not found: {repo_path}"}

    # Check for bespoke deck
    pitch_file = repo_path / "docs" / "pitch" / "index.html"
    alt_pitch_file = repo_path / "docs" / "pitch-deck" / "index.html"

    if _is_bespoke(pitch_file) or _is_bespoke(alt_pitch_file):
        return {
            "repo": repo_name,
            "action": "bespoke",
            "path": str(pitch_file if pitch_file.exists() else alt_pitch_file),
        }

    # Assemble, theme, generate
    data = assemble(
        repo_name=repo_name,
        organ_key=organ_key,
        repo_entry=repo_entry,
        repo_path=repo_path,
    )

    # Get siblings
    organ_data = reg.get("organs", {}).get(organ_key, {})
    data.siblings = [
        r.get("name", "") for r in organ_data.get("repositories", []) if r.get("name") != repo_name
    ]

    theme = resolve_theme(organ_key)
    html_content = generate_pitch_deck(data, theme)

    if dry_run:
        return {
            "repo": repo_name,
            "action": "dry_run",
            "path": str(pitch_file),
            "html": html_content,
        }

    pitch_file.parent.mkdir(parents=True, exist_ok=True)
    pitch_file.write_text(html_content, encoding="utf-8")

    return {"repo": repo_name, "action": "generated", "path": str(pitch_file)}


def _is_bespoke(path: Path) -> bool:
    """Check if an existing pitch deck is bespoke (no auto-marker)."""
    if not path.exists():
        return False
    try:
        content = path.read_text(encoding="utf-8")
        return PITCH_MARKER not in content
    except (OSError, UnicodeDecodeError):
        return False
