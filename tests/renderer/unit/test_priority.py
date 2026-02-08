from core.renderer.config import DEFAULT_CFG
from core.renderer.priority import _score_item, _select_high_priority


def _cfg(**overrides):
    cfg = dict(DEFAULT_CFG)
    cfg.update(overrides)
    return cfg


def _item(**overrides):
    base = {
        "url": "https://example.com/x",
        "title": "Title",
        "title_render": "Title",
        "domain": "example.com",
        "domain_category": "docs_site",
        "kind": "docs",
        "path": "/docs/reference",
        "intent": {"action": "read", "confidence": 0.8},
    }
    base.update(overrides)
    return base


def test_score_item_applies_action_aggregator_and_depth_rules():
    deep_work = _score_item(_item(intent={"action": "deep_work", "confidence": 0.8}))
    watch = _score_item(_item(intent={"action": "watch", "confidence": 0.8}))
    assert deep_work > watch

    normal = _score_item(_item(title="Detailed docs"))
    aggregator = _score_item(_item(title="Top weekly digest docs"))
    assert aggregator < normal


def test_select_high_priority_moves_selected_items_from_source_buckets():
    cfg = _cfg(highPriorityLimit=2, highPriorityMinScore=4, highPriorityMinIntentConfidence=0.7)

    doc_good = _item(url="https://example.com/docs/1", kind="docs", domain_category="docs_site")
    repo_good = _item(
        url="https://github.com/openai/gpt",
        domain="github.com",
        kind="repo",
        domain_category="code_host",
        path="/openai/gpt",
        intent={"action": "build", "confidence": 0.9},
    )
    low_conf_article = _item(
        url="https://example.com/blog/1",
        title="Blog",
        kind="article",
        domain_category="blog",
        intent={"action": "read", "confidence": 0.2},
    )

    buckets = {
        "DOCS": [doc_good, low_conf_article],
        "REPOS": [repo_good],
        "MEDIA": [],
        "HIGH": [],
        "PROJECTS": [],
        "TOOLS": [],
        "QUICK": [],
        "BACKLOG": [],
        "ADMIN": [],
    }

    _select_high_priority(buckets, cfg)

    selected_urls = {it["url"] for it in buckets["HIGH"]}
    assert "https://example.com/docs/1" in selected_urls
    assert "https://github.com/openai/gpt" in selected_urls
    assert "https://example.com/blog/1" not in selected_urls
    assert all(it["url"] not in selected_urls for it in buckets["DOCS"])
    assert all(it["url"] not in selected_urls for it in buckets["REPOS"])


def test_select_high_priority_allows_low_conf_paper_exception():
    cfg = _cfg(highPriorityLimit=1, highPriorityMinScore=4, highPriorityMinIntentConfidence=0.95)

    paper = _item(
        url="https://example.com/whitepaper.pdf",
        title="Architecture Whitepaper",
        kind="paper",
        domain_category="docs_site",
        path="/docs/whitepaper.pdf",
        intent={"action": "read", "confidence": 0.1},
    )

    buckets = {
        "DOCS": [paper],
        "REPOS": [],
        "MEDIA": [],
        "HIGH": [],
        "PROJECTS": [],
        "TOOLS": [],
        "QUICK": [],
        "BACKLOG": [],
        "ADMIN": [],
    }

    _select_high_priority(buckets, cfg)
    assert [it["url"] for it in buckets["HIGH"]] == ["https://example.com/whitepaper.pdf"]
