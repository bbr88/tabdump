#!/usr/bin/env bash
set -euo pipefail

APP_SUPPORT="${HOME}/Library/Application Support/TabDump"
CFG="${APP_SUPPORT}/config.json"
MONITOR="${APP_SUPPORT}/monitor_tabs.py"
MODE_ARG="dump-only"

usage() {
  cat <<'USAGE'
Usage:
  scripts/tabdump_run_once.sh [--close]
USAGE
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --close)
      MODE_ARG="dump-close"
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

JSON_PAYLOAD=""
RAW_DUMP=""
CLEAN_NOTE=""
STATUS=""
REASON=""

if command -v tabdump >/dev/null 2>&1; then
  if [[ "${MODE_ARG}" == "dump-close" ]]; then
    if JSON_PAYLOAD="$(tabdump now --close --json 2>/dev/null)"; then
      :
    else
      JSON_PAYLOAD=""
    fi
  else
    if JSON_PAYLOAD="$(tabdump now --json 2>/dev/null)"; then
      :
    else
      JSON_PAYLOAD=""
    fi
  fi
fi

if [[ -z "${JSON_PAYLOAD}" ]]; then
  if [[ ! -f "${CFG}" ]]; then
    echo "[error] config.json not found: ${CFG}" >&2
    exit 1
  fi
  if [[ ! -f "${MONITOR}" ]]; then
    echo "[error] monitor_tabs.py not found: ${MONITOR}" >&2
    exit 1
  fi

  if ! JSON_PAYLOAD="$(TABDUMP_CONFIG_PATH="${CFG}" python3 "${MONITOR}" --force --mode "${MODE_ARG}" --json 2>&1)"; then
    echo "[error] monitor execution failed." >&2
    [[ -n "${JSON_PAYLOAD}" ]] && echo "${JSON_PAYLOAD}" >&2
    exit 1
  fi
fi

if ! TABDUMP_JSON="${JSON_PAYLOAD}" python3 - <<'PY'
import json
import os

json.loads(os.environ.get("TABDUMP_JSON", ""))
PY
then
  echo "[error] Invalid JSON payload from one-shot run." >&2
  echo "${JSON_PAYLOAD}" >&2
  exit 1
fi

extract_field() {
  local field="$1"
  TABDUMP_JSON="${JSON_PAYLOAD}" TABDUMP_FIELD="${field}" python3 - <<'PY'
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

STATUS="$(extract_field status)"
REASON="$(extract_field reason)"
RAW_DUMP="$(extract_field rawDump)"
CLEAN_NOTE="$(extract_field cleanNote)"

if [[ -z "${RAW_DUMP}" && -n "${CLEAN_NOTE}" && "${CLEAN_NOTE}" == *" (clean).md" ]]; then
  RAW_DUMP="${CLEAN_NOTE% (clean).md}.md"
fi

echo "RAW_DUMP=${RAW_DUMP}"
echo "CLEAN_NOTE=${CLEAN_NOTE}"

if [[ "${STATUS}" == "ok" ]]; then
  exit 0
fi

if [[ "${STATUS}" == "noop" ]]; then
  [[ -z "${REASON}" ]] && REASON="unknown"
  echo "[info] No clean dump produced (${REASON})."
  echo "[hint] Check status/logs with: scripts/tabdump_status.sh"
  exit 3
fi

[[ -z "${REASON}" ]] && REASON="unknown"
if [[ -z "${STATUS}" ]]; then
  echo "[error] One-shot run returned empty status (${REASON})." >&2
else
  echo "[error] One-shot run failed with status=${STATUS} (${REASON})." >&2
fi
exit 1
