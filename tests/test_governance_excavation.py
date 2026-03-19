"""Tests for governance excavation — buried entity scanners."""

import json
from pathlib import Path

from organvm_engine.governance.excavation import (
    BuriedEntity,
    ExcavationReport,
    _classify_sub_package,
    _parse_gitmodules,
    run_full_excavation,
    scan_cross_organ_families,
    scan_extractable_modules,
    scan_lineage,
    scan_misplaced_governance,
    scan_sub_packages,
    scan_submodule_topology,
)


def _make_registry(*organ_repos):
    """Build a minimal registry from (organ_key, repo_dict) tuples."""
    organs = {}
    for organ_key, repo in organ_repos:
        organs.setdefault(organ_key, {"name": organ_key, "repositories": []})
        organs[organ_key]["repositories"].append(repo)
    return {"organs": organs}


def _repo(
    name: str,
    org: str = "organvm-i-theoria",
    impl_status: str = "ACTIVE",
    **kw,
) -> dict:
    r = {
        "name": name,
        "org": org,
        "implementation_status": impl_status,
        "public": True,
        "description": f"Test {name}",
    }
    r.update(kw)
    return r


class TestScanSubPackages:
    def test_detects_nested_pyproject(self, tmp_path):
        """Nested pyproject.toml at depth > 0 should be found."""
        # Create workspace structure: organvm-i-theoria/my-repo/nested/pyproject.toml
        repo_dir = tmp_path / "organvm-i-theoria" / "my-repo"
        nested = repo_dir / "nested"
        nested.mkdir(parents=True)
        (nested / "pyproject.toml").write_text("[project]\nname='nested'")

        reg = _make_registry(("ORGAN-I", _repo("my-repo")))
        findings = scan_sub_packages(tmp_path, reg)

        assert len(findings) == 1
        assert findings[0].entity_type == "sub_package"
        assert findings[0].entity_path == "nested"
        assert findings[0].pattern == "embedded_app"
        assert findings[0].severity == "warning"

    def test_ignores_root_level_manifest(self, tmp_path):
        """Root-level pyproject.toml should not be flagged."""
        repo_dir = tmp_path / "organvm-i-theoria" / "my-repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "pyproject.toml").write_text("[project]\nname='root'")

        reg = _make_registry(("ORGAN-I", _repo("my-repo")))
        findings = scan_sub_packages(tmp_path, reg)
        assert len(findings) == 0

    def test_severity_escalation_for_ci(self, tmp_path):
        """Sub-package with its own CI should be critical, pattern embedded_app."""
        repo_dir = tmp_path / "organvm-i-theoria" / "my-repo"
        nested = repo_dir / "inner"
        workflows = nested / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("name: ci")
        (nested / "pyproject.toml").write_text("[project]\nname='inner'")

        reg = _make_registry(("ORGAN-I", _repo("my-repo")))
        findings = scan_sub_packages(tmp_path, reg)
        assert len(findings) == 1
        assert findings[0].severity == "critical"
        assert findings[0].pattern == "embedded_app"

    def test_skips_venv_and_node_modules(self, tmp_path):
        """Build manifests inside .venv or node_modules should be skipped."""
        repo_dir = tmp_path / "organvm-i-theoria" / "my-repo"
        venv = repo_dir / ".venv" / "lib"
        venv.mkdir(parents=True)
        (venv / "pyproject.toml").write_text("[project]")

        nm = repo_dir / "node_modules" / "some-pkg"
        nm.mkdir(parents=True)
        (nm / "package.json").write_text("{}")

        reg = _make_registry(("ORGAN-I", _repo("my-repo")))
        findings = scan_sub_packages(tmp_path, reg)
        assert len(findings) == 0

    def test_skips_archived_repos(self, tmp_path):
        """Archived repos should not be scanned."""
        repo_dir = tmp_path / "organvm-i-theoria" / "old-repo"
        nested = repo_dir / "inner"
        nested.mkdir(parents=True)
        (nested / "pyproject.toml").write_text("[project]")

        reg = _make_registry(("ORGAN-I", _repo("old-repo", impl_status="ARCHIVED")))
        findings = scan_sub_packages(tmp_path, reg)
        assert len(findings) == 0

    def test_pattern_embedded_app(self, tmp_path):
        """Top-level nested dir without workspace parent → embedded_app."""
        repo_dir = tmp_path / "organvm-i-theoria" / "my-repo"
        nested = repo_dir / "inner-app"
        nested.mkdir(parents=True)
        (nested / "package.json").write_text("{}")

        reg = _make_registry(("ORGAN-I", _repo("my-repo")))
        findings = scan_sub_packages(tmp_path, reg)
        assert len(findings) == 1
        assert findings[0].pattern == "embedded_app"
        assert findings[0].severity == "warning"

    def test_pattern_workspace(self, tmp_path):
        """Sub-package under packages/ → workspace pattern, severity info."""
        repo_dir = tmp_path / "organvm-i-theoria" / "my-repo"
        pkg = repo_dir / "packages" / "core"
        pkg.mkdir(parents=True)
        (pkg / "package.json").write_text("{}")

        reg = _make_registry(("ORGAN-I", _repo("my-repo")))
        findings = scan_sub_packages(tmp_path, reg)
        assert len(findings) == 1
        assert findings[0].pattern == "workspace"
        assert findings[0].severity == "info"

    def test_pattern_misplacement(self, tmp_path):
        """Known misplacement → critical severity."""
        repo_dir = tmp_path / "meta-organvm" / "organvm-corpvs-testamentvm"
        misplaced = repo_dir / "portfolio-site"
        misplaced.mkdir(parents=True)
        (misplaced / "package.json").write_text("{}")

        reg = _make_registry(
            ("META-ORGANVM", _repo("organvm-corpvs-testamentvm", org="meta-organvm")),
        )
        findings = scan_sub_packages(tmp_path, reg)
        assert len(findings) == 1
        assert findings[0].pattern == "misplacement"
        assert findings[0].severity == "critical"

    def test_pattern_workspace_apps_dir(self, tmp_path):
        """Sub-package under apps/ → workspace pattern."""
        repo_dir = tmp_path / "organvm-i-theoria" / "my-repo"
        app = repo_dir / "apps" / "web"
        app.mkdir(parents=True)
        (app / "package.json").write_text("{}")

        reg = _make_registry(("ORGAN-I", _repo("my-repo")))
        findings = scan_sub_packages(tmp_path, reg)
        assert len(findings) == 1
        assert findings[0].pattern == "workspace"

    def test_pattern_in_evidence(self, tmp_path):
        """Pattern should appear in evidence list."""
        repo_dir = tmp_path / "organvm-i-theoria" / "my-repo"
        nested = repo_dir / "nested"
        nested.mkdir(parents=True)
        (nested / "pyproject.toml").write_text("[project]")

        reg = _make_registry(("ORGAN-I", _repo("my-repo")))
        findings = scan_sub_packages(tmp_path, reg)
        assert any("Pattern:" in e for e in findings[0].evidence)

    def test_pattern_specific_recommendation(self, tmp_path):
        """Recommendation should be pattern-specific, not generic."""
        repo_dir = tmp_path / "organvm-i-theoria" / "my-repo"
        pkg = repo_dir / "packages" / "util"
        pkg.mkdir(parents=True)
        (pkg / "package.json").write_text("{}")

        reg = _make_registry(("ORGAN-I", _repo("my-repo")))
        findings = scan_sub_packages(tmp_path, reg)
        assert "workspace manager" in findings[0].recommendation.lower()


