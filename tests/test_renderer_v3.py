import json
import re
from pathlib import Path

import pytest

from renderer_v3 import build_state, render_markdown, _score_item


ROOT = Path(__file__).resolve().parent.parent
FIXTURE_JSON = ROOT / "fixtures" / "sample_payload_v3.json"
FIXTURE_MD = ROOT / "fixtures" / "expected_sample_payload_v3_2.md"


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
