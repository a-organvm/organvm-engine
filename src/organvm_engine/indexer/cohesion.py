"""Cohesion analyzer — identifies atomic components from directory trees.

Normalization layer of the AMMOI architecture: classifying raw filesystem
observations into typed structural entities with dependency edges.

An atomic component is the deepest directory that forms a functional unit.
Heuristics are language-aware: Python packages, JS modules, Go packages,
doc collections, resource bundles.
"""

from __future__ import annotations

import contextlib
import re
from pathlib import Path

from organvm_engine.indexer.types import Component, DirectoryNode

# Regex for Python import statements (top-level module extraction)
_PYTHON_IMPORT_RE = re.compile(
    r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))",
    re.MULTILINE,
)

# File extensions that count as "code"
_CODE_EXTENSIONS = frozenset({
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".rb",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".swift", ".kt",
})

# Extension → language mapping
_LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".md": "markdown",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "css",
    ".yaml": "yaml", ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".sql": "sql",
}


def identify_components(
    tree: DirectoryNode,
    repo_name: str,
    organ_key: str,
    repo_path: Path | None = None,
) -> list[Component]:
    """Identify atomic components from a directory tree.

    Walks the tree bottom-up, classifying each directory by language
    and structure. Returns the deepest directories that form functional units.
    """
    components: list[Component] = []
    _collect_components(tree, repo_name, organ_key, repo_path, components)

    # Resolve Python import graph between sibling components
    if repo_path:
        _resolve_python_imports(components, repo_path)

    return components


def dominant_language(file_types: dict[str, int]) -> str:
    """Determine the dominant language from file extension counts."""
    if not file_types:
        return "unknown"

    lang_counts: dict[str, int] = {}
    for ext, count in file_types.items():
        lang = _LANG_MAP.get(ext, "other")
        lang_counts[lang] = lang_counts.get(lang, 0) + count

    if not lang_counts:
        return "unknown"

    return max(lang_counts, key=lambda k: lang_counts[k])


def classify_cohesion(node: DirectoryNode) -> str | None:
    """Classify a directory's cohesion type, or None if not a component.

    Returns None when the directory has sub-components (children that
    are themselves functional units) — the children are the atomic level.
    """
    # Python package: has __init__.py with no Python sub-packages
    if node.has_init_py:
        has_py_sub = any(c.has_init_py for c in node.children)
        if not has_py_sub:
            return "python_package"
        return None

    # JS/TS module: barrel file at non-root with no barrel sub-dirs
    if node.has_barrel_file and node.depth > 0:
        has_js_sub = any(c.has_barrel_file for c in node.children)
        if not has_js_sub:
            return "js_module"
        return None

    # Go package: directory with .go files
    if node.file_types.get(".go", 0) > 0:
        return "go_package"

    # Rust crate: Cargo.toml at non-root
    if node.has_cargo_toml and node.depth > 0:
        return "rust_crate"

    # Document collection: 2+ markdown files, no code files
    has_code = any(ext in _CODE_EXTENSIONS for ext in node.file_types)
    md_count = node.file_types.get(".md", 0)
    if md_count >= 2 and not has_code:
        return "doc_collection"

    # Leaf directory with 2+ files
    if node.is_leaf and node.file_count >= 2:
        if not has_code:
            return "resource_bundle"
        return "generic"

    return None


def _collect_components(
    node: DirectoryNode,
    repo_name: str,
    organ_key: str,
    repo_path: Path | None,
    components: list[Component],
) -> None:
    """Recursively collect atomic components from the tree."""
    # Skip root node — the repo itself is not a component
    if node.depth == 0:
        for child in node.children:
            _collect_components(child, repo_name, organ_key, repo_path, components)
        return

    cohesion = classify_cohesion(node)

    if cohesion is not None:
        total_files = node.total_files
        total_lines = node.total_lines
        lang = dominant_language(node.file_types)

        components.append(Component(
            repo=repo_name,
            organ=organ_key,
            path=node.path,
            cohesion_type=cohesion,
            depth=node.depth,
            file_count=total_files,
            line_count=total_lines,
            dominant_language=lang,
        ))
    else:
        # Not a component — recurse into children
        for child in node.children:
            _collect_components(child, repo_name, organ_key, repo_path, components)


def extract_python_imports(file_path: Path) -> set[str]:
    """Extract importable module names from a Python file's import statements.

    Returns both top-level names and second-level sub-modules, since
    intra-package imports like ``from organvm_engine.registry import ...``
    need the second segment (``registry``) for sibling resolution.
    """
    modules: set[str] = set()
    with contextlib.suppress(OSError, UnicodeDecodeError):
        content = file_path.read_text()
        for m in _PYTHON_IMPORT_RE.finditer(content):
            mod = m.group(1) or m.group(2)
            if mod:
                parts = mod.split(".")
                modules.add(parts[0])
                if len(parts) > 1:
                    modules.add(parts[1])
    return modules


def _resolve_python_imports(
    components: list[Component],
    repo_path: Path,
) -> None:
    """Resolve import relationships between Python components in a repo."""
    py_components = [c for c in components if c.cohesion_type == "python_package"]
    if not py_components:
        return

    # Build component name → path mapping
    name_to_path: dict[str, str] = {}
    for comp in py_components:
        name = comp.path.rstrip("/").split("/")[-1]
        name_to_path[name] = comp.path

    # Scan each component's .py files for imports
    for comp in py_components:
        comp_path = repo_path / comp.path
        if not comp_path.is_dir():
            continue

        all_imports: set[str] = set()
        for py_file in comp_path.glob("*.py"):
            all_imports |= extract_python_imports(py_file)

        # Match imports against sibling component names
        for imp in all_imports:
            if imp in name_to_path and name_to_path[imp] != comp.path:
                comp.imports_from.append(name_to_path[imp])

    # Build reverse mapping
    path_to_comp = {c.path: c for c in py_components}
    for comp in py_components:
        for imp_path in comp.imports_from:
            target = path_to_comp.get(imp_path)
            if target and comp.path not in target.imported_by:
                target.imported_by.append(comp.path)
