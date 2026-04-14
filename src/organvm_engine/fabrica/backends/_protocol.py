"""Protocol definition for dispatch backends.

Every backend module must expose ``dispatch()`` and ``check_status()``
at module level. This protocol formalises that contract so
``get_backend()`` can return a typed handle.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from organvm_engine.fabrica.models import DispatchRecord


@runtime_checkable
class BackendProtocol(Protocol):
    """Contract every backend module must satisfy."""

    BACKEND_NAME: str

    def dispatch(
        self,
        task_id: str,
        intent_id: str,
        *,
        repo: str,
        title: str,
        body: str,
        labels: list[str] | None = None,
        branch: str | None = None,
        dry_run: bool = True,
    ) -> DispatchRecord:
        """Create a work item and return a DispatchRecord."""
        ...

    def check_status(self, record: DispatchRecord) -> DispatchRecord:
        """Re-fetch the status of a previously dispatched record.

        Returns a new DispatchRecord with updated ``status``,
        ``returned_at``, and ``pr_url`` fields.
        """
        ...
