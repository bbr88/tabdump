"""Priority scoring for High Priority shortlist."""

from __future__ import annotations

from typing import Dict, Iterable, List, Set, Tuple


KEYWORDS = ["internals", "deep", "how", "guide", "tutorial", "benchmarko"]


KIND_ORDER = ["spec", "paper", "docs", "repo", "article", "video", "tool", "misc"]
KIND_RANK = {k: i for i, k in enumerate(KIND_ORDER)}


def score(item: dict, top_domains: Set[str], top_topics: Set[str]) -> int:
    s = 0
    kind = item.get("kind") or ""
    domain = item.get("domain") or ""
    primary = (item.get("topic_primary") or {}).get("slug", "")
    intent = item.get("intent") or {}
    action = intent.get("action")
    conf = float(intent.get("confidence", 0))

    if kind in {"paper", "spec"}:
        s += 3
    if domain in top_domains:
        s += 2
    if primary in top_topics:
        s += 2
    if action in {"implement", "debug", "decide", "learn"}:
        s += 2
    if conf >= 0.75:
        s += 1
    if kind == "misc":
        s -= 2
    if domain == "":
        s -= 1

    title = (item.get("title") or "").lower()
    if any(k in title for k in KEYWORDS):
        s += 1

    return int(s)


def select_high_priority(buckets: Dict[str, List[dict]], now_limit: int, top_domains: Set[str], top_topics: Set[str]):
    """Pull items from eligible buckets into HIGH."""
    eligible_names = {"DOCS", "REPOS", "MEDIA"}
    candidates: List[Tuple[int, float, int, str, str, dict]] = []
    for name in eligible_names:
        for item in buckets.get(name, []):
            sc = score(item, top_domains, top_topics)
            conf = float(item.get("intent", {}).get("confidence", 0))
            kind_rank = KIND_RANK.get(item.get("kind"), len(KIND_RANK))
            domain = item.get("domain") or ""
            title = item.get("title_render") or item.get("title") or ""
            candidates.append((sc, conf, kind_rank, domain, title, item))

    candidates.sort(
        key=lambda tpl: (
            -tpl[0],  # score desc
            -tpl[1],  # intent confidence desc
            tpl[2],  # kind order
            tpl[3],  # domain asc
            tpl[4],  # title asc
        )
    )

    selected = [tpl[5] for tpl in candidates[:now_limit]]

    # Remove selected from original buckets
    selected_urls = {it["url"] for it in selected}
    for name in eligible_names:
        buckets[name] = [it for it in buckets.get(name, []) if it["url"] not in selected_urls]

    buckets["HIGH"] = selected
    return selected
