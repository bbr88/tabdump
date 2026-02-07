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
MONITOR_SOURCE="${CORE_DIR}/monitor_tabs.py"
POSTPROCESS_SOURCE="${CORE_DIR}/postprocess_tabdump.py"
MONITOR_DEST="${CONFIG_DIR}/monitor_tabs.py"
POSTPROCESS_DEST="${CONFIG_DIR}/postprocess_tabdump.py"
CORE_PKG_DEST="${CONFIG_DIR}/core"
RENDERER_DEST_DIR="${CORE_PKG_DEST}/renderer"
APP_PATH="${HOME}/Applications/TabDump.app"
BUNDLE_ID="io.orc-visioner.tabdump"
BIN_DIR="${HOME}/.local/bin"
CLI_PATH="${BIN_DIR}/tabdump"
LAUNCH_AGENT_DIR="${HOME}/Library/LaunchAgents"
LAUNCH_LABEL="io.orc-visioner.tabdump.monitor"
LAUNCH_AGENT_PATH="${LAUNCH_AGENT_DIR}/${LAUNCH_LABEL}.plist"
LOG_DIR="${CONFIG_DIR}/logs"
PYTHON_BIN="$(command -v python3 || true)"
KEYCHAIN_SERVICE="${TABDUMP_KEYCHAIN_SERVICE:-TabDump}"
KEYCHAIN_ACCOUNT="${TABDUMP_KEYCHAIN_ACCOUNT:-openai}"

verify_runtime_manifest() {
  if [[ ! -f "${MANIFEST_PATH}" ]]; then
    echo "Runtime manifest not found: ${MANIFEST_PATH}"
    exit 1
  fi
  if ! command -v shasum >/dev/null 2>&1; then
    echo "shasum is required to verify runtime manifest integrity."
    exit 1
  fi
  if ! (cd "${ROOT_DIR}" && shasum -a 256 -c "${MANIFEST_PATH}"); then
    echo "Runtime manifest verification failed. Aborting install."
    exit 1
  fi
}

echo "TabDump installer"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "python3 not found on PATH. Please install Python 3 and retry."
  exit 1
fi
verify_runtime_manifest

echo "This will create/update:"
echo "  - ${ENGINE_DEST}"
echo "  - ${MONITOR_DEST}"
echo "  - ${POSTPROCESS_DEST}"
echo "  - ${CONFIG_PATH}"
echo "  - ${APP_PATH}"
echo "  - ${CLI_PATH}"
echo "  - ${LAUNCH_AGENT_PATH}"
echo "  - Python: ${PYTHON_BIN}"
echo

read -r -p "Vault Inbox path (required): " VAULT_INBOX_RAW
if [[ -z "${VAULT_INBOX_RAW}" ]]; then
  echo "Vault Inbox path is required."
  exit 1
fi

VAULT_INBOX="$(VAULT_INBOX_RAW="${VAULT_INBOX_RAW}" python3 - <<'PY'
import os, sys
p = os.environ["VAULT_INBOX_RAW"].strip()
if not p:
  sys.exit(1)
p = os.path.expanduser(p)
p = os.path.abspath(p)
if not p.endswith(os.sep):
  p += os.sep
print(p)
PY
)" || {
  echo "Vault Inbox path is required."
  exit 1
}

mkdir -p "${VAULT_INBOX}"
mkdir -p "${CONFIG_DIR}"
mkdir -p "${RENDERER_DEST_DIR}"
mkdir -p "${LOG_DIR}"
mkdir -p "$(dirname "${APP_PATH}")"
mkdir -p "${BIN_DIR}"
mkdir -p "${LAUNCH_AGENT_DIR}"

