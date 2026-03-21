"""Tests for organvm_engine.debt — DEBT header detection and tracking."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from organvm_engine.debt.scanner import (
    _parse_debt_line,
    debt_stats,
    scan_directory,
    scan_file,
    scan_files,
)

# ---------------------------------------------------------------------------
# _parse_debt_line — pattern matching
# ---------------------------------------------------------------------------


class TestParseDebtLine:
    """Unit tests for the line-level parser."""

    def test_pre_spec_pattern(self):
        line = "# DEBT: pre-SPEC-001 inline workaround for registry loader"
        item = _parse_debt_line(line, "foo.py", 10)
        assert item is not None
        assert item.spec == "SPEC-001"
        assert item.kind == "pre-spec"
        assert "inline workaround" in item.description
        assert item.line == 10
        assert item.file == "foo.py"

    def test_parenthesized_spec_pattern(self):
        line = "# DEBT(SPEC-042): temporary bypass of governance check"
        item = _parse_debt_line(line, "bar.py", 5)
        assert item is not None
        assert item.spec == "SPEC-042"
        assert item.kind == "spec-ref"
        assert "temporary bypass" in item.description

    def test_parenthesized_spec_with_spaces(self):
        line = "#  DEBT ( SPEC-099 ) :  padded description"
        item = _parse_debt_line(line, "baz.py", 1)
        assert item is not None
        assert item.spec == "SPEC-099"
        assert item.kind == "spec-ref"

    def test_bare_debt_marker(self):
        line = "# DEBT: untracked hotfix for CI pipeline"
        item = _parse_debt_line(line, "fix.py", 99)
        assert item is not None
        assert item.spec == ""
        assert item.kind == "untracked"
        assert "untracked hotfix" in item.description

    def test_non_debt_comment_returns_none(self):
        line = "# This is a regular comment"
        assert _parse_debt_line(line, "x.py", 1) is None

    def test_code_line_returns_none(self):
        line = "x = DEBT + 1"
        assert _parse_debt_line(line, "x.py", 1) is None

    def test_empty_line_returns_none(self):
        assert _parse_debt_line("", "x.py", 1) is None

    def test_whitespace_only_returns_none(self):
        assert _parse_debt_line("   ", "x.py", 1) is None

    def test_indented_debt_marker(self):
        line = "    # DEBT: pre-SPEC-005 indented in function body"
        item = _parse_debt_line(line, "mod.py", 42)
        assert item is not None
        assert item.spec == "SPEC-005"
        assert item.kind == "pre-spec"

    def test_three_digit_spec_number(self):
        line = "# DEBT: pre-SPEC-123 three digit spec ref"
        item = _parse_debt_line(line, "a.py", 1)
        assert item is not None
        assert item.spec == "SPEC-123"

    def test_bare_debt_with_spec_in_description_is_untracked(self):
        """A bare DEBT without the pre- prefix is untracked even if SPEC appears in text."""
        line = "# DEBT: need to reconcile with SPEC-010 later"
        item = _parse_debt_line(line, "a.py", 1)
        assert item is not None
        assert item.kind == "untracked"
        assert item.spec == ""


# ---------------------------------------------------------------------------
# scan_file — file-level scanning
# ---------------------------------------------------------------------------


class TestScanFile:
    """Tests for scanning a single file."""

    def test_scan_nonexistent_file(self):
        items = scan_file(Path("/nonexistent/file.py"))
        assert items == []

    def test_scan_file_with_no_debt(self, tmp_path):
        f = tmp_path / "clean.py"
        f.write_text("# A regular comment\nx = 1\n")
        assert scan_file(f) == []

    def test_scan_file_with_single_debt(self, tmp_path):
        f = tmp_path / "single.py"
        f.write_text(dedent("""\
            import os
            # DEBT: pre-SPEC-001 workaround for missing config
            def load():
                pass
        """))
        items = scan_file(f)
        assert len(items) == 1
        assert items[0].spec == "SPEC-001"
        assert items[0].line == 2

    def test_scan_file_with_multiple_debts(self, tmp_path):
        f = tmp_path / "multi.py"
        f.write_text(dedent("""\
            # DEBT: pre-SPEC-001 first debt
            x = 1
            # DEBT(SPEC-002): second debt
            y = 2
            # DEBT: untracked third debt
        """))
        items = scan_file(f)
        assert len(items) == 3
        assert items[0].kind == "pre-spec"
        assert items[1].kind == "spec-ref"
        assert items[2].kind == "untracked"

    def test_scan_file_preserves_line_numbers(self, tmp_path):
        f = tmp_path / "lines.py"
        f.write_text(dedent("""\
            line1 = 1
            line2 = 2
            # DEBT: pre-SPEC-010 on line 3
            line4 = 4
            line5 = 5
            # DEBT(SPEC-020): on line 6
        """))
        items = scan_file(f)
        assert items[0].line == 3
        assert items[1].line == 6


# ---------------------------------------------------------------------------
# scan_files — multi-file scanning
# ---------------------------------------------------------------------------


class TestScanFiles:
    """Tests for scanning multiple files."""

    def test_scan_empty_list(self):
        assert scan_files([]) == []

    def test_scan_multiple_files(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("# DEBT: pre-SPEC-001 debt in a\n")
        f2.write_text("# DEBT: pre-SPEC-002 debt in b\n")
        items = scan_files([f1, f2])
        assert len(items) == 2
        specs = {i.spec for i in items}
        assert specs == {"SPEC-001", "SPEC-002"}


# ---------------------------------------------------------------------------
# scan_directory — recursive directory scanning
# ---------------------------------------------------------------------------


class TestScanDirectory:
    """Tests for recursive directory scanning."""

    def test_scan_nonexistent_dir(self):
        assert scan_directory(Path("/nonexistent/dir")) == []

    def test_scan_directory_finds_python_files(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("# DEBT: pre-SPEC-001 top-level debt\n")
        sub = src / "sub"
        sub.mkdir()
        (sub / "helper.py").write_text("# DEBT(SPEC-002): nested debt\n")
        items = scan_directory(src)
        assert len(items) == 2

    def test_scan_directory_skips_non_python(self, tmp_path):
        (tmp_path / "readme.md").write_text("# DEBT: not python\n")
        (tmp_path / "code.py").write_text("# DEBT: pre-SPEC-001 python debt\n")
        items = scan_directory(tmp_path)
        assert len(items) == 1
        assert items[0].spec == "SPEC-001"

    def test_scan_directory_skips_pycache(self, tmp_path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "cached.py").write_text("# DEBT: pre-SPEC-001 should be skipped\n")
        (tmp_path / "real.py").write_text("# DEBT: pre-SPEC-002 real debt\n")
        items = scan_directory(tmp_path)
        assert len(items) == 1
        assert items[0].spec == "SPEC-002"


# ---------------------------------------------------------------------------
# debt_stats — summary statistics
# ---------------------------------------------------------------------------


class TestDebtStats:
    """Tests for the debt_stats aggregation function."""

    def test_empty_list(self):
        stats = debt_stats([])
        assert stats["total"] == 0
        assert stats["untracked_count"] == 0
        assert stats["specs_referenced"] == []

    def test_stats_counts(self, tmp_path):
        f = tmp_path / "mixed.py"
        f.write_text(dedent("""\
            # DEBT: pre-SPEC-001 first
            # DEBT(SPEC-002): second
            # DEBT: untracked third
            # DEBT: pre-SPEC-001 another ref to spec-001
        """))
        items = scan_file(f)
        stats = debt_stats(items)
        assert stats["total"] == 4
        assert stats["by_kind"]["pre-spec"] == 2
        assert stats["by_kind"]["spec-ref"] == 1
        assert stats["by_kind"]["untracked"] == 1
        assert stats["untracked_count"] == 1

    def test_stats_spec_references(self, tmp_path):
        f = tmp_path / "specs.py"
        f.write_text(dedent("""\
            # DEBT: pre-SPEC-001 first ref
            # DEBT(SPEC-002): second ref
            # DEBT: pre-SPEC-001 duplicate ref
        """))
        items = scan_file(f)
        stats = debt_stats(items)
        assert stats["specs_referenced"] == ["SPEC-001", "SPEC-002"]
        assert stats["by_spec"]["SPEC-001"] == 2
        assert stats["by_spec"]["SPEC-002"] == 1

    def test_stats_by_file(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("# DEBT: pre-SPEC-001 one\n# DEBT: pre-SPEC-002 two\n")
        f2.write_text("# DEBT(SPEC-003): three\n")
        items = scan_files([f1, f2])
        stats = debt_stats(items)
        assert len(stats["by_file"]) == 2
        assert stats["by_file"][str(f1)] == 2
        assert stats["by_file"][str(f2)] == 1


# ---------------------------------------------------------------------------
# JSON output — integration-level test via CLI handler
# ---------------------------------------------------------------------------


class TestDebtJSON:
    """Test that debt items serialize to JSON correctly."""

    def test_debt_item_fields(self, tmp_path):
        f = tmp_path / "sample.py"
        f.write_text("# DEBT: pre-SPEC-007 the quick brown fox\n")
        items = scan_file(f)
        assert len(items) == 1
        item = items[0]
        assert item.file == str(f)
        assert item.line == 1
        assert item.spec == "SPEC-007"
        assert item.kind == "pre-spec"
        assert item.description == "the quick brown fox"

        # Verify dataclass serialization works
        import dataclasses

        d = dataclasses.asdict(item)
        assert d["spec"] == "SPEC-007"
        assert d["kind"] == "pre-spec"
        assert d["line"] == 1