class TestClassifySubPackage:
    """Direct tests for the pattern classifier."""

    def test_known_misplacement(self):
        assert _classify_sub_package(
            "organvm-corpvs-testamentvm", Path("portfolio-site"), has_ci=False,
        ) == "misplacement"

    def test_workspace_packages(self):
        assert _classify_sub_package("repo", Path("packages/core"), has_ci=False) == "workspace"

    def test_workspace_apps(self):
        assert _classify_sub_package("repo", Path("apps/web"), has_ci=False) == "workspace"

    def test_workspace_services(self):
        assert _classify_sub_package("repo", Path("services/api"), has_ci=False) == "workspace"

    def test_workspace_libs(self):
        assert _classify_sub_package("repo", Path("libs/shared"), has_ci=False) == "workspace"

    def test_workspace_crates(self):
        assert _classify_sub_package("repo", Path("crates/core"), has_ci=False) == "workspace"

    def test_embedded_app_with_ci(self):
        assert _classify_sub_package("repo", Path("inner"), has_ci=True) == "embedded_app"

    def test_embedded_app_top_level(self):
        assert _classify_sub_package("repo", Path("conductor"), has_ci=False) == "embedded_app"

    def test_embedded_app_deep_nesting(self):
        assert _classify_sub_package(
            "repo", Path("foo/bar/baz"), has_ci=False,
        ) == "embedded_app"

    def test_misplacement_overrides_workspace_parent(self):
        """Explicit misplacement should win even if path contains workspace dir."""
        from organvm_engine.governance.excavation import _KNOWN_MISPLACEMENTS
        # If we added a misplacement under packages/, it should still be misplacement
        _KNOWN_MISPLACEMENTS.add(("test-repo", "packages/wrong"))
        try:
            assert _classify_sub_package(
                "test-repo", Path("packages/wrong"), has_ci=False,
            ) == "misplacement"
        finally:
            _KNOWN_MISPLACEMENTS.discard(("test-repo", "packages/wrong"))


