from core.renderer.buckets import (
    _assign_buckets,
    _bucket_for_item,
    _is_project_workspace,
    _looks_like_repo_path,
    _quick_mini_classify,
    _tighten_quick_wins,
)
from core.renderer.config import DEFAULT_CFG


def _cfg(**overrides):
    cfg = dict(DEFAULT_CFG)
    cfg.update(overrides)
    return cfg


def _item(**overrides):
    base = {
        "url": "https://example.com",
        "domain": "example.com",
        "domain_category": "generic",
        "kind": "misc",
        "provided_kind": "",
        "path": "/",
        "title": "Title",
        "title_render": "Title",
        "canonical_title": "Title",
    }
    if "title" in overrides:
        # Renderer project heuristics read canonical/title_render first.
        title = overrides["title"]
        overrides.setdefault("title_render", title)
        overrides.setdefault("canonical_title", title)
    base.update(overrides)
    return base


def test_looks_like_repo_path():
    assert _looks_like_repo_path("/org/repo") is True
    assert _looks_like_repo_path("/org") is False


def test_is_project_workspace_handles_trello_notion_and_generic_hints():
    cfg = _cfg()

    trello = _item(domain="trello.com", path="/b/board-id", title="Board")
    assert _is_project_workspace(trello, cfg) is True

    notion_with_hint = _item(domain="notion.so", path="/my-page", title="Roadmap Planning")
    assert _is_project_workspace(notion_with_hint, cfg) is True

    notion_without_hint = _item(domain="notion.so", path="/my-page", title="Inbox")
    assert _is_project_workspace(notion_without_hint, cfg) is False

    cfg_loose = _cfg(projectNotionRequireHint=False)
    assert _is_project_workspace(notion_without_hint, cfg_loose) is True


def test_bucket_for_item_routes_by_semantics():
    cfg = _cfg()

    assert _bucket_for_item(_item(domain_category="admin_auth", kind="admin"), cfg) == "ADMIN"
    assert _bucket_for_item(_item(kind="video"), cfg) == "MEDIA"
    assert _bucket_for_item(_item(kind="music"), cfg) == "MEDIA"
    assert _bucket_for_item(_item(kind="repo"), cfg) == "REPOS"
    assert _bucket_for_item(_item(domain_category="code_host", path="/org/repo"), cfg) == "REPOS"
    assert _bucket_for_item(_item(kind="tool"), cfg) == "TOOLS"
    assert _bucket_for_item(_item(domain_category="console"), cfg) == "TOOLS"
    assert _bucket_for_item(_item(kind="docs"), cfg) == "DOCS"

    project = _item(domain="notion.so", path="/x", title="Project Roadmap", kind="article")
    assert _bucket_for_item(project, cfg) == "PROJECTS"

    assert _bucket_for_item(_item(kind="misc"), cfg) == "QUICK"


def test_quick_mini_classify_detects_domains_keywords_and_admin():
    cfg = _cfg()

    admin = _item(domain_category="admin_auth")
    assert _quick_mini_classify(admin, cfg) == ("misc", "admin_path")

    shopping = _item(domain="amazon.com")
    assert _quick_mini_classify(shopping, cfg) == ("shopping", "shopping_domain")

    leisure_kw = _item(domain="example.com", title="Watch trailer now")
    assert _quick_mini_classify(leisure_kw, cfg) == ("leisure", "leisure_keyword")

    leisure_kw_ru = _item(domain="example.com", title="1 серия 3 сезон смотреть онлайн")
    assert _quick_mini_classify(leisure_kw_ru, cfg) == ("leisure", "leisure_keyword")

    leisure_kw_translit = _item(domain="example.com", title="1 seriya 3 sezon smotret online")
    assert _quick_mini_classify(leisure_kw_translit, cfg) == ("leisure", "leisure_keyword")

    shopping_kw_ru = _item(domain="example.com", title="купить сейчас, скидка и доставка")
    assert _quick_mini_classify(shopping_kw_ru, cfg) == ("shopping", "shopping_keyword")

    shopping_kw_translit = _item(domain="example.com", title="kupit cena skidka dostavka")
    assert _quick_mini_classify(shopping_kw_translit, cfg) == ("shopping", "shopping_keyword")


def test_tighten_quick_wins_moves_non_low_effort_to_backlog():
    cfg = _cfg(quickWinsLowEffortReasons=["shopping_domain"])
    buckets = {
        "QUICK": [_item(domain="amazon.com"), _item(domain="example.com", title="Random task")],
        "BACKLOG": [],
    }

    _tighten_quick_wins(buckets, cfg)

    assert len(buckets["QUICK"]) == 1
    assert buckets["QUICK"][0]["quick_why"] == "shopping_domain"
    assert len(buckets["BACKLOG"]) == 1
    assert buckets["BACKLOG"][0]["quick_why"] == "fallback_misc"


def test_assign_buckets_applies_quick_limit_overflow_and_disable_modes():
    cfg = _cfg(includeQuickWins=True, quickWinsMaxItems=1, quickWinsOverflowToBacklog=True)
    items = [
        _item(url="https://amazon.com/p/1", domain="amazon.com", kind="misc"),
        _item(url="https://netflix.com/title/1", domain="netflix.com", kind="misc"),
    ]

    buckets = _assign_buckets(items, cfg)
    assert len(buckets["QUICK"]) == 1
    assert len(buckets["BACKLOG"]) == 1

    cfg_disabled = _cfg(includeQuickWins=False)
    buckets_disabled = _assign_buckets(items, cfg_disabled)
    assert buckets_disabled["QUICK"] == []
    assert len(buckets_disabled["BACKLOG"]) == 2


def test_assign_buckets_drops_overflow_when_backlog_overflow_disabled():
    cfg = _cfg(includeQuickWins=True, quickWinsMaxItems=1, quickWinsOverflowToBacklog=False)
    items = [
        _item(url="https://amazon.com/p/1", domain="amazon.com", kind="misc"),
        _item(url="https://netflix.com/title/1", domain="netflix.com", kind="misc"),
    ]

    buckets = _assign_buckets(items, cfg)

    assert len(buckets["QUICK"]) == 1
    assert buckets["BACKLOG"] == []
