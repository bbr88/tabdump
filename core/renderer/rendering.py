"""Markdown rendering for renderer state."""

from __future__ import annotations

import datetime as _dt
import re
from typing import Dict, List, Tuple
from urllib.parse import quote

from .buckets import _quick_mini_classify
from .config import SECTION_ORDER
from .stats import _badge_cfg, _build_badges, _effort_band, _focus_line, _ordering_cfg, _status_pill, _top_domains, _top_kinds, _top_topics
from .validate import _validate_rendered


def _render_md(state: Dict) -> str:
    cfg = state["cfg"]
    buckets = state["buckets"]
    meta = state["meta"]
    counts = state["counts"]
    items = state["items"]
    deduped = state["deduped_count"]
    badge_cfg = _badge_cfg(cfg)
    ordering_cfg = _ordering_cfg(cfg)

    fm_lines = _frontmatter(meta, counts, items, deduped, cfg)
    dump_date = _dump_date(meta)

    lines: List[str] = []
    lines.extend(fm_lines)
    lines.append("")
    lines.append(f"# 📑 Tab Dump: {dump_date}")
    if cfg.get("includeFocusLine", True):
        lines.append(f"> **Focus:** {_focus_line(items)}")
    lines.append("")

    lines.extend(_render_sections(buckets, cfg, badge_cfg, ordering_cfg, items))

    md = "\n".join(lines).rstrip() + "\n"
    _validate_rendered(md, buckets, cfg)
    return md


def _frontmatter(meta: Dict, counts: Dict, items: List[dict], deduped: int, cfg: Dict) -> List[str]:
    fields = []
    include = cfg.get("frontmatterInclude", [])
    include_set = {str(x) for x in include}

    def _has(*keys: str) -> bool:
        return any(k in include_set for k in keys)

    if _has("dump_date", "Dump Date"):
        fields.append(("Dump Date", _dump_date(meta)))
    if _has("tab_count", "Tab Count"):
        fields.append(("Tab Count", int(counts.get("total") or len(items))))
    if _has("top_domains", "Top Domains"):
        fields.append(("Top Domains", ", ".join(_top_domains(items, 5))))
    if _has("top_kinds", "Top Kinds"):
        fields.append(("Top Kinds", ", ".join(_top_kinds(items, 3))))
    if _has("renderer", "Renderer"):
        fields.append(("Renderer", "tabdump-pretty-v3.2.4.1"))
    if _has("source", "Source"):
        fields.append(("Source", str(meta.get("source") or "")))
    if _has("deduped", "Deduped"):
        fields.append(("Deduped", deduped))

    lines = ["---"]
    for key, val in fields:
        lines.append(f"{key}: {val}")
    lines.append("---")
    return lines


def _dump_date(meta: Dict) -> str:
    if meta.get("dump_date"):
        return str(meta["dump_date"])
    created = str(meta.get("created") or meta.get("ts") or "")
    if not created:
        return ""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", created)
    if match:
        return match.group(1)
    try:
        dt = _dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except Exception:
        return created.split("T")[0].split(" ")[0]


