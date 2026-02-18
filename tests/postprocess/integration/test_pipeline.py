import io
from pathlib import Path

from core.postprocess.models import Item
from core.postprocess.pipeline import build_clean_note
from core.postprocess.urls import normalize_url


def _item(title: str, url: str, domain: str) -> Item:
    clean = normalize_url(url)
    return Item(
        title=title,
        url=url,
        norm_url=clean,
        clean_url=clean,
        domain=domain,
        browser=None,
    )


def test_build_clean_note_uses_llm_and_skips_sensitive_items():
    items = [
        _item("Secrets", "https://example.com/secret?token=abc", "example.com"),
        _item("Docs", "https://docs.python.org/3/tutorial/", "docs.python.org"),
    ]

    seen = {}
    captured = {}

    def classify_with_llm(indexed_for_cls, url_to_idx, api_key):
        seen["indexed"] = indexed_for_cls
        seen["api_key"] = api_key
        assert url_to_idx[items[1].norm_url] == 1
        return {1: {"topic": "python", "kind": "docs", "action": "read", "score": 5}}

    def render(payload, cfg):
        captured["payload"] = payload
        return "md-output"

    md, meta = build_clean_note(
        src_path=Path("/tmp/in.md"),
        items=items,
        dump_id="dump-1",
        llm_enabled=True,
        resolve_openai_api_key_fn=lambda: "k",
        classify_with_llm_fn=classify_with_llm,
        is_sensitive_url_fn=lambda url: "secret" in url,
        default_kind_action_fn=lambda _: ("auth", "ignore"),
        extract_created_ts_fn=lambda *_args, **_kwargs: "2026-02-08 00-00-00",
        render_markdown_fn=render,
    )

    assert md == "md-output"
    assert meta["tabdump_id"] == "dump-1"
    assert seen["api_key"] == "k"
    assert [idx for idx, _ in seen["indexed"]] == [1]

    payload = captured["payload"]
    assert payload["counts"] == {"total": 2, "dumped": 2, "closed": 0, "kept": 0}
    assert payload["items"][0]["kind"] == "auth"
    assert payload["items"][0]["intent"]["action"] == "ignore"
    assert payload["items"][0]["intent"]["confidence"] == 0.6
    assert payload["items"][0]["effort"] == "quick"
    assert payload["items"][1]["kind"] == "docs"
    assert payload["items"][1]["topics"][0]["slug"] == "python"
    assert payload["items"][1]["effort"] == "medium"


def test_build_clean_note_falls_back_to_local_when_llm_enabled_but_key_missing():
    items = [_item("Title", "https://example.com/article", "example.com")]
    stderr = io.StringIO()

    def classify_local(_item_obj):
        return {"topic": "local-topic", "kind": "article", "action": "read", "score": 4}

    captured = {}

    def render(payload, cfg):
        captured["payload"] = payload
        return "md"

    md, _ = build_clean_note(
        src_path=Path("/tmp/in.md"),
        items=items,
        llm_enabled=True,
        resolve_openai_api_key_fn=lambda: None,
        classify_with_llm_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not call llm")),
        classify_local_fn=classify_local,
        extract_created_ts_fn=lambda *_args, **_kwargs: "ts",
        render_markdown_fn=render,
        stderr=stderr,
    )

    assert md == "md"
    assert "LLM disabled: OpenAI API key not found" in stderr.getvalue()
    assert captured["payload"]["items"][0]["kind"] == "article"
    assert captured["payload"]["items"][0]["topics"][0]["slug"] == "local-topic"
    assert captured["payload"]["items"][0]["effort"] == "medium"


def test_build_clean_note_falls_back_to_local_when_llm_coverage_is_below_threshold():
    items = [_item("Unknown", "https://example.com/x", "example.com")]

    captured = {}

    def render(payload, cfg):
        captured["payload"] = payload
        return "md"

    md, _ = build_clean_note(
        src_path=Path("/tmp/in.md"),
        items=items,
        llm_enabled=True,
        resolve_openai_api_key_fn=lambda: "key",
        classify_with_llm_fn=lambda *_args, **_kwargs: {},
        classify_local_fn=lambda *_args, **_kwargs: {
            "topic": "local-topic",
            "kind": "article",
            "action": "read",
            "score": 4,
        },
        extract_created_ts_fn=lambda *_args, **_kwargs: "ts",
        render_markdown_fn=render,
    )

    assert md == "md"
    entry = captured["payload"]["items"][0]
    assert entry["kind"] == "article"
    assert entry["intent"]["action"] == "read"
    assert entry["topics"][0]["slug"] == "local-topic"
    assert entry["effort"] == "medium"


