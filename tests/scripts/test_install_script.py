import json
import os
import stat
import subprocess
import sys
import tarfile
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
    bin_dir: Path
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
if [[ "${TABDUMP_TEST_BOOTOUT_IO_ERROR:-0}" == "1" && "${1:-}" == "bootout" ]]; then
  echo "Boot-out failed: 5: Input/output error" >&2
  echo "Try re-running the command as root for richer errors." >&2
  exit 1
fi
if [[ "${TABDUMP_TEST_FAIL_BOOTSTRAP:-0}" == "1" && "${1:-}" == "bootstrap" ]]; then
  echo "bootstrap failed" >&2
  exit 1
fi
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
  if [[ "${TABDUMP_TEST_KEYCHAIN_EXISTS:-0}" == "1" ]]; then
    exit 0
  fi
  exit 1
fi
exit 0
""",
    )
    _write_stub(
        bin_dir,
        "open",
        """#!/usr/bin/env bash
set -euo pipefail
echo "open $*" >> "${TABDUMP_TEST_LOG:?}"
exit 0
""",
    )
    _write_stub(
        bin_dir,
        "osascript",
        """#!/usr/bin/env bash
set -euo pipefail
echo "osascript $*" >> "${TABDUMP_TEST_LOG:?}"
if [[ "$*" == *"id of application \\\"Google Chrome\\\""* ]]; then
  if [[ "${TABDUMP_TEST_HAS_CHROME:-1}" == "1" ]]; then
    exit 0
  fi
  exit 1
fi
if [[ "$*" == *"id of application \\\"Safari\\\""* ]]; then
  if [[ "${TABDUMP_TEST_HAS_SAFARI:-1}" == "1" ]]; then
    exit 0
  fi
  exit 1
fi
if [[ "$*" == *"id of application \\\"Firefox\\\""* ]]; then
  if [[ "${TABDUMP_TEST_HAS_FIREFOX:-1}" == "1" ]]; then
    exit 0
  fi
  exit 1
fi
exit 0
""",
    )


def _create_prebuilt_app_archive(tmp_path: Path) -> Path:
    stage_dir = tmp_path / "prebuilt-app"
    app_contents = stage_dir / "TabDump.app" / "Contents"
    app_contents.mkdir(parents=True, exist_ok=True)
    (app_contents / "Info.plist").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict></dict></plist>
""",
        encoding="utf-8",
    )

    archive_path = tmp_path / "tabdump-app.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tf:
        tf.add(stage_dir / "TabDump.app", arcname="TabDump.app")
    return archive_path


def _run_install(
    tmp_path: Path,
    user_input: str = "",
    args: list[str] | None = None,
    extra_env: dict[str, str] | None = None,
) -> InstallRun:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    log_path = tmp_path / "command.log"
    home.mkdir(exist_ok=True)
    fake_bin.mkdir(exist_ok=True)
    _install_test_stubs(fake_bin)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["TABDUMP_TEST_LOG"] = str(log_path)
    env["TABDUMP_APP_ARCHIVE"] = str(_create_prebuilt_app_archive(tmp_path))
    if extra_env:
        env.update(extra_env)

    cmd = ["bash", str(INSTALL_SCRIPT)]
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
    return InstallRun(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        home=home,
        bin_dir=fake_bin,
        log_path=log_path,
    )


