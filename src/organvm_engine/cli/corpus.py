"""Corpus knowledge graph CLI commands (IRF-SYS-104)."""

import argparse
import json


def cmd_corpus_scan(args: argparse.Namespace) -> int:
    """Scan the post-flood corpus and produce a knowledge graph."""
    from pathlib import Path

    from organvm_engine.corpus.scanner import scan_corpus

    corpus_dir = Path(args.corpus_dir).resolve()
    ws_root = Path(args.workspace).resolve() if args.workspace else None

    if not corpus_dir.is_dir():
        print(f"Error: {corpus_dir} is not a directory")
        return 1

    graph = scan_corpus(corpus_dir, workspace_root=ws_root)

    if args.output:
        out_path = Path(args.output)
        graph.save(out_path)
        print(f"Graph saved to {out_path}")

    stats = graph.stats()
    print(f"\n  Corpus Knowledge Graph")
    print(f"  {'═' * 50}")
    print(f"  Nodes: {stats['total_nodes']}")
    for ntype, count in sorted(stats["node_types"].items()):
        print(f"    {ntype:>12}: {count}")
    print(f"  Edges: {stats['total_edges']}")
    for etype, count in sorted(stats["edge_types"].items()):
        print(f"    {etype:>16}: {count}")

    gaps = graph.concepts_without_implementation()
    if gaps:
        print(f"\n  Unimplemented concepts: {len(gaps)}")
        for g in gaps:
            print(f"    - {g.title}")
    else:
        print(f"\n  All {len(graph.nodes_by_type('concept'))} concepts have implementations.")

    if args.json:
        print(json.dumps(graph.to_dict(), indent=2, ensure_ascii=False))

    return 0


def cmd_corpus_stats(args: argparse.Namespace) -> int:
    """Show statistics for the corpus knowledge graph."""
    from pathlib import Path

    from organvm_engine.corpus.graph import CorpusGraph
    from organvm_engine.corpus.scanner import scan_corpus

    if args.graph_file:
        graph_path = Path(args.graph_file)
        if not graph_path.is_file():
            print(f"Error: {graph_path} not found")
            return 1
        graph = CorpusGraph.load(graph_path)
    else:
        corpus_dir = Path(args.corpus_dir).resolve()
        ws_root = Path(args.workspace).resolve() if args.workspace else None
        graph = scan_corpus(corpus_dir, workspace_root=ws_root)

    stats = graph.stats()

    if args.json:
        print(json.dumps(stats, indent=2))
        return 0

    print(f"\n  Corpus Knowledge Graph Statistics")
    print(f"  {'═' * 50}")
    print(f"  Total nodes: {stats['total_nodes']}")
    print(f"  Total edges: {stats['total_edges']}")
    print()
    print(f"  Node types:")
    for ntype, count in sorted(stats["node_types"].items()):
        print(f"    {ntype:>12}: {count}")
    print(f"  Edge types:")
    for etype, count in sorted(stats["edge_types"].items()):
        print(f"    {etype:>16}: {count}")
    print()
    return 0


def cmd_corpus_gaps(args: argparse.Namespace) -> int:
    """Show concepts without implementation."""
    from pathlib import Path

    from organvm_engine.corpus.graph import CorpusGraph
    from organvm_engine.corpus.scanner import scan_corpus

    if args.graph_file:
        graph = CorpusGraph.load(Path(args.graph_file))
    else:
        corpus_dir = Path(args.corpus_dir).resolve()
        ws_root = Path(args.workspace).resolve() if args.workspace else None
        graph = scan_corpus(corpus_dir, workspace_root=ws_root)

    gaps = graph.concepts_without_implementation()
    concepts = graph.nodes_by_type("concept")

    if args.json:
        print(json.dumps({
            "total_concepts": len(concepts),
            "unimplemented": len(gaps),
            "gaps": [{"uid": g.uid, "title": g.title, **g.metadata} for g in gaps],
        }, indent=2))
        return 0

    print(f"\n  Implementation Coverage")
    print(f"  {'═' * 50}")
    print(f"  Concepts: {len(concepts)}")
    print(f"  Implemented: {len(concepts) - len(gaps)}")
    print(f"  Gaps: {len(gaps)}")

    if gaps:
        print(f"\n  Unimplemented:")
        for g in gaps:
            desc = g.metadata.get("description", "")
            print(f"    {g.title}")
            if desc:
                print(f"      {desc[:80]}")
    else:
        print(f"\n  All concepts have at least one implementation.")

    # Show implementation details for each concept
    if args.verbose:
        print(f"\n  Implementation Map:")
        for concept in sorted(concepts, key=lambda c: c.uid):
            impls = [e for e in graph.edges_to(concept.uid) if e.edge_type == "IMPLEMENTS"]
            status = f"[{len(impls)} impl]" if impls else "[GAP]"
            print(f"    {status} {concept.title}")
            for impl in impls:
                repo_node = graph.get_node(impl.source)
                aspect = impl.metadata.get("aspect", "")
                name = repo_node.title if repo_node else impl.source
                print(f"           ← {name}: {aspect}")

    return 0
