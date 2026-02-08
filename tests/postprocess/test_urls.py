from core.postprocess.urls import (
    default_kind_action,
    domain_of,
    host_matches_base,
    is_private_or_loopback_host,
    is_sensitive_url,
    matches_sensitive_host_or_path,
    normalize_url,
)


def test_normalize_url_strips_trackers_and_fragment_and_sorts_query():
    url = " HTTPS://Example.com/path/?b=2&utm_source=x&a=1#frag "

    out = normalize_url(url)

    assert out == "https://example.com/path?a=1&b=2"


def test_normalize_url_keeps_non_network_values_as_is():
    assert normalize_url("example.com/path") == "example.com/path"


def test_domain_of_returns_unknown_for_non_network_value():
    assert domain_of("example.com/path") == "(unknown)"


def test_host_matches_base_exact_and_suffix():
    assert host_matches_base("github.com", "github.com")
    assert host_matches_base("api.github.com", "github.com")
    assert not host_matches_base("notgithub.com", "github.com")


def test_is_private_or_loopback_host_variants():
    assert is_private_or_loopback_host("localhost")
    assert is_private_or_loopback_host("127.0.0.1")
    assert is_private_or_loopback_host("10.0.0.5")
    assert is_private_or_loopback_host("machine.local")
    assert not is_private_or_loopback_host("example.com")


def test_matches_sensitive_host_or_path_honors_host_and_path_markers():
    markers = {"github.com/settings", "auth.example.com"}

    assert matches_sensitive_host_or_path("github.com", "/settings/profile", markers)
    assert matches_sensitive_host_or_path("api.auth.example.com", "/", markers)
    assert not matches_sensitive_host_or_path("github.com", "/openai/openai-python", markers)


def test_is_sensitive_url_detects_auth_query_and_private_hosts():
    assert is_sensitive_url("https://example.com/login")
    assert is_sensitive_url("https://example.com/cb?token=abc")
    assert is_sensitive_url("http://localhost:3000/admin")
    assert is_sensitive_url("file:///tmp/x")


def test_is_sensitive_url_allows_normal_docs_urls():
    assert not is_sensitive_url("https://docs.python.org/3/tutorial/")


def test_default_kind_action_returns_expected_defaults():
    assert default_kind_action("file:///tmp/x") == ("local", "ignore")
    assert default_kind_action("https://platform.openai.com/api-keys") == ("auth", "ignore")
    assert default_kind_action("ftp://example.com/path") == ("internal", "ignore")
    assert default_kind_action("https://example.com/path") == ("misc", "triage")
