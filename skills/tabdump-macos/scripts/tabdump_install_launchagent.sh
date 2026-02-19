#!/usr/bin/env bash
set -euo pipefail

APP_SUPPORT="${HOME}/Library/Application Support/TabDump"
CFG="${APP_SUPPORT}/config.json"
MONITOR_WRAPPER="${APP_SUPPORT}/tabdump-monitor"
LOG_DIR="${APP_SUPPORT}/logs"
LAUNCH_AGENT_DIR="${HOME}/Library/LaunchAgents"
PLIST="${LAUNCH_AGENT_DIR}/io.orc-visioner.tabdump.monitor.plist"
LABEL="io.orc-visioner.tabdump.monitor"
TARGET="gui/$(id -u)"
DEFAULT_KEYCHAIN_SERVICE="${TABDUMP_KEYCHAIN_SERVICE_DEFAULT:-TabDump}"
DEFAULT_KEYCHAIN_ACCOUNT="${TABDUMP_KEYCHAIN_ACCOUNT_DEFAULT:-openai}"

usage() {
  cat <<'USAGE'
Usage:
  scripts/tabdump_install_launchagent.sh

Behavior:
  - Reads checkEveryMinutes from ~/Library/Application Support/TabDump/config.json
  - Writes/overwrites ~/Library/LaunchAgents/io.orc-visioner.tabdump.monitor.plist
  - Bootstraps + enables + kickstarts the launch agent
USAGE
}

warn() {
  printf '[warn] %s\n' "$*"
}

die_usage() {
  printf '[error] %s\n' "$*" >&2
  exit 2
}

die_runtime() {
  printf '[error] %s\n' "$*" >&2
  exit 1
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "$#" -ne 0 ]]; then
  die_usage "Unknown option: $1"
fi

if [[ ! -f "${CFG}" ]]; then
  die_usage "config.json not found: ${CFG}"
fi

if [[ ! -x "${MONITOR_WRAPPER}" ]]; then
  die_usage "monitor wrapper missing or not executable: ${MONITOR_WRAPPER}"
fi

if ! command -v launchctl >/dev/null 2>&1; then
  die_usage "launchctl not found on PATH."
fi

mkdir -p "${LAUNCH_AGENT_DIR}" "${LOG_DIR}"

PY_OUT="$(
  CFG="${CFG}" \
  MONITOR_WRAPPER="${MONITOR_WRAPPER}" \
  LOG_DIR="${LOG_DIR}" \
  PLIST="${PLIST}" \
  DEFAULT_KEYCHAIN_SERVICE="${DEFAULT_KEYCHAIN_SERVICE}" \
  DEFAULT_KEYCHAIN_ACCOUNT="${DEFAULT_KEYCHAIN_ACCOUNT}" \
  TABDUMP_KEYCHAIN_SERVICE="${TABDUMP_KEYCHAIN_SERVICE:-}" \
  TABDUMP_KEYCHAIN_ACCOUNT="${TABDUMP_KEYCHAIN_ACCOUNT:-}" \
  python3 - <<'PY'
import json
import os
import plistlib
import sys

cfg_path = os.environ["CFG"]
monitor_wrapper = os.environ["MONITOR_WRAPPER"]
log_dir = os.environ["LOG_DIR"]
plist_path = os.environ["PLIST"]
default_service = os.environ["DEFAULT_KEYCHAIN_SERVICE"]
default_account = os.environ["DEFAULT_KEYCHAIN_ACCOUNT"]
env_service = os.environ.get("TABDUMP_KEYCHAIN_SERVICE", "").strip()
env_account = os.environ.get("TABDUMP_KEYCHAIN_ACCOUNT", "").strip()

try:
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh) or {}
except Exception as exc:
    print(f"config parse failed: {exc}", file=sys.stderr)
    raise SystemExit(2)

minutes_raw = cfg.get("checkEveryMinutes", 60)
try:
    minutes = int(minutes_raw)
except Exception:
    print(f"invalid checkEveryMinutes value: {minutes_raw!r}", file=sys.stderr)
    raise SystemExit(2)

if minutes < 1:
    minutes = 1

start_interval = minutes * 60

existing_service = ""
existing_account = ""
if os.path.exists(plist_path):
    try:
        with open(plist_path, "rb") as fh:
            old = plistlib.load(fh) or {}
        env_old = old.get("EnvironmentVariables", {})
        if isinstance(env_old, dict):
            existing_service = str(env_old.get("TABDUMP_KEYCHAIN_SERVICE", "")).strip()
            existing_account = str(env_old.get("TABDUMP_KEYCHAIN_ACCOUNT", "")).strip()
    except Exception:
        # Continue with defaults if existing plist is malformed.
        pass

keychain_service = env_service or existing_service or default_service
keychain_account = env_account or existing_account or default_account

plist = {
    "Label": "io.orc-visioner.tabdump.monitor",
    "ProgramArguments": [monitor_wrapper],
    "EnvironmentVariables": {
        "TABDUMP_KEYCHAIN_SERVICE": keychain_service,
        "TABDUMP_KEYCHAIN_ACCOUNT": keychain_account,
    },
    "StartInterval": start_interval,
    "RunAtLoad": True,
    "StandardOutPath": os.path.join(log_dir, "monitor.out.log"),
    "StandardErrorPath": os.path.join(log_dir, "monitor.err.log"),
}

with open(plist_path, "wb") as fh:
    plistlib.dump(plist, fh)

print(f"start_interval={start_interval}")
print(f"keychain_service={keychain_service}")
print(f"keychain_account={keychain_account}")
PY
)"

chmod 600 "${PLIST}"

START_INTERVAL="$(printf '%s\n' "${PY_OUT}" | sed -n 's/^start_interval=//p' | head -n 1)"
KEYCHAIN_SERVICE="$(printf '%s\n' "${PY_OUT}" | sed -n 's/^keychain_service=//p' | head -n 1)"
KEYCHAIN_ACCOUNT="$(printf '%s\n' "${PY_OUT}" | sed -n 's/^keychain_account=//p' | head -n 1)"

if [[ -z "${START_INTERVAL}" ]]; then
  die_runtime "failed to compute StartInterval."
fi

echo "[ok] Wrote launch agent plist: ${PLIST}"
echo "  StartInterval=${START_INTERVAL} seconds"
echo "  TABDUMP_KEYCHAIN_SERVICE=${KEYCHAIN_SERVICE}"
echo "  TABDUMP_KEYCHAIN_ACCOUNT=${KEYCHAIN_ACCOUNT}"

if bootout_output="$(launchctl bootout "${TARGET}" "${PLIST}" 2>&1)"; then
  echo "[ok] launchctl bootout completed."
else
  case "${bootout_output}" in
    *"Boot-out failed: 5:"*|*"No such process"*|*"Could not find service"*)
      echo "[ok] No loaded service to boot out."
      ;;
    *)
      warn "launchctl bootout reported: ${bootout_output}"
      ;;
  esac
fi

if ! bootstrap_output="$(launchctl bootstrap "${TARGET}" "${PLIST}" 2>&1)"; then
  die_runtime "launchctl bootstrap failed: ${bootstrap_output}"
fi

if ! enable_output="$(launchctl enable "${TARGET}/${LABEL}" 2>&1)"; then
  die_runtime "launchctl enable failed: ${enable_output}"
fi

if ! kickstart_output="$(launchctl kickstart -k "${TARGET}/${LABEL}" 2>&1)"; then
  die_runtime "launchctl kickstart failed: ${kickstart_output}"
fi

echo "[ok] Installed and started ${LABEL}."
