#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE_SOURCE="${ROOT_DIR}/macos/configurable-tabDump.scpt"
APP_OUTPUT="${HOME}/Applications/TabDump.app"
BUNDLE_ID="io.orc-visioner.tabdump"
CODESIGN_IDENTITY="${TABDUMP_CODESIGN_IDENTITY:--}"
SKIP_CODESIGN=0
VERSION=""

usage() {
  cat <<'USAGE'
Usage:
  scripts/build-local.sh [options]

Options:
  --output <path>                  Output .app path (default: ~/Applications/TabDump.app).
  --bundle-id <id>                 CFBundleIdentifier (default: io.orc-visioner.tabdump).
  --version <version>              Optional bundle version (example: 1.2.3 or v1.2.3).
  --codesign-identity <identity>   codesign identity (default: - for ad-hoc).
  --no-codesign                    Skip codesign step.
  -h, --help                       Show this help.
USAGE
}

require_value() {
  local option="$1"
  local value="${2:-}"
  if [[ -z "${value}" || "${value}" == --* ]]; then
    echo "[error] Option ${option} requires a value." >&2
    exit 1
  fi
}

require_cmd() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "[error] Required command not found on PATH: ${command_name}" >&2
    exit 1
  fi
}

normalize_path() {
  INPUT_PATH_RAW="$1" python3 - <<'PY'
import os
import sys

raw = os.environ.get("INPUT_PATH_RAW", "").strip()
if not raw:
    sys.exit(1)
print(os.path.abspath(os.path.expanduser(raw)))
PY
}

parse_args() {
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --output)
        require_value "$1" "${2:-}"
        APP_OUTPUT="$2"
        shift 2
        ;;
      --bundle-id)
        require_value "$1" "${2:-}"
        BUNDLE_ID="$2"
        shift 2
        ;;
      --version)
        require_value "$1" "${2:-}"
        VERSION="$2"
        shift 2
        ;;
      --codesign-identity)
        require_value "$1" "${2:-}"
        CODESIGN_IDENTITY="$2"
        shift 2
        ;;
      --no-codesign)
        SKIP_CODESIGN=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "[error] Unknown option: $1" >&2
        usage >&2
        exit 1
        ;;
    esac
  done
}

main() {
  parse_args "$@"

  require_cmd osacompile
  require_cmd python3
  if [[ "${SKIP_CODESIGN}" -eq 0 ]]; then
    require_cmd codesign
  fi

  APP_OUTPUT="$(normalize_path "${APP_OUTPUT}")"
  mkdir -p "$(dirname "${APP_OUTPUT}")"

  if [[ -d "${APP_OUTPUT}" ]]; then
    rm -rf "${APP_OUTPUT}"
  fi

  echo "[info] Building local app: ${APP_OUTPUT}"
  osacompile -o "${APP_OUTPUT}" "${ENGINE_SOURCE}"

  APP_PLIST="${APP_OUTPUT}/Contents/Info.plist" \
  BUNDLE_ID="${BUNDLE_ID}" \
  VERSION="${VERSION}" \
  python3 - <<'PY'
import os
import plistlib

plist_path = os.environ["APP_PLIST"]
bundle_id = os.environ["BUNDLE_ID"]
version = os.environ.get("VERSION", "").strip()
bundle_version = version[1:] if version.startswith("v") else version

with open(plist_path, "rb") as fh:
    data = plistlib.load(fh)

data["CFBundleIdentifier"] = bundle_id
if bundle_version:
    data["CFBundleShortVersionString"] = bundle_version
    data["CFBundleVersion"] = bundle_version

with open(plist_path, "wb") as fh:
    plistlib.dump(data, fh)
PY

  if [[ "${SKIP_CODESIGN}" -eq 0 ]]; then
    echo "[info] Signing local app with identity: ${CODESIGN_IDENTITY}"
    codesign --force --deep --sign "${CODESIGN_IDENTITY}" "${APP_OUTPUT}"
  else
    echo "[warn] Skipping codesign (--no-codesign)."
  fi

  echo "[ok] Local app build complete: ${APP_OUTPUT}"
}

main "$@"
