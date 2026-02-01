#!/usr/bin/env python3
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple


def render_markdown(tabs: List[dict], meta: dict, cfg: dict) -> str:
    cfg = _apply_defaults(cfg or {})
    items = _normalize_items(tabs or [])

    top_topics = _top_counts([i["topic"] for i in items], cfg["topTopicsLimit"])
    top_domains = _top_counts([i["domain"] for i in items], cfg["topDomainsLimit"])
    browsers = _top_counts(
        [i["browser"] for i in items if i.get("browser")], limit=1000
    )

    fm_lines = [
        "---",
        f'created: "{meta.get("ts", "")}"',
        "type: tabdump",
        f'source: "{meta.get("sourceFile", "")}"',
        "status: inbox",
        "counts:",
        f"  total: {int(meta.get('counts', {}).get('total', 0))}",
        f"  dumped: {int(meta.get('counts', {}).get('dumped', 0))}",
        f"  closed: {int(meta.get('counts', {}).get('closed', 0))}",
        f"  kept: {int(meta.get('counts', {}).get('kept', 0))}",
        f"browsers: [{', '.join(browsers)}]",
        f"topics_top: [{', '.join(top_topics)}]",
        f"domains_top: [{', '.join(top_domains)}]",
        "---",
    ]

    ts = meta.get("ts", "")
    lines: List[str] = []
    lines.extend(fm_lines)
    lines.append(f"# Tab dump — {ts}")
    lines.append("")
    lines.extend(_summary_callout(meta, top_topics, top_domains))
    lines.append("")
    lines.extend(_triage_checklist())
    lines.append("")

    # Top picks
    top_picks = [i for i in items if i["prio"] == "p1"]
    top_picks = _sort_items(top_picks)[: cfg["topPicksLimit"]]
    lines.extend(_render_section("## ⭐ Top picks", top_picks, cfg))

    # Action buckets (do not remove from top picks)
    buckets = _action_buckets(items)
    section_defs = [
        ("## 📚 Reference (docs / specs)", buckets["reference"]),
        ("## 📌 Read next (articles / posts / papers)", buckets["read"]),
        ("## 🧰 Build / code (repos / tooling)", buckets["build"]),
        ("## 🎥 Watch", buckets["watch"]),
        ("## 🎭 Misc", buckets["misc"]),
        ("## 🧯 Local / ephemeral", buckets["local"]),
    ]
    for title, bucket in section_defs:
        lines.extend(_render_section(title, bucket, cfg))

    if cfg["includeTopicAppendix"]:
        lines.append("## By topic (collapsed)")
        lines.append("> [!info]- Expand")
        lines.append("")
        for topic, topic_items in _group_topics(items):
            lines.append(f"### {topic}")
            for it in _sort_items(topic_items):
                lines.append(_format_item(it, cfg))
            lines.append("")
        _trim_trailing_blank(lines)

    lines.extend(_footer(meta, cfg))
    return "\n".join(lines).rstrip() + "\n"


def _apply_defaults(cfg: dict) -> dict:
    out = {
        "topTopicsLimit": 6,
        "topDomainsLimit": 6,
        "topPicksLimit": 12,
        "minDomainGroupSize": 2,
        "includeTopicAppendix": True,
        "hideEmptySections": True,
        "linkStyle": "chips",
        "rendererVersion": "1.0.0",
    }
    out.update(cfg)
    return out


def _normalize_items(tabs: List[dict]) -> List[dict]:
    items: List[dict] = []
    for t in tabs:
        title = _sanitize_title(str(t.get("title", "")).strip())
        url = str(t.get("url", "")).strip()
        if not title or not url:
            continue
        score = t.get("score")
        prio = t.get("prio")
        if prio is None:
            if score is None:
                prio = "p2"
            else:
                prio = _prio_from_score(int(score))
        prio = str(prio)
        item = {
            "title": title,
            "url": url,
            "topic": str(t.get("topic", "")).strip(),
            "kind": str(t.get("kind", "")).strip(),
            "action": str(t.get("action", "")).strip(),
            "domain": str(t.get("domain", "")).strip(),
            "browser": _normalize_browser(t.get("browser")),
            "score": int(score) if score is not None else 0,
            "prio": prio,
        }
        items.append(item)
    return items


def _prio_from_score(score: int) -> str:
    if score >= 4:
        return "p1"
    if 2 <= score <= 3:
        return "p2"
    return "p3"


def _normalize_browser(value: object) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip().lower()
    if v in {"chrome", "safari", "firefox"}:
        return v
    return None


def _top_counts(values: Iterable[str], limit: int) -> List[str]:
    counts: Dict[str, int] = {}
    for v in values:
        if not v:
            continue
        counts[v] = counts.get(v, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked[:limit]]


