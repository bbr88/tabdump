#!/usr/bin/env bash
set -euo pipefail
umask 077

CONFIG_DIR="${HOME}/Library/Application Support/TabDump"
CONFIG_PATH="${CONFIG_DIR}/config.json"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST_PATH="${ROOT_DIR}/scripts/runtime-manifest.sha256"
ENGINE_SOURCE="${ROOT_DIR}/macos/configurable-tabDump.scpt"
ENGINE_DEST="${CONFIG_DIR}/TabDump.scpt"
CORE_DIR="${ROOT_DIR}/core"
RENDERER_DIR="${CORE_DIR}/renderer"
POSTPROCESS_PKG_DIR="${CORE_DIR}/postprocess"
TAB_POLICY_PKG_DIR="${CORE_DIR}/tab_policy"
MONITOR_SOURCE="${CORE_DIR}/monitor_tabs.py"
MONITOR_DEST="${CONFIG_DIR}/monitor_tabs.py"
MONITOR_WRAPPER_DEST="${CONFIG_DIR}/tabdump-monitor"
CORE_PKG_DEST="${CONFIG_DIR}/core"
RENDERER_DEST_DIR="${CORE_PKG_DEST}/renderer"
POSTPROCESS_DEST_DIR="${CORE_PKG_DEST}/postprocess"
TAB_POLICY_DEST_DIR="${CORE_PKG_DEST}/tab_policy"
POSTPROCESS_CLI_DEST="${POSTPROCESS_DEST_DIR}/cli.py"
APP_PATH="${HOME}/Applications/TabDump.app"
APP_ARCHIVE_DEFAULT="${ROOT_DIR}/dist/tabdump-app.tar.gz"
BUNDLE_ID="io.orc-visioner.tabdump"
BIN_DIR="${HOME}/.local/bin"
CLI_PATH="${BIN_DIR}/tabdump"
LAUNCH_AGENT_DIR="${HOME}/Library/LaunchAgents"
LAUNCH_LABEL="io.orc-visioner.tabdump.monitor"
LAUNCH_AGENT_PATH="${LAUNCH_AGENT_DIR}/${LAUNCH_LABEL}.plist"
LOG_DIR="${CONFIG_DIR}/logs"
KEYCHAIN_SERVICE="${TABDUMP_KEYCHAIN_SERVICE:-TabDump}"
KEYCHAIN_ACCOUNT="${TABDUMP_KEYCHAIN_ACCOUNT:-openai}"

ASSUME_YES=0
VAULT_INBOX_INPUT=""
APP_ARCHIVE_INPUT=""
DRY_RUN_OVERRIDE=""
LLM_OVERRIDE=""
BROWSERS_INPUT=""
KEY_MODE_OVERRIDE=""
OPENAI_KEY_SOURCE=""
REPLACE_KEYCHAIN_OVERRIDE=""
DELETE_KEYCHAIN_OVERRIDE=""
MAX_TABS_OVERRIDE=""
CHECK_EVERY_MINUTES_OVERRIDE=""
COOLDOWN_MINUTES_OVERRIDE=""

VAULT_INBOX=""
APP_ARCHIVE_PATH="${TABDUMP_APP_ARCHIVE:-${APP_ARCHIVE_DEFAULT}}"
PYTHON_BIN=""
BROWSERS_CSV="Chrome,Safari"
DRY_RUN_VALUE="true"
LLM_ENABLED="false"
KEY_MODE="skip"
OPENAI_KEY_VALUE=""
REPLACE_KEYCHAIN="false"
DELETE_KEYCHAIN="false"
MAX_TABS_VALUE="30"
CHECK_EVERY_MINUTES_VALUE="60"
COOLDOWN_MINUTES_VALUE="1440"

TOTAL_STEPS=9
CURRENT_STEP=0
WARNINGS=()

usage() {
  cat <<'USAGE'
Usage:
  scripts/install.sh [options]

Options:
  --yes                               Run non-interactively with defaults where possible.
  --vault-inbox <path>                Required in --yes mode. Vault inbox path.
  --app-archive <path>                Prebuilt TabDump.app archive (.tar.gz).
  --browsers <csv>                    Comma-separated browsers (supported: Chrome,Safari,Firefox).
  --set-dry-run <true|false>          Final dryRun value for config.json.
  --enable-llm <true|false>           Final llmEnabled value for config.json.
  --max-tabs <int>=0                  Final maxTabs value for config.json.
  --check-every-minutes <int>=0       Final checkEveryMinutes value for config.json.
  --cooldown-minutes <int>=0          Final cooldownMinutes value for config.json.
  --key-mode <keychain|env|skip>      LLM key handling strategy when llmEnabled=true.
  --openai-key <value|env:VAR>        OpenAI API key source for keychain mode.
  --replace-keychain <true|false>     Replace existing keychain item in keychain mode.
  --delete-keychain <true|false>      Delete keychain item in env mode if one exists.
  -h, --help                          Show this help.
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

require_value() {
  local option="$1"
  local value="${2:-}"
  if [[ -z "${value}" || "${value}" == --* ]]; then
    die "Option ${option} requires a value."
  fi
}

normalize_bool() {
  local value
  value="$(echo "$1" | tr '[:upper:]' '[:lower:]')"
  case "${value}" in
    true|1|yes|y)
      echo "true"
      ;;
    false|0|no|n)
      echo "false"
      ;;
    *)
      return 1
      ;;
  esac
}

parse_bool_option() {
  local option="$1"
  local raw="$2"
  local parsed
  if ! parsed="$(normalize_bool "${raw}")"; then
    die "Invalid value for ${option}: ${raw}. Expected true or false."
  fi
  echo "${parsed}"
}

parse_nonnegative_int_option() {
  local option="$1"
  local raw="$2"
  if [[ ! "${raw}" =~ ^[0-9]+$ ]]; then
    die "Invalid value for ${option}: ${raw}. Expected a non-negative integer."
  fi
  echo "${raw}"
}

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "${value}"
}

canonical_browser() {
  local input="$1"
  local lower
  lower="$(echo "${input}" | tr '[:upper:]' '[:lower:]')"
  case "${lower}" in
    chrome)
      echo "Chrome"
      ;;
    safari)
      echo "Safari"
      ;;
    firefox)
      echo "Firefox"
      ;;
    *)
      return 1
      ;;
  esac
}

browser_app_name() {
  case "$1" in
    Chrome)
      echo "Google Chrome"
      ;;
    Safari)
      echo "Safari"
      ;;
    Firefox)
      echo "Firefox"
      ;;
    *)
      echo ""
      ;;
  esac
}

warn_missing_browsers() {
  if ! command -v osascript >/dev/null 2>&1; then
    print_warn "Could not verify browser installation (osascript not found)."
    return 0
  fi

  local old_ifs="${IFS}"
  local -a selected=()
  local browser
  local app_name

  IFS=',' read -r -a selected <<< "${BROWSERS_CSV}"
  IFS="${old_ifs}"

  for browser in "${selected[@]}"; do
    app_name="$(browser_app_name "${browser}")"
    if [[ -z "${app_name}" ]]; then
      continue
    fi
    if ! osascript -e "id of application \"${app_name}\"" >/dev/null 2>&1; then
      print_warn "${browser} is configured but not installed. TabDump will skip it until installed."
    fi
  done
}

path_contains_bin_dir() {
  case ":${PATH}:" in
    *":${BIN_DIR}:"*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

detect_shell_rc_file() {
  local shell_name
  shell_name="$(basename "${SHELL:-}")"
  case "${shell_name}" in
    zsh)
      echo "${HOME}/.zshrc"
      ;;
    bash)
      if [[ -f "${HOME}/.bashrc" ]]; then
        echo "${HOME}/.bashrc"
      else
        echo "${HOME}/.bash_profile"
      fi
      ;;
    *)
      echo "${HOME}/.profile"
      ;;
  esac
}

configure_cli_path() {
  local rc_file path_line

  if path_contains_bin_dir; then
    print_ok "CLI directory already on PATH: ${BIN_DIR}"
    return 0
  fi

  rc_file="$(detect_shell_rc_file)"
  path_line='export PATH="$HOME/.local/bin:$PATH"'

  mkdir -p "$(dirname "${rc_file}")"
  touch "${rc_file}"

  if grep -Eq '^[[:space:]]*(export[[:space:]]+)?PATH=.*[.]local/bin' "${rc_file}" || \
     grep -Eq '^[[:space:]]*path[+]?=.*[.]local/bin' "${rc_file}"; then
    print_ok "PATH already configured in ${rc_file}."
  else
    {
      echo ""
      echo "# Added by TabDump installer"
      echo "${path_line}"
    } >> "${rc_file}"
    print_ok "Added ${BIN_DIR} to PATH in ${rc_file}."
  fi

  print_warn "Open a new terminal session (or source ${rc_file}) to use tabdump by name."
}