def _render_sections(
    buckets: Dict[str, List[dict]],
    cfg: Dict,
    badge_cfg: Dict,
    ordering_cfg: Dict,
    all_items: List[dict],
) -> List[str]:
    lines: List[str] = []
    include_empty = bool(cfg.get("includeEmptySections", False))
    for name in SECTION_ORDER:
        start_len = len(lines)
        items = buckets.get(name, [])
        should_render = bool(items) or include_empty
        if name == "HIGH":
            if should_render:
                lines.extend(_render_high(items, all_items, cfg, badge_cfg))
        elif name == "MEDIA":
            if should_render:
                lines.extend(
                    _render_callout(
                        "📺 Watch / Listen Later",
                        "[!video]- Expand Watch / Listen Later",
                        items,
                        cfg,
                        badge_cfg,
                        ordering_cfg,
                        bullet_context="media",
                    )
                )
        elif name == "REPOS":
            if should_render:
                lines.extend(
                    _render_callout(
                        "🏗 Repos",
                        "[!code]- View Repositories",
                        items,
                        cfg,
                        badge_cfg,
                        ordering_cfg,
                        bullet_context="repos",
                    )
                )
        elif name == "PROJECTS":
            if should_render:
                lines.extend(
                    _render_callout(
                        "🗂 Projects",
                        "[!note]- View Project Workspaces",
                        items,
                        cfg,
                        badge_cfg,
                        ordering_cfg,
                        bullet_context="projects",
                    )
                )
        elif name == "TOOLS":
            if should_render:
                lines.extend(
                    _render_callout(
                        "🧰 Apps & Utilities",
                        "[!note]- Expand Apps & Utilities",
                        items,
                        cfg,
                        badge_cfg,
                        ordering_cfg,
                        bullet_context="tools",
                    )
                )
        elif name == "DOCS":
            if should_render:
                lines.extend(
                    _render_docs_callout(
                        "📚 Read Later",
                        "[!info]- Read Later",
                        items,
                        cfg,
                        badge_cfg,
                        ordering_cfg,
                    )
                )
        elif name == "QUICK":
            if cfg.get("includeQuickWins", True) and should_render:
                lines.extend(
                    _render_quick_callout(
                        "🧹 Easy Tasks",
                        "[!tip]- Expand Easy Tasks",
                        items,
                        cfg,
                        badge_cfg,
                        ordering_cfg,
                    )
                )
            else:
                continue
        elif name == "BACKLOG":
            if items:
                lines.extend(
                    _render_callout(
                        "🗃 Maybe Later",
                        "[!quote]- Expand Maybe Later",
                        items,
                        cfg,
                        badge_cfg,
                        ordering_cfg,
                        bullet_context="backlog",
                    )
                )
        elif name == "ADMIN":
            if should_render:
                lines.extend(
                    _render_callout(
                        "🔐 Accounts & Settings",
                        "[!warning]- Account/Settings Access",
                        items,
                        cfg,
                        badge_cfg,
                        ordering_cfg,
                        admin=True,
                        bullet_context="admin",
                    )
                )
        if len(lines) > start_len:
            lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _render_high(items: List[dict], all_items: List[dict], cfg: Dict, badge_cfg: Dict) -> List[str]:
    lines = ["## 🔥 Start Here", "*Auto-selected “do next” items.*"]
    lines.append(_today_context_line(all_items))
    if not items:
        lines.append(cfg.get("emptyBucketMessage", "_(empty)_"))
        return lines
    start_here_title_max = int(cfg.get("startHereTitleMaxLen", 72))
    for it in items:
        lines.extend(
            _format_bullet_two_line(
                it,
                prefix="",
                cfg=cfg,
                badges_cfg=badge_cfg,
                context="high",
                title_max_len=start_here_title_max,
            )
        )
    return lines


def _today_context_line(items: List[dict]) -> str:
    top_topics = _top_topics(items, 3)
    if top_topics:
        values = [f"#{_escape_md(topic)}" for topic in top_topics]
    else:
        values = [_escape_md(domain) for domain in _top_domains(items, 3)]
    if not values:
        values = ["varied"]
    return f"> [!abstract] Today's Context: {' | '.join(values)}"


def _render_callout(
    title: str,
    callout: str,
    items: List[dict],
    cfg: Dict,
    badge_cfg: Dict,
    ordering_cfg: Dict,
    admin: bool = False,
    bullet_context: str = "group",
) -> List[str]:
    count = len(items)
    lines = [f"## {title}", f"> {callout} ({count})"]
    if not items:
        lines.append(f"> {cfg.get('emptyBucketMessage', '_(empty)_')}")
        return lines

    grouped = _group_items(items, admin, ordering_cfg)
    for heading, group_items in grouped:
        lines.append(f"> ### {heading}")
        for it in _sort_items_alpha(group_items):
            if admin:
                lines.append(_format_bullet(it, prefix="> ", cfg=cfg, badges_cfg=badge_cfg, context="admin"))
            else:
                lines.extend(
                    _format_bullet_two_line(
                        it,
                        prefix="> ",
                        cfg=cfg,
                        badges_cfg=badge_cfg,
                        context=bullet_context,
                    )
                )
    return lines


