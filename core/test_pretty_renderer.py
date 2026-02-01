import re

from pretty_renderer import render_markdown


def _meta():
    return {
        "ts": "2026-02-01 12-00-00",
        "sourceFile": "TabDump 2026-02-01.md",
        "counts": {"total": 5, "dumped": 5, "closed": 5, "kept": 0},
        "allowlistPatterns": ["mail.google.com", "slack.com"],
        "skipPrefixes": ["chrome://", "file://"],
    }


def _cfg(**overrides):
    base = {}
    base.update(overrides)
    return base


def _section(md: str, header: str) -> str:
    start = md.index(header)
    rest = md[start + len(header):]
    m = re.search(r"\n## ", rest)
    if not m:
        return rest
    return rest[: m.start()]


def test_section_ordering():
    tabs = [
        {"title": "Doc", "url": "https://docs.example.com/a", "topic": "docs", "kind": "docs", "action": "reference", "domain": "docs.example.com", "prio": "p2", "browser": "chrome"},
        {"title": "Post", "url": "https://blog.example.com/p", "topic": "reading", "kind": "article", "action": "read", "domain": "blog.example.com", "prio": "p2", "browser": "chrome"},
        {"title": "Repo", "url": "https://github.com/x/y", "topic": "code", "kind": "repo", "action": "build", "domain": "github.com", "prio": "p1", "browser": "chrome"},
        {"title": "Video", "url": "https://youtube.com/v", "topic": "video", "kind": "video", "action": "watch", "domain": "youtube.com", "prio": "p3", "browser": "chrome"},
        {"title": "Misc", "url": "https://misc.example.com", "topic": "misc", "kind": "misc", "action": "triage", "domain": "misc.example.com", "prio": "p3", "browser": "chrome"},
        {"title": "Local", "url": "file:///tmp/x", "topic": "local", "kind": "local", "action": "ignore", "domain": "local", "prio": "p3", "browser": "chrome"},
    ]
    md = render_markdown(tabs, _meta(), _cfg(hideEmptySections=True))
    order = [
        "# Tab dump — 2026-02-01 12-00-00",
        "## Inbox triage",
        "## ⭐ Top picks",
        "## 📚 Reference (docs / specs)",
        "## 📌 Read next (articles / posts / papers)",
        "## 🧰 Build / code (repos / tooling)",
        "## 🎥 Watch",
        "## 🎭 Misc",
        "## 🧯 Local / ephemeral",
        "## By topic (collapsed)",
        "## Notes",
    ]
    idx = [md.index(s) for s in order]
    assert idx == sorted(idx)


def test_grouping_by_domain_threshold():
    tabs = [
        {"title": "A1", "url": "https://a.com/1", "topic": "t", "kind": "article", "action": "read", "domain": "a.com", "prio": "p2"},
        {"title": "A2", "url": "https://a.com/2", "topic": "t", "kind": "article", "action": "read", "domain": "a.com", "prio": "p2"},
        {"title": "B1", "url": "https://b.com/1", "topic": "t", "kind": "article", "action": "read", "domain": "b.com", "prio": "p2"},
    ]
    md = render_markdown(tabs, _meta(), _cfg(minDomainGroupSize=2))
    section = _section(md, "## 📌 Read next (articles / posts / papers)")
    assert "### a.com" in section
    assert "### b.com" not in section
    assert "- [B1](https://b.com/1)" in section


def test_top_picks_selection_and_truncation():
    tabs = []
    for i in range(20):
        tabs.append({"title": f"P1 {i}", "url": f"https://x.com/{i}", "topic": "t", "kind": "article", "action": "read", "domain": "x.com", "prio": "p1"})
    md = render_markdown(tabs, _meta(), _cfg(topPicksLimit=12))
    section = _section(md, "## ⭐ Top picks")
    picks = re.findall(r"^- \[P1", section, flags=re.M)
    assert len(picks) == 12


def test_link_formatting_and_title_truncation():
    long_title = "A " * 200
    tabs = [
        {"title": long_title, "url": "https://example.com", "topic": "t", "kind": "article", "action": "read", "domain": "example.com", "prio": "p2", "browser": "safari"},
    ]
    md = render_markdown(tabs, _meta(), _cfg(linkStyle="chips"))
    line = [l for l in md.splitlines() if re.match(r"^- \[[^\]]+\]\(", l)][0]
    assert "src:safari" in line
    assert "\n" not in line
    assert len(re.search(r"\[([^\]]+)\]", line).group(1)) <= 120
    assert "…" in line


def test_hide_empty_sections():
    tabs = [
        {"title": "Doc", "url": "https://docs.example.com/a", "topic": "docs", "kind": "docs", "action": "reference", "domain": "docs.example.com", "prio": "p2"},
    ]
    md = render_markdown(tabs, _meta(), _cfg(hideEmptySections=True, includeTopicAppendix=False))
    assert "## 📚 Reference (docs / specs)" in md
    assert "## 🎥 Watch" not in md


def test_include_topic_appendix():
    tabs = [
        {"title": "Doc", "url": "https://docs.example.com/a", "topic": "docs", "kind": "docs", "action": "reference", "domain": "docs.example.com", "prio": "p2"},
    ]
    md = render_markdown(tabs, _meta(), _cfg(includeTopicAppendix=True))
    assert "## By topic (collapsed)" in md
    md2 = render_markdown(tabs, _meta(), _cfg(includeTopicAppendix=False))
    assert "## By topic (collapsed)" not in md2
