from core.renderer.stats import (
    _badge_cfg,
    _build_badges,
    _focus_line,
    _ordering_cfg,
    _primary_badge,
    _tagify,
    _top_domains,
    _top_kinds,
)


def _item(**overrides):
    base = {
        "domain": "example.com",
        "domain_category": "docs_site",
        "kind": "docs",
        "topics": [{"slug": "Distributed Systems"}],
        "quick_why": "shopping_domain",
    }
    base.update(overrides)
    return base


def test_top_domains_and_kinds_exclude_admin_entries():
    items = [
        _item(domain="a.com", kind="docs", domain_category="docs_site"),
        _item(domain="a.com", kind="docs", domain_category="docs_site"),
        _item(domain="b.com", kind="video", domain_category="video"),
        _item(domain="admin.com", kind="admin", domain_category="admin_auth"),
    ]

    assert _top_domains(items, 2) == ["a.com", "b.com"]
    assert _top_kinds(items, 2) == ["docs", "video"]


def test_focus_line_uses_category_display_mapping():
    items = [
        _item(domain="a.com", domain_category="docs_site", kind="docs"),
        _item(domain="a.com", domain_category="docs_site", kind="docs"),
        _item(domain="video.com", domain_category="video", kind="video"),
    ]

    focus = _focus_line(items)
    assert focus.startswith("Mostly docs + media")
    assert "a.com" in focus


def test_tagify_and_primary_badge():
    assert _tagify("Distributed Systems!!") == "distributed-systems"
    assert _primary_badge(_item(domain_category="admin_internal", kind="docs")) == "admin"
    assert _primary_badge(_item(kind="paper")) == "paper"


def test_badge_cfg_and_ordering_cfg_merge_with_defaults():
    cfg = {
        "render": {
            "badges": {"includeQuickWinsWhy": True, "maxPerBullet": 1},
            "ordering": {"domains": {"pinned": ["a.com"]}},
        }
    }
    badges = _badge_cfg(cfg)
    ordering = _ordering_cfg(cfg)

    assert badges["includeQuickWinsWhy"] is True
    assert badges["maxPerBullet"] == 1
    assert ordering["domains"] == {"pinned": ["a.com"]}


def test_build_badges_for_high_and_quick_contexts():
    cfg = {}
    badges_cfg = {"maxPerBullet": 3, "includeTopicInHighPriority": True, "includeQuickWinsWhy": True}

    high = _build_badges(_item(), cfg, badges_cfg, context="high")
    quick = _build_badges(_item(kind="misc"), cfg, badges_cfg, context="quick")

    assert "docs" in high
    assert "#distributed-systems" in high
    assert "why:shopping_domain" in quick
