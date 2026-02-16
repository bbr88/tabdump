"""Normalization and canonicalization of payload items."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple
from urllib.parse import unquote, urlparse

from core.tab_policy.actions import canonical_action

from .classify import _classify_domain, _derive_kind


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

        browser = str(raw.get("browser") or "unknown").lower()
        intent = _normalize_intent(raw.get("intent"))
        effort = _normalize_effort(raw.get("effort"))
        provided_kind = str(raw.get("kind") or "").strip().lower()
        flags_raw = raw.get("flags") or {}
        flags = _normalize_flags(flags_raw, provided_kind=provided_kind)
        topics = raw.get("topics") if isinstance(raw.get("topics"), list) else []

        domain_category = _classify_domain(
            url,
            parsed,
            domain_display,
            flags,
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
                "flags": flags,
                "browser": browser or "unknown",
                "intent": intent,
                "effort": effort,
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
            for suffix in suffixes:
                if txt.endswith(suffix):
                    txt = txt[: -len(suffix)].rstrip()
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

    if domain_display == "github.com":
        blob_filename_title = _github_blob_filename_title(path, title, title_norm, domain_display)
        if blob_filename_title:
            title = blob_filename_title

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


def _github_blob_filename_title(path: str, current_title: str, title_norm: str, domain_display: str) -> str:
    parts = [p for p in (path or "").split("/") if p]
    if len(parts) < 5:
        return ""
    if parts[2] != "blob":
        return ""

    slug = f"{parts[0]}/{parts[1]}"
    filename = unquote(parts[-1]).strip()
    if not filename:
        return ""

    current_l = current_title.strip().lower()
    title_l = title_norm.strip().lower()
    domain_l = domain_display.strip().lower()
    triggers = {
        f"{slug} — file",
        slug,
        domain_l,
        f"www.{domain_l}",
    }
    if current_l in triggers or title_l in triggers or title_l.startswith("github -"):
        return f"{slug} — {filename}"
    return ""


def _normalize_intent(intent_val) -> Dict:
    if isinstance(intent_val, dict):
        action = canonical_action(intent_val.get("action") or "")
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


def _normalize_effort(value: object) -> str:
    if not isinstance(value, str):
        return ""
    candidate = value.strip().lower()
    if candidate in {"quick", "medium", "deep"}:
        return candidate
    return ""


def _normalize_flags(flags_raw: Dict, provided_kind: str = "") -> Dict:
    flags = {
        "is_local": bool(flags_raw.get("is_local")),
        "is_auth": bool(flags_raw.get("is_auth")),
        "is_chat": bool(flags_raw.get("is_chat")),
        "is_internal": bool(flags_raw.get("is_internal")),
    }
    kind = str(provided_kind or "").strip().lower()
    if kind == "local":
        flags["is_local"] = True
    elif kind == "auth":
        flags["is_auth"] = True
    elif kind == "internal":
        flags["is_internal"] = True
    return flags
