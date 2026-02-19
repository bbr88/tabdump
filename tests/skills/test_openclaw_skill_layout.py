import os
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT_DIR / "skills" / "tabdump-macos"
SKILL_MD = SKILL_DIR / "SKILL.md"
SMOKE_SCRIPT = SKILL_DIR / "scripts" / "test_skill_smoke.sh"


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _create_smoke_stub_environment(
    tmp_path: Path,
    now_exit: int = 0,
    now_json_payload: str | None = None,
    count_json_payload: str | None = None,
    doctor_exit: int = 0,
    doctor_json_payload: str | None = None,
) -> tuple[Path, Path, Path]:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    call_log = tmp_path / "calls.log"

    if now_json_payload is None:
        now_json_payload = '{"status":"ok","reason":"","mode":"dump-only","rawDump":"/tmp/raw.md","cleanNote":"/tmp/clean.md"}'
    if count_json_payload is None:
        count_json_payload = '{"status":"ok","reason":"count_only","mode":"count","tabCount":7}'
    if doctor_json_payload is None:
        doctor_json_payload = (
            '{"schemaVersion":"tabdump-doctor/v1","status":"ok","issueCount":0,'
            '"generatedAt":"2026-01-01T00:00:00Z","issues":[],"recommendedActions":[],'
            '"paths":{"app":"/tmp/TabDump.app","config":"/tmp/config.json"}}'
        )

    _write_executable(
        bin_dir / "tabdump",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "tabdump $*" >> "{call_log}"
cmd="${{1:-}}"
shift || true

case "${{cmd}}" in
  status)
    echo "TabDump status"
    ;;
  now)
    if [[ "${{1:-}}" != "--json" ]]; then
      echo "missing --json" >&2
      exit 1
    fi
    cat <<'JSON'
{now_json_payload}
JSON
    exit {now_exit}
    ;;
  count)
    if [[ "${{1:-}}" != "--json" ]]; then
      echo "missing --json" >&2
      exit 1
    fi
    cat <<'JSON'
{count_json_payload}
JSON
    ;;
  *)
    echo "unknown command: ${{cmd}}" >&2
    exit 1
    ;;
