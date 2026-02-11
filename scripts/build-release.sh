#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE_SOURCE="${ROOT_DIR}/macos/configurable-tabDump.scpt"
BUNDLE_ID="io.orc-visioner.tabdump"

VERSION=""
OUTPUT_DIR="${ROOT_DIR}/dist"
CODESIGN_IDENTITY="${TABDUMP_CODESIGN_IDENTITY:--}"
SKIP_CODESIGN=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/build-release.sh --version <version> [options]

Options:
  --version <version>              Required. Release version (example: v1.2.3).
  --output-dir <path>              Output directory (default: ./dist).
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

parse_args() {
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --version)
        require_value "$1" "${2:-}"
        VERSION="$2"
        shift 2
        ;;
      --output-dir)
        require_value "$1" "${2:-}"
        OUTPUT_DIR="$2"
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

normalize_output_dir() {
  OUTPUT_DIR_RAW="${OUTPUT_DIR}" python3 - <<'PY'
import os
import sys

raw = os.environ.get("OUTPUT_DIR_RAW", "").strip()
if not raw:
    sys.exit(1)
print(os.path.abspath(os.path.expanduser(raw)))
PY
}

main() {
  parse_args "$@"

  if [[ -z "${VERSION}" ]]; then
    echo "[error] --version is required." >&2
    usage >&2
    exit 1
  fi

  require_cmd osacompile
  require_cmd python3
  require_cmd tar
  require_cmd shasum
  if [[ "${SKIP_CODESIGN}" -eq 0 ]]; then
    require_cmd codesign
  fi

  OUTPUT_DIR="$(normalize_output_dir)"
  mkdir -p "${OUTPUT_DIR}"

  local build_root app_path plist_path archive_versioned archive_default checksum_path
  build_root="$(mktemp -d "${TMPDIR:-/tmp}/tabdump-release.XXXXXX")"
  app_path="${build_root}/TabDump.app"
  plist_path="${app_path}/Contents/Info.plist"
  archive_versioned="${OUTPUT_DIR}/tabdump-app-${VERSION}.tar.gz"
  archive_default="${OUTPUT_DIR}/tabdump-app.tar.gz"
  checksum_path="${archive_versioned}.sha256"

  echo "[info] Building TabDump.app for ${VERSION}"
  osacompile -o "${app_path}" "${ENGINE_SOURCE}"

  APP_PLIST="${plist_path}" \
  BUNDLE_ID="${BUNDLE_ID}" \
  VERSION="${VERSION}" \
  python3 - <<'PY'
import os
import plistlib

plist_path = os.environ["APP_PLIST"]
bundle_id = os.environ["BUNDLE_ID"]
version = os.environ["VERSION"]
bundle_version = version[1:] if version.startswith("v") else version

with open(plist_path, "rb") as fh:
    data = plistlib.load(fh)

data["CFBundleIdentifier"] = bundle_id
data["CFBundleShortVersionString"] = bundle_version
data["CFBundleVersion"] = bundle_version

with open(plist_path, "wb") as fh:
    plistlib.dump(data, fh)
PY

  if [[ "${SKIP_CODESIGN}" -eq 0 ]]; then
    echo "[info] Signing app with identity: ${CODESIGN_IDENTITY}"
    codesign --force --deep --sign "${CODESIGN_IDENTITY}" "${app_path}"
  else
    echo "[warn] Skipping codesign (--no-codesign)."
  fi

  echo "[info] Packaging prebuilt app archive"
  tar -czf "${archive_versioned}" -C "${build_root}" "TabDump.app"
  cp -f "${archive_versioned}" "${archive_default}"
  (cd "${OUTPUT_DIR}" && shasum -a 256 "$(basename "${archive_versioned}")" > "$(basename "${checksum_path}")")

  rm -rf "${build_root}"

  echo "[ok] Built archive: ${archive_versioned}"
  echo "[ok] Updated installer default archive: ${archive_default}"
  echo "[ok] Checksum: ${checksum_path}"
}

main "$@"
