# TabDump Config Reference

Scope: `~/Library/Application Support/TabDump/config.json` and `docs/examples/config.example.json`.

Tip: Use `tabdump config show|get|set` for routine updates instead of editing JSON by hand.

Note: Properties are consumed by the runtime (`macos/configurable-tabDump.scpt`, `core/monitor_tabs.py`, or postprocess env wiring).
Renderer tuning defaults in `core/renderer/config.py` are internal defaults and are not loaded from `config.json`.

## Core Paths and Output

| Key | Type | Default | Used by | Description |
|---|---|---|---|---|
| `vaultInbox` | string (absolute path) | required | app + monitor | Destination folder for raw/clean TabDump notes. |
| `outputFilenameTemplate` | string | `TabDump {ts}.md` | app | Raw dump filename template. `{ts}` is replaced with timestamp. |

## Browser Selection and Filters

| Key | Type | Default | Used by | Description |
|---|---|---|---|---|
| `browsers` | array of strings | `["Chrome","Safari"]` | app + CLI permissions/status | Browsers to process (`Chrome`, `Safari`, `Firefox`). |
| `allowlistUrlContains` | array of strings | install defaults | app | If URL contains any item, tab is kept open and not dumped. |
| `keepPinnedTabs` | boolean | `true` | app | Preserve pinned tabs (Chrome reliable, Safari best effort). |
| `skipUrlPrefixes` | array of strings | install defaults | app | Skip internal/system URLs (`chrome://`, `about:`, etc.). |
| `skipTitlesExact` | array of strings | `["New Tab","Start Page"]` | app | Skip title-exact noise tabs. |

## Rendering and Action Mode

| Key | Type | Default | Used by | Description |
|---|---|---|---|---|
| `outputGroupByWindow` | boolean | `true` | app | Group dump by browser/window sections. |
| `outputIncludeMetadata` | boolean | `false` | app | Add metadata chips per line (domain/browser). |
| `dryRun` | boolean | `true` | app + monitor + CLI mode | `true` = dump-only, `false` = dump+close. |
| `dryRunPolicy` | `manual` or `auto` | `auto` when dry-run install, else `manual` | monitor + CLI mode | Auto-policy can switch from dump-only to dump+close after first clean dump. |
| `onboardingStartedAt` | integer epoch seconds | install time / `0` | monitor | Anchor timestamp for auto-mode onboarding window. Usually runtime-managed. |

## Scheduling and Gates

| Key | Type | Default | Used by | Description |
|---|---|---------|---|---|
| `maxTabs` | integer | `30`    | app | Minimum tab threshold before app-level dump action. |
| `checkEveryMinutes` | integer | `60`   | monitor + launch agent + app | Poll interval and monitor gate window. |
| `cooldownMinutes` | integer | `1440` | app | Cooldown between app-side dump actions (`1440` = 24 hours). |

## LLM / Postprocess Controls

| Key | Type | Default | Used by | Description |
|---|---|---|---|---|
| `llmEnabled` | boolean | `false` | monitor -> postprocess | Enable LLM enrichment for classification/tagging. |
| `tagModel` | string | `gpt-4.1-mini` | monitor + app property map | Model name passed to postprocess. |
| `llmRedact` | boolean | `true` | monitor -> postprocess | Redact sensitive text before LLM calls. |
| `llmRedactQuery` | boolean | `true` | monitor -> postprocess | Redact URL query params before LLM calls. |
| `llmTitleMax` | integer | `200` | monitor -> postprocess | Title length cap for LLM prompt payloads. |
| `maxItems` | integer | `0` | monitor -> postprocess | Max items per LLM classification batch (`0` = no explicit cap). |
