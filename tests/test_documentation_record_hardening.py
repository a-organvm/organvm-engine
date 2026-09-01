"""Adversarial regressions for canonical documentation records."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

import nbformat
import pytest
import yaml

from organvm_engine.cli.docs import cmd_docs_validate
from organvm_engine.documentation.audit import audit_repository
from organvm_engine.documentation.record import load_project_record, validate_project_record


def _record() -> dict:
    return {
        "contract_name": "project-record.v1",
        "contract_version": 1,
        "project_id": "example",
        "name": "Example",
        "canonical_repository": "organvm/example",
        "repository_role": "canonical",
        "documentation_class": "B",
        "one_sentence": "A complete test project record.",
        "problem": "Documentation claims need deterministic validation.",
        "intended_users": ["maintainers"],
        "implementation_status": "PROTOTYPE",
        "deployment_status": "not-deployed",
        "authorship": {"owner": "Test Maintainer"},
        "claim_references": [
            {
                "id": "project-status",
                "assertion_contract": "assertion-evidence.v1",
                "assertion_id": "validation",
                "assertion_ref": "docs/evidence/claims/validation.json",
                "scope": "status",
                "claim_posture": "implemented",
            },
            {
                "id": "validation",
                "assertion_contract": "assertion-evidence.v1",
                "assertion_id": "validation",
                "assertion_ref": "docs/evidence/claims/validation.json",
                "scope": "capability",
                "claim_posture": "implemented",
            },
        ],
        "limitations": [],
        "audience_routes": [
            {
                "mode": "general",
                "path": "docs/audiences/general.md",
            },
            {
                "mode": "technical",
                "path": "docs/audiences/technical.md",
            },
        ],
        "search_intents": [],
        "links": {
            "repository": "https://github.com/organvm/example",
            "documentation": "https://docs.example.test/project",
            "evidence": "https://docs.example.test/evidence",
        },
        "generated_at": "2025-01-01T00:00:00Z",
        "verified_at": "2025-01-01T00:00:00Z",
    }


def _git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
    ).stdout


def _write_git_fixture(root: Path) -> dict:
    record = _record()
    for route in record["audience_routes"]:
        route_path = root / route["path"]
        route_path.parent.mkdir(parents=True, exist_ok=True)
        route_path.write_text(f"# {route['mode']}\n", encoding="utf-8")

    evidence_path = root / "docs/evidence/sources/validation.txt"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text("committed evidence\n", encoding="utf-8")
    assertion_path = root / "docs/evidence/claims/validation.json"
    assertion_path.parent.mkdir(parents=True, exist_ok=True)
    assertion_path.write_text(
        json.dumps(
            {
                "contract_name": "assertion-evidence.v1",
                "contract_version": 1,
                "assertion_id": "validation",
                "assertion_class": "historical_record",
                "statement": "The committed validation fixture exists.",
                "verification_state": "verified",
                "evidence_references": [
                    {
                        "evidence_id": "validation-receipt",
                        "independence_group": "local-fixture",
                        "evidence_type": "artifact",
                        "reference": evidence_path.relative_to(root).as_posix(),
                        "body_hash": (
                            "sha256:"
                            + hashlib.sha256(evidence_path.read_bytes()).hexdigest()
                        ),
                    },
                ],
            },
        ),
        encoding="utf-8",
    )
    _git(root, "init")
    _git(root, "config", "user.name", "Record Hardening Tests")
    _git(root, "config", "user.email", "record-hardening@example.test")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture")
    return record


@pytest.mark.parametrize(
    "route",
    [
        "docs/audiences/../private.md",
        "docs/audiences/nested/technical.md",
        "docs/audiences/.md",
        "docs/audiences/technical.txt",
    ],
)
def test_audience_routes_require_one_canonical_slug_file(route: str) -> None:
    record = _record()
    record["audience_routes"][1]["path"] = route

    assert "audience_routes[1] path must match docs/audiences/<slug>.md" in (
        validate_project_record(record)
    )


@pytest.mark.parametrize("slug", ["technical-review", "technical--deep", "technical-"])
def test_audience_route_accepts_schema_permitted_hyphenated_slugs(slug: str) -> None:
    record = _record()
    record["audience_routes"][1]["path"] = f"docs/audiences/{slug}.md"

    assert validate_project_record(record) == []


@pytest.mark.parametrize(
    "repository_url",
    [
        "https://user@github.com/organvm/example",
        "https://user:secret@github.com/organvm/example",
        "https://github.com:443/organvm/example",
        "https://github.com:8443/organvm/example",
        "https://github.com:/organvm/example",
        "https://github.com:not-a-port/organvm/example",
    ],
)
def test_canonical_github_url_rejects_credentials_and_ports(
    repository_url: str,
) -> None:
    record = _record()
    record["links"]["repository"] = repository_url

    assert "links.repository must be a canonical GitHub repository URL" in (
        validate_project_record(record)
    )


@pytest.mark.parametrize(
    ("relative_path", "index_flag", "object_name"),
    [
        (
            "docs/evidence/sources/validation.txt",
            "--assume-unchanged",
            "evidence",
        ),
        (
            "docs/evidence/sources/validation.txt",
            "--skip-worktree",
            "evidence",
        ),
        (
            "docs/evidence/claims/validation.json",
            "--assume-unchanged",
            "assertion",
        ),
        (
            "docs/evidence/claims/validation.json",
            "--skip-worktree",
            "assertion",
        ),
    ],
)
def test_strict_records_reject_hidden_index_flags(
    tmp_path: Path,
    relative_path: str,
    index_flag: str,
    object_name: str,
) -> None:
    record = _write_git_fixture(tmp_path)
    _git(tmp_path, "update-index", index_flag, relative_path)
    target = tmp_path / relative_path
    if target.suffix == ".json":
        assertion = json.loads(target.read_text(encoding="utf-8"))
        assertion["statement"] = "Hidden working-tree assertion bytes."
        target.write_text(json.dumps(assertion), encoding="utf-8")
    else:
        target.write_text("hidden working-tree evidence bytes\n", encoding="utf-8")

    errors = validate_project_record(
        record,
        root=tmp_path,
        require_git_tracked_evidence=True,
    )

    assert any(
        f"{object_name} is marked {index_flag.removeprefix('--')}" in error
        for error in errors
    )


@pytest.mark.parametrize("schema_argument", ["schema", "assertion_schema"])
def test_docs_validate_reports_malformed_schema_as_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    schema_argument: str,
) -> None:
    record_path = tmp_path / "project-record.yml"
    record_path.write_text("{}\n", encoding="utf-8")
    schema_path = tmp_path / f"{schema_argument}.yml"
    schema_path.write_text("properties: [unterminated\n", encoding="utf-8")
    arguments = {
        "record": str(record_path),
        "root": str(tmp_path),
        "schema": None,
        "assertion_schema": None,
        "json": True,
    }
    arguments[schema_argument] = str(schema_path)

    assert cmd_docs_validate(Namespace(**arguments)) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    assert payload["errors"]
    assert "while parsing a flow sequence" in payload["errors"][0]


def test_malformed_yaml_assertion_becomes_an_audit_finding(tmp_path: Path) -> None:
    record = _record()
    for route in record["audience_routes"]:
        route_path = tmp_path / route["path"]
        route_path.parent.mkdir(parents=True, exist_ok=True)
        route_path.write_text(f"# {route['mode']}\n", encoding="utf-8")
    for claim in record["claim_references"]:
        claim["assertion_ref"] = "docs/evidence/claims/validation.yml"
    assertion_path = tmp_path / "docs/evidence/claims/validation.yml"
    assertion_path.parent.mkdir(parents=True, exist_ok=True)
    assertion_path.write_text("evidence_references: [unterminated\n", encoding="utf-8")
    (tmp_path / "project-record.yml").write_text(
        yaml.safe_dump(record, sort_keys=False),
        encoding="utf-8",
    )

    result = audit_repository(tmp_path)

    assert any("cannot load assertion" in error for error in result["record_errors"])
    assert any(
        finding["code"] == "invalid-project-record" for finding in result["findings"]
    )


@pytest.mark.parametrize(
    "key",
    ["project_page", "demo", "deployment", "documentation", "evidence"],
)
def test_every_web_link_rejects_credentials(key: str) -> None:
    record = _record()
    record["links"][key] = "https://user:password@example.test/path"

    assert any(f"links.{key}" in error for error in validate_project_record(record))


@pytest.mark.parametrize("repository", ["./example", "../..", "organvm/..", "./."])
def test_repository_slugs_reject_dot_segments(repository: str) -> None:
    record = _record()
    record["canonical_repository"] = repository
    record["links"]["repository"] = f"https://github.com/{repository}"

    errors = validate_project_record(record)

    assert "canonical_repository must use owner/name form" in errors
    assert "links.repository must be a canonical GitHub repository URL" in errors


def test_yaml_native_datetimes_are_normalized_before_validation(tmp_path: Path) -> None:
    record_path = tmp_path / "project-record.yml"
    record_path.write_text(
        yaml.safe_dump(_record(), sort_keys=False).replace(
            "'2025-01-01T00:00:00Z'",
            "2025-01-01T00:00:00Z",
        ),
        encoding="utf-8",
    )

    record = load_project_record(record_path)

    assert isinstance(record["generated_at"], str)
    assert validate_project_record(
        record,
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    ) == []


def test_verified_deployment_status_requires_a_repository_root() -> None:
    record = _record()
    record["deployment_status"] = "public"
    record["claim_references"].append(
        {
            **record["claim_references"][0],
            "id": "public-deployment",
            "scope": "deployment",
            "claim_posture": "partial",
        },
    )

    assert (
        "deployment_status 'public' requires a repository root to verify assertion evidence"
        in validate_project_record(record)
    )


def test_markdown_audit_ignores_links_inside_code(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Example\n\n`[Inline](missing-inline.md)`\n\n"
        "```markdown\n[Fenced](missing-fenced.md)\n```\n",
        encoding="utf-8",
    )

    result = audit_repository(tmp_path)

    assert not any(
        finding["code"] == "broken-local-links" for finding in result["findings"]
    )


def test_markdown_audit_rejects_outside_symlink_content(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("[Secret](token-from-outside.txt)\n", encoding="utf-8")
    (repository / "README.md").symlink_to(outside)

    result = audit_repository(repository)

    assert result["has_readme"] is False
    assert result["markdown_files"] == 0
    assert "token-from-outside" not in json.dumps(result)


def test_malformed_absolute_markdown_url_is_a_finding(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Example\n\n[Link](http://[)\n", encoding="utf-8")

    result = audit_repository(tmp_path)

    assert any(
        finding["code"] == "broken-local-links" for finding in result["findings"]
    )


def test_builder_scans_python_except_for_exact_structural_labels() -> None:
    builder_path = (
        Path(__file__).parents[1] / "docs/audits/build_reader_mode_estate_audit.py"
    )
    tree = ast.parse(builder_path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "bare_slug_scan_payload"
    )
    namespace = {
        "INPUT_MANIFEST": Path("reader-mode-input-manifest.json"),
        "Path": Path,
        "SOURCE_FILES": {
            "personal": "personal.json",
            "ergon": "ergon.json",
        },
        "json": json,
        "nbformat": nbformat,
        "re": re,
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(builder_path), "exec"), namespace)

    payload = 'segment = "personal"\n# secretproject\nqueue = ["secretproject"]\n'
    scan_payload = namespace["bare_slug_scan_payload"](Path("builder.py"), payload)

    assert '"personal"' not in scan_payload
    assert "secretproject" in scan_payload


def test_committed_notebook_uses_pinned_inputs_and_explicit_integrity_gates() -> None:
    notebook_path = (
        Path(__file__).parents[1]
        / "docs/audits/2026-08-31-reader-mode-estate-audit.ipynb"
    )
    notebook = nbformat.read(notebook_path, as_version=4)
    code = "\n".join(
        cell.source for cell in notebook.cells if cell.cell_type == "code"
    )

    assert "pinned_input_manifest" in code
    assert "input_manifest = pinned_input_manifest" in code
    assert "input_manifest = {" not in code
    assert "assert " not in code


def test_lifecycle_assertion_fact_must_match_the_project_state(tmp_path: Path) -> None:
    record = _write_git_fixture(tmp_path)
    record["deployment_status"] = "public"
    record["claim_references"].append(
        {
            **record["claim_references"][0],
            "id": "public-deployment",
            "scope": "deployment",
            "claim_posture": "partial",
        },
    )
    assertion_path = tmp_path / "docs/evidence/claims/validation.json"
    assertion = json.loads(assertion_path.read_text(encoding="utf-8"))
    assertion["fact"] = {"predicate": "deployment_status", "value": "public"}
    assertion_path.write_text(json.dumps(assertion), encoding="utf-8")

    assert validate_project_record(record, root=tmp_path) == []

    invalid_facts = [
        None,
        {"predicate": "capability", "value": "public"},
        {"predicate": "deployment_status", "value": "pilot"},
    ]
    for fact in invalid_facts:
        candidate = dict(assertion)
        if fact is None:
            candidate.pop("fact")
        else:
            candidate["fact"] = fact
        assertion_path.write_text(json.dumps(candidate), encoding="utf-8")

        assert any(
            "fact predicate/value exactly matches deployment_status" in error
            for error in validate_project_record(record, root=tmp_path)
        )


def test_non_lifecycle_assertions_do_not_require_a_deployment_fact(tmp_path: Path) -> None:
    record = _write_git_fixture(tmp_path)

    assert validate_project_record(record, root=tmp_path) == []


def test_verified_assertion_requires_nonempty_evidence(tmp_path: Path) -> None:
    record = _write_git_fixture(tmp_path)
    assertion_path = tmp_path / "docs/evidence/claims/validation.json"
    assertion = json.loads(assertion_path.read_text(encoding="utf-8"))
    assertion.pop("evidence_references")
    assertion_path.write_text(json.dumps(assertion), encoding="utf-8")

    assert any(
        "verified assertion requires a non-empty evidence_references list" in error
        for error in validate_project_record(record, root=tmp_path)
    )


def test_strict_git_binding_treats_pathspec_magic_as_a_literal(tmp_path: Path) -> None:
    record = _write_git_fixture(tmp_path)
    magic_name = ":(glob)**"
    magic_path = tmp_path / magic_name
    magic_path.write_text("untracked magic evidence\n", encoding="utf-8")
    assertion_path = tmp_path / "docs/evidence/claims/validation.json"
    assertion = json.loads(assertion_path.read_text(encoding="utf-8"))
    assertion["evidence_references"][0]["reference"] = magic_name
    assertion["evidence_references"][0]["body_hash"] = (
        "sha256:" + hashlib.sha256(magic_path.read_bytes()).hexdigest()
    )
    assertion_path.write_text(json.dumps(assertion), encoding="utf-8")
    _git(tmp_path, "add", "--", "docs/evidence/claims/validation.json")
    _git(tmp_path, "commit", "-m", "bind magic path fixture")

    assert any(
        "evidence is ignored or untracked" in error
        for error in validate_project_record(
            record,
            root=tmp_path,
            require_git_tracked_evidence=True,
        )
    )


@pytest.mark.parametrize(
    "uri",
    [
        "https://:443/path",
        "https://example.test:notaport/path",
        "https://example.test:99999/path",
    ],
)
def test_web_uris_require_a_valid_host_and_port(uri: str) -> None:
    record = _record()
    record["links"]["demo"] = uri

    assert "links.demo must be an absolute HTTP(S) URI" in validate_project_record(record)


def test_reference_style_markdown_links_are_audited(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Example\n\n[Guide][guide]\n\n[guide]: docs/missing.md\n",
        encoding="utf-8",
    )

    result = audit_repository(tmp_path)

    assert any(
        finding["code"] == "broken-local-links" for finding in result["findings"]
    )


def test_symlinked_project_record_is_not_read(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("# Repository\n", encoding="utf-8")
    outside = tmp_path / "outside.yml"
    outside.write_text(
        "documentation_class: SECRET_OUTSIDE_RECORD\n",
        encoding="utf-8",
    )
    (repository / "project-record.yml").symlink_to(outside)

    result = audit_repository(repository)

    assert result["has_project_record"] is False
    assert "SECRET_OUTSIDE_RECORD" not in json.dumps(result)


def test_workspace_discovery_keeps_repositories_named_like_generated_dirs(
    tmp_path: Path,
) -> None:
    expected = []
    for name in ("build", "vendor"):
        repository = tmp_path / name
        (repository / ".git").mkdir(parents=True)
        expected.append(repository.resolve())

    from organvm_engine.documentation.audit import discover_repositories

    assert discover_repositories(tmp_path) == expected


def test_builder_rejects_explicit_invalid_visibility() -> None:
    builder_path = (
        Path(__file__).parents[1] / "docs/audits/build_reader_mode_estate_audit.py"
    )
    tree = ast.parse(builder_path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "source_visibility"
    )
    namespace: dict[str, object] = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(builder_path), "exec"), namespace)

    with pytest.raises(RuntimeError, match="invalid visibility"):
        namespace["source_visibility"](
            {"visibility": "internal", "metadata": {"public": True}},
            source="fixture",
            index=0,
        )
