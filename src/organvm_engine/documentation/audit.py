"""Deterministic, read-only repository documentation audit."""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

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
MAX_MARKDOWN_FILE_BYTES = 2_000_000
MAX_MARKDOWN_REPOSITORY_BYTES = 16_000_000
MAX_MARKDOWN_FILES = 4_096
MARKDOWN_FENCE = re.compile(r"^[ ]{0,3}(?P<fence>`{3,}|~{3,})")
MARKDOWN_BLOCKQUOTE = re.compile(r"^[ ]{0,3}>[ \t]?")
MARKDOWN_LIST_MARKER = re.compile(
    r"^(?P<indent>[ \t]*)(?P<marker>[-+*]|\d{1,9}[.)])(?P<spacing>[ \t]+)",
)
REFERENCE_DEFINITION = re.compile(
    r"^[ ]{0,3}\[(?P<label>[^\]\n]+)\]:[ \t]*(?P<destination><[^>\n]+>|[^\s]+)",
)
EMPTY_REFERENCE_DEFINITION = re.compile(
    r"^[ ]{0,3}\[(?P<label>[^\]\n]+)\]:[ \t]*(?:\r?\n)?$",
)
REFERENCE_DESTINATION_CONTINUATION = re.compile(
    r"^[ ]{0,3}(?P<destination><[^>\n]+>|[^\s]+)",
)
REFERENCE_USAGE = re.compile(r"(?<!!)\[(?P<label>[^\]\n]+)\](?![\[(])")
COLLAPSED_REFERENCE_USAGE = re.compile(r"(?<!!)\[(?P<label>[^\]\n]+)\]\[\]")
MARKDOWN_ESCAPABLE = frozenset(r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~""")


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
    readme = _read_bounded_markdown(readme_path) if readme_path else None
    if readme is None:
        readme_path = None
        readme = ""
    markdown_inputs, markdown_limit_exceeded = _markdown_inputs(root_path)
    markdown_files = [path for path, _text in markdown_inputs]
    corpus = "\n".join(text for _path, text in markdown_inputs)
    lowered = corpus.lower()
    readme_lower = readme.lower()
    valid_local_links, broken_local_links = _inspect_local_links(root_path, markdown_inputs)

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
        markdown_limit_exceeded,
    )

    return {
        "repository": root_path.name,
        "path": str(root_path),
        "documentation_class": doc_class,
        "class_source": "project-record" if record else "heuristic",
        "has_readme": readme_path is not None,
        "has_project_record": record_path is not None,
        "markdown_files": len(markdown_files),
        "markdown_input_limit_exceeded": markdown_limit_exceeded,
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
            if _safe_markdown_file(root, path)
            and path.name.casefold() == "readme.md"
            and path.stat().st_size <= MAX_MARKDOWN_FILE_BYTES
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


def _markdown_inputs(root: Path) -> tuple[list[tuple[Path, str]], bool]:
    """Read a deterministic repository-bounded Markdown corpus."""
    inputs: list[tuple[Path, str]] = []
    total_bytes = 0
    for current, dirs, names in os.walk(root):
        dirs[:] = sorted(name for name in dirs if name not in SKIP_DIRS)
        current_path = Path(current)
        for name in sorted(names):
            if Path(name).suffix.casefold() != ".md":
                continue
            path = current_path / name
            try:
                if not _safe_markdown_file(root, path):
                    continue
            except OSError:
                continue
            payload = _read_bounded_markdown_payload(path)
            if payload is None:
                continue
            text, byte_count = payload
            if (
                len(inputs) >= MAX_MARKDOWN_FILES
                or total_bytes + byte_count > MAX_MARKDOWN_REPOSITORY_BYTES
            ):
                return inputs, True
            inputs.append((path, text))
            total_bytes += byte_count
    return inputs, False


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


def _inspect_local_links(
    root: Path,
    markdown_inputs: list[tuple[Path, str]],
) -> tuple[set[Path], list[str]]:
    valid: set[Path] = set()
    broken: list[str] = []
    for source, text in markdown_inputs:
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
            try:
                candidate = (source.parent / path_text).resolve()
            except (OSError, RuntimeError, ValueError):
                broken.append(f"{source.relative_to(root)} -> {target}")
                continue
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
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _mask_markdown_html_comments(_mask_markdown_code(text))
    text, reference_destinations = _reference_destinations(text)
    destinations: list[str] = list(reference_destinations)
    for position in _markdown_link_destination_starts(text):
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
                elif (
                    character == "\\"
                    and position < len(text)
                    and text[position] in MARKDOWN_ESCAPABLE
                ):
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
                elif (
                    character == "\\"
                    and position + 1 < len(text)
                    and text[position + 1] in MARKDOWN_ESCAPABLE
                ):
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
        if rendered and _markdown_link_has_closing_delimiter(text, position):
            destinations.append(rendered)
    return destinations


def _markdown_link_destination_starts(text: str) -> Iterator[int]:
    """Yield inline-link destination starts in one forward bracket pass."""
    open_brackets = 0
    for position, character in enumerate(text):
        if character not in "[]" or _markdown_character_is_escaped(text, position):
            continue
        if character == "[":
            open_brackets += 1
            continue
        if open_brackets == 0:
            continue
        open_brackets -= 1
        if text.startswith("](", position):
            yield position + 2


def _markdown_link_has_closing_delimiter(text: str, position: int) -> bool:
    """Return whether a parsed destination has a valid outer closing delimiter."""
    if position < len(text) and text[position] == ")":
        return True
    if position >= len(text) or not text[position].isspace():
        return False
    while position < len(text) and text[position].isspace():
        position += 1
    if position < len(text) and text[position] == ")":
        return True
    if position >= len(text) or text[position] not in "\"'(":
        return False
    opener = text[position]
    closer = ")" if opener == "(" else opener
    position += 1
    while position < len(text):
        if (
            text[position] == "\\"
            and position + 1 < len(text)
            and text[position + 1] in MARKDOWN_ESCAPABLE
        ):
            position += 2
            continue
        if text[position] == closer:
            position += 1
            break
        position += 1
    else:
        return False
    while position < len(text) and text[position].isspace():
        position += 1
    return position < len(text) and text[position] == ")"


def _markdown_character_is_escaped(text: str, position: int) -> bool:
    """Return whether a Markdown punctuation character has an odd slash prefix."""
    backslashes = 0
    position -= 1
    while position >= 0 and text[position] == "\\":
        backslashes += 1
        position -= 1
    return backslashes % 2 == 1


def _safe_markdown_file(root: Path, path: Path) -> bool:
    """Reject symlinked Markdown inputs and paths resolving outside the root."""
    return _safe_audit_file(root, path)


def _read_bounded_markdown(path: Path) -> str | None:
    """Read at most the documented Markdown input limit, including races."""
    payload = _read_bounded_markdown_payload(path)
    return payload[0] if payload is not None else None


def _read_bounded_markdown_payload(path: Path) -> tuple[str, int] | None:
    """Read one bounded Markdown input and retain its exact byte count."""
    try:
        with path.open("rb") as stream:
            payload = stream.read(MAX_MARKDOWN_FILE_BYTES + 1)
    except OSError:
        return None
    if len(payload) > MAX_MARKDOWN_FILE_BYTES:
        return None
    return payload.decode("utf-8", errors="replace"), len(payload)


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
    lines = text.splitlines(keepends=True)
    index = 0
    while index < len(lines):
        line = lines[index]
        definition_line, container_prefixes = _markdown_reference_containers(line)
        match = REFERENCE_DEFINITION.match(definition_line)
        consumed_lines = 1
        if (
            match is None
            and (empty := EMPTY_REFERENCE_DEFINITION.match(definition_line)) is not None
        ):
            if index + 1 < len(lines):
                continuation_line = _markdown_apply_reference_containers(
                    lines[index + 1],
                    container_prefixes,
                )
                continuation = (
                    REFERENCE_DESTINATION_CONTINUATION.match(continuation_line)
                    if continuation_line is not None
                    else None
                )
                if continuation is not None:
                    match = empty
                    destination = continuation.group("destination")
                    consumed_lines = 2
                else:
                    destination = None
            else:
                destination = None
        else:
            destination = match.group("destination") if match is not None else None
        if match is None or destination is None:
            visible_lines.append(line)
            index += 1
            continue
        label = _normalize_reference_label(match.group("label"))
        definitions.setdefault(
            label,
            _markdown_unescape(destination.strip().strip("<>")),
        )
        for consumed in lines[index : index + consumed_lines]:
            visible_lines.append(
                "".join("\n" if char == "\n" else " " for char in consumed),
            )
        index += consumed_lines

    visible = "".join(visible_lines)
    destinations: list[str] = []
    for pattern in (COLLAPSED_REFERENCE_USAGE, REFERENCE_USAGE):
        for match in pattern.finditer(visible):
            if _markdown_character_is_escaped(visible, match.start()):
                continue
            destination = definitions.get(_normalize_reference_label(match.group("label")))
            if destination is not None:
                destinations.append(destination)
    return visible, destinations


def _markdown_reference_containers(
    value: str,
) -> tuple[str, tuple[tuple[str, int], ...]]:
    """Strip quote/list prefixes and retain operations for a continuation line."""
    prefixes: list[tuple[str, int]] = []
    while True:
        quote = MARKDOWN_BLOCKQUOTE.match(value)
        if quote is not None:
            prefixes.append(("quote", 0))
            value = value[quote.end() :]
            continue
        list_prefix = _markdown_list_prefix(value)
        if list_prefix is None:
            break
        prefix_end, content_indent = list_prefix
        prefixes.append(("indent", content_indent))
        value = value[prefix_end:]
    return value, tuple(prefixes)


def _markdown_apply_reference_containers(
    value: str,
    prefixes: tuple[tuple[str, int], ...],
) -> str | None:
    """Apply one definition line's quote/list prefixes to its continuation."""
    for kind, columns in prefixes:
        if kind == "quote":
            quote = MARKDOWN_BLOCKQUOTE.match(value)
            if quote is None:
                return None
            value = value[quote.end() :]
            continue
        if _markdown_indent_columns(value) < columns:
            return None
        value = _markdown_remove_indent(value, columns)
    return value


def _normalize_reference_label(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip()).casefold()


def _markdown_unescape(value: str) -> str:
    """Decode the ASCII punctuation escapes permitted by CommonMark."""
    rendered: list[str] = []
    position = 0
    while position < len(value):
        if (
            value[position] == "\\"
            and position + 1 < len(value)
            and value[position + 1] in MARKDOWN_ESCAPABLE
        ):
            position += 1
        rendered.append(value[position])
        position += 1
    return "".join(rendered)


def _mask_markdown_html_comments(text: str) -> str:
    """Mask rendered-out HTML comments while retaining source line structure."""
    characters = list(text)
    position = 0
    while (start := text.find("<!--", position)) >= 0:
        closing = text.find("-->", start + 4)
        end = len(text) if closing < 0 else closing + 3
        for index in range(start, end):
            if characters[index] != "\n":
                characters[index] = " "
        position = end
    return "".join(characters)


def _mask_markdown_code(text: str) -> str:
    """Mask code while preserving rendered content inside list containers."""

    def masked(value: str) -> str:
        return "".join("\n" if character == "\n" else " " for character in value)

    lines = text.splitlines(keepends=True)
    visible: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    fence_container_indent = 0
    fence_quote_depth = 0
    list_content_indents: list[int] = []
    paragraph_container: tuple[int, int] | None = None
    paragraph_open = False
    for line in lines:
        container_line, quote_depth = _markdown_strip_blockquotes_with_depth(line)
        stripped = container_line.strip(" \t\r\n")
        leading_columns = _markdown_indent_columns(container_line)
        if fence_character is not None and (
            quote_depth < fence_quote_depth
            or (stripped and leading_columns < fence_container_indent)
        ):
            fence_character = None
            fence_length = 0
            fence_container_indent = 0
            fence_quote_depth = 0
        if stripped and fence_character is None:
            while list_content_indents and leading_columns < list_content_indents[-1]:
                list_content_indents.pop()

        container_indent = list_content_indents[-1] if list_content_indents else 0
        current_container = (quote_depth, container_indent)
        if paragraph_container != current_container:
            paragraph_open = False
            paragraph_container = current_container

        if fence_character is not None:
            visible.append(masked(line))
            relative_line = _markdown_remove_indent(
                container_line,
                fence_container_indent,
            )
            match = MARKDOWN_FENCE.match(relative_line)
            if match is None:
                continue
            fence = match.group("fence")
            remainder = relative_line[match.end() :].strip()
            if (
                fence[0] == fence_character
                and len(fence) >= fence_length
                and not remainder
            ):
                fence_character = None
                fence_length = 0
                fence_container_indent = 0
                fence_quote_depth = 0
            continue

        relative_line = _markdown_remove_indent(container_line, container_indent)
        match = MARKDOWN_FENCE.match(relative_line)
        if match is not None:
            opening_fence = match.group("fence")
            info_string = relative_line[match.end() :].rstrip("\r\n")
            if opening_fence[0] == "`" and "`" in info_string:
                match = None
        if match is not None:
            fence = match.group("fence")
            fence_character = fence[0]
            fence_length = len(fence)
            fence_container_indent = container_indent
            fence_quote_depth = quote_depth
            paragraph_open = False
            visible.append(masked(line))
            continue

        list_prefix = _markdown_list_prefix(relative_line)
        relative_indent = _markdown_indent_columns(relative_line)
        if list_prefix is not None:
            prefix_end, prefix_columns = list_prefix
            content_indent = container_indent + prefix_columns
            list_content_indents.append(content_indent)
            content = relative_line[prefix_end:]
            paragraph_container = (quote_depth, content_indent)
            if _markdown_indent_columns(content) >= 4:
                paragraph_open = False
                visible.append(masked(line))
            else:
                paragraph_open = _markdown_opens_paragraph(content)
                visible.append(line)
        elif relative_indent >= 4 and not paragraph_open:
            visible.append(masked(line))
        else:
            visible.append(line)
            paragraph_open = _markdown_opens_paragraph(relative_line)

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
        if _markdown_character_is_escaped(rendered, position):
            position = run_end
            continue
        delimiter_length = run_end - position
        closing = _next_exact_backtick_run(rendered, run_end, delimiter_length)
        if closing is None:
            position = run_end
            continue
        for index in range(position, closing + delimiter_length):
            if characters[index] != "\n":
                characters[index] = " "
        position = closing + delimiter_length
    return "".join(characters)


def _next_exact_backtick_run(text: str, start: int, length: int) -> int | None:
    """Find a whole backtick run whose length exactly matches ``length``."""
    position = text.find("`", start)
    while position >= 0:
        run_end = position
        while run_end < len(text) and text[run_end] == "`":
            run_end += 1
        if run_end - position == length and not _markdown_character_is_escaped(
            text,
            position,
        ):
            return position
        position = text.find("`", run_end)
    return None


def _markdown_indent_columns(value: str) -> int:
    """Return CommonMark-style columns occupied by leading spaces and tabs."""
    columns = 0
    for character in value:
        if character == " ":
            columns += 1
        elif character == "\t":
            columns += 4 - (columns % 4)
        else:
            break
    return columns


def _markdown_list_prefix(value: str) -> tuple[int, int] | None:
    """Return a list prefix end/width while preserving excess marker padding."""
    match = MARKDOWN_LIST_MARKER.match(value)
    if match is None or _markdown_indent_columns(value) > 3:
        return None
    spacing_start = match.start("spacing")
    prefix_before_spacing = _markdown_column_width(value[:spacing_start])
    spacing_columns = (
        _markdown_column_width(value[: match.end()]) - prefix_before_spacing
    )
    prefix_end = match.end() if spacing_columns <= 4 else spacing_start + 1
    return prefix_end, _markdown_column_width(value[:prefix_end])


def _markdown_strip_blockquotes(value: str) -> str:
    """Strip nested CommonMark blockquote markers for code classification."""
    return _markdown_strip_blockquotes_with_depth(value)[0]


def _markdown_strip_blockquotes_with_depth(value: str) -> tuple[str, int]:
    """Strip nested blockquote markers and return their container depth."""
    depth = 0
    while (match := MARKDOWN_BLOCKQUOTE.match(value)) is not None:
        value = value[match.end() :]
        depth += 1
    return value, depth


def _markdown_opens_paragraph(value: str) -> bool:
    """Return whether a visible line keeps an ordinary paragraph open."""
    stripped = value.strip(" \t\r\n")
    if not stripped or _markdown_indent_columns(value) >= 4:
        return False
    if re.match(r"^(?:#{1,6}(?:[ \t]+|$)|(?:[-*_][ \t]*){3,}$)", stripped):
        return False
    if MARKDOWN_FENCE.match(value) is not None or _markdown_list_prefix(value) is not None:
        return False
    return not stripped.startswith(("<", ">"))


def _markdown_column_width(value: str) -> int:
    """Return display columns occupied by a single Markdown line prefix."""
    columns = 0
    for character in value:
        if character in "\r\n":
            break
        if character == "\t":
            columns += 4 - (columns % 4)
        else:
            columns += 1
    return columns


def _markdown_remove_indent(value: str, columns: int) -> str:
    """Remove up to ``columns`` of container indentation from a line."""
    consumed_columns = 0
    position = 0
    while position < len(value) and consumed_columns < columns:
        character = value[position]
        if character == " ":
            consumed_columns += 1
        elif character == "\t":
            consumed_columns += 4 - (consumed_columns % 4)
        else:
            break
        position += 1
    return value[position:]


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
    markdown_limit_exceeded: bool,
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
    if markdown_limit_exceeded:
        findings.append(
            {
                "severity": "error",
                "code": "markdown-input-limit",
                "message": (
                    "Markdown audit input exceeds the repository-wide "
                    f"{MAX_MARKDOWN_FILES}-file or "
                    f"{MAX_MARKDOWN_REPOSITORY_BYTES}-byte limit."
                ),
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
    schema_path = Path(path)
    try:
        return load_project_record(schema_path)
    except ValueError as exc:
        if str(exc) == f"Project record is not a mapping: {schema_path}":
            raise ValueError(f"Schema is not a mapping: {schema_path}") from exc
        raise
