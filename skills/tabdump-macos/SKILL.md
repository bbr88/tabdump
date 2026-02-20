---
name: tabdump-macos
description: OpenClaw skill for TabDump on macOS. Trigger on requests like dump tabs, capture browser tabs, TabDump, reading queue, Obsidian inbox, and launch agent status. Use to inspect runtime status/logs, run structured doctor diagnostics, manage launch agent state, and reset Automation permissions.
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

- `tabdump status`
- `scripts/tabdump_doctor.sh --json`
- `tabdump now --json`
- `tabdump logs --lines 80`

## Runtime layout

Expected install paths:

- App: `~/Applications/TabDump.app`
- App Support: `~/Library/Application Support/TabDump/`
- Config: `~/Library/Application Support/TabDump/config.json`
- Monitor: `~/Library/Application Support/TabDump/monitor_tabs.py`
- Monitor state: `~/Library/Application Support/TabDump/monitor_state.json`
- Legacy app state: `~/Library/Application Support/TabDump/state.json`
- Logs:
  - `~/Library/Application Support/TabDump/logs/monitor.out.log` (combined stdout/stderr stream)
- Launch agent plist: `~/Library/LaunchAgents/io.orc-visioner.tabdump.monitor.plist`
- Launch-agent monitor default flags: `--verbose`

Path contract: these diagnostics intentionally assume the exact paths above. Keep Homebrew runtime installation aligned with these paths.

## Primary commands

### CLI runtime commands

1. Status and logs:
   - `tabdump status`
   - `tabdump logs`
   - `tabdump logs --lines 80`
   - `tabdump logs --follow`
2. One-shot dumps:
   - `tabdump now --json`
   - `tabdump now --close --json`
3. Count current tabs (same monitor/TCC surface):
   - `tabdump count --json`
4. Safe permissions check:
   - `tabdump permissions`
   - Uses lightweight probe mode (raw-dump permission signal; skips clean-note postprocess).
5. Mode and config:
   - `tabdump mode show`
   - `tabdump mode dump-only|dump-close|auto`
   - `tabdump config show`
   - `tabdump config get <key>`
   - `tabdump config set <key> <value> [<key> <value> ...]`

### Skill-only helper scripts

1. Canonical machine diagnostic entrypoint:
   - `scripts/tabdump_doctor.sh --json`
2. Human doctor output:
   - `scripts/tabdump_doctor.sh`
   - `scripts/tabdump_doctor.sh --tail 80`
3. LaunchAgent repair:
   - `scripts/tabdump_install_launchagent.sh`
   - `scripts/tabdump_reload_launchagent.sh`
4. Reset TCC AppleEvents permissions:
   - `scripts/tabdump_permissions_reset.sh`
5. Installer helpers:
   - `scripts/tabdump_install_from_repo.sh`
   - `scripts/tabdump_install_brew.sh`
6. Smoke checks:
   - `scripts/test_skill_smoke.sh`
   - `scripts/test_skill_smoke.sh --active`

## Doctor JSON output contract

Canonical agent entrypoint: `scripts/tabdump_doctor.sh --json`

Exit codes:

- `0` = no findings (`status=ok`)
- `1` = findings present (`status=issues`)
- `2` = usage/runtime error

JSON fields:

- `schemaVersion` (fixed: `tabdump-doctor/v1`)
- `status` (`ok|issues`)
- `issueCount` (integer)
- `generatedAt` (ISO-8601 UTC)
- `issues[]` objects:
  - `id` (deterministic issue key)
  - `severity` (`low|medium|high`)
  - `category`
  - `message`
- `recommendedActions[]` objects:
  - `id`
  - `command`
  - `reason`
- `paths`:
  - `app`, `appSupport`, `config`, `monitor`, `logDir`, `outLog`, `plist`

## CLI JSON output references

- `tabdump now --json`: expect `status`, `reason`, `mode`, `rawDump`, `cleanNote`.
- `tabdump count --json`: expect `status`, `reason`, `mode=count`, `tabCount`.
- Count is fail-hard semantically: `status=error`, `reason=count_unavailable`, `tabCount=null` (or empty) when fresh evidence is unavailable.

## Migration from removed wrappers

These wrappers were removed intentionally to make the CLI canonical:

- `scripts/tabdump_status.sh` -> `tabdump status` (optionally `tabdump config show`)
- `scripts/tabdump_run_once.sh` -> `tabdump now --json` / `tabdump now --close --json`
- `scripts/tabdump_count.sh` -> `tabdump count --json`

## Verify successful operation

After a run, verify by:

1. Checking newest `TabDump *.md` and `TabDump* (clean).md` in `vaultInbox`.
2. Inspecting monitor state (`lastStatus`, `lastReason`, `lastProcessed`, `lastClean`).
3. Tailing monitor logs with `tabdump logs --lines 80`.

## TCC / Automation troubleshooting

If browser automation is blocked:

1. Run `scripts/tabdump_permissions_reset.sh`
2. Or run directly:
   - `tccutil reset AppleEvents io.orc-visioner.tabdump`
3. Re-run `tabdump now` and approve prompts in:
   - System Settings -> Privacy & Security -> Automation

## Reference

- Config fields and semantics: `references/config.md`
