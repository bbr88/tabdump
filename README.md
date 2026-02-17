# TabDump

TabDump helps reduce browser tab overload on macOS by dumping tabs to Markdown notes, postprocessing into a clean note, and optionally closing tabs based on mode.

## Install (Homebrew)

```bash
brew tap bbr88/tap
brew install tabdump
tabdump init --yes --vault-inbox ~/obsidian/Inbox --enable-llm true --key-mode keychain
```

Sanity check:

```bash
tabdump status
tabdump now
```

## Upgrade

```bash
brew update
brew upgrade tabdump
```

## Uninstall

```bash
tabdump uninstall --yes --remove-config --purge
brew uninstall tabdump
```

## Install from Source (local/dev)

```bash
bash scripts/build-release.sh --version v0.1.0-local --output-dir dist --no-codesign
bash scripts/install.sh --yes --vault-inbox "~/obsidian/Inbox/" --app-archive "./dist/tabdump-app-v0.1.0-local.tar.gz"
```

## Core Commands

```bash
tabdump status
tabdump config show
tabdump mode show
tabdump count
tabdump now
tabdump now --close
tabdump permissions
```

`tabdump count` fails with `count_unavailable` when a fresh post-launch tab count cannot be confirmed.
`tabdump count`, `tabdump now`, and `tabdump now --close` run TabDump in background/hidden mode to avoid stealing focus (except first-time permission prompts).

## OpenClaw Skill

Canonical in-repo skill bundle:

- `skills/tabdump-macos`

Build a versioned OpenClaw skill artifact:

```bash
bash scripts/build-openclaw-skill-package.sh --version v0.1.0-local --output-dir dist
```

## How To Run Live Matrix

Run the live classifier comparison matrix (`local` vs `LLM`, and `LLM` vs `LLM`) against `gpt-4.1-mini`, `gpt-4.1`, and `gpt-5-nano`:

```bash
TABDUMP_LIVE_LLM_EVAL=1 \
TABDUMP_LLM_COMPARE_MODELS="gpt-4.1-mini,gpt-4.1-nano,gpt-4o-mini,gpt-4o,gpt-5-mini,gpt-5.2" \
python3 -m pytest -q -s tests/postprocess/integration/test_classifier_comparison_live.py
```

Enable threshold enforcement during the live run:

```bash
TABDUMP_LIVE_LLM_EVAL=1 \
TABDUMP_LIVE_LLM_ENFORCE_THRESHOLDS=1 \
TABDUMP_LLM_COMPARE_MODELS="gpt-4.1-mini,gpt-4.1,gpt-5-nano" \
python3 -m pytest -q -s tests/postprocess/integration/test_classifier_comparison_live.py
```

Refresh frozen fixtures from live model outputs:

```bash
TABDUMP_LIVE_LLM_EVAL=1 \
TABDUMP_REFRESH_LLM_FIXTURES=1 \
TABDUMP_LLM_COMPARE_MODELS="gpt-4.1-mini,gpt-4.1,gpt-5-nano" \
python3 -m pytest -q -s tests/postprocess/integration/test_classifier_comparison_live.py
```

## Docs

- Detailed usage: `docs/user-manual.md`
- Config reference: `docs/config-reference.md`
- Release guide (runbook + verification + versioning): `docs/release-runbook.md`
- Release policy: `docs/release-policy.md`