class TestScanCrossOrganFamilies:
    def test_groups_by_prefix(self):
        """Repos with same prefix across organs should form a family."""
        reg = _make_registry(
            ("ORGAN-I", _repo("styx-behavioral-theory")),
            ("ORGAN-II", _repo("styx-behavioral-art", org="organvm-ii-poiesis")),
        )
        findings, families = scan_cross_organ_families(reg)
        assert len(families) >= 1
        assert any(f["stem"] == "styx-behavioral" for f in families)

    def test_single_organ_prefix_not_flagged(self):
        """Repos sharing a prefix within ONE organ should not be flagged."""
        reg = _make_registry(
            ("ORGAN-I", _repo("deep-theory-a")),
            ("ORGAN-I", _repo("deep-theory-b")),
        )
        findings, families = scan_cross_organ_families(reg)
        # All in same organ, so no cross-organ family
        assert len(families) == 0

    def test_double_hyphen_stems(self):
        """Double-hyphen names should extract the stem before --."""
        reg = _make_registry(
            ("ORGAN-I", _repo("sema-metra--alchemica")),
            ("ORGAN-II", _repo("sema-metra--artistica", org="organvm-ii-poiesis")),
        )
        findings, families = scan_cross_organ_families(reg)
        assert len(families) >= 1

    def test_short_stems_ignored(self):
        """Very short stems (<4 chars) should not trigger families."""
        reg = _make_registry(
            ("ORGAN-I", _repo("a-x")),
            ("ORGAN-II", _repo("a-y", org="organvm-ii-poiesis")),
        )
        findings, families = scan_cross_organ_families(reg)
        assert len(families) == 0


