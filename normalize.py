"""Normalization helpers for TabDump renderer v3."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple
from urllib.parse import urlparse


ALLOWED_KINDS = {"paper", "docs", "spec", "article", "video", "repo", "tool", "misc", "local", "auth", "internal"}
ALLOWED_ACTIONS = {
    "learn",
    "debug",
    "implement",
    "decide",
    "reference",
    "lookup",
    "explore",
    "chat",
    "relax",
    "entertain",
    "ephemeral",
}


def normalize_items(items: List[dict], cfg: Dict, meta: Dict) -> Tuple[List[dict], int]:
    """Return normalized items list and dedup count."""
    norm_items: List[dict] = []
    seen_urls = set()
    deduped = 0
    skip_prefixes = list(cfg.get("skipPrefixes", [])) + list(meta.get("skipPrefixes", []))
    chat_domains = set(cfg.get("chatDomains", []))
    title_max = int(cfg.get("titleMaxLen", 120))
    strip_www = bool(cfg.get("stripWwwForGrouping", True))

    for raw in items:
        url = str(raw.get("url", "")).strip()
        if not url:
            continue
        if url in seen_urls:
            deduped += 1
            continue
        seen_urls.add(url)

        title_raw = str(raw.get("title", "") or "")
        title = _normalize_title(title_raw)
        if not title:
            continue

        parsed = urlparse(url)
        domain_raw = parsed.hostname or ""
        domain = domain_raw
        if strip_www and domain.startswith("www."):
            domain = domain[4:]

        flags = _normalize_flags(raw.get("flags") or {}, url, parsed, domain_raw, skip_prefixes, chat_domains)
        kind = _normalize_kind(raw.get("kind"), flags, url.lower(), domain)
        browser = _normalize_browser(raw.get("browser"))

        topics = _normalize_topics(raw.get("topics"), cfg)
        topic_primary = _primary_topic(topics)

        intent = _normalize_intent(raw.get("intent"), kind)

        title_render = _truncate_title(title, title_max)

        norm_items.append(
            {
                "url": url,
                "title": title,
                "title_render": title_render,
                "browser": browser,
                "domain": domain,
                "domain_raw": domain_raw,
                "kind": kind,
                "intent": intent,
                "topics": topics,
                "topic_primary": topic_primary,
                "flags": flags,
                "window_id": str(raw.get("window_id")) if raw.get("window_id") is not None else None,
            }
        )

    return norm_items, deduped


def _normalize_title(title: str) -> str:
    title = title.replace("\r\n", "\n").replace("\r", "\n")
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _truncate_title(title: str, max_len: int) -> str:
    if len(title) <= max_len:
        return title
    truncated = title[: max_len - 1].rstrip()
    return f"{truncated}…" if truncated else "…"


def _normalize_browser(value) -> str:
    if value is None:
        return "unknown"
    v = str(value).strip().lower()
    return v or "unknown"


def _normalize_flags(
    flags: Dict, url: str, parsed, domain_raw: str, skip_prefixes: List[str], chat_domains: set
) -> Dict[str, bool]:
    lower_url = url.lower()
    is_local = bool(flags.get("is_local")) or domain_raw in {"localhost", "127.0.0.1"} or parsed.scheme == "file"
    is_chat = bool(flags.get("is_chat")) or (domain_raw in chat_domains)
    is_internal = (
        bool(flags.get("is_internal"))
        or parsed.scheme in {"chrome", "about", "safari-web-extension", "chrome-extension"}
        or any(lower_url.startswith(p.lower()) for p in skip_prefixes)
    )
    auth_markers = [
        "/api-keys",
        "apikey",
        "api_key",
        "token",
        "signin",
        "sign-in",
        "login",
        "oauth",
        "sso",
        "session",
    ]
    is_auth = bool(flags.get("is_auth")) or "accounts.google.com" in domain_raw.lower() or any(
        marker in lower_url for marker in auth_markers
    )
    return {
        "is_local": bool(is_local),
        "is_auth": bool(is_auth),
        "is_chat": bool(is_chat),
        "is_internal": bool(is_internal),
    }


def _normalize_kind(raw_kind, flags: Dict[str, bool], url_lower: str, domain: str) -> str:
    if flags["is_local"]:
        return "local"
    if flags["is_auth"]:
        return "auth"
    if flags["is_internal"]:
        return "internal"
    if url_lower.endswith(".pdf"):
        return "paper"
    if "youtube.com" in domain or "youtu.be" in domain:
        return "video"
    if domain == "github.com":
        return "repo"
    if raw_kind:
        k = str(raw_kind).strip().lower()
        if k in ALLOWED_KINDS:
            return k
    return "article"


def _normalize_topics(value, cfg: Dict) -> List[Dict]:
    topics: List[Dict] = []
    if not isinstance(value, list):
        value = []
    min_conf = float(cfg.get("minTopicConfidence", 0.0))
    for raw in value:
        if not isinstance(raw, dict):
            continue
        slug = str(raw.get("slug") or raw.get("title") or "").strip()
        title = str(raw.get("title") or "").strip()
        conf = raw.get("confidence", 0.5)
        try:
            conf = float(conf)
        except Exception:
            conf = 0.5
        conf = max(0.0, min(1.0, conf))
        if conf < min_conf:
            continue
        if not slug and title:
            slug = _slug_from_title(title)
        if not title and slug:
            title = _title_from_slug(slug)
        if not slug and not title:
            slug = "other"
            title = "Other"
        topics.append({"slug": slug, "title": title, "confidence": conf})
    return topics


def _primary_topic(topics: List[Dict]) -> Dict:
    if not topics:
        return {"slug": "other", "title": "Other", "confidence": 0.0}
    topics_sorted = sorted(topics, key=lambda t: (-t["confidence"], t["slug"]))
    return topics_sorted[0]


def _normalize_intent(intent_value, kind: str) -> Dict:
    default_action = "learn"
    if kind in {"repo", "tool"}:
        default_action = "explore"
    elif kind == "video":
        default_action = "learn"
    elif kind in {"local", "auth", "internal"}:
        default_action = "ephemeral"
    elif kind == "misc":
        default_action = "relax"

    if isinstance(intent_value, dict):
        action = str(intent_value.get("action") or "").strip().lower()
        confidence = intent_value.get("confidence", 0.6)
    else:
        action = ""
        confidence = 0.6

    if action not in ALLOWED_ACTIONS:
        action = default_action
    try:
        confidence = float(confidence)
    except Exception:
        confidence = 0.6
    confidence = max(0.0, min(1.0, confidence))

    return {"action": action, "confidence": confidence}


def _slug_from_title(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower())
    return slug.strip("-") or "other"


def _title_from_slug(slug: str) -> str:
    parts = re.split(r"[-_/]", slug)
    return " ".join(p.capitalize() for p in parts if p) or "Other"
