#!/usr/bin/env python3
"""Post-process a TabDump markdown file.

- Parses Markdown links in bullet list form: - [Title](URL)
- Deduplicates URLs
- Groups by domain
- Calls OpenAI to assign topic tags (lightweight, from title+url only)
- Writes a cleaned companion note: "<orig stem> (clean).md"

Requirements:
- OPENAI_API_KEY env var

This is v1: no PDF content fetching yet.
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


def extract_items(md: str) -> List[Item]:
    items: List[Item] = []
    for line in md.splitlines():
        m = LINK_RE.match(line)
        if not m:
            continue
        title = m.group("title").strip()
        url = m.group("url").strip()
        clean_url = normalize_url(url)
        items.append(Item(title=title, url=url, norm_url=clean_url, clean_url=clean_url, domain=domain_of(clean_url)))
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


def build_clean_note(src_path: Path, items: List[Item]) -> Tuple[str, dict]:
    # Dedup by normalized URL (keep first title)
    seen = set()
    dedup: List[Item] = []
    for it in items:
        if it.norm_url in seen:
            continue
        seen.add(it.norm_url)
        dedup.append(it)

    # Group by domain
    by_domain: Dict[str, List[Item]] = {}
    for it in dedup:
        by_domain.setdefault(it.domain, []).append(it)

    # Ask LLM for topic tags per item
    system = (
        "You are a strict classifier that assigns concise topic tags to browser tabs. "
        "Return ONLY valid JSON."
    )

    # Keep prompt compact: domain + title + url
    domain_blocks = []
    for dom, arr in sorted(by_domain.items()):
        lines = [f"- {a.title} | {a.clean_url}" for a in arr[:80]]  # guard
        domain_blocks.append(f"DOMAIN: {dom}\n" + "\n".join(lines))

    user = (
        "Given these browser tabs grouped by domain, assign topic tags.\n\n"
        "Rules:\n"
        "- Tags must be short, lowercase, kebab-case (e.g. distributed-systems, postgres, llm, video).\n"
        "- Provide 1-3 tags per item.\n"
        "- Also provide a small set of globalTags (max 12) that summarize the whole dump.\n\n"
        "Return JSON like:\n"
        "{\n"
        "  \"globalTags\": [..],\n"
        "  \"items\": [{\"url\": \"...\", \"tags\": [..]}]\n"
        "}\n\n"
        + "\n\n".join(domain_blocks)
    )

    out = openai_chat_json(system=system, user=user)
    tag_map = {normalize_url(x["url"]): x.get("tags", []) for x in out.get("items", []) if isinstance(x, dict) and x.get("url")}
    global_tags = out.get("globalTags", [])

    # Build topic buckets
    topic_buckets: Dict[str, List[Item]] = {}
    for it in dedup:
        tags = tag_map.get(it.norm_url, [])
        primary = tags[0] if tags else it.domain.replace(".", "-")
        topic_buckets.setdefault(primary, []).append(it)

    ts = time.strftime("%Y-%m-%d %H-%M-%S")

    fm = {
        "created": ts,
        "tags": ["tabs", "dump", "clean"] + [t for t in global_tags if isinstance(t, str)],
        "source": src_path.name,
    }

    # YAML frontmatter (simple)
    front = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            vv = ", ".join(v)
            front.append(f"{k}: [{vv}]")
        else:
            front.append(f"{k}: {v}")
    front.append("---")

    lines: List[str] = []
    lines.extend(front)
    lines.append("")
    lines.append(f"# Tab dump (clean) — {ts}")
    lines.append("")

    for topic, arr in sorted(topic_buckets.items(), key=lambda x: (-len(x[1]), x[0])):
        lines.append(f"## {topic}")
        # within topic, sub-group by domain
        sub: Dict[str, List[Item]] = {}
        for it in arr:
            sub.setdefault(it.domain, []).append(it)
        for dom, darr in sorted(sub.items()):
            lines.append(f"### {dom}")
            for it in darr:
                tags = tag_map.get(it.norm_url, [])
                tag_str = (" " + " ".join([f"#{t}" for t in tags])) if tags else ""
                lines.append(f"- [{it.title}]({it.clean_url}){tag_str}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n", fm


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