class TestScanExtractableModules:
    def test_detects_large_module(self, tmp_path):
        """Module with >10 files should be flagged."""
        repo_dir = tmp_path / "meta-organvm" / "organvm-engine"
        mod_dir = repo_dir / "src" / "organvm_engine" / "bigmod"
        mod_dir.mkdir(parents=True)
        for i in range(12):
            (mod_dir / f"file_{i}.py").write_text(f"# line {i}\n" * 50)

        reg = _make_registry(("META-ORGANVM", _repo("organvm-engine", org="meta-organvm")))
        findings = scan_extractable_modules(tmp_path, reg, file_threshold=10)
        assert len(findings) == 1
        assert findings[0].entity_type == "extractable_module"
        assert findings[0].scale["files"] == 12

    def test_excludes_cli_directory(self, tmp_path):
        """cli/ should be excluded (dispatch packages are expected to be large)."""
        repo_dir = tmp_path / "meta-organvm" / "organvm-engine"
        cli_dir = repo_dir / "src" / "organvm_engine" / "cli"
        cli_dir.mkdir(parents=True)
        for i in range(20):
            (cli_dir / f"cmd_{i}.py").write_text("# cmd\n")

        reg = _make_registry(("META-ORGANVM", _repo("organvm-engine", org="meta-organvm")))
        findings = scan_extractable_modules(tmp_path, reg)
        assert len(findings) == 0

    def test_respects_thresholds(self, tmp_path):
        """Custom thresholds should be honored."""
        repo_dir = tmp_path / "meta-organvm" / "organvm-engine"
        mod_dir = repo_dir / "src" / "organvm_engine" / "smallmod"
        mod_dir.mkdir(parents=True)
        for i in range(5):
            (mod_dir / f"f_{i}.py").write_text("x = 1\n")

        reg = _make_registry(("META-ORGANVM", _repo("organvm-engine", org="meta-organvm")))
        # Threshold of 3 should catch this module
        findings = scan_extractable_modules(tmp_path, reg, file_threshold=3)
        assert len(findings) == 1


class TestScanMisplacedGovernance:
    def test_finds_sop_files(self, tmp_path):
        """SOP files in non-governance repos should be found."""
        repo_dir = tmp_path / "organvm-iii-ergon" / "my-product"
        repo_dir.mkdir(parents=True)
        (repo_dir / "SOP-deployment.md").write_text("# SOP")

        reg = _make_registry(
            ("ORGAN-III", _repo("my-product", org="organvm-iii-ergon")),
        )
        findings = scan_misplaced_governance(tmp_path, reg)
        assert len(findings) == 1
        assert findings[0].entity_type == "misplaced_governance"

    def test_excludes_governance_repos(self, tmp_path):
        """Governance repos should not be flagged for having governance files."""
        repo_dir = tmp_path / "meta-organvm" / "praxis-perpetua"
        repo_dir.mkdir(parents=True)
        (repo_dir / "SOP-test.md").write_text("# SOP")

        reg = _make_registry(
            ("META-ORGANVM", _repo("praxis-perpetua", org="meta-organvm")),
        )
        findings = scan_misplaced_governance(tmp_path, reg)
        assert len(findings) == 0

    def test_excludes_standard_root_files(self, tmp_path):
        """CONTRIBUTING.md etc. should not be flagged."""
        repo_dir = tmp_path / "organvm-i-theoria" / "my-repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "CONTRIBUTING.md").write_text("# Contributing")
        (repo_dir / "CODE_OF_CONDUCT.md").write_text("# CoC")

        reg = _make_registry(("ORGAN-I", _repo("my-repo")))
        findings = scan_misplaced_governance(tmp_path, reg)
        assert len(findings) == 0

    def test_finds_governance_directory(self, tmp_path):
        """A governance/ directory in a non-governance repo should be found."""
        repo_dir = tmp_path / "organvm-iii-ergon" / "commerce--meta"
        gov_dir = repo_dir / "governance"
        gov_dir.mkdir(parents=True)
        (gov_dir / "policy.md").write_text("# Policy")

        reg = _make_registry(
            ("ORGAN-III", _repo("commerce--meta", org="organvm-iii-ergon")),
        )
        findings = scan_misplaced_governance(tmp_path, reg)
        assert len(findings) == 1
        assert findings[0].entity_path == "governance"