validate_and_normalize_browsers() {
  local csv="$1"
  local old_ifs="${IFS}"
  local -a raw_items=()
  local -a normalized=()
  local item
  local canonical
  local exists
  local i
  local joined

  IFS=',' read -r -a raw_items <<< "${csv}"
  IFS="${old_ifs}"

  for item in "${raw_items[@]}"; do
    item="$(trim "${item}")"
    if [[ -z "${item}" ]]; then
      continue
    fi
    if ! canonical="$(canonical_browser "${item}")"; then
      return 1
    fi
    exists=0
    if [[ "${#normalized[@]}" -gt 0 ]]; then
      for i in "${normalized[@]}"; do
        if [[ "${i}" == "${canonical}" ]]; then
          exists=1
          break
        fi
      done
    fi
    if [[ "${exists}" -eq 0 ]]; then
      normalized+=("${canonical}")
    fi
  done

  if [[ "${#normalized[@]}" -eq 0 ]]; then
    return 1
  fi

  joined="${normalized[0]}"
  local idx
  for ((idx=1; idx<${#normalized[@]}; idx++)); do
    joined+=",${normalized[idx]}"
  done

  echo "${joined}"
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

normalize_vault_path() {
  VAULT_INBOX_RAW="$1" python3 - <<'PY'
import os
import sys

raw = os.environ.get("VAULT_INBOX_RAW", "").strip()
if not raw:
    sys.exit(1)

path = os.path.expanduser(raw)
path = os.path.abspath(path)
if not path.endswith(os.sep):
    path += os.sep
print(path)
PY
}

normalize_file_path() {
  INPUT_PATH_RAW="$1" python3 - <<'PY'
import os
import sys

raw = os.environ.get("INPUT_PATH_RAW", "").strip()
if not raw:
    sys.exit(1)

path = os.path.abspath(os.path.expanduser(raw))
print(path)
PY
}

prompt_required_vault_inbox() {
  local input
  local normalized
  while true; do
    if ! read -r -p "Vault Inbox path (required): " input; then
      die "Input cancelled."
    fi
    if [[ -z "$(trim "${input}")" ]]; then
      echo "Vault Inbox path is required." >&2
      continue
    fi
    if normalized="$(normalize_vault_path "${input}")"; then
      echo "${normalized}"
      return 0
    fi
    echo "Vault Inbox path is required." >&2
  done
}

prompt_browsers() {
  local input
  local normalized
  local default="Chrome,Safari"
  while true; do
    if ! read -r -p "Browsers to collect (comma-separated) [${default}]: " input; then
      die "Input cancelled."
    fi
    if [[ -z "$(trim "${input}")" ]]; then
      input="${default}"
    fi
    if normalized="$(validate_and_normalize_browsers "${input}")"; then
      echo "${normalized}"
      return 0
    fi
    echo "Invalid browser list. Supported browsers: Chrome, Safari, Firefox." >&2
  done
}

prompt_key_mode() {
  local choice
  while true; do
    echo "OpenAI key setup:" >&2
    echo "  1) Keychain (recommended)" >&2
    echo "  2) I'll set OPENAI_API_KEY myself (env fallback)" >&2
    echo "  3) Skip for now" >&2
    if ! read -r -p "Select [1-3] (default 1): " choice; then
      die "Input cancelled."
    fi
    case "${choice}" in
      ""|1)
        echo "keychain"
        return 0
        ;;
      2)
        echo "env"
        return 0
        ;;
      3)
        echo "skip"
        return 0
        ;;
      *)
        echo "Please choose 1, 2, or 3." >&2
        ;;
    esac
  done
}

resolve_openai_key_value() {
  local source="$1"
  local var_name
  local value

  if [[ "${source}" == env:* ]]; then
    var_name="${source#env:}"
    if [[ -z "${var_name}" ]]; then
      die "Invalid --openai-key value: ${source}. Use env:VAR or a literal key."
    fi
    value="${!var_name:-}"
    if [[ -z "${value}" ]]; then
      die "Environment variable ${var_name} is empty or not set."
    fi
    echo "${value}"
    return 0
  fi

  if [[ -z "${source}" ]]; then
    die "OpenAI API key is empty."
  fi

  echo "${source}"
}

require_cmd() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    die "Required command not found on PATH: ${command_name}"
  fi
}

verify_runtime_manifest() {
  if [[ ! -f "${MANIFEST_PATH}" ]]; then
    die "Runtime manifest not found: ${MANIFEST_PATH}"
  fi

  local output
  if ! output="$(cd "${ROOT_DIR}" && shasum -a 256 -c "${MANIFEST_PATH}" 2>&1)"; then
    echo "${output}" >&2
    die "Runtime manifest verification failed. Aborting install."
  fi
}

resolve_app_archive_path() {
  if [[ -n "${APP_ARCHIVE_INPUT}" ]]; then
    APP_ARCHIVE_PATH="${APP_ARCHIVE_INPUT}"
  fi

  if ! APP_ARCHIVE_PATH="$(normalize_file_path "${APP_ARCHIVE_PATH}")"; then
    die "Invalid --app-archive value: ${APP_ARCHIVE_PATH}"
  fi

  if [[ ! -f "${APP_ARCHIVE_PATH}" ]]; then
    die "Prebuilt app archive not found: ${APP_ARCHIVE_PATH}. Run scripts/build-release.sh first."
  fi
}

parse_args() {
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --yes)
        ASSUME_YES=1
        shift
        ;;
      --vault-inbox)
        require_value "$1" "${2:-}"
        VAULT_INBOX_INPUT="$2"
        shift 2
        ;;
      --app-archive)
        require_value "$1" "${2:-}"
        APP_ARCHIVE_INPUT="$2"
        shift 2
        ;;
      --browsers)
        require_value "$1" "${2:-}"
        BROWSERS_INPUT="$2"
        shift 2
        ;;
      --set-dry-run)
        require_value "$1" "${2:-}"
        DRY_RUN_OVERRIDE="$(parse_bool_option "$1" "$2")"
        shift 2
        ;;
      --enable-llm)
        require_value "$1" "${2:-}"
        LLM_OVERRIDE="$(parse_bool_option "$1" "$2")"
        shift 2
        ;;
      --max-tabs)
        require_value "$1" "${2:-}"
        MAX_TABS_OVERRIDE="$(parse_nonnegative_int_option "$1" "$2")"
        shift 2
        ;;
      --check-every-minutes)
        require_value "$1" "${2:-}"
        CHECK_EVERY_MINUTES_OVERRIDE="$(parse_nonnegative_int_option "$1" "$2")"
        shift 2
        ;;
      --cooldown-minutes)
        require_value "$1" "${2:-}"
        COOLDOWN_MINUTES_OVERRIDE="$(parse_nonnegative_int_option "$1" "$2")"
        shift 2
        ;;
      --key-mode)
        require_value "$1" "${2:-}"
        case "$2" in
          keychain|env|skip)
            KEY_MODE_OVERRIDE="$2"
            ;;
          *)
            die "Invalid --key-mode value: $2. Expected keychain, env, or skip."
            ;;
        esac
        shift 2
        ;;
      --openai-key)
        require_value "$1" "${2:-}"
        OPENAI_KEY_SOURCE="$2"
        shift 2
        ;;
      --replace-keychain)
        require_value "$1" "${2:-}"
        REPLACE_KEYCHAIN_OVERRIDE="$(parse_bool_option "$1" "$2")"
        shift 2
        ;;
      --delete-keychain)
        require_value "$1" "${2:-}"
        DELETE_KEYCHAIN_OVERRIDE="$(parse_bool_option "$1" "$2")"
        shift 2
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

enforce_option_combinations() {
  if [[ -n "${OPENAI_KEY_SOURCE}" && "${KEY_MODE_OVERRIDE}" != "keychain" ]]; then
    die "--openai-key requires --key-mode keychain."
  fi

  if [[ -n "${REPLACE_KEYCHAIN_OVERRIDE}" && "${KEY_MODE_OVERRIDE}" != "keychain" ]]; then
    die "--replace-keychain requires --key-mode keychain."
  fi

  if [[ -n "${DELETE_KEYCHAIN_OVERRIDE}" && "${KEY_MODE_OVERRIDE}" != "env" ]]; then
    die "--delete-keychain requires --key-mode env."
  fi
}

