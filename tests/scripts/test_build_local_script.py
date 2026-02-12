import os
import plistlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
BUILD_LOCAL_SCRIPT = ROOT_DIR / "scripts" / "build-local.sh"


@dataclass
class BuildLocalRun:
    returncode: int
    stdout: str
    stderr: str
    home: Path
    log_path: Path


def _write_stub(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _install_stubs(bin_dir: Path, include_codesign: bool = True) -> None:
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
  <key>CFBundleIdentifier</key>
  <string>original.bundle.id</string>
</dict>
</plist>
PLIST
""",
    )
    if include_codesign:
        _write_stub(
            bin_dir,
            "codesign",
            """#!/usr/bin/env bash
set -euo pipefail
echo "codesign $*" >> "${TABDUMP_TEST_LOG:?}"
exit 0
""",
        )


def _run_build_local(
    tmp_path: Path,
    args: list[str] | None = None,
    include_codesign: bool = True,
) -> BuildLocalRun:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    log_path = tmp_path / "command.log"
    home.mkdir(exist_ok=True)
    fake_bin.mkdir(exist_ok=True)
    _install_stubs(fake_bin, include_codesign=include_codesign)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["TABDUMP_TEST_LOG"] = str(log_path)

    cmd = ["bash", str(BUILD_LOCAL_SCRIPT)]
    if args:
        cmd.extend(args)

    proc = subprocess.run(
        cmd,
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return BuildLocalRun(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        home=home,
        log_path=log_path,
    )


def _read_info_plist(app_path: Path) -> dict:
    plist_path = app_path / "Contents" / "Info.plist"
    with plist_path.open("rb") as fh:
        return plistlib.load(fh)


def test_build_local_default_output_and_codesign(tmp_path):
    proc = _run_build_local(tmp_path)
    output = proc.stdout + proc.stderr
    app_path = proc.home / "Applications" / "TabDump.app"

    assert proc.returncode == 0, output
    assert app_path.exists()

    plist = _read_info_plist(app_path)
    assert plist["CFBundleIdentifier"] == "io.orc-visioner.tabdump"

    log = proc.log_path.read_text(encoding="utf-8")
    assert "osacompile -o" in log
    assert "codesign --force --deep --sign -" in log


def test_build_local_custom_output_bundle_id_and_version_without_codesign(tmp_path):
    proc = _run_build_local(
        tmp_path,
        args=[
            "--output",
            "~/Applications/TabDumpDev.app",
            "--bundle-id",
            "io.example.tabdump.dev",
            "--version",
            "v1.2.3",
            "--no-codesign",
        ],
        include_codesign=False,
    )
    output = proc.stdout + proc.stderr
    app_path = proc.home / "Applications" / "TabDumpDev.app"

    assert proc.returncode == 0, output
    assert app_path.exists()

    plist = _read_info_plist(app_path)
    assert plist["CFBundleIdentifier"] == "io.example.tabdump.dev"
    assert plist["CFBundleShortVersionString"] == "1.2.3"
    assert plist["CFBundleVersion"] == "1.2.3"

    log = proc.log_path.read_text(encoding="utf-8")
    assert "osacompile -o" in log
    assert "codesign" not in log