class TestRunFullExcavation:
    def test_merges_all_scanners(self, tmp_path):
        """Full excavation should merge results from all scanners."""
        # Create a repo with a nested sub-package
        repo_dir = tmp_path / "organvm-i-theoria" / "my-repo"
        nested = repo_dir / "inner"
        nested.mkdir(parents=True)
        (nested / "pyproject.toml").write_text("[project]")

        reg = _make_registry(("ORGAN-I", _repo("my-repo")))
        report = run_full_excavation(tmp_path, reg)

        assert report.scanned_repos >= 1
        assert report.total_findings >= 1
        assert "sub_package" in report.by_type

    def test_summary_counts_correct(self, tmp_path):
        """by_type and by_severity counts should match findings."""
        repo_dir = tmp_path / "organvm-i-theoria" / "my-repo"
        repo_dir.mkdir(parents=True)

        reg = _make_registry(("ORGAN-I", _repo("my-repo")))
        report = run_full_excavation(tmp_path, reg)

        total_by_type = sum(report.by_type.values())
        total_by_sev = sum(report.by_severity.values())
        assert total_by_type == report.total_findings
        assert total_by_sev == report.total_findings

    def test_json_serialization(self, tmp_path):
        """to_dict should produce valid JSON."""
        repo_dir = tmp_path / "organvm-i-theoria" / "my-repo"
        repo_dir.mkdir(parents=True)

        reg = _make_registry(("ORGAN-I", _repo("my-repo")))
        report = run_full_excavation(tmp_path, reg)
        d = report.to_dict()
        # Should be JSON-serializable
        json.dumps(d)

    def test_empty_workspace(self, tmp_path):
        """Empty registry should return empty report."""
        reg = {"organs": {}}
        report = run_full_excavation(tmp_path, reg)
        assert report.scanned_repos == 0
        assert report.total_findings == 0

    def test_findings_sorted_by_severity(self, tmp_path):
        """Findings should be sorted critical > warning > info."""
        # Create sub-package with CI (critical) and regular one (warning)
        repo_dir = tmp_path / "organvm-i-theoria" / "my-repo"
        inner1 = repo_dir / "critical-pkg"
        ci_dir = inner1 / ".github" / "workflows"
        ci_dir.mkdir(parents=True)
        (ci_dir / "ci.yml").write_text("name: ci")
        (inner1 / "pyproject.toml").write_text("[project]")

        inner2 = repo_dir / "warn-pkg"
        inner2.mkdir(parents=True)
        (inner2 / "pyproject.toml").write_text("[project]")

        reg = _make_registry(("ORGAN-I", _repo("my-repo")))
        report = run_full_excavation(tmp_path, reg)

        sev_order = {"critical": 0, "warning": 1, "info": 2}
        for i in range(len(report.findings) - 1):
            cur = sev_order.get(report.findings[i].severity, 9)
            nxt = sev_order.get(report.findings[i + 1].severity, 9)
            assert cur <= nxt


class TestDataclasses:
    def test_buried_entity_to_dict(self):
        be = BuriedEntity(
            repo="test", organ="ORGAN-I", entity_path="inner",
            entity_type="sub_package", severity="warning",
        )
        d = be.to_dict()
        assert d["repo"] == "test"
        assert d["entity_type"] == "sub_package"

    def test_excavation_report_to_dict(self):
        er = ExcavationReport(scanned_repos=10, total_findings=3)
        d = er.to_dict()
        assert d["scanned_repos"] == 10


# ── .gitmodules helper ──────────────────────────────────────────

def _write_gitmodules(path: Path, entries: list[tuple[str, str, str]]):
    """Write a .gitmodules file from (name, path, url) tuples."""
    lines = []
    for name, sub_path, url in entries:
        lines.append(f'[submodule "{name}"]')
        lines.append(f"\tpath = {sub_path}")
        lines.append(f"\turl = {url}")
    path.write_text("\n".join(lines) + "\n")


class TestParseGitmodules:
    def test_parses_basic_entry(self, tmp_path):
        gm = tmp_path / ".gitmodules"
        _write_gitmodules(gm, [("my-repo", "my-repo", "https://github.com/org/my-repo.git")])
        entries = _parse_gitmodules(gm)
        assert len(entries) == 1
        assert entries[0]["name"] == "my-repo"
        assert entries[0]["path"] == "my-repo"

    def test_extracts_github_org(self, tmp_path):
        gm = tmp_path / ".gitmodules"
        _write_gitmodules(gm, [("r", "r", "https://github.com/test-org/r.git")])
        entries = _parse_gitmodules(gm)
        assert entries[0]["github_org"] == "test-org"
        assert entries[0]["github_repo"] == "r"

    def test_handles_ssh_url(self, tmp_path):
        gm = tmp_path / ".gitmodules"
        _write_gitmodules(gm, [("r", "r", "git@github.com:my-org/my-repo.git")])
        entries = _parse_gitmodules(gm)
        assert entries[0]["github_org"] == "my-org"
        assert entries[0]["github_repo"] == "my-repo"

    def test_empty_file(self, tmp_path):
        gm = tmp_path / ".gitmodules"
        gm.write_text("")
        assert _parse_gitmodules(gm) == []

    def test_missing_file(self, tmp_path):
        assert _parse_gitmodules(tmp_path / "nope") == []

    def test_multiple_entries(self, tmp_path):
        gm = tmp_path / ".gitmodules"
        _write_gitmodules(gm, [
            ("a", "a", "https://github.com/org/a.git"),
            ("b", "b", "https://github.com/org/b.git"),
        ])
        entries = _parse_gitmodules(gm)
        assert len(entries) == 2
        assert {e["name"] for e in entries} == {"a", "b"}


