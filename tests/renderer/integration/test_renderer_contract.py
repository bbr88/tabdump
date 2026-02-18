import json
import re
from pathlib import Path

from core.renderer.renderer import build_state, render_markdown, _score_item, _host_matches_base

TESTS_DIR = Path(__file__).resolve().parents[2]
FIXTURES_DIR = TESTS_DIR / "fixtures"
RENDERER_FIXTURES_DIR = FIXTURES_DIR / "renderer"

FIXTURE_JSON = RENDERER_FIXTURES_DIR / "core" / "sample_payload_v3.json"
FIXTURE_MD = RENDERER_FIXTURES_DIR / "core" / "expected_sample_payload_v3.md"
FIXTURE_YT_JSON = RENDERER_FIXTURES_DIR / "title_cleanup" / "title_cleanup_youtube.json"
FIXTURE_GH_JSON = RENDERER_FIXTURES_DIR / "title_cleanup" / "title_cleanup_github.json"
FIXTURE_ADMIN_AUTH_JSON = RENDERER_FIXTURES_DIR / "admin" / "admin_auth_false_positive.json"
FIXTURE_DOCS_SUBGROUP_JSON = RENDERER_FIXTURES_DIR / "docs" / "docs_subgroup_intent.json"
FIXTURE_DOCS_DENOISE_JSON = RENDERER_FIXTURES_DIR / "docs" / "docs_denoise_dom_omit.json"
FIXTURE_QW_SUFFIX_JSON = RENDERER_FIXTURES_DIR / "quickwins" / "quickwins_suffix_disneyplus.json"
FIXTURE_QW_4CHAN_JSON = RENDERER_FIXTURES_DIR / "quickwins" / "quickwins_leisure_4chan.json"
FIXTURE_QW_NO_BEST_VS_JSON = RENDERER_FIXTURES_DIR / "quickwins" / "quickwins_no_best_vs.json"


def _load_payload():
    return json.loads(FIXTURE_JSON.read_text())


def _section(md: str, header: str) -> str:
    start = md.index(header)
    rest = md[start + len(header) :]
    m = re.search(r"\n## ", rest)
    if not m:
        return rest
    return rest[: m.start()]


def test_golden_snapshot():
    payload = _load_payload()
    md = render_markdown(payload)
    expected = FIXTURE_MD.read_text()
    assert md == expected


def test_bucket_exclusivity_and_coverage():
    payload = _load_payload()
    state = build_state(payload)
    items = state["items"]
    buckets = state["buckets"]
    urls = {it["url"] for it in items}
    bucket_urls = []
    for arr in buckets.values():
        bucket_urls.extend([it["url"] for it in arr])
    assert len(bucket_urls) == len(set(bucket_urls))
    assert set(bucket_urls) == urls


def test_admin_forcing():
    payload = _load_payload()
    state = build_state(payload)
    buckets = state["buckets"]
    admin_urls = {it["url"] for it in buckets["ADMIN"]}
    for name, arr in buckets.items():
        if name == "ADMIN":
            continue
        assert admin_urls.isdisjoint({it["url"] for it in arr})


def test_high_priority_rules_and_limit():
    payload = _load_payload()
    state = build_state(payload)
    cfg = state["cfg"]
    high = state["buckets"]["HIGH"]
    assert len(high) <= cfg["highPriorityLimit"]
    for it in high:
        score = _score_item(it)
        assert score >= cfg["highPriorityMinScore"]
        conf = it.get("intent", {}).get("confidence", 0)
        assert conf >= cfg["highPriorityMinIntentConfidence"] or it["kind"] in {"paper", "spec"}
    quick_urls = {it["url"] for it in state["buckets"]["QUICK"]}
    backlog_urls = {it["url"] for it in state["buckets"].get("BACKLOG", [])}
    assert quick_urls.isdisjoint({it["url"] for it in high})
    assert backlog_urls.isdisjoint({it["url"] for it in high})


def test_determinism():
    payload = _load_payload()
    md1 = render_markdown(payload)
    md2 = render_markdown(payload)
    assert md1 == md2


