#!/usr/bin/env bash
set -euo pipefail

# Safety note:
# - Default mode is safe and does not execute active one-shot/count commands.
# - Active mode (`--active`) may open TabDump.app and trigger TCC prompts.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="${TABDUMP_SMOKE_SCRIPTS_DIR:-${ROOT_DIR}/scripts}"
ACTIVE=0

pass() { printf '[ok] %s\n' "$*"; }
fail() { printf '[error] %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
Usage:
  scripts/test_skill_smoke.sh [--active]
USAGE
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --active)
      ACTIVE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown option: $1"
      ;;
  esac
done

require_exec() {
  local p="$1"
  [[ -x "$p" ]] || fail "Missing executable script: $p"
}

RUN_ONCE_SCRIPT="${TABDUMP_SMOKE_RUN_ONCE:-${SCRIPTS_DIR}/tabdump_run_once.sh}"
COUNT_SCRIPT="${TABDUMP_SMOKE_COUNT:-${SCRIPTS_DIR}/tabdump_count.sh}"
STATUS_SCRIPT="${TABDUMP_SMOKE_STATUS:-${SCRIPTS_DIR}/tabdump_status.sh}"
RELOAD_SCRIPT="${TABDUMP_SMOKE_RELOAD:-${SCRIPTS_DIR}/tabdump_reload_launchagent.sh}"
PERMS_SCRIPT="${TABDUMP_SMOKE_PERMS:-${SCRIPTS_DIR}/tabdump_permissions_reset.sh}"
INSTALL_SCRIPT="${TABDUMP_SMOKE_INSTALL:-${SCRIPTS_DIR}/tabdump_install_from_repo.sh}"
INSTALL_BREW_SCRIPT="${TABDUMP_SMOKE_INSTALL_BREW:-${SCRIPTS_DIR}/tabdump_install_brew.sh}"

require_exec "${RUN_ONCE_SCRIPT}"
require_exec "${COUNT_SCRIPT}"
require_exec "${STATUS_SCRIPT}"
require_exec "${RELOAD_SCRIPT}"
require_exec "${PERMS_SCRIPT}"
require_exec "${INSTALL_SCRIPT}"
require_exec "${INSTALL_BREW_SCRIPT}"
pass "All required scripts are present and executable."

status_output="$(${STATUS_SCRIPT})"
printf '%s\n' "${status_output}" | grep -q "TabDump status" || fail "status output missing header"
pass "Status command prints expected header."

if [[ "${ACTIVE}" -eq 0 ]]; then
  pass "Safe mode: skipping active one-shot/count runs (use --active to run them)."
  pass "Smoke test completed."
  exit 0
fi

echo "[warn] Active mode may open TabDump.app and trigger macOS Automation (TCC) prompts."

run_output=""
run_code=0
set +e
run_output="$(${RUN_ONCE_SCRIPT} 2>&1)"
run_code=$?
set -e

printf '%s\n' "${run_output}" | grep -q '^RAW_DUMP=' || fail "run_once output missing RAW_DUMP"
printf '%s\n' "${run_output}" | grep -q '^CLEAN_NOTE=' || fail "run_once output missing CLEAN_NOTE"

if [[ ${run_code} -eq 0 ]]; then
  pass "run_once success output contract is valid."
elif [[ ${run_code} -eq 3 ]]; then
  printf '%s\n' "${run_output}" | grep -q "No clean dump produced" || fail "run_once code=3 without noop diagnostic"
  pass "run_once noop path produced expected diagnostic."
else
  printf '%s\n' "${run_output}" >&2
  fail "run_once failed unexpectedly (exit=${run_code})."
fi

count_output=""
count_code=0
count_contract=""
set +e
count_output="$(${COUNT_SCRIPT} --json 2>&1)"
count_code=$?
set -e

if [[ ${count_code} -ne 0 ]]; then
  printf '%s\n' "${count_output}" >&2
  fail "count failed unexpectedly (exit=${count_code})."
fi

if ! count_contract="$(
  TABDUMP_COUNT_JSON="${count_output}" python3 - <<'PY'
import json
import os
import sys

payload = json.loads(os.environ.get("TABDUMP_COUNT_JSON", ""))
if payload.get("mode") != "count":
    sys.exit(1)

status = payload.get("status")
reason = payload.get("reason")
tab_count = payload.get("tabCount")

if status == "ok":
    if isinstance(tab_count, bool) or not isinstance(tab_count, int):
        sys.exit(1)
    print("ok")
    sys.exit(0)

if status == "error":
    if reason != "count_unavailable":
        sys.exit(1)
    if tab_count not in (None, ""):
        sys.exit(1)
    print("count_unavailable")
    sys.exit(0)

sys.exit(1)
PY
)"; then
  printf '%s\n' "${count_output}" >&2
  fail "count output contract is invalid."
fi

if [[ "${count_contract}" == "ok" ]]; then
  pass "count success output contract is valid."
else
  pass "count fail-hard output contract is valid."
fi

pass "Smoke test completed."
