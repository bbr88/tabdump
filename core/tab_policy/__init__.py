"""Shared tab classification semantics used across pipeline stages."""

from .actions import canonical_action, action_priority_weight
from .matching import host_matches_base

__all__ = ["canonical_action", "action_priority_weight", "host_matches_base"]