collect_install_choices() {
  local normalized
  resolve_app_archive_path

  echo "This will create/update:"
  echo "  - ${ENGINE_DEST}"
  echo "  - ${MONITOR_DEST}"
  echo "  - ${MONITOR_WRAPPER_DEST}"
  echo "  - ${POSTPROCESS_CLI_DEST}"
  echo "  - ${CONFIG_PATH}"
  echo "  - ${APP_PATH}"
  echo "  - ${CLI_PATH}"
  echo "  - ${LAUNCH_AGENT_PATH}"
  echo "  - App archive: ${APP_ARCHIVE_PATH}"
  echo "  - Python: ${PYTHON_BIN}"

  if [[ -n "${VAULT_INBOX_INPUT}" ]]; then
    if ! VAULT_INBOX="$(normalize_vault_path "${VAULT_INBOX_INPUT}")"; then
      die "Vault Inbox path is required."
    fi
  elif [[ "${ASSUME_YES}" -eq 1 ]]; then
    die "--vault-inbox is required when running with --yes."
  else
    VAULT_INBOX="$(prompt_required_vault_inbox)"
  fi

  if [[ -n "${BROWSERS_INPUT}" ]]; then
    if ! normalized="$(validate_and_normalize_browsers "${BROWSERS_INPUT}")"; then
      die "Invalid browser list: ${BROWSERS_INPUT}. Supported browsers: Chrome, Safari, Firefox."
    fi
    BROWSERS_CSV="${normalized}"
  elif [[ "${ASSUME_YES}" -eq 0 ]]; then
    BROWSERS_CSV="$(prompt_browsers)"
  fi

  if [[ -n "${MAX_TABS_OVERRIDE}" ]]; then
    MAX_TABS_VALUE="${MAX_TABS_OVERRIDE}"
  fi
  if [[ -n "${CHECK_EVERY_MINUTES_OVERRIDE}" ]]; then
    CHECK_EVERY_MINUTES_VALUE="${CHECK_EVERY_MINUTES_OVERRIDE}"
  fi
  if [[ -n "${COOLDOWN_MINUTES_OVERRIDE}" ]]; then
    COOLDOWN_MINUTES_VALUE="${COOLDOWN_MINUTES_OVERRIDE}"
  fi

  if [[ -n "${DRY_RUN_OVERRIDE}" ]]; then
    DRY_RUN_VALUE="${DRY_RUN_OVERRIDE}"
  elif [[ "${ASSUME_YES}" -eq 0 ]]; then
    echo
    echo "Mode setup:"
    echo "  🧪 dryRun=true  (dump-only): save raw+clean notes, keep tabs open."
    echo "  ⚠️ dryRun=false (dump+close): also close non-allowlisted/non-pinned tabs."
    if prompt_yes_no "Start in dump+close now?" "n"; then
      DRY_RUN_VALUE="false"
    fi
  fi

  if [[ -n "${LLM_OVERRIDE}" ]]; then
    LLM_ENABLED="${LLM_OVERRIDE}"
  elif [[ "${ASSUME_YES}" -eq 0 ]]; then
    echo
    echo "LLM enrichment is optional and enabled by default."
    if prompt_yes_no "Enable LLM enrichment now?" "y"; then
      LLM_ENABLED="true"
    else
      LLM_ENABLED="false"
    fi
  fi

  if [[ "${LLM_ENABLED}" == "false" ]]; then
    if [[ -n "${KEY_MODE_OVERRIDE}" || -n "${OPENAI_KEY_SOURCE}" || -n "${REPLACE_KEYCHAIN_OVERRIDE}" || -n "${DELETE_KEYCHAIN_OVERRIDE}" ]]; then
      die "Key options require --enable-llm true."
    fi
    return 0
  fi

  if [[ -n "${KEY_MODE_OVERRIDE}" ]]; then
    KEY_MODE="${KEY_MODE_OVERRIDE}"
  elif [[ "${ASSUME_YES}" -eq 1 ]]; then
    KEY_MODE="skip"
  else
    KEY_MODE="$(prompt_key_mode)"
  fi

  if [[ "${KEY_MODE}" == "keychain" ]]; then
    if [[ -n "${OPENAI_KEY_SOURCE}" ]]; then
      OPENAI_KEY_VALUE="$(resolve_openai_key_value "${OPENAI_KEY_SOURCE}")"
    elif [[ "${ASSUME_YES}" -eq 1 ]]; then
      OPENAI_KEY_VALUE="${OPENAI_API_KEY:-}"
    else
      echo "Paste your OpenAI API key (input hidden), then press Enter:"
      if ! read -rs OPENAI_KEY_VALUE; then
        die "Input cancelled."
      fi
      echo
    fi
    OPENAI_KEY_VALUE="$(trim "${OPENAI_KEY_VALUE}")"
    if [[ -z "${OPENAI_KEY_VALUE}" ]]; then
      if [[ "${ASSUME_YES}" -eq 1 ]]; then
        print_warn "No OpenAI key provided for keychain mode; skipping keychain write and relying on existing keychain item or OPENAI_API_KEY env var."
      else
        print_warn "Empty OpenAI key input; switching to local classifier (llmEnabled=false)."
        KEY_MODE="skip"
      fi
    fi

    if [[ "${KEY_MODE}" == "keychain" && -n "${REPLACE_KEYCHAIN_OVERRIDE}" ]]; then
      REPLACE_KEYCHAIN="${REPLACE_KEYCHAIN_OVERRIDE}"
    fi
  fi

  if [[ "${KEY_MODE}" == "env" && -n "${DELETE_KEYCHAIN_OVERRIDE}" ]]; then
    DELETE_KEYCHAIN="${DELETE_KEYCHAIN_OVERRIDE}"
  fi

  if [[ "${KEY_MODE}" == "skip" ]]; then
    LLM_ENABLED="false"
    print_warn "OpenAI key setup skipped; local classifier will be used (llmEnabled=false)."
  fi
}

prepare_directories() {
  mkdir -p "${VAULT_INBOX}"
  mkdir -p "${CONFIG_DIR}"
  mkdir -p "${RENDERER_DEST_DIR}"
  mkdir -p "${POSTPROCESS_DEST_DIR}"
  mkdir -p "${TAB_POLICY_DEST_DIR}"
  mkdir -p "${LOG_DIR}"
  mkdir -p "$(dirname "${APP_PATH}")"
  mkdir -p "${BIN_DIR}"
  mkdir -p "${LAUNCH_AGENT_DIR}"
}

