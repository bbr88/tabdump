import json
import os
import re
import stat
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.monitor_tabs as monitor
import core.postprocess_tabdump as ppt
from core.postprocess_tabdump import Item
from core.renderer.renderer_v3 import render_markdown


def _write_dump(path: Path, *, with_id: bool) -> Path:
    lines = [
        "---",
        "created: 2026-02-07 00-00-00",
    ]
    if with_id:
        lines.append("tabdump_id: test-uuid")
    lines.extend(
        [
            "tags: [tabs, dump]",
            "---",
            "",
            "## Chrome",
            "",
            "- [Example](https://example.com/path?token=abc)",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _make_items(n: int) -> list[Item]:
    items: list[Item] = []
    for i in range(n):
        url = f"https://example.com/item/{i}?q=value{i}"
        items.append(
            Item(
                title=f"Title {i}",
                url=url,
                norm_url=ppt.normalize_url(url),
                clean_url=ppt.normalize_url(url),
                domain="example.com",
                browser=None,
            )
        )
    return items


def test_provenance_required_blocks_without_tabdump_id(tmp_path):
    dump_path = _write_dump(tmp_path / "TabDump 2026-02-07 00-00-00.md", with_id=False)
    rc = ppt.main(["postprocess_tabdump.py", str(dump_path)])
    assert rc == 4


def test_provenance_allows_with_tabdump_id(tmp_path, monkeypatch):
    dump_path = _write_dump(tmp_path / "TabDump 2026-02-07 00-00-00.md", with_id=True)

    monkeypatch.setattr(ppt, "_call_with_retries", lambda **kwargs: {"items": []})

    captured = {}

    def fake_render(payload, *args, **kwargs):
        captured["payload"] = payload
        return "md"

    monkeypatch.setattr(ppt, "render_markdown", fake_render)

    rc = ppt.main(["postprocess_tabdump.py", str(dump_path)])
    assert rc == 0

    clean_path = dump_path.with_name(dump_path.stem + " (clean)" + dump_path.suffix)
    assert clean_path.exists()
    assert clean_path.read_text(encoding="utf-8") == "md"
    assert captured["payload"]["meta"].get("tabdump_id") == "test-uuid"


def test_redact_url_query_params_for_llm(monkeypatch):
    monkeypatch.setattr(ppt, "REDACT_QUERY", True)
    out = ppt.redact_url_for_llm("https://example.com/cb?token=abc&foo=bar")
    assert "abc" not in out
    assert "bar" not in out
    assert "token=REDACTED" in out
    assert "foo=REDACTED" in out


def test_redact_text_for_llm_strips_control_and_sensitive_kv(monkeypatch):
    monkeypatch.setattr(ppt, "MAX_LLM_TITLE", 200)
    text = "hello\x00 token=abc123 world"
    out = ppt.redact_text_for_llm(text)
    assert "\x00" not in out
    assert "token=[REDACTED]" in out


def test_llm_id_mapping_uses_ids_not_urls(monkeypatch):
    items = _make_items(2)

    def fake_call(system, user, **kwargs):
        return {"items": [{"id": 1, "topic": "alpha", "kind": "repo", "action": "read", "score": 5}]}

    captured = {}

    def fake_render(payload, *args, **kwargs):
        captured["payload"] = payload
        return "md"

    monkeypatch.setattr(ppt, "LLM_ENABLED", True)
    monkeypatch.setattr(ppt, "resolve_openai_api_key", lambda: "key")
    monkeypatch.setattr(ppt, "_call_with_retries", fake_call)
    monkeypatch.setattr(ppt, "render_markdown", fake_render)

    ppt.build_clean_note(Path("/tmp/ignore.md"), items, dump_id="id")

    payload_items = captured["payload"]["items"]
    assert payload_items[1]["kind"] == "repo"
    assert payload_items[1]["topics"][0]["slug"] == "alpha"
    assert payload_items[0]["kind"] == "misc"


def test_llm_mapping_fallback_to_url(monkeypatch):
    items = _make_items(1)

    def fake_call(system, user, **kwargs):
        return {
            "items": [
                {"url": items[0].clean_url, "topic": "beta", "kind": "docs", "action": "read", "score": 4}
            ]
        }

    captured = {}

    def fake_render(payload, *args, **kwargs):
        captured["payload"] = payload
        return "md"

    monkeypatch.setattr(ppt, "LLM_ENABLED", True)
    monkeypatch.setattr(ppt, "resolve_openai_api_key", lambda: "key")
    monkeypatch.setattr(ppt, "_call_with_retries", fake_call)
    monkeypatch.setattr(ppt, "render_markdown", fake_render)

    ppt.build_clean_note(Path("/tmp/ignore.md"), items, dump_id="id")

    payload_items = captured["payload"]["items"]
    assert payload_items[0]["kind"] == "docs"
    assert payload_items[0]["topics"][0]["slug"] == "beta"


def test_max_items_cap_limits_classification_only(monkeypatch):
    items = _make_items(4)
    monkeypatch.setattr(ppt, "LLM_ENABLED", True)
    monkeypatch.setattr(ppt, "resolve_openai_api_key", lambda: "key")
    monkeypatch.setattr(ppt, "MAX_ITEMS", 2)

    calls: list[str] = []

    def fake_call(system, user, **kwargs):
        calls.append(user)
        return {
            "items": [
                {"id": 0, "topic": "alpha", "kind": "repo", "action": "read", "score": 5},
                {"id": 1, "topic": "alpha", "kind": "repo", "action": "read", "score": 5},
            ]
        }

    captured = {}

    def fake_render(payload, *args, **kwargs):
        captured["payload"] = payload
        return "md"

    monkeypatch.setattr(ppt, "_call_with_retries", fake_call)
    monkeypatch.setattr(ppt, "render_markdown", fake_render)

    ppt.build_clean_note(Path("/tmp/ignore.md"), items, dump_id="id")

    assert len(calls) == 1
    item_lines = [line for line in calls[0].splitlines() if re.match(r"^- \d+ \|", line)]
    assert len(item_lines) == 2

    payload_items = captured["payload"]["items"]
    assert len(payload_items) == 4
    assert payload_items[0]["kind"] == "repo"
    assert payload_items[1]["kind"] == "repo"
    assert payload_items[2]["kind"] == "misc"
    assert payload_items[3]["kind"] == "misc"


def test_renderer_escapes_markdown_in_titles():
    payload = {
        "meta": {"created": "2026-02-07T00:00:00Z", "source": "escape.raw.json"},
        "counts": {"total": 1, "dumped": 1, "closed": 1, "kept": 0},
        "cfg": {"highPriorityLimit": 0},
        "items": [
            {
                "url": "https://example.com/docs/one",
                "title": "Hello [x](y) *bold* `code` _u_",
                "kind": "docs",
            }
        ],
    }
    md = render_markdown(payload)
    line = next(l for l in md.splitlines() if "Hello" in l and "](" in l)
    assert "\\[x\\]\\(y\\)" in line
    assert "\\*bold\\*" in line
    assert "\\`code\\`" in line
    assert "\\_u\\_" in line


def test_monitor_passes_llm_env_from_config(tmp_path, monkeypatch):
    vault_inbox = tmp_path / "inbox"
    vault_inbox.mkdir()

    config_path = tmp_path / "config.json"
    config_path.write_text(
        (
            json.dumps(
                {
                    "vaultInbox": str(vault_inbox),
                    "checkEveryMinutes": 0,
                    "llmEnabled": True,
                    "tagModel": "gpt-4.1-mini",
                    "llmRedact": True,
                    "llmRedactQuery": False,
                    "llmTitleMax": 123,
                    "maxItems": 7,
                },
                indent=2,
            )
            + "\n"
        ),
        encoding="utf-8",
    )

    dump_path = _write_dump(vault_inbox / "TabDump 2026-02-07 00-00-00.md", with_id=True)
    future = time.time() + 10
    os.utime(dump_path, (future, future))

    monkeypatch.setattr(monitor, "DEFAULT_CFG", config_path)
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(monitor, "STATE_PATH", state_path)
    monkeypatch.setattr(monitor, "LOCK_PATH", state_path.with_suffix(".lock"))
    monkeypatch.setattr(monitor, "run_tabdump_app", lambda: None)
    monkeypatch.setattr(monitor.sys, "argv", ["monitor_tabs.py"])

    captured_env = {}

    def fake_run(args, capture_output, text, timeout, env):
        captured_env.update(env)
        return SimpleNamespace(returncode=3, stdout="", stderr="")

    monkeypatch.setattr(monitor.subprocess, "run", fake_run)

    rc = monitor.main()
    assert rc == 0
    assert captured_env["TABDUMP_LLM_ENABLED"] == "1"
    assert captured_env["TABDUMP_LLM_REDACT"] == "1"
    assert captured_env["TABDUMP_LLM_REDACT_QUERY"] == "0"
    assert captured_env["TABDUMP_LLM_TITLE_MAX"] == "123"
    assert captured_env["TABDUMP_MAX_ITEMS"] == "7"


def test_resolve_openai_api_key_prefers_keychain(monkeypatch):
    monkeypatch.setattr(ppt, "_key_from_keychain", lambda: "keychain-value")
    monkeypatch.setenv("OPENAI_API_KEY", "env-value")

    assert ppt.resolve_openai_api_key() == "keychain-value"


def test_resolve_openai_api_key_falls_back_to_env(monkeypatch):
    monkeypatch.setattr(ppt, "_key_from_keychain", lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "  env-value  ")

    assert ppt.resolve_openai_api_key() == "env-value"


def test_resolve_openai_api_key_missing_everywhere(monkeypatch):
    monkeypatch.setattr(ppt, "_key_from_keychain", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert ppt.resolve_openai_api_key() is None


def test_openai_chat_json_missing_key_message(monkeypatch):
    monkeypatch.setattr(ppt, "KEYCHAIN_SERVICE", "Svc")
    monkeypatch.setattr(ppt, "KEYCHAIN_ACCOUNT", "Acct")
    monkeypatch.setattr(ppt, "resolve_openai_api_key", lambda: None)

    with pytest.raises(RuntimeError) as exc:
        ppt.openai_chat_json("sys", "user")

    msg = str(exc.value)
    assert "Keychain (service=Svc, account=Acct)" in msg
    assert "env OPENAI_API_KEY" in msg


def test_llm_skips_sensitive_urls_and_assigns_safe_defaults(monkeypatch):
    items = [
        Item(
            title="API Keys",
            url="https://platform.openai.com/api-keys?token=abc",
            norm_url=ppt.normalize_url("https://platform.openai.com/api-keys?token=abc"),
            clean_url=ppt.normalize_url("https://platform.openai.com/api-keys?token=abc"),
            domain="platform.openai.com",
            browser=None,
        ),
        Item(
            title="Local admin",
            url="http://localhost:3000/admin",
            norm_url=ppt.normalize_url("http://localhost:3000/admin"),
            clean_url=ppt.normalize_url("http://localhost:3000/admin"),
            domain="localhost:3000",
            browser=None,
        ),
        Item(
            title="Normal docs",
            url="https://docs.python.org/3/tutorial/",
            norm_url=ppt.normalize_url("https://docs.python.org/3/tutorial/"),
            clean_url=ppt.normalize_url("https://docs.python.org/3/tutorial/"),
            domain="docs.python.org",
            browser=None,
        ),
    ]

    calls: list[str] = []

    def fake_call(system, user, **kwargs):
        calls.append(user)
        return {"items": [{"id": 2, "topic": "python", "kind": "docs", "action": "read", "score": 5}]}

    captured = {}

    def fake_render(payload, *args, **kwargs):
        captured["payload"] = payload
        return "md"

    monkeypatch.setattr(ppt, "LLM_ENABLED", True)
    monkeypatch.setattr(ppt, "resolve_openai_api_key", lambda: "key")
    monkeypatch.setattr(ppt, "_call_with_retries", fake_call)
    monkeypatch.setattr(ppt, "render_markdown", fake_render)

    ppt.build_clean_note(Path("/tmp/ignore.md"), items, dump_id="id")

    assert len(calls) == 1
    assert "platform.openai.com" not in calls[0]
    assert "localhost:3000" not in calls[0]
    assert "docs.python.org" in calls[0]

    payload_items = captured["payload"]["items"]
    assert payload_items[0]["kind"] == "auth"
    assert payload_items[1]["kind"] == "local"
    assert payload_items[2]["kind"] == "docs"


def test_local_classifier_used_when_llm_disabled(monkeypatch):
    items = _make_items(1)
    monkeypatch.setattr(ppt, "LLM_ENABLED", False)

    def fail_call(*args, **kwargs):
        raise AssertionError("LLM should not be called when disabled")

    captured = {}

    def fake_render(payload, *args, **kwargs):
        captured["payload"] = payload
        return "md"

    monkeypatch.setattr(ppt, "_call_with_retries", fail_call)
    monkeypatch.setattr(ppt, "render_markdown", fake_render)

    ppt.build_clean_note(Path("/tmp/ignore.md"), items, dump_id="id")
    entry = captured["payload"]["items"][0]
    assert entry["kind"] == "article"
    assert entry["intent"]["action"] in {"read", "reference"}


def test_llm_enabled_without_key_falls_back_to_local(monkeypatch):
    items = _make_items(1)
    monkeypatch.setattr(ppt, "LLM_ENABLED", True)
    monkeypatch.setattr(ppt, "resolve_openai_api_key", lambda: None)

    def fail_call(*args, **kwargs):
        raise AssertionError("LLM should not be called without key")

    captured = {}

    def fake_render(payload, *args, **kwargs):
        captured["payload"] = payload
        return "md"

    monkeypatch.setattr(ppt, "_call_with_retries", fail_call)
    monkeypatch.setattr(ppt, "render_markdown", fake_render)

    ppt.build_clean_note(Path("/tmp/ignore.md"), items, dump_id="id")
    entry = captured["payload"]["items"][0]
    assert entry["kind"] == "article"
    assert entry["intent"]["action"] in {"read", "reference"}


def test_extract_items_parses_parentheses_in_urls():
    md = (
        "---\n"
        "created: 2026-02-07 00-00-00\n"
        "tabdump_id: test-uuid\n"
        "---\n\n"
        "## Chrome\n\n"
        "- [Example](https://example.com/a_(b))\n"
    )
    items = ppt.extract_items(md)
    assert len(items) == 1
    assert items[0].clean_url == "https://example.com/a_(b)"


def test_extract_items_parses_nested_title_brackets_and_pdf_urls():
    md = (
        "---\n"
        "created: 2026-02-07 00-00-00\n"
        "tabdump_id: test-uuid\n"
        "---\n\n"
        "## Chrome\n\n"
        "- [pdfs/SEDA - An Architecture for Well-Conditioned, Scalable Internet Services (seda-sosp01).pdf at master · tpn/pdfs · GitHub](https://github.com/tpn/pdfs/blob/master/SEDA%20-%20An%20Architecture%20for%20Well-Conditioned,%20Scalable%20Internet%20Services%20(seda-sosp01).pdf)\n"
        "- [pdfs/Proving the Correctness of Nonblocking Data Structures - ACM (p30-desnoyers).pdf at master · tpn/pdfs · GitHub](https://github.com/tpn/pdfs/blob/master/Proving%20the%20Correctness%20of%20Nonblocking%20Data%20Structures%20-%20ACM%20(p30-desnoyers).pdf)\n"
        "- [Versioning in an Event Sourced System [Leanpub PDF/iPad/Kindle]](https://leanpub.com/esversioning)\n"
    )
    items = ppt.extract_items(md)
    assert len(items) == 3
    assert items[0].clean_url.endswith("(seda-sosp01).pdf")
    assert items[1].clean_url.endswith("(p30-desnoyers).pdf")
    assert items[2].clean_url == "https://leanpub.com/esversioning"


def test_renderer_encodes_markdown_sensitive_url_chars():
    payload = {
        "meta": {"created": "2026-02-07T00:00:00Z", "source": "escape-url.raw.json"},
        "counts": {"total": 1, "dumped": 1, "closed": 1, "kept": 0},
        "cfg": {"highPriorityLimit": 0},
        "items": [
            {
                "url": "https://example.com/a_(b)?q=hello world",
                "title": "Link",
                "kind": "docs",
            }
        ],
    }
    md = render_markdown(payload)
    line = next(l for l in md.splitlines() if "https://example.com/" in l and "](" in l)
    assert "a_%28b%29" in line
    assert "q=hello%20world" in line


def test_monitor_rejects_group_writable_config(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"vaultInbox": "/tmp", "checkEveryMinutes": 0}\n', encoding="utf-8")
    mode = cfg.stat().st_mode
    cfg.chmod(mode | stat.S_IWGRP)

    with pytest.raises(PermissionError):
        monitor._verify_runtime_integrity(cfg)