def _render_docs_callout(
    title: str,
    callout: str,
    items: List[dict],
    cfg: Dict,
    badge_cfg: Dict,
    ordering_cfg: Dict,
) -> List[str]:
    count = len(items)
    lines = [f"## {title}", f"> {callout} ({count})"]
    if not items:
        lines.append(f"> {cfg.get('emptyBucketMessage', '_(empty)_')}")
        return lines

    grouped = _group_items(items, admin=False, ordering_cfg=ordering_cfg)
    domain_count = len(grouped)
    singleton_count = sum(1 for _, group_items in grouped if len(group_items) == 1)
    multi_min = int(cfg.get("docsMultiDomainMinItems", 2))
    main_items_count = count - singleton_count
    is_large = count >= int(cfg.get("docsLargeSectionItemsGte", 20)) or domain_count >= int(
        cfg.get("docsLargeSectionDomainsGte", 10)
    )

    if not is_large:
        for heading, group_items in grouped:
            lines.append(f"> ### {heading}")
            for it in _sort_items_alpha(group_items):
                lines.extend(_format_bullet_two_line(it, prefix="> ", cfg=cfg, badges_cfg=badge_cfg, context="docs"))
        return lines

    # For large docs sections, make the primary callout represent the focused subset.
    lines[1] = f"> [!info]- Main Sources ({main_items_count})"

    multi_groups: List[Tuple[str, List[dict]]] = []
    singleton_groups: List[Tuple[str, List[dict]]] = []
    for heading, group_items in grouped:
        if len(group_items) >= multi_min:
            multi_groups.append((heading, group_items))
        else:
            singleton_groups.append((heading, group_items))

    if multi_groups:
        for heading, group_items in multi_groups:
            lines.append(f"> ### {heading} ({len(group_items)})")
            for it in _sort_items_alpha(group_items):
                lines.extend(_format_bullet_two_line(it, prefix="> ", cfg=cfg, badges_cfg=badge_cfg, context="docs"))
    else:
        lines.append("> _(no main sources)_")

    if singleton_groups:
        lines.append("")
        lines.append(f"> [!summary]- More Links ({singleton_count})")
        flat_singletons: List[Tuple[str, dict]] = []
        for heading, group_items in singleton_groups:
            for it in _sort_items_alpha(group_items):
                flat_singletons.append((heading, it))

        oneoff_mode = str(cfg.get("docsOneOffGroupingMode", "kind")).strip().lower()
        if oneoff_mode == "kind":
            grouped_oneoffs = _group_oneoffs_by_kind(flat_singletons)
            for label, arr in grouped_oneoffs:
                lines.append(f"> #### {label} ({len(arr)})")
                for source_domain, it in arr:
                    lines.extend(
                        _format_bullet_two_line(
                            it,
                            prefix="> ",
                            cfg=cfg,
                            badges_cfg=badge_cfg,
                            context="docs",
                            source_domain=source_domain,
                        )
                    )
        elif oneoff_mode == "energy":
            grouped_oneoffs = _group_oneoffs_by_energy(flat_singletons)
            for label, arr in grouped_oneoffs:
                lines.append(f"> #### {label} ({len(arr)})")
                for source_domain, it in arr:
                    lines.extend(
                        _format_bullet_two_line(
                            it,
                            prefix="> ",
                            cfg=cfg,
                            badges_cfg=badge_cfg,
                            context="docs",
                            source_domain=source_domain,
                        )
                    )
        else:
            # domain mode: flat one-offs, alphabetical by title.
            for source_domain, it in _sort_oneoffs_alpha(flat_singletons):
                lines.extend(
                    _format_bullet_two_line(
                        it,
                        prefix="> ",
                        cfg=cfg,
                        badges_cfg=badge_cfg,
                        context="docs",
                        source_domain=source_domain,
                    )
                )
    return lines


