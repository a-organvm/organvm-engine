"""DEBT header detection and tracking.

Scans Python source files for emergency maintenance debt markers per the
v3 methodology Emergency Maintenance Protocol. Code changes outside the
RFIV cycle must be committed with ``# DEBT: pre-SPEC-XXX`` headers.

Supported patterns::

    # DEBT: pre-SPEC-001 inline workaround for registry loader
    # DEBT(SPEC-042): temporary bypass of governance check
    # DEBT: untracked hotfix for CI pipeline

Public API::

    from organvm_engine.debt import DebtItem, scan_files, scan_workspace

    items = scan_files([Path("src/foo.py")])
    items = scan_workspace(Path("~/Workspace"), organ="META")
"""

from organvm_engine.debt.scanner import (
    DebtItem,
    debt_stats,
    scan_directory,
    scan_files,
    scan_workspace,
)

__all__ = [
    "DebtItem",
    "debt_stats",
    "scan_directory",
    "scan_files",
    "scan_workspace",
]
