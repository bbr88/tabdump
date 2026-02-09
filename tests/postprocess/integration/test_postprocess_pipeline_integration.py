import json
import os
import re
import time
from pathlib import Path
from types import SimpleNamespace

import core.monitor_tabs as monitor
import core.postprocess.cli as ppt
from core.postprocess.cli import Item


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


def test_monitor_auto_switches_dry_run_after_first_clean_dump(tmp_path, monkeypatch):
    vault_inbox = tmp_path / "inbox"
    vault_inbox.mkdir()

    config_path = tmp_path / "config.json"
    config_path.write_text(
        (
            json.dumps(
                {
                    "vaultInbox": str(vault_inbox),
                    "checkEveryMinutes": 0,
                    "dryRun": True,
                    "dryRunPolicy": "auto",
                    "onboardingStartedAt": 1700000000,
                    "llmEnabled": False,
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

    clean_path = vault_inbox / "TabDump 2026-02-07 00-00-00 (clean).md"

    def fake_run(args, capture_output, text, timeout, env):
        return SimpleNamespace(returncode=0, stdout=str(clean_path), stderr="")

    monkeypatch.setattr(monitor.subprocess, "run", fake_run)

    rc = monitor.main()
    assert rc == 0

    saved_cfg = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved_cfg["dryRun"] is False
    assert saved_cfg["dryRunPolicy"] == "auto"

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["lastClean"] == str(clean_path)
    assert state["autoSwitchReason"] == "first_clean_dump"
    assert isinstance(state["autoSwitchedAt"], float)


def test_monitor_force_mode_override_is_temporary(tmp_path, monkeypatch, capsys):
    vault_inbox = tmp_path / "inbox"
    vault_inbox.mkdir()

    base_cfg = {
        "vaultInbox": str(vault_inbox),
        "checkEveryMinutes": 99,
        "cooldownMinutes": 45,
        "maxTabs": 30,
        "dryRun": True,
        "dryRunPolicy": "manual",
        "onboardingStartedAt": 1700000000,
        "llmEnabled": False,
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(base_cfg, indent=2) + "\n", encoding="utf-8")

    dump_path = _write_dump(vault_inbox / "TabDump 2026-02-07 00-00-00.md", with_id=True)
    future = time.time() + 10
    os.utime(dump_path, (future, future))

    monkeypatch.setattr(monitor, "DEFAULT_CFG", config_path)
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(monitor, "STATE_PATH", state_path)
    monkeypatch.setattr(monitor, "LOCK_PATH", state_path.with_suffix(".lock"))
    seen_cfg = {}

    def fake_run_tabdump_app():
        seen_cfg.update(json.loads(config_path.read_text(encoding="utf-8")))

    monkeypatch.setattr(monitor, "run_tabdump_app", fake_run_tabdump_app)
    monkeypatch.setattr(monitor.sys, "argv", ["monitor_tabs.py", "--force", "--mode", "dump-close", "--json"])

    clean_path = vault_inbox / "TabDump 2026-02-07 00-00-00 (clean).md"

    def fake_run(args, capture_output, text, timeout, env):
        return SimpleNamespace(returncode=0, stdout=str(clean_path), stderr="")

    monkeypatch.setattr(monitor.subprocess, "run", fake_run)

    rc = monitor.main()
    assert rc == 0

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "ok"
    assert payload["forced"] is True
    assert payload["mode"] == "dump-close"
    assert payload["cleanNote"] == str(clean_path)

    assert seen_cfg["checkEveryMinutes"] == 0
    assert seen_cfg["cooldownMinutes"] == 0
    assert seen_cfg["maxTabs"] == 0
    assert seen_cfg["dryRun"] is False

    restored_cfg = json.loads(config_path.read_text(encoding="utf-8"))
    assert restored_cfg == base_cfg


def test_monitor_force_override_preserves_auto_switch(tmp_path, monkeypatch):
    vault_inbox = tmp_path / "inbox"
    vault_inbox.mkdir()

    config_path = tmp_path / "config.json"
    config_path.write_text(
        (
            json.dumps(
                {
                    "vaultInbox": str(vault_inbox),
                    "checkEveryMinutes": 99,
                    "cooldownMinutes": 45,
                    "maxTabs": 30,
                    "dryRun": True,
                    "dryRunPolicy": "auto",
                    "onboardingStartedAt": 1700000000,
                    "llmEnabled": False,
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
    monkeypatch.setattr(monitor.sys, "argv", ["monitor_tabs.py", "--force", "--mode", "dump-close"])

    clean_path = vault_inbox / "TabDump 2026-02-07 00-00-00 (clean).md"

    def fake_run(args, capture_output, text, timeout, env):
        return SimpleNamespace(returncode=0, stdout=str(clean_path), stderr="")

    monkeypatch.setattr(monitor.subprocess, "run", fake_run)

    rc = monitor.main()
    assert rc == 0

    saved_cfg = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved_cfg["dryRun"] is False
    assert saved_cfg["dryRunPolicy"] == "auto"
    assert saved_cfg["checkEveryMinutes"] == 99
    assert saved_cfg["cooldownMinutes"] == 45
    assert saved_cfg["maxTabs"] == 30


def test_monitor_trust_ramp_notification_includes_cta(tmp_path, monkeypatch):
    vault_inbox = tmp_path / "inbox"
    vault_inbox.mkdir()

    config_path = tmp_path / "config.json"
    config_path.write_text(
        (
            json.dumps(
                {
                    "vaultInbox": str(vault_inbox),
                    "checkEveryMinutes": 0,
                    "dryRun": False,
                    "dryRunPolicy": "manual",
                    "onboardingStartedAt": int(time.time()),
                    "llmEnabled": False,
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

    clean_path = vault_inbox / "TabDump 2026-02-07 00-00-00 (clean).md"

    def fake_run(args, capture_output, text, timeout, env):
        return SimpleNamespace(returncode=0, stdout=str(clean_path), stderr="")

    monkeypatch.setattr(monitor.subprocess, "run", fake_run)

    calls = []
    monkeypatch.setattr(monitor, "notify_user", lambda title, message: calls.append((title, message)))

    rc = monitor.main()
    assert rc == 0
    assert any("Review top 3 items now." in message for _, message in calls)


def test_monitor_post_ramp_notification_is_concise(tmp_path, monkeypatch):
    vault_inbox = tmp_path / "inbox"
    vault_inbox.mkdir()

    config_path = tmp_path / "config.json"
    config_path.write_text(
        (
            json.dumps(
                {
                    "vaultInbox": str(vault_inbox),
                    "checkEveryMinutes": 0,
                    "dryRun": False,
                    "dryRunPolicy": "manual",
                    "onboardingStartedAt": int(time.time()) - (monitor.TRUST_RAMP_DAYS + 1) * 86400,
                    "llmEnabled": False,
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

    clean_path = vault_inbox / "TabDump 2026-02-07 00-00-00 (clean).md"

    def fake_run(args, capture_output, text, timeout, env):
        return SimpleNamespace(returncode=0, stdout=str(clean_path), stderr="")

    monkeypatch.setattr(monitor.subprocess, "run", fake_run)

    calls = []
    monkeypatch.setattr(monitor, "notify_user", lambda title, message: calls.append((title, message)))

    rc = monitor.main()
    assert rc == 0
    assert any("Clean dump ready:" in message for _, message in calls)
    assert all("Review top 3 items now." not in message for _, message in calls)


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


def test_local_classifier_matches_plural_blogs_path():
    item = Item(
        title="Summer travel ideas",
        url="https://example.com/blogs/summer-travel-ideas",
        norm_url=ppt.normalize_url("https://example.com/blogs/summer-travel-ideas"),
        clean_url=ppt.normalize_url("https://example.com/blogs/summer-travel-ideas"),
        domain="example.com",
        browser=None,
    )
    cls = ppt._classify_local(item)
    assert cls["kind"] == "article"
    assert cls["topic"] == "travel"


def test_local_classifier_identifies_general_tool_domains():
    item = Item(
        title="Family calendar",
        url="https://calendar.google.com/calendar/u/0/r",
        norm_url=ppt.normalize_url("https://calendar.google.com/calendar/u/0/r"),
        clean_url=ppt.normalize_url("https://calendar.google.com/calendar/u/0/r"),
        domain="calendar.google.com",
        browser=None,
    )
    cls = ppt._classify_local(item)
    assert cls["kind"] == "tool"
    assert cls["topic"] == "productivity"


def test_local_classifier_uses_paper_hints_without_pdf_suffix():
    item = Item(
        title="Reliable Event Streaming Whitepaper",
        url="https://arxiv.org/abs/2401.12345",
        norm_url=ppt.normalize_url("https://arxiv.org/abs/2401.12345"),
        clean_url=ppt.normalize_url("https://arxiv.org/abs/2401.12345"),
        domain="arxiv.org",
        browser=None,
    )
    cls = ppt._classify_local(item)
    assert cls["kind"] == "paper"


def test_local_classifier_uses_project_hints_for_action():
    item = Item(
        title="Sprint planning board",
        url="https://linear.app/acme/issue/APP-123",
        norm_url=ppt.normalize_url("https://linear.app/acme/issue/APP-123"),
        clean_url=ppt.normalize_url("https://linear.app/acme/issue/APP-123"),
        domain="linear.app",
        browser=None,
    )
    cls = ppt._classify_local(item)
    assert cls["kind"] == "tool"
    assert cls["action"] == "build"
    assert cls["topic"] == "project-management"


def test_local_classifier_uses_ui_ux_hints_for_topic():
    item = Item(
        title="Figma component kit",
        url="https://workspace.app/ui-kit/storybook",
        norm_url=ppt.normalize_url("https://workspace.app/ui-kit/storybook"),
        clean_url=ppt.normalize_url("https://workspace.app/ui-kit/storybook"),
        domain="workspace.app",
        browser=None,
    )
    cls = ppt._classify_local(item)
    assert cls["topic"] == "ui-ux"


def test_local_classifier_blog_under_docs_domain_prefers_article():
    item = Item(
        title="Product launch blog post",
        url="https://docs.example.com/blog/my-post",
        norm_url=ppt.normalize_url("https://docs.example.com/blog/my-post"),
        clean_url=ppt.normalize_url("https://docs.example.com/blog/my-post"),
        domain="docs.example.com",
        browser=None,
    )
    cls = ppt._classify_local(item)
    assert cls["kind"] == "article"


def test_local_classifier_code_host_short_path_is_repo():
    item = Item(
        title="Microsoft on GitHub",
        url="https://github.com/microsoft",
        norm_url=ppt.normalize_url("https://github.com/microsoft"),
        clean_url=ppt.normalize_url("https://github.com/microsoft"),
        domain="github.com",
        browser=None,
    )
    cls = ppt._classify_local(item)
    assert cls["kind"] == "repo"


def test_local_classifier_go_boundary_match_learning_go():
    item = Item(
        title="Learning Go.",
        url="https://example.com/programming/intro",
        norm_url=ppt.normalize_url("https://example.com/programming/intro"),
        clean_url=ppt.normalize_url("https://example.com/programming/intro"),
        domain="example.com",
        browser=None,
    )
    cls = ppt._classify_local(item)
    assert cls["topic"] == "go"


def test_local_classifier_deep_paper_sets_deep_work_and_high_score():
    item = Item(
        title="Distributed systems whitepaper guide",
        url="https://arxiv.org/abs/2402.98765",
        norm_url=ppt.normalize_url("https://arxiv.org/abs/2402.98765"),
        clean_url=ppt.normalize_url("https://arxiv.org/abs/2402.98765"),
        domain="arxiv.org",
        browser=None,
    )
    cls = ppt._classify_local(item)
    assert cls["kind"] == "paper"
    assert cls["action"] == "deep_work"
    assert cls["score"] == 5


def test_case_documentation_trap_docs_reference():
    item = Item(
        title="GitHub REST API reference",
        url="https://docs.github.com/en/rest/reference/repos",
        norm_url=ppt.normalize_url("https://docs.github.com/en/rest/reference/repos"),
        clean_url=ppt.normalize_url("https://docs.github.com/en/rest/reference/repos"),
        domain="docs.github.com",
        browser=None,
    )
    cls = ppt._classify_local(item)
    assert cls["kind"] == "docs"
    assert cls["action"] == "reference"


def test_local_classifier_does_not_treat_release_slug_as_docs():
    item = Item(
        title="Release It! Second Edition: Design and Deploy Production-Ready Software by Michael Nygard",
        url="https://pragprog.com/titles/mnee2/release-it-second-edition",
        norm_url=ppt.normalize_url("https://pragprog.com/titles/mnee2/release-it-second-edition"),
        clean_url=ppt.normalize_url("https://pragprog.com/titles/mnee2/release-it-second-edition"),
        domain="pragprog.com",
        browser=None,
    )
    cls = ppt._classify_local(item)
    assert cls["kind"] == "article"


def test_local_classifier_does_not_match_spec_inside_specific_word():
    item = Item(
        title="Context Mapper is an open source project providing a Domain-specific Language",
        url="https://contextmapper.org/",
        norm_url=ppt.normalize_url("https://contextmapper.org/"),
        clean_url=ppt.normalize_url("https://contextmapper.org/"),
        domain="contextmapper.org",
        browser=None,
    )
    cls = ppt._classify_local(item)
    assert cls["kind"] == "tool"


def test_local_classifier_treats_mcp_servers_as_tools():
    item = Item(
        title="Context7 - MCP | Smithery",
        url="https://smithery.ai/server/upstash/context7-mcp",
        norm_url=ppt.normalize_url("https://smithery.ai/server/upstash/context7-mcp"),
        clean_url=ppt.normalize_url("https://smithery.ai/server/upstash/context7-mcp"),
        domain="smithery.ai",
        browser=None,
    )
    cls = ppt._classify_local(item)
    assert cls["kind"] == "tool"


def test_local_classifier_treats_huggingface_course_as_docs():
    item = Item(
        title="Introduction - Hugging Face LLM Course",
        url="https://huggingface.co/learn/llm-course/chapter1/1",
        norm_url=ppt.normalize_url("https://huggingface.co/learn/llm-course/chapter1/1"),
        clean_url=ppt.normalize_url("https://huggingface.co/learn/llm-course/chapter1/1"),
        domain="huggingface.co",
        browser=None,
    )
    cls = ppt._classify_local(item)
    assert cls["kind"] == "docs"


def test_local_classifier_treats_music_and_show_pages_distinctly():
    music_items = [
        Item(
            title="Free Ambient Music - Royalty Free Download",
            url="https://uppbeat.io/music/category/ambient",
            norm_url=ppt.normalize_url("https://uppbeat.io/music/category/ambient"),
            clean_url=ppt.normalize_url("https://uppbeat.io/music/category/ambient"),
            domain="uppbeat.io",
            browser=None,
        ),
        Item(
            title="Яндекс Музыка — собираем музыку и подкасты для вас",
            url="https://music.yandex.ru/",
            norm_url=ppt.normalize_url("https://music.yandex.ru/"),
            clean_url=ppt.normalize_url("https://music.yandex.ru/"),
            domain="music.yandex.ru",
            browser=None,
        ),
    ]
    for item in music_items:
        cls = ppt._classify_local(item)
        assert cls["kind"] == "music"

    show_item = Item(
        title="Очень странные дела 3 сезон 1 серия смотреть онлайн",
        url="https://stranger-things.ru/3-seazons/1-seriya-3-sezon",
        norm_url=ppt.normalize_url("https://stranger-things.ru/3-seazons/1-seriya-3-sezon"),
        clean_url=ppt.normalize_url("https://stranger-things.ru/3-seazons/1-seriya-3-sezon"),
        domain="stranger-things.ru",
        browser=None,
    )
    show_cls = ppt._classify_local(show_item)
    assert show_cls["kind"] == "video"


def test_case_social_thread_defaults_to_misc_article_score2():
    item = Item(
        title="Thread",
        url="https://x.com/theprimeagen/status/12345",
        norm_url=ppt.normalize_url("https://x.com/theprimeagen/status/12345"),
        clean_url=ppt.normalize_url("https://x.com/theprimeagen/status/12345"),
        domain="x.com",
        browser=None,
    )
    cls = ppt._classify_local(item)
    assert cls["topic"] == "misc"
    assert cls["kind"] == "article"
    assert cls["score"] == 2


def test_case_deep_tech_repo_postgres_score5():
    item = Item(
        title="bufmgr internals",
        url="https://github.com/postgres/postgres/blob/master/src/backend/storage/buffer/bufmgr.c",
        norm_url=ppt.normalize_url(
            "https://github.com/postgres/postgres/blob/master/src/backend/storage/buffer/bufmgr.c"
        ),
        clean_url=ppt.normalize_url(
            "https://github.com/postgres/postgres/blob/master/src/backend/storage/buffer/bufmgr.c"
        ),
        domain="github.com",
        browser=None,
    )
    cls = ppt._classify_local(item)
    assert cls["kind"] == "repo"
    assert cls["topic"] == "postgres"
    assert cls["score"] == 5


def test_case_llm_research_pdf():
    item = Item(
        title="LLM research paper",
        url="https://arxiv.org/pdf/2405.12345.pdf",
        norm_url=ppt.normalize_url("https://arxiv.org/pdf/2405.12345.pdf"),
        clean_url=ppt.normalize_url("https://arxiv.org/pdf/2405.12345.pdf"),
        domain="arxiv.org",
        browser=None,
    )
    cls = ppt._classify_local(item)
    assert cls["kind"] == "paper"
    assert cls["topic"] in {"llm", "research"}
