# TabDump Homebrew Shipping Plan

## Goal
Make TabDump fully shippable via Homebrew with verifiable release provenance, pinned immutable artifacts, and release-governed manifest integrity.

## Current State Summary
- Installer and runtime hardening exist (runtime manifest verification, restrictive permissions).
- No Homebrew formula/cask/tap exists in this repository.
- No release/tag signing workflow exists.
- Install flow currently compiles app on end-user machine (`osacompile`), which prevents immutable artifact pinning.

## Definition of Done (Fully Shippable)
1. Homebrew package installs and upgrades successfully on clean macOS runners.
2. Installation consumes immutable release artifacts only (no end-user app compilation).
3. Release tags are signed and verified in CI.
4. Release artifacts are signed and include published checksums.
5. Homebrew formula/cask pins `sha256` to release artifacts.
6. Runtime manifest changes are restricted to release-controlled changes.
7. CI blocks any violation of the above.

## Recommended Packaging Decision
Use **Homebrew Formula** as the primary distribution model.

Rationale:
- Primary interface is CLI (`tabdump`) and scheduled execution.
- Service lifecycle maps to Homebrew `service do` + launchd.
- `.app` can remain an internal runtime asset rather than a user-facing install target.

## Implementation Phases

### Phase 0: Baseline and Policy (Day 0-1)
Deliverables:
- `docs/release-policy.md`
- `docs/release-runbook.md` (outline)
- SemVer/tag convention (`vX.Y.Z`)

Tasks:
1. Freeze public install contract (`tabdump` CLI + service behavior).
2. Define release roles/approvals and required checks.
3. Define rollback procedure for broken release/tap update.

Acceptance criteria:
- Policy docs approved by maintainers.

### Phase 1: Build/Install Separation (Day 1-3)
Deliverables:
- `scripts/build-release.sh` (CI build pipeline script)
- `scripts/install-runtime.sh` (runtime/setup only)
- Updated `scripts/install.sh` wrapper or deprecation note

Tasks:
1. Remove production-path `osacompile` from end-user install flow.
2. Keep install logic focused on config, launch agent/service, and runtime file placement.
3. Keep local developer build in separate script (`build-local` path).

Acceptance criteria:
- User install path does not compile/sign app.
- Existing install tests updated and passing.

### Phase 2: Signed Immutable Release Artifacts (Day 3-5)
Deliverables:
- GitHub Actions workflow: `.github/workflows/release.yml`
- Release assets per version:
  - `TabDump-<version>-macos.tar.gz` (or `.zip`)
  - `TabDump-<version>-macos.sha256`
  - `TabDump-<version>-macos.sig`

Tasks:
1. Build artifact in CI from tagged commit.
2. Sign artifact and produce detached signature.
3. Publish checksums and signatures with release assets.
4. Ensure artifact content is deterministic and versioned.

Acceptance criteria:
- Every release contains artifact + checksum + signature.

### Phase 3: Signed Tags and Verification (Day 5-6)
Deliverables:
- Tag verification job in CI (`verify-tag-signature`)
- `docs/verify.md` with commands for maintainers/users

Tasks:
1. Require signed annotated tags for release branch/tag events.
2. Verify tag signature before building/publishing assets.
3. Fail release workflow if signature verification fails.

Acceptance criteria:
- Unsigned/invalid tags cannot produce a release.

### Phase 4: Homebrew Distribution (Day 6-8)
Deliverables:
- Tap repository (recommended): `orc-visioner/homebrew-tap`
- Formula: `Formula/tabdump.rb`

Tasks:
1. Reference immutable release asset URL in formula.
2. Pin `sha256` to released artifact checksum.
3. Install CLI into `bin`; place runtime assets under `libexec`.
4. Add `service do` block for periodic monitor execution.
5. Add `test do` to validate `tabdump --help` and basic non-destructive behavior.

Acceptance criteria:
- `brew install orc-visioner/tap/tabdump` succeeds on clean macOS CI.
- `brew upgrade` and `brew uninstall` succeed.

### Phase 5: Manifest Governance Controls (Day 8-9)
Deliverables:
- CI policy workflow: `.github/workflows/policy-manifest.yml`
- `CODEOWNERS` rules for installer/release/manifest paths

Tasks:
1. Restrict `scripts/runtime-manifest.sha256` changes to release PRs only.
2. Enforce owner approval for:
   - `scripts/install*.sh`
   - `scripts/update-runtime-manifest.sh`
   - `scripts/runtime-manifest.sha256`
   - release workflows and formula files
3. Require explicit release label/branch for manifest updates.

Acceptance criteria:
- Non-release PRs modifying manifest fail policy checks.

### Phase 6: CI Hardening and Tests (Day 9-10)
Deliverables:
- `.github/workflows/ci.yml`
- Additional tests for tamper detection and packaging checks

Tasks:
1. Add tamper E2E test:
   - modify tracked runtime file
   - assert installer fails on manifest verification
2. Add guard check preventing `osacompile` in production install path.
3. Add shell linting and style checks for scripts.
4. Add formula lint/test in tap CI.

Acceptance criteria:
- Required checks are green before merge/release.

### Phase 7: Dry Run and Launch (Day 10-12)
Deliverables:
- Dry run report (internal)
- First production Homebrew release

Tasks:
1. Perform full dry run: signed tag -> release artifact -> tap update -> brew install.
2. Validate install/start/one-shot/uninstall flows on clean host.
3. Publish release notes with verification instructions.

Acceptance criteria:
- Two consecutive successful dry runs.
- First public release shipped and installable.

## Security Controls Mapping (Requested)

### 1) Sign releases/tags and verify signatures in distribution
Implementation:
- Signed annotated git tags required for release.
- CI blocks unsigned/invalid tags.
- Release artifact signature (`.sig`) published and verified in release checks.

### 2) Pin Homebrew formula checksums to signed release artifacts
Implementation:
- Formula points to immutable versioned asset URL.
- Formula `sha256` equals published release checksum.
- Formula updates are release-coupled; no floating/latest URLs.

### 3) Treat manifest updates as release-controlled changes only
Implementation:
- Manifest path protected by CI policy and CODEOWNERS.
- Manifest regeneration allowed only in release PRs.
- Manifest verification stays fail-closed in installer.

## Risk Register (Top)
1. **Ad-hoc local signing path remains in production installer**
   - Mitigation: remove from production path; keep dev-only build script.
2. **Tap drift from release artifacts**
   - Mitigation: automate formula bump from release metadata; require CI verification.
3. **Manifest churn in feature PRs**
   - Mitigation: policy gate + owner approval + release-only label.

## Execution Checklist
- [ ] Approve formula-first distribution model.
- [ ] Implement build/install split.
- [ ] Implement signed release workflow.
- [ ] Create tap and formula with pinned checksum.
- [ ] Add manifest governance policy gates.
- [ ] Add CI/package/security checks.
- [ ] Run two complete dry runs.
- [ ] Ship v1 Homebrew release.
