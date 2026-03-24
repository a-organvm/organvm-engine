"""Tests for named functions CLI commands and organ_config bridge."""

from __future__ import annotations

import argparse
import json

from organvm_engine.cli.functions import cmd_functions_list, cmd_functions_resolve
from organvm_engine.organ_config import FUNCTION_DIR_MAP, resolve_function

# ---------------------------------------------------------------------------
# resolve_function (organ_config bridge)
# ---------------------------------------------------------------------------


class TestResolveFunction:
    """Test resolve_function in organ_config."""

    def test_direct_function_name(self) -> None:
        assert resolve_function("theoria") == "theoria"

    def test_display_name(self) -> None:
        assert resolve_function("Theoria") == "theoria"

    def test_cli_short_key(self) -> None:
        assert resolve_function("I") == "theoria"

    def test_registry_key_organ(self) -> None:
        assert resolve_function("ORGAN-I") == "theoria"

    def test_registry_key_meta(self) -> None:
        assert resolve_function("META-ORGANVM") == "meta"

    def test_meta_short_key(self) -> None:
        assert resolve_function("META") == "meta"

    def test_genome_display_name(self) -> None:
        assert resolve_function("Genome") == "meta"

    def test_all_organs_resolve(self) -> None:
        expected = {
            "I": "theoria",
            "II": "poiesis",
            "III": "ergon",
            "IV": "taxis",
            "V": "logos",
            "VI": "koinonia",
            "VII": "kerygma",
            "META": "meta",
        }
        for key, fn in expected.items():
            assert resolve_function(key) == fn, f"{key} should resolve to {fn}"

    def test_unknown_returns_none(self) -> None:
        assert resolve_function("NONEXISTENT") is None

    def test_case_insensitive_function_name(self) -> None:
        assert resolve_function("THEORIA") == "theoria"
        assert resolve_function("Ergon") == "ergon"

    def test_mneme_resolves(self) -> None:
        assert resolve_function("mneme") == "mneme"
        assert resolve_function("Mneme") == "mneme"


# ---------------------------------------------------------------------------
# FUNCTION_DIR_MAP
# ---------------------------------------------------------------------------


class TestFunctionDirMap:
    """Test FUNCTION_DIR_MAP completeness."""

    def test_all_functions_have_dirs(self) -> None:
        from organvm_engine.governance.named_functions import VALID_FUNCTION_NAMES

        for fn in VALID_FUNCTION_NAMES:
            assert fn in FUNCTION_DIR_MAP, f"Missing FUNCTION_DIR_MAP entry for {fn}"

    def test_theoria_dir(self) -> None:
        assert FUNCTION_DIR_MAP["theoria"] == "organvm-i-theoria"

    def test_meta_dir(self) -> None:
        assert FUNCTION_DIR_MAP["meta"] == "meta-organvm"


# ---------------------------------------------------------------------------
# cmd_functions_list
# ---------------------------------------------------------------------------


class TestCmdFunctionsList:
    """Test the functions list CLI command."""

    def test_returns_zero(self, capsys: object) -> None:
        args = argparse.Namespace(json=False)
        result = cmd_functions_list(args)
        assert result == 0

    def test_lists_all_nine_functions(self, capsys: object) -> None:
        args = argparse.Namespace(json=False)
        cmd_functions_list(args)
        captured = capsys.readouterr()  # type: ignore[union-attr]
        # All 9 function names should appear
        for name in ("theoria", "poiesis", "ergon", "taxis", "logos",
                     "koinonia", "kerygma", "mneme", "meta"):
            assert name in captured.out, f"{name} missing from output"

    def test_genome_marker(self, capsys: object) -> None:
        args = argparse.Namespace(json=False)
        cmd_functions_list(args)
        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "[GENOME]" in captured.out

    def test_json_output(self, capsys: object) -> None:
        args = argparse.Namespace(json=True)
        result = cmd_functions_list(args)
        assert result == 0
        captured = capsys.readouterr()  # type: ignore[union-attr]
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) == 9
        keys = {f["key"] for f in data}
        assert "theoria" in keys
        assert "meta" in keys


# ---------------------------------------------------------------------------
# cmd_functions_resolve
# ---------------------------------------------------------------------------


class TestCmdFunctionsResolve:
    """Test the functions resolve CLI command."""

    def test_resolve_organ_i(self, capsys: object) -> None:
        args = argparse.Namespace(key="ORGAN-I", json=False)
        result = cmd_functions_resolve(args)
        assert result == 0
        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "theoria" in captured.out

    def test_resolve_direct_name(self, capsys: object) -> None:
        args = argparse.Namespace(key="theoria", json=False)
        result = cmd_functions_resolve(args)
        assert result == 0
        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "theoria" in captured.out

    def test_resolve_meta_organvm(self, capsys: object) -> None:
        args = argparse.Namespace(key="META-ORGANVM", json=False)
        result = cmd_functions_resolve(args)
        assert result == 0
        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "meta" in captured.out

    def test_resolve_unknown_fails(self, capsys: object) -> None:
        args = argparse.Namespace(key="NONEXISTENT", json=False)
        result = cmd_functions_resolve(args)
        assert result == 1
        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "Unknown" in captured.out

    def test_resolve_json_output(self, capsys: object) -> None:
        args = argparse.Namespace(key="theoria", json=True)
        result = cmd_functions_resolve(args)
        assert result == 0
        captured = capsys.readouterr()  # type: ignore[union-attr]
        data = json.loads(captured.out)
        assert data["key"] == "theoria"
        assert "display_name" in data
