"""TabDump Pretty Renderer v3.2.4.1 — domain-first Markdown dashboard."""

from __future__ import annotations

import datetime as _dt
import re
from collections import Counter
from typing import Dict, Iterable, List, Tuple
from urllib.parse import urlparse

# ------------------------------ Config ------------------------------ #

DEFAULT_CFG: Dict = {
    "rendererVersion": "3.2.4.1",
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
    "adminVerboseBullets": False,
    "adminIncludeSrcWhenMultiBrowser": True,
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
    "authPathRegex": [
        "(?i)(^|/)(login|signin|sign-in|sso|oauth)(/|$)",
        "(?i)(^|/)(api-keys|credentials)(/|$)",
    ],
    "authContainsHintsSoft": ["apikey", "api_key", "token", "session"],
    "adminAuthRequiresStrongSignal": True,
    "consoleDomains": ["console.aws.amazon.com", "console.cloud.google.com", "portal.azure.com"],
    "emptyBucketMessage": "_(empty)_",
    "canonicalTitleEnabled": True,
    "canonicalTitleMaxLen": 88,
    "canonicalTitleStripSuffixes": [
        " - YouTube",
        " | YouTube",
        " · GitHub",
        " - GitHub",
        " | GitHub",
    ],
    "canonicalTitleStripPrefixesRegex": [
        "^\\(\\d+\\)\\s+",
    ],
    "canonicalTitleHostRules": {
        "youtube.com": {"stripSuffixes": [" - YouTube", " | YouTube"]},
        "github.com": {"preferRepoSlug": True},
    },
    "docsSubgroupByIntentWhenDomainCountGte": 4,
    "docsSubgroupOrder": ["implement", "debug", "decide", "build", "reference", "learn", "explore", "skim", "other"],
    "docsOmitDomInBullets": True,
    "docsOmitKindFor": ["docs", "article"],
    "docsIncludeSrcWhenMultiBrowser": False,
    "showDomChipInDomainGroupedSections": False,
    "showKindChipInSections": {"media": False, "repos": False, "tools": False, "docs": False},
    "quickWinsEnableMiniCategories": True,
    "quickWinsMiniCategories": ["leisure", "shopping", "misc"],
    "quickWinsDomainSuffixMatching": True,
    "render": {
        "badges": {
            "enabled": True,
            "maxPerBullet": 3,
            "includeTopicInHighPriority": True,
            "includeQuickWinsWhy": True,
        },
        "ordering": {
            "domains": {"byCountThenAlpha": True, "pinned": []},
            "items": {"alphaByTitleThenUrl": True},
        },
    },
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
        canonical_title = _canonical_title(title_norm, domain_display, path, cfg)

        normalized.append(
            {
                "url": url,
                "title": title_norm,
                "canonical_title": canonical_title,
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


def _canonical_title(title_norm: str, domain_display: str, path: str, cfg: Dict) -> str:
    if not cfg.get("canonicalTitleEnabled", True):
        return title_norm

    title = title_norm

    def strip_suffixes(txt: str, suffixes: List[str]) -> str:
        changed = True
        while changed:
            changed = False
            for s in suffixes:
                if txt.endswith(s):
                    txt = txt[: -len(s)].rstrip()
                    changed = True
        return txt

    # Global suffix stripping
    title = strip_suffixes(title, cfg.get("canonicalTitleStripSuffixes", []))

    # Prefix regex stripping
    for rx in cfg.get("canonicalTitleStripPrefixesRegex", []):
        title = re.sub(rx, "", title)

    host_rules = cfg.get("canonicalTitleHostRules", {}) or {}
    host_rule = host_rules.get(domain_display)
    if host_rule:
        title = strip_suffixes(title, host_rule.get("stripSuffixes", []))

    # GitHub repo slug preference
    if host_rule and host_rule.get("preferRepoSlug"):
        slug_title = _github_repo_slug_title(path, title_norm)
        if slug_title:
            title = slug_title

    title = re.sub(r"\s+", " ", title).strip()
    title = _truncate(title or title_norm, int(cfg.get("canonicalTitleMaxLen", 88)))
    return title or title_norm


def _github_repo_slug_title(path: str, title_norm: str) -> str:
    parts = [p for p in (path or "").split("/") if p]
    if len(parts) < 2:
        return ""
    slug = f"{parts[0]}/{parts[1]}"
    if len(parts) >= 3:
        third = parts[2]
        if third in {"issues", "pull", "pulls", "discussions", "wiki", "releases"}:
            slug = f"{slug} — {third}"
        elif third == "blob":
            slug = f"{slug} — file"
        elif third == "tree":
            slug = f"{slug} — tree"
    if len(title_norm) <= 50 and not title_norm.lower().startswith("github -"):
        return ""
    return slug


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

    # Admin auth strict detection
    auth_strong = flags.get("is_auth") or hostname == "accounts.google.com" or _matches_any_regex(
        parsed.path or "", cfg.get("authPathRegex", [])
    )
    auth_soft = _contains_any(lower_url, cfg.get("authContainsHintsSoft", []))
    require_strong = cfg.get("adminAuthRequiresStrongSignal", True)
    if auth_strong or (auth_soft and not require_strong):
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


def _matches_any_regex(text: str, patterns: Iterable[str]) -> bool:
    for rx in patterns or []:
        try:
            if re.search(rx, text):
                return True
        except re.error:
            continue
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
    multi_browser = len({it.get("browser") for it in items if it.get("browser")}) > 1
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

    lines.extend(_render_sections(buckets, cfg, multi_browser, badge_cfg, ordering_cfg))

    md = "\n".join(lines).rstrip() + "\n"
    _validate_rendered(md, buckets)
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
    m = re.search(r"(\d{4}-\d{2}-\d{2})", created)
    if m:
        return m.group(1)
    try:
        dt = _dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except Exception:
        return created.split("T")[0].split(" ")[0]


def _render_sections(
    buckets: Dict[str, List[dict]],
    cfg: Dict,
    multi_browser: bool,
    badge_cfg: Dict,
    ordering_cfg: Dict,
) -> List[str]:
    lines: List[str] = []
    for name in SECTION_ORDER:
        start_len = len(lines)
        items = buckets.get(name, [])
        if name == "HIGH":
            lines.extend(_render_high(items, cfg, badge_cfg))
        elif name == "MEDIA":
            lines.extend(
                _render_callout(
                    "📺 Media Queue",
                    "[!video]- Expand Watch List",
                    items,
                    cfg,
                    badge_cfg,
                    ordering_cfg,
                )
            )
        elif name == "REPOS":
            lines.extend(
                _render_callout(
                    "🏗 Repos",
                    "[!code]- View Repositories",
                    items,
                    cfg,
                    badge_cfg,
                    ordering_cfg,
                )
            )
        elif name == "TOOLS":
            lines.extend(
                _render_callout(
                    "🧰 Tools",
                    "[!note]- Expand Tools",
                    items,
                    cfg,
                    badge_cfg,
                    ordering_cfg,
                )
            )
        elif name == "DOCS":
            lines.extend(
                _render_docs_callout(
                    "📚 Docs & Reading",
                    "[!info]- View Documentation",
                    items,
                    cfg,
                    badge_cfg,
                    ordering_cfg,
                )
            )
        elif name == "QUICK":
            if cfg.get("includeQuickWins", True):
                lines.extend(
                    _render_quick_callout(
                        "🧹 Quick Wins",
                        "[!tip]- Expand Quick Wins",
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
                        "🗃 Backlog",
                        "[!quote]- Expand Backlog",
                        items,
                        cfg,
                        badge_cfg,
                        ordering_cfg,
                    )
                )
        elif name == "ADMIN":
            lines.extend(
                _render_callout(
                    "🔐 Tools & Admin",
                    "[!warning]- Sensitive/Administrative",
                    items,
                    cfg,
                    badge_cfg,
                    ordering_cfg,
                    admin=True,
                )
            )
        if len(lines) > start_len:
            lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _render_high(items: List[dict], cfg: Dict, badge_cfg: Dict) -> List[str]:
    lines = ["## 🔥 High Priority", "*Auto-selected “do next” items.*"]
    if not items:
        lines.append(cfg.get("emptyBucketMessage", "_(empty)_"))
        return lines
    for it in items:
        lines.append(_format_bullet(it, prefix="", cfg=cfg, badges_cfg=badge_cfg, context="high"))
    return lines


def _render_callout(
    title: str,
    callout: str,
    items: List[dict],
    cfg: Dict,
    badge_cfg: Dict,
    ordering_cfg: Dict,
    admin: bool = False,
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
            lines.append(_format_bullet(it, prefix="> ", cfg=cfg, badges_cfg=badge_cfg, context="admin" if admin else "group"))
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
    threshold = int(cfg.get("docsSubgroupByIntentWhenDomainCountGte", 4))
    order = cfg.get("docsSubgroupOrder", [])
    for heading, group_items in grouped:
        lines.append(f"> ### {heading}")
        if len(group_items) < threshold:
            for it in _sort_items_alpha(group_items):
                lines.append(_format_bullet(it, prefix="> ", cfg=cfg, badges_cfg=badge_cfg, context="docs"))
            continue

        # subgroup by intent
        buckets: Dict[str, List[dict]] = {}
        for it in group_items:
            bucket = _intent_subgroup((it.get("intent") or {}).get("action"), order)
            buckets.setdefault(bucket, []).append(it)
        for subgroup in order:
            if subgroup not in buckets:
                continue
            lines.append(f"> #### {subgroup.capitalize()}")
            for it in _sort_items_alpha(buckets[subgroup]):
                lines.append(_format_bullet(it, prefix="> ", cfg=cfg, badges_cfg=badge_cfg, context="docs"))
        # leftover
        for subgroup, arr in buckets.items():
            if subgroup in order:
                continue
            lines.append(f"> #### {subgroup.capitalize()}")
            for it in _sort_items_alpha(arr):
                lines.append(_format_bullet(it, prefix="> ", cfg=cfg, badges_cfg=badge_cfg, context="docs"))
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

    cats = {name: [] for name in cfg.get("quickWinsMiniCategories", ["leisure", "shopping", "misc"])}
    for it in items:
        cat, reason = _quick_mini_classify(it, cfg)
        it["quick_why"] = reason
        cats.setdefault(cat, []).append(it)

    order = ["leisure", "shopping", "misc"]
    for cat in order:
        arr = cats.get(cat, [])
        if not arr:
            continue
        lines.append(f"> ### {cat.capitalize()}")
        for it in _sort_items_alpha(arr):
            lines.append(_format_bullet(it, prefix="> ", cfg=cfg, badges_cfg=badge_cfg, context="quick"))
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


def _format_bullet(it: dict, prefix: str, cfg: Dict, badges_cfg: Dict, context: str) -> str:
    display_title = it.get("canonical_title") or it.get("title_render") or it.get("title") or ""
    display_title = _escape_md(display_title)
    url = it.get("url") or ""
    badges = _build_badges(it, cfg, badges_cfg, context)
    return f"{prefix}- [ ] **{display_title}** ([Link]({url})) · {badges}"


def _sort_items_alpha(items: List[dict]) -> List[dict]:
    def key(it: dict):
        title = it.get("canonical_title") or it.get("title_render") or it.get("title") or ""
        url = it.get("url") or ""
        return (title.lower(), url)

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


def _intent_subgroup(action: str, order: List[str]) -> str:
    action = (action or "").lower()
    mapping = {
        "implement": "implement",
        "build": "implement",
        "debug": "debug",
        "decide": "decide",
        "reference": "reference",
        "learn": "learn",
        "explore": "learn",
        "skim": "skim",
    }
    bucket = mapping.get(action, "other")
    return bucket if bucket in order else "other"

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


def _build_badges(item: dict, cfg: Dict, badges_cfg: Dict, context: str) -> str:
    max_badges = int(badges_cfg.get("maxPerBullet", 3))
    include_topic = bool(badges_cfg.get("includeTopicInHighPriority", True))
    include_why = bool(badges_cfg.get("includeQuickWinsWhy", True))

    badges: List[str] = [_primary_badge(item)]

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


LEISURE_DOMAINS = {
    "disneyplus.com",
    "netflix.com",
    "youtube.com",
    "youtu.be",
    "twitch.tv",
    "spotify.com",
    "primevideo.com",
    "hbomax.com",
    "hulu.com",
    "max.com",
    "paramountplus.com",
    "peacocktv.com",
    "soundcloud.com",
    "music.apple.com",
    "tv.apple.com",
    "music.youtube.com",
    "open.spotify.com",
    "letterboxd.com",
    "imdb.com",
    "myanimelist.net",
    "crunchyroll.com",
    "funimation.com",
    "kick.com",
    "vimeo.com",
    "deezer.com",
    "bandcamp.com",
    "reddit.com",
    "9gag.com",
    "4chan.org",
}
SHOPPING_DOMAINS = {
    "amazon.com",
    "noon.com",
    "aliexpress.com",
    "ebay.com",
    "walmart.com",
    "target.com",
    "bestbuy.com",
    "ikea.com",
    "etsy.com",
    "camelcamelcamel.com",
    "slickdeals.net",
    "shein.com",
    "zalando.com",
    "asos.com",
    "newegg.com",
    "flipkart.com",
    "shopify.com",
    "alibaba.com",
    "temu.com",
}
LEISURE_KEYWORDS = {
    "episode",
    "episodes",
    "watch",
    "watching",
    "trailer",
    "series",
    "movie",
    "film",
    "season",
    "playlist",
    "album",
    "track",
    "lyrics",
    "stream",
    "streaming",
    "listen",
    "full episode",
    "highlights",
    "live stream",
    "soundtrack",
    "imdb",
    "anime",
}
SHOPPING_KEYWORDS = {
    "buy",
    "price",
    "review",
    "reviews",
    "deal",
    "deals",
    "discount",
    "coupon",
    "promo",
    "shipping",
    "free shipping",
    "cart",
    "checkout",
    "sale",
    "order",
    "product",
    "specs",
    "compare",
    "alternatives",
    "shipping",
    "order",
}


def _host_matches_base(host: str, base: str, enable_suffix: bool) -> bool:
    if not host or not base:
        return False
    host_norm = host.lower()
    if host_norm.startswith("www."):
        host_norm = host_norm[4:]
    base_norm = base.lower()
    if host_norm == base_norm:
        return True
    return enable_suffix and host_norm.endswith("." + base_norm)


def _quick_mini_classify(it: dict, cfg: Dict) -> Tuple[str, str]:
    domain = (it.get("domain") or "").lower()
    title = (it.get("canonical_title") or it.get("title_render") or it.get("title") or "").lower()
    url_blob = (it.get("url") or "").lower()
    text_blob = f"{title} {url_blob}"
    suffix_ok = cfg.get("quickWinsDomainSuffixMatching", True)

    if (it.get("domain_category") or "").startswith("admin_"):
        return "misc", "admin_path"

    leisure_domain_hit = any(_host_matches_base(domain, base, suffix_ok) for base in LEISURE_DOMAINS)
    shopping_domain_hit = any(_host_matches_base(domain, base, suffix_ok) for base in SHOPPING_DOMAINS)

    leisure_kw_hit = any(k in text_blob for k in LEISURE_KEYWORDS)
    shopping_kw_hit = any(k in text_blob for k in SHOPPING_KEYWORDS)

    if shopping_domain_hit:
        return "shopping", "shopping_domain"
    if leisure_domain_hit:
        return "leisure", "leisure_domain"
    if shopping_kw_hit:
        return "shopping", "shopping_keyword"
    if leisure_kw_hit:
        return "leisure", "leisure_keyword"
    return "misc", "fallback_misc"


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
