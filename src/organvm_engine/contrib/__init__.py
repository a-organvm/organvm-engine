"""Contribution engine — outbound contribution tracking and backflow routing.

Discovers contrib repos (seed.yaml tier:contrib), checks upstream PR status,
classifies knowledge types, and routes backflow signals to appropriate organs.

Thesis: one contribution, seven returns. Each outbound PR generates typed
knowledge that flows back into the system through organ-specific channels.
See essay-8 (The Recursive Proof) for the theoretical foundation.
"""

from organvm_engine.contrib.discover import discover_contrib_repos
from organvm_engine.contrib.status import check_pr_status, ContribStatus

__all__ = ["discover_contrib_repos", "check_pr_status", "ContribStatus"]
