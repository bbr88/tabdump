#!/usr/bin/env bash
set -euo pipefail

BUNDLE_ID="io.orc-visioner.tabdump"

echo "[info] Resetting AppleEvents Automation permissions for: ${BUNDLE_ID}"
/usr/bin/tccutil reset AppleEvents "${BUNDLE_ID}"
echo "[ok] Reset complete. Re-run TabDump and approve prompts in System Settings -> Privacy & Security -> Automation."
