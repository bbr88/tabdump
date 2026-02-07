#!/usr/bin/env python3
"""Post-process a TabDump markdown file.

Pipeline:
- Parse Markdown links
- Deduplicate URLs
- Classify/enrich (topic/kind/action/score) via LLM
- Pretty render into a structured Markdown note
- Write companion note: "<orig stem> (clean).md"
"""

import json
import os
import ipaddress
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

def _find_root(path: Path) -> Path:
    candidates = [
        path.parent,
        path.parent.parent,
        path.parent.parent.parent,
    ]
    for candidate in candidates:
        if (candidate / "core" / "renderer" / "renderer_v3.py").exists():
            return candidate
    return path.parent.parent


ROOT = _find_root(Path(__file__).resolve())
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from core.renderer.renderer_v3 import render_markdown  # type: ignore
TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "mkt_tok",
    "msclkid",
    "ref",
    "ref_src",
    "spm",
    "yclid",
}
CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
SENSITIVE_KV_RE = re.compile(r"(?i)\b(token|secret|api[-_]?key|auth|session|password|passwd|code|sig|signature)\s*[:=]\s*([^\s&]+)")
REDACT_LLM = os.environ.get("TABDUMP_LLM_REDACT", "1").strip().lower() not in {"0", "false", "no"}
REDACT_QUERY = os.environ.get("TABDUMP_LLM_REDACT_QUERY", "1").strip().lower() not in {"0", "false", "no"}
MAX_LLM_TITLE = int(os.environ.get("TABDUMP_LLM_TITLE_MAX", "200") or 0)
MAX_ITEMS = int(os.environ.get("TABDUMP_MAX_ITEMS", "0") or 0)
KEYCHAIN_SERVICE = os.environ.get("TABDUMP_KEYCHAIN_SERVICE", "TabDump")
KEYCHAIN_ACCOUNT = os.environ.get("TABDUMP_KEYCHAIN_ACCOUNT", "openai")
SENSITIVE_HOSTS = {
    "accounts.google.com",
    "auth.openai.com",
    "platform.openai.com",
}
AUTH_PATH_HINTS = (
    "/login",
    "/signin",
    "/sign-in",
    "/oauth",
    "/sso",
    "/session",
    "/api-keys",
    "/credentials",
    "/token",
)
SENSITIVE_QUERY_KEYS = (
    "token",
    "secret",
    "api_key",
    "apikey",
    "session",
    "code",
    "sig",
    "signature",
    "password",
)


def normalize_url(url: str) -> str:
    url = url.strip()
    try:
        u = urllib.parse.urlsplit(url)
    except Exception:
        return url

    if not u.netloc:
        return url

    # drop common tracking params + utm_*
    q = urllib.parse.parse_qsl(u.query, keep_blank_values=True)
    q2 = []
    for k, v in q:
        kl = k.lower()
        if kl.startswith("utm_") or kl in TRACKING_PARAMS:
            continue
        q2.append((k, v))
    q2.sort(key=lambda kv: (kv[0], kv[1]))
    query = urllib.parse.urlencode(q2, doseq=True)

    # normalize scheme + netloc case
    scheme = (u.scheme or "https").lower()
    netloc = u.netloc.lower()

    path = u.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    # drop fragment for dedup + cleaner output
    return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))


def _strip_control_chars(value: str) -> str:
    return CONTROL_CHARS_RE.sub("", value)


def redact_text_for_llm(text: str) -> str:
    text = _strip_control_chars(text)
    text = SENSITIVE_KV_RE.sub(lambda m: f"{m.group(1)}=[REDACTED]", text)
    if MAX_LLM_TITLE > 0 and len(text) > MAX_LLM_TITLE:
        text = text[:MAX_LLM_TITLE] + "..."
    return text


def redact_url_for_llm(url: str) -> str:
    url = url.strip()
    try:
        u = urllib.parse.urlsplit(url)
    except Exception:
        return url

    if not u.netloc:
        return url

    scheme = (u.scheme or "https").lower()
    netloc = u.netloc.lower()
    path = u.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    query = ""
    if u.query:
        if REDACT_QUERY:
            keys = [k for k, _ in urllib.parse.parse_qsl(u.query, keep_blank_values=True)]
            query = urllib.parse.urlencode([(k, "REDACTED") for k in keys], doseq=True)
        else:
            query = u.query

    return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))