def test_group_headers_match_domains():
    payload = _load_payload()
    md = render_markdown(payload)
    headers = re.findall(r"> ### ([^\n]+)", md)
    # Headers inside non-admin callouts should be unique per domain
    non_admin_headers = [h for h in headers if "admin_" not in h]
    assert len(non_admin_headers) == len(set(non_admin_headers))
    # Each header should have at least one bullet
    for heading in headers:
        pattern = rf"> ### {re.escape(heading)}\n(> - \\[ \\] .*?)(?=\n> ###|\n##|\\Z)"
        match = re.search(pattern, md, flags=re.S)
        if not match:
            continue
        bullets = re.findall(r"\[[^\]]+\]\([^)]+\).*", match.group(0))
        assert bullets  # sanity
        assert all("dom::" not in b for b in bullets)


# ---- v3.2.x additions ----


def test_canonical_title_cleanup_youtube():
    payload = json.loads(FIXTURE_YT_JSON.read_text())
    md = render_markdown(payload)
    assert "Amazing Cats" in md
    bullet_lines = [l for l in md.splitlines() if l.strip().startswith("> - [ ]")]
    assert bullet_lines
    assert all("YouTube" not in l for l in bullet_lines)


def test_github_slug_preference():
    payload = json.loads(FIXTURE_GH_JSON.read_text())
    md = render_markdown(payload)
    assert re.search(r"\[owner/repo\]\(https://github\.com/owner/repo\)", md)
    assert "GitHub -" not in md


def test_admin_auth_false_positive_not_classified():
    payload = json.loads(FIXTURE_ADMIN_AUTH_JSON.read_text())
    state = build_state(payload)
    admin_urls = {it["url"] for it in state["buckets"]["ADMIN"]}
    assert "https://example.com/docs/usage-token" not in admin_urls


def test_docs_no_intent_subgrouping():
    payload = json.loads(FIXTURE_DOCS_SUBGROUP_JSON.read_text())
    md = render_markdown(payload)
    docs_section = _section(md, "## 📚 Read Later")
    assert "#### " not in docs_section
    assert "Implement feature X" in docs_section
    assert "Debugging common issues" in docs_section
    assert "API Reference" in docs_section
    assert "Getting Started" in docs_section


def test_docs_no_domain_numbering_even_when_many_domains():
    payload = {
        "meta": {"created": "2026-02-07T03:00:00Z", "source": "docs_many_domains.raw.json"},
        "counts": {"total": 6, "dumped": 6, "closed": 6, "kept": 0},
        "cfg": {"highPriorityLimit": 0},
        "items": [
            {"url": "https://a.com/docs/one", "title": "A", "kind": "docs"},
            {"url": "https://b.com/docs/one", "title": "B", "kind": "docs"},
            {"url": "https://c.com/docs/one", "title": "C", "kind": "docs"},
            {"url": "https://d.com/docs/one", "title": "D", "kind": "docs"},
            {"url": "https://e.com/docs/one", "title": "E", "kind": "docs"},
            {"url": "https://f.com/docs/one", "title": "F", "kind": "docs"},
        ],
    }
    md = render_markdown(payload)
    docs = _section(md, "## 📚 Read Later")
    assert "> ### a.com" in docs
    assert "> ### f.com" in docs
    assert "[01]" not in docs


def test_docs_no_item_numbering_even_when_entries_gte_5():
    payload = {
        "meta": {"created": "2026-02-07T04:00:00Z", "source": "docs_many_items.raw.json"},
        "counts": {"total": 5, "dumped": 5, "closed": 5, "kept": 0},
        "cfg": {"highPriorityLimit": 0},
        "items": [
            {"url": "https://x.com/docs/one", "title": "Epsilon", "kind": "docs"},
            {"url": "https://x.com/docs/two", "title": "Delta", "kind": "docs"},
            {"url": "https://x.com/docs/three", "title": "Gamma", "kind": "docs"},
            {"url": "https://x.com/docs/four", "title": "Beta", "kind": "docs"},
            {"url": "https://x.com/docs/five", "title": "Alpha", "kind": "docs"},
        ],
    }
    md = render_markdown(payload)
    docs = _section(md, "## 📚 Read Later")
    assert "> ### x.com" in docs
    assert "> - [ ] [Alpha]" in docs
    assert "> - [ ] [Beta]" in docs
    assert "> - [ ] [Delta]" in docs
    assert "> - [ ] [Epsilon]" in docs
    assert "> - [ ] [Gamma]" in docs
    assert "> - [ ] [01] [Alpha]" not in docs