def _render_quick_callout(
    title: str,
    callout: str,
    items: List[dict],
    cfg: Dict,
    badge_cfg: Dict,
    ordering_cfg: Dict,
) -> List[str]:
    if not cfg.get("quickWinsEnableMiniCategories", True):
        return _render_callout(title, callout, items, cfg, badge_cfg, ordering_cfg)

    count = len(items)
    lines = [f"## {title}", f"> {callout} ({count})"]
    if not items:
        lines.append(f"> {cfg.get('emptyBucketMessage', '_(empty)_')}")
        return lines

    category_order = [str(name).lower() for name in cfg.get("quickWinsMiniCategories", ["leisure", "shopping"])]
    cats = {name: [] for name in category_order}
    for it in items:
        cat = str(it.get("quick_cat") or "").lower()
        reason = str(it.get("quick_why") or "").lower()
        if not cat or not reason:
            cat, reason = _quick_mini_classify(it, cfg)
            cat = str(cat).lower()
            reason = str(reason).lower()
            it["quick_cat"] = cat
            it["quick_why"] = reason
        cats.setdefault(cat, []).append(it)

    for cat in category_order:
        arr = cats.get(cat, [])
        if not arr:
            continue
        lines.append(f"> ### {cat.capitalize()}")
        for it in _sort_items_alpha(arr):
            lines.extend(_format_bullet_two_line(it, prefix="> ", cfg=cfg, badges_cfg=badge_cfg, context="quick"))
    return lines


def _group_items(items: List[dict], admin: bool, ordering_cfg: Dict) -> List[Tuple[str, List[dict]]]:
    grouped: Dict[Tuple[str, str], List[dict]] = {}
    for it in items:
        key = (it.get("domain_category"), it.get("domain"))
        grouped.setdefault(key, []).append(it)

    pinned = ordering_cfg.get("domains", {}).get("pinned", []) or []
    pin_index = {d.lower(): i for i, d in enumerate(pinned)}

    def key_sort(kv):
        (domain_cat, domain_disp) = kv[0]
        group = kv[1]
        count = len(group)
        dom = (domain_disp or "").lower()
        if dom in pin_index:
            return (0, pin_index[dom], 0, dom)
        return (1, -count, dom, (domain_cat or "").lower())

    result = []
    for key, group in sorted(grouped.items(), key=key_sort):
        cat, dom = key
        heading = f"{cat} • {dom}" if admin else dom
        result.append((heading, group))
    return result


