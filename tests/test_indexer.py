"""Tests for the deep structural indexer."""

import json as json_mod
from pathlib import Path

from organvm_engine.indexer import index_repo, run_deep_index
from organvm_engine.indexer.cohesion import (
    classify_cohesion,
    dominant_language,
    extract_python_imports,
    identify_components,
)
from organvm_engine.indexer.scanner import walk_repo
from organvm_engine.indexer.seed_gen import generate_seeds
from organvm_engine.indexer.types import (
    ComponentSeed,
    DirectoryNode,
)


def _make_py_package(
    base: Path, name: str, files: list[tuple[str, str]] | None = None,
):
    """Create a Python package directory with __init__.py and optional files."""
    pkg = base / name
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("")
    for fname, content in (files or []):
        (pkg / fname).write_text(content)


# ── Scanner tests ──────────────────────────────────────────────


class TestWalkRepo:
    def test_walks_directory_tree(self, tmp_path):
        (tmp_path / "README.md").write_text("# Hello\n")
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "main.py").write_text("print('hi')\n")

        tree = walk_repo(tmp_path)
        assert tree is not None
        assert tree.path == "."
        assert tree.depth == 0
        assert tree.file_count == 1  # README.md at root
        assert len(tree.children) == 1
        assert tree.children[0].name == "src"
        assert tree.children[0].file_count == 1

    def test_skips_git_and_pycache(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("x")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "foo.pyc").write_text("x")
        (tmp_path / "real.py").write_text("x = 1\n")

        tree = walk_repo(tmp_path)
        assert tree is not None
        assert tree.file_count == 1
        assert len(tree.children) == 0

    def test_detects_init_py(self, tmp_path):
        pkg = tmp_path / "mypackage"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "core.py").write_text("x = 1\n")

        tree = walk_repo(tmp_path)
        assert tree.children[0].has_init_py is True

    def test_detects_package_json(self, tmp_path):
        sub = tmp_path / "frontend"
        sub.mkdir()
        (sub / "package.json").write_text('{"name": "test"}')

        tree = walk_repo(tmp_path)
        assert tree.children[0].has_package_json is True

    def test_detects_barrel_file(self, tmp_path):
        sub = tmp_path / "components"
        sub.mkdir()
        (sub / "index.ts").write_text("export * from './Button';")

        tree = walk_repo(tmp_path)
        assert tree.children[0].has_barrel_file is True

    def test_counts_lines(self, tmp_path):
        (tmp_path / "a.py").write_text("line1\nline2\nline3\n")
        (tmp_path / "b.py").write_text("one\ntwo\n")

        tree = walk_repo(tmp_path)
        assert tree.line_count == 5

    def test_file_types(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "b.py").write_text("y")
        (tmp_path / "c.js").write_text("z")

        tree = walk_repo(tmp_path)
        assert tree.file_types[".py"] == 2
        assert tree.file_types[".js"] == 1

    def test_nonexistent_path_returns_none(self, tmp_path):
        result = walk_repo(tmp_path / "nope")
        assert result is None

    def test_max_depth_limit(self, tmp_path):
        current = tmp_path
        for i in range(5):
            current = current / f"level{i}"
            current.mkdir()
            (current / "file.txt").write_text(f"level {i}")

        tree = walk_repo(tmp_path, max_depth=2)
        assert tree is not None
        level0 = tree.children[0]
        level1 = level0.children[0]
        assert level1.depth == 2
        assert len(level1.children) == 0

    def test_total_files_recursive(self, tmp_path):
        (tmp_path / "root.py").write_text("x")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "a.py").write_text("y")
        (sub / "b.py").write_text("z")

        tree = walk_repo(tmp_path)
        assert tree.total_files == 3

    def test_total_lines_recursive(self, tmp_path):
        (tmp_path / "root.py").write_text("a\nb\n")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "a.py").write_text("x\ny\nz\n")

        tree = walk_repo(tmp_path)
        assert tree.total_lines == 5

    def test_build_manifests_detected(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]")
        (tmp_path / "Makefile").write_text("all:")

        tree = walk_repo(tmp_path)
        assert "pyproject.toml" in tree.build_manifests
        assert "Makefile" in tree.build_manifests

    def test_skips_egg_info(self, tmp_path):
        egg = tmp_path / "mypackage.egg-info"
        egg.mkdir()
        (egg / "PKG-INFO").write_text("x")

        tree = walk_repo(tmp_path)
        assert len(tree.children) == 0


# ── Cohesion tests ─────────────────────────────────────────────


