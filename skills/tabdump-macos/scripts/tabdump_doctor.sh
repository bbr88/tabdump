#!/usr/bin/env bash
set -euo pipefail

APP="${HOME}/Applications/TabDump.app"
APP_SUPPORT="${HOME}/Library/Application Support/TabDump"
CFG="${APP_SUPPORT}/config.json"
MONITOR="${APP_SUPPORT}/monitor_tabs.py"
LOG_DIR="${APP_SUPPORT}/logs"
OUT_LOG="${LOG_DIR}/monitor.out.log"
PLIST="${HOME}/Library/LaunchAgents/io.orc-visioner.tabdump.monitor.plist"
LABEL="io.orc-visioner.tabdump.monitor"
TARGET="gui/$(id -u)/${LABEL}"

TAIL_LINES=40
SCAN_LINES=200
SHOW_FIX_HINTS=1
JSON_MODE=0
ISSUE_KEYS=""
ISSUE_COUNT=0
ACTION_KEYS=""
CONFIG_CHECK_EVERY=""
PLIST_START_INTERVAL=""

usage() {
  cat <<'USAGE'
Usage:
  scripts/tabdump_doctor.sh [--tail N] [--json] [--no-fix-hints]

Options:
  --tail N          Log lines to print per log file (default: 40).
  --json            Emit machine-readable JSON only.
  --no-fix-hints    Skip repair suggestion section.
  -h, --help        Show this help.
USAGE
}

on_runtime_error() {
  exit 2
}
trap on_runtime_error ERR

say() {
  if [[ "${JSON_MODE}" -eq 0 ]]; then
    printf '%s\n' "$*"
  fi
}

section() {
  if [[ "${JSON_MODE}" -eq 0 ]]; then
    echo
    say "$1"
  fi
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

has_action() {
  local key="$1"
  case ",${ACTION_KEYS}," in
    *",${key},"*) return 0 ;;
    *) return 1 ;;
  esac
}

add_action() {
  local key="$1"
  if has_action "${key}"; then
    return 0
  fi
  ACTION_KEYS="${ACTION_KEYS},${key}"
}

any_issue_in() {
  local key
  for key in "$@"; do
    if has_issue "${key}"; then
      return 0
    fi
  done
  return 1
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

  if [[ "${JSON_MODE}" -eq 0 ]]; then
    printf '%s\n' "${cfg_dump}" | sed 's/^/  - /'
  fi

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

  CONFIG_CHECK_EVERY="$(printf '%s\n' "${cfg_dump}" | sed -n 's/^checkEveryMinutes=//p' | head -n 1)"
}

print_launch_interval_alignment() {
  local expected_interval

  if [[ -z "${CONFIG_CHECK_EVERY}" || ! "${CONFIG_CHECK_EVERY}" =~ ^[0-9]+$ ]]; then
    return 0
  fi
  if [[ -z "${PLIST_START_INTERVAL}" || ! "${PLIST_START_INTERVAL}" =~ ^[0-9]+$ ]]; then
    return 0
  fi

  expected_interval=$(( CONFIG_CHECK_EVERY < 1 ? 60 : CONFIG_CHECK_EVERY * 60 ))
  if [[ "${PLIST_START_INTERVAL}" -ne "${expected_interval}" ]]; then
    say "[warn] LaunchAgent StartInterval mismatch: plist=${PLIST_START_INTERVAL}s, expected=${expected_interval}s from checkEveryMinutes=${CONFIG_CHECK_EVERY}."
    mark_issue "launch_interval_mismatch"
  else
    say "[ok] LaunchAgent StartInterval matches checkEveryMinutes (${PLIST_START_INTERVAL}s)."
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
      if [[ "${JSON_MODE}" -eq 0 ]]; then
        printf '%s\n' "${plist_dump}" | sed 's/^/  - /'
      fi
      PLIST_START_INTERVAL="$(printf '%s\n' "${plist_dump}" | sed -n 's/^StartInterval=//p' | head -n 1)"
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
    if [[ "${JSON_MODE}" -eq 0 ]]; then
      printf '%s\n' "${list_output}" | sed 's/^/  | /'
    fi
  else
    say "[warn] launchctl list could not find ${LABEL}."
    if [[ "${JSON_MODE}" -eq 0 ]]; then
      printf '%s\n' "${list_output}" | sed 's/^/  | /'
    fi
    mark_issue "launch_not_listed"
  fi

  local print_output state_line exit_line last_exit
  if print_output="$(launchctl print "${TARGET}" 2>&1)"; then
    say "[ok] launchctl print ${TARGET}: loaded"
    if [[ "${JSON_MODE}" -eq 0 ]]; then
      state_line="$(printf '%s\n' "${print_output}" | sed -n 's/^[[:space:]]*state = /state=/p' | head -n 1)"
      exit_line="$(printf '%s\n' "${print_output}" | sed -n 's/^[[:space:]]*last exit code = /last_exit=/p' | head -n 1)"
      [[ -n "${state_line}" ]] && say "  ${state_line}"
      [[ -n "${exit_line}" ]] && say "  ${exit_line}"
    fi
    last_exit="$(printf '%s\n' "${print_output}" | sed -n 's/^[[:space:]]*last exit code = //p' | head -n 1)"
    if [[ -n "${last_exit}" && "${last_exit}" != "0" ]]; then
      mark_issue "launch_last_exit_nonzero"
    fi
  else
    say "[warn] launchctl print failed for ${TARGET}."
    if [[ "${JSON_MODE}" -eq 0 ]]; then
      printf '%s\n' "${print_output}" | sed 's/^/  | /'
    fi
    mark_issue "launch_not_loaded"
  fi

  print_launch_interval_alignment
}

