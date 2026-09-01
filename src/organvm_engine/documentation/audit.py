"""Deterministic, read-only repository documentation audit."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import yaml

from organvm_engine.documentation.record import load_project_record, validate_project_record

DIMENSIONS = (
    "orientation",
    "technical_depth",
    "conceptual_depth",
    "commercial_relevance",
    "evidence",
    "seo_surface",
    "cross_linking",
)
SKIP_DIRS = frozenset(
    {".git", ".venv", "node_modules", "vendor", "dist", "build", "__pycache__"},
)
MARKDOWN_LINK_START = re.compile(r"\]\(")
MARKDOWN_FENCE = re.compile(r"^[ ]{0,3}(?P<fence>`{3,}|~{3,})")
MARKDOWN_INDENTED_CODE = re.compile(r"^(?: {4}| {0,3}\t)")
REFERENCE_DEFINITION = re.compile(
    r"^[ ]{0,3}\[(?P<label>[^\]\n]+)\]:[ \t]*(?P<destination><[^>\n]+>|[^\s]+)",
)
REFERENCE_USAGE = re.compile(r"(?<!!)\[(?P<label>[^\]\n]+)\](?![\[(])")
COLLAPSED_REFERENCE_USAGE = re.compile(r"(?<!!)\[(?P<label>[^\]\n]+)\]\[\]")


def discover_repositories(workspace: str | Path) -> list[Path]:
    """Find repository roots below a workspace without descending into them."""
    workspace_path = Path(workspace).resolve()
    repositories: list[Path] = []
    for current, dirs, _files in os.walk(workspace_path):
        current_path = Path(current)
        dirs[:] = [
            item
            for item in dirs
            if item not in SKIP_DIRS or (current_path / item / ".git").exists()
        ]
        if (current_path / ".git").exists():
            repositories.append(current_path)
            dirs[:] = []
    return sorted(repositories)


def audit_repository(root: str | Path) -> dict[str, Any]:
    """Audit a repository's reader-mode documentation without mutating it."""
    root_path = Path(root).resolve()
    readme_path = _readme_path(root_path)
    readme = readme_path.read_text(encoding="utf-8", errors="replace") if readme_path else ""
    markdown_files = _markdown_files(root_path)
    corpus = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in markdown_files)
    lowered = corpus.lower()
    readme_lower = readme.lower()
    valid_local_links, broken_local_links = _inspect_local_links(root_path, markdown_files)

    record_path = _record_path(root_path)
    record: dict[str, Any] | None = None
    record_errors: list[str] = []
    if record_path:
        try:
            record = load_project_record(record_path)
            record_errors = validate_project_record(record, root=root_path)
        except (OSError, ValueError) as exc:
            record_errors = [str(exc)]

    doc_class = str(record.get("documentation_class")) if record else _suggest_class(root_path, readme)
    signals = {
        "orientation": _score_orientation(readme_lower),
        "technical_depth": _score_categories(
            lowered,
            (
                ("architecture", "system design", "component boundary", "data flow"),
                ("install", "quick start", "getting started", "usage", "run locally"),
                ("test", "verification", "coverage", "quality assurance"),
                ("api", "interface", "schema", "endpoint", "protocol"),
                ("failure mode", "observability", "security", "technical debt", "operations"),
            ),
            bonus=(root_path / "docs/audiences/technical.md").is_file(),
        ),
        "conceptual_depth": _score_categories(
            lowered,
            (
                ("theory", "concept", "research question", "intellectual"),
                ("humanities", "aesthetic", "cultural", "epistemology", "ontology"),
                ("genealogy", "related work", "prior art", "tradition"),
                ("ethic", "pedagog", "authorship", "interpretation", "narrative"),
            ),
            bonus=(root_path / "docs/audiences/humanities.md").is_file(),
        ),
        "commercial_relevance": _score_categories(
            lowered,
            (
                ("problem statement", "primary user", "who experiences", "user need"),
                ("workflow", "inputs and outputs", "current workaround", "use case"),
                ("business model", "value proposition", "buyer", "customer"),
                ("integration", "risk", "constraint", "implementation requirement"),
                ("deployment status", "projected value", "operational", "industry"),
            ),
            bonus=(root_path / "docs/audiences/business.md").is_file(),
        ),
        "evidence": _score_categories(
            lowered,
            (
                ("test", "demo", "source", "revision history"),
                ("current state", "current status", "implementation status", "live status"),
                ("authorship", "contribution", "what anthony built", "initial condition"),
                ("limitation", "incomplete", "known issue", "not yet"),
                ("evidence record", "evidence", "verified", "proposed"),
            ),
            bonus=record_path is not None or (root_path / "docs/evidence/README.md").is_file(),
        ),
        "seo_surface": _score_seo(root_path, readme_lower, markdown_files),
        "cross_linking": _score_cross_linking(
            root_path,
            corpus,
            valid_local_links=len(valid_local_links),
        ),
    }
    findings = _findings(
        root_path,
        readme,
        record_path,
        record_errors,
        signals,
        broken_local_links,
    )

    return {
        "repository": root_path.name,
        "path": str(root_path),
        "documentation_class": doc_class,
        "class_source": "project-record" if record else "heuristic",
        "has_readme": readme_path is not None,
        "has_project_record": record_path is not None,
        "markdown_files": len(markdown_files),
        "signals": signals,
        "signal_semantics": "structural markers only; not a quality score",
        "record_errors": record_errors,
        "findings": findings,
    }


