import json
import re
from pathlib import Path

import pytest

from renderer_v3 import build_state, render_markdown, _score_item


ROOT = Path(__file__).resolve().parent.parent
FIXTURE_JSON = ROOT / "fixtures" / "sample_payload_v3.json"
FIXTURE_MD = ROOT / "fixtures" / "expected_sample_payload_v3_2.md"
FIXTURE_YT_JSON = ROOT / "fixtures" / "title_cleanup_youtube.json"
FIXTURE_GH_JSON = ROOT / "fixtures" / "title_cleanup_github.json"
FIXTURE_ADMIN_AUTH_JSON = ROOT / "fixtures" / "admin_auth_false_positive.json"
FIXTURE_DOCS_SUBGROUP_JSON = ROOT / "fixtures" / "docs_subgroup_intent.json"
FIXTURE_DOCS_DENOISE_JSON = ROOT / "fixtures" / "docs_denoise_dom_omit.json"
FIXTURE_QW_SUFFIX_JSON = ROOT / "fixtures" / "quickwins_suffix_disneyplus.json"
FIXTURE_QW_4CHAN_JSON = ROOT / "fixtures" / "quickwins_leisure_4chan.json"
FIXTURE_QW_NO_BEST_VS_JSON = ROOT / "fixtures" / "quickwins_no_best_vs.json"


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
    # Each bullet under a header should match that domain
    for heading in headers:
        domain = heading.split("•")[-1].strip() if "•" in heading else heading.strip()
        pattern = rf"> ### {re.escape(heading)}\n(> - \\[ \\] .*?)(?=\n> ###|\n##|\\Z)"
        match = re.search(pattern, md, flags=re.S)
        if not match:
            continue
        bullets = re.findall(r"\[Link\]\([^)]+\).*", match.group(0))
        assert bullets  # sanity
        for b in bullets:
            assert domain in b


# ---- v3.2.1 additions ----


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
    assert re.search(r"\*\*owner/repo\*\*", md)
    assert "GitHub -" not in md


def test_admin_auth_false_positive_not_classified():
    payload = json.loads(FIXTURE_ADMIN_AUTH_JSON.read_text())
    state = build_state(payload)
    admin_urls = {it["url"] for it in state["buckets"]["ADMIN"]}
    assert "https://example.com/docs/usage-token" not in admin_urls


def test_docs_intent_subgrouping():
    payload = json.loads(FIXTURE_DOCS_SUBGROUP_JSON.read_text())
    md = render_markdown(payload)
    docs_section = _section(md, "## 📚 Docs & Reading")
    assert "#### Implement" in docs_section
    assert "#### Debug" in docs_section
    assert "#### Reference" in docs_section
    assert "#### Learn" in docs_section


def test_admin_compact_bullets_default():
    payload = _load_payload()
    md = render_markdown(payload)
    admin_section = _section(md, "## 🔐 Tools & Admin")
    # Should not show dom/kind when adminVerboseBullets is false by default
    for line in admin_section.splitlines():
        if line.strip().startswith("> - [ ]"):
            assert "(dom::" not in line
            assert "(kind::" not in line


def test_docs_denoise_omit_dom_and_kind():
    payload = json.loads(FIXTURE_DOCS_DENOISE_JSON.read_text())
    md = render_markdown(payload)
    docs_section = _section(md, "## 📚 Docs & Reading")
    bullet_lines = [l for l in docs_section.splitlines() if l.strip().startswith("> - [ ]")]
    assert bullet_lines
    for line in bullet_lines:
        assert "dom::" not in line
        assert "kind:: docs" not in line


def test_quickwins_suffix_matching_disneyplus():
    payload = json.loads(FIXTURE_QW_SUFFIX_JSON.read_text())
    md = render_markdown(payload)
    quick = _section(md, "## 🧹 Quick Wins")
    assert "### Leisure" in quick
    assert "disneyplus" in quick.lower()


def test_quickwins_leisure_4chan():
    payload = json.loads(FIXTURE_QW_4CHAN_JSON.read_text())
    md = render_markdown(payload)
    quick = _section(md, "## 🧹 Quick Wins")
    assert "### Leisure" in quick
    assert "4chan" in quick


def test_quickwins_no_best_vs_keyword_only():
    payload = json.loads(FIXTURE_QW_NO_BEST_VS_JSON.read_text())
    md = render_markdown(payload)
    quick = _section(md, "## 🧹 Quick Wins")
    # Should fall into Misc (not Shopping)
    assert "### Shopping" not in quick
    assert "### Misc" in quick