def test_docs_large_section_summary_and_singleton_split():
    payload = {
        "meta": {"created": "2026-02-07T05:00:00Z", "source": "docs_large_split.raw.json"},
        "counts": {"total": 8, "dumped": 8, "closed": 8, "kept": 0},
        "cfg": {"highPriorityLimit": 0, "docsLargeSectionDomainsGte": 6},
        "items": [
            {"url": "https://a.com/docs/1", "title": "A1", "kind": "docs"},
            {"url": "https://a.com/docs/2", "title": "A2", "kind": "docs"},
            {"url": "https://b.com/docs/1", "title": "B1", "kind": "docs"},
            {"url": "https://b.com/docs/2", "title": "B2", "kind": "docs"},
            {"url": "https://c.com/docs/1", "title": "C1", "kind": "docs"},
            {"url": "https://d.com/docs/1", "title": "D1", "kind": "docs"},
            {"url": "https://e.com/docs/1", "title": "E1", "kind": "docs"},
            {"url": "https://f.com/docs/1", "title": "F1", "kind": "docs"},
        ],
    }
    md = render_markdown(payload)
    docs = _section(md, "## 📚 Read Later")
    assert "> [!info]- Main Sources (4)" in docs
    assert "_8 total = 4 from main sources + 4 more links_" not in docs
    assert "> #### Main Sources (4)" not in docs
    assert "> ### a.com (2)" in docs
    assert "> ### b.com (2)" in docs
    assert "> [!summary]- More Links (4)" in docs
    # singleton tail is grouped by source domain in domain mode.
    assert "> #### c.com (1)" in docs
    assert "> #### d.com (1)" in docs
    assert "> #### e.com (1)" in docs
    assert "> #### f.com (1)" in docs
    assert " · c.com" not in docs
    assert " · f.com" not in docs


def test_docs_oneoffs_grouped_by_kind_when_many_oneoff_domains():
    payload = {
        "meta": {"created": "2026-02-07T06:00:00Z", "source": "docs_oneoff_kinds.raw.json"},
        "counts": {"total": 12, "dumped": 12, "closed": 12, "kept": 0},
        "cfg": {
            "highPriorityLimit": 0,
            "docsLargeSectionDomainsGte": 10,
            "docsOneOffGroupByKindWhenDomainsGt": 8,
            "docsOneOffGroupingMode": "kind",
        },
        "items": [
            {"url": "https://a.com/docs/1", "title": "A1", "kind": "docs"},
            {"url": "https://a.com/docs/2", "title": "A2", "kind": "docs"},
            {"url": "https://b.com/article/1", "title": "B1", "kind": "article"},
            {"url": "https://c.com/article/1", "title": "C1", "kind": "article"},
            {"url": "https://d.com/docs/1", "title": "D1", "kind": "docs"},
            {"url": "https://e.com/docs/1", "title": "E1", "kind": "docs"},
            {"url": "https://f.com/paper/1.pdf", "title": "F1", "kind": "paper"},
            {"url": "https://g.com/spec/1", "title": "G1", "kind": "spec"},
            {"url": "https://h.com/misc/1", "title": "H1", "kind": "misc"},
            {"url": "https://i.com/docs/1", "title": "I1", "kind": "docs"},
            {"url": "https://j.com/docs/1", "title": "J1", "kind": "docs"},
            {"url": "https://k.com/docs/1", "title": "K1", "kind": "docs"},
        ],
    }
    md = render_markdown(payload)
    docs = _section(md, "## 📚 Read Later")
    assert "> [!summary]- More Links (" in docs
    assert "> #### Docs (" in docs
    assert "> #### Articles (" in docs
    assert "> #### Papers (" in docs
    assert "> #### Specs (" in docs


def test_admin_compact_bullets_default():
    payload = _load_payload()
    md = render_markdown(payload)
    admin_section = _section(md, "## 🔐 Accounts & Settings")
    # Should show admin badge and no dom:: chips
    for line in admin_section.splitlines():
        if line.strip().startswith("> - [ ]"):
            assert " · admin" in line
            assert "effort" not in line
            assert "dom::" not in line


