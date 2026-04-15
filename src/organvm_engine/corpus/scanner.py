"""Corpus scanner — reads zettelkasten sidecar, Layer 2 frontmatter, and seed.yaml implements fields.

Phase 1 of the corpus knowledge graph pipeline (IRF-SYS-104).
Zero NLP. Pure structural scan.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from organvm_engine.corpus.graph import CorpusGraph, GraphEdge, GraphNode


def _read_yaml_frontmatter(path: Path) -> dict[str, Any]:
    """Extract YAML frontmatter from a markdown file."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end < 0:
        return {}
    try:
        return yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return {}


def _scan_zettelkasten(sidecar_path: Path, graph: CorpusGraph) -> None:
    """Read .zettel-index.yaml and create transcript + concept nodes."""
    data = yaml.safe_load(sidecar_path.read_text(encoding="utf-8"))

    # Transcript nodes
    for trx_id, trx_data in data.get("transcripts", {}).items():
        graph.add_node(GraphNode(
            uid=trx_id,
            node_type="transcript",
            title=trx_data.get("title", trx_id),
            metadata={
                "file": trx_data.get("file", ""),
                "depth": trx_data.get("depth", 0),
                "qa_own": trx_data.get("qa_own", 0),
                "line_count": trx_data.get("line_count", 0),
                "layer2_extractions": trx_data.get("layer2_extractions", 0),
            },
        ))
        # Parent → child edges
        for child_id in trx_data.get("children", []):
            graph.add_edge(GraphEdge(
                source=trx_id,
                target=child_id,
                edge_type="BRANCHES_TO",
            ))

    # Compiled spec nodes
    for spec_id, spec_data in data.get("compiled_specs", {}).items():
        graph.add_node(GraphNode(
            uid=spec_id,
            node_type="spec",
            title=spec_data.get("title", spec_id),
            metadata={
                "file": spec_data.get("file", ""),
                "line_count": spec_data.get("line_count", 0),
                "compilation_quality": spec_data.get("compilation_quality", ""),
            },
        ))
        # COMPILES edges from source transcripts
        for src_trx in spec_data.get("source_transcripts", []):
            graph.add_edge(GraphEdge(
                source=src_trx,
                target=spec_id,
                edge_type="COMPILES",
            ))

    # Cross-trunk concept nodes
    for concept_id, concept_data in data.get("cross_trunk_concepts", {}).items():
        graph.add_node(GraphNode(
            uid=f"concept:{concept_id}",
            node_type="concept",
            title=concept_id,
            metadata={
                "description": concept_data.get("description", ""),
                "trunks": concept_data.get("trunks", []),
                "primary_source": concept_data.get("primary_source", ""),
            },
        ))
        # DEFINES edges from primary source transcript
        primary = concept_data.get("primary_source")
        if primary:
            graph.add_edge(GraphEdge(
                source=primary,
                target=f"concept:{concept_id}",
                edge_type="DEFINES",
            ))
        # REFERENCES edges from all present_in transcripts
        for trx_id in concept_data.get("present_in", []):
            if trx_id != primary:
                graph.add_edge(GraphEdge(
                    source=trx_id,
                    target=f"concept:{concept_id}",
                    edge_type="REFERENCES",
                ))


def _scan_layer2_frontmatter(corpus_dir: Path, graph: CorpusGraph) -> None:
    """Scan Layer 2 extracted module files for EXTRACTED_FROM edges."""
    # Walk all .md files in the corpus EXCEPT archive_original/ and .claude/
    for md_file in corpus_dir.rglob("*.md"):
        rel = md_file.relative_to(corpus_dir)
        if str(rel).startswith("archive_original/") or str(rel).startswith(".claude/"):
            continue
        fm = _read_yaml_frontmatter(md_file)
        if not fm.get("source_file") and not fm.get("source_files"):
            continue

        doc_uid = f"doc:{rel}"
        graph.add_node(GraphNode(
            uid=doc_uid,
            node_type="document",
            title=fm.get("title", md_file.stem),
            metadata={
                "file": str(rel),
                "status": fm.get("status", ""),
                "tags": fm.get("tags", []),
                "date_extracted": fm.get("date_extracted", ""),
                "source_qa_index": fm.get("source_qa_index"),
            },
        ))

        # EXTRACTED_FROM edge to source transcript via provenance
        source_file = fm.get("source_file") or ""
        if source_file:
            # Resolve source_file to TRX ID via provenance map
            # For now, create edge to the filename (linker resolves to TRX ID later)
            graph.add_edge(GraphEdge(
                source=doc_uid,
                target=f"transcript_file:{source_file}",
                edge_type="EXTRACTED_FROM",
                metadata={"source_qa_index": fm.get("source_qa_index")},
            ))


