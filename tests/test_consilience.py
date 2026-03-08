"""Tests for metrics/consilience.py."""

import pytest
from pathlib import Path

from organvm_engine.metrics.consilience import (
    ConsilienceReport,
    PrincipleRecord,
    ResearchDoc,
    _infer_domains,
    _parse_sources,
    compute_consilience,
    parse_derived_principles,
    scan_research_docs,
)


class TestPrincipleRecord:
    def test_consilience_index(self):
        p = PrincipleRecord(
            code="Y1", title="Test", source_text="a, b, c",
            sources=["a", "b", "c"],
        )
        assert p.consilience_index == 3

    def test_domain_breadth(self):
        p = PrincipleRecord(
            code="Y1", title="Test", source_text="",
            domains=["engineering", "philosophy", "engineering"],
        )
        assert p.domain_breadth == 2

    def test_composite_score(self):
        p = PrincipleRecord(
            code="Y1", title="Test", source_text="",
            sources=["a", "b", "c"],
            domains=["eng", "phil"],
        )
        assert p.composite_score == 6.0  # 3 * 2

    def test_to_dict(self):
        p = PrincipleRecord(
            code="S1", title="Test principle", source_text="src",
            sources=["src"],
            domains=["engineering"],
            confirming_docs=["doc.md"],
        )
        d = p.to_dict()
        assert d["code"] == "S1"
        assert d["consilience_index"] == 1
        assert d["domain_breadth"] == 1
        assert d["confirming_docs"] == ["doc.md"]

    def test_empty_sources(self):
        p = PrincipleRecord(code="X1", title="Empty", source_text="")
        assert p.consilience_index == 0
        assert p.domain_breadth == 0
        assert p.composite_score == 0.0


class TestConsilienceReport:
    def _make_report(self):
        return ConsilienceReport(
            principles=[
                PrincipleRecord(
                    code="Y1", title="Strong", source_text="",
                    sources=["a", "b", "c", "d"],
                    domains=["eng", "phil", "empirical", "lived"],
                ),
                PrincipleRecord(
                    code="S1", title="Medium", source_text="",
                    sources=["a", "b"],
                    domains=["eng"],
                ),
                PrincipleRecord(
                    code="C1", title="Weak", source_text="",
                    sources=["a"],
                    domains=["eng"],
                ),
            ],
            research_docs=[
                ResearchDoc(
                    path=Path("test.md"),
                    filename="test.md",
                    source="chatgpt",
                    source_type="ai-artifact",
                ),
            ],
        )

    def test_avg_consilience(self):
        r = self._make_report()
        # (4 + 2 + 1) / 3 = 2.33
        assert abs(r.avg_consilience - 2.33) < 0.1

    def test_hypothesis_count(self):
        r = self._make_report()
        assert r.hypothesis_count == 1  # C1 has index 1

    def test_law_count(self):
        r = self._make_report()
        assert r.law_count == 1  # Y1 has index 4

    def test_by_strength(self):
        r = self._make_report()
        ordered = r.by_strength()
        assert ordered[0].code == "Y1"  # highest composite
        assert ordered[-1].code == "C1"  # lowest composite

    def test_summary_contains_table(self):
        r = self._make_report()
        s = r.summary()
        assert "Consilience Index Report" in s
        assert "Y1" in s
        assert "Avg consilience:" in s

    def test_to_dict(self):
        r = self._make_report()
        d = r.to_dict()
        assert d["principle_count"] == 3
        assert d["research_doc_count"] == 1
        assert d["hypothesis_count"] == 1
        assert d["law_count"] == 1

    def test_empty_report(self):
        r = ConsilienceReport()
        assert r.avg_consilience == 0.0
        assert r.hypothesis_count == 0
        assert r.law_count == 0


class TestParseSources:
    def test_single_source(self):
        result = _parse_sources("2026-03-07 four-branch synthesis")
        assert result == ["2026-03-07 four-branch synthesis"]

    def test_multiple_sources(self):
        result = _parse_sources(
            "2026-03-07 four-branch synthesis (P2), 2026-03-06 materia-collider"
        )
        assert len(result) == 2
        assert "2026-03-07 four-branch synthesis (P2)" in result
        assert "2026-03-06 materia-collider" in result

    def test_empty(self):
        result = _parse_sources("")
        assert result == []

    def test_three_sources(self):
        result = _parse_sources(
            "2026-03-07 synthesis (P1), 2026-03-06 audit, 2025-12 manifesto"
        )
        assert len(result) == 3