def test_docs_denoise_omit_dom_and_kind():
    payload = json.loads(FIXTURE_DOCS_DENOISE_JSON.read_text())
    md = render_markdown(payload)
    docs_section = _section(md, "## 📚 Read Later")
    lines = docs_section.splitlines()
    bullet_lines = [l for l in lines if l.strip().startswith("> - [ ]")]
    assert bullet_lines
    for idx, line in enumerate(lines):
        if not line.strip().startswith("> - [ ]"):
            continue
        assert "dom::" not in line
        if " · " in line:
            assert re.search(r"\[(low|medium|high) effort\] · (docs|article|paper|spec|misc)", line)
            continue
        assert idx + 1 < len(lines)
        assert lines[idx + 1].startswith(">   ")
        assert " · " in lines[idx + 1]
        assert re.search(r"\[(low|medium|high) effort\] · (docs|article|paper|spec|misc)", lines[idx + 1])


def test_quickwins_suffix_matching_disneyplus():
    payload = json.loads(FIXTURE_QW_SUFFIX_JSON.read_text())
    md = render_markdown(payload)
    quick = _section(md, "## 🧹 Easy Tasks")
    assert "### Leisure" in quick
    assert "why:" not in quick


def test_quickwins_leisure_4chan():
    payload = json.loads(FIXTURE_QW_4CHAN_JSON.read_text())
    md = render_markdown(payload)
    quick = _section(md, "## 🧹 Easy Tasks")
    assert "### Leisure" in quick
    assert "why:" not in quick


def test_quickwins_no_best_vs_keyword_only():
    payload = json.loads(FIXTURE_QW_NO_BEST_VS_JSON.read_text())
    md = render_markdown(payload)
    # Empty quick wins section should be hidden by default.
    assert "## 🧹 Easy Tasks" not in md
    assert "why:fallback_misc" not in md
    backlog = _section(md, "## 🗃 Maybe Later")
    assert "best laptops vs tablets 2026" in backlog


def test_include_empty_sections_opt_in():
    payload = json.loads(FIXTURE_QW_NO_BEST_VS_JSON.read_text())
    md = render_markdown(payload, cfg={"includeEmptySections": True})
    assert "## 🧹 Easy Tasks" in md
    assert "> _(empty)_" in md


def test_suffix_match_helper():
    assert _host_matches_base("apps.disneyplus.com", "disneyplus.com", True)
    assert _host_matches_base("www.netflix.com", "netflix.com", True)
    assert not _host_matches_base("notnetflix.com", "netflix.com", True)


def test_postprocess_sensitive_kinds_are_admin_bucketed():
    payload = {
        "meta": {"created": "2026-02-07T10:00:00Z", "source": "sensitive_kinds.raw.json"},
        "counts": {"total": 3, "dumped": 3, "closed": 3, "kept": 0},
        "cfg": {"highPriorityLimit": 0},
        "items": [
            {"url": "https://platform.openai.com/api-keys?token=abc", "title": "API Keys", "kind": "auth"},
            {"url": "http://localhost:3000/admin", "title": "Local Admin", "kind": "local"},
            {"url": "custom-scheme://internal/panel", "title": "Internal Panel", "kind": "internal"},
        ],
    }
    state = build_state(payload)
    admin_urls = {it["url"] for it in state["buckets"]["ADMIN"]}
    assert "https://platform.openai.com/api-keys?token=abc" in admin_urls
    assert "http://localhost:3000/admin" in admin_urls
    assert "custom-scheme://internal/panel" in admin_urls
    assert not state["buckets"]["DOCS"]


def test_postprocess_repo_kind_short_path_stays_in_repos():
    payload = {
        "meta": {"created": "2026-02-07T11:00:00Z", "source": "repo_short_path.raw.json"},
        "counts": {"total": 1, "dumped": 1, "closed": 1, "kept": 0},
        "cfg": {"highPriorityLimit": 0},
        "items": [
            {"url": "https://github.com/microsoft", "title": "Microsoft on GitHub", "kind": "repo"},
        ],
    }
    state = build_state(payload)
    assert len(state["buckets"]["REPOS"]) == 1
    assert not state["buckets"]["BACKLOG"]


def test_shared_video_domain_classifies_as_video_category():
    payload = {
        "meta": {"created": "2026-02-08T12:00:00Z", "source": "video_domain.raw.json"},
        "counts": {"total": 1, "dumped": 1, "closed": 1, "kept": 0},
        "cfg": {"highPriorityLimit": 0},
        "items": [
            {"url": "https://netflix.com/title/123", "title": "Netflix Show"},
        ],
    }
    state = build_state(payload)
    item = state["items"][0]
    assert item["domain_category"] == "video"
    assert item["kind"] == "video"


