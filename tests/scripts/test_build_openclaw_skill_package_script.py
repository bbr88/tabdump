import os
import subprocess
import tarfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT_DIR / "scripts" / "build-openclaw-skill-package.sh"


def test_build_openclaw_skill_package_happy_path(tmp_path):
    version = "v1.2.3-test"
    output_dir = tmp_path / "dist"

    proc = subprocess.run(
        [
            "bash",
            str(BUILD_SCRIPT),
            "--version",
            version,
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output

    package_archive = output_dir / f"tabdump-openclaw-skill-{version}.tar.gz"
    package_checksum = output_dir / f"tabdump-openclaw-skill-{version}.tar.gz.sha256"
    assert package_archive.exists()
    assert package_checksum.exists()

    with tarfile.open(package_archive, "r:gz") as tf:
        names = {name[2:] if name.startswith("./") else name for name in tf.getnames()}

    assert "tabdump-macos/SKILL.md" in names
    assert "tabdump-macos/references/config.md" in names
    assert "tabdump-macos/scripts/tabdump_run_once.sh" in names
    assert "tabdump-macos/scripts/tabdump_status.sh" in names
    assert "tabdump-macos/scripts/test_skill_smoke.sh" in names


def test_build_openclaw_skill_package_fails_for_missing_skill_path(tmp_path):
    version = "v1.2.3-test"
    output_dir = tmp_path / "dist"
    missing_skill_dir = tmp_path / "no-skill-here"

    proc = subprocess.run(
        [
            "bash",
            str(BUILD_SCRIPT),
            "--version",
            version,
            "--output-dir",
            str(output_dir),
            "--skill-path",
            str(missing_skill_dir),
        ],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1
    assert "Skill path not found:" in output


def test_build_openclaw_skill_package_fails_when_skill_md_missing(tmp_path):
    version = "v1.2.3-test"
    output_dir = tmp_path / "dist"
    skill_dir = tmp_path / "skill"
    (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)
    (skill_dir / "references").mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(
        [
            "bash",
            str(BUILD_SCRIPT),
            "--version",
            version,
            "--output-dir",
            str(output_dir),
            "--skill-path",
            str(skill_dir),
        ],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1
    assert "SKILL.md not found under skill path:" in output
