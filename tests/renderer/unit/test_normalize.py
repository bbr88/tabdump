from core.renderer.config import DEFAULT_CFG
from core.renderer.normalize import (
    _canonical_title,
    _github_repo_slug_title,
    _normalize_flags,
    _normalize_intent,
    _normalize_items,
    _normalize_title,
    _truncate,
)


def test_normalize_title_and_truncate():
    assert _normalize_title("  hello\n\tworld  ") == "hello world"
    truncated = _truncate("abcdef", 5)
    assert truncated == "abcd\u2026"


def test_github_repo_slug_title_prefers_slug_for_long_titles():
    slug = _github_repo_slug_title("/openai/gpt/issues/1", "GitHub - this is a long enough title to trigger slug")
    assert slug == "openai/gpt \u2014 issues"

    short = _github_repo_slug_title("/openai/gpt", "tiny title")
    assert short == ""


def test_normalize_intent_and_flags():
    assert _normalize_intent({"action": "implement", "confidence": "2"}) == {
        "action": "build",
        "confidence": 1.0,
    }
    assert _normalize_intent({"action": "", "confidence": "bad"}) == {
        "action": "",
        "confidence": 0.0,
    }

    assert _normalize_flags({}, provided_kind="local")["is_local"] is True
    assert _normalize_flags({}, provided_kind="auth")["is_auth"] is True
    assert _normalize_flags({}, provided_kind="internal")["is_internal"] is True


def test_canonical_title_obeys_disable_flag():
    cfg = dict(DEFAULT_CFG)
    cfg["canonicalTitleEnabled"] = False
    assert _canonical_title("  My Title  ", "example.com", "/", cfg) == "  My Title  "


def test_normalize_items_dedupes_and_derives_fields():
    cfg = dict(DEFAULT_CFG)
    cfg["titleMaxLen"] = 20

    raw_items = [
        {
            "url": "https://www.github.com/openai/gpt/issues/1",
            "title": "GitHub - OpenAI GPT issue tracker with a very long title for slug preference",
            "browser": "Chrome",
            "intent": {"action": "implement", "confidence": 0.9},
            "kind": "repo",
            "topics": [{"slug": "ai"}],
        },
        {
            "url": "https://www.github.com/openai/gpt/issues/1",
            "title": "duplicate",
        },
        {
            "url": "https://example.com/path",
            "title": "   spaced   title   ",
            "kind": "local",
        },
    ]

    items, deduped = _normalize_items(raw_items, cfg)

    assert deduped == 1
    assert len(items) == 2

    first = items[0]
    assert first["domain"] == "github.com"
    assert first["browser"] == "chrome"
    assert first["kind"] == "repo"
    assert first["intent"]["action"] == "build"
    assert first["canonical_title"].startswith("openai/gpt")

    second = items[1]
    assert second["title"] == "spaced title"
    assert second["flags"]["is_local"] is True
    assert second["kind"] == "admin"
