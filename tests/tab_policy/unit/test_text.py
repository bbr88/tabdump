from core.tab_policy.text import slugify_kebab


def test_slugify_kebab_normalizes_text_and_collapse_separators():
    assert slugify_kebab("  Distributed Systems 101  ") == "distributed-systems-101"
    assert slugify_kebab("A___B---C") == "a-b-c"


def test_slugify_kebab_uses_fallback_for_empty_values():
    assert slugify_kebab("", fallback="other") == "other"
    assert slugify_kebab("***", fallback="fallback") == "fallback"
