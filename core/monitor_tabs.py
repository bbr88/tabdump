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
LOCK_PATH = STATE_PATH.with_suffix(".lock")
VERBOSE = False


def log(msg: str) -> None:
    if not VERBOSE:
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[monitor_tabs] {ts} {msg}", file=sys.stderr)


def load_cfg(p: Path) -> dict:
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


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


def parse_args(argv: List[str]) -> None:
    global VERBOSE
    rest = []
    for arg in argv[1:]:
        if arg in ("-v", "--verbose"):
            VERBOSE = True
        elif arg in ("-h", "--help"):
            print("usage: monitor_tabs.py [--verbose]", file=sys.stderr)
            raise SystemExit(0)
        else:
            rest.append(arg)
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
    TabDump.app bundle.
    """
    if not APP_PATH.exists():
        raise FileNotFoundError(f"TabDump app not found: {APP_PATH}")

    # `open` returns quickly; TabDump itself should run and quit.
    subprocess.run(["/usr/bin/open", "-a", str(APP_PATH)], check=True, timeout=30)

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


def main() -> int:
    parse_args(sys.argv)
    _lock_fh = acquire_lock()
    log("start")
    _verify_runtime_integrity(DEFAULT_CFG)
    cfg = load_cfg(DEFAULT_CFG)
    vault_inbox = Path(cfg["vaultInbox"]).expanduser().resolve()

    state = load_state()
    now = time.time()
    check_every = int(cfg.get("checkEveryMinutes", 5))
    last_check = float(state.get("lastCheck", 0))
    if check_every > 0 and last_check and (now - last_check) < check_every * 60:
        log(f"skip: checkEveryMinutes gate (check_every={check_every}, last_check={last_check}, now={now})")
        return 0
    state["lastCheck"] = now

    start_ts = time.time()
    log("run TabDump.app")
    run_tabdump_app()

    # Find newest dump and postprocess it (only if created after this run started)
    newest = newest_tabdump(vault_inbox)
    if newest is None:
        log("skip: no new TabDump *.md found")
        save_state(state)
        return 0
    last_processed = state.get("lastProcessed")
    if last_processed and str(newest) == last_processed:
        log(f"skip: newest already processed ({newest})")
        save_state(state)
        return 0
    if newest.stat().st_mtime < (start_ts - 2):
        log(f"skip: newest predates run start ({newest})")
        save_state(state)
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
    env["TABDUMP_LLM_ENABLED"] = _env_bool(cfg.get("llmEnabled", False), default=False)
    env["TABDUMP_TAG_MODEL"] = str(cfg.get("tagModel", "gpt-4.1-mini"))
    env["TABDUMP_LLM_REDACT"] = _env_bool(cfg.get("llmRedact", True), default=True)
    env["TABDUMP_LLM_REDACT_QUERY"] = _env_bool(cfg.get("llmRedactQuery", True), default=True)
    env["TABDUMP_LLM_TITLE_MAX"] = str(cfg.get("llmTitleMax", 200))
    env["TABDUMP_MAX_ITEMS"] = str(cfg.get("maxItems", 0))
    pp = subprocess.run([sys.executable, str(POSTPROCESS), str(newest)], capture_output=True, text=True, timeout=240,
                        env=env)
    if pp.returncode == 3:
        log("skip: postprocess indicated no-op (code 3)")
        state["lastProcessed"] = str(newest)
        state["lastProcessedAt"] = time.time()
        save_state(state)
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
    save_state(state)
    log("done")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
