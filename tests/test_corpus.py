"""Tests for corpus knowledge graph (IRF-SYS-104).

Validates the scanner builds correct nodes/edges from
zettelkasten sidecar, Layer 2 frontmatter, and seed.yaml implements fields.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from organvm_engine.corpus.graph import CorpusGraph, GraphEdge, GraphNode
from organvm_engine.corpus.scanner import scan_corpus


# ── Fixtures ──────────────────────────────────────────────


def _make_sidecar(tmp_path: Path) -> Path:
    """Create a minimal .zettel-index.yaml."""
    archive = tmp_path / "archive_original"
    archive.mkdir()
    sidecar = archive / ".zettel-index.yaml"
    sidecar.write_text(yaml.dump({
        "schema_version": "1.1",
        "transcripts": {
            "TRX-TEST": {
                "file": "Test-Transcript.md",
                "title": "Test Transcript",
                "depth": 0,
                "parent": None,
                "children": ["TRX-TEST.1"],
                "qa_total": 3,
                "qa_own": 3,
                "line_count": 100,
                "layer2_extractions": 1,
            },
            "TRX-TEST.1": {
                "file": "Branch-Test-Transcript--topic.md",
                "title": "Test Branch",
                "depth": 1,
                "parent": "TRX-TEST",
                "children": [],
                "qa_total": 2,
                "qa_own": 1,
                "line_count": 50,
                "layer2_extractions": 0,
            },
        },
        "compiled_specs": {
            "TRX-C.01": {
                "file": "extracted_modules_compiled/Test-Spec.md",
                "title": "Test Specification",
                "compilation_quality": "clean",
                "source_transcripts": ["TRX-TEST"],
                "line_count": 200,
            },
        },
        "layer2_provenance": {
            "Test-Transcript.md": "TRX-TEST",
            "Branch-Test-Transcript--topic.md": "TRX-TEST.1",
        },
        "cross_trunk_concepts": {
            "test_concept": {
                "description": "A test concept for validation",
                "present_in": ["TRX-TEST", "TRX-TEST.1"],
                "trunks": ["TEST"],
                "primary_source": "TRX-TEST",
            },
            "orphan_concept": {
                "description": "A concept with no implementation",
                "present_in": ["TRX-TEST"],
                "trunks": ["TEST"],
                "primary_source": "TRX-TEST",
            },
        },
    }), encoding="utf-8")

    # Create a dummy transcript file
    (archive / "Test-Transcript.md").write_text(
        "---\ntrx_id: TRX-TEST\ntitle: Test\nstatus: transcript\n---\n## Q:\nTest?\n## A:\nYes.",
        encoding="utf-8",
    )
    return tmp_path


def _make_layer2(corpus_dir: Path) -> None:
    """Add a Layer 2 extracted module."""
    theme_dir = corpus_dir / "test-theme"
    theme_dir.mkdir()
    doc = theme_dir / "test-extraction.md"
    doc.write_text(
        '---\ntitle: "Test Extraction"\ndate_extracted: "2026-04-14"\n'
        'source_file: "Test-Transcript.md"\nsource_qa_index: 1\n'
        'tags: [test]\nstatus: extracted\n---\n\nExtracted content.',
        encoding="utf-8",
    )


def _make_seed_with_implements(ws_root: Path) -> None:
    """Create a repo with seed.yaml that has implements field."""
    repo_dir = ws_root / "organvm-i-theoria" / "test-repo"
    repo_dir.mkdir(parents=True)
    seed = repo_dir / "seed.yaml"
    seed.write_text(yaml.dump({
        "schema_version": "1.0",
        "organ": "I",
        "repo": "test-repo",
        "org": "organvm-i-theoria",
        "implements": [
            {
                "concept": "test_concept",
                "zettel_source": "post-flood/.zettel-index.yaml#test_concept",
                "aspect": "Test implementation aspect",
            },
        ],
        "produces": [],
        "consumes": [],
    }), encoding="utf-8")


# ── Graph Tests ───────────────────────────────────────────


class TestCorpusGraph:
    def test_add_and_retrieve_node(self) -> None:
        g = CorpusGraph()
        g.add_node(GraphNode(uid="n1", node_type="concept", title="Test"))
        assert g.get_node("n1") is not None
        assert g.get_node("n1").title == "Test"

    def test_nodes_by_type(self) -> None:
        g = CorpusGraph()
        g.add_node(GraphNode(uid="c1", node_type="concept", title="C1"))
        g.add_node(GraphNode(uid="t1", node_type="transcript", title="T1"))
        g.add_node(GraphNode(uid="c2", node_type="concept", title="C2"))
        assert len(g.nodes_by_type("concept")) == 2
        assert len(g.nodes_by_type("transcript")) == 1

    def test_concepts_without_implementation(self) -> None:
        g = CorpusGraph()
        g.add_node(GraphNode(uid="concept:a", node_type="concept", title="A"))
        g.add_node(GraphNode(uid="concept:b", node_type="concept", title="B"))
        g.add_edge(GraphEdge(source="repo:x", target="concept:a", edge_type="IMPLEMENTS"))
        gaps = g.concepts_without_implementation()
        assert len(gaps) == 1
        assert gaps[0].uid == "concept:b"

    def test_stats(self) -> None:
        g = CorpusGraph()
        g.add_node(GraphNode(uid="n1", node_type="concept", title="N1"))
        g.add_edge(GraphEdge(source="a", target="b", edge_type="DEFINES"))
        s = g.stats()
        assert s["total_nodes"] == 1
        assert s["total_edges"] == 1

    def test_save_and_load(self, tmp_path: Path) -> None:
        g = CorpusGraph()
        g.add_node(GraphNode(uid="n1", node_type="concept", title="Test"))
        g.add_edge(GraphEdge(source="n1", target="n2", edge_type="DEFINES"))
        path = tmp_path / "graph.json"
        g.save(path)

        loaded = CorpusGraph.load(path)
        assert len(loaded.nodes) == 1
        assert len(loaded.edges) == 1
        assert loaded.get_node("n1").title == "Test"


# ── Scanner Tests ─────────────────────────────────────────


class TestZettelkastenScan:
    def test_creates_transcript_nodes(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        transcripts = graph.nodes_by_type("transcript")
        assert len(transcripts) == 2

    def test_creates_concept_nodes(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        concepts = graph.nodes_by_type("concept")
        assert len(concepts) == 2

    def test_creates_spec_nodes(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        specs = graph.nodes_by_type("spec")
        assert len(specs) == 1
        assert specs[0].uid == "TRX-C.01"

    def test_defines_edge_from_primary_source(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        defines = [e for e in graph.edges if e.edge_type == "DEFINES"]
        assert len(defines) == 2  # One per concept
        targets = {e.target for e in defines}
        assert "concept:test_concept" in targets
        assert "concept:orphan_concept" in targets

    def test_branches_to_edge(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        branches = [e for e in graph.edges if e.edge_type == "BRANCHES_TO"]
        assert len(branches) == 1
        assert branches[0].source == "TRX-TEST"
        assert branches[0].target == "TRX-TEST.1"

    def test_compiles_edge(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        compiles = [e for e in graph.edges if e.edge_type == "COMPILES"]
        assert len(compiles) == 1
        assert compiles[0].target == "TRX-C.01"


class TestLayer2Scan:
    def test_creates_document_nodes(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        _make_layer2(corpus_dir)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        docs = graph.nodes_by_type("document")
        assert len(docs) == 1
        assert "Test Extraction" in docs[0].title

    def test_extracted_from_edge_resolved(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        _make_layer2(corpus_dir)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        extracted = [e for e in graph.edges if e.edge_type == "EXTRACTED_FROM"]
        assert len(extracted) == 1
        assert extracted[0].target == "TRX-TEST"  # Resolved via provenance


class TestSeedImplementsScan:
    def test_creates_repo_node(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        _make_seed_with_implements(tmp_path)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        repos = graph.nodes_by_type("repo")
        assert len(repos) == 1
        assert repos[0].title == "test-repo"

    def test_implements_edge(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        _make_seed_with_implements(tmp_path)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        impl = [e for e in graph.edges if e.edge_type == "IMPLEMENTS"]
        assert len(impl) == 1
        assert impl[0].target == "concept:test_concept"
        assert impl[0].metadata.get("aspect") == "Test implementation aspect"

    def test_orphan_concept_detected(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        _make_seed_with_implements(tmp_path)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        gaps = graph.concepts_without_implementation()
        assert len(gaps) == 1
        assert gaps[0].uid == "concept:orphan_concept"


def _make_spec_dirs(corpus_dir: Path) -> None:
    """Create mock SPEC directories for concept discovery tests."""
    specs = corpus_dir / "specs"
    specs.mkdir()

    # Numbered SPEC with grounding.md
    s000 = specs / "SPEC-000"
    s000.mkdir()
    (s000 / "grounding.md").write_text(
        "---\ntitle: System Manifesto Grounding\n---\n# System Manifesto\n",
        encoding="utf-8",
    )

    # Named SPEC (SPEC-NNN-name pattern)
    s019 = specs / "SPEC-019-system-manifestation"
    s019.mkdir()
    (s019 / "specification.md").write_text(
        "# System Manifestation\n\nThe system renders itself.\n",
        encoding="utf-8",
    )

    # Pure named directory
    era = specs / "era-model"
    era.mkdir()
    (era / "grounding.md").write_text(
        "---\ndescription: Temporal era governance model\n---\n",
        encoding="utf-8",
    )

    # Non-concept directory (no indicator files)
    lib = specs / "library"
    lib.mkdir()
    (lib / "README.md").write_text("# Library\nReference materials.\n")

    # Directory matching existing cross_trunk concept (should be skipped)
    tc = specs / "test-concept"
    tc.mkdir()
    (tc / "grounding.md").write_text("# Test Concept\n")


class TestSpecDirectoryScan:
    def test_creates_concept_from_numbered_spec(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        _make_spec_dirs(corpus_dir)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        node = graph.get_node("concept:system_manifesto")
        assert node is not None
        assert node.node_type == "concept"
        assert node.metadata["discovery"] == "spec_directory"

    def test_creates_concept_from_named_spec(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        _make_spec_dirs(corpus_dir)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        # SPEC-019-system-manifestation → system_manifestation
        node = graph.get_node("concept:system_manifestation")
        assert node is not None
        # era-model → era_model
        node2 = graph.get_node("concept:era_model")
        assert node2 is not None
        assert node2.metadata["description"] == "Temporal era governance model"

    def test_skips_existing_cross_trunk_concept(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        _make_spec_dirs(corpus_dir)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        # test_concept exists in cross_trunk_concepts from sidecar
        tc_node = graph.get_node("concept:test_concept")
        assert tc_node is not None
        # Should be the original from cross_trunk, not from spec dir
        assert tc_node.metadata.get("discovery") != "spec_directory"

    def test_skips_library_directory(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        _make_spec_dirs(corpus_dir)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        assert graph.get_node("concept:library") is None

    def test_creates_defines_edge(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        _make_spec_dirs(corpus_dir)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        defines = [
            e for e in graph.edges
            if e.edge_type == "DEFINES" and e.target == "concept:system_manifesto"
        ]
        assert len(defines) >= 1
        assert any(e.source == "spec_dir:SPEC-000" for e in defines)


class TestFullPipeline:
    def test_end_to_end(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        _make_layer2(corpus_dir)
        _make_seed_with_implements(tmp_path)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)

        # Verify core node types present
        assert len(graph.nodes_by_type("transcript")) == 2
        assert len(graph.nodes_by_type("concept")) >= 2  # At least cross_trunk concepts
        assert len(graph.nodes_by_type("spec")) == 1
        assert len(graph.nodes_by_type("document")) == 1
        assert len(graph.nodes_by_type("repo")) == 1

        # Verify all edge types present
        edge_types = {e.edge_type for e in graph.edges}
        assert "DEFINES" in edge_types
        assert "REFERENCES" in edge_types
        assert "BRANCHES_TO" in edge_types
        assert "COMPILES" in edge_types
        assert "EXTRACTED_FROM" in edge_types
        assert "IMPLEMENTS" in edge_types

        # Verify gap detection (orphan_concept has no implementation)
        gaps = graph.concepts_without_implementation()
        assert any(g.uid == "concept:orphan_concept" for g in gaps)


class TestTraceConcept:
    def _build_graph(self, tmp_path: Path) -> CorpusGraph:
        corpus_dir = _make_sidecar(tmp_path)
        _make_layer2(corpus_dir)
        _make_seed_with_implements(tmp_path)
        return scan_corpus(corpus_dir, workspace_root=tmp_path)

    def test_traces_implemented_concept(self, tmp_path: Path) -> None:
        graph = self._build_graph(tmp_path)
        trace = graph.trace_concept("test_concept")
        assert trace["concept"] == "test_concept"
        assert trace["implementation_count"] == 1
        assert len(trace["implementations"]) == 1
        assert trace["implementations"][0]["repo"] == "test-repo"

    def test_traces_unimplemented_concept(self, tmp_path: Path) -> None:
        graph = self._build_graph(tmp_path)
        trace = graph.trace_concept("orphan_concept")
        assert trace["implementation_count"] == 0
        assert trace["implementations"] == []

    def test_returns_error_for_missing_concept(self, tmp_path: Path) -> None:
        graph = self._build_graph(tmp_path)
        trace = graph.trace_concept("nonexistent")
        assert "error" in trace

    def test_includes_definitions(self, tmp_path: Path) -> None:
        graph = self._build_graph(tmp_path)
        trace = graph.trace_concept("test_concept")
        assert len(trace["definitions"]) >= 1

    def test_accepts_prefixed_uid(self, tmp_path: Path) -> None:
        graph = self._build_graph(tmp_path)
        trace = graph.trace_concept("concept:test_concept")
        assert trace["concept"] == "concept:test_concept"
        assert "error" not in trace


class TestCoverageDepth:
    def test_returns_all_concepts(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        _make_seed_with_implements(tmp_path)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        depth = graph.coverage_depth()
        concepts = graph.nodes_by_type("concept")
        assert len(depth) == len(concepts)

    def test_sorts_by_fragility(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        _make_seed_with_implements(tmp_path)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        depth = graph.coverage_depth()
        counts = [d["implementations"] for d in depth]
        assert counts == sorted(counts)

    def test_marks_fragile_concepts(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        _make_seed_with_implements(tmp_path)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        depth = graph.coverage_depth()
        orphan = next(d for d in depth if d["concept"] == "orphan_concept")
        assert orphan["fragile"] is True
        assert orphan["implementations"] == 0

    def test_implemented_concept_has_repos(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        _make_seed_with_implements(tmp_path)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        depth = graph.coverage_depth()
        implemented = next(d for d in depth if d["concept"] == "test_concept")
        assert "test-repo" in implemented["repos"]
        assert implemented["implementations"] == 1


class TestRepoConcepts:
    def test_finds_concepts_for_repo(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        _make_seed_with_implements(tmp_path)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        concepts = graph.repo_concepts("test-repo")
        assert len(concepts) == 1
        assert concepts[0]["concept"] == "test_concept"

    def test_returns_empty_for_unknown_repo(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        concepts = graph.repo_concepts("nonexistent-repo")
        assert concepts == []

    def test_includes_aspect(self, tmp_path: Path) -> None:
        corpus_dir = _make_sidecar(tmp_path)
        _make_seed_with_implements(tmp_path)
        graph = scan_corpus(corpus_dir, workspace_root=tmp_path)
        concepts = graph.repo_concepts("test-repo")
        assert concepts[0]["aspect"] != ""

        # Verify save/load round-trip
        path = tmp_path / "corpus-graph.json"
        graph.save(path)
        loaded = CorpusGraph.load(path)
        assert loaded.stats() == graph.stats()
