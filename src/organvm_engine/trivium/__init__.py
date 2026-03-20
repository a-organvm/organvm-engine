"""Trivium — Dialectica Universalis.

The structural isomorphism of thought, truth, and computation. Every organ
in ORGANVM speaks a distinct dialect of a single underlying universal logic.
This module detects, classifies, and renders those structural correspondences.

The thesis: Language, mathematics, and algorithms are not different disciplines;
they are merely different dialects of the same underlying universal logic.

MCP tool signatures (implementation deferred to organvm-mcp-server):
    organvm_trivium_dialects — list all eight dialects with profiles
    organvm_trivium_matrix   — full 28-pair translation evidence matrix
    organvm_trivium_scan     — scan structural correspondences between two organs
    organvm_trivium_status   — trivium subsystem health
"""

from organvm_engine.trivium.dialects import (
    Dialect,
    DialectProfile,
    all_dialects,
    classical_parallel,
    dialect_for_organ,
    dialect_profile,
    organ_for_dialect,
)

__all__ = [
    "Dialect",
    "DialectProfile",
    "all_dialects",
    "classical_parallel",
    "dialect_for_organ",
    "dialect_profile",
    "organ_for_dialect",
]
