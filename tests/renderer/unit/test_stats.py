from core.renderer.stats import (
    _badge_cfg,
    _build_badges,
    _effort_band,
    _focus_line,
    _ordering_cfg,
    _primary_badge,
    _status_pill,
    _tagify,
    _top_domains,
    _top_kinds,
    _top_topics,
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


def test_top_topics_excludes_misc_and_admin_entries():
    items = [
        _item(topics=[{"slug": "postgres"}]),
        _item(topics=[{"slug": "postgres"}]),
        _item(topics=[{"slug": "llm"}]),
        _item(topics=[{"slug": "misc"}]),
        _item(topics=[{"slug": "security"}], domain_category="admin_auth"),
    ]
    assert _top_topics(items, 3) == ["postgres", "llm"]


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
    badges_cfg = {"maxPerBullet": 3, "includeTopicInHighPriority": True, "includeQuickWinsWhy": True}

    high = _build_badges(_item(), badges_cfg, context="high")
    quick = _build_badges(_item(kind="misc"), badges_cfg, context="quick")
    project_misc = _build_badges(_item(kind="misc"), badges_cfg, context="projects")
    tool_misc = _build_badges(_item(kind="misc"), badges_cfg, context="tools")

    assert "docs" in high
    assert "#distributed-systems" in high
    assert "why:shopping_domain" in quick
    assert project_misc.startswith("project")
    assert tool_misc.startswith("tool")


def test_effort_band_and_status_pill_from_explicit_and_fallback_values():
    explicit = _item(kind="article", effort="deep", intent={"action": "read"})
    assert _effort_band(explicit) == "deep"
    assert _status_pill(explicit) == "[high effort]"

    paper = _item(kind="paper", effort="", intent={"action": "read"})
    assert _effort_band(paper) == "deep"
    assert _status_pill(paper) == "[high effort]"

    video = _item(kind="video", effort="", intent={"action": "watch"})
    assert _effort_band(video) == "quick"
    assert _status_pill(video) == "[low effort]"

    medium = _item(kind="docs", effort="", intent={"action": "read"})
    assert _effort_band(medium) == "medium"
    assert _status_pill(medium) == "[medium effort]"