class TestCohesion:
    def test_python_leaf_package(self, tmp_path):
        """Leaf Python package (no sub-packages) = atomic component."""
        _make_py_package(tmp_path / "src" / "mypkg", "core", [
            ("models.py", "class Model: pass"),
            ("utils.py", "def helper(): pass"),
        ])

        tree = walk_repo(tmp_path)
        components = identify_components(tree, "test-repo", "ORGAN-I", tmp_path)

        assert len(components) == 1
        assert components[0].cohesion_type == "python_package"
        assert components[0].path == "src/mypkg/core"

    def test_python_parent_with_subpackages(self, tmp_path):
        """Parent with sub-packages: children are components, not parent."""
        pkg = tmp_path / "src" / "mypkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        _make_py_package(pkg, "sub_a", [("a.py", "x=1")])
        _make_py_package(pkg, "sub_b", [("b.py", "y=2")])

        tree = walk_repo(tmp_path)
        components = identify_components(tree, "test-repo", "ORGAN-I", tmp_path)

        comp_paths = [c.path for c in components]
        assert any("sub_a" in p for p in comp_paths)
        assert any("sub_b" in p for p in comp_paths)
        # Parent should NOT be a component
        assert not any(p.endswith("mypkg") for p in comp_paths)

    def test_go_package(self, tmp_path):
        go_dir = tmp_path / "cmd"
        go_dir.mkdir()
        (go_dir / "main.go").write_text("package main")
        (go_dir / "server.go").write_text("package main")

        tree = walk_repo(tmp_path)
        components = identify_components(tree, "test-repo", "ORGAN-I")

        assert len(components) == 1
        assert components[0].cohesion_type == "go_package"

    def test_doc_collection(self, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("# Guide")
        (docs / "reference.md").write_text("# Reference")
        (docs / "faq.md").write_text("# FAQ")

        tree = walk_repo(tmp_path)
        components = identify_components(tree, "test-repo", "ORGAN-V")

        assert len(components) == 1
        assert components[0].cohesion_type == "doc_collection"

    def test_resource_bundle(self, tmp_path):
        assets = tmp_path / "assets"
        assets.mkdir()
        (assets / "logo.svg").write_text("<svg/>")
        (assets / "icon.svg").write_text("<svg/>")

        tree = walk_repo(tmp_path)
        components = identify_components(tree, "test-repo", "ORGAN-II")

        assert len(components) == 1
        assert components[0].cohesion_type == "resource_bundle"

    def test_js_module_with_barrel(self, tmp_path):
        comp = tmp_path / "src" / "components"
        comp.mkdir(parents=True)
        (comp / "index.ts").write_text("export * from './Button';")
        (comp / "Button.tsx").write_text("export function Button() {}")

        tree = walk_repo(tmp_path)
        components = identify_components(tree, "test-repo", "ORGAN-III")

        assert any(c.cohesion_type == "js_module" for c in components)

    def test_dominant_language(self):
        assert dominant_language({".py": 5, ".js": 2}) == "python"
        assert dominant_language({".ts": 3, ".tsx": 2}) == "typescript"
        assert dominant_language({".go": 1}) == "go"
        assert dominant_language({}) == "unknown"

    def test_classify_none_for_parent_with_sub_packages(self):
        """Parent with sub-packages should NOT be classified."""
        parent = DirectoryNode(path="pkg", name="pkg", depth=1, has_init_py=True)
        child = DirectoryNode(path="pkg/sub", name="sub", depth=2, has_init_py=True)
        parent.children = [child]

        result = classify_cohesion(parent)
        assert result is None

    def test_classify_leaf_python_package(self):
        node = DirectoryNode(path="pkg/core", name="core", depth=2, has_init_py=True)
        result = classify_cohesion(node)
        assert result == "python_package"

    def test_empty_repo_yields_no_components(self, tmp_path):
        tree = walk_repo(tmp_path)
        components = identify_components(tree, "empty", "ORGAN-I")
        assert len(components) == 0


# ── Import analysis tests ──────────────────────────────────────


class TestImportAnalysis:
    def test_extract_imports(self, tmp_path):
        py_file = tmp_path / "test.py"
        py_file.write_text(
            "import os\n"
            "from pathlib import Path\n"
            "from organvm_engine.registry import loader\n"
            "import json\n",
        )

        imports = extract_python_imports(py_file)
        assert "os" in imports
        assert "pathlib" in imports
        assert "organvm_engine" in imports
        assert "json" in imports

    def test_extract_imports_empty_file(self, tmp_path):
        py_file = tmp_path / "empty.py"
        py_file.write_text("")

        imports = extract_python_imports(py_file)
        assert len(imports) == 0

    def test_import_resolution_between_siblings(self, tmp_path):
        """Python imports between sibling components get resolved."""
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)

        _make_py_package(src, "comp_a", [
            ("logic.py", "from comp_b import helper"),
        ])
        _make_py_package(src, "comp_b", [
            ("helper.py", "def helper(): pass"),
        ])

        tree = walk_repo(tmp_path)
        components = identify_components(tree, "test-repo", "ORGAN-I", tmp_path)

        comp_a = next((c for c in components if "comp_a" in c.path), None)
        assert comp_a is not None
        assert any("comp_b" in p for p in comp_a.imports_from)

    def test_imported_by_reverse_mapping(self, tmp_path):
        """imported_by gets populated as the reverse of imports_from."""
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)

        _make_py_package(src, "consumer", [
            ("main.py", "from provider import service"),
        ])
        _make_py_package(src, "provider", [
            ("service.py", "def service(): pass"),
        ])

        tree = walk_repo(tmp_path)
        components = identify_components(tree, "test-repo", "ORGAN-I", tmp_path)

        provider = next((c for c in components if "provider" in c.path), None)
        assert provider is not None
        assert any("consumer" in p for p in provider.imported_by)


