from core.renderer.config import ALLOWED_KINDS, DEFAULT_CFG, merge_cfg


def test_merge_cfg_applies_payload_then_override():
    payload_cfg = {
        "titleMaxLen": 77,
        "includeFocusLine": False,
        "render": {"badges": {"enabled": False}},
    }
    override_cfg = {
        "titleMaxLen": 42,
        "quickWinsMaxItems": 9,
    }

    merged = merge_cfg(payload_cfg, override_cfg)

    assert merged["titleMaxLen"] == 42
    assert merged["includeFocusLine"] is False
    assert merged["quickWinsMaxItems"] == 9
    assert merged["render"] == {"badges": {"enabled": False}}


def test_defaults_include_shared_taxonomy_hints():
    assert "netflix.com" in DEFAULT_CFG["videoDomains"]
    assert "music.yandex.ru" in DEFAULT_CFG["musicDomains"]
    assert "/api" in DEFAULT_CFG["docsPathHints"]
    assert "/post/" in DEFAULT_CFG["blogPathHints"]
    assert "access_token" in DEFAULT_CFG["authContainsHintsSoft"]


def test_allowed_kinds_keeps_renderer_specific_and_postprocess_values():
    assert "spec" in ALLOWED_KINDS
    assert "admin" in ALLOWED_KINDS
    assert "local" in ALLOWED_KINDS
    assert "video" in ALLOWED_KINDS
    assert "music" in ALLOWED_KINDS