class TestInferDomains:
    def test_engineering(self):
        d = _infer_domains("structural audit")
        assert "engineering" in d

    def test_philosophy(self):
        d = _infer_domains("metaphysics of flux")
        assert "philosophy" in d

    def test_empirical(self):
        d = _infer_domains("bootstrap case studies")
        assert "empirical" in d

    def test_mixed(self):
        d = _infer_domains("2026-03-07 four-branch synthesis (P2), 2026-03-06 structural audit")
        assert "synthesis" in d
        assert "engineering" in d

    def test_unclassified(self):
        d = _infer_domains("something completely random")
        assert d == ["unclassified"]

    def test_economics(self):
        d = _infer_domains("revenue imperative + market analysis")
        assert "economics" in d


class TestParseDerivedPrinciples:
    def test_parses_principle(self):
        text = """# Derived Principles

## Structural Principles

### S1. Superproject allowlist `.gitignore` silently hides files
**Source:** 2026-03-06 Gemini Styx session

Description text here.

### S2. SOPs and governance docs belong in governed submodules
**Source:** 2026-03-06 Gemini Styx session, 2026-03-07 review

More description.
"""
        principles = parse_derived_principles(text)
        assert len(principles) == 2
        assert principles[0].code == "S1"
        assert principles[0].title == "Superproject allowlist `.gitignore` silently hides files"
        assert "Gemini Styx session" in principles[0].source_text
        assert len(principles[0].sources) >= 1

    def test_parses_systemic_principles(self):
        text = """### Y1. Structural integrity through semantic flexibility
**Source:** 2026-03-07 four-branch product implementation synthesis (P1)

### Y2. Governance is soil, not bureaucracy
**Source:** 2026-03-07 four-branch synthesis (P2), 2026-03-06 materia-collider founding document
"""
        principles = parse_derived_principles(text)
        assert len(principles) == 2
        assert principles[0].code == "Y1"
        assert principles[1].code == "Y2"
        assert len(principles[1].sources) == 2

    def test_empty_text(self):
        assert parse_derived_principles("") == []

    def test_no_principles(self):
        assert parse_derived_principles("# Just a heading\nSome text.") == []

    def test_principle_with_colon_separator(self):
        text = """### Y6: The system is ontologically stratified
**Source:** 2026-03-08 ontological topology analysis
"""
        principles = parse_derived_principles(text)
        assert len(principles) == 1
        assert principles[0].code == "Y6"


class TestScanResearchDocs:
    def test_scans_directory(self, tmp_path):
        doc = tmp_path / "2026-01-test.md"
        doc.write_text("""---
source: chatgpt
source_type: ai-artifact
tags:
  - test
  - ontology
cross_references:
  - meta-organvm/VISION.md
---
# Test Document
Content here.
""")
        docs = scan_research_docs(tmp_path)
        assert len(docs) == 1
        assert docs[0].filename == "2026-01-test.md"
        assert docs[0].source == "chatgpt"
        assert "test" in docs[0].tags
        assert len(docs[0].cross_references) == 1

    def test_skips_no_frontmatter(self, tmp_path):
        doc = tmp_path / "no-fm.md"
        doc.write_text("# No Frontmatter\nJust text.")
        docs = scan_research_docs(tmp_path)
        assert len(docs) == 0

    def test_empty_dir(self, tmp_path):
        docs = scan_research_docs(tmp_path)
        assert docs == []

    def test_nonexistent_dir(self, tmp_path):
        docs = scan_research_docs(tmp_path / "nope")
        assert docs == []

    def test_multiple_docs(self, tmp_path):
        for i in range(3):
            doc = tmp_path / f"doc-{i}.md"
            doc.write_text(f"---\nsource: test-{i}\nsource_type: test\n---\n# Doc {i}\n")
        docs = scan_research_docs(tmp_path)
        assert len(docs) == 3


class TestResearchDoc:
    def test_to_dict(self):
        d = ResearchDoc(
            path=Path("test.md"),
            filename="test.md",
            source="claude",
            source_type="ai-generated-research",
            tags=["ontology"],
            cross_references=["VISION.md"],
        )
        result = d.to_dict()
        assert result["source"] == "claude"
        assert result["tags"] == ["ontology"]