def _readme_path(root: Path) -> Path | None:
    try:
        candidates = [
            path
            for path in root.iterdir()
            if _safe_markdown_file(root, path) and path.name.casefold() == "readme.md"
        ]
    except OSError:
        return None
    return min(candidates, key=lambda path: (path.name != "README.md", path.name), default=None)


def _record_path(root: Path) -> Path | None:
    for name in ("project-record.yml", "project-record.yaml", "project-record.json"):
        path = root / name
        if _safe_audit_file(root, path):
            return path
    return None


def _markdown_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        current_path = Path(current)
        for name in names:
            if Path(name).suffix.casefold() != ".md":
                continue
            path = current_path / name
            try:
                if _safe_markdown_file(root, path) and path.stat().st_size <= 2_000_000:
                    files.append(path)
            except OSError:
                continue
    return sorted(files)


def _score_orientation(readme_lower: str) -> int:
    if not readme_lower:
        return 0
    score = 1
    first_screen = readme_lower[:1800]
    if any(term in first_screen for term in ("overview", "what is", "what am i looking at", "purpose")):
        score += 1
    if any(term in readme_lower for term in ("current state", "current status", "implementation status", "project status")):
        score += 1
    if any(term in readme_lower for term in ("choose your reading path", "read this project your way", "i am reading as")):
        score += 1
    return min(4, score)


def _score_categories(
    text: str,
    categories: tuple[tuple[str, ...], ...],
    *,
    bonus: bool = False,
) -> int:
    hits = sum(any(term in text for term in category) for category in categories)
    if bonus:
        hits += 1
    if hits == 0:
        return 0
    if hits == 1:
        return 1
    if hits == 2:
        return 2
    if hits <= 4:
        return 3
    return 4


def _score_seo(root: Path, readme_lower: str, markdown_files: list[Path]) -> int:
    score = 0
    if readme_lower and len(readme_lower[:900].split()) >= 20:
        score += 1
    relative_paths = {path.relative_to(root).as_posix() for path in markdown_files}
    if any(path.startswith("docs/audiences/") for path in relative_paths):
        score += 1
    if any(path.startswith("docs/concepts/") for path in relative_paths):
        score += 1
    if any(path.startswith("docs/industries/") for path in relative_paths):
        score += 1
    return min(4, score)