class TestScanSubmoduleTopology:
    def test_detects_superproject_mismatch(self, tmp_path):
        """Repo in ORGAN-I superproject but registered in ORGAN-IV."""
        organ_i = tmp_path / "organvm-i-theoria"
        organ_i.mkdir()
        _write_gitmodules(
            organ_i / ".gitmodules",
            [("misplaced", "misplaced", "https://github.com/organvm-i-theoria/misplaced.git")],
        )

        reg = _make_registry(("ORGAN-IV", _repo("misplaced", org="organvm-iv-taxis")))
        findings = scan_submodule_topology(tmp_path, reg)

        sp_findings = [f for f in findings if f.pattern == "superproject_mismatch"]
        assert len(sp_findings) == 1
        assert sp_findings[0].severity == "critical"
        assert sp_findings[0].organ == "ORGAN-IV"
        assert "ORGAN-I" in sp_findings[0].evidence[1]

    def test_detects_org_mismatch(self, tmp_path):
        """URL org differs from registry org."""
        organ_iv = tmp_path / "organvm-iv-taxis"
        organ_iv.mkdir()
        _write_gitmodules(
            organ_iv / ".gitmodules",
            [("repo-x", "repo-x", "https://github.com/wrong-org/repo-x.git")],
        )

        reg = _make_registry(("ORGAN-IV", _repo("repo-x", org="organvm-iv-taxis")))
        findings = scan_submodule_topology(tmp_path, reg)

        org_findings = [f for f in findings if f.pattern == "org_mismatch"]
        assert len(org_findings) == 1
        assert org_findings[0].severity == "warning"
        assert "wrong-org" in str(org_findings[0].evidence)

    def test_detects_dual_homed(self, tmp_path):
        """Repo appears in two different organ superprojects."""
        for organ_dir in ("organvm-i-theoria", "organvm-iv-taxis"):
            d = tmp_path / organ_dir
            d.mkdir()
            _write_gitmodules(
                d / ".gitmodules",
                [("shared", "shared", "https://github.com/org/shared.git")],
            )

        reg = _make_registry(("ORGAN-I", _repo("shared")))
        findings = scan_submodule_topology(tmp_path, reg)

        dual = [f for f in findings if f.pattern == "dual_homed"]
        assert len(dual) == 1
        assert "2 superprojects" in dual[0].evidence[0]

    def test_detects_orphan_submodule(self, tmp_path):
        """Submodule not in registry is flagged as orphan."""
        organ_i = tmp_path / "organvm-i-theoria"
        organ_i.mkdir()
        _write_gitmodules(
            organ_i / ".gitmodules",
            [("ghost", "ghost", "https://github.com/org/ghost.git")],
        )

        reg = _make_registry()  # empty
        findings = scan_submodule_topology(tmp_path, reg)

        orphans = [f for f in findings if f.entity_type == "submodule_orphan"]
        assert len(orphans) == 1
        assert orphans[0].repo == "ghost"

    def test_skips_dot_repos(self, tmp_path):
        """.github entries should not be flagged as orphan."""
        organ_i = tmp_path / "organvm-i-theoria"
        organ_i.mkdir()
        _write_gitmodules(
            organ_i / ".gitmodules",
            [(".github", ".github", "https://github.com/org/.github.git")],
        )

        reg = _make_registry()
        findings = scan_submodule_topology(tmp_path, reg)
        assert len(findings) == 0

    def test_no_findings_when_aligned(self, tmp_path):
        """Correctly aligned repo produces no findings."""
        organ_i = tmp_path / "organvm-i-theoria"
        organ_i.mkdir()
        _write_gitmodules(
            organ_i / ".gitmodules",
            [("good", "good", "https://github.com/organvm-i-theoria/good.git")],
        )

        reg = _make_registry(("ORGAN-I", _repo("good", org="organvm-i-theoria")))
        findings = scan_submodule_topology(tmp_path, reg)
        assert len(findings) == 0

    def test_no_gitmodules(self, tmp_path):
        """Missing .gitmodules files should not cause errors."""
        reg = _make_registry(("ORGAN-I", _repo("lonely")))
        findings = scan_submodule_topology(tmp_path, reg)
        assert len(findings) == 0

    def test_empty_registry(self, tmp_path):
        """Empty registry + no .gitmodules → no findings."""
        reg = {"organs": {}}
        findings = scan_submodule_topology(tmp_path, reg)
        assert len(findings) == 0


