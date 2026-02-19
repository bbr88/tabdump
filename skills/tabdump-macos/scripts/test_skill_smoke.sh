#!/usr/bin/env bash
set -euo pipefail

# Safety note:
# - Default mode is safe and does not execute active one-shot/count commands.
# - Active mode (`--active`) may open TabDump.app and trigger TCC prompts.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="${TABDUMP_SMOKE_SCRIPTS_DIR:-${ROOT_DIR}/scripts}"
TABDUMP_CMD="${TABDUMP_SMOKE_TABDUMP_CMD:-tabdump}"
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

require_cmd() {
  local cmd="$1"
  command -v "${cmd}" >/dev/null 2>&1 || fail "Required command not found on PATH: ${cmd}"
}

DOCTOR_SCRIPT="${TABDUMP_SMOKE_DOCTOR:-${SCRIPTS_DIR}/tabdump_doctor.sh}"
RELOAD_SCRIPT="${TABDUMP_SMOKE_RELOAD:-${SCRIPTS_DIR}/tabdump_reload_launchagent.sh}"
INSTALL_LAUNCHAGENT_SCRIPT="${TABDUMP_SMOKE_INSTALL_LAUNCHAGENT:-${SCRIPTS_DIR}/tabdump_install_launchagent.sh}"
PERMS_SCRIPT="${TABDUMP_SMOKE_PERMS:-${SCRIPTS_DIR}/tabdump_permissions_reset.sh}"
INSTALL_SCRIPT="${TABDUMP_SMOKE_INSTALL:-${SCRIPTS_DIR}/tabdump_install_from_repo.sh}"
INSTALL_BREW_SCRIPT="${TABDUMP_SMOKE_INSTALL_BREW:-${SCRIPTS_DIR}/tabdump_install_brew.sh}"

require_cmd "${TABDUMP_CMD}"
require_exec "${DOCTOR_SCRIPT}"
require_exec "${RELOAD_SCRIPT}"
require_exec "${INSTALL_LAUNCHAGENT_SCRIPT}"
require_exec "${PERMS_SCRIPT}"
require_exec "${INSTALL_SCRIPT}"
require_exec "${INSTALL_BREW_SCRIPT}"
pass "All required commands/scripts are present and executable."

status_output="$("${TABDUMP_CMD}" status 2>&1)"
printf '%s\n' "${status_output}" | grep -q "TabDump status" || fail "tabdump status output missing header"
pass "tabdump status prints expected header."

doctor_output=""
doctor_code=0
set +e
doctor_output="$("${DOCTOR_SCRIPT}" --json 2>&1)"
doctor_code=$?
set -e

if [[ ${doctor_code} -ne 0 && ${doctor_code} -ne 1 ]]; then
  printf '%s\n' "${doctor_output}" >&2
  fail "doctor --json failed unexpectedly (exit=${doctor_code})."
fi

if ! TABDUMP_DOCTOR_JSON="${doctor_output}" python3 - <<'PY'
import json
import os
import sys

payload = json.loads(os.environ.get("TABDUMP_DOCTOR_JSON", ""))
required_keys = {
    "schemaVersion",
    "status",
    "issueCount",
    "generatedAt",
    "issues",
    "recommendedActions",
    "paths",
}
missing = required_keys.difference(payload.keys())
if missing:
    sys.exit(1)

if payload.get("schemaVersion") != "tabdump-doctor/v1":
    sys.exit(1)
if payload.get("status") not in {"ok", "issues"}:
    sys.exit(1)
if not isinstance(payload.get("issueCount"), int):
    sys.exit(1)
if not isinstance(payload.get("issues"), list):
    sys.exit(1)
if not isinstance(payload.get("recommendedActions"), list):
    sys.exit(1)
if not isinstance(payload.get("paths"), dict):
    sys.exit(1)
PY
then
  printf '%s\n' "${doctor_output}" >&2
  fail "doctor JSON output contract is invalid."
fi

if [[ ${doctor_code} -eq 0 ]]; then
  pass "doctor JSON output contract is valid (healthy)."
else
  pass "doctor JSON output contract is valid (issues detected)."
fi

if [[ "${ACTIVE}" -eq 0 ]]; then
  pass "Safe mode: skipping active now/count runs (use --active to run them)."
  pass "Smoke test completed."
  exit 0
fi

echo "[warn] Active mode may open TabDump.app and trigger macOS Automation (TCC) prompts."

now_output=""
now_code=0
set +e
now_output="$("${TABDUMP_CMD}" now --json 2>&1)"
now_code=$?
set -e

if [[ ${now_code} -ne 0 ]]; then
  printf '%s\n' "${now_output}" >&2
  fail "tabdump now --json failed unexpectedly (exit=${now_code})."
fi

if ! TABDUMP_NOW_JSON="${now_output}" python3 - <<'PY'
import json
import os
import sys

payload = json.loads(os.environ.get("TABDUMP_NOW_JSON", ""))
required = {"status", "reason", "mode", "rawDump", "cleanNote"}
if required.difference(payload.keys()):
    sys.exit(1)
if payload.get("status") not in {"ok", "noop", "error"}:
    sys.exit(1)
for key in ("reason", "mode", "rawDump", "cleanNote"):
    value = payload.get(key)
    if value is None:
        continue
    if not isinstance(value, str):
        sys.exit(1)
PY
then
  printf '%s\n' "${now_output}" >&2
  fail "now JSON output contract is invalid."
fi

pass "now JSON output contract is valid."

count_output=""
count_code=0
count_contract=""
set +e
count_output="$("${TABDUMP_CMD}" count --json 2>&1)"
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
