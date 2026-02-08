"""High-priority selection and scoring."""

from __future__ import annotations

from typing import Dict, List, Tuple

from core.tab_policy.actions import action_priority_weight, canonical_action

from .config import AGGREGATOR_MARKERS, DEPTH_HINTS, KIND_PRIORITY_INDEX


def _select_high_priority(buckets: Dict[str, List[dict]], cfg: Dict) -> None:
    eligible_buckets = {"DOCS", "REPOS", "MEDIA"}
    min_score = int(cfg.get("highPriorityMinScore", 4))
    min_conf = float(cfg.get("highPriorityMinIntentConfidence", 0.70))
    limit = int(cfg.get("highPriorityLimit", 5))
    eligible_categories = set(cfg.get("highPriorityEligibleCategories", []))

    candidates: List[Tuple[int, int, float, str, str, dict]] = []
    for bucket_name in eligible_buckets:
        for item in buckets.get(bucket_name, []):
            if item.get("domain_category") not in eligible_categories:
                continue
            score = _score_item(item)
            item["_high_score"] = score
            conf = float((item.get("intent") or {}).get("confidence", 0.0))
            kind_rank = KIND_PRIORITY_INDEX.get(item.get("kind"), len(KIND_PRIORITY_INDEX))
            domain = item.get("domain") or ""
            title = item.get("title_render") or item.get("title") or ""
            if score < min_score:
                continue
            if conf < min_conf and item.get("kind") not in {"paper", "spec"}:
                continue
            candidates.append((score, kind_rank, conf, domain, title, item))

    candidates.sort(
        key=lambda tpl: (
            -tpl[0],  # score desc
            tpl[1],  # kind priority
            -tpl[2],  # intent confidence desc
            tpl[3],  # domain asc
            tpl[4],  # title asc
        )
    )

    selected = [tpl[5] for tpl in candidates[:limit]]
    selected_urls = {it["url"] for it in selected}

    for bucket_name in eligible_buckets:
        buckets[bucket_name] = [it for it in buckets.get(bucket_name, []) if it["url"] not in selected_urls]

    buckets["HIGH"] = selected


def _score_item(item: dict) -> int:
    score = 0
    kind = item.get("kind") or ""
    domain_category = item.get("domain_category") or ""
    intent = item.get("intent") or {}
    action = canonical_action(intent.get("action") or "")
    conf = float(intent.get("confidence", 0.0))
    title = (item.get("title") or "").lower()
    path = item.get("path") or ""

    # Kind
    if kind == "paper":
        score += 5
    elif kind == "spec":
        score += 4
    elif kind == "docs":
        score += 3
    elif kind == "repo":
        score += 3
    elif kind == "article":
        score += 1

    # Domain category
    if domain_category in {"docs_site", "blog", "code_host"}:
        score += 2
    elif domain_category == "console":
        score += 1

    # Intent action (aligned with postprocess semantics)
    score += action_priority_weight(action)

    # Confidence
    if conf >= 0.80:
        score += 1
    elif conf < 0.70 and kind not in {"paper", "spec"}:
        score -= 2

    # Aggregator penalty
    if any(marker in title for marker in AGGREGATOR_MARKERS):
        score -= 2

    # Depth hint bonus
    if any(hint in path for hint in DEPTH_HINTS):
        score += 1

    return int(score)