esac
""",
    )

    _write_executable(
        scripts_dir / "tabdump_doctor.sh",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "doctor $*" >> "{call_log}"
if [[ "${{1:-}}" != "--json" ]]; then
  echo "missing --json" >&2
  exit 2
fi
cat <<'JSON'
{doctor_json_payload}
JSON
exit {doctor_exit}
""",
    )

    _write_executable(
        scripts_dir / "tabdump_reload_launchagent.sh",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "reload" >> "{call_log}"
""",
    )
    _write_executable(
        scripts_dir / "tabdump_install_launchagent.sh",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "install_launchagent" >> "{call_log}"
""",
    )
    _write_executable(
        scripts_dir / "tabdump_permissions_reset.sh",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "perms" >> "{call_log}"
""",
    )
    _write_executable(
        scripts_dir / "tabdump_install_from_repo.sh",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "install" >> "{call_log}"
""",
    )
    _write_executable(
        scripts_dir / "tabdump_install_brew.sh",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "install_brew" >> "{call_log}"
""",
    )

    return scripts_dir, bin_dir, call_log


def test_openclaw_skill_layout_contains_required_files():
    required = [
        SKILL_DIR / "SKILL.md",
        SKILL_DIR / "references" / "config.md",
        SKILL_DIR / "scripts" / "tabdump_doctor.sh",
        SKILL_DIR / "scripts" / "tabdump_reload_launchagent.sh",
        SKILL_DIR / "scripts" / "tabdump_install_launchagent.sh",
        SKILL_DIR / "scripts" / "tabdump_permissions_reset.sh",
        SKILL_DIR / "scripts" / "tabdump_install_from_repo.sh",
        SKILL_DIR / "scripts" / "tabdump_install_brew.sh",
        SKILL_DIR / "scripts" / "test_skill_smoke.sh",
    ]
    for path in required:
        assert path.exists(), f"Missing required skill file: {path}"


def test_openclaw_skill_scripts_are_executable():
    scripts = [
        SKILL_DIR / "scripts" / "tabdump_doctor.sh",
        SKILL_DIR / "scripts" / "tabdump_reload_launchagent.sh",
        SKILL_DIR / "scripts" / "tabdump_install_launchagent.sh",
        SKILL_DIR / "scripts" / "tabdump_permissions_reset.sh",
        SKILL_DIR / "scripts" / "tabdump_install_from_repo.sh",
        SKILL_DIR / "scripts" / "tabdump_install_brew.sh",
        SKILL_DIR / "scripts" / "test_skill_smoke.sh",
    ]
    for script in scripts:
        assert os.access(script, os.X_OK), f"Script is not executable: {script}"


def test_skill_md_contains_required_trigger_and_ops_sections():
    text = SKILL_MD.read_text(encoding="utf-8")
    lower = text.lower()

    required_triggers = [
        "dump tabs",
        "capture browser tabs",
        "tabdump",
        "reading queue",
        "obsidian inbox",
        "launch agent status",
    ]
    for trigger in required_triggers:
        assert trigger in lower, f"Missing trigger phrase in SKILL.md: {trigger}"

    required_sections = [
        "runtime layout",
        "primary commands",
        "doctor json output contract",
        "migration from removed wrappers",
        "tcc / automation troubleshooting",
    ]
    for section in required_sections:
        assert section in lower, f"Missing section in SKILL.md: {section}"

    assert "scripts/tabdump_doctor.sh --json" in lower
    assert "tccutil reset appleevents io.orc-visioner.tabdump" in lower


def test_skill_smoke_safe_mode_does_not_run_active_cli(tmp_path):
    scripts_dir, bin_dir, call_log = _create_smoke_stub_environment(tmp_path, now_exit=0)
    env = os.environ.copy()
    env["TABDUMP_SMOKE_SCRIPTS_DIR"] = str(scripts_dir)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    proc = subprocess.run(
        ["bash", str(SMOKE_SCRIPT)],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output
    assert "Safe mode: skipping active now/count runs" in output
    assert "doctor JSON output contract is valid" in output

    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert any(line.startswith("tabdump status") for line in calls)
    assert any(line.startswith("doctor --json") for line in calls)
    assert not any(line.startswith("tabdump now") for line in calls)
    assert not any(line.startswith("tabdump count") for line in calls)


def test_skill_smoke_active_mode_runs_now_and_count_success(tmp_path):
    scripts_dir, bin_dir, call_log = _create_smoke_stub_environment(tmp_path, now_exit=0)
    env = os.environ.copy()
    env["TABDUMP_SMOKE_SCRIPTS_DIR"] = str(scripts_dir)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    proc = subprocess.run(
        ["bash", str(SMOKE_SCRIPT), "--active"],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output
    assert "now JSON output contract is valid." in output
    assert "count success output contract is valid." in output

    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert any(line.startswith("tabdump now --json") for line in calls)
    assert any(line.startswith("tabdump count --json") for line in calls)


def test_skill_smoke_active_mode_accepts_now_noop_contract(tmp_path):
    scripts_dir, bin_dir, _call_log = _create_smoke_stub_environment(
        tmp_path,
        now_exit=0,
        now_json_payload='{"status":"noop","reason":"cooldown_active","mode":"dump-only","rawDump":"","cleanNote":""}',
    )
    env = os.environ.copy()
    env["TABDUMP_SMOKE_SCRIPTS_DIR"] = str(scripts_dir)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    proc = subprocess.run(
        ["bash", str(SMOKE_SCRIPT), "--active"],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output
    assert "now JSON output contract is valid." in output


def test_skill_smoke_active_mode_accepts_count_unavailable_contract(tmp_path):
    scripts_dir, bin_dir, call_log = _create_smoke_stub_environment(
        tmp_path,
        now_exit=0,
        count_json_payload='{"status":"error","reason":"count_unavailable","mode":"count","tabCount":null}',
    )
    env = os.environ.copy()
    env["TABDUMP_SMOKE_SCRIPTS_DIR"] = str(scripts_dir)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    proc = subprocess.run(
        ["bash", str(SMOKE_SCRIPT), "--active"],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output
    assert "count fail-hard output contract is valid." in output

    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert any(line.startswith("tabdump count --json") for line in calls)
