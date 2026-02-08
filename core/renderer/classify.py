"""Domain/category classification and kind derivation."""

from __future__ import annotations

import re
from typing import Dict, Iterable

from core.tab_policy.matching import host_matches_base

from .config import ALLOWED_KINDS


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


def _classify_domain(
    url: str,
    parsed,
    domain_display: str,
    flags: Dict,
    cfg: Dict,
) -> str:
    lower_url = url.lower()
    hostname = domain_display.lower()
    suffix_match = True

    # Admin forcing
    if flags.get("is_local") or hostname in {"localhost", "127.0.0.1"} or parsed.scheme == "file":
        return "admin_local"
    if flags.get("is_internal") or any(lower_url.startswith(p.lower()) for p in cfg.get("skipPrefixes", [])):
        return "admin_internal"
    if flags.get("is_chat") or any(
        host_matches_base(hostname, str(base).lower(), enable_suffix=suffix_match) for base in cfg.get("chatDomains", [])
    ):
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
    if any(
        host_matches_base(hostname, str(base).lower(), enable_suffix=suffix_match)
        for base in cfg.get("codeHostDomains", [])
    ):
        return "code_host"
    if any(
        host_matches_base(hostname, str(base).lower(), enable_suffix=suffix_match)
        for base in cfg.get("videoDomains", [])
    ):
        return "video"
    if any(
        host_matches_base(hostname, str(base).lower(), enable_suffix=suffix_match)
        for base in cfg.get("consoleDomains", [])
    ):
        return "console"
    if hostname.startswith(str(cfg.get("docsDomainPrefix", "docs."))):
        return "docs_site"
    if _contains_any(lower_url, cfg.get("docsPathHints", [])):
        return "docs_site"
    if _contains_any(lower_url, cfg.get("blogPathHints", [])):
        return "blog"
    return "generic"


def _derive_kind(domain_category: str, provided_kind: str, url: str) -> str:
    lower_url = url.lower()
    if provided_kind in {"local", "auth", "internal"}:
        return "admin"
    if provided_kind in ALLOWED_KINDS:
        return provided_kind
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
    return "article"
