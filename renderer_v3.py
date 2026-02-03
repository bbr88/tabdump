"""TabDump Pretty Renderer v3.2 — domain-first Markdown dashboard."""

from __future__ import annotations

import datetime as _dt
import re
from collections import Counter
from typing import Dict, Iterable, List, Tuple
from urllib.parse import urlparse

# ------------------------------ Config ------------------------------ #

DEFAULT_CFG: Dict = {
    "rendererVersion": "3.2.0",
    "titleMaxLen": 96,
    "stripWwwForGrouping": True,
    "includeFocusLine": True,
    "frontmatterInclude": [
        "dump_date",
        "tab_count",
        "top_domains",
        "top_kinds",
        "status",
        "renderer",
        "source",
        "deduped",
    ],
    "highPriorityLimit": 5,
    "highPriorityMinScore": 4,
    "highPriorityMinIntentConfidence": 0.70,
    "highPriorityEligibleCategories": ["docs_site", "blog", "code_host"],
    "includeQuickWins": True,
    "quickWinsMaxItems": 15,
    "quickWinsOverflowToBacklog": True,
    "backlogMaxItems": 50,
    "adminAlwaysLast": True,
    "adminVerboseBullets": True,
    "groupingMode": "domain_first",
    "groupWithinSectionsBy": ["domain_category", "domain_display"],
    "compactBullets": True,
    "includeInlineBadges": True,
    "includeInlineTopicIfAvailable": False,
    "includeDetailTopicIfAvailable": False,
    "skipPrefixes": [
        "chrome://",
        "chrome-extension://",
        "about:",
        "file://",
        "safari://",
        "safari-web-extension://",
    ],
    "chatDomains": ["chatgpt.com", "gemini.google.com", "claude.ai", "copilot.microsoft.com"],
    "codeHostDomains": ["github.com", "gitlab.com", "bitbucket.org"],
    "videoDomains": ["youtube.com", "www.youtube.com", "vimeo.com"],
    "docsDomainPrefix": "docs.",
    "docsPathHints": ["/docs/", "/documentation/", "/reference/", "/guides/"],
    "blogPathHints": ["/blog/", "/posts/", "/articles/"],
    "authPathHints": [
        "/api-keys",
        "apikey",
        "api_key",
        "token",
        "oauth",
        "signin",
        "sign-in",
        "login",
        "sso",
        "session",
        "/credentials",
    ],
    "consoleDomains": ["console.aws.amazon.com", "console.cloud.google.com", "portal.azure.com"],
    "emptyBucketMessage": "_(empty)_",
}

ALLOWED_KINDS = {"admin", "paper", "docs", "spec", "article", "video", "repo", "tool", "misc"}

KIND_PRIORITY = ["paper", "spec", "docs", "repo", "article", "video", "tool", "misc", "admin"]
KIND_PRIORITY_INDEX = {k: i for i, k in enumerate(KIND_PRIORITY)}

DOMAIN_CATEGORY_ORDER = ["docs_site", "blog", "code_host", "console", "generic", "video"]
ADMIN_CATEGORY_ORDER = ["admin_auth", "admin_chat", "admin_local", "admin_internal"]

AGGREGATOR_MARKERS = ["trending", "top", "best of", "weekly", "digest", "list of", "directory"]
DEPTH_HINTS = ["/reference/", "/docs/", "/guide/", "/internals/", "/config", "/api-reference/"]

SECTION_ORDER = ["HIGH", "MEDIA", "REPOS", "TOOLS", "DOCS", "QUICK", "BACKLOG", "ADMIN"]


# ------------------------------ Public API ------------------------------ #