def test_shared_docs_path_hint_classifies_as_docs_site():
    payload = {
        "meta": {"created": "2026-02-08T12:00:00Z", "source": "docs_hint.raw.json"},
        "counts": {"total": 1, "dumped": 1, "closed": 1, "kept": 0},
        "cfg": {"highPriorityLimit": 0},
        "items": [
            {"url": "https://example.com/api/users", "title": "Users API"},
        ],
    }
    state = build_state(payload)
    item = state["items"][0]
    assert item["domain_category"] == "docs_site"
    assert item["kind"] == "docs"


def test_postprocess_action_semantics_score_mapping():
    base = {
        "kind": "article",
        "domain_category": "generic",
        "intent": {"confidence": 0.8},
        "title": "Sample",
        "path": "/",
    }

    def score_for(action: str) -> int:
        it = dict(base)
        it["intent"] = {"action": action, "confidence": 0.8}
        return _score_item(it)

    assert score_for("build") == score_for("deep_work")
    assert score_for("reference") == score_for("triage")
    assert score_for("watch") < score_for("reference")
    assert score_for("ignore") < score_for("watch")


def test_docs_dom_chip_suppression_and_paper_kind():
    payload = _load_payload()
    md = render_markdown(payload)
    docs_section = _section(md, "## 📚 Read Later")
    # paper retains kind in metadata line, but no dom chip
    lines = docs_section.splitlines()
    idx = next(i for i, line in enumerate(lines) if "hstore.pdf" in line)
    assert idx + 1 < len(lines)
    meta = lines[idx + 1]
    assert " · paper" in meta
    assert "dom::" not in meta


def test_media_queue_omits_dom_chip():
    payload = _load_payload()
    md = render_markdown(payload)
    media_section = _section(md, "## 📺 Watch / Listen Later")
    lines = media_section.splitlines()
    bullet_idxs = [i for i, line in enumerate(lines) if line.strip().startswith("> - [ ]")]
    assert bullet_idxs
    for idx in bullet_idxs:
        assert "dom::" not in lines[idx]
        assert " · " not in lines[idx]
        assert idx + 1 < len(lines)
        meta = lines[idx + 1]
        assert meta.startswith(">   ")
        assert "dom::" not in meta
        assert " · video" in meta


def test_bullets_have_badges_and_no_dom():
    payload = _load_payload()
    md = render_markdown(payload)
    lines = md.splitlines()
    bullet_lines = [l for l in lines if l.strip().startswith("- [ ]") or l.strip().startswith("> - [ ]")]
    assert bullet_lines
    for idx, line in enumerate(lines):
        if not (line.strip().startswith("- [ ]") or line.strip().startswith("> - [ ]")):
            continue
        assert "dom::" not in line
        if " · " in line:
            m = re.search(r"\)\s·\s(.+)$", line)
            assert m
            badges = m.group(1)
            assert badges == badges.lower()
            continue

        assert idx + 1 < len(lines)
        next_line = lines[idx + 1]
        assert next_line.startswith(">   ") or next_line.startswith("  ")
        assert " · " in next_line
        assert next_line.strip() == next_line.strip().lower()


def test_start_here_includes_context_line():
    payload = _load_payload()
    md = render_markdown(payload)
    start = _section(md, "## 🔥 Start Here")
    assert "> [!abstract] Today's Context:" in start
    assert "#" in start


def test_non_admin_sections_use_two_line_bullets():
    payload = _load_payload()
    md = render_markdown(payload)
    sections = [
        "## 🔥 Start Here",
        "## 📺 Watch / Listen Later",
        "## 📚 Read Later",
    ]
    for header in sections:
        section = _section(md, header)
        lines = section.splitlines()
        bullet_idxs = [i for i, line in enumerate(lines) if line.strip().startswith("- [ ]") or line.strip().startswith("> - [ ]")]
        assert bullet_idxs
        for idx in bullet_idxs:
            assert " · " not in lines[idx]
            assert idx + 1 < len(lines)
            next_line = lines[idx + 1]
            assert next_line.startswith("  ") or next_line.startswith(">   ")
            assert " · " in next_line


