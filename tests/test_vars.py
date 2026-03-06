"""Tests for the variable binding system (metrics/vars.py)."""

import json

import pytest

from organvm_engine.metrics.vars import (
    VAR_PATTERN,
    Replacement,
    ResolutionResult,
    build_vars,
    load_vars,
    resolve_file,
    resolve_targets,
    resolve_targets_from_manifest,
    write_vars,
)


# --- build_vars ---


@pytest.fixture
def sample_metrics():
    return {
        "computed": {
            "total_repos": 103,
            "active_repos": 82,
            "archived_repos": 9,
            "total_organs": 8,
            "operational_organs": 8,
            "ci_workflows": 102,
            "dependency_edges": 156,
            "total_words_numeric": 404000,
            "total_words_short": "404K+",
            "published_essays": 48,
            "sprints_completed": 33,
            "code_files": 500,
            "test_files": 120,
            "repos_with_tests": 30,
        },
        "manual": {},
    }


@pytest.fixture
def sample_registry():
    return {
        "organs": {
            "ORGAN-I": {
                "name": "Theoria",
                "repositories": [{"name": f"repo-{i}"} for i in range(20)],
            },
            "ORGAN-III": {
                "name": "Ergon",
                "repositories": [{"name": f"repo-{i}"} for i in range(27)],
            },
            "META-ORGANVM": {
                "name": "Meta",
                "repositories": [{"name": f"repo-{i}"} for i in range(7)],
            },
        },
    }


def test_build_vars_core_counts(sample_metrics, sample_registry):
    v = build_vars(sample_metrics, sample_registry)
    assert v["total_repos"] == "103"
    assert v["active_repos"] == "82"
    assert v["archived_repos"] == "9"
    assert v["total_organs"] == "8"
    assert v["operational_organs"] == "8"
    assert v["ci_workflows"] == "102"
    assert v["dependency_edges"] == "156"


def test_build_vars_word_counts(sample_metrics, sample_registry):
    v = build_vars(sample_metrics, sample_registry)
    assert v["total_words_numeric"] == "404000"
    assert v["total_words_formatted"] == "404,000"
    assert v["total_words_short"] == "404K+"


def test_build_vars_word_counts_fallback_to_manual(sample_registry):
    metrics = {
        "computed": {"total_repos": 5},
        "manual": {
            "total_words_numeric": 300000,
            "total_words_short": "300K+",
        },
    }
    v = build_vars(metrics, sample_registry)
    assert v["total_words_numeric"] == "300000"
    assert v["total_words_short"] == "300K+"


def test_build_vars_per_organ(sample_metrics, sample_registry):
    v = build_vars(sample_metrics, sample_registry)
    assert v["organ_repos.ORGAN-I"] == "20"
    assert v["organ_repos.ORGAN-III"] == "27"
    assert v["organ_repos.META-ORGANVM"] == "7"
    assert v["organ_name.ORGAN-I"] == "Theoria"
    assert v["organ_name.ORGAN-III"] == "Ergon"


def test_build_vars_all_strings(sample_metrics, sample_registry):
    v = build_vars(sample_metrics, sample_registry)
    for key, val in v.items():
        assert isinstance(val, str), f"{key} should be string, got {type(val)}"


def test_build_vars_code_metrics(sample_metrics, sample_registry):
    v = build_vars(sample_metrics, sample_registry)
    assert v["code_files"] == "500"
    assert v["test_files"] == "120"
    assert v["repos_with_tests"] == "30"


# --- write_vars / load_vars ---


def test_write_and_load_vars(tmp_path, sample_metrics, sample_registry):
    v = build_vars(sample_metrics, sample_registry)
    out = tmp_path / "system-vars.json"
    write_vars(v, out)
    loaded = load_vars(out)
    assert loaded == v


def test_write_vars_sorted_keys(tmp_path):
    v = {"z_var": "1", "a_var": "2", "m_var": "3"}
    out = tmp_path / "vars.json"
    write_vars(v, out)
    raw = out.read_text()
    keys = [line.strip().split('"')[1] for line in raw.splitlines() if ":" in line]
    assert keys == sorted(keys)