def test_build_clean_note_defaults_unmapped_when_llm_coverage_is_above_threshold():
    items = [
        _item("Item 0", "https://example.com/0", "example.com"),
        _item("Item 1", "https://example.com/1", "example.com"),
        _item("Item 2", "https://example.com/2", "example.com"),
        _item("Item 3", "https://example.com/3", "example.com"),
    ]
    captured = {}

    def render(payload, cfg):
        captured["payload"] = payload
        return "md"

    md, _ = build_clean_note(
        src_path=Path("/tmp/in.md"),
        items=items,
        llm_enabled=True,
        resolve_openai_api_key_fn=lambda: "key",
        classify_with_llm_fn=lambda *_args, **_kwargs: {
            0: {"topic": "alpha", "kind": "docs", "action": "read", "score": 3},
            1: {"topic": "alpha", "kind": "docs", "action": "read", "score": 3},
            2: {"topic": "alpha", "kind": "docs", "action": "read", "score": 3},
        },
        classify_local_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not call local")),
        extract_created_ts_fn=lambda *_args, **_kwargs: "ts",
        render_markdown_fn=render,
    )

    assert md == "md"
    payload_items = captured["payload"]["items"]
    assert payload_items[3]["kind"] == "misc"
    assert payload_items[3]["intent"]["action"] == "triage"


def test_build_clean_note_supports_raw_derived_and_hybrid_action_policy():
    item = _item("Fix issue", "https://github.com/org/repo/issues/1", "github.com")

    def _action_for(policy: str) -> str:
        captured = {}

        def render(payload, cfg):
            captured["payload"] = payload
            return "md"

        build_clean_note(
            src_path=Path("/tmp/in.md"),
            items=[item],
            llm_enabled=True,
            resolve_openai_api_key_fn=lambda: "key",
            classify_with_llm_fn=lambda *_args, **_kwargs: {
                0: {"topic": "dev", "kind": "repo", "action": "read", "score": 4}
            },
            llm_action_policy=policy,
            min_llm_coverage=0.0,
            extract_created_ts_fn=lambda *_args, **_kwargs: "ts",
            render_markdown_fn=render,
        )
        return captured["payload"]["items"][0]["intent"]["action"]

    assert _action_for("raw") == "read"
    assert _action_for("derived") == "triage"
    assert _action_for("hybrid") == "triage"


def test_build_clean_note_effort_does_not_collapse_for_core_kinds():
    items = [
        _item("Movie trailer 2 min", "https://media.example/video/trailer", "media.example"),
        _item("Full course personal finance 4h", "https://media.example/video/full-course", "media.example"),
        _item("API reference cheat sheet", "https://docs.example/reference/card", "docs.example"),
        _item("Complete guide to retirement planning", "https://docs.example/guide/retirement", "docs.example"),
        _item("Weekly market recap 10 min", "https://news.example/article/recap", "news.example"),
        _item("Longform guide to debt recovery", "https://news.example/article/debt-recovery", "news.example"),
        _item("Issue triage board", "https://projects.example/repo/issues", "projects.example"),
        _item("Architecture migration plan", "https://projects.example/repo/migration", "projects.example"),
        _item("Calendar dashboard", "https://apps.example/tool/dashboard", "apps.example"),
        _item("End-to-end automation workflow setup", "https://apps.example/tool/workflow", "apps.example"),
    ]

    captured = {}

    def render(payload, cfg):
        captured["payload"] = payload
        return "md"

    cls_map = {
        0: {"topic": "entertainment", "kind": "video", "action": "watch", "score": 2},
        1: {"topic": "finance", "kind": "video", "action": "watch", "score": 4},
        2: {"topic": "reference", "kind": "docs", "action": "reference", "score": 3},
        3: {"topic": "finance", "kind": "docs", "action": "read", "score": 4},
        4: {"topic": "finance", "kind": "article", "action": "read", "score": 3},
        5: {"topic": "finance", "kind": "article", "action": "read", "score": 4},
        6: {"topic": "work", "kind": "repo", "action": "triage", "score": 3},
        7: {"topic": "work", "kind": "repo", "action": "build", "score": 4},
        8: {"topic": "productivity", "kind": "tool", "action": "triage", "score": 2},
        9: {"topic": "productivity", "kind": "tool", "action": "build", "score": 4},
    }

    md, _ = build_clean_note(
        src_path=Path("/tmp/in.md"),
        items=items,
        llm_enabled=True,
        resolve_openai_api_key_fn=lambda: "key",
        classify_with_llm_fn=lambda *_args, **_kwargs: cls_map,
        extract_created_ts_fn=lambda *_args, **_kwargs: "ts",
        render_markdown_fn=render,
    )

    assert md == "md"
    effort_by_kind = {}
    for item in captured["payload"]["items"]:
        effort_by_kind.setdefault(item["kind"], set()).add(item["effort"])

    for kind in ("video", "docs", "article", "repo", "tool"):
        assert len(effort_by_kind[kind]) >= 2, f"{kind} effort collapsed: {sorted(effort_by_kind[kind])}"
