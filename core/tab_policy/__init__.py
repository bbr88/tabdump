"""Shared tab classification semantics used across pipeline stages."""

from .actions import canonical_action, action_priority_weight
from .matching import host_matches_base
from .text import slugify_kebab
from .taxonomy import (
    AUTH_PATH_HINTS,
    BLOG_PATH_HINTS,
    CODE_HOST_DOMAINS,
    DOC_PATH_HINTS,
    POSTPROCESS_ACTION_ORDER,
    POSTPROCESS_ACTIONS,
    POSTPROCESS_KIND_ORDER,
    POSTPROCESS_KINDS,
    RENDERER_ALLOWED_KINDS,
    MUSIC_DOMAINS,
    SENSITIVE_HOSTS,
    SENSITIVE_QUERY_KEYS,
    TOOL_DOMAINS,
    VIDEO_DOMAINS,
)

__all__ = [
    "canonical_action",
    "action_priority_weight",
    "host_matches_base",
    "slugify_kebab",
    "POSTPROCESS_ACTION_ORDER",
    "POSTPROCESS_ACTIONS",
    "POSTPROCESS_KIND_ORDER",
    "POSTPROCESS_KINDS",
    "RENDERER_ALLOWED_KINDS",
    "CODE_HOST_DOMAINS",
    "VIDEO_DOMAINS",
    "MUSIC_DOMAINS",
    "DOC_PATH_HINTS",
    "BLOG_PATH_HINTS",
    "TOOL_DOMAINS",
    "SENSITIVE_HOSTS",
    "AUTH_PATH_HINTS",
    "SENSITIVE_QUERY_KEYS",
]
