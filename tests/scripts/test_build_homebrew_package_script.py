import os
import subprocess
import tarfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT_DIR / "scripts" / "build-homebrew-package.sh"


def _create_fake_app_artifacts(tmp_path: Path, version: str) -> tuple[Path, Path]:
    output_dir = tmp_path / "dist"
    output_dir.mkdir(parents=True, exist_ok=True)

    versioned = output_dir / f"tabdump-app-{version}.tar.gz"
    with tarfile.open(versioned, "w:gz") as tf:
        stage = tmp_path / "stage"
        app_info = stage / "TabDump.app" / "Contents" / "Info.plist"
        app_info.parent.mkdir(parents=True, exist_ok=True)
        app_info.write_text("<plist></plist>", encoding="utf-8")
        tf.add(stage / "TabDump.app", arcname="TabDump.app")

    default_path = output_dir / "tabdump-app.tar.gz"
    default_path.write_bytes(versioned.read_bytes())
    return output_dir, versioned


def test_build_homebrew_package_contains_runtime_and_app_archive(tmp_path):
    version = "v9.9.9-test"
    output_dir, versioned_archive = _create_fake_app_artifacts(tmp_path, version)

    env = os.environ.copy()
    cmd = [
        "bash",
        str(BUILD_SCRIPT),
        "--version",
        version,
        "--output-dir",
        str(output_dir),
        "--app-archive",
        str(versioned_archive),
    ]
    proc = subprocess.run(
        cmd,
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output

    package_archive = output_dir / f"tabdump-homebrew-{version}.tar.gz"
    package_checksum = output_dir / f"tabdump-homebrew-{version}.tar.gz.sha256"
    assert package_archive.exists()
    assert package_checksum.exists()

    with tarfile.open(package_archive, "r:gz") as tf:
        raw_names = tf.getnames()
    names = {name[2:] if name.startswith("./") else name for name in raw_names}
    names = {name for name in names if not name.startswith("._")}
    assert "scripts/install.sh" in names
    assert "scripts/runtime-manifest.sha256" in names
    assert f"dist/tabdump-app-{version}.tar.gz" in names
    assert "dist/tabdump-app.tar.gz" in names
    assert "skills/tabdump-macos/SKILL.md" in names
    assert "skills/tabdump-macos/references/config.md" in names
    assert "skills/tabdump-macos/scripts/tabdump_run_once.sh" in names
    assert "skills/tabdump-macos/scripts/tabdump_count.sh" in names
    assert "skills/tabdump-macos/scripts/tabdump_status.sh" in names
    assert "skills/tabdump-macos/scripts/tabdump_doctor.sh" in names
    assert "skills/tabdump-macos/scripts/tabdump_install_launchagent.sh" in names


def test_build_homebrew_package_fails_when_app_archive_missing(tmp_path):
    output_dir = tmp_path / "dist"
    output_dir.mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(
        [
            "bash",
            str(BUILD_SCRIPT),
            "--version",
            "v1.0.0",
            "--output-dir",
            str(output_dir),
            "--app-archive",
            str(output_dir / "missing.tar.gz"),
        ],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1
    assert "App archive not found:" in output
