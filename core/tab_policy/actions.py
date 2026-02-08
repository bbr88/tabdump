"""Shared action semantics for postprocess and renderer stages."""

from __future__ import annotations


# Postprocess emits this action vocabulary today.
POSTPROCESS_ACTIONS = {
    "read",
    "watch",
    "reference",
    "build",
    "triage",
    "ignore",
    "deep_work",
}

# Renderer historically used a different vocabulary; keep aliases for compatibility.
LEGACY_ACTION_ALIASES = {
    "implement": "build",
    "debug": "triage",
    "decide": "reference",
    "learn": "read",
    "explore": "read",
    "skim": "ignore",
    "entertain": "watch",
    "relax": "watch",
    "ephemeral": "ignore",
}


def canonical_action(action: str) -> str:
    value = str(action or "").strip().lower()
    if not value:
        return ""
    return LEGACY_ACTION_ALIASES.get(value, value)


def action_priority_weight(action: str) -> int:
    """Map canonical action to renderer high-priority score adjustment."""
    normalized = canonical_action(action)
    if normalized in {"build", "deep_work"}:
        return 2
    if normalized in {"reference", "read", "triage"}:
        return 1
    if normalized == "watch":
        return -1
    if normalized == "ignore":
        return -3
    return 0