def _score_cross_linking(root: Path, corpus: str, *, valid_local_links: int) -> int:
    links = [link for link in _markdown_destinations(corpus) if not link.startswith("#")]
    if not links:
        return 0
    score = 1
    external_repo = [link for link in links if "github.com/" in link]
    if valid_local_links >= 3:
        score += 1
    if len(external_repo) >= 2:
        score += 1
    typed_graph = any(
        term in corpus.lower()
        for term in ("related systems", "dependencies", "implemented by", "canonical project")
    )
    if typed_graph and (root / "docs/audiences").is_dir():
        score += 1
    return min(4, score)


def _inspect_local_links(root: Path, markdown_files: list[Path]) -> tuple[set[Path], list[str]]:
    valid: set[Path] = set()
    broken: list[str] = []
    for source in markdown_files:
        text = source.read_text(encoding="utf-8", errors="replace")
        for raw_target in _markdown_destinations(text):
            target = raw_target.strip().strip("<>")
            if not target or target.startswith("#") or target.startswith("//"):
                continue
            try:
                parsed = urlparse(target)
            except ValueError:
                broken.append(f"{source.relative_to(root)} -> {target}")
                continue
            if parsed.scheme:
                continue
            path_text = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not path_text:
                continue
            candidate = (source.parent / path_text).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                broken.append(f"{source.relative_to(root)} -> {target}")
                continue
            if candidate.exists():
                valid.add(candidate)
            else:
                broken.append(f"{source.relative_to(root)} -> {target}")
    return valid, sorted(set(broken))


def _markdown_destinations(text: str) -> list[str]:
    """Extract inline Markdown link destinations without swallowing link titles.

    This intentionally stays smaller than a renderer while handling the pieces
    needed for repository link validation: angle-bracket destinations, escaped
    characters, balanced parentheses, and optional whitespace-separated titles.
    """
    text = _mask_markdown_code(text)
    text, reference_destinations = _reference_destinations(text)
    destinations: list[str] = list(reference_destinations)
    for match in MARKDOWN_LINK_START.finditer(text):
        position = match.end()
        while position < len(text) and text[position] in " \t\n":
            position += 1
        if position >= len(text):
            continue

        destination: list[str] = []
        if text[position] == "<":
            position += 1
            escaped = False
            while position < len(text):
                character = text[position]
                position += 1
                if escaped:
                    destination.append(character)
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == ">":
                    break
                else:
                    destination.append(character)
            else:
                continue
        else:
            depth = 0
            escaped = False
            while position < len(text):
                character = text[position]
                if escaped:
                    destination.append(character)
                    escaped = False
                    position += 1
                elif character == "\\":
                    escaped = True
                    position += 1
                elif character == "(":
                    depth += 1
                    destination.append(character)
                    position += 1
                elif character == ")":
                    if depth == 0:
                        break
                    depth -= 1
                    destination.append(character)
                    position += 1
                elif character.isspace() and depth == 0:
                    break
                else:
                    destination.append(character)
                    position += 1

        rendered = "".join(destination)
        if rendered:
            destinations.append(rendered)
    return destinations


def _safe_markdown_file(root: Path, path: Path) -> bool:
    """Reject symlinked Markdown inputs and paths resolving outside the root."""
    return _safe_audit_file(root, path)


def _safe_audit_file(root: Path, path: Path) -> bool:
    """Return whether an audit input is a regular in-repository file."""
    try:
        if path.is_symlink() or not path.is_file():
            return False
        path.resolve(strict=True).relative_to(root)
    except (OSError, ValueError):
        return False
    return True


def _reference_destinations(text: str) -> tuple[str, list[str]]:
    """Resolve destinations used through CommonMark-style reference links."""
    definitions: dict[str, str] = {}
    visible_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        match = REFERENCE_DEFINITION.match(line)
        if match is None:
            visible_lines.append(line)
            continue
        label = _normalize_reference_label(match.group("label"))
        destination = match.group("destination").strip().strip("<>")
        definitions.setdefault(label, destination)
        visible_lines.append("".join("\n" if char == "\n" else " " for char in line))

    visible = "".join(visible_lines)
    destinations: list[str] = []
    for pattern in (COLLAPSED_REFERENCE_USAGE, REFERENCE_USAGE):
        for match in pattern.finditer(visible):
            destination = definitions.get(_normalize_reference_label(match.group("label")))
            if destination is not None:
                destinations.append(destination)
    return visible, destinations


