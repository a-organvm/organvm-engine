"""Tests for the trivium CLI command group."""

import argparse
from pathlib import Path

from organvm_engine.cli.trivium import (
    cmd_trivium_dialects,
    cmd_trivium_matrix,
    cmd_trivium_scan,
    cmd_trivium_status,
    cmd_trivium_synthesize,
)

FIXTURE = str(Path(__file__).parent / "fixtures" / "registry-trivium.json")


def test_cmd_trivium_dialects():
    args = argparse.Namespace(json=False)
    assert cmd_trivium_dialects(args) == 0


def test_cmd_trivium_dialects_json():
    args = argparse.Namespace(json=True)
    assert cmd_trivium_dialects(args) == 0


def test_cmd_trivium_matrix():
    args = argparse.Namespace(json=False, organ=None, registry=FIXTURE)
    assert cmd_trivium_matrix(args) == 0


def test_cmd_trivium_matrix_json():
    args = argparse.Namespace(json=True, organ=None, registry=FIXTURE)
    assert cmd_trivium_matrix(args) == 0


def test_cmd_trivium_scan_pair():
    args = argparse.Namespace(
        organ_a="I", organ_b="III", all=False, json=False, registry=FIXTURE,
    )
    assert cmd_trivium_scan(args) == 0


def test_cmd_trivium_scan_all():
    args = argparse.Namespace(
        organ_a=None, organ_b=None, all=True, json=False, registry=FIXTURE,
    )
    assert cmd_trivium_scan(args) == 0


def test_cmd_trivium_scan_no_args():
    args = argparse.Namespace(
        organ_a=None, organ_b=None, all=False, json=False, registry=FIXTURE,
    )
    assert cmd_trivium_scan(args) == 1  # error


def test_cmd_trivium_synthesize_dry_run():
    args = argparse.Namespace(
        write=False, registry=FIXTURE, output_dir=None,
    )
    assert cmd_trivium_synthesize(args) == 0


def test_cmd_trivium_synthesize_write(tmp_path):
    args = argparse.Namespace(
        write=True, registry=FIXTURE, output_dir=str(tmp_path),
    )
    assert cmd_trivium_synthesize(args) == 0


def test_cmd_trivium_status():
    args = argparse.Namespace(json=False, registry=None)
    assert cmd_trivium_status(args) == 0


def test_cmd_trivium_status_json():
    args = argparse.Namespace(json=True, registry=None)
    assert cmd_trivium_status(args) == 0
