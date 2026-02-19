import json
import os
import plistlib
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "skills" / "tabdump-macos" / "scripts" / "tabdump_install_launchagent.sh"


def _write_exec(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _prepare_runtime(home: Path, check_every_minutes: int = 30) -> tuple[Path, Path, Path]:
    app_support = home / "Library" / "Application Support" / "TabDump"
    app_support.mkdir(parents=True, exist_ok=True)
    cfg_path = app_support / "config.json"
    cfg_path.write_text(json.dumps({"checkEveryMinutes": check_every_minutes}), encoding="utf-8")

    wrapper_path = app_support / "tabdump-monitor"
    _write_exec(
        wrapper_path,
        "#!/usr/bin/env bash\nset -euo pipefail\necho monitor \"$@\"\n",
    )
    return app_support, cfg_path, wrapper_path


def _install_launchctl_stub(bin_dir: Path) -> Path:
    log_path = bin_dir / "launchctl.log"
    _write_exec(
        bin_dir / "launchctl",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "launchctl $*" >> "{log_path}"
if [[ "${{TABDUMP_TEST_FAIL_CMD:-}}" != "" && "${{1:-}}" == "${{TABDUMP_TEST_FAIL_CMD}}" ]]; then
  echo "${{1}} failed" >&2
  exit 1
fi
exit 0
""",
    )
    return log_path


def _plist_path(home: Path) -> Path:
    return home / "Library" / "LaunchAgents" / "io.orc-visioner.tabdump.monitor.plist"


def test_install_launchagent_rewrites_plist_and_restarts_job(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    _app_support, _cfg, wrapper = _prepare_runtime(home, check_every_minutes=30)

    plist_path = _plist_path(home)
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    with plist_path.open("wb") as fh:
        plistlib.dump(
            {
                "EnvironmentVariables": {
                    "TABDUMP_KEYCHAIN_SERVICE": "CustomService",
                    "TABDUMP_KEYCHAIN_ACCOUNT": "custom-account",
                }
            },
            fh,
        )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    launchctl_log = _install_launchctl_stub(bin_dir)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output
    assert "Installed and started io.orc-visioner.tabdump.monitor." in output

    with plist_path.open("rb") as fh:
        plist = plistlib.load(fh)
    assert plist["StartInterval"] == 1800
    assert plist["ProgramArguments"] == [str(wrapper)]
    assert plist["EnvironmentVariables"]["TABDUMP_KEYCHAIN_SERVICE"] == "CustomService"
    assert plist["EnvironmentVariables"]["TABDUMP_KEYCHAIN_ACCOUNT"] == "custom-account"

    calls = launchctl_log.read_text(encoding="utf-8")
    assert "launchctl bootout gui/" in calls
    assert "launchctl bootstrap gui/" in calls
    assert "launchctl enable gui/" in calls
    assert "launchctl kickstart -k gui/" in calls


def test_install_launchagent_respects_env_override_and_clamps_interval(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    _prepare_runtime(home, check_every_minutes=0)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    _install_launchctl_stub(bin_dir)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["TABDUMP_KEYCHAIN_SERVICE"] = "EnvService"
    env["TABDUMP_KEYCHAIN_ACCOUNT"] = "env-account"

    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output

    with _plist_path(home).open("rb") as fh:
        plist = plistlib.load(fh)
    assert plist["StartInterval"] == 60
    assert plist["EnvironmentVariables"]["TABDUMP_KEYCHAIN_SERVICE"] == "EnvService"
    assert plist["EnvironmentVariables"]["TABDUMP_KEYCHAIN_ACCOUNT"] == "env-account"


def test_install_launchagent_fails_when_config_missing(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["HOME"] = str(home)

    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 2
    assert "config.json not found" in output


def test_install_launchagent_fails_when_wrapper_missing(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    app_support = home / "Library" / "Application Support" / "TabDump"
    app_support.mkdir(parents=True, exist_ok=True)
    (app_support / "config.json").write_text(json.dumps({"checkEveryMinutes": 30}), encoding="utf-8")

    env = os.environ.copy()
    env["HOME"] = str(home)

    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 2
    assert "monitor wrapper missing or not executable" in output
