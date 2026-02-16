#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./tabdump_install_from_repo.sh /path/to/tabDump [install.sh args...]

REPO="${1:-}"
shift || true

if [[ -z "${REPO}" ]]; then
  echo "[error] Provide repo path as first argument." >&2
  exit 2
fi
if [[ ! -d "${REPO}" ]]; then
  echo "[error] Repo not found: ${REPO}" >&2
  exit 2
fi
if [[ ! -f "${REPO}/scripts/install.sh" ]]; then
  echo "[error] Expected installer at: ${REPO}/scripts/install.sh" >&2
  exit 2
fi

exec /usr/bin/env bash "${REPO}/scripts/install.sh" "$@"
