import stat
from pathlib import Path

import pytest

import core.monitor_tabs as monitor
import core.postprocess.cli as ppt
from core.postprocess.cli import Item
from core.renderer.renderer import render_markdown

ROOT_DIR = Path(__file__).resolve().parents[3]
INSTALL_SCRIPT = ROOT_DIR / "scripts" / "install.sh"


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


@pytest.mark.policy("SEC-001")
def test_provenance_required_blocks_without_tabdump_id(tmp_path):
    dump_path = _write_dump(tmp_path / "TabDump 2026-02-07 00-00-00.md", with_id=False)
    rc = ppt.main(["cli.py", str(dump_path)])
    assert rc == 4


@pytest.mark.policy("SEC-001")
def test_provenance_allows_with_tabdump_id(tmp_path, monkeypatch):
    dump_path = _write_dump(tmp_path / "TabDump 2026-02-07 00-00-00.md", with_id=True)

    monkeypatch.setattr(ppt, "_call_with_retries", lambda **kwargs: {"items": []})

    captured = {}

    def fake_render(payload, *args, **kwargs):
        captured["payload"] = payload
        return "md"

    monkeypatch.setattr(ppt, "render_markdown", fake_render)

    rc = ppt.main(["cli.py", str(dump_path)])
    assert rc == 0

    clean_path = dump_path.with_name(dump_path.stem + " (clean)" + dump_path.suffix)
    assert clean_path.exists()
    assert clean_path.read_text(encoding="utf-8") == "md"
    assert captured["payload"]["meta"].get("tabdump_id") == "test-uuid"


@pytest.mark.policy("SEC-003")
def test_redact_url_query_params_for_llm(monkeypatch):
    monkeypatch.setattr(ppt, "REDACT_QUERY", True)
    out = ppt.redact_url_for_llm("https://example.com/cb?token=abc&foo=bar")
    assert "abc" not in out
    assert "bar" not in out
    assert "token=REDACTED" in out
    assert "foo=REDACTED" in out


@pytest.mark.policy("SEC-003")
def test_redact_text_for_llm_strips_control_and_sensitive_kv(monkeypatch):
    monkeypatch.setattr(ppt, "MAX_LLM_TITLE", 200)
    text = "hello\x00 token=abc123 world"
    out = ppt.redact_text_for_llm(text)
    assert "\x00" not in out
    assert "token=[REDACTED]" in out


@pytest.mark.policy("SEC-005")
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


@pytest.mark.policy("SEC-004")
def test_resolve_openai_api_key_prefers_keychain(monkeypatch):
    monkeypatch.setattr(ppt, "_key_from_keychain", lambda: "keychain-value")
    monkeypatch.setenv("OPENAI_API_KEY", "env-value")

    assert ppt.resolve_openai_api_key() == "keychain-value"


@pytest.mark.policy("SEC-004")
def test_resolve_openai_api_key_falls_back_to_env(monkeypatch):
    monkeypatch.setattr(ppt, "_key_from_keychain", lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "  env-value  ")

    assert ppt.resolve_openai_api_key() == "env-value"


@pytest.mark.policy("SEC-004")
def test_resolve_openai_api_key_missing_everywhere(monkeypatch):
    monkeypatch.setattr(ppt, "_key_from_keychain", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert ppt.resolve_openai_api_key() is None


@pytest.mark.policy("SEC-004")
def test_openai_chat_json_missing_key_message(monkeypatch):
    monkeypatch.setattr(ppt, "KEYCHAIN_SERVICE", "Svc")
    monkeypatch.setattr(ppt, "KEYCHAIN_ACCOUNT", "Acct")
    monkeypatch.setattr(ppt, "resolve_openai_api_key", lambda: None)

    with pytest.raises(RuntimeError) as exc:
        ppt.openai_chat_json("sys", "user")

    msg = str(exc.value)
    assert "Keychain (service=Svc, account=Acct)" in msg
    assert "env OPENAI_API_KEY" in msg


@pytest.mark.policy("SEC-002")
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


@pytest.mark.policy("SEC-002")
def test_sensitive_host_path_marker_applies_only_to_settings_path():
    assert ppt._is_sensitive_url("https://github.com/settings/profile")
    assert not ppt._is_sensitive_url("https://github.com/openai/openai-python")


@pytest.mark.policy("SEC-006")
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


@pytest.mark.policy("SEC-006")
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


@pytest.mark.policy("SEC-005")
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


@pytest.mark.policy("SEC-007")
def test_monitor_rejects_group_writable_config(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"vaultInbox": "/tmp", "checkEveryMinutes": 0}\n', encoding="utf-8")
    mode = cfg.stat().st_mode
    cfg.chmod(mode | stat.S_IWGRP)

    with pytest.raises(PermissionError):
        monitor._verify_runtime_integrity(cfg)


@pytest.mark.policy("SEC-008")
def test_installer_verifies_runtime_manifest_and_fails_closed():
    text = INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert "verify_runtime_manifest()" in text
    assert "shasum -a 256 -c" in text
    assert "Runtime manifest verification failed. Aborting install." in text
    assert "verify_runtime_manifest" in text and "exit 1" in text


@pytest.mark.policy("SEC-009")
def test_installer_enforces_restrictive_permissions():
    text = INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert "umask 077" in text
    assert "chmod 700" in text
    assert "chmod 600" in text
