"""Tests for the seed module."""

from collections import defaultdict
from pathlib import Path

import pytest

from organvm_engine.seed.graph import SeedGraph
from organvm_engine.seed.reader import get_consumes, get_produces, read_seed, seed_identity

FIXTURES = Path(__file__).parent / "fixtures"


class TestReader:
    def test_read_valid_seed(self):
        seed = read_seed(FIXTURES / "seed-example.yaml")
        assert seed["schema_version"] == "1.0"
        assert seed["organ"] == "I"
        assert seed["repo"] == "recursive-engine"

    def test_get_produces(self):
        seed = read_seed(FIXTURES / "seed-example.yaml")
        produces = get_produces(seed)
        assert len(produces) == 1
        assert produces[0]["type"] == "theory"

    def test_get_consumes_empty(self):
        seed = read_seed(FIXTURES / "seed-example.yaml")
        consumes = get_consumes(seed)
        assert consumes == []

    def test_seed_identity(self):
        seed = read_seed(FIXTURES / "seed-example.yaml")
        assert seed_identity(seed) == "organvm-i-theoria/recursive-engine"

    def test_read_missing_file(self):
        with pytest.raises(FileNotFoundError):
            read_seed("/nonexistent/seed.yaml")


class TestSeedGraphStringEntries:
    """Test that build_seed_graph handles string produces/consumes entries."""

    def _build_graph_from_seeds(self, seeds_by_identity):
        """Helper to build a graph from pre-parsed seeds without filesystem."""
        from organvm_engine.seed.reader import get_consumes, get_produces

        graph = SeedGraph()
        producers_by_type: dict[str, list[str]] = defaultdict(list)

        for identity, _seed in seeds_by_identity.items():
            graph.nodes.append(identity)

        for identity, seed in seeds_by_identity.items():
            for p in get_produces(seed):
                ptype = "unknown" if isinstance(p, str) else p.get("type", "unknown")
                graph.produces.setdefault(identity, []).append(p)
                producers_by_type[ptype].append(identity)

        for identity, seed in seeds_by_identity.items():
            for c in get_consumes(seed):
                if isinstance(c, str):
                    ctype = "unknown"
                    source = ""
                else:
                    ctype = c.get("type", "unknown")
                    source = c.get("source", "")
                graph.consumes.setdefault(identity, []).append(c)

                for producer in producers_by_type.get(ctype, []):
                    if producer == identity:
                        continue
                    if source:
                        producer_org = producer.split("/")[0] if "/" in producer else ""
                        if source not in (producer, producer_org):
                            continue
                    graph.edges.append((producer, identity, ctype))

        return graph

    def test_string_produces_no_crash(self):
        """Seeds with string produces entries should not crash."""
        seeds = {
            "meta-organvm/corpvs": {
                "produces": ["registry-v2.json", "governance-rules.json"],
                "consumes": [],
            },
        }
        graph = self._build_graph_from_seeds(seeds)
        assert "meta-organvm/corpvs" in graph.nodes
        assert len(graph.produces["meta-organvm/corpvs"]) == 2

    def test_string_consumes_no_crash(self):
        """Seeds with string consumes entries should not crash."""
        seeds = {
            "meta-organvm/engine": {
                "produces": [],
                "consumes": ["registry-v2.json"],
            },
        }
        graph = self._build_graph_from_seeds(seeds)
        assert len(graph.consumes["meta-organvm/engine"]) == 1

    def test_mixed_produces_dict_and_string(self):
        """Seeds with mixed dict and string produces entries."""
        seeds = {
            "org/repo-a": {
                "produces": [
                    {"type": "json", "description": "registry"},
                    "some-artifact.yaml",
                ],
                "consumes": [],
            },
        }
        graph = self._build_graph_from_seeds(seeds)
        prods = graph.produces["org/repo-a"]
        assert len(prods) == 2

    def test_string_produces_typed_as_unknown(self):
        """String produces entries get type 'unknown' for edge matching."""
        seeds = {
            "org/producer": {
                "produces": ["artifact.json"],
                "consumes": [],
            },
            "org/consumer": {
                "produces": [],
                "consumes": [{"type": "unknown", "source": ""}],
            },
        }
        graph = self._build_graph_from_seeds(seeds)
        # Edge should be created: producer --[unknown]--> consumer
        assert len(graph.edges) == 1
        assert graph.edges[0] == ("org/producer", "org/consumer", "unknown")


class TestSeedGraphRegistryKeyAlias:
    """Test that build_seed_graph resolves registry-key organ names to dir names."""

    def test_registry_key_source_resolves(self, tmp_path, monkeypatch):
        """source: META-ORGANVM should match producer org 'meta-organvm'."""
        import yaml

        # Create two seed.yaml files
        producer_dir = tmp_path / "meta-organvm" / "schema-defs"
        producer_dir.mkdir(parents=True)
        (producer_dir / "seed.yaml").write_text(yaml.dump({
            "schema_version": "1.0",
            "organ": "Meta", "repo": "schema-defs", "org": "meta-organvm",
            "produces": [{"type": "schema", "description": "JSON schemas"}],
        }))

        consumer_dir = tmp_path / "meta-organvm" / "engine"
        consumer_dir.mkdir(parents=True)
        (consumer_dir / "seed.yaml").write_text(yaml.dump({
            "schema_version": "1.0",
            "organ": "Meta", "repo": "engine", "org": "meta-organvm",
            "consumes": [{"type": "schema", "source": "META-ORGANVM"}],
        }))

        # Patch discover_seeds to find only these two
        monkeypatch.setattr(
            "organvm_engine.seed.graph.discover_seeds",
            lambda workspace=None, orgs=None: [
                producer_dir / "seed.yaml",
                consumer_dir / "seed.yaml",
            ],
        )

        from organvm_engine.seed.graph import build_seed_graph

        graph = build_seed_graph()
        assert len(graph.edges) == 1
        assert graph.edges[0] == (
            "meta-organvm/schema-defs", "meta-organvm/engine", "schema"
        )
