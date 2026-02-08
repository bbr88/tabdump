"""TabDump Pretty Renderer — domain-first Markdown dashboard."""

from __future__ import annotations

from typing import Dict

from .buckets import _assign_buckets, _host_matches_base
from .config import DEFAULT_CFG, merge_cfg
from .normalize import _normalize_items
from .priority import _score_item, _select_high_priority
from .rendering import _render_md
from .validate import _annotate_bucket_on_items, _validate_coverage


def render_markdown(payload: dict, cfg_override: Dict | None = None, cfg: Dict | None = None) -> str:
    """Render payload into Obsidian-friendly Markdown.

    `cfg_override` is kept for API compatibility; `cfg` is an alias.
    """
    if cfg_override is None:
        cfg_override = cfg
    elif cfg is not None:
        merged = dict(cfg_override)
        merged.update(cfg)
        cfg_override = merged

    state = build_state(payload, cfg_override)
    return _render_md(state)


def build_state(payload: dict, cfg_override: Dict | None = None, cfg: Dict | None = None) -> Dict:
    """Build renderer state (useful for tests). Accepts `cfg` alias like render_markdown."""
    if cfg_override is None:
        cfg_override = cfg
    elif cfg is not None:
        merged = dict(cfg_override)
        merged.update(cfg)
        cfg_override = merged

    if payload is None:
        raise ValueError("payload is required")

    merged_cfg = _merge_cfg(payload.get("cfg"), cfg_override)
    meta = payload.get("meta") or {}
    items_raw = payload.get("items") or []
    items, deduped_count = _normalize_items(items_raw, merged_cfg)

    buckets = _assign_buckets(items, merged_cfg)
    _select_high_priority(buckets, merged_cfg)
    _annotate_bucket_on_items(buckets)
    _validate_coverage(items, buckets)

    state = {
        "cfg": merged_cfg,
        "meta": meta,
        "counts": payload.get("counts") or {},
        "items": items,
        "deduped_count": deduped_count,
        "buckets": buckets,
    }
    return state


def _merge_cfg(payload_cfg: Dict | None, override_cfg: Dict | None) -> Dict:
    return merge_cfg(payload_cfg, override_cfg)


__all__ = [
    "DEFAULT_CFG",
    "render_markdown",
    "build_state",
    "_merge_cfg",
    "_score_item",
    "_host_matches_base",
]
