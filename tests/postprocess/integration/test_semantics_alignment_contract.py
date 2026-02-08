from urllib.parse import urlparse

from core.postprocess.classify_local import infer_local_kind
from core.postprocess.models import Item
from core.postprocess.urls import default_kind_action, is_sensitive_url, normalize_url
from core.renderer.classify import _classify_domain, _derive_kind
from core.renderer.config import DEFAULT_CFG


def _item(url: str, title: str = "title") -> Item:
    clean = normalize_url(url)
    parsed = urlparse(clean)
    return Item(
        title=title,
        url=url,
        norm_url=clean,
        clean_url=clean,
        domain=parsed.hostname or "",
        browser=None,
    )


def _renderer_raw(url: str, provided_kind: str = "") -> tuple[str, str]:
    parsed = urlparse(url)
    domain = parsed.hostname or "unknown"
    flags = {
        "is_local": provided_kind == "local",
        "is_auth": provided_kind == "auth",
        "is_chat": False,
        "is_internal": provided_kind == "internal",
    }
    domain_category = _classify_domain(
        url=url,
        parsed=parsed,
        domain_display=domain,
        flags=flags,
        cfg=DEFAULT_CFG,
    )
    kind = _derive_kind(domain_category=domain_category, provided_kind=provided_kind, url=url)
    return domain_category, kind


def test_sensitive_query_key_handling_is_aligned_between_detection_and_fallback():
    url = "https://example.com/cb?token=abc"

    assert is_sensitive_url(url) is True
    assert default_kind_action(url) == ("auth", "ignore")


def test_shared_tool_domains_are_classified_consistently_in_postprocess_and_renderer():
    urls = [
        "https://calendar.google.com/calendar/u/0/r",
        "https://slack.com/client/T1/C1",
        "https://notion.so/workspace",
    ]

    for url in urls:
        assert infer_local_kind(_item(url, title="workspace")) == "tool"
        assert _renderer_raw(url) == ("console", "tool")


def test_non_http_urls_are_consistently_internal_or_admin():
    urls = [
        "custom-scheme://abc/path",
        "ftp://example.com/path",
    ]

    for url in urls:
        assert default_kind_action(url) == ("internal", "ignore")
        assert _renderer_raw(url) == ("admin_internal", "admin")
        assert _renderer_raw(url, provided_kind="internal") == ("admin_internal", "admin")


def test_auth_path_hints_are_classified_consistently_in_renderer_raw_mode():
    urls = [
        "https://example.com/session/abc",
        "https://example.com/token",
        "https://example.com/profile",
    ]

    for url in urls:
        assert is_sensitive_url(url) is True
        assert default_kind_action(url) == ("auth", "ignore")
        assert _renderer_raw(url) == ("admin_auth", "admin")

    assert _renderer_raw("https://example.com/login") == ("admin_auth", "admin")


def test_blog_urls_are_treated_as_articles_consistently():
    url = "https://example.com/blog/post-1"

    assert infer_local_kind(_item(url, title="blog entry")) == "article"
    assert _renderer_raw(url) == ("blog", "article")
