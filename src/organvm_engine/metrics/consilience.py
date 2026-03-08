"""Consilience Index — measure how many independent sources confirm each derived principle.

A principle with consilience index 1 (single source, single domain) is a hypothesis.
A principle with index 4+ (multiple sources, multiple domains) approaches law.

Sources: research documents (YAML frontmatter cross_references + tags),
         derived-principles.md (source citations per principle).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class PrincipleRecord:
    """A derived principle with its consilience metadata."""

    code: str          # e.g. "Y1", "S3", "E1"
    title: str
    source_text: str   # The **Source:** line
    sources: list[str] = field(default_factory=list)  # Parsed source references
    domains: list[str] = field(default_factory=list)   # Inferred knowledge domains
    confirming_docs: list[str] = field(default_factory=list)  # Research docs that reference it

    @property
    def consilience_index(self) -> int:
        """Number of independent source citations."""
        return len(self.sources)

    @property
    def domain_breadth(self) -> int:
        """Number of distinct knowledge domains across sources."""
        return len(set(self.domains))

    @property
    def composite_score(self) -> float:
        """Composite: consilience_index * domain_breadth."""
        return self.consilience_index * self.domain_breadth

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "title": self.title,
            "source_text": self.source_text,
            "sources": self.sources,
            "domains": self.domains,
            "confirming_docs": self.confirming_docs,
            "consilience_index": self.consilience_index,
            "domain_breadth": self.domain_breadth,
            "composite_score": self.composite_score,
        }


@dataclass
class ResearchDoc:
    """A research document with its YAML metadata."""

    path: Path
    filename: str
    source: str          # e.g. "chatgpt", "claude-code"
    source_type: str     # e.g. "ai-artifact", "ai-generated-research"
    tags: list[str] = field(default_factory=list)
    cross_references: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "source": self.source,
            "source_type": self.source_type,
            "tags": self.tags,
            "cross_references": self.cross_references,
        }


@dataclass
class ConsilienceReport:
    """Full consilience analysis across principles and research corpus."""

    principles: list[PrincipleRecord] = field(default_factory=list)
    research_docs: list[ResearchDoc] = field(default_factory=list)

    @property
    def avg_consilience(self) -> float:
        if not self.principles:
            return 0.0
        return sum(p.consilience_index for p in self.principles) / len(self.principles)

    @property
    def hypothesis_count(self) -> int:
        """Principles with consilience index == 1."""
        return sum(1 for p in self.principles if p.consilience_index == 1)

    @property
    def law_count(self) -> int:
        """Principles with consilience index >= 4."""
        return sum(1 for p in self.principles if p.consilience_index >= 4)

    def by_strength(self) -> list[PrincipleRecord]:
        """Principles sorted by composite score, highest first."""
        return sorted(self.principles, key=lambda p: -p.composite_score)

    def summary(self) -> str:
        lines = [
            "Consilience Index Report",
            "=" * 40,
            f"Principles: {len(self.principles)}",
            f"Research docs: {len(self.research_docs)}",
            f"Avg consilience: {self.avg_consilience:.1f}",
            f"Hypotheses (index=1): {self.hypothesis_count}",
            f"Approaching law (index>=4): {self.law_count}",
            "",
            f"{'Code':<6} {'CI':<4} {'Domains':<8} {'Title'}",
            "-" * 60,
        ]
        for p in self.by_strength():
            lines.append(
                f"{p.code:<6} {p.consilience_index:<4} {p.domain_breadth:<8} {p.title}",
            )
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "principle_count": len(self.principles),
            "research_doc_count": len(self.research_docs),
            "avg_consilience": round(self.avg_consilience, 2),
            "hypothesis_count": self.hypothesis_count,
            "law_count": self.law_count,
            "principles": [p.to_dict() for p in self.by_strength()],
        }


# ---------------------------------------------------------------------------
# Domain inference
# ---------------------------------------------------------------------------

# Map source descriptions to knowledge domains
_DOMAIN_KEYWORDS = {
    "case study": "empirical",
    "case studies": "empirical",
    "bootstrap": "empirical",
    "shipping": "empirical",
    "synthesis": "synthesis",
    "four-branch": "synthesis",
    "structural audit": "engineering",
    "structural": "engineering",
    "code": "engineering",
    "architecture": "engineering",
    "ci": "engineering",
    "gemini": "cross-agent",
    "styx": "cross-agent",
    "agent": "cross-agent",
    "handoff": "cross-agent",
    "manifesto": "philosophy",
    "metaphysics": "philosophy",
    "ontolog": "philosophy",
    "plato": "philosophy",
    "aristotle": "philosophy",
    "morphodynamics": "physics-analogy",
    "accretion": "physics-analogy",
    "assembly": "physics-analogy",
    "superorganism": "biology-analogy",
    "autopoiesis": "systems-theory",
    "systems": "systems-theory",
    "cybernetics": "systems-theory",
    "feedback": "systems-theory",
    "personal-hell": "lived-experience",
    "experience": "lived-experience",
    "session": "lived-experience",
    "revenue": "economics",
    "economic": "economics",
    "market": "economics",
    "bootstrap-to-scale": "economics",
    "essay": "discourse",
    "rhetoric": "discourse",
}


def _infer_domains(source_text: str) -> list[str]:
    """Infer knowledge domains from a source citation string."""
    domains: set[str] = set()
    lower = source_text.lower()
    for keyword, domain in _DOMAIN_KEYWORDS.items():
        if keyword in lower:
            domains.add(domain)
    return sorted(domains) if domains else ["unclassified"]


def _parse_sources(source_text: str) -> list[str]:
    """Parse a **Source:** line into individual source references.

    Examples:
        "2026-03-07 four-branch synthesis (P2), 2026-03-06 materia-collider"
        → ["2026-03-07 four-branch synthesis (P2)", "2026-03-06 materia-collider"]
    """
    # Split on comma followed by a date or end
    parts = re.split(r",\s*(?=\d{4}-)", source_text)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_PRINCIPLE_HEADER = re.compile(
    r"^###\s+([A-Z]\d+)[.:]\s+(.+)$",
)
_SOURCE_LINE = re.compile(
    r"^\*\*Source:\*\*\s+(.+)$",
)


def parse_derived_principles(text: str) -> list[PrincipleRecord]:
    """Parse derived-principles.md into PrincipleRecord list."""
    principles: list[PrincipleRecord] = []
    current: PrincipleRecord | None = None

    for line in text.splitlines():
        header_match = _PRINCIPLE_HEADER.match(line)
        if header_match:
            if current is not None:
                principles.append(current)
            code = header_match.group(1)
            title = header_match.group(2).strip()
            current = PrincipleRecord(code=code, title=title, source_text="")
            continue

        if current is not None:
            source_match = _SOURCE_LINE.match(line)
            if source_match:
                source_text = source_match.group(1).strip()
                current.source_text = source_text
                current.sources = _parse_sources(source_text)
                current.domains = _infer_domains(source_text)

    if current is not None:
        principles.append(current)

    return principles


def _parse_frontmatter(path: Path) -> dict:
    """Extract YAML frontmatter from a markdown file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    if not text.startswith("---"):
        return {}

    end = text.find("---", 3)
    if end == -1:
        return {}

    try:
        return yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return {}