def _escape_md(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\\", "\\\\")
    for ch in ("`", "*", "_", "[", "]", "(", ")"):
        text = text.replace(ch, "\\" + ch)
    return text


def _format_bullet(
    it: dict,
    prefix: str,
    cfg: Dict,
    badges_cfg: Dict,
    context: str,
    source_domain: str | None = None,
    title_max_len: int | None = None,
) -> str:
    display_title = _display_title(it, title_max_len=title_max_len)
    url = _escape_md_url(str(it.get("url") or ""))
    meta = " · ".join(_meta_parts(it, cfg, badges_cfg, context, source_domain))
    return f"{prefix}- [ ] [{display_title}]({url}) · {meta}"


def _format_bullet_two_line(
    it: dict,
    prefix: str,
    cfg: Dict,
    badges_cfg: Dict,
    context: str,
    source_domain: str | None = None,
    title_max_len: int | None = None,
) -> List[str]:
    display_title = _display_title(it, title_max_len=title_max_len)
    url = _escape_md_url(str(it.get("url") or ""))
    meta = " · ".join(_meta_parts(it, cfg, badges_cfg, context, source_domain))
    return [f"{prefix}- [ ] [{display_title}]({url})", f"{prefix}  {meta}"]


def _display_title(it: dict, title_max_len: int | None = None) -> str:
    display_title = it.get("canonical_title") or it.get("title_render") or it.get("title") or ""
    if title_max_len and title_max_len > 0:
        display_title = _truncate_display_title(display_title, title_max_len)
    return _escape_md(display_title)


def _meta_parts(
    it: dict,
    cfg: Dict,
    badges_cfg: Dict,
    context: str,
    source_domain: str | None = None,
) -> List[str]:
    badges = _build_badges(it, badges_cfg, context)
    if context == "admin":
        parts = [badges]
    else:
        parts = [_status_pill(it), badges]
    omit_docs_domain = context == "docs" and bool(cfg.get("docsOmitDomInBullets", True))
    if source_domain and not omit_docs_domain:
        parts.append(_escape_md(source_domain))
    return [p for p in parts if p]


def _truncate_display_title(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    truncated = text[: max_len - 1].rstrip()
    return f"{truncated}…" if truncated else "…"


def _escape_md_url(url: str) -> str:
    if not url:
        return ""
    # Encode characters that can break markdown link destinations (notably whitespace and parentheses).
    return quote(url, safe=":/?#[]@!$&'*+,;=%-._~")


def _sort_items_alpha(items: List[dict]) -> List[dict]:
    def key(it: dict):
        title = it.get("canonical_title") or it.get("title_render") or it.get("title") or ""
        url = it.get("url") or ""
        return (title.lower(), url)

    return sorted(items, key=key)


def _kind_display_label(kind: str) -> str:
    k = (kind or "").lower()
    if k == "docs":
        return "Docs"
    if k == "article":
        return "Articles"
    if k == "paper":
        return "Papers"
    if k == "music":
        return "Music"
    if k == "spec":
        return "Specs"
    return "Other"


def _group_oneoffs_by_kind(flat_singletons: List[Tuple[str, dict]]) -> List[Tuple[str, List[Tuple[str, dict]]]]:
    grouped: Dict[str, List[Tuple[str, dict]]] = {}
    for source_domain, it in flat_singletons:
        label = _kind_display_label(it.get("kind") or "")
        grouped.setdefault(label, []).append((source_domain, it))

    order = ["Docs", "Articles", "Papers", "Music", "Specs", "Other"]
    result: List[Tuple[str, List[Tuple[str, dict]]]] = []
    for label in order:
        arr = grouped.get(label, [])
        if not arr:
            continue
        arr_sorted = sorted(
            arr,
            key=lambda pair: (
                (
                    pair[1].get("canonical_title")
                    or pair[1].get("title_render")
                    or pair[1].get("title")
                    or ""
                ).lower(),
                pair[0].lower(),
                pair[1].get("url") or "",
            ),
        )
        result.append((label, arr_sorted))
    return result


def _sort_oneoffs_alpha(flat_singletons: List[Tuple[str, dict]]) -> List[Tuple[str, dict]]:
    return sorted(
        flat_singletons,
        key=lambda pair: (
            (
                pair[1].get("canonical_title")
                or pair[1].get("title_render")
                or pair[1].get("title")
                or ""
            ).lower(),
            pair[1].get("url") or "",
        ),
    )


def _group_oneoffs_by_energy(flat_singletons: List[Tuple[str, dict]]) -> List[Tuple[str, List[Tuple[str, dict]]]]:
    grouped: Dict[str, List[Tuple[str, dict]]] = {"Deep Reads": [], "Quick References": []}
    for source_domain, it in flat_singletons:
        label = "Deep Reads" if _is_deep_read(it) else "Quick References"
        grouped[label].append((source_domain, it))

    result: List[Tuple[str, List[Tuple[str, dict]]]] = []
    for label in ("Deep Reads", "Quick References"):
        arr = grouped[label]
        if not arr:
            continue
        arr_sorted = sorted(
            arr,
            key=lambda pair: (
                (
                    pair[1].get("canonical_title")
                    or pair[1].get("title_render")
                    or pair[1].get("title")
                    or ""
                ).lower(),
                pair[0].lower(),
                pair[1].get("url") or "",
            ),
        )
        result.append((label, arr_sorted))
    return result


def _is_deep_read(item: dict) -> bool:
    return _effort_band(item) == "deep"