# --- VAR_PATTERN ---


def test_var_pattern_matches_simple():
    text = "There are <!-- v:total_repos -->103<!-- /v --> repos"
    m = VAR_PATTERN.search(text)
    assert m is not None
    assert m.group(2) == "total_repos"


def test_var_pattern_matches_dotted():
    text = "<!-- v:organ_repos.ORGAN-I -->20<!-- /v -->"
    m = VAR_PATTERN.search(text)
    assert m is not None
    assert m.group(2) == "organ_repos.ORGAN-I"


def test_var_pattern_matches_multiline():
    text = "<!-- v:some_var -->line1\nline2<!-- /v -->"
    m = VAR_PATTERN.search(text)
    assert m is not None
    assert m.group(2) == "some_var"


def test_var_pattern_multiple_matches():
    text = "<!-- v:a -->1<!-- /v --> and <!-- v:b -->2<!-- /v -->"
    matches = VAR_PATTERN.findall(text)
    assert len(matches) == 2


# --- resolve_file ---


def test_resolve_file_replaces_value(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("We have <!-- v:total_repos -->99<!-- /v --> repositories.")
    variables = {"total_repos": "103"}

    replacements = resolve_file(f, variables)

    assert len(replacements) == 1
    assert replacements[0].key == "total_repos"
    assert replacements[0].old_value == "99"
    assert replacements[0].new_value == "103"
    assert "<!-- v:total_repos -->103<!-- /v -->" in f.read_text()


def test_resolve_file_preserves_unknown_key(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("<!-- v:unknown_var -->old<!-- /v -->")
    variables = {"total_repos": "103"}

    replacements = resolve_file(f, variables)

    assert len(replacements) == 1
    assert replacements[0].key == "unknown_var"
    assert replacements[0].old_value == replacements[0].new_value
    # File should be unchanged
    assert f.read_text() == "<!-- v:unknown_var -->old<!-- /v -->"


def test_resolve_file_handles_multiline(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("<!-- v:count -->line1\nline2<!-- /v -->")
    variables = {"count": "42"}

    replacements = resolve_file(f, variables)

    assert len(replacements) == 1
    assert replacements[0].new_value == "42"
    assert f.read_text() == "<!-- v:count -->42<!-- /v -->"


def test_resolve_file_dry_run(tmp_path):
    f = tmp_path / "test.md"
    original = "<!-- v:total_repos -->99<!-- /v -->"
    f.write_text(original)
    variables = {"total_repos": "103"}

    replacements = resolve_file(f, variables, dry_run=True)

    assert len(replacements) == 1
    assert replacements[0].new_value == "103"
    # File should NOT be changed in dry run
    assert f.read_text() == original


def test_resolve_file_multiple_vars(tmp_path):
    f = tmp_path / "test.md"
    f.write_text(
        "Repos: <!-- v:total_repos -->99<!-- /v -->, "
        "Organs: <!-- v:total_organs -->7<!-- /v -->"
    )
    variables = {"total_repos": "103", "total_organs": "8"}

    replacements = resolve_file(f, variables)

    assert len(replacements) == 2
    content = f.read_text()
    assert "<!-- v:total_repos -->103<!-- /v -->" in content
    assert "<!-- v:total_organs -->8<!-- /v -->" in content


def test_resolve_file_no_markers(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("No markers here, just text.")
    variables = {"total_repos": "103"}

    replacements = resolve_file(f, variables)
    assert replacements == []


def test_resolve_file_dotted_key(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("Organ I has <!-- v:organ_repos.ORGAN-I -->0<!-- /v --> repos.")
    variables = {"organ_repos.ORGAN-I": "20"}

    replacements = resolve_file(f, variables)

    assert len(replacements) == 1
    assert "<!-- v:organ_repos.ORGAN-I -->20<!-- /v -->" in f.read_text()


def test_resolve_file_value_unchanged(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("<!-- v:total_repos -->103<!-- /v -->")
    variables = {"total_repos": "103"}

    replacements = resolve_file(f, variables)

    assert len(replacements) == 1
    assert replacements[0].old_value == replacements[0].new_value


# --- resolve_targets ---


def test_resolve_targets_multiple_files(tmp_path):
    f1 = tmp_path / "a.md"
    f1.write_text("<!-- v:total_repos -->0<!-- /v -->")
    f2 = tmp_path / "b.md"
    f2.write_text("<!-- v:total_organs -->0<!-- /v -->")

    variables = {"total_repos": "103", "total_organs": "8"}
    result = resolve_targets(variables, [f1, f2])

    assert result.files_scanned == 2
    assert result.files_changed == 2
    assert result.total_replacements == 2


def test_resolve_targets_skips_missing_files(tmp_path):
    existing = tmp_path / "a.md"
    existing.write_text("<!-- v:total_repos -->0<!-- /v -->")
    missing = tmp_path / "does-not-exist.md"

    variables = {"total_repos": "103"}
    result = resolve_targets(variables, [existing, missing])

    assert result.files_scanned == 1
    assert result.total_replacements == 1


def test_resolve_targets_tracks_unknown_keys(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("<!-- v:mystery -->x<!-- /v -->")

    result = resolve_targets({}, [f])

    assert "mystery" in result.unknown_keys


# --- resolve_targets_from_manifest ---


def test_resolve_targets_from_manifest(tmp_path):
    # Create target files
    sub = tmp_path / "docs"
    sub.mkdir()
    (sub / "a.md").write_text("<!-- v:total_repos -->0<!-- /v -->")
    (sub / "b.md").write_text("<!-- v:total_organs -->0<!-- /v -->")
    (sub / "ignore.txt").write_text("not markdown")

    # Create manifest
    manifest = tmp_path / "vars-targets.yaml"
    manifest.write_text(
        f"targets:\n"
        f"  - root: \"{sub}\"\n"
        f"    files: [\"a.md\", \"b.md\"]\n"
    )

    variables = {"total_repos": "103", "total_organs": "8"}
    result = resolve_targets_from_manifest(variables, manifest)

    assert result.files_scanned == 2
    assert result.total_replacements == 2


def test_resolve_targets_from_manifest_with_globs(tmp_path):
    sub = tmp_path / "docs"
    sub.mkdir()
    (sub / "page1.md").write_text("<!-- v:total_repos -->0<!-- /v -->")
    (sub / "page2.md").write_text("<!-- v:total_repos -->0<!-- /v -->")

    manifest = tmp_path / "vars-targets.yaml"
    manifest.write_text(
        f"targets:\n"
        f"  - root: \"{sub}\"\n"
        f"    globs: [\"*.md\"]\n"
    )

    variables = {"total_repos": "103"}
    result = resolve_targets_from_manifest(variables, manifest)

    assert result.files_scanned == 2
    assert result.total_replacements == 2


# --- Round-trip test ---


def test_round_trip(tmp_path, sample_metrics, sample_registry):
    """Write markers, resolve, read back — values should match."""
    v = build_vars(sample_metrics, sample_registry)

    # Write a test file with markers
    f = tmp_path / "test.md"
    lines = [
        f"Total repos: <!-- v:total_repos -->PLACEHOLDER<!-- /v -->\n",
        f"Active: <!-- v:active_repos -->PLACEHOLDER<!-- /v -->\n",
        f"Words: <!-- v:total_words_short -->PLACEHOLDER<!-- /v -->\n",
        f"Organ I: <!-- v:organ_repos.ORGAN-I -->PLACEHOLDER<!-- /v -->\n",
    ]
    f.write_text("".join(lines))

    # Resolve
    resolve_file(f, v)

    # Verify
    content = f.read_text()
    assert "<!-- v:total_repos -->103<!-- /v -->" in content
    assert "<!-- v:active_repos -->82<!-- /v -->" in content
    assert "<!-- v:total_words_short -->404K+<!-- /v -->" in content
    assert "<!-- v:organ_repos.ORGAN-I -->20<!-- /v -->" in content

    # Second resolve should be idempotent
    replacements = resolve_file(f, v)
    assert all(r.old_value == r.new_value for r in replacements)
    assert f.read_text() == content
