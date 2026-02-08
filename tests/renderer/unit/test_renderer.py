import pytest

from core.renderer.config import merge_cfg
from core.renderer.renderer import _merge_cfg, build_state, render_markdown


def _payload(items):
    return {
        "meta": {"created": "2026-02-08T10:00:00Z", "source": "unit.raw.json"},
        "counts": {"total": len(items), "dumped": len(items), "closed": len(items), "kept": 0},
        "items": items,
    }


def test_build_state_requires_payload():
    with pytest.raises(ValueError, match="payload is required"):
        build_state(None)


def test_merge_cfg_wrapper_matches_shared_merge_function():
    payload_cfg = {"titleMaxLen": 88}
    override_cfg = {"titleMaxLen": 44}
    assert _merge_cfg(payload_cfg, override_cfg) == merge_cfg(payload_cfg, override_cfg)


def test_build_state_normalizes_dedupes_and_annotates_bucket():
    payload = _payload(
        [
            {"url": "https://example.com/docs/a", "title": "Doc A", "kind": "docs"},
            {"url": "https://example.com/docs/a", "title": "Duplicate", "kind": "docs"},
        ]
    )

    state = build_state(payload)

    assert state["deduped_count"] == 1
    assert len(state["items"]) == 1
    item = state["items"][0]
    assert "bucket" in item
    assert item["bucket"] in state["buckets"]


def test_render_markdown_supports_cfg_alias_merge():
    payload = _payload(
        [
            {"url": "https://example.com/docs/a", "title": "Doc A", "kind": "docs"},
        ]
    )

    md = render_markdown(
        payload,
        cfg_override={"includeFocusLine": False},
        cfg={"includeEmptySections": True},
    )

    assert md.startswith("---\n")
    assert "# \U0001F4D1 Tab Dump:" in md
    assert "**Focus:**" not in md
    assert md.endswith("\n")
