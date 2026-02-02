import json
import re
from copy import deepcopy
from pathlib import Path

from renderer_v3 import render_markdown


ROOT = Path(__file__).resolve().parent.parent
FIXTURE_JSON = ROOT / "fixtures" / "sample_payload_v3.json"
FIXTURE_MD = ROOT / "fixtures" / "expected_sample_payload_v3.md"


def _load_sample():
    return json.loads(FIXTURE_JSON.read_text())


def _section(md: str, header: str) -> str:
    start = md.index(header)
    rest = md[start + len(header) :]
    m = re.search(r"\n## ", rest)
    if not m:
        return rest
    return rest[: m.start()]


def test_golden_snapshot():
    payload = _load_sample()
    md = render_markdown(payload)
    expected = FIXTURE_MD.read_text()
    assert md == expected


def test_no_duplicate_urls():
    payload = _load_sample()
    md = render_markdown(payload)
    urls = re.findall(r"\[Link\]\(([^)]+)\)", md)
    assert len(urls) == len(set(urls))


def test_high_priority_extraction_limit_and_isolation():
    payload = _load_sample()
    md = render_markdown(payload)
    high = _section(md, "## 🔥 High Priority")
    high_urls = set(re.findall(r"\[Link\]\(([^)]+)\)", high))
    assert len(high_urls) <= payload["cfg"]["nowLimit"]
    rest_urls = set(re.findall(r"\[Link\]\(([^)]+)\)", md.replace(high, "")))
    assert high_urls.isdisjoint(rest_urls)


def test_admin_callout_formatting():
    payload = _load_sample()
    md = render_markdown(payload)
    admin = _section(md, "## 🔐 Tools & Admin")
    header_line = [l for l in admin.splitlines() if l.startswith("> [!warning]")][0]
    assert "(2)" in header_line  # from sample fixture
    admin_bullets = [l for l in admin.splitlines() if l.strip().startswith("> - [ ]")]
    assert admin_bullets
    assert all(l.startswith("> - [ ]") for l in admin_bullets)


def test_dedup_count_and_single_instance():
    payload = _load_sample()
    md = render_markdown(payload)
    assert "deduped: 1" in md.splitlines()[7]
    urls = re.findall(r"https?://pganalyze.com[^\s)]+", md)
    assert len(urls) == 1


def test_determinism():
    payload = _load_sample()
    md1 = render_markdown(payload)
    md2 = render_markdown(payload)
    assert md1 == md2


def test_title_truncation_respects_max_len():
    payload = _load_sample()
    long_item = {
        "url": "https://example.com/long",
        "title": "L" * 200,
        "kind": "article",
        "topics": [{"slug": "long", "title": "Long", "confidence": 0.9}],
        "intent": {"action": "learn", "confidence": 0.9},
    }
    payload["items"] = [long_item]
    payload["counts"]["total"] = 1
    payload["cfg"]["titleMaxLen"] = 50
    md = render_markdown(payload)
    line = [l for l in md.splitlines() if l.startswith("- [ ]") or l.startswith("> - [ ]")][-1]
    title = re.search(r"\*\*(.+?)\*\*", line).group(1)
    assert len(title) <= payload["cfg"]["titleMaxLen"]
    assert title.endswith("…")
