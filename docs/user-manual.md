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

## OpenClaw Skill Delivery

Canonical skill source in this repo:

- `skills/tabdump-macos`

Build versioned skill artifact:

```bash
bash scripts/build-openclaw-skill-package.sh --version v0.1.0-local --output-dir dist
```

Result:

- `dist/tabdump-openclaw-skill-v0.1.0-local.tar.gz`
- `dist/tabdump-openclaw-skill-v0.1.0-local.tar.gz.sha256`

The skill bundle includes helper wrappers:

1. `scripts/tabdump_run_once.sh [--close]`
2. `scripts/tabdump_count.sh [--json]`
3. `scripts/tabdump_status.sh`
4. `scripts/tabdump_reload_launchagent.sh`
5. `scripts/tabdump_permissions_reset.sh`
6. `scripts/tabdump_install_from_repo.sh`
7. `scripts/test_skill_smoke.sh [--active]`

## Core Commands

Open app:

```bash
tabdump run
```

One-shot dump-only run (forced, bypasses gates):

```bash
tabdump now
```

Count current tabs (same monitor/TCC path, no dump decision made):

```bash
tabdump count
tabdump count --json
```

`tabdump count` is fail-hard: it returns an error if a fresh post-launch count cannot be confirmed.

`tabdump count`, `tabdump now`, and `tabdump now --close` launch TabDump in background/hidden mode to reduce focus stealing. First-time Automation prompts may still appear in foreground.

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

`tabdump count --json` fields include:

1. `status` (`ok|error`)
2. `reason` (`count_only` on success, `count_unavailable` when freshness cannot be confirmed)
3. `mode` (`count`)
4. `forced`
5. `tabCount`

## Clean Note UX Cues

The clean renderer adds quick orientation cues:

1. `Start Here` includes a `Today's Context` line (top topics, with domain fallback).
2. Bullets include effort pills such as `[low effort]`, `[medium effort]`, `[high effort]`.
3. Non-admin sections use two-line bullets for better title readability, while `Accounts & Settings` stays compact one-line.
4. `docsMoreLinksGroupingMode` controls singleton grouping:
   - `kind` (default): `Docs` / `Articles` / `Papers`... (title-sorted within each kind).
   - `domain`: flat alphabetic list with no per-domain subheaders.
   - `energy`: `Deep Reads` / `Quick References`
5. Legacy `domain` defaults are migrated once to `kind` and marked in monitor state; after that, user-set mode remains respected.

## Effort Estimation Model

Effort pills are estimated with a shared domain-neutral resolver used by both postprocess and renderer fallback.

Primary signals:

1. Baseline by kind/action:
   - `auth/local/internal` start at low effort.
   - `paper/spec/deep_work` start at high effort.
   - other kinds start at medium effort.
2. Depth signals:
   - long-form cues such as `full course`, `complete guide`, `masterclass`, `deep dive`, `step-by-step`.
3. Quick-consumption signals:
   - cues such as `trailer`, `clip`, `highlights`, `overview`, `faq`, `quickstart`, `cheat sheet`.
4. Duration signals:
   - parses `Xh`, `X-hour`, `HH:MM:SS`, and `MM min`.
5. Task-complexity signals:
   - setup/configuration, multi-step workflows, planning/onboarding, checkout/application flows.

Important behavior notes:

1. Effort is not tied only to `kind` or `action`.
2. Model-provided effort (when present) is advisory and accepted only when within one band of derived effort.
3. This prevents outlier labels while keeping flexibility for ambiguous items.

Optional runtime diagnostics:

```bash
TABDUMP_EFFORT_DEBUG=1 tabdump now
```

This prints effort band totals and top signal triggers to stderr for the run.

Optional strict benchmark enforcement in tests:

```bash
TABDUMP_EVAL_ENFORCE_EFFORT=1 python3 -m pytest -q tests/postprocess/integration/test_effort_estimation.py
```

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
9. `tagModel`
10. `llmActionPolicy` (`raw|derived|hybrid`)
11. `minLlmCoverage` (`0.0` to `1.0`)

CLI helpers:

1. `tabdump config show`
2. `tabdump config get <key>`
3. `tabdump config set <key> <value> [<key> <value> ...]`

## LLM Action Policy and Coverage Guardrail

TabDump has two controls that affect how LLM classification behaves when responses are noisy or incomplete:

1. `TABDUMP_LLM_ACTION_POLICY` (config key: `llmActionPolicy`)
2. `TABDUMP_MIN_LLM_COVERAGE` (config key: `minLlmCoverage`)

In normal `tabdump now` / launch-agent runs, set these via config keys (`llmActionPolicy`, `minLlmCoverage`). The monitor exports them as env vars for postprocess.

### `TABDUMP_LLM_ACTION_POLICY`

Supported values:

1. `raw`: use model action directly after normalization/coercion.
2. `derived`: ignore model action; derive action from `kind + URL/title` rules.
3. `hybrid` (default): use model action only when it is valid and compatible with the predicted kind; otherwise derive action from rules.

Compatibility rules used by `hybrid`:

1. `video`, `music` -> `watch`
2. `tool`, `repo` -> `triage` or `build`
3. `article`, `docs` -> `read` or `reference`
4. `paper` -> `read`, `reference`, or `deep_work`
5. `misc`, `local`, `internal`, `auth` -> `triage` or `ignore`

Recommendation:

1. Use `hybrid` for production reliability.
2. Use `raw` only when auditing model verb behavior.
3. Use `derived` when you want strictly deterministic action behavior from local policy.

### `TABDUMP_MIN_LLM_COVERAGE`

This controls fallback behavior for unmapped non-sensitive tabs.

Coverage is computed as:

1. `mapped_non_sensitive / non_sensitive_total`

Behavior:

1. If coverage is below `minLlmCoverage`, unmapped tabs fall back to local classifier.
2. If coverage meets/exceeds `minLlmCoverage`, unmapped tabs keep generic defaults (`kind=misc`, `action=triage`).

Tuning guidance:

1. Start at `0.7` (default).
2. Raise to `0.8-0.9` to be stricter and force more local fallback when LLM mapping quality drops.
3. Lower to `0.5-0.6` if you prefer to trust partial LLM output more aggressively.

### Configure via `tabdump config`

Set recommended defaults:

```bash
tabdump config set llmActionPolicy hybrid minLlmCoverage 0.7
```

Inspect current values:

```bash
tabdump config get llmActionPolicy
tabdump config get minLlmCoverage
```

Advanced direct postprocess override:

```bash
TABDUMP_LLM_ACTION_POLICY=derived \
TABDUMP_MIN_LLM_COVERAGE=0.85 \
python3 core/postprocess/cli.py "/path/to/TabDump YYYY-MM-DD HH-MM-SS.md"
```

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
