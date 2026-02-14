# macos Scripts

This folder contains AppleScript sources used by TabDump.

- `configurable-tabDump.scpt`: production engine used by build/install/release scripts.
- `standalone-tabDump-template.scpt`: manual, no-install template for ad-hoc local use.

Notes:
- The standalone template is safe by default (`closeDumpedTabs=false`).
- Runtime configuration example JSON lives at `docs/examples/config.example.json`.
