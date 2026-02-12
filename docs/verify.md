# TabDump Verification Guide

## Scope
This document describes how to verify:
1. Release tag signature
2. Artifact checksum integrity
3. Artifact signature authenticity

## 1) Verify Release Tag Signature
Verify the signed annotated tag locally:

```bash
git fetch --tags
git tag -v vX.Y.Z
```

Expected:
- Signature verification succeeds.
- Tag points to the intended release commit.

## 2) Verify Artifact Checksum
Download release assets for the tag:

```bash
gh release download vX.Y.Z \
  -p "tabdump-app-vX.Y.Z.tar.gz" \
  -p "tabdump-app-vX.Y.Z.tar.gz.sha256" \
  -p "tabdump-homebrew-vX.Y.Z.tar.gz" \
  -p "tabdump-homebrew-vX.Y.Z.tar.gz.sha256" \
  -D /tmp/tabdump-verify
```

Verify checksum:

```bash
cd /tmp/tabdump-verify
shasum -a 256 -c tabdump-app-vX.Y.Z.tar.gz.sha256
shasum -a 256 -c tabdump-homebrew-vX.Y.Z.tar.gz.sha256
```

Expected:
- `tabdump-app-vX.Y.Z.tar.gz: OK`
- `tabdump-homebrew-vX.Y.Z.tar.gz: OK`

## 3) Verify Artifact Signature (`.sig`)
Create an allowed signers file with the published release signing key:

```bash
cat > /tmp/tabdump-verify/allowed_signers <<'EOF'
tabdump-release-signing ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDPdAPr5A+78p73lIXJ0csNUlcmSZVGFmTpox7SCqBBI
EOF
```

Verify signature:

```bash
cd /tmp/tabdump-verify
ssh-keygen -Y verify \
  -f allowed_signers \
  -I tabdump-release-signing \
  -n file \
  -s tabdump-app-vX.Y.Z.tar.gz.sig < tabdump-app-vX.Y.Z.tar.gz

ssh-keygen -Y verify \
  -f allowed_signers \
  -I tabdump-release-signing \
  -n file \
  -s tabdump-homebrew-vX.Y.Z.tar.gz.sig < tabdump-homebrew-vX.Y.Z.tar.gz
```

Expected:
- `Good "file" signature for tabdump-release-signing ...`

## Failure Handling
If any verification step fails:
1. Do not install the artifact.
2. Check that tag/version and filenames match exactly.
3. Re-download assets from the release page.
4. If failure persists, treat as a potential supply-chain incident.
