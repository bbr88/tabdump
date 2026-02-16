#!/usr/bin/env bash
set -euo pipefail

APP_SUPPORT="${HOME}/Library/Application Support/TabDump"
CFG="${APP_SUPPORT}/config.json"
MONITOR_STATE="${APP_SUPPORT}/monitor_state.json"
LEGACY_STATE="${APP_SUPPORT}/state.json"
OUT_LOG="${APP_SUPPORT}/logs/monitor.out.log"
ERR_LOG="${APP_SUPPORT}/logs/monitor.err.log"
APP="${HOME}/Applications/TabDump.app"
PLIST="${HOME}/Library/LaunchAgents/io.orc-visioner.tabdump.monitor.plist"
LABEL="io.orc-visioner.tabdump.monitor"
TARGET="gui/$(id -u)/${LABEL}"

say() { printf '%s\n' "$*"; }

if command -v tabdump >/dev/null 2>&1; then
  if tabdump status >/dev/null 2>&1; then
    tabdump status
    if tabdump config show >/dev/null 2>&1; then
      echo
      tabdump config show
    fi
    exit 0
  fi
fi

say "TabDump status"

if [[ -d "${APP_SUPPORT}" ]]; then
  say "- App Support: ${APP_SUPPORT}"
else
  say "- App Support: MISSING (${APP_SUPPORT})"
fi

if [[ -d "${APP}" ]]; then
  say "- App: ${APP}"
else
  say "- App: MISSING (${APP})"
fi

if [[ -f "${CFG}" ]]; then
  say "- config.json: ${CFG}"
  python3 - "${CFG}" <<'PY'
import json
import sys

p = sys.argv[1]
with open(p, "r", encoding="utf-8") as fh:
    d = json.load(fh) or {}

print("  vaultInbox:", d.get("vaultInbox"))
print("  browsers:", d.get("browsers"))
print("  dryRun:", d.get("dryRun"))
print("  dryRunPolicy:", d.get("dryRunPolicy"))
print("  onboardingStartedAt:", d.get("onboardingStartedAt"))
print("  checkEveryMinutes:", d.get("checkEveryMinutes"))
print("  cooldownMinutes:", d.get("cooldownMinutes"))
print("  maxTabs:", d.get("maxTabs"))
print("  llmEnabled:", d.get("llmEnabled"))
PY
else
  say "- config.json: MISSING (${CFG})"
fi

if [[ -f "${MONITOR_STATE}" ]]; then
  say "- monitor_state.json: ${MONITOR_STATE}"
  python3 - "${MONITOR_STATE}" <<'PY'
import datetime
import json
import sys

p = sys.argv[1]
try:
    d = json.load(open(p, "r", encoding="utf-8")) or {}
except Exception:
    d = {}

for ts_key in ("lastCheck", "lastProcessedAt", "lastResultAt", "autoSwitchedAt"):
    val = d.get(ts_key)
    if val is None:
        continue
    try:
        iso = datetime.datetime.fromtimestamp(float(val)).isoformat(sep=" ", timespec="seconds")
        print(f"  {ts_key}_iso: {iso}")
    except Exception:
        pass

for key in (
    "lastStatus",
    "lastReason",
    "lastProcessed",
    "lastClean",
    "lastResultRawDump",
    "lastResultCleanNote",
    "autoSwitchReason",
    "lastError",
):
    if key in d:
        print(f"  {key}: {d.get(key)}")
PY
else
  say "- monitor_state.json: (none yet)"
fi

if [[ -f "${LEGACY_STATE}" ]]; then
  say "- app state (legacy self-gating): ${LEGACY_STATE}"
  python3 - "${LEGACY_STATE}" <<'PY'
import json
import sys

p = sys.argv[1]
try:
    d = json.load(open(p, "r", encoding="utf-8")) or {}
except Exception:
    d = {}

for key in ("lastCheck", "lastDump", "lastTabs"):
    if key in d:
        print(f"  {key}: {d.get(key)}")
PY
else
  say "- app state (legacy self-gating): (none yet)"
fi

if [[ -f "${PLIST}" ]]; then
  say "- launch agent plist: ${PLIST}"
else
  say "- launch agent plist: (not installed) ${PLIST}"
fi

if command -v launchctl >/dev/null 2>&1; then
  if launch_output="$(launchctl print "${TARGET}" 2>&1)"; then
    say "- launch agent runtime: loaded (${TARGET})"
    state_line="$(printf '%s\n' "${launch_output}" | sed -n 's/^[[:space:]]*state = /state=/p' | head -n 1)"
    exit_line="$(printf '%s\n' "${launch_output}" | sed -n 's/^[[:space:]]*last exit code = /last_exit=/p' | head -n 1)"
    [[ -n "${state_line}" ]] && say "  ${state_line}"
    [[ -n "${exit_line}" ]] && say "  ${exit_line}"
  else
    say "- launch agent runtime: not loaded (${TARGET})"
  fi
else
  say "- launch agent runtime: launchctl not available"
fi

say "- last monitor.out.log lines:"
if [[ -f "${OUT_LOG}" ]]; then
  tail -n 30 "${OUT_LOG}" | sed 's/^/  | /'
else
  say "  | (missing)"
fi

say "- last monitor.err.log lines:"
if [[ -f "${ERR_LOG}" ]]; then
  tail -n 30 "${ERR_LOG}" | sed 's/^/  | /'
else
  say "  | (missing)"
fi
