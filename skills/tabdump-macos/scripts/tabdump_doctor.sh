#!/usr/bin/env bash
set -euo pipefail

APP="${HOME}/Applications/TabDump.app"
APP_SUPPORT="${HOME}/Library/Application Support/TabDump"
CFG="${APP_SUPPORT}/config.json"
MONITOR="${APP_SUPPORT}/monitor_tabs.py"
LOG_DIR="${APP_SUPPORT}/logs"
OUT_LOG="${LOG_DIR}/monitor.out.log"
ERR_LOG="${LOG_DIR}/monitor.err.log"
PLIST="${HOME}/Library/LaunchAgents/io.orc-visioner.tabdump.monitor.plist"
LABEL="io.orc-visioner.tabdump.monitor"
TARGET="gui/$(id -u)/${LABEL}"

TAIL_LINES=40
SCAN_LINES=200
SHOW_FIX_HINTS=1
ISSUE_KEYS=""
ISSUE_COUNT=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/tabdump_doctor.sh [--tail N] [--no-fix-hints]

Options:
  --tail N          Log lines to print per log file (default: 40).
  --no-fix-hints    Skip repair suggestion section.
  -h, --help        Show this help.
USAGE
}

say() {
  printf '%s\n' "$*"
}

section() {
  echo
  say "$1"
}

has_issue() {
  local key="$1"
  case ",${ISSUE_KEYS}," in
    *",${key},"*) return 0 ;;
    *) return 1 ;;
  esac
}

mark_issue() {
  local key="$1"
  if has_issue "${key}"; then
    return 0
  fi
  ISSUE_KEYS="${ISSUE_KEYS},${key}"
  ISSUE_COUNT=$((ISSUE_COUNT + 1))
}

check_path() {
  local key="$1"
  local label="$2"
  local path="$3"
  local kind="$4"

  if [[ "${kind}" == "dir" ]]; then
    if [[ -d "${path}" ]]; then
      say "[ok] ${label}: ${path}"
    else
      say "[warn] ${label}: MISSING (${path})"
      mark_issue "${key}"
    fi
    return 0
  fi

  if [[ -f "${path}" ]]; then
    say "[ok] ${label}: ${path}"
  else
    say "[warn] ${label}: MISSING (${path})"
    mark_issue "${key}"
  fi
}

sig_detected() {
  local blob="$1"
  local pattern="$2"
  printf '%s\n' "${blob}" | grep -Eqi "${pattern}"
}

print_config_highlights() {
  section "Config highlights"

  if [[ ! -f "${CFG}" ]]; then
    say "[warn] config.json missing: ${CFG}"
    mark_issue "config_missing"
    return 0
  fi

  local cfg_dump
  if ! cfg_dump="$(python3 - "${CFG}" <<'PY'
import json
import sys

cfg = sys.argv[1]
with open(cfg, "r", encoding="utf-8") as fh:
    data = json.load(fh) or {}

def txt(value):
    if isinstance(value, list):
        return ",".join(str(item).strip() for item in value if str(item).strip())
    return str(value)

print(f"vaultInbox={txt(data.get('vaultInbox', ''))}")
print(f"browsers={txt(data.get('browsers', []))}")
print(f"llmEnabled={txt(data.get('llmEnabled', ''))}")
print(f"dryRun={txt(data.get('dryRun', ''))}")
print(f"dryRunPolicy={txt(data.get('dryRunPolicy', ''))}")
print(f"checkEveryMinutes={txt(data.get('checkEveryMinutes', ''))}")
print(f"cooldownMinutes={txt(data.get('cooldownMinutes', ''))}")
print(f"maxTabs={txt(data.get('maxTabs', ''))}")
PY
)"; then
    say "[warn] Failed to parse config.json: ${CFG}"
    mark_issue "config_parse_error"
    return 0
  fi

  printf '%s\n' "${cfg_dump}" | sed 's/^/  - /'

  local vault_inbox expanded_vault
  vault_inbox="$(printf '%s\n' "${cfg_dump}" | sed -n 's/^vaultInbox=//p' | head -n 1)"
  if [[ -z "${vault_inbox}" ]]; then
    say "[warn] vaultInbox is empty in config."
    mark_issue "vault_inbox_missing"
    return 0
  fi

  expanded_vault="${vault_inbox/#\~/${HOME}}"
  if [[ -d "${expanded_vault}" ]]; then
    say "[ok] vaultInbox path exists: ${expanded_vault}"
  else
    say "[warn] vaultInbox path missing: ${expanded_vault}"
    mark_issue "vault_inbox_path_missing"
  fi
}

