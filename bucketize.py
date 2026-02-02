"""Bucket assignment helpers for TabDump renderer v3."""

from __future__ import annotations

from typing import Dict, List


def assign_buckets(items: List[dict], cfg: Dict) -> Dict[str, List[dict]]:
    """Assign base buckets. Returns dict with ADMIN/MEDIA/REPOS/DOCS/QUICK (and FUN if enabled)."""
    buckets: Dict[str, List[dict]] = {"ADMIN": [], "MEDIA": [], "REPOS": [], "DOCS": [], "QUICK": []}
    if cfg.get("includeFunBucket"):
        buckets["FUN"] = []

    for item in items:
        bucket = _bucket_for_item(item, cfg)
        buckets.setdefault(bucket, []).append(item)

    # If quick wins disabled, merge quick into docs
    if not cfg.get("includeQuickWins", True):
        buckets["DOCS"].extend(buckets.get("QUICK", []))
        buckets["QUICK"] = []
    return buckets


def _bucket_for_item(item: dict, cfg: Dict) -> str:
    flags = item.get("flags") or {}
    kind = item.get("kind")
    intent = (item.get("intent") or {}).get("action")

    if flags.get("is_local") or flags.get("is_auth") or flags.get("is_chat") or flags.get("is_internal"):
        return "ADMIN"
    if kind == "video":
        return "MEDIA"
    if kind in {"repo", "tool"}:
        return "REPOS"
    if kind in {"docs", "spec", "paper", "article"}:
        return "DOCS"

    # Optional fun bucket
    if cfg.get("includeFunBucket") and (intent in {"relax", "entertain"} or kind == "misc"):
        return "FUN"

    return "QUICK"
