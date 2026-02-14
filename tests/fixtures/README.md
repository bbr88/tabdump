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

## Conventions

1. Keep paired artifacts (`.json` input + `.md` expected output) in the same category folder.
2. Use descriptive, scenario-oriented names.
3. When adding new test domains, create a top-level folder under `tests/fixtures/` instead of mixing files into existing categories.