install_runtime_files() {
  cp -f "${ENGINE_SOURCE}" "${ENGINE_DEST}"
  cp -f "${MONITOR_SOURCE}" "${MONITOR_DEST}"
  cat > "${MONITOR_WRAPPER_DEST}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "${PYTHON_BIN}" "${MONITOR_DEST}" "\$@"
EOF
  cp -f "${CORE_DIR}/__init__.py" "${CORE_PKG_DEST}/__init__.py"
  cp -f "${RENDERER_DIR}"/*.py "${RENDERER_DEST_DIR}/"
  cp -f "${POSTPROCESS_PKG_DIR}"/*.py "${POSTPROCESS_DEST_DIR}/"
  cp -f "${TAB_POLICY_PKG_DIR}"/*.py "${TAB_POLICY_DEST_DIR}/"

  chmod 700 "${CONFIG_DIR}" "${CORE_PKG_DEST}" "${RENDERER_DEST_DIR}" "${POSTPROCESS_DEST_DIR}" "${TAB_POLICY_DEST_DIR}" "${LOG_DIR}"
  chmod 700 "${MONITOR_WRAPPER_DEST}"
  chmod 600 "${ENGINE_DEST}" "${MONITOR_DEST}" "${CORE_PKG_DEST}/__init__.py"
  chmod 600 "${RENDERER_DEST_DIR}"/*.py
  chmod 600 "${POSTPROCESS_DEST_DIR}"/*.py
  chmod 600 "${TAB_POLICY_DEST_DIR}"/*.py
}

write_config() {
  VAULT_INBOX="${VAULT_INBOX}" \
  CONFIG_PATH="${CONFIG_PATH}" \
  DRY_RUN_VALUE="${DRY_RUN_VALUE}" \
  LLM_ENABLED="${LLM_ENABLED}" \
  BROWSERS_CSV="${BROWSERS_CSV}" \
  MAX_TABS_VALUE="${MAX_TABS_VALUE}" \
  CHECK_EVERY_MINUTES_VALUE="${CHECK_EVERY_MINUTES_VALUE}" \
  COOLDOWN_MINUTES_VALUE="${COOLDOWN_MINUTES_VALUE}" \
  python3 - <<'PY'
import json
import os
import time

vault_inbox = os.environ["VAULT_INBOX"]
config_path = os.environ["CONFIG_PATH"]
dry_run = os.environ["DRY_RUN_VALUE"].strip().lower() == "true"
dry_run_policy = "auto" if dry_run else "manual"
llm_enabled = os.environ["LLM_ENABLED"].strip().lower() == "true"
browsers_csv = os.environ.get("BROWSERS_CSV", "Chrome,Safari")
browsers = [item.strip() for item in browsers_csv.split(",") if item.strip()]
max_tabs = int(os.environ.get("MAX_TABS_VALUE", "30"))
check_every_minutes = int(os.environ.get("CHECK_EVERY_MINUTES_VALUE", "60"))
cooldown_minutes = int(os.environ.get("COOLDOWN_MINUTES_VALUE", "1440"))

data = {
  "vaultInbox": vault_inbox,
  "outputFilenameTemplate": "TabDump {ts}.md",
  "browsers": browsers,
  "allowlistUrlContains": [
    "mail.google.com",
    "calendar.google.com",
    "slack.com",
    "notion.so"
  ],
  "keepPinnedTabs": True,
  "skipUrlPrefixes": [
    "chrome://",
    "chrome-extension://",
    "about:",
    "file://",
    "safari-web-extension://",
    "favorites://",
    "safari://"
  ],
  "skipTitlesExact": ["New Tab", "Start Page"],
  "outputGroupByWindow": True,
  "outputIncludeMetadata": False,
  "dryRun": dry_run,
  "dryRunPolicy": dry_run_policy,
  "onboardingStartedAt": int(time.time()),
  "maxTabs": max_tabs,
  "checkEveryMinutes": check_every_minutes,
  "cooldownMinutes": cooldown_minutes,
  "llmEnabled": llm_enabled,
  "tagModel": "gpt-4.1-mini",
  "llmRedact": True,
  "llmRedactQuery": True,
  "llmTitleMax": 200,
  "maxItems": 0,
  "docsMoreLinksGroupingMode": "kind"
}

with open(config_path, "w", encoding="utf-8") as f:
  json.dump(data, f, indent=2)
  f.write("\n")
PY

  chmod 600 "${CONFIG_PATH}"
}

configure_llm_key_mode() {
  if [[ "${LLM_ENABLED}" != "true" ]]; then
    print_ok "LLM enrichment remains disabled (llmEnabled=false)."
    return 0
  fi

  case "${KEY_MODE}" in
    keychain)
      if security find-generic-password -s "${KEYCHAIN_SERVICE}" -a "${KEYCHAIN_ACCOUNT}" >/dev/null 2>&1; then
        if [[ -n "${REPLACE_KEYCHAIN_OVERRIDE}" ]]; then
          REPLACE_KEYCHAIN="${REPLACE_KEYCHAIN_OVERRIDE}"
        elif [[ "${ASSUME_YES}" -eq 0 ]]; then
          if prompt_yes_no "Keychain item exists for service=${KEYCHAIN_SERVICE}, account=${KEYCHAIN_ACCOUNT}. Replace?" "n"; then
            REPLACE_KEYCHAIN="true"
          else
            REPLACE_KEYCHAIN="false"
          fi
        fi

        if [[ "${REPLACE_KEYCHAIN}" == "true" ]]; then
          if [[ -n "${OPENAI_KEY_VALUE}" ]]; then
            security add-generic-password -s "${KEYCHAIN_SERVICE}" -a "${KEYCHAIN_ACCOUNT}" -w "${OPENAI_KEY_VALUE}" -U >/dev/null
            print_ok "Stored OpenAI key in Keychain (service=${KEYCHAIN_SERVICE}, account=${KEYCHAIN_ACCOUNT})."
          else
            print_warn "Requested keychain replacement but no key value was provided; keeping existing Keychain item."
          fi
        else
          print_warn "Kept existing Keychain item."
        fi
      else
        if [[ -n "${OPENAI_KEY_VALUE}" ]]; then
          security add-generic-password -s "${KEYCHAIN_SERVICE}" -a "${KEYCHAIN_ACCOUNT}" -w "${OPENAI_KEY_VALUE}" >/dev/null
          print_ok "Stored OpenAI key in Keychain (service=${KEYCHAIN_SERVICE}, account=${KEYCHAIN_ACCOUNT})."
        else
          print_warn "No OpenAI key value provided; keychain was not updated. Runtime resolution order is Keychain, then OPENAI_API_KEY env var."
        fi
      fi
      ;;
    env)
      print_ok "Skipping key storage. Runtime resolution order is Keychain, then OPENAI_API_KEY env var."
      if security find-generic-password -s "${KEYCHAIN_SERVICE}" -a "${KEYCHAIN_ACCOUNT}" >/dev/null 2>&1; then
        if [[ -n "${DELETE_KEYCHAIN_OVERRIDE}" ]]; then
          DELETE_KEYCHAIN="${DELETE_KEYCHAIN_OVERRIDE}"
        elif [[ "${ASSUME_YES}" -eq 0 ]]; then
          print_warn "A Keychain item exists and will take precedence over env vars."
          if prompt_yes_no "Delete existing Keychain item?" "n"; then
            DELETE_KEYCHAIN="true"
          else
            DELETE_KEYCHAIN="false"
          fi
        fi

        if [[ "${DELETE_KEYCHAIN}" == "true" ]]; then
          security delete-generic-password -s "${KEYCHAIN_SERVICE}" -a "${KEYCHAIN_ACCOUNT}" >/dev/null 2>&1 || true
          print_ok "Deleted Keychain item."
        else
          print_warn "Keeping Keychain item; it will be used first."
        fi
      fi
      ;;
    skip)
      print_warn "Skipping OpenAI key setup."
      ;;
    *)
      die "Unsupported key mode: ${KEY_MODE}"
      ;;
  esac
}

install_prebuilt_app_bundle() {
  local tmp_dir
  local extracted_app

  tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/tabdump-app.XXXXXX")"

  if ! tar -xzf "${APP_ARCHIVE_PATH}" -C "${tmp_dir}"; then
    rm -rf "${tmp_dir}"
    die "Failed to extract prebuilt app archive: ${APP_ARCHIVE_PATH}"
  fi

  if [[ -d "${tmp_dir}/TabDump.app" ]]; then
    extracted_app="${tmp_dir}/TabDump.app"
  else
    extracted_app="$(find "${tmp_dir}" -maxdepth 4 -type d -name 'TabDump.app' | head -n 1 || true)"
  fi

  if [[ -z "${extracted_app}" || ! -d "${extracted_app}" ]]; then
    rm -rf "${tmp_dir}"
    die "Archive did not contain TabDump.app: ${APP_ARCHIVE_PATH}"
  fi

  if [[ -d "${APP_PATH}" ]]; then
    rm -rf "${APP_PATH}"
  fi
  cp -R "${extracted_app}" "${APP_PATH}"
  rm -rf "${tmp_dir}"
}

build_app_and_cli() {
  install_prebuilt_app_bundle

  cat > "${CLI_PATH}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

APP_PATH="$HOME/Applications/TabDump.app"
CONFIG_PATH="$HOME/Library/Application Support/TabDump/config.json"
MONITOR_PATH="$HOME/Library/Application Support/TabDump/monitor_tabs.py"
STATE_DIR="$HOME/Library/Application Support/TabDump"
MONITOR_STATE_PATH="$STATE_DIR/monitor_state.json"
LEGACY_STATE_PATH="$STATE_DIR/state.json"
LOG_DIR="$STATE_DIR/logs"
LAUNCH_LABEL="io.orc-visioner.tabdump.monitor"
LAUNCH_AGENT_PATH="$HOME/Library/LaunchAgents/${LAUNCH_LABEL}.plist"
BREW_FORMULA_NAME="tabdump"

usage() {
  cat <<'USAGE'
Usage:
  tabdump init [install-options]
  tabdump uninstall [uninstall-options]
  tabdump [run|open]
  tabdump count [--json]
  tabdump now [--close] [--json]
  tabdump mode [show|dump-only|dump-close|auto]
  tabdump config [show|get <key>|set <key> <value> ...]
  tabdump status
  tabdump permissions
  tabdump help
USAGE
}

open_tabdump() {
  if [[ ! -d "${APP_PATH}" ]]; then
    echo "[error] TabDump app not found at ${APP_PATH}" >&2
    exit 1
  fi
  open "${APP_PATH}"
}

find_brew_libexec_root() {
  local prefix

  if command -v brew >/dev/null 2>&1; then
    prefix="$(brew --prefix "${BREW_FORMULA_NAME}" 2>/dev/null || true)"
    if [[ -n "${prefix}" && -d "${prefix}/libexec" ]]; then
      echo "${prefix}/libexec"
      return 0
    fi
  fi

  if [[ -d "/opt/homebrew/opt/${BREW_FORMULA_NAME}/libexec" ]]; then
    echo "/opt/homebrew/opt/${BREW_FORMULA_NAME}/libexec"
    return 0
  fi
  if [[ -d "/usr/local/opt/${BREW_FORMULA_NAME}/libexec" ]]; then
    echo "/usr/local/opt/${BREW_FORMULA_NAME}/libexec"
    return 0
  fi

  return 1
}

init_cmd() {
  local libexec archive

  if ! libexec="$(find_brew_libexec_root)"; then
    echo "[error] Could not locate Homebrew runtime package for '${BREW_FORMULA_NAME}'." >&2
    echo "[hint] Ensure '${BREW_FORMULA_NAME}' is installed via Homebrew and run again." >&2
    return 1
  fi

  archive="$(find "${libexec}/dist" -maxdepth 1 -type f -name 'tabdump-app-v*.tar.gz' | head -n 1 || true)"
  if [[ -z "${archive}" ]]; then
    echo "[error] prebuilt app archive not found under ${libexec}/dist" >&2
    return 1
  fi

  exec "${libexec}/scripts/install.sh" --app-archive "${archive}" "$@"
}

uninstall_cmd() {
  local libexec

  if ! libexec="$(find_brew_libexec_root)"; then
    echo "[error] Could not locate Homebrew runtime package for '${BREW_FORMULA_NAME}'." >&2
    echo "[hint] If you installed from source, run scripts/uninstall.sh from your clone." >&2
    return 1
  fi

  exec "${libexec}/scripts/uninstall.sh" "$@"
}

browser_app_name() {
  case "$1" in
    Chrome)
      echo "Google Chrome"
      ;;
    Safari)
      echo "Safari"
      ;;
    Firefox)
      echo "Firefox"
      ;;
    *)
      echo ""
      ;;
  esac
}

load_browsers_csv() {
  CONFIG_PATH="${CONFIG_PATH}" python3 - <<'PY'
import json
import os

config_path = os.environ.get("CONFIG_PATH", "")
default = ["Chrome", "Safari"]
mapping = {"chrome": "Chrome", "safari": "Safari", "firefox": "Firefox"}

data = {}
if config_path and os.path.exists(config_path):
  try:
    with open(config_path, "r", encoding="utf-8") as fh:
      data = json.load(fh) or {}
  except Exception:
    data = {}

raw = data.get("browsers", default)
if not isinstance(raw, list):
  raw = default

normalized = []
seen = set()
for item in raw:
  key = str(item).strip().lower()
  val = mapping.get(key)
  if not val:
    continue
  if val in seen:
    continue
  seen.add(val)
  normalized.append(val)

if not normalized:
  normalized = default

print(",".join(normalized))
PY
}

is_app_installed() {
  local app_name="$1"
  osascript -e "id of application \"${app_name}\"" >/dev/null 2>&1
}

join_with_slash() {
  local -a items=("$@")
  if [[ "${#items[@]}" -eq 0 ]]; then
    printf '%s' ""
    return 0
  fi
  local joined="${items[0]}"
  local idx
  for ((idx=1; idx<${#items[@]}; idx++)); do
    joined+="/${items[idx]}"
  done
  printf '%s' "${joined}"
}

ensure_config() {
  if [[ ! -f "${CONFIG_PATH}" ]]; then
    echo "[error] config.json not found at ${CONFIG_PATH}" >&2
    exit 1
  fi
}

ensure_monitor() {
  if [[ ! -f "${MONITOR_PATH}" ]]; then
    echo "[error] monitor_tabs.py not found at ${MONITOR_PATH}" >&2
    exit 1
  fi
}

load_mode_summary() {
  ensure_config
  CONFIG_PATH="${CONFIG_PATH}" python3 - <<'PY'
import json
import os

config_path = os.environ["CONFIG_PATH"]
with open(config_path, "r", encoding="utf-8") as fh:
  data = json.load(fh) or {}

dry_run = bool(data.get("dryRun", True))
policy = str(data.get("dryRunPolicy", "manual")).strip().lower()
if policy not in {"manual", "auto"}:
  policy = "manual"
mode = "dump-only" if dry_run else "dump-close"
print(("true" if dry_run else "false") + " " + policy + " " + mode)
PY
}

set_mode_values() {
  local dry_run_value="$1"
  local policy_value="$2"
  ensure_config
  CONFIG_PATH="${CONFIG_PATH}" \
  DRY_RUN_VALUE="${dry_run_value}" \
  DRY_RUN_POLICY="${policy_value}" \
  python3 - <<'PY'
import json
import os
import stat

config_path = os.environ["CONFIG_PATH"]
dry_run_value = os.environ["DRY_RUN_VALUE"].strip().lower()
policy_value = os.environ["DRY_RUN_POLICY"].strip().lower()

if dry_run_value not in {"true", "false"}:
  raise SystemExit(f"invalid dryRun value: {dry_run_value}")
if policy_value not in {"manual", "auto"}:
  raise SystemExit(f"invalid dryRunPolicy value: {policy_value}")

with open(config_path, "r", encoding="utf-8") as fh:
  data = json.load(fh) or {}

data["dryRun"] = dry_run_value == "true"
data["dryRunPolicy"] = policy_value

with open(config_path, "w", encoding="utf-8") as fh:
  json.dump(data, fh, indent=2)
  fh.write("\n")

os.chmod(config_path, stat.S_IRUSR | stat.S_IWUSR)
PY
}

mode_show_cmd() {
  local dry_run policy mode
  read -r dry_run policy mode <<< "$(load_mode_summary)"
  echo "mode=${mode}, dryRun=${dry_run}, dryRunPolicy=${policy}"
  if [[ "${policy}" == "auto" && "${dry_run}" == "true" ]]; then
    echo "🧪 Auto mode is in onboarding: after the first clean dump, TabDump switches to dump+close."
  fi
}

mode_cmd() {
  local subcmd="${1:-show}"
  local dry_run policy mode
  case "${subcmd}" in
    show)
      mode_show_cmd
      ;;
    dump-only)
      set_mode_values "true" "manual"
      echo "🧪 Dump-only enabled. Notes are saved, tabs stay open."
      ;;
    dump-close)
      set_mode_values "false" "manual"
      echo "⚠️ Dump+Close enabled. Non-allowlisted/non-pinned tabs may be closed."
      ;;
    auto)
      read -r dry_run policy mode <<< "$(load_mode_summary)"
      if [[ "${dry_run}" == "true" ]]; then
        set_mode_values "true" "auto"
        echo "🧪 Auto mode enabled. Starts in dump-only, then switches to dump+close after first clean dump."
      else
        set_mode_values "false" "auto"
        echo "⚠️ Auto mode enabled while current mode remains dump+close."
      fi
      ;;
    *)
      echo "[error] Unknown mode: ${subcmd}" >&2
      echo "Usage: tabdump mode [show|dump-only|dump-close|auto]" >&2
      exit 1
      ;;
  esac
}

reload_launch_agent_if_present() {
  local uid_num target
  uid_num="$(id -u)"
  target="gui/${uid_num}"

  if [[ ! -f "${LAUNCH_AGENT_PATH}" ]]; then
    echo "[warn] Launch agent plist not found at ${LAUNCH_AGENT_PATH}. Skipping reload."
    return 0
  fi

  launchctl bootout "${target}" "${LAUNCH_AGENT_PATH}" >/dev/null 2>&1 || true
  if ! launchctl bootstrap "${target}" "${LAUNCH_AGENT_PATH}" >/dev/null 2>&1; then
    echo "[warn] Failed to bootstrap launch agent after config update." >&2
    return 0
  fi
  launchctl enable "${target}/${LAUNCH_LABEL}" >/dev/null 2>&1 || true
  launchctl kickstart -k "${target}/${LAUNCH_LABEL}" >/dev/null 2>&1 || true
  echo "[ok] Reloaded launch agent to apply schedule changes."
}

config_show_cmd() {
  ensure_config
  CONFIG_PATH="${CONFIG_PATH}" python3 - <<'PY'
import json
import os
from pathlib import Path

config_path = Path(os.environ["CONFIG_PATH"]).expanduser()
with open(config_path, "r", encoding="utf-8") as fh:
  data = json.load(fh) or {}

def bool_txt(value, default=False):
  return "true" if bool(value if value is not None else default) else "false"

browsers = data.get("browsers", [])
if isinstance(browsers, list):
  browsers_out = ",".join(str(item).strip() for item in browsers if str(item).strip())
else:
  browsers_out = ""

print("TabDump config")
print(f"path={config_path}")
print(f"vaultInbox={data.get('vaultInbox', '')}")
print(f"browsers={browsers_out}")
print(f"dryRun={bool_txt(data.get('dryRun', True), True)}")
print(f"dryRunPolicy={str(data.get('dryRunPolicy', 'manual')).strip().lower() or 'manual'}")
print(f"maxTabs={int(data.get('maxTabs', 30))}")
print(f"checkEveryMinutes={int(data.get('checkEveryMinutes', 60))}")
print(f"cooldownMinutes={int(data.get('cooldownMinutes', 1440))}")
print(f"llmEnabled={bool_txt(data.get('llmEnabled', False), False)}")
print(f"tagModel={str(data.get('tagModel', 'gpt-4.1-mini'))}")
print(f"llmRedact={bool_txt(data.get('llmRedact', True), True)}")
print(f"llmRedactQuery={bool_txt(data.get('llmRedactQuery', True), True)}")
print(f"llmTitleMax={int(data.get('llmTitleMax', 200))}")
print(f"maxItems={int(data.get('maxItems', 0))}")
print(f"docsMoreLinksGroupingMode={str(data.get('docsMoreLinksGroupingMode', 'kind')).strip().lower() or 'kind'}")
PY
}

config_get_cmd() {
  local key="${1:-}"
  if [[ -z "${key}" ]]; then
    echo "[error] Usage: tabdump config get <key>" >&2
    return 1
  fi
  ensure_config
  CONFIG_PATH="${CONFIG_PATH}" CONFIG_KEY="${key}" python3 - <<'PY'
import json
import os
import sys

config_path = os.environ["CONFIG_PATH"]
key = os.environ["CONFIG_KEY"].strip()
supported = {
  "vaultInbox",
  "browsers",
  "dryRun",
  "dryRunPolicy",
  "maxTabs",
  "checkEveryMinutes",
  "cooldownMinutes",
  "llmEnabled",
  "tagModel",
  "llmRedact",
  "llmRedactQuery",
  "llmTitleMax",
  "maxItems",
  "docsMoreLinksGroupingMode",
}
if key not in supported:
  print(f"Unsupported config key: {key}", file=sys.stderr)
  raise SystemExit(1)

with open(config_path, "r", encoding="utf-8") as fh:
  data = json.load(fh) or {}

value = data.get(key)
if key == "browsers":
  if isinstance(value, list):
    print(",".join(str(item).strip() for item in value if str(item).strip()))
  else:
    print("")
elif isinstance(value, bool):
  print("true" if value else "false")
elif value is None:
  print("")
else:
  print(str(value))
PY
}

config_set_cmd() {
  ensure_config
  if [[ "$#" -lt 2 || $(( $# % 2 )) -ne 0 ]]; then
    echo "[error] Usage: tabdump config set <key> <value> [<key> <value> ...]" >&2
    return 1
  fi

  local reload_needed=0
  local key
  local idx=1
  while [[ "${idx}" -le "$#" ]]; do
    key="${!idx}"
    if [[ "${key}" == "checkEveryMinutes" ]]; then
      reload_needed=1
    fi
    idx=$((idx + 2))
  done

  if ! CONFIG_PATH="${CONFIG_PATH}" python3 - "$@" <<'PY'
import json
import os
import stat
import sys

config_path = os.environ["CONFIG_PATH"]
args = sys.argv[1:]

with open(config_path, "r", encoding="utf-8") as fh:
  data = json.load(fh) or {}

mapping = {"chrome": "Chrome", "safari": "Safari", "firefox": "Firefox"}

def parse_bool(raw: str) -> bool:
  value = raw.strip().lower()
  if value in {"1", "true", "yes", "y", "on"}:
    return True
  if value in {"0", "false", "no", "n", "off"}:
    return False
  raise ValueError("expected boolean")

def parse_nonneg_int(raw: str) -> int:
  value = raw.strip()
  if not value.isdigit():
    raise ValueError("expected non-negative integer")
  return int(value)

updated = []
try:
  for i in range(0, len(args), 2):
    key = args[i].strip()
    raw = args[i + 1]

    if key == "vaultInbox":
      out = os.path.abspath(os.path.expanduser(raw.strip()))
      if not out:
        raise ValueError("vaultInbox cannot be empty")
      if not out.endswith(os.sep):
        out += os.sep
      data[key] = out
    elif key == "browsers":
      parts = [item.strip() for item in raw.split(",") if item.strip()]
      normalized = []
      seen = set()
      for part in parts:
        val = mapping.get(part.lower())
        if not val:
          raise ValueError(f"invalid browser: {part}")
        if val in seen:
          continue
        seen.add(val)
        normalized.append(val)
      if not normalized:
        raise ValueError("browsers cannot be empty")
      data[key] = normalized
    elif key in {"dryRun", "llmEnabled", "llmRedact", "llmRedactQuery", "keepPinnedTabs", "outputGroupByWindow", "outputIncludeMetadata"}:
      data[key] = parse_bool(raw)
    elif key == "dryRunPolicy":
      policy = raw.strip().lower()
      if policy not in {"manual", "auto"}:
        raise ValueError("dryRunPolicy must be manual or auto")
      data[key] = policy
    elif key in {"maxTabs", "checkEveryMinutes", "cooldownMinutes", "maxItems"}:
      data[key] = parse_nonneg_int(raw)
    elif key == "llmTitleMax":
      value = parse_nonneg_int(raw)
      if value < 1:
        raise ValueError("llmTitleMax must be >= 1")
      data[key] = value
    elif key == "docsMoreLinksGroupingMode":
      mode = raw.strip().lower()
      if mode not in {"kind", "energy"}:
        raise ValueError("docsMoreLinksGroupingMode must be kind or energy")
      data[key] = mode
    elif key in {"tagModel", "outputFilenameTemplate"}:
      value = raw.strip()
      if not value:
        raise ValueError(f"{key} cannot be empty")
      data[key] = value
    else:
      raise ValueError(f"unsupported config key: {key}")
    updated.append(key)
except ValueError as exc:
  print(str(exc), file=sys.stderr)
  raise SystemExit(1)

with open(config_path, "w", encoding="utf-8") as fh:
  json.dump(data, fh, indent=2)
  fh.write("\n")
os.chmod(config_path, stat.S_IRUSR | stat.S_IWUSR)

print("[ok] Updated config keys: " + ", ".join(updated))
PY
  then
    return 1
  fi

  if [[ "${reload_needed}" -eq 1 ]]; then
    reload_launch_agent_if_present
  fi
}

config_cmd() {
  local subcmd="${1:-show}"
  case "${subcmd}" in
    show)
      config_show_cmd
      ;;
    get)
      shift || true
      config_get_cmd "${1:-}"
      ;;
    set)
      shift || true
      config_set_cmd "$@"
      ;;
    help|-h|--help)
      cat <<'USAGE'
Usage:
  tabdump config show
  tabdump config get <key>
  tabdump config set <key> <value> [<key> <value> ...]
USAGE
      ;;
    *)
      echo "[error] Unknown config command: ${subcmd}" >&2
      echo "Usage: tabdump config [show|get <key>|set <key> <value> ...]" >&2
      return 1
      ;;
  esac
}

read_json_field() {
  local payload="$1"
  local field="$2"
  MONITOR_JSON="${payload}" MONITOR_FIELD="${field}" python3 - <<'PY'
import json
import os

payload = os.environ.get("MONITOR_JSON", "")
field = os.environ.get("MONITOR_FIELD", "")
try:
  data = json.loads(payload)
except Exception:
  print("")
  raise SystemExit(0)
value = data.get(field, "")
if value is None:
  value = ""
print(str(value))
PY
}

run_monitor_json() {
  local mode_arg="$1"
  local output
  if ! output="$(python3 "${MONITOR_PATH}" --force --mode "${mode_arg}" --json 2>&1)"; then
    echo "[error] monitor_tabs failed: ${output}" >&2
    return 1
  fi
  echo "${output}"
}

count_cmd() {
  local want_json=0
  local arg
  local monitor_json
  local status
  local tab_count
  local reason

  while [[ "$#" -gt 0 ]]; do
    arg="$1"
    case "${arg}" in
      --json)
        want_json=1
        ;;
      -h|--help)
        echo "Usage: tabdump count [--json]"
        return 0
        ;;
      *)
        echo "[error] Unknown option for tabdump count: ${arg}" >&2
        echo "Usage: tabdump count [--json]" >&2
        return 1
        ;;
    esac
    shift
  done

  ensure_config
  ensure_monitor

  if ! monitor_json="$(run_monitor_json "count")"; then
    return 1
  fi
  if [[ "${want_json}" -eq 1 ]]; then
    echo "${monitor_json}"
    return 0
  fi

  status="$(read_json_field "${monitor_json}" "status")"
  tab_count="$(read_json_field "${monitor_json}" "tabCount")"
  reason="$(read_json_field "${monitor_json}" "reason")"

  if [[ "${status}" == "ok" && "${tab_count}" =~ ^[0-9]+$ ]]; then
    echo "${tab_count}"
    return 0
  fi

  if [[ -z "${reason}" ]]; then
    reason="unknown"
  fi
  echo "[error] Failed to count tabs (${reason})." >&2
  return 1
}

now_cmd() {
  local mode_arg="dump-only"
  local want_json=0
  local arg
  local monitor_json
  local status
  local clean_note
  local reason

  while [[ "$#" -gt 0 ]]; do
    arg="$1"
    case "${arg}" in
      --close)
        mode_arg="dump-close"
        ;;
      --json)
        want_json=1
        ;;
      -h|--help)
        echo "Usage: tabdump now [--close] [--json]"
        return 0
        ;;
      *)
        echo "[error] Unknown option for tabdump now: ${arg}" >&2
        echo "Usage: tabdump now [--close] [--json]" >&2
        return 1
        ;;
    esac
    shift
  done

  ensure_config
  ensure_monitor

  if ! monitor_json="$(run_monitor_json "${mode_arg}")"; then
    return 1
  fi
  if [[ "${want_json}" -eq 1 ]]; then
    echo "${monitor_json}"
    return 0
  fi

  status="$(read_json_field "${monitor_json}" "status")"
  clean_note="$(read_json_field "${monitor_json}" "cleanNote")"
  reason="$(read_json_field "${monitor_json}" "reason")"

  if [[ "${status}" == "ok" && -n "${clean_note}" ]]; then
    echo "[ok] Clean dump: ${clean_note}"
    return 0
  fi

  if [[ -z "${reason}" ]]; then
    reason="unknown"
  fi
  if [[ "${status}" == "noop" ]]; then
    echo "[info] No clean dump produced (${reason})."
    return 0
  fi

  echo "[error] No clean dump produced (${reason})." >&2
  return 1
}

permissions_cmd() {
  local monitor_json
  local status
  local reason
  local clean_note
  local browsers_csv
  local old_ifs
  local -a browsers=()
  local -a installed=()
  local -a missing=()
  local browser
  local app_name
  local installed_label
  local missing_label

  ensure_config
  ensure_monitor
  echo "[info] Running a safe permissions check (forced dump-only; tabs will not be closed)."
  if ! monitor_json="$(run_monitor_json "dump-only")"; then
    return 1
  fi
  status="$(read_json_field "${monitor_json}" "status")"
  reason="$(read_json_field "${monitor_json}" "reason")"
  clean_note="$(read_json_field "${monitor_json}" "cleanNote")"
  if [[ "${status}" == "ok" && -n "${clean_note}" ]]; then
    echo "[ok] Permissions check produced clean dump: ${clean_note}"
  elif [[ "${status}" == "noop" ]]; then
    if [[ -z "${reason}" ]]; then
      reason="noop"
    fi
    echo "[info] Permissions check completed (${reason})."
  else
    if [[ -z "${status}" ]]; then
      status="unknown"
    fi
    if [[ -z "${reason}" ]]; then
      reason="unknown"
    fi
    echo "[warn] Permissions check returned status=${status} reason=${reason}."
  fi

  browsers_csv="$(load_browsers_csv)"
  old_ifs="${IFS}"
  IFS=',' read -r -a browsers <<< "${browsers_csv}"
  IFS="${old_ifs}"

  for browser in "${browsers[@]}"; do
    [[ -z "${browser}" ]] && continue
    app_name="$(browser_app_name "${browser}")"
    if [[ -z "${app_name}" ]]; then
      continue
    fi
    if is_app_installed "${app_name}"; then
      installed+=("${browser}")
    else
      missing+=("${browser}")
      echo "[warn] ${browser} is configured but not installed. Skipping."
    fi
  done

  if [[ "${#installed[@]}" -eq 0 ]]; then
    echo "[info] If prompts do not appear, open:"
    echo "  System Settings -> Privacy & Security -> Automation -> TabDump"
    if [[ "${#missing[@]}" -gt 0 ]]; then
      missing_label="$(join_with_slash "${missing[@]}")"
      echo "[warn] Configured but missing browsers: ${missing_label}"
    fi
    return 0
  fi

  installed_label="$(join_with_slash "${installed[@]}")"
  echo "[info] If prompts do not appear, open:"
  echo "  System Settings -> Privacy & Security -> Automation -> TabDump -> ${installed_label}"
  echo "[info] Keep these browsers running when triggering permissions."
  if [[ "${#missing[@]}" -gt 0 ]]; then
    missing_label="$(join_with_slash "${missing[@]}")"
    echo "[warn] Configured but missing browsers: ${missing_label}"
  fi
}

status_cmd() {
  local status_payload
  local uid_num
  local service
  local launch_output
  local run_state
  local last_exit
  local out_log
  local err_log

  ensure_config
  out_log="${LOG_DIR}/monitor.out.log"
  err_log="${LOG_DIR}/monitor.err.log"

  echo "TabDump status"
  echo "- config: ${CONFIG_PATH}"

  status_payload="$(
    CONFIG_PATH="${CONFIG_PATH}" MONITOR_STATE_PATH="${MONITOR_STATE_PATH}" LEGACY_STATE_PATH="${LEGACY_STATE_PATH}" python3 - <<'PY'
import json
import os
from datetime import datetime
from pathlib import Path


def load_json(path_str: str) -> dict:
    path = Path(path_str).expanduser()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


cfg_path = Path(os.environ["CONFIG_PATH"]).expanduser()
monitor_state_path = Path(os.environ["MONITOR_STATE_PATH"]).expanduser()
legacy_state_path = Path(os.environ["LEGACY_STATE_PATH"]).expanduser()

cfg = load_json(str(cfg_path))
monitor_state = load_json(str(monitor_state_path))
legacy_state = load_json(str(legacy_state_path))

dry_run = bool(cfg.get("dryRun", True))
mode = "dump-only" if dry_run else "dump-close"
policy = str(cfg.get("dryRunPolicy", "manual")).strip().lower()
if policy not in {"manual", "auto"}:
    policy = "manual"

print(f"- mode: {mode} (dryRun={'true' if dry_run else 'false'}, dryRunPolicy={policy})")
print(
    "- gates: "
    f"checkEveryMinutes={cfg.get('checkEveryMinutes', 'n/a')}, "
    f"cooldownMinutes={cfg.get('cooldownMinutes', 'n/a')}, "
    f"maxTabs={cfg.get('maxTabs', 'n/a')}"
)

browsers = cfg.get("browsers", [])
if isinstance(browsers, list):
    browsers_out = ", ".join(str(item) for item in browsers if str(item).strip())
else:
    browsers_out = ""
if not browsers_out:
    browsers_out = "n/a"
print(f"- browsers: {browsers_out}")

print(f"- monitor state: {monitor_state_path}")
print(f"  lastStatus={monitor_state.get('lastStatus', '-')}")
print(f"  lastReason={monitor_state.get('lastReason', '-')}")
print(f"  lastResultAt={monitor_state.get('lastResultAt', '-')}")
print(f"  lastProcessed={monitor_state.get('lastProcessed', '-')}")
print(f"  lastClean={monitor_state.get('lastClean', '-')}")
print(f"  lastCount={monitor_state.get('lastCount', '-')}")
last_count_at = monitor_state.get("lastCountAt", "-")
print(f"  lastCountAt={last_count_at}")
try:
    if last_count_at not in {"-", "", None}:
        print(f"  lastCountAtIso={datetime.fromtimestamp(float(last_count_at)).isoformat(sep=' ', timespec='seconds')}")
except Exception:
    pass

print(f"- app state (legacy self-gating): {legacy_state_path}")
print(f"  lastCheck={legacy_state.get('lastCheck', '-')}")
print(f"  lastDump={legacy_state.get('lastDump', '-')}")
print(f"  lastTabs={legacy_state.get('lastTabs', '-')}")
PY
  )"
  printf '%s\n' "${status_payload}"

  uid_num="$(id -u)"
  service="gui/${uid_num}/${LAUNCH_LABEL}"
  if launch_output="$(launchctl print "${service}" 2>/dev/null)"; then
    run_state="$(printf '%s\n' "${launch_output}" | awk -F'= ' '/^[[:space:]]*state = / {print $2; exit}')"
    last_exit="$(printf '%s\n' "${launch_output}" | awk -F'= ' '/^[[:space:]]*last exit code = / {print $2; exit}')"
    echo "- launch agent: loaded (${service})"
    if [[ -n "${run_state}" ]]; then
      echo "  state=${run_state}"
    fi
    if [[ -n "${last_exit}" ]]; then
      echo "  last_exit=${last_exit}"
    fi
  else
    echo "- launch agent: not loaded (${service})"
  fi

  echo "- log tail: ${out_log}"
  if [[ -f "${out_log}" ]]; then
    tail -n 8 "${out_log}" | sed 's/^/  /'
  else
    echo "  (missing)"
  fi
  echo "- log tail: ${err_log}"
  if [[ -f "${err_log}" ]]; then
    tail -n 8 "${err_log}" | sed 's/^/  /'
  else
    echo "  (missing)"
  fi
}

cmd="${1:-run}"
case "${cmd}" in
  init)
    shift || true
    init_cmd "$@"
    ;;
  uninstall)
    shift || true
    uninstall_cmd "$@"
    ;;
  run|open)
    open_tabdump
    ;;
  now)
    shift || true
    now_cmd "$@"
    ;;
  count)
    shift || true
    count_cmd "$@"
    ;;
  mode)
    mode_cmd "${2:-show}"
    ;;
  config)
    shift || true
    config_cmd "$@"
    ;;
  status)
    status_cmd
    ;;
  permissions)
    permissions_cmd
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "[error] Unknown command: ${cmd}" >&2
    usage >&2
    exit 1
    ;;
esac
EOF
  chmod +x "${CLI_PATH}"
}

write_launch_agent() {
  local start_interval
  start_interval="$(CONFIG_PATH="${CONFIG_PATH}" python3 - <<'PY'
import json
import os

config_path = os.environ["CONFIG_PATH"]
with open(config_path, "r", encoding="utf-8") as fh:
    data = json.load(fh)
minutes = int(data.get("checkEveryMinutes", 60))
if minutes < 1:
    minutes = 1
print(minutes * 60)
PY
)"

  cat > "${LAUNCH_AGENT_PATH}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LAUNCH_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${MONITOR_WRAPPER_DEST}</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>TABDUMP_KEYCHAIN_SERVICE</key>
    <string>${KEYCHAIN_SERVICE}</string>
    <key>TABDUMP_KEYCHAIN_ACCOUNT</key>
    <string>${KEYCHAIN_ACCOUNT}</string>
  </dict>
  <key>StartInterval</key>
  <integer>${start_interval}</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/monitor.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/monitor.err.log</string>
</dict>
</plist>
PLIST

  chmod 600 "${LAUNCH_AGENT_PATH}"
}

bootstrap_launch_agent() {
  local uid_num target bootout_output bootstrap_output enable_output kickstart_output
  uid_num="$(id -u)"
  target="gui/${uid_num}"

  if bootout_output="$(launchctl bootout "${target}" "${LAUNCH_AGENT_PATH}" 2>&1)"; then
    print_ok "Stopped existing launch agent (if any)."
  else
    case "${bootout_output}" in
      *"Boot-out failed: 5:"*|*"No such process"*|*"Could not find service"*)
        print_ok "No existing launch agent to stop."
        ;;
      *)
        print_warn "launchctl bootout reported: ${bootout_output}"
        ;;
    esac
  fi

  if ! bootstrap_output="$(launchctl bootstrap "${target}" "${LAUNCH_AGENT_PATH}" 2>&1)"; then
    die "launchctl bootstrap failed for ${LAUNCH_AGENT_PATH}: ${bootstrap_output}"
  fi
  print_ok "Bootstrapped launch agent."

  if ! enable_output="$(launchctl enable "${target}/${LAUNCH_LABEL}" 2>&1)"; then
    die "launchctl enable failed for ${LAUNCH_LABEL}: ${enable_output}"
  fi
  print_ok "Enabled launch agent."

  if kickstart_output="$(launchctl kickstart -k "${target}/${LAUNCH_LABEL}" 2>&1)"; then
    print_ok "Kickstarted launch agent."
  else
    print_warn "launchctl kickstart reported: ${kickstart_output}"
  fi
}

print_summary() {
  echo
  echo "Wrote config:     ${CONFIG_PATH}"
  echo "Vault Inbox:      ${VAULT_INBOX}"
  echo "Browsers:         ${BROWSERS_CSV}"
  echo "Gates:            checkEveryMinutes=${CHECK_EVERY_MINUTES_VALUE}, cooldownMinutes=${COOLDOWN_MINUTES_VALUE}, maxTabs=${MAX_TABS_VALUE}"
  echo "Installed engine: ${ENGINE_DEST}"
  echo "Installed monitor:${MONITOR_DEST}"
  echo "Installed wrapper:${MONITOR_WRAPPER_DEST}"
  echo "Installed app:    ${APP_PATH}"
  echo "Bundle id:        ${BUNDLE_ID}"
  echo "Installed CLI:    ${CLI_PATH}"
  echo "Installed job:    ${LAUNCH_AGENT_PATH}"
  echo
  echo "Quick start:"
  echo "  tabdump status"
  echo "  tabdump config show"
  echo "  tabdump mode show"
  echo "  tabdump count"
  echo "  tabdump now"
  echo "  tabdump now --close"
  echo "  tabdump permissions   # safe: forced dump-only, no tab closing"
  echo
  echo "Modes:"
  echo "  🧪 dump-only  (dryRun=true): writes raw+clean notes and keeps tabs open."
  echo "  ⚠️ dump+close (dryRun=false): may close non-allowlisted/non-pinned tabs."
  if [[ "${DRY_RUN_VALUE}" == "true" ]]; then
    echo "  Auto mode is enabled by default and will switch to dump+close after the first clean dump."
  fi
  echo
  echo "If Automation prompts do not reappear, reset with:"
  echo "  tccutil reset AppleEvents ${BUNDLE_ID}"
  echo
  echo "To reload the job after changing checkEveryMinutes:"
  echo "  launchctl bootout gui/$(id -u) ${LAUNCH_AGENT_PATH}"
  echo "  launchctl bootstrap gui/$(id -u) ${LAUNCH_AGENT_PATH}"

  if [[ "${#WARNINGS[@]}" -gt 0 ]]; then
    echo
    echo "Warnings:"
    local warning
    for warning in "${WARNINGS[@]}"; do
      echo "  - ${warning}"
    done
  fi
}

main() {
  parse_args "$@"
  enforce_option_combinations

  echo "TabDump installer"

  step "Preflight checks"
  require_cmd python3
  require_cmd shasum
  require_cmd tar
  require_cmd security
  require_cmd launchctl
  PYTHON_BIN="$(command -v python3)"
  verify_runtime_manifest
  print_ok "Preflight checks passed."

  step "Collect install choices"
  collect_install_choices
  warn_missing_browsers
  print_ok "Install options resolved."

  step "Prepare directories"
  prepare_directories
  print_ok "Prepared runtime directories."

  step "Install runtime files"
  install_runtime_files
  print_ok "Copied runtime files."

  step "Write config"
  write_config
  print_ok "Wrote config.json."

  step "Configure LLM key mode"
  configure_llm_key_mode

  step "Install app and CLI"
  build_app_and_cli
  configure_cli_path
  print_ok "Installed prebuilt app bundle and CLI shim."

  step "Install launch agent"
  write_launch_agent
  bootstrap_launch_agent

  step "Summary"
  print_summary
}

main "$@"