# ── Seed generation tests ──────────────────────────────────────


class TestSeedGeneration:
    def test_generates_seeds(self, tmp_path):
        _make_py_package(tmp_path / "src" / "pkg", "core", [
            ("models.py", "class Model: pass\n"),
        ])

        tree = walk_repo(tmp_path)
        components = identify_components(tree, "my-repo", "ORGAN-I", tmp_path)
        seeds = generate_seeds(components, tmp_path)

        assert len(seeds) == 1
        seed = seeds[0]
        assert seed.parent_repo == "my-repo"
        assert seed.organ == "ORGAN-I"
        assert seed.cohesion_type == "python_package"
        assert seed.language == "python"
        assert seed.files > 0
        assert len(seed.fingerprint) == 16

    def test_seed_to_dict_has_component_flag(self):
        seed = ComponentSeed(
            parent_repo="repo",
            organ="ORGAN-I",
            path="src/pkg/core",
            cohesion_type="python_package",
            files=3,
            lines=100,
            language="python",
        )
        d = seed.to_dict()
        assert d["component"] is True
        assert d["parent_repo"] == "repo"

    def test_fingerprint_stability(self, tmp_path):
        _make_py_package(tmp_path / "src" / "pkg", "mod", [
            ("a.py", "x=1"),
        ])

        tree1 = walk_repo(tmp_path)
        comp1 = identify_components(tree1, "repo", "ORGAN-I", tmp_path)
        seeds1 = generate_seeds(comp1, tmp_path)

        tree2 = walk_repo(tmp_path)
        comp2 = identify_components(tree2, "repo", "ORGAN-I", tmp_path)
        seeds2 = generate_seeds(comp2, tmp_path)

        assert seeds1[0].fingerprint == seeds2[0].fingerprint

    def test_produces_contains_module_name(self, tmp_path):
        _make_py_package(tmp_path / "src" / "pkg", "governance", [
            ("audit.py", "x=1"),
        ])

        tree = walk_repo(tmp_path)
        components = identify_components(tree, "repo", "META", tmp_path)
        seeds = generate_seeds(components, tmp_path)

        assert "governance" in seeds[0].produces

    def test_consumes_from_imports(self, tmp_path):
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)
        _make_py_package(src, "consumer", [
            ("main.py", "from provider import x"),
        ])
        _make_py_package(src, "provider", [
            ("x.py", "x=1"),
        ])

        tree = walk_repo(tmp_path)
        components = identify_components(tree, "repo", "ORGAN-I", tmp_path)
        seeds = generate_seeds(components, tmp_path)

        consumer_seed = next(s for s in seeds if "consumer" in s.path)
        assert "provider" in consumer_seed.consumes


# ── Full pipeline tests ────────────────────────────────────────


