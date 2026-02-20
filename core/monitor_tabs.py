#!/usr/bin/env python3
"""Monitor tab count and run tabdump + postprocessing when it exceeds a threshold.

This script is intended to be run by a scheduler (launchd/cron) every N minutes.
It is intentionally self-contained (no OpenClaw agent loop needed).

Flow:
- Load config.json (App Support by default)
- Optional checkEveryMinutes gating (to avoid rapid relaunches)
- Run TabDump.app (self-gating handles maxTabs + cooldown)
- Find newest TabDump *.md in vaultInbox (new since start)
- Postprocess it (local classification + optional LLM enrichment) -> creates "(clean)" note
- Append link to today's reading queue note

Env:
- Optional OpenAI API key for LLM enrichment. Resolved by core.postprocess.cli
  (Keychain -> OPENAI_API_KEY env var) when enabled.
"""

import fcntl
import json
import os
import stat
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

HERE = Path(__file__).resolve().parent


def _resolve_postprocess_path() -> Path:
    candidates = (
        HERE / "postprocess" / "cli.py",          # repo runtime (core/monitor_tabs.py)
        HERE / "core" / "postprocess" / "cli.py", # installed runtime (App Support root)
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


POSTPROCESS = _resolve_postprocess_path()
APP_SUPPORT = Path("~/Library/Application Support/TabDump").expanduser()
DEFAULT_CFG = Path(os.environ.get("TABDUMP_CONFIG_PATH", str(APP_SUPPORT / "config.json"))).expanduser()
APP_PATH = Path(os.environ.get("TABDUMP_APP_PATH", "~/Applications/TabDump.app")).expanduser()
APP_EXEC = Path(os.environ.get("TABDUMP_APP_EXEC", str(APP_PATH / "Contents/MacOS/applet"))).expanduser()
STATE_PATH = Path(os.environ.get("TABDUMP_MONITOR_STATE", str(APP_SUPPORT / "monitor_state.json"))).expanduser()
LEGACY_STATE_PATH = Path(os.environ.get("TABDUMP_LEGACY_STATE", str(APP_SUPPORT / "state.json"))).expanduser()
LOCK_PATH = STATE_PATH.with_suffix(".lock")
VERBOSE = False
FORCE = False
JSON_OUTPUT = False
PRINT_CLEAN = False
MODE_OVERRIDE = "config"
VALID_MODES = {"config", "dump-only", "dump-close", "count", "permissions"}
COUNT_ONLY_MAX_TABS = 2_147_483_647
TRUST_RAMP_DAYS = 3
NEW_DUMP_WAIT_SECONDS = float(os.environ.get("TABDUMP_NEW_DUMP_WAIT_SECONDS", "8"))
NEW_DUMP_POLL_SECONDS = float(os.environ.get("TABDUMP_NEW_DUMP_POLL_SECONDS", "0.25"))
DOCS_MORE_LINKS_MODE_MIGRATION_KEY = "docsMoreLinksKindDefault_v1"


def log(msg: str) -> None:
    if not VERBOSE:
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[monitor_tabs] {ts} {msg}", file=sys.stderr)


def load_cfg(p: Path) -> dict:
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def save_cfg(path: Path, cfg: dict) -> None:
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def acquire_lock():
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fh = LOCK_PATH.open("w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(0)
    return fh


def newest_tabdump(vault_inbox: Path) -> Optional[Path]:
    candidates = []
    for p in vault_inbox.glob("TabDump *.md"):
        if "(clean)" in p.name:
            continue
        candidates.append(p)
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _snapshot_newest_tabdump(vault_inbox: Path) -> tuple[Optional[Path], float]:
    newest = newest_tabdump(vault_inbox)
    if newest is None:
        return None, 0.0
    try:
        return newest, newest.stat().st_mtime
    except FileNotFoundError:
        return None, 0.0


def wait_for_new_tabdump(
    vault_inbox: Path,
    baseline_path: Optional[Path],
    baseline_mtime: float,
) -> Optional[Path]:
    """Wait briefly for a new raw dump file produced by the app launch."""
    deadline = time.time() + max(0.0, NEW_DUMP_WAIT_SECONDS)
    poll = max(0.05, NEW_DUMP_POLL_SECONDS)
    while True:
        newest = newest_tabdump(vault_inbox)
        if newest is not None:
            try:
                mtime = newest.stat().st_mtime
            except FileNotFoundError:
                mtime = 0.0
            if baseline_path is None:
                return newest
            if newest != baseline_path or mtime > baseline_mtime:
                return newest
        if time.time() >= deadline:
            return None
        time.sleep(poll)


def parse_args(argv: List[str]) -> None:
    global VERBOSE, FORCE, JSON_OUTPUT, PRINT_CLEAN, MODE_OVERRIDE
    VERBOSE = False
    FORCE = False
    JSON_OUTPUT = False
    PRINT_CLEAN = False
    MODE_OVERRIDE = "config"
    rest = []
    args = list(argv[1:])
    idx = 0
    while idx < len(args):
        arg = args[idx]
        if arg in ("-v", "--verbose"):
            VERBOSE = True
        elif arg == "--force":
            FORCE = True
        elif arg == "--json":
            JSON_OUTPUT = True
        elif arg == "--print-clean":
            PRINT_CLEAN = True
        elif arg == "--mode":
            if idx + 1 >= len(args):
                raise SystemExit("--mode requires one of: config, dump-only, dump-close, count, permissions")
            idx += 1
            MODE_OVERRIDE = args[idx].strip().lower()
            if MODE_OVERRIDE not in VALID_MODES:
                raise SystemExit(f"invalid --mode value: {MODE_OVERRIDE}")
        elif arg.startswith("--mode="):
            MODE_OVERRIDE = arg.split("=", 1)[1].strip().lower()
            if MODE_OVERRIDE not in VALID_MODES:
                raise SystemExit(f"invalid --mode value: {MODE_OVERRIDE}")
        elif arg in ("-h", "--help"):
            print(
                "usage: monitor_tabs.py [--verbose] [--force] [--mode config|dump-only|dump-close|count|permissions] "
                "[--json|--print-clean]",
                file=sys.stderr,
            )
            raise SystemExit(0)
        else:
            rest.append(arg)
        idx += 1
    if rest:
        raise SystemExit(f"unknown args: {' '.join(rest)}")


def _assert_secure_path(path: Path, name: str) -> None:
    st = path.stat()
    if st.st_uid != os.getuid():
        raise PermissionError(f"{name} owner mismatch: {path}")
    if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise PermissionError(f"{name} is group/world writable: {path}")


def _verify_runtime_integrity(cfg_path: Path) -> None:
    must_check = [
        (cfg_path, "config"),
        (Path(__file__).resolve(), "monitor script"),
        (POSTPROCESS, "postprocess script"),
    ]
    renderer_root = HERE / "core" / "renderer"
    postprocess_root = HERE / "core" / "postprocess"
    if renderer_root.exists():
        must_check.append((renderer_root, "renderer package"))
    if postprocess_root.exists():
        must_check.append((postprocess_root, "postprocess package"))
    for path, name in must_check:
        if not path.exists():
            raise FileNotFoundError(f"Missing required {name}: {path}")
        _assert_secure_path(path, name)


def run_tabdump_app() -> None:
    """Launch TabDump in a TCC-friendly way.

    Running the applet binary directly (Contents/MacOS/applet) can sometimes bypass
    the normal GUI launch path and lead to AppleEvents authorization issues.
    Using `open -a` ensures macOS attributes Automation prompts/approvals to the
    TabDump.app bundle, while `-g -j` reduces focus stealing for regular runs.
    """
    if not APP_PATH.exists():
        raise FileNotFoundError(f"TabDump app not found: {APP_PATH}")

    # `open` returns quickly; TabDump itself should run and quit.
    subprocess.run(["/usr/bin/open", "-g", "-j", "-a", str(APP_PATH)], check=True, timeout=30)

    # Give the app a moment to run and write files.
    time.sleep(1.5)


def append_to_queue(vault_inbox: Path, clean_note_path: Path) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    q = vault_inbox / f"Reading Queue {today}.md"
    rel = clean_note_path.name
    entry = f"- [[{rel}]]\n"
    if q.exists():
        txt = q.read_text(encoding="utf-8")
        if entry.strip() in txt:
            return
        q.write_text(txt.rstrip() + "\n" + entry, encoding="utf-8")
    else:
        q.write_text(f"# Reading Queue {today}\n\n" + entry, encoding="utf-8")


def _cfg_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _normalize_docs_more_links_grouping_mode(value: object, default: str = "kind") -> str:
    mode = str(value or "").strip().lower()
    if mode in {"domain", "kind", "energy"}:
        return mode
    return default


def _ensure_docs_more_links_mode_migrated(cfg: dict, state: dict, cfg_path: Path) -> bool:
    migrations = state.get("migrations")
    if not isinstance(migrations, dict):
        migrations = {}
        state["migrations"] = migrations
    if migrations.get(DOCS_MORE_LINKS_MODE_MIGRATION_KEY):
        return False

    changed = False
    raw_mode = str(cfg.get("docsMoreLinksGroupingMode", "")).strip().lower()
    current_mode = _normalize_docs_more_links_grouping_mode(raw_mode, default="kind")
    if raw_mode == "domain":
        cfg["docsMoreLinksGroupingMode"] = "kind"
        changed = True
    elif raw_mode and raw_mode != current_mode:
        cfg["docsMoreLinksGroupingMode"] = current_mode
        changed = True

    migrations[DOCS_MORE_LINKS_MODE_MIGRATION_KEY] = True
    if changed:
        save_cfg(cfg_path, cfg)
    return True


def build_runtime_cfg(cfg: dict) -> tuple[dict, bool]:
    runtime_cfg = dict(cfg)
    changed = False

    if FORCE:
        for key, value in (("checkEveryMinutes", 0), ("cooldownMinutes", 0), ("maxTabs", 0)):
            if runtime_cfg.get(key) != value:
                runtime_cfg[key] = value
                changed = True

    if MODE_OVERRIDE == "dump-only":
        if not _cfg_bool(runtime_cfg.get("dryRun", True), default=True):
            runtime_cfg["dryRun"] = True
            changed = True
    elif MODE_OVERRIDE == "dump-close":
        if _cfg_bool(runtime_cfg.get("dryRun", True), default=True):
            runtime_cfg["dryRun"] = False
            changed = True
    elif MODE_OVERRIDE == "count":
        for key, value in (
            ("checkEveryMinutes", 0),
            ("cooldownMinutes", 0),
            ("maxTabs", COUNT_ONLY_MAX_TABS),
        ):
            if runtime_cfg.get(key) != value:
                runtime_cfg[key] = value
                changed = True
        if not _cfg_bool(runtime_cfg.get("dryRun", True), default=True):
            runtime_cfg["dryRun"] = True
            changed = True
    elif MODE_OVERRIDE == "permissions":
        for key, value in (
            ("checkEveryMinutes", 0),
            ("cooldownMinutes", 0),
            ("maxTabs", 0),
        ):
            if runtime_cfg.get(key) != value:
                runtime_cfg[key] = value
                changed = True
        if not _cfg_bool(runtime_cfg.get("dryRun", True), default=True):
            runtime_cfg["dryRun"] = True
            changed = True

    return runtime_cfg, changed


def emit_result(
    *,
    status: str,
    reason: str = "",
    raw_dump: Optional[Path] = None,
    clean_note: Optional[Path] = None,
    auto_switched: bool = False,
    tab_count: Optional[int] = None,
) -> None:
    payload = {
        "status": status,
        "reason": reason,
        "forced": FORCE,
        "mode": MODE_OVERRIDE,
        "rawDump": str(raw_dump) if raw_dump else "",
        "cleanNote": str(clean_note) if clean_note else "",
        "autoSwitched": auto_switched,
        "tabCount": tab_count,
    }
    if JSON_OUTPUT:
        print(json.dumps(payload, sort_keys=True))
    elif PRINT_CLEAN and clean_note:
        print(str(clean_note))


def record_last_result(
    state: dict,
    *,
    status: str,
    reason: str = "",
    raw_dump: Optional[Path] = None,
    clean_note: Optional[Path] = None,
    error_message: str = "",
) -> None:
    state["lastStatus"] = status
    state["lastReason"] = reason
    state["lastResultAt"] = time.time()
    state["lastResultRawDump"] = str(raw_dump) if raw_dump else ""
    state["lastResultCleanNote"] = str(clean_note) if clean_note else ""
    if error_message:
        state["lastError"] = error_message
    else:
        state.pop("lastError", None)


def _applescript_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def notify_user(title: str, message: str) -> None:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    enabled = str(os.environ.get("TABDUMP_NOTIFY", "1")).strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        return
    try:
        script = f'display notification "{_applescript_escape(message)}" with title "{_applescript_escape(title)}"'
        subprocess.Popen(
            ["/usr/bin/osascript", "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        log(f"warn: notification failed ({exc})")


def maybe_notify_success(cfg: dict, clean_path: Path, auto_switched: bool) -> None:
    now = time.time()
    raw_started = cfg.get("onboardingStartedAt")
    started = None
    if raw_started is not None:
        try:
            started = float(raw_started)
        except Exception:
            started = None
    if not started or started <= 0:
        started = now
        cfg["onboardingStartedAt"] = int(now)
        try:
            save_cfg(DEFAULT_CFG, cfg)
        except Exception as exc:
            log(f"warn: failed to persist onboardingStartedAt ({exc})")

    within_ramp = (now - started) <= TRUST_RAMP_DAYS * 86400
    if within_ramp:
        notify_user(
            "TabDump",
            f"✅ Clean dump ready: {clean_path.name}\nReview top 3 items now.",
        )
    else:
        notify_user("TabDump", f"✅ Clean dump ready: {clean_path.name}")

    if auto_switched:
        notify_user("TabDump", "⚠️ Auto mode switched to Dump+Close for future runs.")


def maybe_auto_switch_dry_run(cfg: dict, cfg_path: Path, state: dict) -> bool:
    policy = str(cfg.get("dryRunPolicy", "manual")).strip().lower()
    if policy != "auto":
        return False
    if not _cfg_bool(cfg.get("dryRun", True), default=True):
        return False

    cfg["dryRun"] = False
    cfg["dryRunPolicy"] = "auto"
    try:
        save_cfg(cfg_path, cfg)
    except Exception as exc:
        log(f"warn: failed to persist auto-switch to config ({exc})")
        return False

    switched_at = time.time()
    state["autoSwitchedAt"] = switched_at
    state["autoSwitchReason"] = "first_clean_dump"
    log("auto-switch: dryRun=false (policy=auto, reason=first_clean_dump)")
    return True


def _legacy_int(value: object) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def snapshot_legacy_state(state_path: Path) -> dict:
    out = {"exists": False, "mtime": 0.0, "lastCheck": None, "lastTabs": None}
    if not state_path.exists():
        return out
    out["exists"] = True
    try:
        out["mtime"] = float(state_path.stat().st_mtime)
    except Exception:
        out["mtime"] = 0.0
    try:
        data = json.loads(state_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return out
    out["lastCheck"] = _legacy_int(data.get("lastCheck"))
    out["lastTabs"] = _legacy_int(data.get("lastTabs"))
    return out


def wait_for_fresh_legacy_tab_count(state_path: Path, baseline: dict) -> Optional[int]:
    deadline = time.time() + max(0.0, NEW_DUMP_WAIT_SECONDS)
    poll = max(0.05, NEW_DUMP_POLL_SECONDS)
    while True:
        current = snapshot_legacy_state(state_path)
        tab_count = current.get("lastTabs")
        if tab_count is not None:
            fresh = False
            if baseline.get("exists"):
                if float(current.get("mtime") or 0.0) > float(baseline.get("mtime") or 0.0):
                    fresh = True
                else:
                    baseline_last_check = baseline.get("lastCheck")
                    current_last_check = current.get("lastCheck")
                    if (
                        baseline_last_check is not None
                        and current_last_check is not None
                        and int(current_last_check) > int(baseline_last_check)
                    ):
                        fresh = True
            elif current.get("exists"):
                fresh = True
            if fresh:
                return int(tab_count)

        if time.time() >= deadline:
            return None
        time.sleep(poll)


def main() -> int:
    parse_args(sys.argv)
    _lock_fh = acquire_lock()
    log("start")
    _verify_runtime_integrity(DEFAULT_CFG)
    cfg = load_cfg(DEFAULT_CFG)
    state = load_state()
    if _ensure_docs_more_links_mode_migrated(cfg, state, DEFAULT_CFG):
        save_state(state)
    persistent_cfg = dict(cfg)
    runtime_cfg, runtime_cfg_overridden = build_runtime_cfg(cfg)
    if runtime_cfg_overridden:
        save_cfg(DEFAULT_CFG, runtime_cfg)
    cfg_for_run = runtime_cfg if runtime_cfg_overridden else cfg
    vault_inbox = Path(cfg_for_run["vaultInbox"]).expanduser().resolve()
    auto_switched = False
    cfg_after_run_persistent = dict(persistent_cfg)
    try:
        if MODE_OVERRIDE == "count":
            baseline_legacy_state = snapshot_legacy_state(LEGACY_STATE_PATH)
            run_tabdump_app()
            tab_count = wait_for_fresh_legacy_tab_count(LEGACY_STATE_PATH, baseline_legacy_state)
            if tab_count is None:
                log("error: count mode could not confirm fresh lastTabs from legacy state")
                record_last_result(state, status="error", reason="count_unavailable")
                save_state(state)
                emit_result(status="error", reason="count_unavailable")
                return 1
            state["lastCount"] = tab_count
            state["lastCountAt"] = time.time()
            record_last_result(state, status="ok", reason="count_only")
            save_state(state)
            emit_result(status="ok", reason="count_only", tab_count=tab_count)
            return 0

        if MODE_OVERRIDE == "permissions":
            baseline_path, baseline_mtime = _snapshot_newest_tabdump(vault_inbox)
            log("run TabDump.app (permissions mode)")
            run_tabdump_app()
            newest = wait_for_new_tabdump(vault_inbox, baseline_path, baseline_mtime)
            if newest is None:
                log("permissions: no new TabDump *.md observed")
                record_last_result(state, status="noop", reason="permissions_no_new_dump")
                save_state(state)
                emit_result(status="noop", reason="permissions_no_new_dump")
                return 0

            log(f"permissions: raw dump observed ({newest})")
            record_last_result(state, status="ok", reason="permissions_raw_dump", raw_dump=newest)
            save_state(state)
            emit_result(status="ok", reason="permissions_raw_dump", raw_dump=newest)
            return 0

        now = time.time()
        check_every = int(cfg_for_run.get("checkEveryMinutes", 60))
        last_check = float(state.get("lastCheck", 0))
        if not FORCE and check_every > 0 and last_check and (now - last_check) < check_every * 60:
            log(f"skip: checkEveryMinutes gate (check_every={check_every}, last_check={last_check}, now={now})")
            record_last_result(state, status="noop", reason="check_every_gate")
            save_state(state)
            emit_result(status="noop", reason="check_every_gate")
            return 0
        state["lastCheck"] = now

        baseline_path, baseline_mtime = _snapshot_newest_tabdump(vault_inbox)
        log("run TabDump.app")
        run_tabdump_app()

        # Wait briefly for a fresh dump produced by this launch.
        newest = wait_for_new_tabdump(vault_inbox, baseline_path, baseline_mtime)
        if newest is None:
            log("skip: no new TabDump *.md found")
            record_last_result(state, status="noop", reason="no_new_dump")
            save_state(state)
            emit_result(status="noop", reason="no_new_dump")
            return 0
        last_processed = state.get("lastProcessed")
        if last_processed and str(newest) == last_processed:
            log(f"skip: newest already processed ({newest})")
            record_last_result(state, status="noop", reason="already_processed", raw_dump=newest)
            save_state(state)
            emit_result(status="noop", reason="already_processed", raw_dump=newest)
            return 0

        def _env_bool(value: object, default: bool = False) -> str:
            if value is None:
                return "1" if default else "0"
            if isinstance(value, bool):
                return "1" if value else "0"
            if isinstance(value, (int, float)):
                return "1" if value else "0"
            v = str(value).strip().lower()
            if v in {"1", "true", "yes", "y", "on"}:
                return "1"
            if v in {"0", "false", "no", "n", "off"}:
                return "0"
            return "1" if default else "0"

        env = dict(os.environ)
        env["TABDUMP_LLM_ENABLED"] = _env_bool(cfg_for_run.get("llmEnabled", False), default=False)
        env["TABDUMP_TAG_MODEL"] = str(cfg_for_run.get("tagModel", "gpt-4.1-mini"))
        env["TABDUMP_LLM_REDACT"] = _env_bool(cfg_for_run.get("llmRedact", True), default=True)
        env["TABDUMP_LLM_REDACT_QUERY"] = _env_bool(cfg_for_run.get("llmRedactQuery", True), default=True)
        env["TABDUMP_LLM_TITLE_MAX"] = str(cfg_for_run.get("llmTitleMax", 200))
        env["TABDUMP_LLM_ACTION_POLICY"] = str(cfg_for_run.get("llmActionPolicy", "hybrid")).strip().lower()
        env["TABDUMP_MIN_LLM_COVERAGE"] = str(cfg_for_run.get("minLlmCoverage", 0.7))
        env["TABDUMP_MAX_ITEMS"] = str(cfg_for_run.get("maxItems", 0))
        env["TABDUMP_DOCS_MORE_LINKS_GROUPING_MODE"] = _normalize_docs_more_links_grouping_mode(
            cfg_for_run.get("docsMoreLinksGroupingMode", "kind"),
            default="kind",
        )
        pp = subprocess.run(
            [sys.executable, str(POSTPROCESS), str(newest)],
            capture_output=True,
            text=True,
            timeout=240,
            env=env,
        )
        if pp.returncode == 3:
            log("skip: postprocess indicated no-op (code 3)")
            state["lastProcessed"] = str(newest)
            state["lastProcessedAt"] = time.time()
            record_last_result(state, status="noop", reason="postprocess_noop", raw_dump=newest)
            save_state(state)
            emit_result(status="noop", reason="postprocess_noop", raw_dump=newest)
            return 0
        if pp.returncode != 0:
            log(f"error: postprocess failed (code {pp.returncode}) {pp.stderr.strip() or pp.stdout.strip()}")
            raise RuntimeError(f"postprocess failed: {pp.stderr.strip() or pp.stdout.strip()}")
        clean_path = Path(pp.stdout.strip()).resolve()
        log(f"postprocess ok: {clean_path}")

        append_to_queue(vault_inbox, clean_path)
        log("append to queue ok")

        state["lastProcessed"] = str(newest)
        state["lastProcessedAt"] = time.time()
        state["lastClean"] = str(clean_path)
        auto_switched = maybe_auto_switch_dry_run(cfg_after_run_persistent, DEFAULT_CFG, state)
        maybe_notify_success(cfg_after_run_persistent, clean_path, auto_switched)
        record_last_result(
            state,
            status="ok",
            raw_dump=newest,
            clean_note=clean_path,
        )
        save_state(state)
        emit_result(status="ok", raw_dump=newest, clean_note=clean_path, auto_switched=auto_switched)
        log("done")

        return 0
    except Exception as exc:
        record_last_result(
            state,
            status="error",
            reason="run_failed",
            error_message=str(exc),
        )
        try:
            save_state(state)
        except Exception as state_exc:
            log(f"warn: failed to persist error state ({state_exc})")
        raise
    finally:
        if runtime_cfg_overridden:
            try:
                save_cfg(DEFAULT_CFG, cfg_after_run_persistent)
            except Exception as exc:
                log(f"warn: failed to restore config after runtime override ({exc})")


if __name__ == "__main__":
    raise SystemExit(main())
