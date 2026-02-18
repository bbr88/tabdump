#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
TabDump Homebrew install helper (print-only).
Copy/paste the commands below.

LLM-enabled setup (default):
  brew tap bbr88/tap
  brew install tabdump
  tabdump init --yes --vault-inbox ~/obsidian/Inbox --enable-llm true --key-mode keychain
  tabdump status
  tabdump logs --lines 30
  tabdump now

No-LLM setup (optional):
  brew tap bbr88/tap
  brew install tabdump
  tabdump init --yes --vault-inbox ~/obsidian/Inbox
  tabdump status
  tabdump logs --lines 30
  tabdump now
EOF