def _read_config(home: Path) -> dict:
    cfg_path = home / "Library" / "Application Support" / "TabDump" / "config.json"
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def _run_generated_cli(
    run: InstallRun,
    args: list[str] | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    cli_path = run.home / ".local" / "bin" / "tabdump"
    env = os.environ.copy()
    env["HOME"] = str(run.home)
    env["PATH"] = f"{run.bin_dir}:{env['PATH']}"
    env["TABDUMP_TEST_LOG"] = str(run.log_path)
    if extra_env:
        env.update(extra_env)

    cmd = [str(cli_path)]
    if args:
        cmd.extend(args)

    return subprocess.run(
        cmd,
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_install_requires_vault_inbox_path_in_yes_mode(tmp_path):
    proc = _run_install(tmp_path, args=["--yes"])
    output = proc.stdout + proc.stderr

    assert proc.returncode == 1
    assert "--vault-inbox is required when running with --yes." in output


def test_install_fails_when_prebuilt_app_archive_missing(tmp_path):
    proc = _run_install(
        tmp_path,
        args=["--yes", "--vault-inbox", "~/vault/inbox"],
        extra_env={"TABDUMP_APP_ARCHIVE": str(tmp_path / "missing-app.tar.gz")},
    )
    output = proc.stdout + proc.stderr

    assert proc.returncode == 1
    assert "Prebuilt app archive not found:" in output


def test_install_writes_default_config_and_artifacts(tmp_path):
    proc = _run_install(tmp_path, user_input="~/vault/inbox\n\nn\nn\n")
    output = proc.stdout + proc.stderr
    home = proc.home
    config_dir = home / "Library" / "Application Support" / "TabDump"
    config_path = config_dir / "config.json"
    wrapper_path = config_dir / "tabdump-monitor"
    app_path = home / "Applications" / "TabDump.app"
    cli_path = home / ".local" / "bin" / "tabdump"
    plist_path = home / "Library" / "LaunchAgents" / "io.orc-visioner.tabdump.monitor.plist"

    assert proc.returncode == 0, output
    assert config_path.exists()
    assert wrapper_path.exists()
    assert app_path.exists()
    assert cli_path.exists()
    assert plist_path.exists()

    data = _read_config(home)
    expected_vault = (home / "vault" / "inbox").resolve()
    assert data["vaultInbox"] == f"{expected_vault}{os.sep}"
    assert data["dryRun"] is True
    assert data["dryRunPolicy"] == "auto"
    assert isinstance(data["onboardingStartedAt"], int)
    assert data["onboardingStartedAt"] > 0
    assert data["llmEnabled"] is False
    assert data["browsers"] == ["Chrome", "Safari"]

    assert stat.S_IMODE(config_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(config_dir.stat().st_mode) == 0o700
    assert os.access(wrapper_path, os.X_OK)
    assert os.access(cli_path, os.X_OK)
    plist_text = plist_path.read_text(encoding="utf-8")
    assert "<integer>3600</integer>" in plist_text
    assert f"<string>{wrapper_path}</string>" in plist_text

    log = proc.log_path.read_text(encoding="utf-8")
    assert "shasum -a 256 -c" in log
    assert "osacompile -o" not in log
    assert "codesign --force --deep --sign -" not in log
    assert "launchctl bootstrap" in log


def test_install_noninteractive_skip_key_mode_disables_llm(tmp_path):
    proc = _run_install(
        tmp_path,
        args=[
            "--yes",
            "--vault-inbox",
            "~/vault/inbox",
            "--browsers",
            "Safari, Chrome, Firefox",
            "--set-dry-run",
            "false",
            "--enable-llm",
            "true",
            "--key-mode",
            "skip",
        ],
    )
    output = proc.stdout + proc.stderr

    assert proc.returncode == 0, output
    data = _read_config(proc.home)
    assert data["dryRun"] is False
    assert data["dryRunPolicy"] == "manual"
    assert isinstance(data["onboardingStartedAt"], int)
    assert data["onboardingStartedAt"] > 0
    assert data["llmEnabled"] is False
    assert data["browsers"] == ["Safari", "Chrome", "Firefox"]


def test_install_applies_gate_overrides_from_args(tmp_path):
    proc = _run_install(
        tmp_path,
        args=[
            "--yes",
            "--vault-inbox",
            "~/vault/inbox",
            "--max-tabs",
            "55",
            "--check-every-minutes",
            "15",
            "--cooldown-minutes",
            "720",
        ],
    )
    output = proc.stdout + proc.stderr

    assert proc.returncode == 0, output
    data = _read_config(proc.home)
    assert data["maxTabs"] == 55
    assert data["checkEveryMinutes"] == 15
    assert data["cooldownMinutes"] == 720

    plist_path = proc.home / "Library" / "LaunchAgents" / "io.orc-visioner.tabdump.monitor.plist"
    plist_text = plist_path.read_text(encoding="utf-8")
    assert "<integer>900</integer>" in plist_text


def test_install_rejects_invalid_browsers(tmp_path):
    proc = _run_install(
        tmp_path,
        args=[
            "--yes",
            "--vault-inbox",
            "~/vault/inbox",
            "--browsers",
            "Chrome,Brave",
        ],
    )
    output = proc.stdout + proc.stderr

    assert proc.returncode == 1
    assert "Invalid browser list" in output


def test_install_warns_for_missing_configured_browser(tmp_path):
    proc = _run_install(
        tmp_path,
        args=[
            "--yes",
            "--vault-inbox",
            "~/vault/inbox",
            "--browsers",
            "Chrome,Safari",
        ],
        extra_env={"TABDUMP_TEST_HAS_CHROME": "0", "TABDUMP_TEST_HAS_SAFARI": "1"},
    )
    output = proc.stdout + proc.stderr

    assert proc.returncode == 0, output
    assert "Chrome is configured but not installed. TabDump will skip it until installed." in output


def test_install_fails_when_launchctl_bootstrap_fails(tmp_path):
    proc = _run_install(
        tmp_path,
        args=["--yes", "--vault-inbox", "~/vault/inbox"],
        extra_env={"TABDUMP_TEST_FAIL_BOOTSTRAP": "1"},
    )
    output = proc.stdout + proc.stderr

    assert proc.returncode == 1
    assert "launchctl bootstrap failed" in output

    log = proc.log_path.read_text(encoding="utf-8")
    assert "launchctl bootstrap" in log


def test_install_treats_bootout_io_error_as_expected(tmp_path):
    proc = _run_install(
        tmp_path,
        args=["--yes", "--vault-inbox", "~/vault/inbox"],
        extra_env={"TABDUMP_TEST_BOOTOUT_IO_ERROR": "1"},
    )
    output = proc.stdout + proc.stderr

    assert proc.returncode == 0, output
    assert "[ok] No existing launch agent to stop." in output
    assert "[warn] launchctl bootout reported:" not in output


def test_install_adds_local_bin_path_to_shell_rc(tmp_path):
    proc = _run_install(
        tmp_path,
        args=["--yes", "--vault-inbox", "~/vault/inbox"],
        extra_env={"SHELL": "/bin/zsh"},
    )
    output = proc.stdout + proc.stderr
    zshrc_path = proc.home / ".zshrc"

    assert proc.returncode == 0, output
    assert zshrc_path.exists()
    zshrc_text = zshrc_path.read_text(encoding="utf-8")
    assert 'export PATH="$HOME/.local/bin:$PATH"' in zshrc_text


def test_install_ignores_alias_local_bin_and_still_adds_path_export(tmp_path):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    zshrc_path = home / ".zshrc"
    zshrc_path.write_text('alias nvim=/Users/i.bisarnov/.local/bin/lvim\n', encoding="utf-8")

    proc = _run_install(
        tmp_path,
        args=["--yes", "--vault-inbox", "~/vault/inbox"],
        extra_env={"SHELL": "/bin/zsh"},
    )
    output = proc.stdout + proc.stderr

    assert proc.returncode == 0, output
    zshrc_text = zshrc_path.read_text(encoding="utf-8")
    assert 'alias nvim=/Users/i.bisarnov/.local/bin/lvim' in zshrc_text
    assert 'export PATH="$HOME/.local/bin:$PATH"' in zshrc_text


def test_install_interactive_defaults_to_enabling_llm(tmp_path):
    proc = _run_install(tmp_path, user_input="~/vault/inbox\n\nn\n\n2\n")
    output = proc.stdout + proc.stderr
    data = _read_config(proc.home)

    assert proc.returncode == 0, output
    assert data["llmEnabled"] is True


def test_install_allows_keychain_mode_in_yes_mode_without_inline_key(tmp_path):
    proc = _run_install(
        tmp_path,
        args=[
            "--yes",
            "--vault-inbox",
            "~/vault/inbox",
            "--enable-llm",
            "true",
            "--key-mode",
            "keychain",
        ],
    )
    output = proc.stdout + proc.stderr

    assert proc.returncode == 0, output
    data = _read_config(proc.home)
    assert data["llmEnabled"] is True
    assert "No OpenAI key provided for keychain mode; skipping keychain write" in output


def test_install_reprompts_on_invalid_key_mode_choice(tmp_path):
    proc = _run_install(tmp_path, user_input="~/vault/inbox\n\nn\ny\n9\n2\n")
    output = proc.stdout + proc.stderr

    assert proc.returncode == 0, output
    assert "Please choose 1, 2, or 3." in output

    data = _read_config(proc.home)
    assert data["llmEnabled"] is True


def test_generated_cli_permissions_handles_missing_chrome(tmp_path):
    install_run = _run_install(tmp_path, user_input="~/vault/inbox\n\nn\nn\n")
    assert install_run.returncode == 0, install_run.stdout + install_run.stderr

    monitor_path = install_run.home / "Library" / "Application Support" / "TabDump" / "monitor_tabs.py"
    monitor_path.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
log = os.environ.get("TABDUMP_TEST_LOG")
if log:
  with open(log, "a", encoding="utf-8") as fh:
    fh.write("monitor " + " ".join(sys.argv[1:]) + "\\n")
payload = {
  "status": "noop",
  "reason": "no_new_dump",
  "forced": True,
  "mode": "dump-only",
  "rawDump": "",
  "cleanNote": "",
  "autoSwitched": False,
}
print(json.dumps(payload, sort_keys=True))
""",
        encoding="utf-8",
    )

    cli_run = _run_generated_cli(
        install_run,
        args=["permissions"],
        extra_env={"TABDUMP_TEST_HAS_CHROME": "0", "TABDUMP_TEST_HAS_SAFARI": "1"},
    )
    output = cli_run.stdout + cli_run.stderr

    assert cli_run.returncode == 0, output
    assert "safe permissions check" in output
    assert "Chrome is configured but not installed. Skipping." in output
    assert "System Settings -> Privacy & Security -> Automation -> TabDump -> Safari" in output

    log = install_run.log_path.read_text(encoding="utf-8")
    assert "monitor --force --mode dump-only --json" in log


def test_generated_cli_mode_commands_update_config(tmp_path):
    install_run = _run_install(tmp_path, user_input="~/vault/inbox\n\nn\nn\n")
    assert install_run.returncode == 0, install_run.stdout + install_run.stderr

    show_initial = _run_generated_cli(install_run, args=["mode", "show"])
    out_initial = show_initial.stdout + show_initial.stderr
    assert show_initial.returncode == 0, out_initial
    assert "mode=dump-only, dryRun=true, dryRunPolicy=auto" in out_initial

    set_close = _run_generated_cli(install_run, args=["mode", "dump-close"])
    out_close = set_close.stdout + set_close.stderr
    assert set_close.returncode == 0, out_close
    assert "Dump+Close enabled" in out_close
    data = _read_config(install_run.home)
    assert data["dryRun"] is False
    assert data["dryRunPolicy"] == "manual"

    set_auto = _run_generated_cli(install_run, args=["mode", "auto"])
    out_auto = set_auto.stdout + set_auto.stderr
    assert set_auto.returncode == 0, out_auto
    assert "Auto mode enabled" in out_auto
    data = _read_config(install_run.home)
    assert data["dryRun"] is False
    assert data["dryRunPolicy"] == "auto"

    set_dump_only = _run_generated_cli(install_run, args=["mode", "dump-only"])
    out_dump_only = set_dump_only.stdout + set_dump_only.stderr
    assert set_dump_only.returncode == 0, out_dump_only
    assert "Dump-only enabled" in out_dump_only
    data = _read_config(install_run.home)
    assert data["dryRun"] is True
    assert data["dryRunPolicy"] == "manual"


def test_generated_cli_config_show_get_set(tmp_path):
    install_run = _run_install(tmp_path, user_input="~/vault/inbox\n\nn\nn\n")
    assert install_run.returncode == 0, install_run.stdout + install_run.stderr

    show_run = _run_generated_cli(install_run, args=["config", "show"])
    show_output = show_run.stdout + show_run.stderr
    assert show_run.returncode == 0, show_output
    assert "TabDump config" in show_output
    assert "checkEveryMinutes=60" in show_output
    assert "cooldownMinutes=1440" in show_output
    assert "maxTabs=30" in show_output

    get_run = _run_generated_cli(install_run, args=["config", "get", "checkEveryMinutes"])
    get_output = get_run.stdout + get_run.stderr
    assert get_run.returncode == 0, get_output
    assert get_run.stdout.strip() == "60"

    set_run = _run_generated_cli(
        install_run,
        args=[
            "config",
            "set",
            "checkEveryMinutes",
            "30",
            "cooldownMinutes",
            "2880",
            "maxTabs",
            "45",
            "browsers",
            "Safari,Firefox",
            "llmEnabled",
            "true",
        ],
    )
    set_output = set_run.stdout + set_run.stderr
    assert set_run.returncode == 0, set_output
    assert "[ok] Updated config keys:" in set_output
    assert "Reloaded launch agent to apply schedule changes." in set_output

    data = _read_config(install_run.home)
    assert data["checkEveryMinutes"] == 30
    assert data["cooldownMinutes"] == 2880
    assert data["maxTabs"] == 45
    assert data["browsers"] == ["Safari", "Firefox"]
    assert data["llmEnabled"] is True


def test_generated_cli_config_set_rejects_invalid_key(tmp_path):
    install_run = _run_install(tmp_path, user_input="~/vault/inbox\n\nn\nn\n")
    assert install_run.returncode == 0, install_run.stdout + install_run.stderr

    set_run = _run_generated_cli(install_run, args=["config", "set", "nope", "1"])
    output = set_run.stdout + set_run.stderr
    assert set_run.returncode == 1
    assert "unsupported config key: nope" in output


def test_generated_cli_now_uses_monitor_and_prints_clean_path(tmp_path):
    install_run = _run_install(tmp_path, user_input="~/vault/inbox\n\nn\nn\n")
    assert install_run.returncode == 0, install_run.stdout + install_run.stderr

    monitor_path = install_run.home / "Library" / "Application Support" / "TabDump" / "monitor_tabs.py"
    monitor_path.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
log = os.environ.get("TABDUMP_TEST_LOG")
if log:
  with open(log, "a", encoding="utf-8") as fh:
    fh.write("monitor " + " ".join(sys.argv[1:]) + "\\n")
payload = {
  "status": "ok",
  "reason": "",
  "forced": True,
  "mode": "dump-only",
  "rawDump": "/tmp/raw.md",
  "cleanNote": "/tmp/clean.md",
  "autoSwitched": False,
}
print(json.dumps(payload, sort_keys=True))
""",
        encoding="utf-8",
    )

    cli_run = _run_generated_cli(install_run, args=["now"])
    output = cli_run.stdout + cli_run.stderr
    assert cli_run.returncode == 0, output
    assert "[ok] Clean dump: /tmp/clean.md" in output

    log = install_run.log_path.read_text(encoding="utf-8")
    assert "monitor --force --mode dump-only --json" in log


def test_generated_cli_now_noop_returns_zero(tmp_path):
    install_run = _run_install(tmp_path, user_input="~/vault/inbox\n\nn\nn\n")
    assert install_run.returncode == 0, install_run.stdout + install_run.stderr

    monitor_path = install_run.home / "Library" / "Application Support" / "TabDump" / "monitor_tabs.py"
    monitor_path.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
log = os.environ.get("TABDUMP_TEST_LOG")
if log:
  with open(log, "a", encoding="utf-8") as fh:
    fh.write("monitor " + " ".join(sys.argv[1:]) + "\\n")
payload = {
  "status": "noop",
  "reason": "check_every_gate",
  "forced": True,
  "mode": "dump-only",
  "rawDump": "",
  "cleanNote": "",
  "autoSwitched": False,
}
print(json.dumps(payload, sort_keys=True))
""",
        encoding="utf-8",
    )

    cli_run = _run_generated_cli(install_run, args=["now"])
    output = cli_run.stdout + cli_run.stderr
    assert cli_run.returncode == 0, output
    assert "[info] No clean dump produced (check_every_gate)." in output


def test_generated_cli_now_close_json_passthrough(tmp_path):
    install_run = _run_install(tmp_path, user_input="~/vault/inbox\n\nn\nn\n")
    assert install_run.returncode == 0, install_run.stdout + install_run.stderr

    monitor_path = install_run.home / "Library" / "Application Support" / "TabDump" / "monitor_tabs.py"
    monitor_path.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
log = os.environ.get("TABDUMP_TEST_LOG")
if log:
  with open(log, "a", encoding="utf-8") as fh:
    fh.write("monitor " + " ".join(sys.argv[1:]) + "\\n")
payload = {
  "status": "ok",
  "reason": "",
  "forced": True,
  "mode": "dump-close",
  "rawDump": "/tmp/raw-close.md",
  "cleanNote": "/tmp/clean-close.md",
  "autoSwitched": False,
}
print(json.dumps(payload, sort_keys=True))
""",
        encoding="utf-8",
    )

    cli_run = _run_generated_cli(install_run, args=["now", "--close", "--json"])
    output = cli_run.stdout + cli_run.stderr
    assert cli_run.returncode == 0, output

    payload = json.loads(cli_run.stdout.strip())
    assert payload["mode"] == "dump-close"
    assert payload["cleanNote"] == "/tmp/clean-close.md"

    log = install_run.log_path.read_text(encoding="utf-8")
    assert "monitor --force --mode dump-close --json" in log


def test_generated_cli_status_prints_expected_sections(tmp_path):
    install_run = _run_install(tmp_path, user_input="~/vault/inbox\n\nn\nn\n")
    assert install_run.returncode == 0, install_run.stdout + install_run.stderr

    state_dir = install_run.home / "Library" / "Application Support" / "TabDump"
    monitor_state_path = state_dir / "monitor_state.json"
    legacy_state_path = state_dir / "state.json"
    logs_dir = state_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    monitor_state_path.write_text(
        json.dumps(
            {
                "lastStatus": "noop",
                "lastReason": "check_every_gate",
                "lastProcessed": "/tmp/raw.md",
                "lastClean": "/tmp/clean.md",
            }
        ),
        encoding="utf-8",
    )
    legacy_state_path.write_text(
        json.dumps(
            {
                "lastCheck": 1,
                "lastDump": 2,
                "lastTabs": 3,
            }
        ),
        encoding="utf-8",
    )
    (logs_dir / "monitor.out.log").write_text("out line\n", encoding="utf-8")
    (logs_dir / "monitor.err.log").write_text("err line\n", encoding="utf-8")

    cli_run = _run_generated_cli(install_run, args=["status"])
    output = cli_run.stdout + cli_run.stderr
    assert cli_run.returncode == 0, output
    assert "TabDump status" in output
    assert "- mode:" in output
    assert "- monitor state:" in output
    assert "lastStatus=noop" in output
    assert "- app state (legacy self-gating):" in output
    assert "- launch agent: loaded" in output
    assert "- log tail:" in output
