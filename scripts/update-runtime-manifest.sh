#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST_PATH="${ROOT_DIR}/scripts/runtime-manifest.sha256"

TRACKED_FILES=(
  "core/monitor_tabs.py"
  "core/postprocess_tabdump.py"
  "core/postprocess/__init__.py"
  "core/postprocess/cli.py"
  "core/postprocess/classify_local.py"
  "core/postprocess/coerce.py"
  "core/postprocess/constants.py"
  "core/postprocess/llm.py"
  "core/postprocess/models.py"
  "core/postprocess/parsing.py"
  "core/postprocess/pipeline.py"
  "core/postprocess/redaction.py"
  "core/postprocess/urls.py"
  "core/renderer/renderer_v3.py"
  "macos/configurable-tabDump.scpt"
  "scripts/install.sh"
)

usage() {
  cat <<'USAGE'
Usage:
  scripts/update-runtime-manifest.sh            # regenerate manifest
  scripts/update-runtime-manifest.sh update     # regenerate manifest
  scripts/update-runtime-manifest.sh verify     # verify manifest against tracked files
USAGE
}

require_shasum() {
  if ! command -v shasum >/dev/null 2>&1; then
    echo "shasum is required but not found on PATH."
    exit 1
  fi
}

ensure_tracked_files_exist() {
  local missing=0
  local rel
  for rel in "${TRACKED_FILES[@]}"; do
    if [[ ! -f "${ROOT_DIR}/${rel}" ]]; then
      echo "Missing tracked file: ${rel}"
      missing=1
    fi
  done
  if [[ "${missing}" -ne 0 ]]; then
    exit 1
  fi
}

update_manifest() {
  require_shasum
  ensure_tracked_files_exist
  (
    cd "${ROOT_DIR}"
    shasum -a 256 "${TRACKED_FILES[@]}" > "${MANIFEST_PATH}"
  )
  echo "Updated ${MANIFEST_PATH}"
}

verify_manifest() {
  require_shasum
  if [[ ! -f "${MANIFEST_PATH}" ]]; then
    echo "Manifest not found: ${MANIFEST_PATH}"
    exit 1
  fi
  (
    cd "${ROOT_DIR}"
    shasum -a 256 -c "${MANIFEST_PATH}"
  )
}

cmd="${1:-update}"
case "${cmd}" in
  update)
    update_manifest
    ;;
  verify)
    verify_manifest
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown command: ${cmd}"
    usage
    exit 1
    ;;
esac
