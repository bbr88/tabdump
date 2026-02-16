"""Stats and badge helpers for rendering."""

from __future__ import annotations

from collections import Counter
from typing import Dict, List

from core.tab_policy.actions import canonical_action
from core.tab_policy.text import slugify_kebab

from .config import DEFAULT_CFG


def _top_domains(items: List[dict], limit: int) -> List[str]:
    non_admin = [it for it in items if not (it.get("domain_category") or "").startswith("admin_")]
    counts = Counter(it.get("domain") or "" for it in non_admin)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [d for d, _ in ranked[:limit] if d]


def _top_kinds(items: List[dict], limit: int) -> List[str]:
    non_admin = [it for it in items if not (it.get("domain_category") or "").startswith("admin_")]
    counts = Counter(it.get("kind") or "" for it in non_admin)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked[:limit] if k]


def _top_topics(items: List[dict], limit: int) -> List[str]:
    non_admin = [it for it in items if not (it.get("domain_category") or "").startswith("admin_")]
    counts = Counter()
    for item in non_admin:
        topics = item.get("topics")
        if not isinstance(topics, list):
            continue
        for topic in topics:
            slug = ""
            if isinstance(topic, dict):
                slug = _tagify(str(topic.get("slug") or ""))
            elif isinstance(topic, str):
                slug = _tagify(topic)
            if slug in {"", "misc", "other"}:
                continue
            counts[slug] += 1
            break
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [slug for slug, _ in ranked[:limit]]


def _focus_line(items: List[dict]) -> str:
    non_admin = [it for it in items if not (it.get("domain_category") or "").startswith("admin_")]
    cat_counts = Counter(it.get("domain_category") or "" for it in non_admin)
    dom_counts = Counter(it.get("domain") or "" for it in non_admin)
    top_cats = [c for c, _ in sorted(cat_counts.items(), key=lambda kv: (-kv[1], kv[0])) if c][:2]
    top_doms = [d for d, _ in sorted(dom_counts.items(), key=lambda kv: (-kv[1], kv[0])) if d][:2]

    def cat_display(cat: str) -> str:
        mapping = {
            "docs_site": "docs",
            "blog": "reading",
            "code_host": "repos",
            "video": "media",
            "music": "media",
            "console": "tools",
            "generic": "browsing",
        }
        return mapping.get(cat, cat or "varied")

    cats_str = " + ".join(cat_display(c) for c in top_cats) if top_cats else "varied"
    doms_str = " and ".join(top_doms) if top_doms else "various domains"
    return f"Mostly {cats_str} across {doms_str}."


def _tagify(slug: str) -> str:
    return slugify_kebab(slug, fallback="other")


def _badge_cfg(cfg: Dict) -> Dict:
    render_cfg = cfg.get("render") or {}
    defaults = DEFAULT_CFG.get("render", {}).get("badges", {})
    merged = dict(defaults)
    merged.update(render_cfg.get("badges") or {})
    return merged


def _ordering_cfg(cfg: Dict) -> Dict:
    render_cfg = cfg.get("render") or {}
    defaults = DEFAULT_CFG.get("render", {}).get("ordering", {})
    merged = dict(defaults)
    merged.update(render_cfg.get("ordering") or {})
    return merged


def _primary_badge(item: dict) -> str:
    domain_category = item.get("domain_category") or ""
    if domain_category.startswith("admin_") or item.get("kind") == "admin":
        return "admin"
    kind = (item.get("kind") or "misc").lower()
    return kind


def _effort_band(item: dict) -> str:
    raw_effort = str(item.get("effort") or "").strip().lower()
    if raw_effort in {"quick", "medium", "deep"}:
        return raw_effort

    action = canonical_action((item.get("intent") or {}).get("action") or "")
    kind = str(item.get("kind") or "").strip().lower()
    if kind in {"paper", "spec"} or action == "deep_work":
        return "deep"
    if action in {"reference", "watch", "ignore"}:
        return "quick"
    return "medium"


def _status_pill(item: dict) -> str:
    band = _effort_band(item)
    display = {"quick": "low", "medium": "medium", "deep": "high"}.get(band, "medium")
    return f"[{display} effort]"


def _build_badges(item: dict, badges_cfg: Dict, context: str) -> str:
    max_badges = int(badges_cfg.get("maxPerBullet", 3))
    include_topic = bool(badges_cfg.get("includeTopicInHighPriority", True))
    include_why = bool(badges_cfg.get("includeQuickWinsWhy", False))

    primary_badge = _primary_badge(item)
    if primary_badge == "misc":
        if context == "projects":
            primary_badge = "project"
        elif context == "tools":
            primary_badge = "tool"

    badges: List[str] = [primary_badge]

    if context == "quick" and include_why:
        reason = (item.get("quick_why") or "fallback_misc").lower()
        badges.append(f"why:{reason}")

    if context == "high" and include_topic and item.get("topics"):
        slug = _tagify((item["topics"][0] or {}).get("slug") or "")
        badges.append(f"#{slug}")

    badges = [b.lower() for b in badges if b]
    if not badges:
        badges = ["misc"]
    return " · ".join(badges[:max_badges])
