#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${HOME}/Applications/TabDump.app"
CONFIG_DIR="${HOME}/Library/Application Support/TabDump"
ENGINE_DEST="${CONFIG_DIR}/TabDump.scpt"
CONFIG_PATH="${CONFIG_DIR}/config.json"
MONITOR_DEST="${CONFIG_DIR}/monitor_tabs.py"
MONITOR_WRAPPER_PATH="${CONFIG_DIR}/tabdump-monitor"
CORE_PKG_DIR="${CONFIG_DIR}/core"
RENDERER_DIR="${CORE_PKG_DIR}/renderer"
POSTPROCESS_DIR="${CORE_PKG_DIR}/postprocess"
TAB_POLICY_DIR="${CORE_PKG_DIR}/tab_policy"
CORE_PYCACHE_DIR="${CORE_PKG_DIR}/__pycache__"
CORE_INIT_PATH="${CORE_PKG_DIR}/__init__.py"
LOG_DIR="${CONFIG_DIR}/logs"
MONITOR_STATE_PATH="${CONFIG_DIR}/monitor_state.json"
MONITOR_LOCK_PATH="${CONFIG_DIR}/monitor_state.lock"
STATE_PATH="${CONFIG_DIR}/state.json"
CLI_PATH="${HOME}/.local/bin/tabdump"
BUNDLE_ID="io.orc-visioner.tabdump"
LAUNCH_AGENT_DIR="${HOME}/Library/LaunchAgents"
LAUNCH_LABEL="io.orc-visioner.tabdump.monitor"
LAUNCH_AGENT_PATH="${LAUNCH_AGENT_DIR}/${LAUNCH_LABEL}.plist"

ASSUME_YES=0
CONFIG_BEHAVIOR="prompt"
PURGE_TCC=0

TOTAL_STEPS=5
CURRENT_STEP=0
REMOVE_CONFIG=0
REMOVED_ITEMS=()
SKIPPED_ITEMS=()
WARNINGS=()

usage() {
  cat <<'USAGE'
Usage:
  scripts/uninstall.sh [options]

Options:
  --yes            Run non-interactively.
  --remove-config  Remove config.json.
  --keep-config    Keep config.json.
  --purge          Reset TCC AppleEvents permission for TabDump.
  -h, --help       Show this help.
USAGE
}

step() {
  CURRENT_STEP=$((CURRENT_STEP + 1))
  echo
  echo "[${CURRENT_STEP}/${TOTAL_STEPS}] $1"
}

print_ok() {
  echo "[ok] $1"
}

print_warn() {
  local message="$1"
  echo "[warn] ${message}"
  WARNINGS+=("${message}")
}

die() {
  echo "[error] $1" >&2
  exit 1
}

prompt_yes_no() {
  local prompt="$1"
  local default="$2"
  local answer=""
  local normalized=""
  local suffix=""

  if [[ "${default}" == "y" ]]; then
    suffix="[Y/n]"
  else
    suffix="[y/N]"
  fi

  while true; do
    if ! read -r -p "${prompt} ${suffix}: " answer; then
      die "Input cancelled."
    fi
    if [[ -z "${answer}" ]]; then
      answer="${default}"
    fi
    normalized="$(echo "${answer}" | tr '[:upper:]' '[:lower:]')"
    case "${normalized}" in
      y|yes)
        return 0
        ;;
      n|no)
        return 1
        ;;
      *)
        echo "Please answer y or n."
        ;;
    esac
  done
}

record_removed() {
  REMOVED_ITEMS+=("$1")
}

record_skipped() {
  SKIPPED_ITEMS+=("$1")
}

remove_file_if_exists() {
  local path="$1"
  local label="$2"
  if [[ -e "${path}" || -L "${path}" ]]; then
    rm -f "${path}"
    record_removed "${label}: ${path}"
  else
    record_skipped "${label}: not present"
  fi
}