print_launch_agent_status() {
  section "LaunchAgent"
  if [[ -f "${PLIST}" ]]; then
    say "[ok] plist: ${PLIST}"

    local plist_dump
    if plist_dump="$(python3 - "${PLIST}" <<'PY'
import plistlib
import sys

plist_path = sys.argv[1]
with open(plist_path, "rb") as fh:
    data = plistlib.load(fh) or {}

label = data.get("Label", "")
interval = data.get("StartInterval", "")
programs = data.get("ProgramArguments", [])
program0 = programs[0] if isinstance(programs, list) and programs else ""

print(f"Label={label}")
print(f"StartInterval={interval}")
print(f"Program={program0}")
if isinstance(interval, int):
    mins = interval / 60.0
    mins_txt = str(int(mins)) if mins.is_integer() else f"{mins:.2f}"
    print(f"StartIntervalMinutes={mins_txt}")
PY
)"; then
      printf '%s\n' "${plist_dump}" | sed 's/^/  - /'
    else
      say "[warn] Failed to parse plist: ${PLIST}"
      mark_issue "plist_parse_error"
    fi
  else
    say "[warn] plist missing: ${PLIST}"
    mark_issue "plist_missing"
  fi

  if ! command -v launchctl >/dev/null 2>&1; then
    say "[warn] launchctl not available."
    mark_issue "launchctl_missing"
    return 0
  fi

  local list_output
  if list_output="$(launchctl list "${LABEL}" 2>&1)"; then
    say "[ok] launchctl list ${LABEL}:"
    printf '%s\n' "${list_output}" | sed 's/^/  | /'
  else
    say "[warn] launchctl list could not find ${LABEL}."
    printf '%s\n' "${list_output}" | sed 's/^/  | /'
    mark_issue "launch_not_listed"
  fi

  local print_output state_line exit_line last_exit
  if print_output="$(launchctl print "${TARGET}" 2>&1)"; then
    say "[ok] launchctl print ${TARGET}: loaded"
    state_line="$(printf '%s\n' "${print_output}" | sed -n 's/^[[:space:]]*state = /state=/p' | head -n 1)"
    exit_line="$(printf '%s\n' "${print_output}" | sed -n 's/^[[:space:]]*last exit code = /last_exit=/p' | head -n 1)"
    [[ -n "${state_line}" ]] && say "  ${state_line}"
    [[ -n "${exit_line}" ]] && say "  ${exit_line}"
    last_exit="$(printf '%s\n' "${exit_line}" | sed -n 's/^last_exit=//p')"
    if [[ -n "${last_exit}" && "${last_exit}" != "0" ]]; then
      mark_issue "launch_last_exit_nonzero"
    fi
  else
    say "[warn] launchctl print failed for ${TARGET}."
    printf '%s\n' "${print_output}" | sed 's/^/  | /'
    mark_issue "launch_not_loaded"
  fi
}

