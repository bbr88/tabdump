import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
UNINSTALL_SCRIPT = ROOT_DIR / "scripts" / "uninstall.sh"


@dataclass
class UninstallRun:
    returncode: int
    stdout: str
    stderr: str
    home: Path
    log_path: Path


def _write_stub(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _install_uninstall_stubs(bin_dir: Path) -> None:
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
        "tccutil",
        """#!/usr/bin/env bash
set -euo pipefail
echo "tccutil $*" >> "${TABDUMP_TEST_LOG:?}"
exit 0
""",
    )


def _create_installed_layout(home: Path) -> None:
    config_dir = home / "Library" / "Application Support" / "TabDump"
    core_dir = config_dir / "core"
    renderer_dir = core_dir / "renderer"
    postprocess_dir = core_dir / "postprocess"
    tab_policy_dir = core_dir / "tab_policy"
    logs_dir = config_dir / "logs"

    app_dir = home / "Applications" / "TabDump.app"
    launch_agent_dir = home / "Library" / "LaunchAgents"
    cli_dir = home / ".local" / "bin"

    for directory in [
        renderer_dir,
        postprocess_dir,
        tab_policy_dir,
        logs_dir,
        app_dir,
        launch_agent_dir,
        cli_dir,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    (config_dir / "TabDump.scpt").write_text("engine", encoding="utf-8")
    (config_dir / "monitor_tabs.py").write_text("monitor", encoding="utf-8")
    (core_dir / "__init__.py").write_text("", encoding="utf-8")
    (renderer_dir / "renderer.py").write_text("", encoding="utf-8")
    (postprocess_dir / "cli.py").write_text("", encoding="utf-8")
    (tab_policy_dir / "matching.py").write_text("", encoding="utf-8")
    (config_dir / "monitor_state.json").write_text("{}", encoding="utf-8")
    (config_dir / "monitor_state.lock").write_text("", encoding="utf-8")
    (config_dir / "state.json").write_text("{}", encoding="utf-8")
    (config_dir / "config.json").write_text("{}", encoding="utf-8")
    (launch_agent_dir / "io.orc-visioner.tabdump.monitor.plist").write_text("plist", encoding="utf-8")
    (cli_dir / "tabdump").write_text("#!/usr/bin/env bash\n", encoding="utf-8")


def _run_uninstall(
    tmp_path: Path,
    user_input: str = "",
    args: list[str] | None = None,
    extra_env: dict[str, str] | None = None,
    setup_home: Callable[[Path], None] | None = None,
) -> UninstallRun:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    log_path = tmp_path / "command.log"
    home.mkdir()
    fake_bin.mkdir()

    _create_installed_layout(home)
    if setup_home:
        setup_home(home)
    _install_uninstall_stubs(fake_bin)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["TABDUMP_TEST_LOG"] = str(log_path)
    if extra_env:
        env.update(extra_env)

    cmd = ["bash", str(UNINSTALL_SCRIPT)]
    if args:
        cmd.extend(args)

    proc = subprocess.run(
        cmd,
        cwd=ROOT_DIR,
        env=env,
        input=user_input,
        text=True,
        capture_output=True,
        check=False,
    )

    return UninstallRun(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        home=home,
        log_path=log_path,
    )


def test_uninstall_yes_keeps_config_and_does_not_purge_tcc(tmp_path):
    proc = _run_uninstall(tmp_path, args=["--yes"])
    output = proc.stdout + proc.stderr
    config_path = proc.home / "Library" / "Application Support" / "TabDump" / "config.json"

    assert proc.returncode == 0, output
    assert config_path.exists()
    assert not (proc.home / "Applications" / "TabDump.app").exists()

    log = proc.log_path.read_text(encoding="utf-8")
    assert "launchctl bootout" in log
    assert "tccutil reset" not in log


def test_uninstall_purge_and_remove_config(tmp_path):
    proc = _run_uninstall(tmp_path, args=["--yes", "--purge", "--remove-config"])
    output = proc.stdout + proc.stderr
    config_path = proc.home / "Library" / "Application Support" / "TabDump" / "config.json"

    assert proc.returncode == 0, output
    assert not config_path.exists()

    log = proc.log_path.read_text(encoding="utf-8")
    assert "tccutil reset AppleEvents io.orc-visioner.tabdump" in log


def test_uninstall_rejects_conflicting_config_flags(tmp_path):
    proc = _run_uninstall(tmp_path, args=["--yes", "--remove-config", "--keep-config"])
    output = proc.stdout + proc.stderr

    assert proc.returncode == 1
    assert "--remove-config and --keep-config cannot be used together." in output


def test_uninstall_interactive_can_remove_config(tmp_path):
    proc = _run_uninstall(tmp_path, user_input="y\ny\n")
    output = proc.stdout + proc.stderr
    config_path = proc.home / "Library" / "Application Support" / "TabDump" / "config.json"

    assert proc.returncode == 0, output
    assert not config_path.exists()


def test_uninstall_removes_core_pycache_and_cleans_core_dir(tmp_path):
    def _setup(home: Path) -> None:
        pycache_dir = home / "Library" / "Application Support" / "TabDump" / "core" / "__pycache__"
        pycache_dir.mkdir(parents=True, exist_ok=True)
        (pycache_dir / "renderer.cpython-314.pyc").write_bytes(b"pyc")

    proc = _run_uninstall(
        tmp_path,
        args=["--yes", "--remove-config"],
        setup_home=_setup,
    )
    output = proc.stdout + proc.stderr
    core_dir = proc.home / "Library" / "Application Support" / "TabDump" / "core"
    pycache_dir = core_dir / "__pycache__"

    assert proc.returncode == 0, output
    assert "Core __pycache__:" in output
    assert not pycache_dir.exists()
    assert not core_dir.exists()