def domain_of(url: str) -> str:
    try:
        u = urllib.parse.urlsplit(url)
        return (u.netloc or "").lower() or "(unknown)"
    except Exception:
        return "(unknown)"


@dataclass
class Item:
    title: str
    url: str
    norm_url: str
    clean_url: str
    domain: str
    browser: Optional[str]


def _parse_markdown_link_line(line: str) -> Optional[Tuple[str, str]]:
    s = line.strip()
    if not s.startswith("- ["):
        return None

    i = 3
    title_chars: List[str] = []
    escaped = False
    while i < len(s):
        ch = s[i]
        if escaped:
            title_chars.append(ch)
            escaped = False
            i += 1
            continue
        if ch == "\\":
            escaped = True
            i += 1
            continue
        if ch == "]":
            break
        title_chars.append(ch)
        i += 1
    if i >= len(s) or s[i] != "]":
        return None
    i += 1

    while i < len(s) and s[i].isspace():
        i += 1
    if i >= len(s) or s[i] != "(":
        return None
    i += 1

    depth = 1
    url_chars: List[str] = []
    escaped = False
    while i < len(s):
        ch = s[i]
        if escaped:
            url_chars.append(ch)
            escaped = False
            i += 1
            continue
        if ch == "\\":
            escaped = True
            i += 1
            continue
        if ch == "(":
            depth += 1
            url_chars.append(ch)
            i += 1
            continue
        if ch == ")":
            depth -= 1
            if depth == 0:
                i += 1
                break
            url_chars.append(ch)
            i += 1
            continue
        url_chars.append(ch)
        i += 1

    if depth != 0:
        return None
    if s[i:].strip():
        return None

    title = "".join(title_chars).strip()
    url = "".join(url_chars).strip()
    if not title or not url:
        return None
    return title, url


def extract_items(md: str) -> List[Item]:
    items: List[Item] = []
    current_browser: Optional[str] = None
    for line in md.splitlines():
        if line.startswith("## "):
            if line.startswith("## Chrome"):
                current_browser = "chrome"
            elif line.startswith("## Safari"):
                current_browser = "safari"
            elif line.startswith("## Firefox"):
                current_browser = "firefox"
        if line.startswith("### "):
            # ignore window headings
            continue
        parsed = _parse_markdown_link_line(line)
        if parsed is None:
            continue
        title, url = parsed
        clean_url = normalize_url(url)
        items.append(
            Item(
                title=title,
                url=url,
                norm_url=clean_url,
                clean_url=clean_url,
                domain=domain_of(clean_url),
                browser=current_browser,
            )
        )
    return items


