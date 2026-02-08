from core.postprocess.classify_local import (
    classify_local,
    infer_local_action,
    infer_local_kind,
    infer_local_score,
    needle_in_blob,
    slugify_topic,
    topic_from_host,
    topic_from_keywords,
)
from core.postprocess.models import Item
from core.postprocess.urls import normalize_url


def _item(title: str, url: str, domain: str | None = None) -> Item:
    clean = normalize_url(url)
    return Item(
        title=title,
        url=url,
        norm_url=clean,
        clean_url=clean,
        domain=domain or (clean.split("//", 1)[1].split("/", 1)[0] if "//" in clean else "example.com"),
        browser=None,
    )


def test_slugify_topic():
    assert slugify_topic("  Distributed Systems!! ") == "distributed-systems"
    assert slugify_topic("***") == "misc"


def test_topic_from_host_ignores_social_domains():
    assert topic_from_host("x.com") is None


def test_topic_from_host_extracts_stem():
    assert topic_from_host("www.python.org") == "python"
    assert topic_from_host("docs.internal") == "docs"


def test_needle_in_blob_for_go_requires_context():
    assert not needle_in_blob("go", "go", "we go now")
    assert needle_in_blob("go", "go", "learning go with goroutine examples")


def test_topic_from_keywords_prefers_keyword_map_then_special_hints():
    assert topic_from_keywords("fastapi tutorial") == "python"
    assert topic_from_keywords("new figma component kit") == "ui-ux"
    assert topic_from_keywords("linear.app board") == "project-management"


def test_infer_local_kind_precedence_paper_over_blog_and_other_hints():
    item = _item("post", "https://example.com/blog/file.pdf")
    assert infer_local_kind(item) == "paper"


def test_infer_local_kind_blog_path_wins_over_docs_domain():
    item = _item("launch", "https://docs.example.com/blog/my-post")
    assert infer_local_kind(item) == "article"


def test_infer_local_kind_code_host_path_treated_as_repo():
    item = _item("microsoft", "https://github.com/microsoft")
    assert infer_local_kind(item) == "repo"


def test_infer_local_kind_tool_domain_and_docs_path():
    tool_item = _item("calendar", "https://calendar.google.com/calendar/u/0/r")
    docs_item = _item("docs", "https://example.com/docs/getting-started")

    assert infer_local_kind(tool_item) == "tool"
    assert infer_local_kind(docs_item) == "docs"


def test_infer_local_action_cases():
    video = _item("Video", "https://youtube.com/watch?v=1")
    repo_issue = _item("Issue", "https://github.com/org/repo/issues/1")
    repo_code = _item("Code", "https://github.com/org/repo")
    tool_project = _item("Sprint board", "https://linear.app/acme/issue/APP-1")
    paper_deep = _item("whitepaper guide", "https://arxiv.org/abs/1234")
    docs_ref = _item("API reference", "https://docs.github.com/en/rest/reference/repos")

    assert infer_local_action("video", video) == "watch"
    assert infer_local_action("repo", repo_issue) == "triage"
    assert infer_local_action("repo", repo_code) == "build"
    assert infer_local_action("tool", tool_project) == "build"
    assert infer_local_action("paper", paper_deep) == "deep_work"
    assert infer_local_action("docs", docs_ref) == "reference"


def test_infer_local_score_applies_adjustments_and_clamps():
    social = _item("Thread", "https://x.com/u/status/1", domain="x.com")
    deep_paper = _item("distributed systems whitepaper guide", "https://arxiv.org/abs/2401.1")
    noisy_video = _item("Top 10 review", "https://youtube.com/watch?v=1")

    assert infer_local_score("article", "read", social) == 2
    assert infer_local_score("paper", "deep_work", deep_paper) == 5
    assert 1 <= infer_local_score("video", "watch", noisy_video) <= 5


def test_classify_local_end_to_end():
    item = _item("Reliable Event Streaming Whitepaper", "https://arxiv.org/abs/2401.12345", domain="arxiv.org")

    cls = classify_local(item)

    assert cls["kind"] == "paper"
    assert cls["action"] == "deep_work"
    assert cls["topic"] == "research"
    assert cls["score"] == 5