print_logs_and_signatures() {
  section "Recent logs"

  say "- monitor.out.log (last ${TAIL_LINES} lines):"
  if [[ -f "${OUT_LOG}" ]]; then
    tail -n "${TAIL_LINES}" "${OUT_LOG}" | sed 's/^/  | /'
  else
    say "  | (missing)"
    mark_issue "out_log_missing"
  fi

  say "- monitor.err.log (last ${TAIL_LINES} lines):"
  if [[ -f "${ERR_LOG}" ]]; then
    tail -n "${TAIL_LINES}" "${ERR_LOG}" | sed 's/^/  | /'
  else
    say "  | (missing)"
    mark_issue "err_log_missing"
  fi

  local scan_blob out_scan err_scan
  scan_blob=""
  out_scan=""
  err_scan=""
  if [[ -f "${OUT_LOG}" ]]; then
    out_scan="$(tail -n "${SCAN_LINES}" "${OUT_LOG}" 2>/dev/null || true)"
  fi
  if [[ -f "${ERR_LOG}" ]]; then
    err_scan="$(tail -n "${SCAN_LINES}" "${ERR_LOG}" 2>/dev/null || true)"
  fi
  scan_blob="${out_scan}"$'\n'"${err_scan}"

  section "Detected signatures"
  local found_any=0

  if sig_detected "${scan_blob}" '(-1743|not authorized to send apple events|not permitted to send apple events|appleevents[^[:alnum:]]*(denied|not permitted)|kTCCServiceAppleEvents)'; then
    say "[warn] AppleEvents/TCC denial detected."
    mark_issue "tcc_appleevents_denied"
    found_any=1
  fi

  if sig_detected "${scan_blob}" '(Permission denied|Operation not permitted)'; then
    say "[warn] Filesystem/permission denial detected."
    mark_issue "permission_denied"
    found_any=1
  fi

  if sig_detected "${scan_blob}" '(vaultInbox path missing|vaultInbox.*does not exist|vaultInbox.*not found|No such file or directory.*TabDump .*\.md|No such file or directory.*vault)'; then
    say "[warn] Missing vault inbox path detected."
    mark_issue "vault_inbox_path_missing"
    found_any=1
  fi

  if sig_detected "${scan_blob}" '(config\.json not found|monitor_tabs\.py not found|TabDump app not found)'; then
    say "[warn] Missing runtime file detected (app/config/monitor)."
    mark_issue "runtime_file_missing"
    found_any=1
  fi

  if sig_detected "${scan_blob}" '(count_unavailable)'; then
    say "[warn] count_unavailable observed (fresh tab count not confirmed)."
    mark_issue "count_unavailable"
    found_any=1
  fi

  if [[ "${found_any}" -eq 0 ]]; then
    say "[ok] No known error signatures found in recent logs."
  fi
}

print_fix_hints() {
  if [[ "${SHOW_FIX_HINTS}" -ne 1 ]]; then
    return 0
  fi

  section "Safe repair suggestions"
  say "- Refresh status and logs:"
  say "  scripts/tabdump_status.sh"

  if has_issue "launch_not_loaded" || has_issue "launch_not_listed" || has_issue "launch_last_exit_nonzero" || has_issue "plist_missing"; then
    say "- Reload launch agent:"
    say "  scripts/tabdump_reload_launchagent.sh"
  fi

  if has_issue "tcc_appleevents_denied" || has_issue "permission_denied"; then
    say "- Reset AppleEvents permissions and re-approve prompts:"
    say "  scripts/tabdump_permissions_reset.sh"
    say "  Then run: scripts/tabdump_run_once.sh"
    say "  Open: System Settings -> Privacy & Security -> Automation -> TabDump"
  fi

  if has_issue "vault_inbox_missing" || has_issue "vault_inbox_path_missing"; then
    say "- Fix inbox path in config (example):"
    say "  tabdump config set vaultInbox ~/obsidian/Inbox/"
  fi

  if has_issue "app_missing" || has_issue "config_missing" || has_issue "monitor_missing" || has_issue "runtime_file_missing"; then
    say "- Reinstall/repair runtime files:"
    say "  bash scripts/install.sh --yes --vault-inbox ~/obsidian/Inbox"
  fi

  say "- Re-run doctor:"
  say "  scripts/tabdump_doctor.sh"
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --tail)
      if [[ "$#" -lt 2 || "${2}" == --* ]]; then
        echo "[error] --tail requires an integer value." >&2
        exit 2
      fi
      if [[ ! "${2}" =~ ^[0-9]+$ ]]; then
        echo "[error] --tail expects a non-negative integer." >&2
        exit 2
      fi
      TAIL_LINES="${2}"
      shift 2
      ;;
    --no-fix-hints)
      SHOW_FIX_HINTS=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[error] Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

say "TabDump doctor"

section "Path checks"
check_path "app_missing" "TabDump.app" "${APP}" "dir"
check_path "app_support_missing" "App Support" "${APP_SUPPORT}" "dir"
check_path "config_missing" "config.json" "${CFG}" "file"
check_path "monitor_missing" "monitor_tabs.py" "${MONITOR}" "file"
check_path "logs_dir_missing" "logs dir" "${LOG_DIR}" "dir"
check_path "plist_missing" "LaunchAgent plist" "${PLIST}" "file"

print_config_highlights
print_launch_agent_status
print_logs_and_signatures
print_fix_hints

section "Summary"
if [[ "${ISSUE_COUNT}" -eq 0 ]]; then
  say "[ok] No obvious issues found."
else
  say "[warn] Found ${ISSUE_COUNT} issue(s)."
fi
