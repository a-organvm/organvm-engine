"""Tests for the refresh CLI command."""

import argparse
import json

import pytest

from organvm_engine.cli.refresh import cmd_refresh


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Create a minimal workspace with registry and metrics."""
    # Prevent resolve_workspace from falling through to the real ~/Workspace
    # via the ORGANVM_WORKSPACE_DIR env var.
    monkeypatch.delenv("ORGANVM_WORKSPACE_DIR", raising=False)
    monkeypatch.delenv("ORGANVM_CORPUS_DIR", raising=False)

    corpus = tmp_path / "corpus"
    corpus.mkdir()

    registry = {
        "version": "2.0",
        "organs": {
            "ORGAN-I": {
                "name": "Theoria",
                "launch_status": "OPERATIONAL",
                "repositories": [
                    {
                        "name": "repo-1",
                        "implementation_status": "ACTIVE",
                        "ci_workflow": True,
                        "dependencies": [],
                    },
                ],
            },
        },
    }
    reg_path = corpus / "registry-v2.json"
    with reg_path.open("w") as f:
        json.dump(registry, f)

    return tmp_path, corpus, reg_path


def _make_args(reg_path, dry_run=True, **kwargs):
    defaults = {
        "registry": str(reg_path),
        "workspace": None,
        "dry_run": dry_run,
        "skip_context": True,
        "skip_organism": True,
        "skip_legacy": True,
        "skip_plans": True,
        "skip_sop": True,
        "skip_atoms": True,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_refresh_dry_run(workspace, capsys):
    tmp_path, corpus, reg_path = workspace
    args = _make_args(reg_path, dry_run=True)

    rc = cmd_refresh(args)

    assert rc == 0
    out = capsys.readouterr().out
    assert "[DRY RUN]" in out
    assert "[1/10]" in out
    assert "[2/10]" in out


def test_refresh_writes_metrics_and_vars(workspace, capsys):
    tmp_path, corpus, reg_path = workspace
    args = _make_args(reg_path, dry_run=False)

    rc = cmd_refresh(args)

    assert rc == 0
    assert (corpus / "system-metrics.json").exists()
    assert (corpus / "system-vars.json").exists()

    with (corpus / "system-vars.json").open() as f:
        variables = json.load(f)
    assert variables["total_repos"] == "1"
    assert variables["organ_repos.ORGAN-I"] == "1"


def test_refresh_resolves_var_targets(workspace, capsys):
    tmp_path, corpus, reg_path = workspace

    # Create a target file with markers
    target = corpus / "README.md"
    target.write_text("Repos: <!-- v:total_repos -->0<!-- /v -->\n")

    # Create vars-targets.yaml
    manifest = corpus / "vars-targets.yaml"
    manifest.write_text(
        f"targets:\n"
        f"  - root: \"{corpus}\"\n"
        f"    files: [\"README.md\"]\n",
    )

    args = _make_args(reg_path, dry_run=False)
    rc = cmd_refresh(args)

    assert rc == 0
    content = target.read_text()
    assert "<!-- v:total_repos -->1<!-- /v -->" in content


def test_refresh_no_vars_targets(workspace, capsys):
    """Refresh should work even without vars-targets.yaml."""
    tmp_path, corpus, reg_path = workspace
    args = _make_args(reg_path, dry_run=False)

    rc = cmd_refresh(args)

    assert rc == 0
    out = capsys.readouterr().out
    assert "No vars-targets.yaml found" in out


def test_refresh_skip_flags(workspace, capsys):
    tmp_path, corpus, reg_path = workspace
    args = _make_args(
        reg_path, dry_run=True,
        skip_context=True, skip_organism=True, skip_legacy=True,
    )

    rc = cmd_refresh(args)

    assert rc == 0
    out = capsys.readouterr().out
    assert "skipped" in out.lower()