remove_dir_if_exists() {
  local path="$1"
  local label="$2"
  if [[ -d "${path}" ]]; then
    rm -rf "${path}"
    record_removed "${label}: ${path}"
  else
    record_skipped "${label}: not present"
  fi
}

rmdir_if_empty() {
  local path="$1"
  local label="$2"
  if [[ -d "${path}" ]]; then
    if rmdir "${path}" 2>/dev/null; then
      record_removed "${label}: ${path} (empty directory)"
    else
      record_skipped "${label}: left in place (not empty)"
    fi
  else
    record_skipped "${label}: not present"
  fi
}

parse_args() {
  local remove_seen=0
  local keep_seen=0

  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --yes)
        ASSUME_YES=1
        shift
        ;;
      --remove-config)
        if [[ "${keep_seen}" -eq 1 ]]; then
          die "--remove-config and --keep-config cannot be used together."
        fi
        remove_seen=1
        CONFIG_BEHAVIOR="remove"
        shift
        ;;
      --keep-config)
        if [[ "${remove_seen}" -eq 1 ]]; then
          die "--remove-config and --keep-config cannot be used together."
        fi
        keep_seen=1
        CONFIG_BEHAVIOR="keep"
        shift
        ;;
      --purge)
        PURGE_TCC=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Unknown option: $1"
        ;;
    esac
  done
}

determine_confirmation_and_config_behavior() {
  echo "TabDump uninstaller"
  echo "This will remove:"
  echo "  - ${ENGINE_DEST}"
  echo "  - ${MONITOR_DEST}"
  echo "  - ${MONITOR_WRAPPER_PATH}"
  echo "  - ${APP_PATH}"
  echo "  - ${CLI_PATH}"
  echo "  - ${LAUNCH_AGENT_PATH}"
  echo "  - ${RENDERER_DIR}"
  echo "  - ${POSTPROCESS_DIR}"
  echo "  - ${TAB_POLICY_DIR}"
  echo "  - ${CORE_PKG_DIR}"
  echo "  - ${LOG_DIR}"
  echo "  - ${MONITOR_STATE_PATH}"
  echo "  - ${MONITOR_LOCK_PATH}"
  echo "  - ${STATE_PATH}"
  echo "  - ${CONFIG_PATH} (optional)"

  if [[ "${ASSUME_YES}" -ne 1 ]]; then
    if ! prompt_yes_no "Proceed?" "n"; then
      echo "Aborted."
      exit 0
    fi
  fi

  case "${CONFIG_BEHAVIOR}" in
    remove)
      REMOVE_CONFIG=1
      ;;
    keep)
      REMOVE_CONFIG=0
      ;;
    prompt)
      if [[ "${ASSUME_YES}" -eq 1 ]]; then
        REMOVE_CONFIG=0
      else
        if prompt_yes_no "Remove config.json too?" "n"; then
          REMOVE_CONFIG=1
        else
          REMOVE_CONFIG=0
        fi
      fi
      ;;
    *)
      die "Unexpected config behavior: ${CONFIG_BEHAVIOR}"
      ;;
  esac

  if [[ "${PURGE_TCC}" -eq 1 ]]; then
    print_ok "TCC purge requested (--purge)."
  else
    print_ok "TCC permissions will be left unchanged (use --purge to reset)."
  fi

  if [[ "${REMOVE_CONFIG}" -eq 1 ]]; then
    print_ok "config.json will be removed."
  else
    print_ok "config.json will be kept."
  fi
}

