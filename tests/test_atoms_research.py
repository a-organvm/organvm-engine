"""Tests for the research activation stage of the atoms pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

class TestParseFrontmatter:
    """parse_frontmatter extracts YAML-like metadata from markdown."""

    def test_full_frontmatter(self):
        from organvm_engine.atoms.research import parse_frontmatter

        text = (
            "---\n"
            "title: AI Conductor SDLC Research\n"
            "status: reference-actionable\n"
            "date: 2026-03-08\n"
            'tags: [python, fastapi, "github-actions"]\n'
            "---\n"
            "# Body here\n"
        )
        fm = parse_frontmatter(text)
        assert fm["title"] == "AI Conductor SDLC Research"
        assert fm["status"] == "reference-actionable"
        assert fm["date"] == "2026-03-08"
        assert "python" in fm["tags"]
        assert "fastapi" in fm["tags"]

    def test_no_frontmatter(self):
        from organvm_engine.atoms.research import parse_frontmatter

        text = "# Just a heading\n\nSome content.\n"
        fm = parse_frontmatter(text)
        assert fm == {}

    def test_partial_frontmatter(self):
        from organvm_engine.atoms.research import parse_frontmatter

        text = "---\nstatus: reference\n---\n# Heading\n"
        fm = parse_frontmatter(text)
        assert fm["status"] == "reference"
        assert "title" not in fm

    def test_status_with_quotes(self):
        from organvm_engine.atoms.research import parse_frontmatter

        text = '---\nstatus: "reference-actionable"\n---\n'
        fm = parse_frontmatter(text)
        assert fm["status"] == "reference-actionable"


# ---------------------------------------------------------------------------
# Document parsing
# ---------------------------------------------------------------------------

class TestParseResearchDoc:
    """parse_research_doc reads a markdown file into a ResearchDoc."""

    def test_parse_with_frontmatter(self, tmp_path):
        from organvm_engine.atoms.research import parse_research_doc

        doc_path = tmp_path / "2026-03-08-test-research.md"
        doc_path.write_text(
            "---\n"
            "title: Test Research\n"
            "status: reference-actionable\n"
            "date: 2026-03-08\n"
            "tags: [python, mcp]\n"
            "---\n"
            "# Test Research\n\n"
            "Some content about implementation.\n",
        )

        doc = parse_research_doc(doc_path)
        assert doc.title == "Test Research"
        assert doc.status == "reference-actionable"
        assert doc.date == "2026-03-08"
        assert "python" in doc.tags
        assert doc.is_scannable is True
        assert doc.is_activated is False

    def test_parse_without_frontmatter(self, tmp_path):
        from organvm_engine.atoms.research import parse_research_doc

        doc_path = tmp_path / "2026-03-08-bare-doc.md"
        doc_path.write_text("# Bare Document\n\nJust some text.\n")

        doc = parse_research_doc(doc_path)
        assert doc.title == "Bare Document"
        assert doc.status == "reference"
        assert doc.date == "2026-03-08"
        assert doc.is_scannable is True

    def test_parse_activated_doc(self, tmp_path):
        from organvm_engine.atoms.research import parse_research_doc

        doc_path = tmp_path / "activated.md"
        doc_path.write_text("---\nstatus: reference-activated\n---\n# Done\n")

        doc = parse_research_doc(doc_path)
        assert doc.is_activated is True
        assert doc.is_scannable is False


# ---------------------------------------------------------------------------
# Directive extraction
# ---------------------------------------------------------------------------

class TestExtractDirectives:
    """extract_directives finds actionable items in research docs."""

    def _make_doc(self, tmp_path, content, status="reference"):
        from organvm_engine.atoms.research import parse_research_doc

        doc_path = tmp_path / "test-doc.md"
        doc_path.write_text(f"---\nstatus: {status}\n---\n{content}")
        return parse_research_doc(doc_path)

    def test_extract_checkboxes(self, tmp_path):
        from organvm_engine.atoms.research import extract_directives

        content = (
            "# Research\n\n"
            "## Implementation Proposal\n\n"
            "- [ ] Implement the Score-Rehearse-Perform ritual loop for CI validation\n"
            "- [x] Design the tier-based testing matrix for flagship repos\n"
            "- [ ] Add DORA metrics dashboard extension to system-dashboard\n"
        )
        doc = self._make_doc(tmp_path, content)
        directives = extract_directives(doc)

        assert len(directives) == 3
        # Unchecked items have higher confidence
        pending = [d for d in directives if d.confidence == 0.8]
        completed = [d for d in directives if d.confidence == 0.3]
        assert len(pending) == 2
        assert len(completed) == 1

    def test_extract_bold_directives(self, tmp_path):
        from organvm_engine.atoms.research import extract_directives

        content = (
            "# Analysis\n\n"
            "The key insight is that **Implement faceted classification with "
            "confidence routing** for the ingestion pipeline.\n\n"
            "Also, **Build a two-lane diagnostic scorecard** "
            "for cross-repo health.\n"
        )
        doc = self._make_doc(tmp_path, content)
        directives = extract_directives(doc)

        assert len(directives) == 2
        titles = [d.title for d in directives]
        assert any("faceted classification" in t for t in titles)
        assert any("diagnostic scorecard" in t for t in titles)

    def test_extract_numbered_in_actionable_section(self, tmp_path):
        from organvm_engine.atoms.research import extract_directives

        content = (
            "# Overview\n\n"
            "General discussion.\n\n"
            "## Concrete Implementation Proposal\n\n"
            "1. Create a new module for the scoring engine in `src/scoring/engine.py`\n"
            "2. Add the rehearsal loop with configurable retry thresholds\n"
            "3. Wire the performance stage into the CI pipeline\n\n"
            "## Background\n\n"
            "More general text.\n"
        )
        doc = self._make_doc(tmp_path, content)
        directives = extract_directives(doc)

        assert len(directives) == 3
        assert all(d.section == "Concrete Implementation Proposal" for d in directives)

    def test_skip_code_blocks(self, tmp_path):
        from organvm_engine.atoms.research import extract_directives

        content = (
            "# Code Example\n\n"
            "```python\n"
            "- [ ] This checkbox is inside a code block and should be skipped\n"
            "**Implement this thing** also inside code\n"
            "```\n\n"
            "- [ ] This checkbox is real and should be extracted as a directive\n"
        )
        doc = self._make_doc(tmp_path, content)
        directives = extract_directives(doc)

        assert len(directives) == 1
        assert "real" in directives[0].title

    def test_arrow_directives(self, tmp_path):
        from organvm_engine.atoms.research import extract_directives

        content = (
            "# Recommendations\n\n"
            "-> Integrate the constrained variation principle as a design pattern for generative systems\n"
        )
        doc = self._make_doc(tmp_path, content)
        directives = extract_directives(doc)

        assert len(directives) == 1
        assert "constrained variation" in directives[0].title

    def test_no_directives_from_plain_prose(self, tmp_path):
        from organvm_engine.atoms.research import extract_directives

        content = (
            "# Literature Review\n\n"
            "This document reviews the existing literature on recursive systems.\n"
            "The findings suggest several avenues for future exploration.\n"
            "No concrete proposals are made at this time.\n"
        )
        doc = self._make_doc(tmp_path, content)
        directives = extract_directives(doc)

        assert len(directives) == 0

    def test_short_items_skipped(self, tmp_path):
        from organvm_engine.atoms.research import extract_directives

        content = (
            "# Notes\n\n"
            "- [ ] TODO\n"
            "- [ ] Fix it\n"
            "- [ ] Implement the full scoring engine with tier-based routing\n"
        )
        doc = self._make_doc(tmp_path, content)
        directives = extract_directives(doc)

        # First two are < 15 chars, should be skipped
        assert len(directives) == 1


# ---------------------------------------------------------------------------
# Task emission
# ---------------------------------------------------------------------------

class TestDirectiveToTask:
    """directive_to_task produces task dicts compatible with AtomicTask.to_dict()."""

    def test_task_structure(self, tmp_path):
        from organvm_engine.atoms.research import (
            ResearchDirective,
            ResearchDoc,
            directive_to_task,
        )

        doc = ResearchDoc(
            path=tmp_path / "test-research.md",
            title="Test Research",
            date="2026-03-08",
            status="reference",
            tags=["python"],
        )
        directive = ResearchDirective(
            title="Implement scoring engine",
            body="Implement scoring engine with `src/scoring/engine.py`",
            line_start=10,
            line_end=10,
            section="Proposals",
            directive_type="proposal",
            confidence=0.7,
        )

        task = directive_to_task(directive, doc, tmp_path)

        # Core fields
        assert task["id"]  # non-empty hash
        assert task["title"] == "Implement scoring engine"
        assert task["source_type"] == "research-directive"
        assert task["agent"] == "research"
        assert task["status"] == "pending"
        assert task["actionable"] is True

        # Source metadata
        assert task["source"]["plan_title"] == "Test Research"
        assert task["source"]["plan_date"] == "2026-03-08"
        assert task["source"]["line_start"] == 10

        # Research-specific metadata
        assert task["research_metadata"]["directive_type"] == "proposal"
        assert task["research_metadata"]["confidence"] == 0.7

        # Tags extracted from body + doc-level
        assert "python" in task["tags"]

        # File refs extracted from body
        assert any("src/scoring/engine.py" in ft["path"] for ft in task["files_touched"])

        # Domain fingerprint computed
        assert task["domain_fingerprint"]
        assert len(task["domain_fingerprint"]) == 16

    def test_task_id_is_stable(self, tmp_path):
        from organvm_engine.atoms.research import (
            ResearchDirective,
            ResearchDoc,
            directive_to_task,
        )

        doc = ResearchDoc(path=tmp_path / "doc.md", title="Doc")
        directive = ResearchDirective(title="Do something", section="S1")

        task1 = directive_to_task(directive, doc, tmp_path)
        task2 = directive_to_task(directive, doc, tmp_path)
        assert task1["id"] == task2["id"]


# ---------------------------------------------------------------------------
# Status update
# ---------------------------------------------------------------------------

class TestMarkDocActivated:
    """mark_doc_activated updates frontmatter status."""

    def test_updates_existing_status(self, tmp_path):
        from organvm_engine.atoms.research import mark_doc_activated

        doc_path = tmp_path / "doc.md"
        doc_path.write_text("---\nstatus: reference\ntitle: Test\n---\n# Content\n")

        result = mark_doc_activated(doc_path)
        assert result is True

        text = doc_path.read_text()
        assert "reference-activated" in text
        assert "title: Test" in text

    def test_adds_status_to_existing_frontmatter(self, tmp_path):
        from organvm_engine.atoms.research import mark_doc_activated

        doc_path = tmp_path / "doc.md"
        doc_path.write_text("---\ntitle: No Status\n---\n# Content\n")

        result = mark_doc_activated(doc_path)
        assert result is True

        text = doc_path.read_text()
        assert "reference-activated" in text

    def test_adds_frontmatter_when_missing(self, tmp_path):
        from organvm_engine.atoms.research import mark_doc_activated

        doc_path = tmp_path / "doc.md"
        doc_path.write_text("# No Frontmatter\n\nContent.\n")

        result = mark_doc_activated(doc_path)
        assert result is True

        text = doc_path.read_text()
        assert text.startswith("---\nstatus: reference-activated\n---\n")

    def test_noop_when_already_activated(self, tmp_path):
        from organvm_engine.atoms.research import mark_doc_activated

        doc_path = tmp_path / "doc.md"
        doc_path.write_text("---\nstatus: reference-activated\n---\n# Done\n")

        result = mark_doc_activated(doc_path)
        assert result is False


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

class TestDiscoverResearchDocs:
    """discover_research_docs finds markdown files in a directory tree."""

    def test_finds_markdown_files(self, tmp_path):
        from organvm_engine.atoms.research import discover_research_docs

        (tmp_path / "doc1.md").write_text("# Doc 1")
        (tmp_path / "doc2.md").write_text("# Doc 2")
        (tmp_path / "not-markdown.txt").write_text("Not a doc")

        docs = discover_research_docs(tmp_path)
        assert len(docs) == 2

    def test_recursive_search(self, tmp_path):
        from organvm_engine.atoms.research import discover_research_docs

        sub = tmp_path / "subdir"
        sub.mkdir()
        (tmp_path / "top.md").write_text("# Top")
        (sub / "nested.md").write_text("# Nested")

        docs = discover_research_docs(tmp_path, recursive=True)
        assert len(docs) == 2

    def test_nonrecursive_search(self, tmp_path):
        from organvm_engine.atoms.research import discover_research_docs

        sub = tmp_path / "subdir"
        sub.mkdir()
        (tmp_path / "top.md").write_text("# Top")
        (sub / "nested.md").write_text("# Nested")

        docs = discover_research_docs(tmp_path, recursive=False)
        assert len(docs) == 1

    def test_missing_directory(self):
        from organvm_engine.atoms.research import discover_research_docs

        docs = discover_research_docs(Path("/nonexistent/dir"))
        assert docs == []


# ---------------------------------------------------------------------------
# High-level API: activate_research
# ---------------------------------------------------------------------------

class TestActivateResearch:
    """activate_research scans a directory and produces tasks."""

    def test_end_to_end(self, tmp_path):
        from organvm_engine.atoms.research import activate_research

        (tmp_path / "actionable.md").write_text(
            "---\n"
            "title: Actionable Research\n"
            "status: reference-actionable\n"
            "date: 2026-03-08\n"
            "---\n"
            "# Actionable Research\n\n"
            "## Implementation Proposal\n\n"
            "- [ ] Create a scoring engine module at `src/scoring/engine.py`\n"
            "- [ ] Add tier-based test matrix for flagship repositories\n\n"
            "## Background\n\n"
            "General discussion text.\n",
        )
        (tmp_path / "activated.md").write_text(
            "---\nstatus: reference-activated\n---\n# Already Done\n",
        )

        result = activate_research(tmp_path, min_confidence=0.4)

        assert result.docs_scanned == 1
        assert result.docs_skipped == 1  # activated doc skipped
        assert result.docs_with_directives == 1
        assert result.total_directives == 2
        assert len(result.tasks) == 2

        # Verify task structure
        for task in result.tasks:
            assert task["source_type"] == "research-directive"
            assert task["id"]
            assert task["research_metadata"]["confidence"] >= 0.4

    def test_confidence_filtering(self, tmp_path):
        from organvm_engine.atoms.research import activate_research

        (tmp_path / "doc.md").write_text(
            "---\nstatus: reference\n---\n"
            "# Research\n\n"
            "- [x] Already done item with low confidence value\n"
            "- [ ] Pending item with normal confidence value for testing\n",
        )

        # High confidence threshold should filter out completed checkboxes (0.3)
        result = activate_research(tmp_path, min_confidence=0.5)
        assert result.total_directives == 1

        # Low threshold includes completed checkboxes
        result = activate_research(tmp_path, min_confidence=0.2)
        assert result.total_directives == 2

    def test_mark_activated_flag(self, tmp_path):
        from organvm_engine.atoms.research import activate_research

        doc_path = tmp_path / "doc.md"
        doc_path.write_text(
            "---\nstatus: reference\n---\n"
            "# Research\n\n"
            "- [ ] Implement a real feature with some descriptive text\n",
        )

        result = activate_research(tmp_path, mark_activated=True)
        assert result.docs_scanned == 1

        # Verify the doc was updated
        text = doc_path.read_text()
        assert "reference-activated" in text

        # A second scan should skip it
        result2 = activate_research(tmp_path)
        assert result2.docs_scanned == 0
        assert result2.docs_skipped == 1

    def test_empty_directory(self, tmp_path):
        from organvm_engine.atoms.research import activate_research

        result = activate_research(tmp_path)
        assert result.docs_scanned == 0
        assert result.total_directives == 0
        assert result.tasks == []

    def test_errors_are_captured(self, tmp_path):
        from organvm_engine.atoms.research import activate_research

        # Create an unreadable file by making it a directory with .md name
        # (will cause read error)
        bad = tmp_path / "bad.md"
        bad.mkdir()

        result = activate_research(tmp_path)
        assert len(result.errors) == 1


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------

class TestPipelineResearchIntegration:
    """Research stage integrates into the atoms pipeline."""

    @patch("organvm_engine.plans.atomizer.atomize_all")
    @patch("organvm_engine.atoms.research.activate_research")
    def test_pipeline_includes_research(self, mock_research, mock_atomize, tmp_path):
        from organvm_engine.atoms.pipeline import run_pipeline
        from organvm_engine.atoms.research import ResearchActivationResult
        from organvm_engine.plans.atomizer import AtomizeResult

        mock_atomize.return_value = AtomizeResult(
            tasks=[{"id": "t1", "status": "pending"}],
            plans_parsed=1,
            errors=[],
            archetype_counts={"checklist": 1},
            status_counts={"pending": 1},
        )
        mock_research.return_value = ResearchActivationResult(
            docs_scanned=2,
            docs_with_directives=1,
            total_directives=3,
            tasks=[
                {"id": "r1", "status": "pending", "source_type": "research-directive"},
                {"id": "r2", "status": "pending", "source_type": "research-directive"},
                {"id": "r3", "status": "pending", "source_type": "research-directive"},
            ],
        )

        result = run_pipeline(
            output_dir=tmp_path,
            skip_narrate=True,
            skip_link=True,
            skip_research=False,
            research_dir=tmp_path,
            dry_run=True,
        )

        # Plan tasks (1) + research directives (3) = 4 total
        assert result.atomize_count == 4
        assert result.research_docs_scanned == 2
        assert result.research_directives == 3

    @patch("organvm_engine.plans.atomizer.atomize_all")
    def test_pipeline_skip_research(self, mock_atomize, tmp_path):
        from organvm_engine.atoms.pipeline import run_pipeline
        from organvm_engine.plans.atomizer import AtomizeResult

        mock_atomize.return_value = AtomizeResult(
            tasks=[{"id": "t1", "status": "pending"}],
            plans_parsed=1,
            errors=[],
            archetype_counts={},
            status_counts={},
        )

        result = run_pipeline(
            output_dir=tmp_path,
            skip_narrate=True,
            skip_link=True,
            skip_research=True,
            dry_run=True,
        )

        assert result.research_docs_scanned == 0
        assert result.research_directives == 0

    @patch("organvm_engine.plans.atomizer.atomize_all")
    @patch("organvm_engine.atoms.research.activate_research")
    def test_pipeline_manifest_includes_research_counts(
        self, mock_research, mock_atomize, tmp_path,
    ):
        from organvm_engine.atoms.pipeline import run_pipeline
        from organvm_engine.atoms.research import ResearchActivationResult
        from organvm_engine.plans.atomizer import AtomizeResult

        mock_atomize.return_value = AtomizeResult(
            tasks=[], plans_parsed=0, errors=[],
            archetype_counts={}, status_counts={},
        )
        mock_research.return_value = ResearchActivationResult(
            docs_scanned=5,
            docs_with_directives=2,
            total_directives=7,
            tasks=[{"id": f"r{i}", "status": "pending"} for i in range(7)],
        )

        result = run_pipeline(
            output_dir=tmp_path,
            skip_narrate=True,
            skip_link=True,
            research_dir=tmp_path,
            dry_run=True,
        )

        counts = result.manifest["counts"]
        assert counts["research_docs_scanned"] == 5
        assert counts["research_directives"] == 7


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

class TestCLIResearch:
    """CLI handler for atoms research subcommand."""

    @patch("organvm_engine.atoms.research.activate_research")
    def test_cli_research_dry_run(self, mock_activate, tmp_path, capsys):
        from organvm_engine.atoms.research import ResearchActivationResult
        from organvm_engine.cli.atoms import cmd_atoms_research

        mock_activate.return_value = ResearchActivationResult(
            docs_scanned=3,
            docs_with_directives=2,
            total_directives=5,
            tasks=[
                {
                    "id": "abc123",
                    "title": "Implement scoring engine",
                    "research_metadata": {
                        "directive_type": "proposal",
                        "confidence": 0.7,
                        "source_doc": "test.md",
                    },
                },
            ],
        )

        args = MagicMock()
        args.write = False
        args.research_dir = str(tmp_path)
        args.min_confidence = 0.4
        args.json = False

        # Create the directory so the check passes
        tmp_path.mkdir(exist_ok=True)

        ret = cmd_atoms_research(args)

        assert ret == 0
        captured = capsys.readouterr()
        assert "Research Activation" in captured.out
        assert "Docs scanned:        3" in captured.out
        assert "Directives extracted: 5" in captured.out

    @patch("organvm_engine.atoms.research.activate_research")
    def test_cli_research_json(self, mock_activate, tmp_path, capsys):
        from organvm_engine.atoms.research import ResearchActivationResult
        from organvm_engine.cli.atoms import cmd_atoms_research

        mock_activate.return_value = ResearchActivationResult(
            docs_scanned=1,
            docs_with_directives=1,
            total_directives=2,
            tasks=[{"id": "r1"}, {"id": "r2"}],
        )

        args = MagicMock()
        args.write = False
        args.research_dir = str(tmp_path)
        args.min_confidence = 0.4
        args.json = True

        tmp_path.mkdir(exist_ok=True)

        ret = cmd_atoms_research(args)

        assert ret == 0
        output = json.loads(capsys.readouterr().out)
        assert output["docs_scanned"] == 1
        assert output["total_directives"] == 2
        assert len(output["tasks"]) == 2


class TestCLIPipeline:
    """CLI pipeline includes research stage in output."""

    @patch("organvm_engine.plans.atomizer.atomize_all")
    def test_cli_pipeline_shows_research_step(self, mock_atomize, tmp_path, capsys):
        from organvm_engine.cli.atoms import cmd_atoms_pipeline
        from organvm_engine.plans.atomizer import AtomizeResult

        mock_atomize.return_value = AtomizeResult(
            tasks=[{"id": "t1"}], plans_parsed=1, errors=[],
            archetype_counts={}, status_counts={},
        )

        args = MagicMock()
        args.write = False
        args.output_dir = str(tmp_path)
        args.agent = None
        args.organ = None
        args.skip_narrate = True
        args.skip_link = True
        args.skip_reconcile = True
        args.skip_research = True
        args.research_dir = None
        args.threshold = 0.30

        ret = cmd_atoms_pipeline(args)

        assert ret == 0
        captured = capsys.readouterr()
        assert "[2/7] Research:" in captured.out
