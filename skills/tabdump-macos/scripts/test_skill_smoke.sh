#!/usr/bin/env bash
set -euo pipefail

# Safety note:
# - Default mode is safe and does not execute an active one-shot dump.
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
STATUS_SCRIPT="${TABDUMP_SMOKE_STATUS:-${SCRIPTS_DIR}/tabdump_status.sh}"
RELOAD_SCRIPT="${TABDUMP_SMOKE_RELOAD:-${SCRIPTS_DIR}/tabdump_reload_launchagent.sh}"
PERMS_SCRIPT="${TABDUMP_SMOKE_PERMS:-${SCRIPTS_DIR}/tabdump_permissions_reset.sh}"
INSTALL_SCRIPT="${TABDUMP_SMOKE_INSTALL:-${SCRIPTS_DIR}/tabdump_install_from_repo.sh}"

require_exec "${RUN_ONCE_SCRIPT}"
require_exec "${STATUS_SCRIPT}"
require_exec "${RELOAD_SCRIPT}"
require_exec "${PERMS_SCRIPT}"
require_exec "${INSTALL_SCRIPT}"
pass "All required scripts are present and executable."

status_output="$(${STATUS_SCRIPT})"
printf '%s\n' "${status_output}" | grep -q "TabDump status" || fail "status output missing header"
pass "Status command prints expected header."

if [[ "${ACTIVE}" -eq 0 ]]; then
  pass "Safe mode: skipping active one-shot run (use --active to run it)."
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

pass "Smoke test completed."
