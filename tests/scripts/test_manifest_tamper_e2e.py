import os
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = ROOT_DIR / "scripts" / "install.sh"


def _write_stub(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _prepare_minimal_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    scripts_dir = root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    script_copy = scripts_dir / "install.sh"
    script_copy.write_text(INSTALL_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    script_copy.chmod(0o755)

    # Deliberately incorrect checksum for an existing tracked file.
    (scripts_dir / "runtime-manifest.sha256").write_text(
        "0000000000000000000000000000000000000000000000000000000000000000  scripts/install.sh\n",
        encoding="utf-8",
    )
    return root


def _install_stubs(bin_dir: Path) -> None:
    _write_stub(
        bin_dir,
        "shasum",
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$#" -eq 4 && "$1" == "-a" && "$2" == "256" && "$3" == "-c" ]]; then
  manifest="$4"
  python3 - "$manifest" <<'PY'
import hashlib
import os
import sys

manifest = sys.argv[1]
ok = True
with open(manifest, "r", encoding="utf-8") as fh:
    for line in fh:
        line = line.rstrip("\\n")
        if not line:
            continue
        expected, rel = line.split("  ", 1)
        with open(rel, "rb") as f:
            actual = hashlib.sha256(f.read()).hexdigest()
        if actual == expected:
            print(f"{rel}: OK")
        else:
            print(f"{rel}: FAILED")
            ok = False
if not ok:
    sys.exit(1)
PY
  exit $?
fi
echo "unsupported shasum call: $*" >&2
exit 2
""",
    )
    _write_stub(
        bin_dir,
        "security",
        """#!/usr/bin/env bash
set -euo pipefail
exit 0
""",
    )
    _write_stub(
        bin_dir,
        "launchctl",
        """#!/usr/bin/env bash
set -euo pipefail
exit 0
""",
    )


def test_install_fails_closed_when_manifest_tampered(tmp_path):
    root = _prepare_minimal_root(tmp_path)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    _install_stubs(fake_bin)

    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["PATH"] = f"{fake_bin}:{env['PATH']}"

    proc = subprocess.run(
        ["bash", str(root / "scripts" / "install.sh")],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    output = proc.stdout + proc.stderr
    assert proc.returncode == 1
    assert "scripts/install.sh: FAILED" in output
    assert "Runtime manifest verification failed. Aborting install." in output
