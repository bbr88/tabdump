# TabDump User Manual

## What TabDump Does

TabDump helps you clear tab overload in Chrome/Safari by:

1. Dumping eligible tabs into a raw Markdown note.
2. Postprocessing the raw note into a clean note.
3. Optionally closing dumped tabs (depending on mode).

By default, installed TabDump starts in safe dump-only mode.

## Install

Run installer:

```bash
bash scripts/install.sh
```

Non-interactive install example:

```bash
bash scripts/install.sh --yes --vault-inbox "~/obsidian/Inbox/"
```

## Core Commands

Open app:

```bash
tabdump run
```

One-shot dump-only run (forced, bypasses gates):

```bash
tabdump now
```

One-shot dump+close run (forced, bypasses gates):

```bash
tabdump now --close
```

Machine-readable output:

```bash
tabdump now --json
```

Safe permissions check (forced dump-only, no tab closing):

```bash
tabdump permissions
```

Inspect current state:

```bash
tabdump status
```

## Modes

Show current mode:

```bash
tabdump mode show
```

Set dump-only mode:

```bash
tabdump mode dump-only
```

Set dump+close mode:

```bash
tabdump mode dump-close
```

Set auto mode:

```bash
tabdump mode auto
```

Mode behavior:

1. `dump-only` (`dryRun=true`): writes notes, keeps tabs open.
2. `dump-close` (`dryRun=false`): writes notes and may close non-allowlisted/non-pinned tabs.
3. `auto` (`dryRunPolicy=auto`): starts/continues based on current `dryRun`; auto-switches to close mode after first clean dump when currently in dry run.

## Output Contract

TabDump produces:

1. Raw note: `TabDump YYYY-MM-DD HH-MM-SS.md`
2. Clean note: `TabDump YYYY-MM-DD HH-MM-SS (clean).md`

`tabdump now` human output:

1. `[ok] Clean dump: <path>` on success.
2. `[info] No clean dump produced (<reason>).` for expected no-op cases.

`tabdump now --json` fields include:

1. `status` (`ok|noop|error`)
2. `reason`
3. `mode`
4. `forced`
5. `rawDump`
6. `cleanNote`
7. `autoSwitched`

## Understanding `tabdump status`

`tabdump status` shows:

1. Current mode/policy and gate values (`checkEveryMinutes`, `cooldownMinutes`, `maxTabs`).
2. Monitor state (`monitor_state.json`): pipeline result (`lastStatus`, `lastReason`, `lastProcessed`, `lastClean`).
3. Legacy app self-gating state (`state.json`): raw app-level checks (`lastCheck`, `lastDump`, `lastTabs`).
4. Launch agent runtime state and recent logs.

## Permissions (TCC / Automation)

If browser control prompts do not appear:

```bash
tabdump permissions
```

Reset Automation permission if needed:

```bash
tccutil reset AppleEvents io.orc-visioner.tabdump
```

Then run `tabdump permissions` again.

## Launch Agent

TabDump installs a launch agent:

`~/Library/LaunchAgents/io.orc-visioner.tabdump.monitor.plist`

Reload after changing schedule-related config:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/io.orc-visioner.tabdump.monitor.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/io.orc-visioner.tabdump.monitor.plist
```

## Config File

Main config path:

`~/Library/Application Support/TabDump/config.json`

Common keys:

1. `vaultInbox`
2. `browsers`
3. `dryRun`
4. `dryRunPolicy` (`manual|auto`)
5. `maxTabs`
6. `checkEveryMinutes`
7. `cooldownMinutes`
8. `llmEnabled`

## Troubleshooting

No output from `tabdump now`:

1. Run `tabdump status`.
2. Check `lastStatus` and `lastReason`.
3. Review log tails shown by `tabdump status`.

No tabs closed when expected:

1. Run `tabdump mode show`.
2. Ensure mode is `dump-close` (or `auto` with `dryRun=false`).
3. Check allowlist/pinned tab rules in config.

Unexpected no-op:

1. `tabdump now` bypasses gates.
2. If still no-op, reason is usually no eligible/new dump or already-processed input.

## Uninstall

```bash
bash scripts/uninstall.sh
```

To also remove config:

```bash
bash scripts/uninstall.sh --remove-config
```
