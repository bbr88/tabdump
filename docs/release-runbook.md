# TabDump Release Runbook

## Purpose
Single release guide for versioning, publishing, verification, and Homebrew promotion.

## Preconditions
1. `main` protections and required CI checks are enabled.
2. Release workflow is green on `main`.
3. Tap CI is green in `bbr88/homebrew-tap`.
4. Release secrets are configured.

## Required Secrets
Set in `Settings -> Secrets and variables -> Actions`:

1. `RELEASE_TAG_ALLOWED_SIGNERS`
2. `RELEASE_ARTIFACT_SIGNING_KEY`
3. `RELEASE_CODESIGN_IDENTITY` (optional)

## Versioning Rules
1. Use semver tags: `vMAJOR.MINOR.PATCH`.
2. Tags must be annotated and signed.
3. Tag must point to merged `main`.
4. Artifact names must include exact version:
   - `tabdump-app-vX.Y.Z.tar.gz`
   - `tabdump-app-vX.Y.Z.tar.gz.sha256`
   - `tabdump-app-vX.Y.Z.tar.gz.sig`
   - `tabdump-homebrew-vX.Y.Z.tar.gz`
   - `tabdump-homebrew-vX.Y.Z.tar.gz.sha256`
   - `tabdump-homebrew-vX.Y.Z.tar.gz.sig`
   - `tabdump-openclaw-skill-vX.Y.Z.tar.gz`
   - `tabdump-openclaw-skill-vX.Y.Z.tar.gz.sha256`
   - `tabdump-openclaw-skill-vX.Y.Z.tar.gz.sig`
5. If `scripts/runtime-manifest.sha256` changes, it must be release-scoped and rationale must be documented in the PR.

## Release Flow

### A) Prepare Release PR
1. Create branch `release/vX.Y.Z`.
2. Update code/docs/changelog for `vX.Y.Z`.
3. If manifest changed, run:
   - `scripts/update-runtime-manifest.sh update`
   - add PR label `release-manifest`
4. Get PR checks green and approvals.

### B) Tag and Publish
1. Merge release PR.
2. Create and push signed tag:
   - `git tag -s vX.Y.Z -m "Release vX.Y.Z"`
   - `git push origin vX.Y.Z`
3. Confirm `release.yml` publishes all artifacts listed above.

### C) Verify Published Artifacts
Use this public key for artifact signature verification:

`ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDPdAPr5A+78p73lIXJ0csNUlcmSZVGFmTpox7SCqBBI tabdump-release-signing`

1. Verify tag signature:
   - `git fetch --tags`
   - `git tag -v vX.Y.Z`
2. Download assets:
   - `gh release download vX.Y.Z -p "tabdump-app-vX.Y.Z.tar.gz" -p "tabdump-app-vX.Y.Z.tar.gz.sha256" -p "tabdump-app-vX.Y.Z.tar.gz.sig" -p "tabdump-homebrew-vX.Y.Z.tar.gz" -p "tabdump-homebrew-vX.Y.Z.tar.gz.sha256" -p "tabdump-homebrew-vX.Y.Z.tar.gz.sig" -p "tabdump-openclaw-skill-vX.Y.Z.tar.gz" -p "tabdump-openclaw-skill-vX.Y.Z.tar.gz.sha256" -p "tabdump-openclaw-skill-vX.Y.Z.tar.gz.sig" -D /tmp/tabdump-verify`
3. Verify checksums:
   - `cd /tmp/tabdump-verify`
   - `shasum -a 256 -c tabdump-app-vX.Y.Z.tar.gz.sha256`
   - `shasum -a 256 -c tabdump-homebrew-vX.Y.Z.tar.gz.sha256`
   - `shasum -a 256 -c tabdump-openclaw-skill-vX.Y.Z.tar.gz.sha256`
4. Verify signatures:
   - `cat > allowed_signers <<'EOF'`
   - `tabdump-release-signing ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDPdAPr5A+78p73lIXJ0csNUlcmSZVGFmTpox7SCqBBI`
   - `EOF`
   - `ssh-keygen -Y verify -f allowed_signers -I tabdump-release-signing -n file -s tabdump-app-vX.Y.Z.tar.gz.sig < tabdump-app-vX.Y.Z.tar.gz`
   - `ssh-keygen -Y verify -f allowed_signers -I tabdump-release-signing -n file -s tabdump-homebrew-vX.Y.Z.tar.gz.sig < tabdump-homebrew-vX.Y.Z.tar.gz`
   - `ssh-keygen -Y verify -f allowed_signers -I tabdump-release-signing -n file -s tabdump-openclaw-skill-vX.Y.Z.tar.gz.sig < tabdump-openclaw-skill-vX.Y.Z.tar.gz`

### D) Update Homebrew Tap
Source of truth: `bbr88/homebrew-tap`, `Formula/tabdump.rb`.

1. Create tap branch: `bump/vX.Y.Z`.
2. Bump formula from release:
   - `scripts/bump-tabdump-formula.sh --tag vX.Y.Z --from-release`
3. Merge tap PR after tap CI is green.
4. Smoke test:
   - `brew update`
   - `brew install bbr88/tap/tabdump` (or `brew upgrade tabdump`)
   - `tabdump init --yes --vault-inbox ~/obsidian/Inbox/`
   - `tabdump status`

## Post-Release Checklist
1. Validate one-shot run and service behavior on a clean machine.
2. Validate uninstall:
   - `tabdump uninstall --yes --remove-config --purge`
   - `brew uninstall tabdump`
3. Record release audit data:
   - tag
   - checksums
   - signature verification result
   - tap formula commit
   - rollback target tag

## Rollback
1. Repoint tap formula to previous known-good version+sha.
2. Publish incident note with scope and mitigation.
3. Ship signed patch release.