def test_docs_more_links_supports_energy_grouping_mode():
    payload = {
        "meta": {"created": "2026-02-07T06:00:00Z", "source": "docs_oneoff_energy.raw.json"},
        "counts": {"total": 12, "dumped": 12, "closed": 12, "kept": 0},
        "cfg": {
            "highPriorityLimit": 0,
            "docsLargeSectionDomainsGte": 10,
            "docsOneOffGroupingMode": "energy",
            "docsOneOffGroupByKindWhenDomainsGt": 8,
        },
        "items": [
            {"url": "https://a.com/docs/1", "title": "A1", "kind": "docs"},
            {"url": "https://a.com/docs/2", "title": "A2", "kind": "docs"},
            {"url": "https://b.com/article/1", "title": "B1", "kind": "article", "effort": "quick"},
            {"url": "https://c.com/article/1", "title": "C1", "kind": "article", "effort": "quick"},
            {"url": "https://d.com/docs/1", "title": "D1", "kind": "docs", "effort": "quick"},
            {"url": "https://e.com/docs/1", "title": "E1", "kind": "docs", "effort": "quick"},
            {"url": "https://f.com/paper/1.pdf", "title": "F1", "kind": "paper", "effort": "deep"},
            {"url": "https://g.com/spec/1", "title": "G1", "kind": "spec", "effort": "deep"},
            {"url": "https://h.com/misc/1", "title": "H1", "kind": "misc", "effort": "quick"},
            {"url": "https://i.com/docs/1", "title": "I1", "kind": "docs", "effort": "quick"},
            {"url": "https://j.com/docs/1", "title": "J1", "kind": "docs", "effort": "quick"},
            {"url": "https://k.com/docs/1", "title": "K1", "kind": "docs", "effort": "quick"},
        ],
    }
    md = render_markdown(payload)
    docs = _section(md, "## 📚 Read Later")
    assert "> #### Deep Reads (" in docs
    assert "> #### Quick References (" in docs
    assert "> #### Docs (" not in docs


def test_misc_kind_is_relabelled_by_section_for_projects_and_tools():
    payload = {
        "meta": {"created": "2026-02-16T09:31:52Z", "source": "section_kind_relabel.raw.json"},
        "counts": {"total": 2, "dumped": 2, "closed": 2, "kept": 0},
        "cfg": {"highPriorityLimit": 0},
        "items": [
            {
                "url": "https://drive.google.com/drive/folders/1jIJMyBOeWiVxLCUUtLvEFEFCnWxbh6cs",
                "title": "ML Books \u2013 Google Drive",
                "kind": "misc",
            },
            {
                "url": "https://console.cloud.google.com/apis/dashboard",
                "title": "Google Cloud Console",
                "kind": "misc",
            },
        ],
    }
    md = render_markdown(payload)
    projects = _section(md, "## 🗂 Projects")
    tools = _section(md, "## 🧰 Apps & Utilities")
    assert " · project" in projects
    assert " · misc" not in projects
    assert " · tool" in tools
    assert " · misc" not in tools


def test_domain_ordering_and_item_alpha():
    payload = {
        "meta": {"created": "2026-02-07T02:00:00Z", "source": "ordering.raw.json"},
        "counts": {"total": 5, "dumped": 5, "closed": 5, "kept": 0},
        "cfg": {"highPriorityLimit": 0},
        "items": [
            {"url": "https://b.com/docs/one", "title": "Gamma", "kind": "docs"},
            {"url": "https://b.com/docs/two", "title": "Beta", "kind": "docs"},
            {"url": "https://a.com/docs/one", "title": "Zeta", "kind": "docs"},
            {"url": "https://a.com/docs/two", "title": "Alpha", "kind": "docs"},
            {"url": "https://c.com/docs/one", "title": "Only", "kind": "docs"},
        ],
    }
    md = render_markdown(payload)
    docs = _section(md, "## 📚 Read Later")
    headers = re.findall(r"> ### ([^\n]+)", docs)
    assert headers[:3] == ["a.com", "b.com", "c.com"]
    # a.com items should be alpha by title
    lines = docs.splitlines()
    start = lines.index("> ### a.com")
    a_lines = []
    for line in lines[start + 1 :]:
        if line.startswith("> ###") or line.startswith("## "):
            break
        if line.strip().startswith("> - [ ]"):
            a_lines.append(line)
    assert a_lines
    assert "Alpha" in a_lines[0]