def _summary_callout(meta: dict, top_topics: List[str], top_domains: List[str]) -> List[str]:
    counts = meta.get("counts", {})
    top_topics_str = ", ".join(top_topics) if top_topics else "none"
    top_domains_str = ", ".join(top_domains) if top_domains else "none"
    return [
        "> [!summary] Summary",
        f"> total: {int(counts.get('total', 0))} | dumped: {int(counts.get('dumped', 0))} | closed: {int(counts.get('closed', 0))} | kept: {int(counts.get('kept', 0))}",
        f"> top topics: {top_topics_str}",
        f"> top domains: {top_domains_str}",
    ]


def _triage_checklist() -> List[str]:
    return [
        "## Inbox triage",
        "- [ ] Scan for must-read today",
        "- [ ] Archive or ignore low-value items",
        "- [ ] Capture tasks / TODOs",
        "- [ ] Move key links into projects",
    ]


def _action_buckets(items: List[dict]) -> Dict[str, List[dict]]:
    buckets = {k: [] for k in ["reference", "read", "build", "watch", "misc", "local"]}
    for it in items:
        action = it["action"]
        kind = it["kind"]
        if action == "reference":
            buckets["reference"].append(it)
        if action == "read":
            buckets["read"].append(it)
        if action == "build":
            buckets["build"].append(it)
        if action == "watch":
            buckets["watch"].append(it)
        if action == "triage" or kind == "misc":
            buckets["misc"].append(it)
        if action == "ignore" or kind in {"local", "auth", "internal"}:
            buckets["local"].append(it)
    return buckets


def _render_section(title: str, items: List[dict], cfg: dict) -> List[str]:
    if not items and cfg["hideEmptySections"]:
        return []
    lines: List[str] = [title]
    if not items:
        lines.append("")
        return lines

    items = _sort_items(items)
    lines.append("")
    lines.extend(_render_grouped(items, cfg))
    lines.append("")
    return lines


def _render_grouped(items: List[dict], cfg: dict) -> List[str]:
    min_size = int(cfg["minDomainGroupSize"])
    by_domain: Dict[str, List[dict]] = {}
    for it in items:
        by_domain.setdefault(it["domain"], []).append(it)

    big_domains = {d for d, arr in by_domain.items() if len(arr) >= min_size}
    lines: List[str] = []

    if not big_domains:
        for it in items:
            lines.append(_format_item(it, cfg))
        return lines

    for domain in sorted(big_domains):
        lines.append(f"### {domain}")
        for it in _sort_items(by_domain[domain]):
            lines.append(_format_item(it, cfg))
        lines.append("")

    remaining = [it for it in items if it["domain"] not in big_domains]
    for it in remaining:
        lines.append(_format_item(it, cfg))

    _trim_trailing_blank(lines)
    return lines


def _group_topics(items: List[dict]) -> List[Tuple[str, List[dict]]]:
    by_topic: Dict[str, List[dict]] = {}
    for it in items:
        topic = it["topic"] or "(unknown)"
        by_topic.setdefault(topic, []).append(it)
    ranked = sorted(by_topic.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return ranked


def _sort_items(items: List[dict]) -> List[dict]:
    order = {"p1": 0, "p2": 1, "p3": 2}

    def key(it: dict) -> Tuple[int, int, str, str, str]:
        pr = order.get(it["prio"], 1)
        score = it.get("score") or 0
        return (
            pr,
            -int(score),
            (it.get("topic") or "").lower(),
            (it.get("domain") or "").lower(),
            (it.get("title") or "").lower(),
        )

    return sorted(items, key=key)


def _format_item(it: dict, cfg: dict) -> str:
    if cfg["linkStyle"] == "dataview":
        lines = [f"- [{it['title']}]({it['url']})"]
        lines.append(f"  - topic:: {it['topic']}")
        lines.append(f"  - kind:: {it['kind']}")
        lines.append(f"  - prio:: {it['prio']}")
        if it.get("browser"):
            lines.append(f"  - src:: {it['browser']}")
        return "\n".join(lines)

    chips = [
        f"`topic:{it['topic']}`",
        f"`kind:{it['kind']}`",
        f"`prio:{it['prio']}`",
    ]
    if it.get("browser"):
        chips.append(f"`src:{it['browser']}`")
    return f"- [{it['title']}]({it['url']}) · " + " ".join(chips)


def _sanitize_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title.replace("\n", " ").replace("\r", " ")).strip()
    if len(title) > 120:
        return title[:119] + "…"
    return title


def _trim_trailing_blank(lines: List[str]) -> None:
    while lines and lines[-1] == "":
        lines.pop()


def _footer(meta: dict, cfg: dict) -> List[str]:
    allowlist = meta.get("allowlistPatterns", []) or []
    prefixes = meta.get("skipPrefixes", []) or []
    allowlist_str = ", ".join(allowlist) if allowlist else "none"
    prefixes_str = ", ".join(prefixes) if prefixes else "none"
    return [
        "## Notes",
        f"- Allowlist kept open: {allowlist_str}",
        f"- Skipped internal prefixes: {prefixes_str}",
        f"- Renderer version: {cfg.get('rendererVersion', '1.0.0')}",
    ]
