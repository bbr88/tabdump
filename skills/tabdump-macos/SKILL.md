---
name: tabdump-macos
description: OpenClaw skill for TabDump on macOS. Trigger on requests like dump tabs, capture browser tabs, TabDump, reading queue, Obsidian inbox, and launch agent status. Use to run one-shot dumps, inspect status/logs, run doctor diagnostics, reload launch agent, and reset Automation permissions.
---

# TabDump (macOS)

Use this skill when the user asks to dump tabs, capture browser tabs, operate TabDump, check reading queue output, troubleshoot Obsidian inbox notes, or inspect launch agent status.

## 30-second quickstart

```bash
brew tap bbr88/tap
brew install tabdump
tabdump init --yes --vault-inbox ~/obsidian/Inbox --enable-llm true --key-mode keychain
# Optional no-LLM setup:
tabdump init --yes --vault-inbox ~/obsidian/Inbox
```

Then run:

- `scripts/tabdump_status.sh`
- `scripts/tabdump_doctor.sh`
- `scripts/tabdump_run_once.sh`
- `scripts/tabdump_reload_launchagent.sh`

## Runtime layout

Expected install paths:

- App: `~/Applications/TabDump.app`
- App Support: `~/Library/Application Support/TabDump/`
- Config: `~/Library/Application Support/TabDump/config.json`
- Monitor: `~/Library/Application Support/TabDump/monitor_tabs.py`
- Monitor state: `~/Library/Application Support/TabDump/monitor_state.json`
- Legacy app state: `~/Library/Application Support/TabDump/state.json`
- Logs:
  - `~/Library/Application Support/TabDump/logs/monitor.out.log`
  - `~/Library/Application Support/TabDump/logs/monitor.err.log`
- Launch agent plist: `~/Library/LaunchAgents/io.orc-visioner.tabdump.monitor.plist`

Path contract: these scripts intentionally assume the exact paths above. Keep Homebrew runtime installation aligned with these paths.

## Primary commands

1. Tail runtime logs:
   - `tabdump logs`
   - `tabdump logs --lines 80`
   - `tabdump logs --follow`
2. Check status and logs:
   - `scripts/tabdump_status.sh`
3. Run doctor diagnostics (paths/config/launch agent/log signatures):
   - `scripts/tabdump_doctor.sh`
   - `scripts/tabdump_doctor.sh --tail 80`
4. Count current tabs (monitor path; same TCC surface):
   - `scripts/tabdump_count.sh`
   - `scripts/tabdump_count.sh --json`
5. Run one-shot dump (default dump-only):
   - `scripts/tabdump_run_once.sh`
6. Run one-shot dump+close:
   - `scripts/tabdump_run_once.sh --close`
7. Reload launch agent:
   - `scripts/tabdump_reload_launchagent.sh`
8. Reset TCC AppleEvents permissions:
   - `scripts/tabdump_permissions_reset.sh`
9. Safe smoke checks:
   - `scripts/test_skill_smoke.sh`
10. Active smoke checks (may open app and trigger prompts):
   - `scripts/test_skill_smoke.sh --active`

## Config updates

Prefer CLI config commands instead of manual JSON editing:

- `tabdump config show`
- `tabdump config get <key>`
- `tabdump config set <key> <value> [<key> <value> ...]`

## One-shot output contract

`tabdump_run_once.sh` always prints:

- `RAW_DUMP=<absolute-path-or-empty>`
- `CLEAN_NOTE=<absolute-path-or-empty>`

Exit codes:

- `0` if monitor status is `ok`
- `3` if monitor status is `noop`
- `1` for runtime/JSON errors

## Tab count output contract

`scripts/tabdump_count.sh`:

- Prints a single integer tab count to stdout.

`scripts/tabdump_count.sh --json`:

- Returns monitor JSON payload with `status`, `reason`, `mode=count`, and `tabCount`.
- Fail-hard behavior is expected: if a fresh count cannot be confirmed, payload returns `status=error`, `reason=count_unavailable`, and `tabCount=null` (or empty).

## Verify successful operation

After a run, verify by:

1. Checking newest `TabDump *.md` and `TabDump* (clean).md` in `vaultInbox`.
2. Inspecting monitor state (`lastStatus`, `lastReason`, `lastProcessed`, `lastClean`).
3. Tailing monitor logs.

## TCC / Automation troubleshooting

If browser automation is blocked:

1. Run `scripts/tabdump_permissions_reset.sh`
2. Or run directly:
   - `tccutil reset AppleEvents io.orc-visioner.tabdump`
3. Re-run a one-shot command and approve prompts in:
   - System Settings -> Privacy & Security -> Automation

## Reference

- Config fields and semantics: `references/config.md`
