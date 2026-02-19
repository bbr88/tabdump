import json
import os
import plistlib
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "skills" / "tabdump-macos" / "scripts" / "tabdump_doctor.sh"


def _write_exec(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _prepare_healthy_runtime(home: Path, check_every_minutes: int = 30) -> None:
    app = home / "Applications" / "TabDump.app"
    app.mkdir(parents=True, exist_ok=True)

    app_support = home / "Library" / "Application Support" / "TabDump"
    logs_dir = app_support / "logs"
    inbox = home / "vault" / "Inbox"
    launch_agents = home / "Library" / "LaunchAgents"
    launch_agents.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    inbox.mkdir(parents=True, exist_ok=True)

    (app_support / "monitor_tabs.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (logs_dir / "monitor.out.log").write_text("runtime ok\n", encoding="utf-8")
    (logs_dir / "monitor.err.log").write_text("\n", encoding="utf-8")

    config = {
        "vaultInbox": str(inbox),
        "browsers": ["Chrome", "Safari"],
        "llmEnabled": True,
        "dryRun": True,
        "dryRunPolicy": "manual",
        "checkEveryMinutes": check_every_minutes,
        "cooldownMinutes": 1440,
        "maxTabs": 30,
    }
    (app_support / "config.json").write_text(json.dumps(config), encoding="utf-8")

    plist_path = launch_agents / "io.orc-visioner.tabdump.monitor.plist"
    with plist_path.open("wb") as fh:
        plistlib.dump(
            {
                "Label": "io.orc-visioner.tabdump.monitor",
                "StartInterval": check_every_minutes * 60,
                "ProgramArguments": [str(app_support / "tabdump-monitor")],
            },
            fh,
        )


def _prepare_issue_runtime(home: Path) -> None:
    app_support = home / "Library" / "Application Support" / "TabDump"
    logs_dir = app_support / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "monitor.out.log").write_text("count_unavailable\n", encoding="utf-8")
    (logs_dir / "monitor.err.log").write_text("not authorized to send apple events\n", encoding="utf-8")


def _install_launchctl_stub(bin_dir: Path) -> None:
    _write_exec(
        bin_dir / "launchctl",
        """#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
  list)
    echo "{\"PID\":0,\"Label\":\"io.orc-visioner.tabdump.monitor\"}"
    ;;
  print)
    cat <<'OUT'
state = running
last exit code = 0
OUT
    ;;
  *)
    echo "ok"
    ;;
esac
""",
    )


def _run_doctor(home: Path, bin_dir: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_doctor_json_healthy_contract(tmp_path: Path):
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    home.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)

    _prepare_healthy_runtime(home, check_every_minutes=30)
    _install_launchctl_stub(bin_dir)

    proc = _run_doctor(home, bin_dir, ["--json"])
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output

    payload = json.loads(proc.stdout.strip())
    assert payload["schemaVersion"] == "tabdump-doctor/v1"
    assert payload["status"] == "ok"
    assert payload["issueCount"] == 0
    assert payload["issues"] == []
    assert payload["recommendedActions"] == []
    assert isinstance(payload["generatedAt"], str)
    assert isinstance(payload["paths"], dict)


def test_doctor_json_issues_contract_and_deterministic_ids(tmp_path: Path):
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    home.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)

    _prepare_issue_runtime(home)
    _install_launchctl_stub(bin_dir)

    first = _run_doctor(home, bin_dir, ["--json"])
    second = _run_doctor(home, bin_dir, ["--json"])

    out_first = first.stdout + first.stderr
    out_second = second.stdout + second.stderr
    assert first.returncode == 1, out_first
    assert second.returncode == 1, out_second

    p1 = json.loads(first.stdout.strip())
    p2 = json.loads(second.stdout.strip())

    assert p1["schemaVersion"] == "tabdump-doctor/v1"
    assert p1["status"] == "issues"
    assert p1["issueCount"] > 0
    assert len(p1["issues"]) == p1["issueCount"]
    assert len(p1["recommendedActions"]) > 0

    issue_ids_1 = [item["id"] for item in p1["issues"]]
    issue_ids_2 = [item["id"] for item in p2["issues"]]
    action_ids_1 = [item["id"] for item in p1["recommendedActions"]]
    action_ids_2 = [item["id"] for item in p2["recommendedActions"]]

    assert issue_ids_1 == issue_ids_2
    assert action_ids_1 == action_ids_2

    for issue in p1["issues"]:
        assert issue["severity"] in {"low", "medium", "high"}
        assert isinstance(issue["category"], str)
        assert isinstance(issue["message"], str)

    for action in p1["recommendedActions"]:
        assert isinstance(action["command"], str)
        assert action["command"]
        assert isinstance(action["reason"], str)
        assert action["reason"]


def test_doctor_usage_error_exits_two(tmp_path: Path):
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    home.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)

    _prepare_healthy_runtime(home)
    _install_launchctl_stub(bin_dir)

    proc = _run_doctor(home, bin_dir, ["--unknown-flag"])
    output = proc.stdout + proc.stderr
    assert proc.returncode == 2, output
    assert "Unknown option" in output
