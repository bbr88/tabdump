#!/usr/bin/env bash
set -euo pipefail

# Note:
# - This command may open TabDump.app in background/hidden mode.
# - First-time runs may still trigger macOS Automation (TCC) prompts.

APP_SUPPORT="${HOME}/Library/Application Support/TabDump"
CFG="${APP_SUPPORT}/config.json"
MONITOR="${APP_SUPPORT}/monitor_tabs.py"
WANT_JSON=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/tabdump_count.sh [--json]
USAGE
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --json)
      WANT_JSON=1
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

is_valid_json() {
  local payload="$1"
  TABDUMP_JSON="${payload}" python3 - <<'PY'
import json
import os
import sys

payload = os.environ.get("TABDUMP_JSON", "")
try:
    json.loads(payload)
except Exception:
    sys.exit(1)
PY
}

read_json_field() {
  local payload="$1"
  local field="$2"
  TABDUMP_JSON="${payload}" TABDUMP_FIELD="${field}" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ.get("TABDUMP_JSON", "{}"))
field = os.environ.get("TABDUMP_FIELD", "")
value = payload.get(field, "")
if value is None:
    value = ""
print(str(value))
PY
}

is_cli_count_unsupported() {
  local payload="$1"
  printf '%s\n' "${payload}" | grep -qiE 'Unknown command: count|Unknown option for tabdump count'
}

run_cli_json() {
  local payload
  local rc

  if ! command -v tabdump >/dev/null 2>&1; then
    return 2
  fi

  set +e
  payload="$(tabdump count --json 2>&1)"
  rc=$?
  set -e

  if [[ ${rc} -eq 0 ]]; then
    if ! is_valid_json "${payload}"; then
      echo "[error] Invalid JSON payload from tabdump count --json." >&2
      echo "${payload}" >&2
      return 1
    fi
    printf '%s\n' "${payload}"
    return 0
  fi

  if is_cli_count_unsupported "${payload}"; then
    return 2
  fi

  echo "[error] tabdump count --json failed." >&2
  [[ -n "${payload}" ]] && echo "${payload}" >&2
  return 1
}

run_monitor_json() {
  local payload

  if [[ ! -f "${CFG}" ]]; then
    echo "[error] config.json not found: ${CFG}" >&2
    return 1
  fi
  if [[ ! -f "${MONITOR}" ]]; then
    echo "[error] monitor_tabs.py not found: ${MONITOR}" >&2
    return 1
  fi

  if ! payload="$(TABDUMP_CONFIG_PATH="${CFG}" python3 "${MONITOR}" --force --mode count --json 2>&1)"; then
    echo "[error] monitor execution failed." >&2
    [[ -n "${payload}" ]] && echo "${payload}" >&2
    return 1
  fi

  if ! is_valid_json "${payload}"; then
    echo "[error] Invalid JSON payload from monitor count run." >&2
    echo "${payload}" >&2
    return 1
  fi

  printf '%s\n' "${payload}"
}

JSON_PAYLOAD=""
set +e
JSON_PAYLOAD="$(run_cli_json)"
CLI_RESULT=$?
set -e

if [[ ${CLI_RESULT} -eq 2 ]]; then
  JSON_PAYLOAD="$(run_monitor_json)"
elif [[ ${CLI_RESULT} -ne 0 ]]; then
  exit 1
fi

if [[ "${WANT_JSON}" -eq 1 ]]; then
  printf '%s\n' "${JSON_PAYLOAD}"
  exit 0
fi

STATUS="$(read_json_field "${JSON_PAYLOAD}" "status")"
TAB_COUNT="$(read_json_field "${JSON_PAYLOAD}" "tabCount")"
REASON="$(read_json_field "${JSON_PAYLOAD}" "reason")"

if [[ "${STATUS}" == "ok" && "${TAB_COUNT}" =~ ^[0-9]+$ ]]; then
  echo "${TAB_COUNT}"
  exit 0
fi

[[ -z "${REASON}" ]] && REASON="unknown"
echo "[error] Failed to count tabs (${REASON})." >&2
exit 1