def render_markdown(payload: dict, cfg_override: Dict | None = None, cfg: Dict | None = None) -> str:
    """Render payload into Obsidian-friendly Markdown following v3.2 spec.

    `cfg_override` is kept for API compatibility with v3; `cfg` is an alias.
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
    merged = dict(DEFAULT_CFG)
    if payload_cfg:
        merged.update(payload_cfg)
    if override_cfg:
        merged.update(override_cfg)
    return merged


# ------------------------------ Normalization ------------------------------ #

def _normalize_items(items_raw: List[dict], cfg: Dict) -> Tuple[List[dict], int]:
    seen_urls = set()
    deduped = 0
    normalized: List[dict] = []
    strip_www = bool(cfg.get("stripWwwForGrouping", True))

    for raw in items_raw:
        url = str(raw.get("url", "")).strip()
        if not url:
            continue
        if url in seen_urls:
            deduped += 1
            continue
        seen_urls.add(url)

        title_raw = str(raw.get("title", "") or "")
        title_norm = _normalize_title(title_raw)
        if not title_norm:
            continue
        title_render = _truncate(title_norm, int(cfg.get("titleMaxLen", 96)))

        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        domain_display = hostname
        if strip_www and domain_display.startswith("www."):
            domain_display = domain_display[4:]
        domain_display = domain_display or "unknown"
        path = parsed.path or ""

        flags_raw = raw.get("flags") or {}
        browser = str(raw.get("browser") or "unknown").lower()
        intent = _normalize_intent(raw.get("intent"))
        provided_kind = str(raw.get("kind") or "").strip().lower()
        topics = raw.get("topics") if isinstance(raw.get("topics"), list) else []

        domain_category = _classify_domain(
            url,
            parsed,
            domain_display,
            path,
            flags_raw,
            cfg,
        )
        kind_norm = _derive_kind(domain_category, provided_kind, url)

        normalized.append(
            {
                "url": url,
                "title": title_norm,
                "title_render": title_render,
                "domain": domain_display,
                "domain_raw": hostname or "unknown",
                "domain_category": domain_category,
                "path": path,
                "flags": _normalize_flags(flags_raw),
                "browser": browser or "unknown",
                "intent": intent,
                "topics": topics,
                "provided_kind": provided_kind,
                "kind": kind_norm,
            }
        )

    return normalized, deduped


def _normalize_title(title: str) -> str:
    title = title.replace("\r\n", "\n").replace("\r", "\n")
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    truncated = text[: max_len - 1].rstrip()
    return f"{truncated}…" if truncated else "…"


def _normalize_intent(intent_val) -> Dict:
    if isinstance(intent_val, dict):
        action = str(intent_val.get("action") or "").strip().lower()
        conf = intent_val.get("confidence", 0.0)
    else:
        action = ""
        conf = 0.0
    try:
        conf = float(conf)
    except Exception:
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    return {"action": action, "confidence": conf}


def _normalize_flags(flags_raw: Dict) -> Dict:
    return {
        "is_local": bool(flags_raw.get("is_local")),
        "is_auth": bool(flags_raw.get("is_auth")),
        "is_chat": bool(flags_raw.get("is_chat")),
        "is_internal": bool(flags_raw.get("is_internal")),
    }


# ------------------------------ Classification ------------------------------ #

def _classify_domain(
    url: str,
    parsed,
    domain_display: str,
    path: str,
    flags: Dict,
    cfg: Dict,
) -> str:
    lower_url = url.lower()
    hostname = domain_display.lower()

    # Admin forcing
    if flags.get("is_local") or hostname in {"localhost", "127.0.0.1"} or parsed.scheme == "file":
        return "admin_local"
    if flags.get("is_internal") or any(lower_url.startswith(p.lower()) for p in cfg.get("skipPrefixes", [])):
        return "admin_internal"
    if flags.get("is_chat") or hostname in {d.lower() for d in cfg.get("chatDomains", [])}:
        return "admin_chat"
    if flags.get("is_auth") or hostname == "accounts.google.com" or _contains_any(lower_url, cfg.get("authPathHints", [])):
        return "admin_auth"

    # Non-admin categories
    if hostname in {d.lower() for d in cfg.get("codeHostDomains", [])}:
        return "code_host"
    if hostname in {d.lower() for d in cfg.get("videoDomains", [])}:
        return "video"
    if hostname in {d.lower() for d in cfg.get("consoleDomains", [])}:
        return "console"
    if hostname.startswith(str(cfg.get("docsDomainPrefix", "docs."))):
        return "docs_site"
    if _contains_any(lower_url, cfg.get("docsPathHints", [])):
        return "docs_site"
    if _contains_any(lower_url, cfg.get("blogPathHints", [])):
        return "blog"
    return "generic"


def _contains_any(text: str, patterns: Iterable[str]) -> bool:
    for p in patterns or []:
        if p.lower() in text:
            return True
    return False


def _derive_kind(domain_category: str, provided_kind: str, url: str) -> str:
    lower_url = url.lower()
    if domain_category.startswith("admin_"):
        return "admin"
    if lower_url.endswith(".pdf"):
        return "paper"
    if domain_category == "video":
        return "video"
    if domain_category == "code_host":
        return "repo"
    if domain_category in {"docs_site", "blog"}:
        return "docs"
    if provided_kind in ALLOWED_KINDS:
        return provided_kind
    return "article"


# ------------------------------ Buckets ------------------------------ #

def _assign_buckets(items: List[dict], cfg: Dict) -> Dict[str, List[dict]]:
    buckets: Dict[str, List[dict]] = {name: [] for name in SECTION_ORDER}

    for item in items:
        bucket = _bucket_for_item(item, cfg)
        buckets[bucket].append(item)

    # Quick wins overflow handling
    if cfg.get("includeQuickWins", True):
        quick_limit = int(cfg.get("quickWinsMaxItems", 15))
        quick_items = buckets["QUICK"]
        if len(quick_items) > quick_limit:
            overflow = quick_items[quick_limit:]
            buckets["QUICK"] = quick_items[:quick_limit]
            if cfg.get("quickWinsOverflowToBacklog", True):
                backlog_cap = int(cfg.get("backlogMaxItems", 50))
                buckets["BACKLOG"] = overflow[:backlog_cap]
            else:
                buckets["BACKLOG"] = []
    else:
        # If quick wins disabled, collapse QUICK into BACKLOG for visibility
        buckets["BACKLOG"] = buckets["QUICK"]
        buckets["QUICK"] = []

    # Ensure keys exist even if unused
    for name in SECTION_ORDER:
        buckets.setdefault(name, [])
    return buckets


def _bucket_for_item(item: dict, cfg: Dict) -> str:
    domain_category = item.get("domain_category") or ""
    kind = item.get("kind") or ""
    provided_kind = item.get("provided_kind") or ""
    path = item.get("path") or ""

    if domain_category.startswith("admin_"):
        return "ADMIN"
    if kind == "video":
        return "MEDIA"
    if domain_category == "code_host" and _looks_like_repo_path(path):
        return "REPOS"
    if provided_kind == "tool" or domain_category == "console":
        return "TOOLS"
    if kind in {"paper", "docs", "spec", "article"}:
        return "DOCS"
    return "QUICK"


def _looks_like_repo_path(path: str) -> bool:
    parts = [p for p in (path or "").split("/") if p]
    return len(parts) >= 2


# ------------------------------ High Priority ------------------------------ #

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
    action = intent.get("action") or ""
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

    # Intent action
    if action in {"implement", "build", "debug", "decide"}:
        score += 2
    elif action in {"learn", "reference", "explore"}:
        score += 1
    elif action in {"skim", "entertain", "relax", "ephemeral"}:
        score -= 2

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


# ------------------------------ Rendering ------------------------------ #

def _render_md(state: Dict) -> str:
    cfg = state["cfg"]
    buckets = state["buckets"]
    meta = state["meta"]
    counts = state["counts"]
    items = state["items"]
    deduped = state["deduped_count"]

    fm_lines = _frontmatter(meta, counts, items, deduped, cfg)
    dump_date = _dump_date(meta)

    lines: List[str] = []
    lines.extend(fm_lines)
    lines.append("")
    lines.append(f"# 📑 Tab Dump: {dump_date}")
    if cfg.get("includeFocusLine", True):
        lines.append(f"> **Focus:** {_focus_line(items)}")
    lines.append("")

    lines.extend(_render_sections(buckets, cfg))

    md = "\n".join(lines).rstrip() + "\n"
    _validate_rendered(md, buckets)
    return md


def _frontmatter(meta: Dict, counts: Dict, items: List[dict], deduped: int, cfg: Dict) -> List[str]:
    fields = []
    include = cfg.get("frontmatterInclude", [])
    if "dump_date" in include:
        fields.append(("dump_date", _dump_date(meta)))
    if "tab_count" in include:
        fields.append(("tab_count", int(counts.get("total") or len(items))))
    if "top_domains" in include:
        fields.append(("top_domains", ", ".join(_top_domains(items, 5))))
    if "top_kinds" in include:
        fields.append(("top_kinds", ", ".join(_top_kinds(items, 3))))
    if "status" in include:
        fields.append(("status", "📥 Inbox"))
    if "renderer" in include:
        fields.append(("renderer", "tabdump-pretty-v3.2"))
    if "source" in include:
        fields.append(("source", str(meta.get("source") or "")))
    if "deduped" in include:
        fields.append(("deduped", deduped))

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
    m = re.search(r"(\d{4}-\d{2}-\d{2})", created)
    if m:
        return m.group(1)
    try:
        dt = _dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except Exception:
        return created.split("T")[0].split(" ")[0]


def _render_sections(buckets: Dict[str, List[dict]], cfg: Dict) -> List[str]:
    lines: List[str] = []
    for name in SECTION_ORDER:
        start_len = len(lines)
        items = buckets.get(name, [])
        if name == "HIGH":
            lines.extend(_render_high(items, cfg))
        elif name == "MEDIA":
            lines.extend(_render_callout("📺 Media Queue", "[!video]- Expand Watch List", items, cfg))
        elif name == "REPOS":
            lines.extend(_render_callout("🏗 Repos", "[!code]- View Repositories", items, cfg))
        elif name == "TOOLS":
            lines.extend(_render_callout("🧰 Tools", "[!note]- Expand Tools", items, cfg))
        elif name == "DOCS":
            lines.extend(_render_callout("📚 Docs & Reading", "[!info]- View Documentation", items, cfg))
        elif name == "QUICK":
            if cfg.get("includeQuickWins", True):
                lines.extend(_render_callout("🧹 Quick Wins", "[!tip]- Expand Quick Wins", items, cfg))
            else:
                continue
        elif name == "BACKLOG":
            if items:
                lines.extend(_render_callout("🗃 Backlog", "[!quote]- Expand Backlog", items, cfg))
        elif name == "ADMIN":
            lines.extend(_render_callout("🔐 Tools & Admin", "[!warning]- Sensitive/Administrative", items, cfg, admin=True))
        if len(lines) > start_len:
            lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _render_high(items: List[dict], cfg: Dict) -> List[str]:
    lines = ["## 🔥 High Priority", "*Auto-selected “do next” items (no manual priority).*"]
    if not items:
        lines.append(cfg.get("emptyBucketMessage", "_(empty)_"))
        return lines
    for it in _sort_items(items, admin=False):
        lines.append(_format_bullet(it, prefix="", admin=False, cfg=cfg, in_callout=False))
    return lines


def _render_callout(title: str, callout: str, items: List[dict], cfg: Dict, admin: bool = False) -> List[str]:
    count = len(items)
    lines = [f"## {title}", f"> {callout} ({count})"]
    if not items:
        lines.append(f"> {cfg.get('emptyBucketMessage', '_(empty)_')}")
        return lines

    grouped = _group_items(items, admin)
    for heading, group_items in grouped:
        lines.append(f"> ### {heading}")
        for it in _sort_items(group_items, admin=admin):
            lines.append(_format_bullet(it, prefix='> ', admin=admin, cfg=cfg, in_callout=True))
    return lines


def _group_items(items: List[dict], admin: bool) -> List[Tuple[str, List[dict]]]:
    grouped: Dict[Tuple[str, str], List[dict]] = {}
    for it in items:
        key = (it.get("domain_category"), it.get("domain"))
        grouped.setdefault(key, []).append(it)

    def key_sort(kv):
        (domain_cat, domain_disp) = kv[0]
        order_map = ADMIN_CATEGORY_ORDER if admin else DOMAIN_CATEGORY_ORDER
        idx = order_map.index(domain_cat) if domain_cat in order_map else len(order_map)
        return (idx, domain_disp or "", domain_cat or "")

    result = []
    for key, group in sorted(grouped.items(), key=key_sort):
        cat, dom = key
        heading = f"{cat} • {dom}" if admin else dom
        result.append((heading, group))
    return result


def _format_bullet(it: dict, prefix: str, admin: bool, cfg: Dict, in_callout: bool) -> str:
    title = it.get("title_render") or it.get("title") or ""
    url = it.get("url") or ""
    domain = it.get("domain") or "unknown"
    kind = it.get("kind") or "misc"
    browser = it.get("browser") or "unknown"
    domain_category = it.get("domain_category") or ""

    if admin and cfg.get("adminVerboseBullets", True):
        chips = [
            f"(kind:: {kind})",
            f"(src:: {browser})",
            f"(dom:: {domain})",
            f"(cat:: {domain_category})",
        ]
        return f"{prefix}- [ ] **{title}** ([Link]({url})) • " + " • ".join(chips)

    # Non-admin / compact bullets
    parts = []
    if cfg.get("includeInlineBadges", True):
        parts.append(f"kind:: {kind}")
        parts.append(f"dom:: {domain}")
    if cfg.get("includeInlineTopicIfAvailable", False) and it.get("topics"):
        slug = _tagify((it["topics"][0] or {}).get("slug") or "")
        parts.append(f"topic:: #{slug}")

    badge = ""
    if parts:
        badge = " *(" + " • ".join(parts) + ")*"

    return f"{prefix}- [ ] **{title}** ([Link]({url}))" + badge


def _sort_items(items: List[dict], admin: bool) -> List[dict]:
    order_map = ADMIN_CATEGORY_ORDER if admin else DOMAIN_CATEGORY_ORDER

    def key(it: dict):
        domain_cat = it.get("domain_category") or ""
        domain = it.get("domain") or ""
        conf = float((it.get("intent") or {}).get("confidence", -1.0))
        title = it.get("title_render") or it.get("title") or ""
        idx = order_map.index(domain_cat) if domain_cat in order_map else len(order_map)
        return (idx, domain.lower(), -conf, title.lower())

    return sorted(items, key=key)


# ------------------------------ Stats ------------------------------ #

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
            "console": "tools",
            "generic": "browsing",
        }
        return mapping.get(cat, cat or "varied")

    cats_str = " + ".join(cat_display(c) for c in top_cats) if top_cats else "varied"
    doms_str = " and ".join(top_doms) if top_doms else "various domains"
    return f"Mostly {cats_str} across {doms_str}."


def _tagify(slug: str) -> str:
    tag = re.sub(r"[^a-zA-Z0-9]+", "-", (slug or "").lower())
    tag = re.sub(r"-+", "-", tag).strip("-")
    return tag or "other"


# ------------------------------ Validation ------------------------------ #

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


def _validate_rendered(md: str, buckets: Dict[str, List[dict]]) -> None:
    # Section order
    positions = []
    for header in ["## 🔥 High Priority", "## 📺 Media Queue", "## 🏗 Repos", "## 🧰 Tools", "## 📚 Docs & Reading"]:
        pos = md.find(header)
        if pos == -1:
            raise ValueError(f"Missing section {header}")
        positions.append(pos)
    # Quick Wins optional but included by default
    if "## 🧹 Quick Wins" in md:
        positions.append(md.find("## 🧹 Quick Wins"))
    if "## 🗃 Backlog" in md:
        positions.append(md.find("## 🗃 Backlog"))
    admin_pos = md.find("## 🔐 Tools & Admin")
    if admin_pos == -1:
        raise ValueError("Missing section Admin")
    positions.append(admin_pos)
    if positions != sorted(positions):
        raise ValueError("Section order incorrect")


# ------------------------------------------------------------------------ #
