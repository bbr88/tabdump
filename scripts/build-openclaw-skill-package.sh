#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${ROOT_DIR}/dist"
VERSION=""
SKILL_PATH="${ROOT_DIR}/skills/tabdump-macos"

usage() {
  cat <<'USAGE'
Usage:
  scripts/build-openclaw-skill-package.sh --version <version> [options]

Options:
  --version <version>      Required. Tag/version (example: v1.2.3).
  --output-dir <path>      Output directory for package artifacts (default: ./dist).
  --skill-path <path>      Skill folder to package (default: ./skills/tabdump-macos).
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
      --skill-path)
        require_value "$1" "${2:-}"
        SKILL_PATH="$2"
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
  SKILL_PATH="$(normalize_path "${SKILL_PATH}")"

  if [[ ! -d "${SKILL_PATH}" ]]; then
    echo "[error] Skill path not found: ${SKILL_PATH}" >&2
    exit 1
  fi
  if [[ ! -f "${SKILL_PATH}/SKILL.md" ]]; then
    echo "[error] SKILL.md not found under skill path: ${SKILL_PATH}" >&2
    exit 1
  fi

  mkdir -p "${OUTPUT_DIR}"

  local staging package_archive checksum_path
  staging="$(mktemp -d "${TMPDIR:-/tmp}/tabdump-openclaw-skill.XXXXXX")"
  package_archive="${OUTPUT_DIR}/tabdump-openclaw-skill-${VERSION}.tar.gz"
  checksum_path="${package_archive}.sha256"

  cp -R "${SKILL_PATH}" "${staging}/tabdump-macos"
  tar -czf "${package_archive}" -C "${staging}" "tabdump-macos"
  (cd "${OUTPUT_DIR}" && shasum -a 256 "$(basename "${package_archive}")" > "$(basename "${checksum_path}")")
  rm -rf "${staging}"

  echo "[ok] Built OpenClaw skill package: ${package_archive}"
  echo "[ok] Checksum: ${checksum_path}"
}

main "$@"
