"""Bucket assignment and quick-win classification."""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from core.tab_policy.matching import host_matches_base as _host_matches_base_shared

from .config import SECTION_ORDER


def _assign_buckets(items: List[dict], cfg: Dict) -> Dict[str, List[dict]]:
    buckets: Dict[str, List[dict]] = {name: [] for name in SECTION_ORDER}

    for item in items:
        bucket = _bucket_for_item(item, cfg)
        buckets[bucket].append(item)

    # Quick wins tightening + overflow handling
    if cfg.get("includeQuickWins", True):
        _tighten_quick_wins(buckets, cfg)
        quick_limit = int(cfg.get("quickWinsMaxItems", 15))
        quick_items = buckets["QUICK"]
        if len(quick_items) > quick_limit:
            overflow = quick_items[quick_limit:]
            buckets["QUICK"] = quick_items[:quick_limit]
            if cfg.get("quickWinsOverflowToBacklog", True):
                # Preserve all items to keep bucket coverage strict.
                buckets["BACKLOG"] = buckets.get("BACKLOG", []) + overflow
            else:
                buckets["BACKLOG"] = buckets.get("BACKLOG", [])
    else:
        # If quick wins disabled, collapse QUICK into BACKLOG for visibility
        buckets["BACKLOG"] = buckets["QUICK"]
        buckets["QUICK"] = []

    # Ensure keys exist even if unused
    for name in SECTION_ORDER:
        buckets.setdefault(name, [])
    return buckets


def _tighten_quick_wins(buckets: Dict[str, List[dict]], cfg: Dict) -> None:
    """Keep only explicit low-effort items in QUICK; move others to BACKLOG."""
    allowed_reasons = {
        str(reason).lower()
        for reason in cfg.get(
            "quickWinsLowEffortReasons",
            ["leisure_domain", "leisure_keyword", "shopping_domain", "shopping_keyword"],
        )
    }

    filtered: List[dict] = []
    moved_to_backlog: List[dict] = []
    for it in buckets.get("QUICK", []):
        cat, reason = _quick_mini_classify(it, cfg)
        it["quick_cat"] = str(cat).lower()
        it["quick_why"] = str(reason).lower()
        if it["quick_why"] in allowed_reasons:
            filtered.append(it)
        else:
            moved_to_backlog.append(it)

    buckets["QUICK"] = filtered
    if moved_to_backlog:
        buckets["BACKLOG"] = moved_to_backlog + buckets.get("BACKLOG", [])


def _bucket_for_item(item: dict, cfg: Dict) -> str:
    domain_category = item.get("domain_category") or ""
    kind = item.get("kind") or ""
    provided_kind = item.get("provided_kind") or ""
    path = item.get("path") or ""

    if domain_category.startswith("admin_") or kind == "admin" or provided_kind in {"local", "auth", "internal"}:
        return "ADMIN"
    if kind in {"video", "music"}:
        return "MEDIA"
    if kind == "repo" or (domain_category == "code_host" and _looks_like_repo_path(path)):
        return "REPOS"
    if _is_project_workspace(item, cfg):
        return "PROJECTS"
    if kind == "tool" or provided_kind == "tool" or domain_category == "console":
        return "TOOLS"
    if kind in {"paper", "docs", "spec", "article"}:
        return "DOCS"
    return "QUICK"


def _looks_like_repo_path(path: str) -> bool:
    parts = [p for p in (path or "").split("/") if p]
    return len(parts) >= 2


def _is_project_workspace(item: dict, cfg: Dict) -> bool:
    domain = (item.get("domain") or "").lower()
    path = (item.get("path") or "").lower()
    title = (item.get("canonical_title") or item.get("title_render") or item.get("title") or "").lower()
    text_blob = f"{title} {path}"
    suffix_ok = bool(cfg.get("projectDomainSuffixMatching", True))

    def _matches_any_base(bases: Iterable[str]) -> bool:
        return any(_host_matches_base(domain, str(base).lower(), suffix_ok) for base in (bases or []))

    if _matches_any_base(["trello.com"]) and (path.startswith("/b/") or path.startswith("/c/")):
        return True

    jira_hints = [str(h).lower() for h in cfg.get("projectJiraPathHints", [])]
    if _matches_any_base(cfg.get("projectJiraDomains", [])) and any(h in path for h in jira_hints):
        return True

    figma_hints = [str(h).lower() for h in cfg.get("projectFigmaPathHints", [])]
    if _matches_any_base(["figma.com"]) and any(h in path for h in figma_hints):
        return True

    if _matches_any_base(["drive.google.com"]) and "/folders/" in path:
        return True

    notion_hints = [str(h).lower() for h in cfg.get("projectNotionHints", [])]
    if _matches_any_base(cfg.get("projectNotionDomains", [])):
        if not cfg.get("projectNotionRequireHint", True):
            return True
        return any(h in text_blob for h in notion_hints)

    generic_hints = [str(h).lower() for h in cfg.get("projectTitleHints", [])]
    if _matches_any_base(cfg.get("projectDomains", [])) and any(h in text_blob for h in generic_hints):
        return True

    return False


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
    "серия",
    "seriya",
    "сезон",
    "sezon",
    "фильм",
    "смотреть",
    "smotret",
    "музыка",
    "muzyka",
    "песня",
    "pesnya",
    "альбом",
    "albom",
    "подкаст",
    "podkast",
    "слушать",
    "slushat",
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
    "купить",
    "kupit",
    "цена",
    "cena",
    "скидка",
    "skidka",
    "заказ",
    "zakaz",
    "доставка",
    "dostavka",
}


def _host_matches_base(host: str, base: str, enable_suffix: bool) -> bool:
    return _host_matches_base_shared(
        host,
        base,
        enable_suffix=enable_suffix,
        strip_www_host=True,
    )


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
