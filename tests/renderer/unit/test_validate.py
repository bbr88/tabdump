import pytest

from core.renderer.validate import _annotate_bucket_on_items, _validate_coverage, _validate_rendered


def _buckets_with_all_keys(**overrides):
    buckets = {
        "HIGH": [],
        "MEDIA": [],
        "REPOS": [],
        "PROJECTS": [],
        "TOOLS": [],
        "DOCS": [],
        "QUICK": [],
        "BACKLOG": [],
        "ADMIN": [],
    }
    buckets.update(overrides)
    return buckets


def test_annotate_bucket_on_items_sets_bucket_name():
    buckets = _buckets_with_all_keys(HIGH=[{"url": "https://a"}], DOCS=[{"url": "https://b"}])
    _annotate_bucket_on_items(buckets)

    assert buckets["HIGH"][0]["bucket"] == "HIGH"
    assert buckets["DOCS"][0]["bucket"] == "DOCS"


def test_validate_coverage_success_and_failures():
    items = [{"url": "https://a"}, {"url": "https://b"}]
    ok = _buckets_with_all_keys(HIGH=[{"url": "https://a"}], DOCS=[{"url": "https://b"}])
    _validate_coverage(items, ok)

    dup = _buckets_with_all_keys(HIGH=[{"url": "https://a"}], DOCS=[{"url": "https://a"}, {"url": "https://b"}])
    with pytest.raises(ValueError, match="Duplicate URL"):
        _validate_coverage(items, dup)

    missing = _buckets_with_all_keys(HIGH=[{"url": "https://a"}])
    with pytest.raises(ValueError, match="Not all items assigned"):
        _validate_coverage(items, missing)


def test_validate_rendered_enforces_presence_and_order():
    cfg = {"includeEmptySections": False, "includeQuickWins": True}
    buckets = _buckets_with_all_keys(HIGH=[{"url": "https://a"}], ADMIN=[{"url": "https://b"}])

    md_ok = "\n".join([
        "## \U0001F525 Start Here",
        "content",
        "## \U0001F510 Accounts & Settings",
        "content",
    ])
    _validate_rendered(md_ok, buckets, cfg)

    md_missing = "## \U0001F525 Start Here\ncontent"
    with pytest.raises(ValueError, match="Missing section"):
        _validate_rendered(md_missing, buckets, cfg)

    md_wrong_order = "\n".join([
        "## \U0001F510 Accounts & Settings",
        "content",
        "## \U0001F525 Start Here",
        "content",
    ])
    with pytest.raises(ValueError, match="Section order incorrect"):
        _validate_rendered(md_wrong_order, buckets, cfg)
