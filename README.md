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

Run the live classifier comparison matrix (`local` vs `LLM`, and `LLM` vs `LLM`) against any model set.

Force **v2** gold fixture explicitly (recommended):

```bash
TABDUMP_LIVE_LLM_EVAL=1 \
TABDUMP_CLASSIFIER_GOLD_FIXTURE="/Users/i.bisarnov/develop/orc-visioner/tabDump/tests/fixtures/classifier_eval/gold_generic_v2.json" \
TABDUMP_LLM_COMPARE_MODELS="gpt-4.1-mini,gpt-4.1-nano,gpt-4o-mini,gpt-4o,gpt-5-mini,gpt-5.2" \
python3 -m pytest -q -s /Users/i.bisarnov/develop/orc-visioner/tabDump/tests/postprocess/integration/test_classifier_comparison_live.py
```

Force **v1** gold fixture explicitly (backward comparability):

```bash
TABDUMP_LIVE_LLM_EVAL=1 \
TABDUMP_CLASSIFIER_GOLD_FIXTURE="/Users/i.bisarnov/develop/orc-visioner/tabDump/tests/fixtures/classifier_eval/gold_generic_v1.json" \
TABDUMP_LLM_COMPARE_MODELS="gpt-4.1-mini,gpt-4.1,gpt-5-nano" \
python3 -m pytest -q -s /Users/i.bisarnov/develop/orc-visioner/tabDump/tests/postprocess/integration/test_classifier_comparison_live.py
```

Use any comma-separated matrix via `TABDUMP_LLM_COMPARE_MODELS`.

Enable threshold enforcement during the live run:

```bash
TABDUMP_LIVE_LLM_EVAL=1 \
TABDUMP_CLASSIFIER_GOLD_FIXTURE="/Users/i.bisarnov/develop/orc-visioner/tabDump/tests/fixtures/classifier_eval/gold_generic_v2.json" \
TABDUMP_LIVE_LLM_ENFORCE_THRESHOLDS=1 \
TABDUMP_LLM_COMPARE_MODELS="gpt-4.1-mini,gpt-4.1-nano,gpt-4o-mini,gpt-4o,gpt-5-mini,gpt-5.2" \
python3 -m pytest -q -s /Users/i.bisarnov/develop/orc-visioner/tabDump/tests/postprocess/integration/test_classifier_comparison_live.py
```

Refresh frozen fixtures from live model outputs:

```bash
TABDUMP_LIVE_LLM_EVAL=1 \
TABDUMP_CLASSIFIER_GOLD_FIXTURE="/Users/i.bisarnov/develop/orc-visioner/tabDump/tests/fixtures/classifier_eval/gold_generic_v2.json" \
TABDUMP_REFRESH_LLM_FIXTURES=1 \
TABDUMP_LLM_COMPARE_MODELS="gpt-4.1-mini,gpt-4.1,gpt-5-nano" \
python3 -m pytest -q -s /Users/i.bisarnov/develop/orc-visioner/tabDump/tests/postprocess/integration/test_classifier_comparison_live.py
```

Key runtime controls for classifier behavior:

- `TABDUMP_LLM_ACTION_POLICY`: `raw`, `derived`, or `hybrid` (default `hybrid`)
- `TABDUMP_MIN_LLM_COVERAGE`: minimum mapped non-sensitive ratio before local fallback for unmapped items (default `0.7`)
- `TABDUMP_TAG_MODEL`: primary model selector for production tagging/classification
- `TABDUMP_TAG_TEMPERATURE`: optional temperature override for LLM classification requests (`0.2` default, unset/empty to omit)
- `TABDUMP_DOCS_MORE_LINKS_GROUPING_MODE`: `domain`, `kind`, or `energy` (default `kind`)
- `TABDUMP_EFFORT_DEBUG`: optional effort diagnostics (`0/1`); prints effort band totals + top signal triggers per run

Optional effort benchmark gate:

- `TABDUMP_EVAL_ENFORCE_EFFORT`: when set to `1`, enforce effort benchmark thresholds in `tests/postprocess/integration/test_effort_estimation.py`

## Docs

- Detailed usage: `docs/user-manual.md`
- Config reference: `docs/config-reference.md`
- Release guide (runbook + verification + versioning): `docs/release-runbook.md`
- Release policy: `docs/release-policy.md`