print_logs_and_signatures() {
  section "Recent logs"

  say "- monitor.out.log (last ${TAIL_LINES} lines):"
  if [[ -f "${OUT_LOG}" ]]; then
    if [[ "${JSON_MODE}" -eq 0 ]]; then
      tail -n "${TAIL_LINES}" "${OUT_LOG}" | sed 's/^/  | /'
    fi
  else
    say "  | (missing)"
    mark_issue "out_log_missing"
  fi

  local scan_blob out_scan
  scan_blob=""
  out_scan=""
  if [[ -f "${OUT_LOG}" ]]; then
    out_scan="$(tail -n "${SCAN_LINES}" "${OUT_LOG}" 2>/dev/null || true)"
  fi
  scan_blob="${out_scan}"

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

collect_recommended_actions() {
  ACTION_KEYS=""

  if [[ "${ISSUE_COUNT}" -eq 0 ]]; then
    return 0
  fi

  add_action "check_status"
  add_action "check_logs"

  if any_issue_in "launch_not_loaded" "launch_not_listed" "launch_last_exit_nonzero" "plist_missing" "launch_interval_mismatch" "plist_parse_error" "launchctl_missing"; then
    add_action "reinstall_launchagent"
    add_action "reload_launchagent"
  fi

  if any_issue_in "tcc_appleevents_denied" "permission_denied"; then
    add_action "reset_appleevents"
    add_action "run_now"
  fi

  if any_issue_in "vault_inbox_missing" "vault_inbox_path_missing"; then
    add_action "set_vault_inbox"
  fi

  if any_issue_in "app_missing" "app_support_missing" "config_missing" "monitor_missing" "runtime_file_missing"; then
    add_action "reinstall_runtime"
  fi

  if has_issue "count_unavailable"; then
    add_action "recheck_count"
  fi

  add_action "rerun_doctor"
}

print_fix_hints() {
  if [[ "${SHOW_FIX_HINTS}" -ne 1 ]]; then
    return 0
  fi

  section "Safe repair suggestions"
  say "- Refresh status and logs:"
  say "  tabdump status"
  say "  tabdump logs --lines 80"

  if any_issue_in "launch_not_loaded" "launch_not_listed" "launch_last_exit_nonzero" "plist_missing" "launch_interval_mismatch" "plist_parse_error" "launchctl_missing"; then
    say "- Reinstall LaunchAgent from config (clean rebuild):"
    say "  scripts/tabdump_install_launchagent.sh"
    say "- If plist already looks correct, simple reload is also available:"
    say "  scripts/tabdump_reload_launchagent.sh"
  fi

  if any_issue_in "tcc_appleevents_denied" "permission_denied"; then
    say "- Reset AppleEvents permissions and re-approve prompts:"
    say "  scripts/tabdump_permissions_reset.sh"
    say "  Then run: tabdump now"
    say "  Open: System Settings -> Privacy & Security -> Automation -> TabDump"
  fi

  if any_issue_in "vault_inbox_missing" "vault_inbox_path_missing"; then
    say "- Fix inbox path in config (example):"
    say "  tabdump config set vaultInbox ~/obsidian/Inbox/"
  fi

  if any_issue_in "app_missing" "app_support_missing" "config_missing" "monitor_missing" "runtime_file_missing"; then
    say "- Reinstall/repair runtime files:"
    say "  bash scripts/install.sh --yes --vault-inbox ~/obsidian/Inbox"
  fi

  say "- Re-run doctor:"
  say "  scripts/tabdump_doctor.sh"
  say "  scripts/tabdump_doctor.sh --json"
}

emit_json_output() {
  local status

  collect_recommended_actions

  if [[ "${ISSUE_COUNT}" -eq 0 ]]; then
    status="ok"
  else
    status="issues"
  fi

  TABDUMP_DOCTOR_STATUS="${status}" \
  TABDUMP_DOCTOR_ISSUE_COUNT="${ISSUE_COUNT}" \
  TABDUMP_DOCTOR_ISSUE_KEYS="${ISSUE_KEYS}" \
  TABDUMP_DOCTOR_ACTION_KEYS="${ACTION_KEYS}" \
  TABDUMP_PATH_APP="${APP}" \
  TABDUMP_PATH_APP_SUPPORT="${APP_SUPPORT}" \
  TABDUMP_PATH_CONFIG="${CFG}" \
  TABDUMP_PATH_MONITOR="${MONITOR}" \
  TABDUMP_PATH_LOG_DIR="${LOG_DIR}" \
  TABDUMP_PATH_OUT_LOG="${OUT_LOG}" \
  TABDUMP_PATH_PLIST="${PLIST}" \
  python3 - <<'PY'
import datetime
import json
import os

issue_meta = {
    "app_missing": {"severity": "high", "category": "runtime", "message": "TabDump.app is missing."},
    "app_support_missing": {"severity": "medium", "category": "runtime", "message": "App Support directory is missing."},
    "config_missing": {"severity": "high", "category": "config", "message": "config.json is missing."},
    "monitor_missing": {"severity": "high", "category": "runtime", "message": "monitor_tabs.py is missing."},
    "logs_dir_missing": {"severity": "medium", "category": "logs", "message": "Log directory is missing."},
    "plist_missing": {"severity": "medium", "category": "launchagent", "message": "LaunchAgent plist is missing."},
    "config_parse_error": {"severity": "medium", "category": "config", "message": "config.json could not be parsed."},
    "vault_inbox_missing": {"severity": "medium", "category": "config", "message": "vaultInbox is empty in config."},
    "vault_inbox_path_missing": {"severity": "medium", "category": "config", "message": "vaultInbox path does not exist."},
    "launch_interval_mismatch": {"severity": "medium", "category": "launchagent", "message": "LaunchAgent StartInterval does not match checkEveryMinutes."},
    "plist_parse_error": {"severity": "medium", "category": "launchagent", "message": "LaunchAgent plist could not be parsed."},
    "launchctl_missing": {"severity": "medium", "category": "launchagent", "message": "launchctl command is not available."},
    "launch_not_listed": {"severity": "medium", "category": "launchagent", "message": "LaunchAgent label is not listed by launchctl."},
    "launch_last_exit_nonzero": {"severity": "medium", "category": "launchagent", "message": "LaunchAgent last exit code is non-zero."},
    "launch_not_loaded": {"severity": "high", "category": "launchagent", "message": "LaunchAgent is not loaded."},
    "out_log_missing": {"severity": "low", "category": "logs", "message": "monitor.out.log is missing."},
    "tcc_appleevents_denied": {"severity": "high", "category": "permissions", "message": "AppleEvents/TCC denial detected."},
    "permission_denied": {"severity": "medium", "category": "permissions", "message": "Permission denial detected in logs."},
    "runtime_file_missing": {"severity": "high", "category": "runtime", "message": "Runtime file missing signature detected in logs."},
    "count_unavailable": {"severity": "low", "category": "runtime", "message": "count_unavailable observed in logs."},
}

action_meta = {
    "check_status": {
        "command": "tabdump status",
        "reason": "Inspect mode, monitor state, launch agent status, and recent log tails.",
    },
    "check_logs": {
        "command": "tabdump logs --lines 80",
        "reason": "Inspect a broader runtime log window for recurring errors.",
    },
    "reinstall_launchagent": {
        "command": "scripts/tabdump_install_launchagent.sh",
        "reason": "Rebuild LaunchAgent plist from config and restart the job.",
    },
    "reload_launchagent": {
        "command": "scripts/tabdump_reload_launchagent.sh",
        "reason": "Reload an existing LaunchAgent without rewriting the plist.",
    },
    "reset_appleevents": {
        "command": "scripts/tabdump_permissions_reset.sh",
        "reason": "Reset Automation permissions and trigger fresh approval prompts.",
    },
    "run_now": {
        "command": "tabdump now",
        "reason": "Run a forced one-shot dump to verify current runtime health.",
    },
    "set_vault_inbox": {
        "command": "tabdump config set vaultInbox ~/obsidian/Inbox/",
        "reason": "Set a valid inbox path for raw/clean note output.",
    },
    "reinstall_runtime": {
        "command": "bash scripts/install.sh --yes --vault-inbox ~/obsidian/Inbox",
        "reason": "Restore missing runtime app/support files.",
    },
    "recheck_count": {
        "command": "tabdump count --json",
        "reason": "Re-run count to confirm whether fresh tab evidence is available.",
    },
    "rerun_doctor": {
        "command": "scripts/tabdump_doctor.sh --json",
        "reason": "Re-run diagnostics after applying fixes.",
    },
}

status = os.environ.get("TABDUMP_DOCTOR_STATUS", "issues")
issue_count = int(os.environ.get("TABDUMP_DOCTOR_ISSUE_COUNT", "0"))
issue_keys = [k for k in os.environ.get("TABDUMP_DOCTOR_ISSUE_KEYS", "").split(",") if k]
action_keys = [k for k in os.environ.get("TABDUMP_DOCTOR_ACTION_KEYS", "").split(",") if k]

issues = []
for key in issue_keys:
    meta = issue_meta.get(
        key,
        {
            "severity": "medium",
            "category": "unknown",
            "message": "Unknown diagnostic issue.",
        },
    )
    issues.append(
        {
            "id": key,
            "severity": meta["severity"],
            "category": meta["category"],
            "message": meta["message"],
        }
    )

actions = []
for key in action_keys:
    meta = action_meta.get(key)
    if not meta:
        continue
    actions.append(
        {
            "id": key,
            "command": meta["command"],
            "reason": meta["reason"],
        }
    )

payload = {
    "schemaVersion": "tabdump-doctor/v1",
    "status": status,
    "issueCount": issue_count,
    "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
    "issues": issues,
    "recommendedActions": actions,
    "paths": {
        "app": os.environ.get("TABDUMP_PATH_APP", ""),
        "appSupport": os.environ.get("TABDUMP_PATH_APP_SUPPORT", ""),
        "config": os.environ.get("TABDUMP_PATH_CONFIG", ""),
        "monitor": os.environ.get("TABDUMP_PATH_MONITOR", ""),
        "logDir": os.environ.get("TABDUMP_PATH_LOG_DIR", ""),
        "outLog": os.environ.get("TABDUMP_PATH_OUT_LOG", ""),
        "plist": os.environ.get("TABDUMP_PATH_PLIST", ""),
    },
}

print(json.dumps(payload, separators=(",", ":"), sort_keys=False))
PY
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
    --json)
      JSON_MODE=1
      shift
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

if [[ "${JSON_MODE}" -eq 1 ]]; then
  emit_json_output
  if [[ "${ISSUE_COUNT}" -eq 0 ]]; then
    exit 0
  fi
  exit 1
fi

section "Summary"
if [[ "${ISSUE_COUNT}" -eq 0 ]]; then
  say "[ok] No obvious issues found."
else
  say "[warn] Found ${ISSUE_COUNT} issue(s)."
fi
