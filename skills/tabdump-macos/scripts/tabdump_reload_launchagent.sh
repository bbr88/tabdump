#!/usr/bin/env bash
set -euo pipefail

PLIST="${HOME}/Library/LaunchAgents/io.orc-visioner.tabdump.monitor.plist"
LABEL="io.orc-visioner.tabdump.monitor"
UID_NUM="$(id -u)"
TARGET="gui/${UID_NUM}"

if [[ ! -f "${PLIST}" ]]; then
  echo "[error] Launch agent plist not found: ${PLIST}" >&2
  exit 2
fi

if bootout_output="$(launchctl bootout "${TARGET}" "${PLIST}" 2>&1)"; then
  echo "[ok] launchctl bootout completed."
else
  case "${bootout_output}" in
    *"Boot-out failed: 5:"*|*"No such process"*|*"Could not find service"*)
      echo "[ok] No loaded service to boot out."
      ;;
    *)
      echo "[warn] launchctl bootout reported: ${bootout_output}" >&2
      ;;
  esac
fi

launchctl bootstrap "${TARGET}" "${PLIST}"
launchctl enable "${TARGET}/${LABEL}"
launchctl kickstart -k "${TARGET}/${LABEL}"

echo "[ok] Reloaded ${LABEL}."
