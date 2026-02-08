from core.renderer.rendering import (
    _dump_date,
    _escape_md,
    _escape_md_url,
    _format_bullet,
    _frontmatter,
    _group_items,
    _group_oneoffs_by_kind,
    _kind_display_label,
    _render_docs_callout,
    _render_quick_callout,
)


def _item(**overrides):
    base = {
        "url": "https://example.com/x",
        "title": "Title",
        "title_render": "Title",
        "canonical_title": "Title",
        "domain": "example.com",
        "domain_category": "docs_site",
        "kind": "docs",
        "topics": [{"slug": "distributed-systems"}],
    }
    base.update(overrides)
    return base


def test_dump_date_parsing_paths():
    assert _dump_date({"dump_date": "2026-02-08"}) == "2026-02-08"
    assert _dump_date({"created": "2026-02-08T15:30:00Z"}) == "2026-02-08"
    assert _dump_date({"created": "2026-02-08 15-30-00"}) == "2026-02-08"


def test_frontmatter_respects_include_filter():
    cfg = {"frontmatterInclude": ["dump_date", "tab_count", "source"]}
    meta = {"created": "2026-02-08T00:00:00Z", "source": "dump.md"}
    counts = {"total": 3}

    lines = _frontmatter(meta, counts, [_item()], deduped=0, cfg=cfg)
    text = "\n".join(lines)

    assert "Dump Date: 2026-02-08" in text
    assert "Tab Count: 3" in text
    assert "Source: dump.md" in text
    assert "Renderer:" not in text


def test_escape_and_format_bullet_encodes_markdown_sensitive_text():
    escaped = _escape_md("A [b](c)_*`")
    assert "\\[" in escaped
    assert "\\(" in escaped

    url = _escape_md_url("https://example.com/a b(c)")
    assert "%20" in url
    assert "%28" in url
    assert "%29" in url

    badges_cfg = {"maxPerBullet": 3, "includeTopicInHighPriority": True, "includeQuickWinsWhy": False}
    bullet = _format_bullet(
        _item(canonical_title="A [Title]", url="https://example.com/a b(c)"),
        prefix="> ",
        cfg={},
        badges_cfg=badges_cfg,
        context="high",
        source_domain="source.example",
    )
    assert bullet.startswith("> - [ ] ")
    assert "[A \\[Title\\]](https://example.com/a%20b%28c%29)" in bullet
    assert "source.example" in bullet


def test_group_items_respects_pins_and_admin_heading_format():
    items = [
        _item(domain="z.com", domain_category="docs_site"),
        _item(domain="a.com", domain_category="blog"),
    ]
    ordering_cfg = {"domains": {"pinned": ["z.com"]}}

    grouped = _group_items(items, admin=False, ordering_cfg=ordering_cfg)
    assert [h for h, _ in grouped] == ["z.com", "a.com"]

    admin_grouped = _group_items([_item(domain="a.com", domain_category="admin_auth")], admin=True, ordering_cfg={})
    assert admin_grouped[0][0] == "admin_auth \u2022 a.com"


def test_kind_labels_and_group_oneoffs_sorting():
    assert _kind_display_label("docs") == "Docs"
    assert _kind_display_label("article") == "Articles"
    assert _kind_display_label("unknown") == "Other"

    grouped = _group_oneoffs_by_kind(
        [
            ("a.com", _item(kind="article", canonical_title="z")),
            ("b.com", _item(kind="docs", canonical_title="a")),
            ("c.com", _item(kind="paper", canonical_title="b")),
        ]
    )
    assert [label for label, _ in grouped] == ["Docs", "Articles", "Papers"]


def test_render_quick_callout_and_docs_large_mode_grouping():
    cfg = {
        "quickWinsEnableMiniCategories": True,
        "quickWinsMiniCategories": ["leisure", "shopping"],
        "emptyBucketMessage": "_(empty)_",
        "docsLargeSectionItemsGte": 1,
        "docsLargeSectionDomainsGte": 99,
        "docsMultiDomainMinItems": 2,
        "docsOneOffGroupByKindWhenDomainsGt": 1,
        "docsOmitDomInBullets": True,
        "docsOmitKindFor": ["docs", "article"],
    }
    badges_cfg = {"maxPerBullet": 3, "includeTopicInHighPriority": True, "includeQuickWinsWhy": False}

    quick_lines = _render_quick_callout(
        "Easy Tasks",
        "[!tip]- Expand Easy Tasks",
        [_item(domain="amazon.com", kind="misc"), _item(domain="netflix.com", kind="misc")],
        cfg,
        badges_cfg,
        ordering_cfg={},
    )
    quick_text = "\n".join(quick_lines)
    assert "> ### Shopping" in quick_text
    assert "> ### Leisure" in quick_text

    docs_items = [
        _item(domain="d1.com", kind="docs", canonical_title="Doc A"),
        _item(domain="d2.com", kind="article", canonical_title="Article A"),
        _item(domain="d3.com", kind="paper", canonical_title="Paper A"),
    ]
    docs_lines = _render_docs_callout(
        "Read Later",
        "[!info]- Read Later",
        docs_items,
        cfg,
        badges_cfg,
        ordering_cfg={},
    )
    docs_text = "\n".join(docs_lines)
    assert "> [!summary]- More Links" in docs_text
    assert "> #### Docs" in docs_text
    assert "> #### Articles" in docs_text
    assert "> #### Papers" in docs_text


def test_render_quick_callout_falls_back_to_generic_mode_when_disabled():
    cfg = {
        "quickWinsEnableMiniCategories": False,
        "emptyBucketMessage": "_(empty)_",
    }
    badges_cfg = {"maxPerBullet": 3, "includeTopicInHighPriority": True, "includeQuickWinsWhy": False}

    lines = _render_quick_callout(
        "Easy Tasks",
        "[!tip]- Expand Easy Tasks",
        [_item(domain="amazon.com", kind="misc"), _item(domain="netflix.com", kind="misc")],
        cfg,
        badges_cfg,
        ordering_cfg={},
    )
    text = "\n".join(lines)
    assert "> ### amazon.com" in text
    assert "> ### netflix.com" in text
    assert "> ### Shopping" not in text
    assert "> ### Leisure" not in text
