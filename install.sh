#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${HOME}/Library/Application Support/TabDump"
CONFIG_PATH="${CONFIG_DIR}/config.json"
ENGINE_SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/macos/configurable-tabDump.scpt"
ENGINE_DEST="${CONFIG_DIR}/TabDump.scpt"
APP_PATH="${HOME}/Applications/TabDump.app"
BIN_DIR="${HOME}/.local/bin"
CLI_PATH="${BIN_DIR}/tabdump"

echo "TabDump installer"
echo "This will create/update:"
echo "  - ${ENGINE_DEST}"
echo "  - ${CONFIG_PATH}"
echo "  - ${APP_PATH}"
echo "  - ${CLI_PATH}"
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
mkdir -p "$(dirname "${APP_PATH}")"
mkdir -p "${BIN_DIR}"

cp -f "${ENGINE_SOURCE}" "${ENGINE_DEST}"

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
  "dryRun": True
}

with open(config_path, "w", encoding="utf-8") as f:
  json.dump(data, f, indent=2)
  f.write("\n")
PY

echo
echo "Wrote config: ${CONFIG_PATH}"
echo "Vault Inbox:  ${VAULT_INBOX}"

osacompile -o "${APP_PATH}" "${ENGINE_DEST}"

cat > "${CLI_PATH}" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
open "$HOME/Applications/TabDump.app"
SH
chmod +x "${CLI_PATH}"

echo
echo "Installed engine: ${ENGINE_DEST}"
echo "Installed app:    ${APP_PATH}"
echo "Installed CLI:    ${CLI_PATH}"
echo
echo "OpenClaw command:"
echo "  open ~/Applications/TabDump.app"