def test_keyword_exclusions_domain_wins():
    payload = {
        "meta": {"created": "2026-02-07T00:00:00Z", "source": "domain_wins.raw.json"},
        "counts": {"total": 1, "dumped": 1, "closed": 1, "kept": 0},
        "cfg": {"highPriorityLimit": 0},
        "items": [
            {
                "url": "https://amazon.com/best-ssd-vs-hdd",
                "title": "Best SSD vs HDD",
                "kind": "misc",
                "intent": {"action": "explore", "confidence": 0.6},
            }
        ],
    }
    md = render_markdown(payload)
    quick = _section(md, "## 🧹 Easy Tasks")
    assert "### Shopping" in quick
    assert "why:" not in quick


def test_quickwins_reason_kept_in_state_not_rendered():
    payload = json.loads(FIXTURE_QW_SUFFIX_JSON.read_text())
    state = build_state(payload)
    quick_items = state["buckets"]["QUICK"]
    assert quick_items
    assert any((it.get("quick_why") or "").startswith("leisure_") for it in quick_items)

    md = render_markdown(payload)
    quick = _section(md, "## 🧹 Easy Tasks")
    assert "why:" not in quick


def test_classification_precedence_admin_over_keywords():
    payload = {
        "meta": {"created": "2026-02-07T01:00:00Z", "source": "admin_over_keywords.raw.json"},
        "counts": {"total": 1, "dumped": 1, "closed": 1, "kept": 0},
        "cfg": {"highPriorityLimit": 0},
        "items": [
            {
                "url": "https://platform.openai.com/api-keys?buy=1",
                "title": "API keys buy now",
                "kind": "docs",
                "intent": {"action": "reference", "confidence": 0.8},
                "flags": {"is_auth": True},
            }
        ],
    }
    state = build_state(payload)
    assert state["buckets"]["ADMIN"]
    assert not state["buckets"]["QUICK"]


def test_projects_section_collects_nontech_project_hubs():
    payload = {
        "meta": {"created": "2026-02-07T08:00:00Z", "source": "projects_hubs.raw.json"},
        "counts": {"total": 5, "dumped": 5, "closed": 5, "kept": 0},
        "cfg": {"highPriorityLimit": 0},
        "items": [
            {
                "url": "https://acme.notion.so/Q1-Project-Plan-1a2b3c4d5e6f",
                "title": "Q1 Project Plan",
            },
            {
                "url": "https://trello.com/b/abcd1234/marketing-launch-board",
                "title": "Marketing Launch Board",
            },
            {
                "url": "https://acme.atlassian.net/jira/software/c/projects/APP/boards/42",
                "title": "APP Sprint Board",
            },
            {
                "url": "https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOp",
                "title": "Campaign Assets Folder",
            },
            {
                "url": "https://www.figma.com/file/ABCDEFG123/Product-Roadmap",
                "title": "Product Roadmap",
            },
        ],
    }
    state = build_state(payload)
    projects = state["buckets"]["PROJECTS"]
    assert len(projects) == 5
    project_urls = {it["url"] for it in projects}
    assert project_urls.isdisjoint({it["url"] for it in state["buckets"]["DOCS"]})
    assert project_urls.isdisjoint({it["url"] for it in state["buckets"]["TOOLS"]})
    assert project_urls.isdisjoint({it["url"] for it in state["buckets"]["QUICK"]})
    assert project_urls.isdisjoint({it["url"] for it in state["buckets"]["REPOS"]})

    md = render_markdown(payload)
    projects_section = _section(md, "## 🗂 Projects")
    assert "Q1 Project Plan" in projects_section
    assert "Marketing Launch Board" in projects_section
    assert "APP Sprint Board" in projects_section
    assert "Campaign Assets Folder" in projects_section
    assert "Product Roadmap" in projects_section


def test_notion_requires_project_hints_by_default():
    payload = {
        "meta": {"created": "2026-02-07T09:00:00Z", "source": "notion_non_project.raw.json"},
        "counts": {"total": 1, "dumped": 1, "closed": 1, "kept": 0},
        "cfg": {"highPriorityLimit": 0},
        "items": [
            {
                "url": "https://acme.notion.so/Meeting-Notes-6f5e4d3c2b1a",
                "title": "Meeting Notes",
            }
        ],
    }
    state = build_state(payload)
    assert not state["buckets"]["PROJECTS"]
    assert state["buckets"]["TOOLS"]
    assert not state["buckets"]["DOCS"]

    md = render_markdown(payload)
    assert "## 🗂 Projects" not in md