class TestScanLineage:
    def test_detects_art_from_derivative(self):
        """art-from--X with matching source X should be detected."""
        reg = _make_registry(
            ("ORGAN-I", _repo("auto-revision-epistemic-engine")),
            ("ORGAN-II", _repo(
                "art-from--auto-revision-epistemic-engine",
                org="organvm-ii-poiesis",
            )),
        )
        findings = scan_lineage(reg)
        assert len(findings) == 1
        assert findings[0].pattern == "artistic_derivative"
        assert findings[0].repo == "art-from--auto-revision-epistemic-engine"

    def test_cross_organ_derivative_is_warning(self):
        """Cross-organ derivation should be warning severity."""
        reg = _make_registry(
            ("ORGAN-I", _repo("source-engine")),
            ("ORGAN-II", _repo("art-from--source-engine", org="organvm-ii-poiesis")),
        )
        findings = scan_lineage(reg)
        assert findings[0].severity == "warning"
        assert "Cross-organ" in findings[0].evidence[3]

    def test_same_organ_derivative_is_info(self):
        """Same-organ derivation should be info severity."""
        reg = _make_registry(
            ("ORGAN-II", _repo("base-work", org="organvm-ii-poiesis")),
            ("ORGAN-II", _repo("art-from--base-work", org="organvm-ii-poiesis")),
        )
        findings = scan_lineage(reg)
        assert findings[0].severity == "info"
        assert "Same-organ" in findings[0].evidence[3]

    def test_orphan_derivative(self):
        """art-from--X with no matching source → orphan_derivative."""
        reg = _make_registry(
            ("ORGAN-II", _repo("art-from--nonexistent", org="organvm-ii-poiesis")),
        )
        findings = scan_lineage(reg)
        assert len(findings) == 1
        assert findings[0].pattern == "orphan_derivative"
        assert findings[0].severity == "warning"

    def test_skips_archived_repos(self):
        """Archived repos should be excluded from lineage scan."""
        reg = _make_registry(
            ("ORGAN-I", _repo("old-engine", impl_status="ARCHIVED")),
            ("ORGAN-II", _repo("art-from--old-engine", org="organvm-ii-poiesis")),
        )
        findings = scan_lineage(reg)
        # Source is archived → art-from--old-engine has no match → orphan
        assert len(findings) == 1
        assert findings[0].pattern == "orphan_derivative"

    def test_no_derivation_patterns(self):
        """Repos without derivation prefixes produce no findings."""
        reg = _make_registry(
            ("ORGAN-I", _repo("plain-repo")),
            ("ORGAN-II", _repo("another-repo", org="organvm-ii-poiesis")),
        )
        findings = scan_lineage(reg)
        assert len(findings) == 0

    def test_empty_registry(self):
        """Empty registry → no findings."""
        findings = scan_lineage({"organs": {}})
        assert len(findings) == 0
