from urllib.parse import urlparse

from core.renderer.classify import _classify_domain, _contains_any, _derive_kind, _matches_any_regex
from core.renderer.config import DEFAULT_CFG


def _cfg(**overrides):
    cfg = dict(DEFAULT_CFG)
    cfg.update(overrides)
    return cfg


def _classify(url: str, *, flags=None, cfg=None) -> str:
    parsed = urlparse(url)
    domain = (parsed.hostname or "")
    return _classify_domain(
        url=url,
        parsed=parsed,
        domain_display=domain,
        flags=flags or {},
        cfg=cfg or _cfg(),
    )


def test_contains_any_and_regex_helpers_are_resilient():
    assert _contains_any("abc token xyz", ["TOKEN"]) is True
    assert _contains_any("abc", ["zzz"]) is False

    assert _matches_any_regex("/login", [r"(?i)login"]) is True
    assert _matches_any_regex("/login", [r"("]) is False


def test_classify_domain_admin_paths():
    assert _classify("file:///tmp/a.txt", flags={"is_local": False}) == "admin_local"
    assert _classify("chrome://settings", cfg=_cfg(skipPrefixes=["chrome://"])) == "admin_internal"
    assert _classify("https://chatgpt.com/", cfg=_cfg(chatDomains=["chatgpt.com"])) == "admin_chat"
    assert _classify("https://example.com/login") == "admin_auth"


def test_classify_domain_soft_auth_when_strong_not_required():
    cfg = _cfg(adminAuthRequiresStrongSignal=False, authContainsHintsSoft=["token"])
    assert _classify("https://example.com/?token=abc", cfg=cfg) == "admin_auth"


def test_classify_domain_non_admin_categories():
    assert _classify("https://github.com/openai/gpt") == "code_host"
    assert _classify("https://netflix.com/title/123") == "video"
    assert _classify("https://console.aws.amazon.com/ec2/home") == "console"
    assert _classify("https://example.com/api/users") == "docs_site"
    assert _classify("https://example.com/blog/post") == "blog"
    assert _classify("https://example.com/") == "generic"


def test_derive_kind_prioritizes_provided_and_domain_fallbacks():
    assert _derive_kind("generic", "local", "https://example.com") == "admin"
    assert _derive_kind("generic", "tool", "https://example.com") == "tool"
    assert _derive_kind("admin_auth", "", "https://example.com") == "admin"
    assert _derive_kind("generic", "", "https://example.com/readme.pdf") == "paper"
    assert _derive_kind("video", "", "https://netflix.com/title/123") == "video"
    assert _derive_kind("code_host", "", "https://github.com/openai/gpt") == "repo"
    assert _derive_kind("docs_site", "", "https://example.com/docs") == "docs"
    assert _derive_kind("generic", "", "https://example.com") == "article"
