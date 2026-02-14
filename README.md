# TabDump

TabDump helps reduce browser tab overload on macOS by dumping tabs to Markdown notes, postprocessing into a clean note, and optionally closing tabs based on mode.

## Install (Homebrew)

```bash
brew tap bbr88/tap
brew install tabdump
tabdump init --yes --vault-inbox ~/obsidian/Inbox/
```

Sanity check:

```bash
tabdump status
tabdump now
```

## Upgrade

```bash
brew update
brew upgrade tabdump
```

## Uninstall

```bash
tabdump uninstall --yes --remove-config --purge
brew uninstall tabdump
```

## Install from Source (local/dev)

```bash
bash scripts/build-release.sh --version v0.1.0-local --output-dir dist --no-codesign
bash scripts/install.sh --yes --vault-inbox "~/obsidian/Inbox/" --app-archive "./dist/tabdump-app-v0.1.0-local.tar.gz"
```

## Core Commands

```bash
tabdump status
tabdump mode show
tabdump now
tabdump now --close
tabdump permissions
```

## Docs

- Detailed usage: `docs/user-manual.md`
- Config reference: `docs/config-reference.md`
- Release guide (runbook + verification + versioning): `docs/release-runbook.md`
- Release policy: `docs/release-policy.md`