def scan_research_docs(research_dir: Path) -> list[ResearchDoc]:
    """Scan a research directory for documents with YAML frontmatter."""
    docs: list[ResearchDoc] = []

    if not research_dir.is_dir():
        return docs

    for md_file in sorted(research_dir.glob("*.md")):
        fm = _parse_frontmatter(md_file)
        if not fm:
            continue
        docs.append(ResearchDoc(
            path=md_file,
            filename=md_file.name,
            source=fm.get("source", "unknown"),
            source_type=fm.get("source_type", "unknown"),
            tags=fm.get("tags") or [],
            cross_references=fm.get("cross_references") or [],
        ))

    return docs


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def compute_consilience(
    principles_path: Path | None = None,
    research_dir: Path | None = None,
) -> ConsilienceReport:
    """Compute the full consilience report.

    Args:
        principles_path: Path to derived-principles.md.
            Defaults to praxis-perpetua/lessons/derived-principles.md.
        research_dir: Path to research directory.
            Defaults to praxis-perpetua/research/.

    Returns:
        ConsilienceReport with indexed principles and research doc inventory.
    """
    from organvm_engine.paths import workspace_root

    ws = workspace_root()
    praxis = ws / "meta-organvm" / "praxis-perpetua"

    if principles_path is None:
        principles_path = praxis / "lessons" / "derived-principles.md"
    if research_dir is None:
        research_dir = praxis / "research"

    # Parse principles
    principles: list[PrincipleRecord] = []
    if principles_path.is_file():
        text = principles_path.read_text(encoding="utf-8", errors="replace")
        principles = parse_derived_principles(text)

    # Scan research docs
    research_docs = scan_research_docs(research_dir)

    # Cross-reference: for each research doc, check if it's cited by any principle
    doc_filenames = {d.filename for d in research_docs}
    for p in principles:
        for src in p.sources:
            # Check if any research doc filename appears in the source text
            for fname in doc_filenames:
                stem = Path(fname).stem
                if stem in src:
                    p.confirming_docs.append(fname)

    return ConsilienceReport(
        principles=principles,
        research_docs=research_docs,
    )
