"""TabDump Pretty Renderer v3 (Markdown dashboard)."""

from __future__ import annotations

import datetime
from typing import Dict, List, Tuple

import bucketize
import normalize
import scoring
import stats


DEFAULT_CFG: Dict = {
    "rendererVersion": "3.0.0",
    "nowLimit": 7,
    "titleMaxLen": 120,
    "stripWwwForGrouping": True,
    "skipPrefixes": [
        "chrome://",
        "chrome-extension://",
        "about:",
        "file://",
        "safari://",
        "safari-web-extension://",
    ],
    "chatDomains": ["chatgpt.com", "gemini.google.com"],
    "focusTopN": 2,
    "topListN": 6,
    "indexLimit": 12,
    "includeQuickWins": True,
    "quickWinsMaxItems": 30,
    "bucketOrder": ["HIGH", "MEDIA", "REPOS", "DOCS", "QUICK", "ADMIN"],
    "includeFunBucket": False,
    "minTopicConfidence": 0.0,
    "showDedupedInSummary": True,
}


def render_markdown(payload: dict, cfg: Dict | None = None) -> str:
    if payload is None:
        raise ValueError("payload is required")
    merged_cfg = _merge_cfg(payload.get("cfg") or {}, cfg or {})
    meta = payload.get("meta") or {}
    items_raw = payload.get("items") or []

    items, deduped_count = normalize.normalize_items(items_raw, merged_cfg, meta)

    base_buckets = bucketize.assign_buckets(items, merged_cfg)
    if "FUN" in base_buckets:
        base_buckets["QUICK"].extend(base_buckets.pop("FUN"))
    _validate_base_coverage(items, base_buckets)

    # Annotate bucket on items for later stats
    for name, arr in base_buckets.items():
        for it in arr:
            it["bucket"] = name

    top_topics_frontmatter = stats.top_counts(
        [(it.get("topic_primary") or {}).get("slug", "") for it in items], int(merged_cfg["topListN"])
    )

    # High priority extraction
    top_domains_ctx = set(
        stats.top_counts([it.get("domain") for it in items if it.get("bucket") != "ADMIN"], merged_cfg["topListN"])
    )
    top_topics_ctx = set(
        stats.top_counts(
            [(it.get("topic_primary") or {}).get("slug") for it in items if it.get("bucket") != "ADMIN"],
            merged_cfg["topListN"],
        )
    )
    scoring.select_high_priority(base_buckets, int(merged_cfg["nowLimit"]), top_domains_ctx, top_topics_ctx)

    # Annotate buckets after extraction
    for name, arr in base_buckets.items():
        for it in arr:
            it["bucket"] = name

    _validate_totals(items, base_buckets)

    focus = stats.focus_line(items, merged_cfg)

    fm = _frontmatter(
        meta, payload.get("counts") or {}, len(items_raw), top_topics_frontmatter, deduped_count, merged_cfg
    )

    lines: List[str] = []
    lines.extend(fm)
    lines.append("")
    lines.append(f"# 📑 Tab Dump: {_dump_date(meta)}")
    lines.append(f"> **Focus:** {focus}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for section in merged_cfg["bucketOrder"]:
        if section == "HIGH":
            lines.extend(_render_high(base_buckets.get("HIGH", [])))
        elif section == "MEDIA":
            lines.extend(_render_callout("📺 Media Queue", "Videos from YouTube and other platforms.", "[!video]- Expand Watch List", base_buckets.get("MEDIA", [])))
        elif section == "REPOS":
            lines.extend(_render_callout("🏗 Projects & Repos", "GitHub repositories and technical specs.", "[!code]- View Repositories", base_buckets.get("REPOS", [])))
        elif section == "DOCS":
            lines.extend(_render_callout("📚 Technical Reference (Docs)", "Manuals, API specs, and blog deep-dives.", "[!info]- View Documentation", base_buckets.get("DOCS", [])))
        elif section == "QUICK" and merged_cfg.get("includeQuickWins", True):
            items_quick = base_buckets.get("QUICK", [])
            max_q = int(merged_cfg.get("quickWinsMaxItems", len(items_quick)))
            items_quick = items_quick[:max_q]
            lines.extend(_render_callout("🧹 Quick Wins", "Low-effort items: skim / decide later.", "[!tip]- Expand Quick Wins", items_quick))
        elif section == "ADMIN":
            lines.extend(_render_callout("🔐 Tools & Admin", "Auth keys, config pages, chats, localhosts.", "[!warning]- Sensitive/Administrative", base_buckets.get("ADMIN", [])))

        lines.append("")

    md = "\n".join(lines).rstrip() + "\n"
    _validate_markdown(md, merged_cfg)
    return md


def _merge_cfg(payload_cfg: Dict, override_cfg: Dict) -> Dict:
    merged = dict(DEFAULT_CFG)
    merged.update(payload_cfg or {})
    merged.update(override_cfg or {})
    return merged


def _dump_date(meta: Dict) -> str:
    if meta.get("dump_date"):
        return str(meta["dump_date"])
    created = str(meta.get("created") or meta.get("ts") or "")
    if not created:
        return ""
    return created.split()[0]


def _frontmatter(
    meta: Dict, counts: Dict, total_items: int, top_topics: List[str], deduped_count: int, cfg: Dict
) -> List[str]:
    top_topics_tags = [f"#{stats.tagify(t)}" for t in top_topics][: cfg.get("topListN", 6)]
    source = meta.get("source") or meta.get("sourceFile") or ""
    dump_date = _dump_date(meta)
    tab_count = counts.get("total") or total_items
    fm = [
        "---",
        f"dump_date: {dump_date}",
        f"tab_count: {tab_count}",
        f"top_topics: {', '.join(top_topics_tags)}",
        "status: 📥 Inbox",
        "renderer: tabdump-pretty-v3",
        f'source: "{source}"',
    ]
    if cfg.get("showDedupedInSummary", True):
        fm.append(f"deduped: {deduped_count}")
    fm.append("---")
    return fm


def _render_high(items: List[dict]) -> List[str]:
    lines = ["## 🔥 High Priority", "*Auto-selected “do next” items (no manual priority).*"]
    if not items:
        lines.append("_(empty)_")
        return lines
    for it in _sort_bucket(items):
        lines.append(_format_item(it, prefix=""))
    return lines


def _render_callout(title: str, subtitle: str, callout: str, items: List[dict]) -> List[str]:
    count = len(items)
    lines = [f"## {title}", f"*{subtitle}*", f"> {callout} ({count})"]
    if not items:
        lines.append("> _(empty)_")
        return lines
    for it in _sort_bucket(items):
        lines.append(_format_item(it, prefix="> "))
    return lines


def _format_item(item: dict, prefix: str = "") -> str:
    title = item.get("title_render") or item.get("title") or ""
    url = item.get("url") or ""
    kind = item.get("kind") or "misc"
    intent = (item.get("intent") or {}).get("action") or "learn"
    topic = stats.tagify((item.get("topic_primary") or {}).get("slug") or "")
    domain = item.get("domain") or "unknown"
    browser = (item.get("browser") or "unknown")
    return (
        f"{prefix}- [ ] **{title}** ([Link]({url})) • (kind:: {kind}) • "
        f"(intent:: {intent}) • (topic:: #{topic}) • (domain:: {domain}) • (src:: {browser})"
    )


def _sort_bucket(items: List[dict]) -> List[dict]:
    return sorted(
        items,
        key=lambda it: (
            ((it.get("topic_primary") or {}).get("title") or "").lower(),
            (it.get("domain") or "").lower(),
            -float((it.get("intent") or {}).get("confidence", 0)),
            (it.get("title_render") or it.get("title") or "").lower(),
        ),
    )


def _validate_base_coverage(items: List[dict], buckets: Dict[str, List[dict]]):
    all_urls = {it["url"] for it in items}
    assigned = set()
    for arr in buckets.values():
        for it in arr:
            if it["url"] in assigned:
                raise ValueError(f"Duplicate assignment for URL: {it['url']}")
            assigned.add(it["url"])
    if all_urls != assigned:
        raise ValueError("Not all items assigned to a base bucket")


def _validate_totals(items: List[dict], buckets: Dict[str, List[dict]]):
    total = sum(len(arr) for arr in buckets.values())
    if total != len(items):
        raise ValueError("Bucket totals mismatch after HIGH extraction")
    # URL uniqueness across all rendered buckets
    seen = set()
    for arr in buckets.values():
        for it in arr:
            url = it["url"]
            if url in seen:
                raise ValueError(f"Duplicate URL across buckets: {url}")
            seen.add(url)


def _validate_markdown(md: str, cfg: Dict):
    # Ensure sections in order
    headers = ["## 🔥 High Priority", "## 📺 Media Queue", "## 🏗 Projects & Repos", "## 📚 Technical Reference (Docs)"]
    if cfg.get("includeQuickWins", True):
        headers.append("## 🧹 Quick Wins")
    headers.append("## 🔐 Tools & Admin")
    positions = []
    for h in headers:
        pos = md.find(h)
        if pos == -1:
            raise ValueError(f"Missing section {h}")
        positions.append(pos)
    if positions != sorted(positions):
        raise ValueError("Section order incorrect")
