"""Invariant checks for bucket coverage and rendered section ordering."""

from __future__ import annotations

from typing import Dict, List


def _annotate_bucket_on_items(buckets: Dict[str, List[dict]]) -> None:
    for bucket, arr in buckets.items():
        for it in arr:
            it["bucket"] = bucket


def _validate_coverage(items: List[dict], buckets: Dict[str, List[dict]]) -> None:
    urls_all = {it["url"] for it in items}
    urls_bucketed = set()
    for arr in buckets.values():
        for it in arr:
            if it["url"] in urls_bucketed:
                raise ValueError(f"Duplicate URL across buckets: {it['url']}")
            urls_bucketed.add(it["url"])
    if urls_all != urls_bucketed:
        missing = urls_all - urls_bucketed
        raise ValueError(f"Not all items assigned to a bucket: {missing}")


def _validate_rendered(md: str, buckets: Dict[str, List[dict]], cfg: Dict) -> None:
    include_empty = bool(cfg.get("includeEmptySections", False))
    include_quick = bool(cfg.get("includeQuickWins", True))

    ordered_sections = [
        ("## 🔥 Start Here", "HIGH"),
        ("## 📺 Watch / Listen Later", "MEDIA"),
        ("## 🏗 Repos", "REPOS"),
        ("## 🗂 Projects", "PROJECTS"),
        ("## 🧰 Apps & Utilities", "TOOLS"),
        ("## 📚 Read Later", "DOCS"),
        ("## 🧹 Easy Tasks", "QUICK"),
        ("## 🗃 Maybe Later", "BACKLOG"),
        ("## 🔐 Accounts & Settings", "ADMIN"),
    ]

    positions = []
    for header, bucket_name in ordered_sections:
        items = buckets.get(bucket_name, [])
        should_render = bool(items) or include_empty
        if bucket_name == "QUICK":
            should_render = include_quick and should_render
        elif bucket_name == "BACKLOG":
            should_render = bool(items)

        if not should_render:
            continue

        pos = md.find(header)
        if pos == -1:
            raise ValueError(f"Missing section {header}")
        positions.append(pos)

    if positions != sorted(positions):
        raise ValueError("Section order incorrect")