class TestFullPipeline:
    def test_index_repo(self, tmp_path):
        _make_py_package(tmp_path / "src" / "engine", "registry", [
            ("loader.py", "def load(): pass"),
            ("query.py", "def find(): pass"),
        ])
        _make_py_package(tmp_path / "src" / "engine", "governance", [
            ("audit.py", "from registry import loader\n\ndef audit(): pass"),
        ])

        idx = index_repo(tmp_path, "test-engine", "META-ORGANVM")

        assert idx.repo == "test-engine"
        assert len(idx.components) == 2
        assert len(idx.seeds) == 2
        assert idx.total_files > 0

    def test_index_empty_repo(self, tmp_path):
        idx = index_repo(tmp_path, "empty", "ORGAN-I")
        assert idx.repo == "empty"
        assert len(idx.components) == 0

    def test_index_nonexistent_repo(self, tmp_path):
        idx = index_repo(tmp_path / "nope", "nope", "ORGAN-I")
        assert len(idx.components) == 0

    def test_system_index_with_registry(self, tmp_path):
        organ_dir = tmp_path / "organvm-i-theoria"
        organ_dir.mkdir()
        repo = organ_dir / "my-repo"
        repo.mkdir()
        _make_py_package(repo / "src" / "pkg", "core", [
            ("main.py", "x = 1\n"),
        ])

        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {"name": "my-repo", "org": "test-org"},
                    ],
                },
            },
        }

        index = run_deep_index(tmp_path, registry)
        assert index.scanned_repos == 1
        assert index.total_components >= 1
        assert "ORGAN-I" in index.by_organ

    def test_system_index_organ_filter(self, tmp_path):
        organ1 = tmp_path / "organvm-i-theoria"
        organ1.mkdir()
        repo1 = organ1 / "repo-a"
        repo1.mkdir()
        _make_py_package(repo1 / "src" / "pkg", "core", [("m.py", "x=1")])

        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {"name": "repo-a", "org": "test-org"},
                    ],
                },
                "META-ORGANVM": {
                    "repositories": [
                        {"name": "repo-b", "org": "meta"},
                    ],
                },
            },
        }

        index = run_deep_index(tmp_path, registry, organ_filter="ORGAN-I")
        assert index.scanned_repos == 1

    def test_system_index_repo_filter(self, tmp_path):
        organ1 = tmp_path / "organvm-i-theoria"
        organ1.mkdir()
        repo_a = organ1 / "repo-a"
        repo_a.mkdir()
        _make_py_package(repo_a / "src" / "pkg", "core", [("m.py", "x=1")])
        repo_b = organ1 / "repo-b"
        repo_b.mkdir()
        _make_py_package(repo_b / "src" / "pkg", "other", [("m.py", "x=1")])

        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {"name": "repo-a", "org": "test-org"},
                        {"name": "repo-b", "org": "test-org"},
                    ],
                },
            },
        }

        index = run_deep_index(tmp_path, registry, repo_filter="repo-a")
        assert index.scanned_repos == 1
        assert index.repos[0].repo == "repo-a"

    def test_skips_archived_repos(self, tmp_path):
        organ_dir = tmp_path / "organvm-i-theoria"
        organ_dir.mkdir()
        repo = organ_dir / "archived-repo"
        repo.mkdir()

        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "archived-repo",
                            "implementation_status": "ARCHIVED",
                        },
                    ],
                },
            },
        }

        index = run_deep_index(tmp_path, registry)
        assert index.scanned_repos == 0

    def test_serialization_roundtrip(self, tmp_path):
        """to_dict produces valid JSON-serializable output."""
        _make_py_package(tmp_path / "src" / "pkg", "core", [("m.py", "x=1")])

        idx = index_repo(tmp_path, "test", "ORGAN-I")
        d = idx.to_dict()

        json_str = json_mod.dumps(d)
        parsed = json_mod.loads(json_str)
        assert parsed["repo"] == "test"
        assert len(parsed["components"]) > 0

    def test_max_depth_tracked(self, tmp_path):
        deep = tmp_path / "src" / "pkg" / "sub"
        _make_py_package(deep, "deep_mod", [("x.py", "x=1")])

        idx = index_repo(tmp_path, "deep", "ORGAN-I")
        assert idx.max_depth >= 3

    def test_component_depth_reflects_nesting(self, tmp_path):
        _make_py_package(tmp_path / "src" / "pkg", "shallow", [("a.py", "x=1")])

        tree = walk_repo(tmp_path)
        components = identify_components(tree, "r", "O")

        for c in components:
            assert c.depth > 0  # never at root level

    def test_directory_node_is_leaf(self):
        leaf = DirectoryNode(path="leaf", name="leaf", depth=1)
        assert leaf.is_leaf is True

        parent = DirectoryNode(path="parent", name="parent", depth=0)
        parent.children = [leaf]
        assert parent.is_leaf is False
