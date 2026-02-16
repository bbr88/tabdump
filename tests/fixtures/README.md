# Test Fixtures Layout

Fixtures are grouped by test domain to avoid a flat, hard-to-maintain file list.

## Structure

- `renderer/core/`
  - canonical payload + golden expected output used by renderer contract tests.
- `renderer/title_cleanup/`
  - cases for title normalization (e.g., YouTube/GitHub cleanup).
- `renderer/admin/`
  - admin/auth classification edge cases.
- `renderer/docs/`
  - docs-section rendering and denoise scenarios.
- `renderer/quickwins/`
  - quick-wins bucketing/scoring scenarios.
- `classifier_eval/`
  - generic 24-case gold benchmark and frozen LLM prediction fixtures for classifier comparison tests.

## Conventions

1. Keep paired artifacts (`.json` input + `.md` expected output) in the same category folder.
2. Use descriptive, scenario-oriented names.
3. When adding new test domains, create a top-level folder under `tests/fixtures/` instead of mixing files into existing categories.
4. Classifier eval fixtures:
   - keep `gold_generic_v1.json` as the source-of-truth label set;
   - keep `llm_predictions_frozen_v1.json` deterministic for CI;
   - refresh frozen predictions only via opt-in live runs (`TABDUMP_LIVE_LLM_EVAL=1 TABDUMP_REFRESH_LLM_FIXTURES=1`).