def _scan_seed_implements(workspace_root: Path, graph: CorpusGraph) -> None:
    """Scan seed.yaml implements[] fields for IMPLEMENTS edges."""
    for seed_path in workspace_root.rglob("seed.yaml"):
        # Skip deep paths (node_modules, .venv, etc.)
        rel = seed_path.relative_to(workspace_root)
        if any(p.startswith(".") or p in ("node_modules", ".venv", "__pycache__")
               for p in rel.parts):
            continue
        # Only go 3 levels deep
        if len(rel.parts) > 3:
            continue

        try:
            data = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError):
            continue

        if not data or not isinstance(data, dict):
            continue

        implements = data.get("implements", [])
        if not implements:
            continue

        repo_name = data.get("repo", seed_path.parent.name)
        org = data.get("org", "")
        repo_uid = f"repo:{org}/{repo_name}"

        graph.add_node(GraphNode(
            uid=repo_uid,
            node_type="repo",
            title=repo_name,
            metadata={
                "org": org,
                "organ": str(data.get("organ", "")),
                "promotion_status": data.get("metadata", {}).get("promotion_status", ""),
            },
        ))

        for impl in implements:
            concept = impl.get("concept", "")
            if not concept:
                continue
            concept_uid = f"concept:{concept}"
            graph.add_edge(GraphEdge(
                source=repo_uid,
                target=concept_uid,
                edge_type="IMPLEMENTS",
                metadata={"aspect": impl.get("aspect", "")},
            ))


def _resolve_provenance(sidecar_path: Path, graph: CorpusGraph) -> None:
    """Replace transcript_file: edges with actual TRX ID references."""
    data = yaml.safe_load(sidecar_path.read_text(encoding="utf-8"))
    provenance = data.get("layer2_provenance", {})

    resolved_edges: list[GraphEdge] = []
    for edge in graph.edges:
        if edge.target.startswith("transcript_file:"):
            filename = edge.target[len("transcript_file:"):]
            trx_id = provenance.get(filename)
            if trx_id:
                resolved_edges.append(GraphEdge(
                    source=edge.source,
                    target=trx_id,
                    edge_type=edge.edge_type,
                    metadata=edge.metadata,
                ))
            else:
                resolved_edges.append(edge)  # Keep unresolved for gap detection
        else:
            resolved_edges.append(edge)

    graph.edges = resolved_edges


def scan_corpus(
    corpus_dir: Path | str,
    workspace_root: Path | str | None = None,
) -> CorpusGraph:
    """Build the corpus knowledge graph from filesystem.

    Args:
        corpus_dir: Path to post-flood/ directory
        workspace_root: Path to ~/Workspace/ (for seed.yaml scanning)

    Returns:
        Populated CorpusGraph
    """
    corpus_dir = Path(corpus_dir)
    ws = Path(workspace_root) if workspace_root else corpus_dir.parent.parent

    graph = CorpusGraph()
    sidecar = corpus_dir / "archive_original" / ".zettel-index.yaml"

    if sidecar.is_file():
        _scan_zettelkasten(sidecar, graph)

    _scan_layer2_frontmatter(corpus_dir, graph)

    _scan_seed_implements(ws, graph)

    if sidecar.is_file():
        _resolve_provenance(sidecar, graph)

    return graph
