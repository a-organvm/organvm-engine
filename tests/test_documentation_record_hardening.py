"""Adversarial regressions for canonical documentation records."""

from __future__ import annotations

import hashlib
import json
import subprocess
from argparse import Namespace
from pathlib import Path

import pytest

from organvm_engine.cli.docs import cmd_docs_validate
from organvm_engine.documentation.record import validate_project_record


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
