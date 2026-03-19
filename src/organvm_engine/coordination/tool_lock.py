"""Tool checkout line — prevent concurrent agents from closing all the streets.

Implements: SPEC-014, RSRC-003 (resource constraints and tool checkout)

Before running a heavy command (pytest, npm test, build), an agent checks out
the tool. If another agent already has it checked out, the requesting agent
must wait. Light commands (git status, ls) can run concurrently.

Uses the same JSONL event log as claims.py (append-only, shared state).
Tool checkouts auto-expire after 5 minutes to prevent deadlocks.

Concurrency limits by command weight:
    heavy  (pytest, npm test, pip install, build): 1 at a time
    medium (ruff check, git commit, npm run lint): 2 at a time
    light  (git status, ls, echo, cat):            unlimited
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

# Auto-expiry: commands shouldn't take longer than 5 minutes.
# If they do, the checkout is stale and can be reclaimed.
CHECKOUT_TTL_SECONDS = 5 * 60

# Concurrency limits per weight class.
TOOL_LIMITS = {"heavy": 1, "medium": 2, "light": 0}  # 0 = unlimited

# Command classification patterns.
_HEAVY_PATTERNS = [
    r"\bpytest\b",
    r"\bnpm\s+(test|run\s+build)\b",
    r"\bpip\s+install\b",
    r"\bcargo\s+(build|test)\b",
    r"\bmake\b",
    r"\bgo\s+(build|test)\b",
    r"\bnpx\s+vitest\b",
    r"\bturbo\b",
]

_MEDIUM_PATTERNS = [
    r"\bruff\s+check\b",
    r"\bgit\s+commit\b",
    r"\bgit\s+push\b",
    r"\bnpm\s+run\s+lint\b",
    r"\bpyright\b",
    r"\btsc\b",
    r"\bgit\s+rebase\b",
]


def classify_command(command: str) -> str:
    """Classify a shell command as heavy, medium, or light."""
    for pattern in _HEAVY_PATTERNS:
        if re.search(pattern, command):
            return "heavy"
    for pattern in _MEDIUM_PATTERNS:
        if re.search(pattern, command):
            return "medium"
    return "light"


@dataclass
class ToolCheckout:
    """An active tool checkout by an agent."""

    checkout_id: str
    handle: str  # agent handle (e.g. "claude-forge")
    tool: str  # "bash", "write", etc.
    command_hint: str
    weight: str  # heavy, medium, light
    timestamp: float
    released: bool = False
    release_timestamp: float = 0.0

    @property
    def is_expired(self) -> bool:
        return time.time() > (self.timestamp + CHECKOUT_TTL_SECONDS)

    @property
    def is_active(self) -> bool:
        return not self.released and not self.is_expired

    @property
    def age_seconds(self) -> int:
        return int(time.time() - self.timestamp)


def _read_tool_events() -> list[dict]:
    """Read tool checkout/checkin events from the claims file."""
    from organvm_engine.coordination.claims import _read_events

    return [
        e for e in _read_events()
        if e.get("event_type", "").startswith("tool.")
    ]


def _build_active_checkouts(events: list[dict]) -> list[ToolCheckout]:
    """Build list of active tool checkouts from event log."""
    checkouts: dict[str, ToolCheckout] = {}

    for event in events:
        etype = event.get("event_type")
        if etype == "tool.checkout":
            co = ToolCheckout(
                checkout_id=event.get("checkout_id", ""),
                handle=event.get("handle", ""),
                tool=event.get("tool", ""),
                command_hint=event.get("command_hint", ""),
                weight=event.get("weight", "medium"),
                timestamp=event.get("timestamp", 0),
            )
            checkouts[co.checkout_id] = co
        elif etype == "tool.checkin":
            cid = event.get("checkout_id", "")
            if cid in checkouts:
                checkouts[cid].released = True
                checkouts[cid].release_timestamp = event.get(
                    "timestamp", time.time(),
                )

    return [c for c in checkouts.values() if c.is_active]


def active_checkouts() -> list[ToolCheckout]:
    """Return all currently active tool checkouts."""
    events = _read_tool_events()
    return _build_active_checkouts(events)


def tool_checkout(
    handle: str,
    tool: str = "bash",
    command_hint: str = "",
    weight: str | None = None,
) -> dict[str, Any]:
    """Check out a tool before running a command.

    If the tool lane is clear, the checkout is granted. If another agent
    already holds the lane, returns a wait advisory with queue details.

    Args:
        handle: Agent handle from punch_in (e.g. "claude-forge").
        tool: Tool name (usually "bash").
        command_hint: The command about to be run (used for classification
            and display to other agents).
        weight: Override weight classification. If None, auto-classified
            from command_hint.

    Returns:
        {cleared: True, checkout_id: "..."} if the lane is clear.
        {wait: True, queue: [...], suggestion: "..."} if blocked.
    """
    from organvm_engine.coordination.claims import _append_event

    if weight is None:
        weight = classify_command(command_hint)

    # Light commands always pass through — no checkout needed
    limit = TOOL_LIMITS.get(weight, 0)
    if limit == 0:
        return {
            "cleared": True,
            "checkout_id": "",
            "weight": weight,
            "note": "Light command — no checkout needed.",
        }

    # Check current lane occupancy
    current = active_checkouts()
    same_weight = [c for c in current if c.weight == weight and c.tool == tool]

    if len(same_weight) >= limit:
        # Lane is full — advise waiting
        queue = [
            {
                "holder": c.handle,
                "command": c.command_hint,
                "weight": c.weight,
                "running_for_seconds": c.age_seconds,
            }
            for c in same_weight
        ]
        return {
            "cleared": False,
            "wait": True,
            "queue": queue,
            "queue_length": len(queue),
            "suggestion": (
                f"The {weight} lane is at capacity ({len(same_weight)}/{limit}). "
                "Wait for a checkin or expiry before running."
            ),
        }

    # Lane is clear — grant checkout
    now = time.time()
    raw = f"tool:{handle}:{tool}:{now}"
    checkout_id = hashlib.sha256(raw.encode()).hexdigest()[:10]

    event = {
        "event_type": "tool.checkout",
        "checkout_id": checkout_id,
        "handle": handle,
        "tool": tool,
        "command_hint": command_hint,
        "weight": weight,
        "timestamp": now,
        "iso_time": datetime.now(timezone.utc).isoformat(),
    }
    _append_event(event)

    return {
        "cleared": True,
        "checkout_id": checkout_id,
        "handle": handle,
        "weight": weight,
        "lane_occupancy": f"{len(same_weight) + 1}/{limit}",
    }


def tool_checkin(checkout_id: str) -> dict[str, Any]:
    """Check in a tool after a command completes.

    Args:
        checkout_id: The checkout_id from tool_checkout.

    Returns:
        {released: True} on success.
    """
    from organvm_engine.coordination.claims import _append_event

    if not checkout_id:
        return {"released": True, "note": "No checkout to release (was light)."}

    current = active_checkouts()
    found = None
    for c in current:
        if c.checkout_id == checkout_id:
            found = c
            break

    if found is None:
        return {"released": True, "note": "Checkout already expired or released."}

    event = {
        "event_type": "tool.checkin",
        "checkout_id": checkout_id,
        "handle": found.handle,
        "tool": found.tool,
        "timestamp": time.time(),
        "iso_time": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": found.age_seconds,
    }
    _append_event(event)

    return {
        "released": True,
        "checkout_id": checkout_id,
        "handle": found.handle,
        "duration_seconds": found.age_seconds,
    }


def tool_queue() -> dict[str, Any]:
    """View the current tool checkout queue — who's running what."""
    current = active_checkouts()

    by_weight: dict[str, list[dict]] = {"heavy": [], "medium": [], "light": []}
    for c in current:
        by_weight.setdefault(c.weight, []).append({
            "holder": c.handle,
            "tool": c.tool,
            "command": c.command_hint,
            "running_for_seconds": c.age_seconds,
            "expires_in_seconds": max(
                0, CHECKOUT_TTL_SECONDS - c.age_seconds,
            ),
        })

    return {
        "active_checkouts": len(current),
        "heavy_lane": {
            "occupied": len(by_weight["heavy"]),
            "limit": TOOL_LIMITS["heavy"],
            "checkouts": by_weight["heavy"],
        },
        "medium_lane": {
            "occupied": len(by_weight["medium"]),
            "limit": TOOL_LIMITS["medium"],
            "checkouts": by_weight["medium"],
        },
        "light_note": "Light commands do not require checkout.",
    }
