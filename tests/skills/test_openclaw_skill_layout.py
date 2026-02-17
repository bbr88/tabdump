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


def _create_smoke_stub_scripts(
    tmp_path: Path,
    run_once_exit: int = 0,
    count_json_payload: str | None = None,
) -> tuple[Path, Path]:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    call_log = tmp_path / "calls.log"
    if count_json_payload is None:
        count_json_payload = '{"status":"ok","reason":"count_only","mode":"count","tabCount":7}'

    _write_executable(
        scripts_dir / "tabdump_run_once.sh",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "run_once" >> "{call_log}"
echo "RAW_DUMP=/tmp/raw.md"
echo "CLEAN_NOTE=/tmp/clean.md"
if [[ "{run_once_exit}" == "3" ]]; then
  echo "[info] No clean dump produced (cooldown_active)."
fi
exit {run_once_exit}
""",
    )
    _write_executable(
        scripts_dir / "tabdump_count.sh",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "count" >> "{call_log}"
if [[ "${{1:-}}" == "--json" ]]; then
  cat <<'JSON'
{count_json_payload}
JSON
  exit 0
fi
echo "7"
""",
    )
    _write_executable(
        scripts_dir / "tabdump_status.sh",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "status" >> "{call_log}"
echo "TabDump status"
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
    return scripts_dir, call_log


def test_openclaw_skill_layout_contains_required_files():
    required = [
        SKILL_DIR / "SKILL.md",
        SKILL_DIR / "references" / "config.md",
        SKILL_DIR / "scripts" / "tabdump_run_once.sh",
        SKILL_DIR / "scripts" / "tabdump_count.sh",
        SKILL_DIR / "scripts" / "tabdump_status.sh",
        SKILL_DIR / "scripts" / "tabdump_reload_launchagent.sh",
        SKILL_DIR / "scripts" / "tabdump_permissions_reset.sh",
        SKILL_DIR / "scripts" / "tabdump_install_from_repo.sh",
        SKILL_DIR / "scripts" / "test_skill_smoke.sh",
    ]
    for path in required:
        assert path.exists(), f"Missing required skill file: {path}"


def test_openclaw_skill_scripts_are_executable():
    scripts = [
        SKILL_DIR / "scripts" / "tabdump_run_once.sh",
        SKILL_DIR / "scripts" / "tabdump_count.sh",
        SKILL_DIR / "scripts" / "tabdump_status.sh",
        SKILL_DIR / "scripts" / "tabdump_reload_launchagent.sh",
        SKILL_DIR / "scripts" / "tabdump_permissions_reset.sh",
        SKILL_DIR / "scripts" / "tabdump_install_from_repo.sh",
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
        "one-shot output contract",
        "verify successful operation",
        "tcc / automation troubleshooting",
    ]
    for section in required_sections:
        assert section in lower, f"Missing section in SKILL.md: {section}"

    assert "tccutil reset appleevents io.orc-visioner.tabdump" in lower


def test_skill_smoke_safe_mode_does_not_run_one_shot(tmp_path):
    scripts_dir, call_log = _create_smoke_stub_scripts(tmp_path, run_once_exit=0)
    env = os.environ.copy()
    env["TABDUMP_SMOKE_SCRIPTS_DIR"] = str(scripts_dir)

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
    assert "Safe mode: skipping active one-shot/count runs" in output

    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert "status" in calls
    assert "run_once" not in calls
    assert "count" not in calls


def test_skill_smoke_active_mode_runs_one_shot_success(tmp_path):
    scripts_dir, call_log = _create_smoke_stub_scripts(tmp_path, run_once_exit=0)
    env = os.environ.copy()
    env["TABDUMP_SMOKE_SCRIPTS_DIR"] = str(scripts_dir)

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
    assert "Active mode may open TabDump.app and trigger macOS Automation (TCC) prompts." in output
    assert "run_once success output contract is valid." in output
    assert "count success output contract is valid." in output

    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert "run_once" in calls
    assert "count" in calls


def test_skill_smoke_active_mode_accepts_noop_contract(tmp_path):
    scripts_dir, call_log = _create_smoke_stub_scripts(tmp_path, run_once_exit=3)
    env = os.environ.copy()
    env["TABDUMP_SMOKE_SCRIPTS_DIR"] = str(scripts_dir)

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
    assert "run_once noop path produced expected diagnostic." in output

    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert "run_once" in calls
    assert "count" in calls


def test_skill_smoke_active_mode_accepts_count_unavailable_contract(tmp_path):
    scripts_dir, call_log = _create_smoke_stub_scripts(
        tmp_path,
        run_once_exit=0,
        count_json_payload='{"status":"error","reason":"count_unavailable","mode":"count","tabCount":null}',
    )
    env = os.environ.copy()
    env["TABDUMP_SMOKE_SCRIPTS_DIR"] = str(scripts_dir)

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
    assert "count" in calls
