"""Tests for the Archivist primitive."""

from organvm_engine.primitives.archivist import Archivist, ArchivistStore
from organvm_engine.primitives.types import (
    ExecutionMode,
    Frame,
    FrameType,
    InstitutionalContext,
    PrincipalPosition,
)


def test_archivist_capture(tmp_path):
    store = ArchivistStore(base_path=tmp_path)
    archivist = Archivist(store=store)

    context = InstitutionalContext(
        situation="Captured a decision",
        data={
            "mode": "capture",
            "category": "decision",
            "summary": "Decided to pursue legal remedy for lease dispute",
            "tags": ["legal", "housing"],
        },
    )
    result = archivist.invoke(context, Frame(FrameType.OPERATIONAL), PrincipalPosition())

    assert result.confidence == 1.0
    assert result.execution_mode == ExecutionMode.PROTOCOL_STRUCTURED
    assert result.output["category"] == "decision"
    assert "MEM-" in result.output["record_id"]


def test_archivist_retrieve(tmp_path):
    store = ArchivistStore(base_path=tmp_path)
    archivist = Archivist(store=store)

    # Capture first
    cap_ctx = InstitutionalContext(
        data={
            "mode": "capture",
            "category": "precedent",
            "summary": "Previous lease negotiation resulted in 6-month extension",
            "tags": ["housing", "negotiation"],
        },
    )
    archivist.invoke(cap_ctx, Frame(FrameType.OPERATIONAL), PrincipalPosition())

    # Retrieve
    ret_ctx = InstitutionalContext(
        data={
            "mode": "retrieve",
            "search_tags": ["housing"],
        },
    )
    result = archivist.invoke(ret_ctx, Frame(FrameType.OPERATIONAL), PrincipalPosition())

    assert len(result.output) == 1
    assert "lease" in result.output[0]["summary"].lower()


def test_archivist_retrieve_empty(tmp_path):
    store = ArchivistStore(base_path=tmp_path)
    archivist = Archivist(store=store)

    context = InstitutionalContext(
        data={"mode": "retrieve", "search_text": "nonexistent"},
    )
    result = archivist.invoke(context, Frame(FrameType.OPERATIONAL), PrincipalPosition())

    assert result.output == []
    assert result.confidence < 0.5


def test_archivist_text_search(tmp_path):
    store = ArchivistStore(base_path=tmp_path)
    archivist = Archivist(store=store)

    # Capture
    for summary in ["Billing dispute resolved", "Legal filing completed", "Billing overcharge"]:
        cap_ctx = InstitutionalContext(
            data={"mode": "capture", "summary": summary, "category": "outcome"},
        )
        archivist.invoke(cap_ctx, Frame(FrameType.OPERATIONAL), PrincipalPosition())

    # Search for "billing"
    ret_ctx = InstitutionalContext(
        data={"mode": "retrieve", "search_text": "billing"},
    )
    result = archivist.invoke(ret_ctx, Frame(FrameType.OPERATIONAL), PrincipalPosition())

    assert len(result.output) == 2
