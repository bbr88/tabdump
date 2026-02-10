# TabDump Versioning

## Scheme
Use semantic versioning with a `v` prefix:
- `vMAJOR.MINOR.PATCH`

Examples:
- `v1.0.0`
- `v1.1.3`

## Increment Rules
1. **MAJOR**: breaking behavior or interface changes.
2. **MINOR**: backward-compatible feature additions.
3. **PATCH**: backward-compatible bug/security fixes.

## Release Tag Rules
1. Tags must be annotated and signed.
2. Tags must reference a commit already merged to default branch.
3. Tag name and artifact version must match exactly.

## Artifact Naming
Include version in all release artifacts.

Recommended pattern:
- `TabDump-vX.Y.Z-macos-universal.tar.gz`
- `TabDump-vX.Y.Z-macos-universal.sha256`
- `TabDump-vX.Y.Z-macos-universal.sig`

## Homebrew Mapping
- Formula version maps 1:1 to release tag version.
- Formula `sha256` maps to corresponding release artifact checksum.
- Formula updates must not point to mutable URLs.

## Manifest and Version Coupling
When `scripts/runtime-manifest.sha256` changes:
1. Treat change as release-scoped.
2. Include version bump in same PR.
3. Document rationale in PR and release notes.

## Pre-release Labels
Until stable launch, pre-releases may use:
- `vX.Y.Z-rc.N`

Rules:
1. Pre-release tags must still be signed.
2. Do not update stable Homebrew formula from RC tags.
3. RC assets should be clearly marked as prerelease.

## Changelog Requirement
Every version must have a changelog section containing:
- notable user-visible changes
- security-relevant changes
- migration/rollback notes (if any)
