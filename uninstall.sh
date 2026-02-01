#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${HOME}/Applications/TabDump.app"
CONFIG_DIR="${HOME}/Library/Application Support/TabDump"
ENGINE_DEST="${CONFIG_DIR}/TabDump.scpt"
CONFIG_PATH="${CONFIG_DIR}/config.json"
MONITOR_STATE_PATH="${CONFIG_DIR}/monitor_state.json"
MONITOR_LOCK_PATH="${CONFIG_DIR}/monitor_state.lock"
STATE_PATH="${CONFIG_DIR}/state.json"
CLI_PATH="${HOME}/.local/bin/tabdump"
BUNDLE_ID="io.orc-visioner.tabdump"

ASSUME_YES=0
if [[ "${1:-}" == "--yes" ]]; then
  ASSUME_YES=1
fi

echo "TabDump uninstaller"
echo "This will remove:"
echo "  - ${ENGINE_DEST}"
echo "  - ${APP_PATH}"
echo "  - ${CLI_PATH}"
echo "  - ${MONITOR_STATE_PATH}"
echo "  - ${MONITOR_LOCK_PATH}"
echo "  - ${STATE_PATH}"
echo "  - ${CONFIG_PATH} (optional)"
echo

if [[ "${ASSUME_YES}" -ne 1 ]]; then
  read -r -p "Proceed? (y/N): " CONFIRM
  if [[ "${CONFIRM}" != "y" && "${CONFIRM}" != "Y" ]]; then
    echo "Aborted."
    exit 0
  fi
fi

REMOVE_CONFIG=0
if [[ "${ASSUME_YES}" -eq 1 ]]; then
  REMOVE_CONFIG=1
else
  read -r -p "Remove config.json too? (y/N): " CONFIRM_CFG
  if [[ "${CONFIRM_CFG}" == "y" || "${CONFIRM_CFG}" == "Y" ]]; then
    REMOVE_CONFIG=1
  fi
fi

if command -v tccutil >/dev/null 2>&1; then
  tccutil reset AppleEvents "${BUNDLE_ID}" >/dev/null 2>&1 || true
fi

if [[ -e "${APP_PATH}" ]]; then
  rm -rf "${APP_PATH}"
fi

if [[ -e "${CLI_PATH}" ]]; then
  rm -f "${CLI_PATH}"
fi

if [[ -e "${ENGINE_DEST}" ]]; then
  rm -f "${ENGINE_DEST}"
fi

if [[ -e "${MONITOR_STATE_PATH}" ]]; then
  rm -f "${MONITOR_STATE_PATH}"
fi

if [[ -e "${MONITOR_LOCK_PATH}" ]]; then
  rm -f "${MONITOR_LOCK_PATH}"
fi

if [[ -e "${STATE_PATH}" ]]; then
  rm -f "${STATE_PATH}"
fi

if [[ "${REMOVE_CONFIG}" -eq 1 && -e "${CONFIG_PATH}" ]]; then
  rm -f "${CONFIG_PATH}"
fi

if [[ -d "${CONFIG_DIR}" ]]; then
  rmdir "${CONFIG_DIR}" 2>/dev/null || true
fi

echo "Done."
