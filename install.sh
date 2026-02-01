#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${HOME}/Library/Application Support/TabDump"
CONFIG_PATH="${CONFIG_DIR}/config.json"

echo "TabDump installer"
echo "This will create/update: ${CONFIG_PATH}"
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
  "dryRun": False
}

with open(config_path, "w", encoding="utf-8") as f:
  json.dump(data, f, indent=2)
  f.write("\n")
PY

echo
echo "Wrote config: ${CONFIG_PATH}"
echo "Vault Inbox:  ${VAULT_INBOX}"
echo "Next: open macos/configurable-tabDump.scpt in Script Editor and run."
