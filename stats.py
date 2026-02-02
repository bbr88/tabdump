"""Stats helpers: top topics/domains/browsers + focus line."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Tuple


def top_counts(values: Iterable[str], limit: int) -> List[str]:
    counts: Dict[str, int] = {}
    for v in values:
        if not v:
            continue
        counts[v] = counts.get(v, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked[:limit]]


def tagify(slug: str) -> str:
    tag = re.sub(r"[^a-zA-Z0-9]+", "-", (slug or "").lower())
    tag = re.sub(r"-+", "-", tag).strip("-")
    return tag or "other"


def focus_line(items: List[dict], cfg: Dict) -> str:
    non_admin = [it for it in items if it.get("bucket") != "ADMIN"]
    top_n = int(cfg.get("focusTopN", 2))
    counts: Dict[str, int] = {}
    for it in non_admin:
        slug = (it.get("topic_primary") or {}).get("slug", "")
        if not slug:
            continue
        counts[slug] = counts.get(slug, 0) + 1

    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top = ranked[:top_n]
    if not top:
        return "No dominant topics detected."

    tags = [f"(topic:: #{tagify(slug)})" for slug, _ in top]
    if len(tags) == 1:
        return f"High concentration of {tags[0]} research."
    return f"High concentration of {tags[0]} and {tags[1]} research."