def _normalize_reference_label(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip()).casefold()


def _mask_markdown_code(text: str) -> str:
    """Mask fenced blocks and inline code while preserving source positions."""

    def masked(value: str) -> str:
        return "".join("\n" if character == "\n" else " " for character in value)

    lines = text.splitlines(keepends=True)
    visible: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    for line in lines:
        match = MARKDOWN_FENCE.match(line)
        if fence_character is None:
            if match is not None:
                fence = match.group("fence")
                fence_character = fence[0]
                fence_length = len(fence)
                visible.append(masked(line))
            elif MARKDOWN_INDENTED_CODE.match(line) is not None:
                visible.append(masked(line))
            else:
                visible.append(line)
            continue

        visible.append(masked(line))
        if match is None:
            continue
        fence = match.group("fence")
        remainder = line[match.end() :].strip()
        if fence[0] == fence_character and len(fence) >= fence_length and not remainder:
            fence_character = None
            fence_length = 0

    rendered = "".join(visible)
    characters = list(rendered)
    position = 0
    while position < len(rendered):
        if rendered[position] != "`":
            position += 1
            continue
        run_end = position
        while run_end < len(rendered) and rendered[run_end] == "`":
            run_end += 1
        delimiter = rendered[position:run_end]
        closing = rendered.find(delimiter, run_end)
        if closing < 0:
            position = run_end
            continue
        for index in range(position, closing + len(delimiter)):
            if characters[index] != "\n":
                characters[index] = " "
        position = closing + len(delimiter)
    return "".join(characters)


def _suggest_class(root: Path, readme: str) -> str:
    name = root.name.lower()
    lowered = readme.lower()
    if "archived" in name or "⚠️ archived" in lowered or "this repository is archived" in lowered:
        return "F"
    if name.endswith("-play") or name.startswith("pages--") or "compiled build" in lowered:
        return "D"
    if any(term in name for term in ("theory", "research", "inquiry", "corpus")):
        return "E"
    if any(term in name for term in ("sdk", "schema", "engine", "framework", "bridge")):
        return "C"
    return "B"


def _findings(
    root: Path,
    readme: str,
    record_path: Path | None,
    record_errors: list[str],
    signals: dict[str, int],
    broken_local_links: list[str],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if not readme:
        findings.append({"severity": "error", "code": "missing-readme", "message": "Root README is missing."})
    if record_path is None:
        findings.append(
            {
                "severity": "error",
                "code": "missing-project-record",
                "message": "No canonical project-record.yml exists; all documentation classes require one.",
            },
        )
    for error in record_errors:
        findings.append({"severity": "error", "code": "invalid-project-record", "message": error})
    if broken_local_links:
        preview = "; ".join(broken_local_links[:3])
        findings.append(
            {
                "severity": "error",
                "code": "broken-local-links",
                "message": f"{len(broken_local_links)} broken local link(s): {preview}",
            },
        )
    for dimension, signal_count in signals.items():
        if signal_count <= 1:
            findings.append(
                {
                    "severity": "warning",
                    "code": f"few-{dimension.replace('_', '-')}-signals",
                    "message": (
                        f"Automated scan found {signal_count} {dimension.replace('_', ' ')} "
                        "structural marker(s); human quality assessment is still required."
                    ),
                },
            )
    if (root / "docs").is_dir() and signals["cross_linking"] <= 1:
        findings.append(
            {
                "severity": "warning",
                "code": "orphan-docs",
                "message": "Documentation exists but is weakly linked from the project surface.",
            },
        )
    return findings


def load_schema(path: str | Path) -> dict[str, Any]:
    """Load a JSON Schema stored as YAML or JSON."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Schema is not a mapping: {path}")
    return data
