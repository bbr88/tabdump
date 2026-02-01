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
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pretty_renderer import render_markdown
LINK_RE = re.compile(r"^-\s+\[(?P<title>[^\]]+)\]\((?P<url>[^\)]+)\)\s*$")
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
        m = LINK_RE.match(line)
        if not m:
            continue
        title = m.group("title").strip()
        url = m.group("url").strip()
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


def openai_chat_json(system: str, user: str, model: Optional[str] = None) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

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


def _chunked(items: List[Item], size: int) -> List[List[Item]]:
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


def build_clean_note(src_path: Path, items: List[Item]) -> Tuple[str, dict]:
    # Dedup by normalized URL (keep first title)
    seen = set()
    dedup: List[Item] = []
    for it in items:
        if it.norm_url in seen:
            continue
        seen.add(it.norm_url)
        dedup.append(it)

    # Ask LLM for enrichment
    system = (
        "You are a strict classifier for browser tabs. "
        "Return ONLY valid JSON."
    )

    cls_map: Dict[str, dict] = {}
    chunk_size = int(os.environ.get("TABDUMP_CLASSIFY_CHUNK", "30"))
    for chunk in _chunked(dedup, chunk_size):
        lines = [f"- {it.title} | {it.clean_url} | {it.domain}" for it in chunk]
        user = (
            "For each tab, provide:\n"
            "- topic: short, lowercase, kebab-case (e.g. distributed-systems, postgres, llm)\n"
            "- kind: one of [video, repo, paper, docs, article, tool, misc, local, auth, internal]\n"
            "- action: one of [read, watch, reference, build, triage, ignore]\n"
            "- score: integer 1-5 (importance)\n\n"
            "Return JSON like:\n"
            "{\n"
            "  \"items\": [\n"
            "    {\"url\": \"...\", \"topic\": \"...\", \"kind\": \"...\", \"action\": \"...\", \"score\": 3}\n"
            "  ]\n"
            "}\n\n"
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
            url = x.get("url")
            if not url:
                continue
            cls_map[normalize_url(url)] = x

    enriched: List[dict] = []
    for it in dedup:
        cls = cls_map.get(it.norm_url, {})
        topic = _safe_topic(cls.get("topic"), it.domain)
        kind = _safe_kind(cls.get("kind"))
        action = _safe_action(cls.get("action"))
        score = _safe_score(cls.get("score"))
        prio = _safe_prio(cls.get("prio"))

        entry = {
            "title": it.title,
            "url": it.clean_url,
            "topic": topic,
            "kind": kind,
            "action": action,
            "domain": it.domain,
            "browser": it.browser,
        }
        if score is not None:
            entry["score"] = score
        if prio is not None:
            entry["prio"] = prio
        enriched.append(entry)

    ts = _extract_created_ts(src_path, fallback=time.strftime("%Y-%m-%d %H-%M-%S"))
    meta = {
        "ts": ts,
        "sourceFile": src_path.name,
        "counts": {
            "total": len(enriched),
            "dumped": len(enriched),
            "closed": 0,
            "kept": 0,
        },
        "allowlistPatterns": [],
        "skipPrefixes": [],
    }

    md = render_markdown(enriched, meta, cfg={})
    return md, meta


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print("usage: postprocess_tabdump.py <path-to-tabdump-md>", file=sys.stderr)
        return 2

    src = Path(argv[1]).expanduser().resolve()
    md = src.read_text(encoding="utf-8", errors="replace")
    items = extract_items(md)
    if not items:
        print("No tab items found in the note; nothing to do.", file=sys.stderr)
        return 3

    clean_text, _fm = build_clean_note(src, items)

    clean_path = src.with_name(src.stem + " (clean)" + src.suffix)
    clean_path.write_text(clean_text, encoding="utf-8")
    print(str(clean_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
