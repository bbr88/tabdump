import json
import os
import plistlib
import re
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
        url = f"https://example.com/item/{i}?token=secret{i}"
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


def test_provenance_required_blocks_without_tabdump_id(tmp_path, monkeypatch):
    dump_path = _write_dump(tmp_path / "TabDump 2026-02-07 00-00-00.md", with_id=False)
    monkeypatch.setattr(ppt, "REQUIRE_PROVENANCE", True)
    rc = ppt.main(["postprocess_tabdump.py", str(dump_path)])
    assert rc == 4


def test_provenance_allows_with_tabdump_id(tmp_path, monkeypatch):
    dump_path = _write_dump(tmp_path / "TabDump 2026-02-07 00-00-00.md", with_id=True)

    monkeypatch.setattr(ppt, "REQUIRE_PROVENANCE", True)
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

    monkeypatch.setattr(ppt, "_call_with_retries", fake_call)
    monkeypatch.setattr(ppt, "render_markdown", fake_render)

    ppt.build_clean_note(Path("/tmp/ignore.md"), items, dump_id="id")

    payload_items = captured["payload"]["items"]
    assert payload_items[0]["kind"] == "docs"
    assert payload_items[0]["topics"][0]["slug"] == "beta"


def test_max_items_cap_limits_classification_only(monkeypatch):
    items = _make_items(4)
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
    line = next(l for l in md.splitlines() if "Hello" in l and "[Link]" in l)
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
                    "tagModel": "gpt-4.1-mini",
                    "llmRedact": True,
                    "llmRedactQuery": False,
                    "llmTitleMax": 123,
                    "maxItems": 7,
                    "requireProvenance": True,
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
    assert captured_env["TABDUMP_LLM_REDACT"] == "1"
    assert captured_env["TABDUMP_LLM_REDACT_QUERY"] == "0"
    assert captured_env["TABDUMP_LLM_TITLE_MAX"] == "123"
    assert captured_env["TABDUMP_MAX_ITEMS"] == "7"
    assert captured_env["TABDUMP_REQUIRE_PROVENANCE"] == "1"


def test_resolve_openai_api_key_prefers_keychain(monkeypatch):
    monkeypatch.setattr(ppt, "_key_from_keychain", lambda: "keychain-value")
    monkeypatch.setattr(ppt, "_key_from_launch_agent_plist", lambda: "plist-value")
    monkeypatch.setenv("OPENAI_API_KEY", "env-value")

    assert ppt.resolve_openai_api_key() == "keychain-value"


def test_resolve_openai_api_key_falls_back_to_plist(monkeypatch):
    monkeypatch.setattr(ppt, "_key_from_keychain", lambda: None)
    monkeypatch.setattr(ppt, "_key_from_launch_agent_plist", lambda: "plist-value")
    monkeypatch.setenv("OPENAI_API_KEY", "env-value")

    assert ppt.resolve_openai_api_key() == "plist-value"


def test_resolve_openai_api_key_falls_back_to_env(monkeypatch):
    monkeypatch.setattr(ppt, "_key_from_keychain", lambda: None)
    monkeypatch.setattr(ppt, "_key_from_launch_agent_plist", lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "  env-value  ")

    assert ppt.resolve_openai_api_key() == "env-value"


def test_resolve_openai_api_key_missing_everywhere(monkeypatch):
    monkeypatch.setattr(ppt, "_key_from_keychain", lambda: None)
    monkeypatch.setattr(ppt, "_key_from_launch_agent_plist", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert ppt.resolve_openai_api_key() is None


def test_key_from_launch_agent_plist_reads_environment_value(tmp_path, monkeypatch):
    plist_path = tmp_path / "io.orc-visioner.tabdump.monitor.plist"
    plist_data = {
        "Label": "io.orc-visioner.tabdump.monitor",
        "EnvironmentVariables": {"OPENAI_API_KEY": "plist-value"},
    }
    with plist_path.open("wb") as fh:
        plistlib.dump(plist_data, fh)

    monkeypatch.setattr(ppt, "LAUNCH_AGENT_PLIST", str(plist_path))
    assert ppt._key_from_launch_agent_plist() == "plist-value"


def test_openai_chat_json_missing_key_message(monkeypatch):
    monkeypatch.setattr(ppt, "KEYCHAIN_SERVICE", "Svc")
    monkeypatch.setattr(ppt, "KEYCHAIN_ACCOUNT", "Acct")
    monkeypatch.setattr(ppt, "LAUNCH_AGENT_PLIST", "/tmp/tabdump-test.plist")
    monkeypatch.setattr(ppt, "resolve_openai_api_key", lambda: None)

    with pytest.raises(RuntimeError) as exc:
        ppt.openai_chat_json("sys", "user")

    msg = str(exc.value)
    assert "Keychain (service=Svc, account=Acct)" in msg
    assert "LaunchAgent plist (/tmp/tabdump-test.plist)" in msg
    assert "env OPENAI_API_KEY" in msg
