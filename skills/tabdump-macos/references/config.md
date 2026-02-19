# TabDump config.json (macOS)

Default path:

- `~/Library/Application Support/TabDump/config.json`

Prefer CLI updates:

- `tabdump config show`
- `tabdump config get <key>`
- `tabdump config set <key> <value> [<key> <value> ...]`

## Core fields

- `vaultInbox` (string, required): output directory for raw/clean notes.
- `outputFilenameTemplate` (string): raw note naming template (default `TabDump {ts}.md`).
- `browsers` (array): `Chrome`, `Safari`, `Firefox`.
- `allowlistUrlContains` (array): matching tabs are kept open and not dumped.
- `skipUrlPrefixes` (array): skip internal URLs (`chrome://`, `about:`, `safari://`, etc.).
- `skipTitlesExact` (array): skip exact title matches like `New Tab`.
- `keepPinnedTabs` (bool): keep pinned tabs.
- `outputGroupByWindow` (bool): group output by browser/window.
- `outputIncludeMetadata` (bool): include metadata lines in raw note.

## Mode and gating fields

- `dryRun` (bool):
  - `true` = dump-only (notes are written, tabs stay open)
  - `false` = dump+close
- `dryRunPolicy` (`manual|auto`): auto mode may switch to close mode after first clean dump.
- `onboardingStartedAt` (epoch int): onboarding/trust-ramp anchor timestamp.
- `maxTabs` (int >= 0): minimum open-tab threshold before normal scheduled runs dump.
- `checkEveryMinutes` (int >= 0): scheduler gate interval. `tabdump config set checkEveryMinutes ...` also updates LaunchAgent `StartInterval`.
- `cooldownMinutes` (int >= 0): minimum interval between dumps.

## LLM/postprocess fields

- `llmEnabled` (bool)
- `tagModel` (string)
- `llmRedact` (bool)
- `llmRedactQuery` (bool)
- `llmTitleMax` (int)
- `maxItems` (int)

## State files and logs

- Monitor state: `~/Library/Application Support/TabDump/monitor_state.json`
  - includes `lastStatus`, `lastReason`, `lastProcessed`, `lastClean`, `lastCount`, `lastCountAt`
- Legacy app state: `~/Library/Application Support/TabDump/state.json`
- Logs:
  - `~/Library/Application Support/TabDump/logs/monitor.out.log`
  - `~/Library/Application Support/TabDump/logs/monitor.err.log`

## Count semantics

- `tabdump count` is fail-hard.
- If fresh count evidence is unavailable, reason is `count_unavailable` and `tabCount` is null/empty.