cp -f "${ENGINE_SOURCE}" "${ENGINE_DEST}"
cp -f "${MONITOR_SOURCE}" "${MONITOR_DEST}"
cp -f "${POSTPROCESS_SOURCE}" "${POSTPROCESS_DEST}"
cp -f "${CORE_DIR}/__init__.py" "${CORE_PKG_DEST}/__init__.py"
cp -f "${RENDERER_DIR}"/*.py "${RENDERER_DEST_DIR}/"
chmod 700 "${CONFIG_DIR}" "${CORE_PKG_DEST}" "${RENDERER_DEST_DIR}" "${LOG_DIR}"
chmod 600 "${ENGINE_DEST}" "${MONITOR_DEST}" "${POSTPROCESS_DEST}" "${CORE_PKG_DEST}/__init__.py"
chmod 600 "${RENDERER_DEST_DIR}"/*.py

VAULT_INBOX="${VAULT_INBOX}" CONFIG_PATH="${CONFIG_PATH}" python3 - <<'PY'
import json, os

vault_inbox = os.environ["VAULT_INBOX"]
config_path = os.environ["CONFIG_PATH"]

data = {
  "vaultInbox": vault_inbox,
  "outputFilenameTemplate": "TabDump {ts}.md",
  "browsers": ["Chrome", "Safari"],
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
  "dryRun": True,
  "maxTabs": 30,
  "checkEveryMinutes": 5,
  "cooldownMinutes": 30,
  "tagModel": "gpt-4.1-mini",
  "llmRedact": True,
  "llmRedactQuery": True,
  "llmTitleMax": 200,
  "maxItems": 0
}

with open(config_path, "w", encoding="utf-8") as f:
  json.dump(data, f, indent=2)
  f.write("\n")
PY
chmod 600 "${CONFIG_PATH}"

read -r -p "Set dryRun=false now? (y/N): " SET_DRY_RUN
if [[ "${SET_DRY_RUN}" == "y" || "${SET_DRY_RUN}" == "Y" ]]; then
  CONFIG_PATH="${CONFIG_PATH}" python3 - <<'PY'
import json, os
config_path = os.environ["CONFIG_PATH"]
with open(config_path, "r", encoding="utf-8") as f:
  data = json.load(f)
data["dryRun"] = False
with open(config_path, "w", encoding="utf-8") as f:
  json.dump(data, f, indent=2)
  f.write("\n")
PY
fi

echo
echo "LLM tagging requires an OpenAI API key."
echo "Choose storage:"
echo "  1) Keychain (recommended)"
echo "  2) I'll set OPENAI_API_KEY myself (env fallback)"
echo "  3) Skip for now"
read -r -p "Select [1-3] (default 1): " KEY_CHOICE
if [[ -z "${KEY_CHOICE}" ]]; then
  KEY_CHOICE="1"
fi

case "${KEY_CHOICE}" in
  1)
    echo ""
    echo "OpenAI key setup (Keychain)"
    echo "Paste your OpenAI API key (input hidden), then press Enter:"
    read -rs OPENAI_API_KEY_INPUT
    echo ""
    if [[ -n "${OPENAI_API_KEY_INPUT}" ]]; then
      if security find-generic-password -s "${KEYCHAIN_SERVICE}" -a "${KEYCHAIN_ACCOUNT}" >/dev/null 2>&1; then
        read -r -p "Keychain item exists for service=${KEYCHAIN_SERVICE}, account=${KEYCHAIN_ACCOUNT}. Replace? (y/N): " REPLACE_KEY
        if [[ "${REPLACE_KEY}" == "y" || "${REPLACE_KEY}" == "Y" ]]; then
          security add-generic-password -s "${KEYCHAIN_SERVICE}" -a "${KEYCHAIN_ACCOUNT}" -w "${OPENAI_API_KEY_INPUT}" -U >/dev/null
          echo "✅ Stored OpenAI key in Keychain (service=${KEYCHAIN_SERVICE}, account=${KEYCHAIN_ACCOUNT})"
        else
          echo "ℹ️  Kept existing Keychain item."
        fi
      else
        security add-generic-password -s "${KEYCHAIN_SERVICE}" -a "${KEYCHAIN_ACCOUNT}" -w "${OPENAI_API_KEY_INPUT}" >/dev/null
        echo "✅ Stored OpenAI key in Keychain (service=${KEYCHAIN_SERVICE}, account=${KEYCHAIN_ACCOUNT})"
      fi
      echo "   To read it later:"
      echo "   security find-generic-password -s \"${KEYCHAIN_SERVICE}\" -a \"${KEYCHAIN_ACCOUNT}\" -w"
    else
      echo "ℹ️  Skipped (empty input)"
    fi
    ;;
  2)
    echo ""
    echo "ℹ️  Skipping key storage."
    echo "   Set OPENAI_API_KEY in your environment before running."
    echo "   (Runtime resolution order is Keychain, then OPENAI_API_KEY env var.)"
    if security find-generic-password -s "${KEYCHAIN_SERVICE}" -a "${KEYCHAIN_ACCOUNT}" >/dev/null 2>&1; then
      echo "ℹ️  Note: a Keychain item exists and will take precedence over env vars."
      read -r -p "Delete existing Keychain item? (y/N): " DELETE_KEYCHAIN
      if [[ "${DELETE_KEYCHAIN}" == "y" || "${DELETE_KEYCHAIN}" == "Y" ]]; then
        security delete-generic-password -s "${KEYCHAIN_SERVICE}" -a "${KEYCHAIN_ACCOUNT}" >/dev/null 2>&1 || true
        echo "✅ Deleted Keychain item."
      else
        echo "ℹ️  Keeping Keychain item; it will be used first."
      fi
    fi
    ;;
  3)
    echo ""
    echo "ℹ️  Skipping OpenAI key setup."
    ;;
  *)
    echo ""
    echo "ℹ️  Invalid choice; skipping OpenAI key setup."
    ;;
esac

echo
echo "Wrote config: ${CONFIG_PATH}"
echo "Vault Inbox:  ${VAULT_INBOX}"

START_INTERVAL="$(CONFIG_PATH="${CONFIG_PATH}" python3 - <<'PY'
import json, os
p = os.environ["CONFIG_PATH"]
with open(p, "r", encoding="utf-8") as f:
  data = json.load(f)
minutes = int(data.get("checkEveryMinutes", 5))
if minutes < 1:
  minutes = 1
print(minutes * 60)
PY
)"

osacompile -o "${APP_PATH}" "${ENGINE_DEST}"

PLIST_PATH="${APP_PATH}/Contents/Info.plist"
if /usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "${PLIST_PATH}" >/dev/null 2>&1; then
  /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier ${BUNDLE_ID}" "${PLIST_PATH}"
else
  /usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string ${BUNDLE_ID}" "${PLIST_PATH}"
fi

# add-hoc re-sigh step required for the TCC
codesign --force --deep --sign - "${APP_PATH}"

cat > "${CLI_PATH}" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
open "$HOME/Applications/TabDump.app"
SH
chmod +x "${CLI_PATH}"

cat > "${LAUNCH_AGENT_PATH}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LAUNCH_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>${MONITOR_DEST}</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>TABDUMP_KEYCHAIN_SERVICE</key>
    <string>${KEYCHAIN_SERVICE}</string>
    <key>TABDUMP_KEYCHAIN_ACCOUNT</key>
    <string>${KEYCHAIN_ACCOUNT}</string>
PLIST

cat >> "${LAUNCH_AGENT_PATH}" <<PLIST
  </dict>
  <key>StartInterval</key>
  <integer>${START_INTERVAL}</integer>
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

if command -v launchctl >/dev/null 2>&1; then
  set +e
  UID_NUM="$(id -u)"
  launchctl bootout "gui/${UID_NUM}" "${LAUNCH_AGENT_PATH}" >/dev/null 2>&1
  launchctl bootstrap "gui/${UID_NUM}" "${LAUNCH_AGENT_PATH}"
  launchctl enable "gui/${UID_NUM}/${LAUNCH_LABEL}" >/dev/null 2>&1
  launchctl kickstart -k "gui/${UID_NUM}/${LAUNCH_LABEL}" >/dev/null 2>&1
  set -e
fi

echo
echo "Installed engine: ${ENGINE_DEST}"
echo "Installed monitor: ${MONITOR_DEST}"
echo "Installed postprocess: ${POSTPROCESS_DEST}"
echo "Installed app:    ${APP_PATH}"
echo "Bundle id:        ${BUNDLE_ID}"
echo "Installed CLI:    ${CLI_PATH}"
echo "Installed job:    ${LAUNCH_AGENT_PATH}"
echo
echo "OpenClaw command:"
echo "  open ~/Applications/TabDump.app"
echo
echo "If Automation prompts do not reappear, reset with:"
echo "  tccutil reset AppleEvents ${BUNDLE_ID}"
echo
echo "To reload the job after changing checkEveryMinutes:"
echo "  launchctl bootout gui/$(id -u) ${LAUNCH_AGENT_PATH}"
echo "  launchctl bootstrap gui/$(id -u) ${LAUNCH_AGENT_PATH}"