stop_services_and_optional_purge() {
  local uid_num
  local target
  local output

  if [[ "${PURGE_TCC}" -eq 1 ]]; then
    if command -v tccutil >/dev/null 2>&1; then
      if output="$(tccutil reset AppleEvents "${BUNDLE_ID}" 2>&1)"; then
        record_removed "TCC reset: AppleEvents ${BUNDLE_ID}"
      else
        print_warn "tccutil reset reported: ${output}"
      fi
    else
      print_warn "tccutil not found; skipped TCC reset."
    fi
  else
    record_skipped "TCC reset: skipped (use --purge)"
  fi

  if command -v launchctl >/dev/null 2>&1; then
    uid_num="$(id -u)"
    target="gui/${uid_num}"
    if output="$(launchctl bootout "${target}" "${LAUNCH_AGENT_PATH}" 2>&1)"; then
      record_removed "launchctl bootout: ${LAUNCH_LABEL}"
    else
      print_warn "launchctl bootout reported: ${output}"
      record_skipped "launchctl bootout: ${LAUNCH_LABEL} (not loaded or already stopped)"
    fi
  else
    print_warn "launchctl not found; skipped service shutdown."
    record_skipped "launchctl bootout: skipped (launchctl missing)"
  fi
}

remove_runtime_artifacts() {
  remove_file_if_exists "${LAUNCH_AGENT_PATH}" "Launch agent plist"
  remove_dir_if_exists "${APP_PATH}" "Application bundle"
  remove_file_if_exists "${CLI_PATH}" "CLI launcher"
  remove_file_if_exists "${ENGINE_DEST}" "AppleScript engine"
  remove_file_if_exists "${MONITOR_DEST}" "Monitor script"
  remove_file_if_exists "${MONITOR_WRAPPER_PATH}" "Monitor wrapper"

  remove_dir_if_exists "${RENDERER_DIR}" "Renderer package"
  remove_dir_if_exists "${POSTPROCESS_DIR}" "Postprocess package"
  remove_dir_if_exists "${TAB_POLICY_DIR}" "Tab policy package"
  remove_dir_if_exists "${CORE_PYCACHE_DIR}" "Core __pycache__"
  remove_file_if_exists "${CORE_INIT_PATH}" "Core package __init__"
  rmdir_if_empty "${CORE_PKG_DIR}" "Core package directory"

  remove_file_if_exists "${MONITOR_STATE_PATH}" "Monitor state file"
  remove_file_if_exists "${MONITOR_LOCK_PATH}" "Monitor lock file"
  remove_dir_if_exists "${LOG_DIR}" "Logs directory"
  remove_file_if_exists "${STATE_PATH}" "Legacy state file"
}

remove_optional_config_and_cleanup() {
  if [[ "${REMOVE_CONFIG}" -eq 1 ]]; then
    remove_file_if_exists "${CONFIG_PATH}" "Config file"
  else
    record_skipped "Config file: kept by user choice"
  fi

  rmdir_if_empty "${CONFIG_DIR}" "Config directory"
}

print_summary() {
  local item

  echo
  echo "Removed:"
  if [[ "${#REMOVED_ITEMS[@]}" -eq 0 ]]; then
    echo "  - none"
  else
    for item in "${REMOVED_ITEMS[@]}"; do
      echo "  - ${item}"
    done
  fi

  echo
  echo "Skipped:"
  if [[ "${#SKIPPED_ITEMS[@]}" -eq 0 ]]; then
    echo "  - none"
  else
    for item in "${SKIPPED_ITEMS[@]}"; do
      echo "  - ${item}"
    done
  fi

  if [[ "${#WARNINGS[@]}" -gt 0 ]]; then
    echo
    echo "Warnings:"
    for item in "${WARNINGS[@]}"; do
      echo "  - ${item}"
    done
  fi

  echo
  echo "Done."
}

main() {
  parse_args "$@"

  step "Confirm uninstall choices"
  determine_confirmation_and_config_behavior

  step "Stop services and optional purge"
  stop_services_and_optional_purge
  print_ok "Service shutdown completed."

  step "Remove runtime artifacts"
  remove_runtime_artifacts
  print_ok "Runtime artifacts removed where present."

  step "Remove optional config and clean directories"
  remove_optional_config_and_cleanup
  print_ok "Config cleanup step completed."

  step "Summary"
  print_summary
}

main "$@"
