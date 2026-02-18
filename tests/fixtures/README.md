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
  - generic classifier benchmarks (v1 + v2) and frozen LLM prediction fixtures for classifier comparison tests.
- `effort_eval/`
  - domain-neutral effort benchmark fixture used by effort estimation integration tests.

## Conventions

1. Keep paired artifacts (`.json` input + `.md` expected output) in the same category folder.
2. Use descriptive, scenario-oriented names.
3. When adding new test domains, create a top-level folder under `tests/fixtures/` instead of mixing files into existing categories.
4. Classifier eval fixtures:
   - keep `gold_generic_v1.json` for backward comparability;
   - use `gold_generic_v2.json` as the primary benchmark (balanced distribution + `accepted_actions` + `rationale`);
   - keep `llm_predictions_frozen_v1.json` and `llm_predictions_frozen_v2.json` deterministic for CI;
   - refresh frozen predictions only via opt-in live runs (`TABDUMP_LIVE_LLM_EVAL=1 TABDUMP_REFRESH_LLM_FIXTURES=1`).
5. Effort eval fixtures:
   - keep `gold_effort_v1.json` generic and domain-neutral (not tied to one browsing session);
   - keep action/kind distributions balanced enough to avoid single-band collapse for `video/docs/article/repo/tool`;
   - allow `accepted_efforts` for intentionally ambiguous cases;
   - use `TABDUMP_EVAL_ENFORCE_EFFORT=1` only when intentionally enforcing strict thresholds.