def _key_from_keychain() -> Optional[str]:
    security_path = "/usr/bin/security"
    if not Path(security_path).exists():
        return None
    cmd = [
        security_path,
        "find-generic-password",
        "-s",
        KEYCHAIN_SERVICE,
        "-a",
        KEYCHAIN_ACCOUNT,
        "-w",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value or None


def resolve_openai_api_key() -> Optional[str]:
    value = _key_from_keychain()
    if value:
        return value
    value = os.environ.get("OPENAI_API_KEY")
    if value:
        value = value.strip()
    return value or None


def openai_chat_json(system: str, user: str, model: Optional[str] = None) -> dict:
    api_key = resolve_openai_api_key()
    if not api_key:
        raise RuntimeError(
            "OpenAI API key not found. Checked: "
            f"Keychain (service={KEYCHAIN_SERVICE}, account={KEYCHAIN_ACCOUNT}), "
            "env OPENAI_API_KEY."
        )

    model = model or os.environ.get("TABDUMP_TAG_MODEL") or "gpt-4.1-mini"

    #todo: Use OpenAI Responses API. For now, keep it minimal via Chat Completions-compatible endpoint.
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


def _safe_topic(value: object, domain: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if domain:
        return domain.replace(".", "-")
    return "misc"


def _safe_kind(value: object) -> str:
    allowed = {"video", "repo", "paper", "docs", "article", "tool", "misc", "local", "auth", "internal"}
    if isinstance(value, str):
        v = value.strip().lower()
        if v in allowed:
            return v
    return "misc"


def _safe_action(value: object) -> str:
    allowed = {"read", "watch", "reference", "build", "triage", "ignore"}
    if isinstance(value, str):
        v = value.strip().lower()
        if v in allowed:
            return v
    return "triage"


def _safe_score(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        v = int(value)
    except Exception:
        return None
    if v < 0:
        v = 0
    if v > 5:
        v = 5
    return v


def _safe_prio(value: object) -> Optional[str]:
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"p1", "p2", "p3"}:
            return v
    return None


def _extract_created_ts(src_path: Path, fallback: str) -> str:
    try:
        head = src_path.read_text(encoding="utf-8", errors="replace").splitlines()[:30]
    except Exception:
        return fallback
    for line in head:
        m = re.match(r'^created:\s*"?(.+?)"?$', line.strip())
        if m:
            return m.group(1)
    return fallback


def _extract_frontmatter_value(src_path: Path, key: str) -> Optional[str]:
    try:
        head = src_path.read_text(encoding="utf-8", errors="replace").splitlines()[:80]
    except Exception:
        return None
    if not head or head[0].strip() != "---":
        return None
    pattern = re.compile(rf"^{re.escape(key)}:\s*\"?(.+?)\"?\s*$")
    for line in head[1:]:
        if line.strip() == "---":
            break
        m = pattern.match(line.strip())
        if m:
            return m.group(1)
    return None


def _chunked(items: List, size: int) -> List[List]:
    if size <= 0:
        return [items]
    return [items[i : i + size] for i in range(0, len(items), size)]


def _call_with_retries(system: str, user: str, tries: int = 3, backoff_sec: float = 1.5) -> dict:
    last_err: Optional[Exception] = None
    for attempt in range(tries):
        try:
            return openai_chat_json(system=system, user=user)
        except Exception as e:
            last_err = e
            if attempt == tries - 1:
                raise
            time.sleep(backoff_sec * (attempt + 1))
    if last_err is not None:
        raise last_err
    raise RuntimeError("LLM call failed with unknown error")


def _is_private_or_loopback_host(host: str) -> bool:
    host = host.strip().lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    if host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(ip.is_private or ip.is_loopback or ip.is_link_local)


def _is_sensitive_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url)
    except Exception:
        return True

    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        return True

    host = (parsed.hostname or "").lower()
    if not host:
        return True
    if host in SENSITIVE_HOSTS:
        return True
    if _is_private_or_loopback_host(host):
        return True

    lower_url = url.lower()
    if any(hint in lower_url for hint in AUTH_PATH_HINTS):
        return True

    for key, _ in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        if key.strip().lower() in SENSITIVE_QUERY_KEYS:
            return True
    return False


def _default_kind_action(url: str) -> Tuple[str, str]:
    lower_url = url.lower()
    try:
        parsed = urllib.parse.urlsplit(url)
    except Exception:
        return "internal", "ignore"
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()
    if not host:
        return "internal", "ignore"

    if scheme == "file" or _is_private_or_loopback_host(host):
        return "local", "ignore"
    if any(hint in lower_url for hint in AUTH_PATH_HINTS) or host in SENSITIVE_HOSTS:
        return "auth", "ignore"
    if scheme not in {"http", "https"}:
        return "internal", "ignore"
    return "misc", "triage"


def build_clean_note(src_path: Path, items: List[Item], dump_id: Optional[str] = None) -> Tuple[str, dict]:
    # Ask LLM for enrichment
    system = (
        "You are a strict classifier for browser tabs. "
        "Return ONLY valid JSON."
    )

    cls_map: Dict[int, dict] = {}
    indexed_items = list(enumerate(items))
    url_to_idx = {it.norm_url: idx for idx, it in indexed_items}
    sensitive_items: Dict[int, bool] = {idx: _is_sensitive_url(it.clean_url) for idx, it in indexed_items}
    indexed_for_cls = [(idx, it) for idx, it in indexed_items if not sensitive_items[idx]]
    if MAX_ITEMS > 0 and len(indexed_for_cls) > MAX_ITEMS:
        indexed_for_cls = indexed_for_cls[:MAX_ITEMS]
    chunk_size = int(os.environ.get("TABDUMP_CLASSIFY_CHUNK", "30"))
    for chunk in _chunked(indexed_for_cls, chunk_size):
        lines = []
        for idx, it in chunk:
            title = redact_text_for_llm(it.title) if REDACT_LLM else it.title
            url = redact_url_for_llm(it.clean_url) if REDACT_LLM else it.clean_url
            lines.append(f"- {idx} | {title} | {url} | {it.domain}")
        user = (
            "For each tab, provide:\n"
            "- topic: short, lowercase, kebab-case (e.g. distributed-systems, postgres, llm)\n"
            "- kind: one of [video, repo, paper, docs, article, tool, misc, local, auth, internal]\n"
            "- action: one of [read, watch, reference, build, triage, ignore]\n"
            "- score: integer 1-5 (importance)\n\n"
            "Return JSON like:\n"
            "{\n"
            "  \"items\": [\n"
            "    {\"id\": 123, \"topic\": \"...\", \"kind\": \"...\", \"action\": \"...\", \"score\": 3}\n"
            "  ]\n"
            "}\n\n"
            "Use the provided id as-is; do not invent ids.\n\n"
            + "\n".join(lines)
        )
        try:
            out = _call_with_retries(system=system, user=user)
        except Exception as e:
            print(f"LLM classify failed (chunk size {len(chunk)}): {e}", file=sys.stderr)
            out = {"items": []}

        for x in out.get("items", []):
            if not isinstance(x, dict):
                continue
            idx_raw = x.get("id")
            idx: Optional[int] = None
            if idx_raw is not None:
                try:
                    idx = int(idx_raw)
                except Exception:
                    idx = None
            if idx is None:
                url = x.get("url")
                if url:
                    idx = url_to_idx.get(normalize_url(str(url)))
            if idx is None:
                continue
            cls_map[idx] = x

    enriched: List[dict] = []
    for idx, it in indexed_items:
        cls = cls_map.get(idx, {})
        if sensitive_items.get(idx):
            kind, action = _default_kind_action(it.clean_url)
            topic = _safe_topic(None, it.domain)
            score = 3
        else:
            topic = _safe_topic(cls.get("topic"), it.domain)
            kind = _safe_kind(cls.get("kind"))
            action = _safe_action(cls.get("action"))
            score = _safe_score(cls.get("score"))

        entry = {
            "title": it.title,
            "url": it.clean_url,
            "domain": it.domain,
            "browser": it.browser,
            "kind": kind,
            "topics": [{"slug": topic, "title": topic.replace('-', ' ').title(), "confidence": 0.8}],
            "intent": {"action": action, "confidence": (score or 3) / 5},
            "flags": {},
        }
        enriched.append(entry)

    ts = _extract_created_ts(src_path, fallback=time.strftime("%Y-%m-%d %H-%M-%S"))
    meta = {
        "created": ts,
        "source": src_path.name,
        "allowlistPatterns": [],
        "skipPrefixes": [],
    }
    if dump_id:
        meta["tabdump_id"] = dump_id
    counts = {
        "total": len(enriched),
        "dumped": len(enriched),
        "closed": 0,
        "kept": 0,
    }
    payload = {
        "meta": meta,
        "counts": counts,
        "items": enriched,
    }

    md = render_markdown(payload, cfg={})
    return md, meta


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print("usage: postprocess_tabdump.py <path-to-tabdump-md>", file=sys.stderr)
        return 2

    src = Path(argv[1]).expanduser().resolve()
    md = src.read_text(encoding="utf-8", errors="replace")
    dump_id = _extract_frontmatter_value(src, "tabdump_id")
    if not dump_id:
        print("Missing tabdump_id frontmatter; refusing to postprocess.", file=sys.stderr)
        return 4
    items = extract_items(md)
    if not items:
        print("No tab items found in the note; nothing to do.", file=sys.stderr)
        return 3

    clean_text, _fm = build_clean_note(src, items, dump_id=dump_id)

    clean_path = src.with_name(src.stem + " (clean)" + src.suffix)
    clean_path.write_text(clean_text, encoding="utf-8")
    print(str(clean_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
