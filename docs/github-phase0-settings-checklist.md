# GitHub Phase 0 Settings Checklist (`bbr88/tabdump`)

## Goal
Lock repository governance before release automation work starts.

## 1) Repository Basics
- [ ] Repository visibility is correct for your release plan (public recommended for Homebrew tap consumption).
- [ ] Default branch is `main`.
- [ ] Disable merge commits if you want linear history (`Squash` or `Rebase` only).
- [ ] Enable "Automatically delete head branches" after merge.

## 2) Branch Protection / Ruleset for `main`
Create a branch ruleset targeting `main`.

Required settings:
- [ ] Require a pull request before merging.
- [ ] Require at least 1 approving review.
- [ ] Dismiss stale reviews when new commits are pushed.
- [ ] Require review from Code Owners.
- [ ] Require conversation resolution before merge.
- [ ] Require status checks to pass before merging.
- [ ] Require branches to be up to date before merging.
- [ ] Block force pushes.
- [ ] Block branch deletion.

Recommended settings:
- [ ] Require signed commits (enable only if your team already signs commits consistently).
- [ ] Require linear history.

## 3) Tag Protection / Ruleset for Release Tags
Create a tag ruleset targeting `v*`.

- [ ] Restrict tag creation/update/deletion to maintainers only.
- [ ] Block tag deletion for `v*` tags.
- [ ] Require signed tags by policy (enforced in CI in Phase 3).

## 4) Access Control
- [ ] Confirm least-privilege roles for collaborators.
- [ ] Keep Admin role limited to release maintainers.
- [ ] Require 2FA for organization members (if org-owned repo).

## 5) Security Settings
In `Settings -> Security` enable:
- [ ] Dependabot alerts.
- [ ] Dependabot security updates.
- [ ] Secret scanning alerts.
- [ ] Push protection for secrets (if available in your plan).

## 6) Actions Hardening
In `Settings -> Actions -> General`:
- [ ] Allow actions: "GitHub Actions and verified creators".
- [ ] Set workflow permissions to "Read repository contents" by default.
- [ ] Enable "Allow GitHub Actions to create and approve pull requests" only if required.

## 7) Environments (Release Guardrail)
Create environment `release`.

- [ ] Required reviewers: at least 1 maintainer.
- [ ] Restrict deployment branches/tags to `v*` tags.
- [ ] Store signing/notarization secrets in this environment only (Phase 2+).

## 8) Labels (for Policy Routing)
Create labels:
- [ ] `release`
- [ ] `release-manifest`
- [ ] `security`
- [ ] `breaking-change`

Use:
- Manifest changes must include `release-manifest` label.

## 9) CODEOWNERS Baseline
Add and enforce `/Users/i.bisarnov/develop/orc-visioner/tabDump/.github/CODEOWNERS` with at least:

```text
# Release-critical paths
/scripts/install.sh @bbr88
/scripts/update-runtime-manifest.sh @bbr88
/scripts/runtime-manifest.sha256 @bbr88
/docs/release-policy.md @bbr88
/docs/release-runbook.md @bbr88
/docs/versioning.md @bbr88
/.github/workflows/* @bbr88
```

- [ ] Verify CODEOWNERS review is required by branch protection.

## 10) Release Signing Prerequisites (Phase 0 prep)
- [ ] Choose signing method for tags: GPG or SSH signing.
- [ ] Upload public signing key to GitHub account.
- [ ] Verify local setup:
  - `git tag -s v0.0.0-test -m "test"` (GPG path)
  - `git tag -v v0.0.0-test`
- [ ] Delete test tag locally/remotely after validation.

## 11) Required Checks Plan
Before enabling strict required checks, define check names that will exist:

Phase 1-2 expected checks:
- [ ] `ci / test`
- [ ] `ci / lint`
- [ ] `policy / manifest-guard`
- [ ] `release / verify-tag-signature`

Then add these checks as required in `main` branch protection.

## 12) Phase 0 Exit Criteria
- [ ] `main` protection is active and tested.
- [ ] Tag ruleset for `v*` is active.
- [ ] Security and Actions hardening settings are enabled.
- [ ] Labels created.
- [ ] CODEOWNERS enforced.
- [ ] Signing key validated with a test tag.

## Quick Verification Script (manual run)
Use this after settings are configured:

1. Open a test PR from a branch without approvals.
2. Confirm merge is blocked.
3. Add approval from code owner.
4. Confirm merge still blocked if required checks are missing/failing.
5. Attempt force-push to `main` (should be blocked).
6. Attempt delete protected tag `v0.0.0-test` (should be blocked by ruleset if configured).
