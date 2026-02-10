# TabDump Release Runbook

## Purpose
Operational checklist to ship a Homebrew-ready TabDump release safely.

## Preconditions
1. GitHub repository is configured.
2. Default branch protections are enabled.
3. Release workflow and CI workflows are green on default branch.
4. Signing key is configured for release publisher.

## Inputs
- Target version (example: `v1.2.0`)
- Release notes/changelog entries
- Expected artifact names

## Phase A: Prepare Release PR
1. Create branch `release/vX.Y.Z`.
2. Update versioned metadata per `docs/versioning.md`.
3. Update changelog/release notes draft.
4. If runtime manifest changes:
   - regenerate manifest
   - include rationale in PR
5. Run full CI and required tests.
6. Obtain required approvals.

## Phase B: Tag and Publish
1. Merge release PR.
2. Create annotated signed tag:
   - `git tag -s vX.Y.Z -m "Release vX.Y.Z"`
3. Push tag:
   - `git push origin vX.Y.Z`
4. Confirm CI tag verification passes.
5. Confirm release workflow publishes:
   - `TabDump-vX.Y.Z-*.tar.gz|zip`
   - `.sha256`
   - `.sig`

## Phase C: Verify Published Artifacts
1. Verify artifact checksum equals published `.sha256`.
2. Verify artifact signature using project public key.
3. Ensure artifact names include exact version.
4. Confirm assets are attached to the correct release tag.

## Phase D: Homebrew Update
1. Update formula URL to `vX.Y.Z` artifact.
2. Update formula `sha256` to published checksum.
3. Run formula lint/tests in tap CI.
4. Merge tap PR.
5. Validate clean install:
   - `brew update`
   - `brew install <tap>/tabdump`
   - `tabdump --help`

## Phase E: Post-Release Validation
1. Validate one-shot command on clean host.
2. Validate service start/stop behavior.
3. Validate uninstall path.
4. Record release audit fields:
   - tag, checksum, signature result, formula commit, rollback tag.

## Rollback Procedure
Trigger rollback if release is broken or compromised.

1. Stop promoting latest release in docs/tap.
2. Repoint Homebrew formula to previous known-good version and checksum.
3. Publish incident note with scope and mitigation.
4. Prepare and ship signed patch release.

## Quick Commands (Template)
```bash
# Create and push signed tag
git tag -s vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z

# Verify tag locally
git tag -v vX.Y.Z

# Homebrew smoke checks
brew update
brew install <tap>/tabdump
tabdump --help
```

## Exit Criteria
- Signed tag verified
- Assets published with checksum/signature
- Tap updated with matching sha256
- Fresh install and smoke tests pass
- Audit record completed
