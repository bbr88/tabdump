import json
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = ROOT_DIR / "scripts" / "install.sh"
PLISTBUDDY = Path("/usr/libexec/PlistBuddy")

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin" or not PLISTBUDDY.exists(),
    reason="install.sh integration tests require macOS PlistBuddy",
)


@dataclass
class InstallRun:
    returncode: int
    stdout: str
    stderr: str
    home: Path
    log_path: Path


def _write_stub(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _install_test_stubs(bin_dir: Path) -> None:
    _write_stub(
        bin_dir,
        "shasum",
        """#!/usr/bin/env bash
set -euo pipefail
echo "shasum $*" >> "${TABDUMP_TEST_LOG:?}"
exit 0
""",
    )
    _write_stub(
        bin_dir,
        "osacompile",
        """#!/usr/bin/env bash
set -euo pipefail
echo "osacompile $*" >> "${TABDUMP_TEST_LOG:?}"
out=""
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "-o" ]]; then
    out="$2"
    shift 2
    continue
  fi
  shift
done
if [[ -z "${out}" ]]; then
  echo "missing -o output path" >&2
  exit 1
fi
mkdir -p "${out}/Contents"
cat > "${out}/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
</dict>
</plist>
PLIST
""",
    )
    _write_stub(
        bin_dir,
        "codesign",
        """#!/usr/bin/env bash
set -euo pipefail
echo "codesign $*" >> "${TABDUMP_TEST_LOG:?}"
exit 0
""",
    )
    _write_stub(
        bin_dir,
        "launchctl",
        """#!/usr/bin/env bash
set -euo pipefail
echo "launchctl $*" >> "${TABDUMP_TEST_LOG:?}"
exit 0
""",
    )
    _write_stub(
        bin_dir,
        "security",
        """#!/usr/bin/env bash
set -euo pipefail
echo "security $*" >> "${TABDUMP_TEST_LOG:?}"
if [[ "${1:-}" == "find-generic-password" ]]; then
  exit 1
fi
exit 0
""",
    )


def _run_install(tmp_path: Path, user_input: str) -> InstallRun:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    log_path = tmp_path / "command.log"
    home.mkdir()
    fake_bin.mkdir()
    _install_test_stubs(fake_bin)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["TABDUMP_TEST_LOG"] = str(log_path)

    proc = subprocess.run(
        ["bash", str(INSTALL_SCRIPT)],
        cwd=ROOT_DIR,
        env=env,
        input=user_input,
        text=True,
        capture_output=True,
        check=False,
    )
    return InstallRun(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        home=home,
        log_path=log_path,
    )


def _read_config(home: Path) -> dict:
    cfg_path = home / "Library" / "Application Support" / "TabDump" / "config.json"
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def test_install_requires_vault_inbox_path(tmp_path):
    proc = _run_install(tmp_path, "\n")
    output = proc.stdout + proc.stderr
    cfg_path = proc.home / "Library" / "Application Support" / "TabDump" / "config.json"

    assert proc.returncode == 1
    assert "Vault Inbox path is required." in output
    assert not cfg_path.exists()


def test_install_writes_default_config_and_artifacts(tmp_path):
    proc = _run_install(tmp_path, "~/vault/inbox\nn\nn\n")
    output = proc.stdout + proc.stderr
    home = proc.home
    config_dir = home / "Library" / "Application Support" / "TabDump"
    config_path = config_dir / "config.json"
    app_path = home / "Applications" / "TabDump.app"
    cli_path = home / ".local" / "bin" / "tabdump"
    plist_path = home / "Library" / "LaunchAgents" / "io.orc-visioner.tabdump.monitor.plist"

    assert proc.returncode == 0, output
    assert config_path.exists()
    assert app_path.exists()
    assert cli_path.exists()
    assert plist_path.exists()

    data = _read_config(home)
    expected_vault = (home / "vault" / "inbox").resolve()
    assert data["vaultInbox"] == f"{expected_vault}{os.sep}"
    assert data["dryRun"] is True
    assert data["llmEnabled"] is False

    assert stat.S_IMODE(config_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(config_dir.stat().st_mode) == 0o700
    assert os.access(cli_path, os.X_OK)
    assert "<integer>300</integer>" in plist_path.read_text(encoding="utf-8")

    log = proc.log_path.read_text(encoding="utf-8")
    assert "shasum -a 256 -c" in log
    assert "osacompile -o" in log
    assert "codesign --force --deep --sign -" in log


def test_install_can_enable_llm_and_disable_dry_run(tmp_path):
    proc = _run_install(tmp_path, "~/vault/inbox\ny\ny\n2\n")
    output = proc.stdout + proc.stderr
    data = _read_config(proc.home)
    log = proc.log_path.read_text(encoding="utf-8")

    assert proc.returncode == 0, output
    assert data["dryRun"] is False
    assert data["llmEnabled"] is True
    assert "security find-generic-password" in log
