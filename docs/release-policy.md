# TabDump Release Policy

## Purpose
Define mandatory controls for shipping TabDump via Homebrew with strong provenance and predictable rollback.

## Scope
Applies to:
- Source repository releases
- Release tags and assets
- Homebrew formula updates
- Runtime manifest updates

## Release Principles
1. Every shipped version is immutable and reproducible from a signed tag.
2. Homebrew must install versioned release artifacts only.
3. Runtime manifest changes are release-controlled.
4. No end-user build steps are allowed in production distribution flow.

## Roles
- **Release Manager**: prepares candidate, coordinates release window.
- **Approver**: independent maintainer approving release PR and tag intent.
- **Publisher**: executes signed tag + release workflow.

A single person should not perform all three roles for production releases.

## Versioning
- Use semantic versioning: `vMAJOR.MINOR.PATCH`.
- Release tags must be annotated and signed.
- Patch releases are for fixes only; no behavior expansion.

## Branch and PR Requirements
1. Default branch is protected.
2. Required status checks must pass before merge.
3. At least one maintainer approval is required.
4. Release PR must include:
   - version bump
   - changelog entry
   - manifest rationale (if manifest changed)

## Tag and Artifact Requirements
1. Tags must be signed and verified in CI.
2. Release artifacts must be generated in CI from the signed tag.
3. Release must publish:
   - packaged artifact (`tabdump-app-vX.Y.Z.tar.gz`)
   - checksum file (`.sha256`)
   - signature file (`.sig`)
4. Artifact filenames must include exact version.

## Homebrew Requirements
1. Formula references versioned immutable release URL.
2. Formula `sha256` must match published checksum.
3. Formula updates are coupled to a release version.
4. No `latest` or mutable URLs are permitted.

## Manifest Governance (Mandatory)
`/scripts/runtime-manifest.sha256` is release-controlled.

Rules:
1. Manifest changes are allowed only in release PRs.
2. Manifest update must include rationale in PR description.
3. Manifest and installer paths require code owner approval.
4. CI must fail if manifest changes appear outside release-labeled PRs.

## Forbidden Patterns
1. Building app artifacts on end-user install path for production distribution.
2. Unsigned release tags.
3. Publishing artifacts outside release workflow.
4. Updating formula checksum without corresponding tagged release asset.

## Emergency Patch Procedure
1. Create hotfix branch from latest release tag.
2. Apply minimal fix + tests.
3. Open expedited PR with two maintainer approvals when possible.
4. Publish signed patch tag (`vX.Y.Z+1`) and artifacts.
5. Update Homebrew formula checksum to new patch release.

## Auditability
For each release keep:
- tag id
- artifact checksums
- signature verification result
- formula commit id
- rollback target tag

Store this in release notes or runbook records.
