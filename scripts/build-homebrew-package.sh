#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${ROOT_DIR}/dist"
VERSION=""
APP_ARCHIVE=""

usage() {
  cat <<'USAGE'
Usage:
  scripts/build-homebrew-package.sh --version <version> [options]

Options:
  --version <version>      Required. Tag/version (example: v1.2.3).
  --output-dir <path>      Output directory for package artifacts (default: ./dist).
  --app-archive <path>     Path to prebuilt app archive (default: <output-dir>/tabdump-app-<version>.tar.gz).
  -h, --help               Show this help.
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
      --app-archive)
        require_value "$1" "${2:-}"
        APP_ARCHIVE="$2"
        shift 2
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

  if [[ -z "${VERSION}" ]]; then
    echo "[error] --version is required." >&2
    usage >&2
    exit 1
  fi

  require_cmd python3
  require_cmd tar
  require_cmd shasum

  OUTPUT_DIR="$(normalize_path "${OUTPUT_DIR}")"
  mkdir -p "${OUTPUT_DIR}"

  if [[ -z "${APP_ARCHIVE}" ]]; then
    APP_ARCHIVE="${OUTPUT_DIR}/tabdump-app-${VERSION}.tar.gz"
  fi
  APP_ARCHIVE="$(normalize_path "${APP_ARCHIVE}")"

  if [[ ! -f "${APP_ARCHIVE}" ]]; then
    echo "[error] App archive not found: ${APP_ARCHIVE}" >&2
    echo "[hint] Build it first with scripts/build-release.sh --version ${VERSION}" >&2
    exit 1
  fi

  local app_archive_default
  app_archive_default="${OUTPUT_DIR}/tabdump-app.tar.gz"
  if [[ ! -f "${app_archive_default}" ]]; then
    cp -f "${APP_ARCHIVE}" "${app_archive_default}"
  fi

  local staging package_root package_archive
  staging="$(mktemp -d "${TMPDIR:-/tmp}/tabdump-homebrew.XXXXXX")"
  package_root="${staging}/package"
  package_archive="${OUTPUT_DIR}/tabdump-homebrew-${VERSION}.tar.gz"

  mkdir -p "${package_root}"
  cp -R "${ROOT_DIR}/core" "${package_root}/core"
  cp -R "${ROOT_DIR}/macos" "${package_root}/macos"
  cp -R "${ROOT_DIR}/scripts" "${package_root}/scripts"
  cp -f "${ROOT_DIR}/docs/user-manual.md" "${package_root}/USER_MANUAL.md"
  mkdir -p "${package_root}/dist"
  cp -f "${APP_ARCHIVE}" "${package_root}/dist/$(basename "${APP_ARCHIVE}")"
  cp -f "${app_archive_default}" "${package_root}/dist/$(basename "${app_archive_default}")"
  if [[ -f "${APP_ARCHIVE}.sha256" ]]; then
    cp -f "${APP_ARCHIVE}.sha256" "${package_root}/dist/$(basename "${APP_ARCHIVE}.sha256")"
  fi

  tar -czf "${package_archive}" -C "${package_root}" .
  (cd "${OUTPUT_DIR}" && shasum -a 256 "$(basename "${package_archive}")" > "$(basename "${package_archive}").sha256")
  rm -rf "${staging}"

  echo "[ok] Built Homebrew package: ${package_archive}"
  echo "[ok] Checksum: ${package_archive}.sha256"
}

main "$@"
