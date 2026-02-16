# TabDump User Manual

## What TabDump Does

TabDump helps you clear tab overload in Chrome/Safari by:

1. Dumping eligible tabs into a raw Markdown note.
2. Postprocessing the raw note into a clean note.
3. Optionally closing dumped tabs (depending on mode).

By default, installed TabDump starts in safe dump-only mode.

## Install

Homebrew (recommended):

```bash
brew tap bbr88/tap
brew install tabdump
tabdump init --yes --vault-inbox ~/obsidian/Inbox --enable-llm true --key-mode keychain
```

From source:

Build a prebuilt app archive (required once per local source checkout):

```bash
bash scripts/build-release.sh --version v0.1.0-local --output-dir dist --no-codesign
```

Run installer (explicit archive path):

```bash
bash scripts/install.sh --yes --vault-inbox "~/obsidian/Inbox/" --app-archive "./dist/tabdump-app-v0.1.0-local.tar.gz"
```

Optional gate overrides at install time:

```bash
bash scripts/install.sh --yes --vault-inbox "~/obsidian/Inbox/" --max-tabs 40 --check-every-minutes 30 --cooldown-minutes 1440
```

If `./dist/tabdump-app.tar.gz` exists, `--app-archive` is optional:

```bash
bash scripts/install.sh --yes --vault-inbox "~/obsidian/Inbox/"
```

Manual (no build/install pipeline):

1. Copy `macos/standalone-tabDump-template.scpt`.
2. Update `vaultInbox` and optional allowlist in the script.
3. Keep `closeDumpedTabs` as `false` for dump-only behavior, or set it to `true` to enable close mode.

Reference config schema:

`docs/examples/config.example.json`

Property-by-property reference:

`docs/config-reference.md`

## Local Developer App Build

Build only the local `.app` bundle (does not install runtime/config/launch agent):

```bash
bash scripts/build-local.sh
```

Custom output/bundle id/version:

```bash
bash scripts/build-local.sh --output "~/Applications/TabDumpDev.app" --bundle-id "io.example.tabdump.dev" --version "v1.2.3"
```

Skip codesign for rapid local iteration:

```bash
bash scripts/build-local.sh --no-codesign
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

Inspect and update config:

```bash
tabdump config show
tabdump config get checkEveryMinutes
tabdump config set checkEveryMinutes 30 cooldownMinutes 1440 maxTabs 40
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

## Clean Note UX Cues

The clean renderer adds quick orientation cues:

1. `Start Here` includes a `Today's Context` line (top topics, with domain fallback).
2. Bullets include effort pills such as `[quick read]`, `[medium read]`, `[deep watch]`.
3. Large `Read Later` sections split singleton domains into `More Links` with two-line bullets for better title readability.
4. `docsMoreLinksGroupingMode` controls singleton grouping:
   - `kind` (default): `Docs` / `Articles` / `Papers`...
   - `energy`: `Deep Reads` / `Quick References`

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

CLI helpers:

1. `tabdump config show`
2. `tabdump config get <key>`
3. `tabdump config set <key> <value> [<key> <value> ...]`

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

Homebrew install:

```bash
tabdump uninstall --yes --remove-config --purge
brew uninstall tabdump
```

Source install:

```bash
bash scripts/uninstall.sh
```

To also remove config:

```bash
bash scripts/uninstall.sh --remove-config
```
