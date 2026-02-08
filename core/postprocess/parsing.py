"""Markdown and frontmatter parsing helpers."""

import re
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from .models import Item
from .urls import domain_of, normalize_url


def parse_markdown_link_line(line: str) -> Optional[Tuple[str, str]]:
    stripped = line.strip()
    if not stripped.startswith("- ["):
        return None

    idx = 2
    if idx >= len(stripped) or stripped[idx] != "[":
        return None
    idx += 1

    title_depth = 1
    title_chars: List[str] = []
    escaped = False
    while idx < len(stripped):
        ch = stripped[idx]
        if escaped:
            title_chars.append(ch)
            escaped = False
            idx += 1
            continue
        if ch == "\\":
            escaped = True
            idx += 1
            continue
        if ch == "[":
            title_depth += 1
            title_chars.append(ch)
            idx += 1
            continue
        if ch == "]":
            title_depth -= 1
            if title_depth == 0:
                idx += 1
                break
            title_chars.append(ch)
            idx += 1
            continue
        title_chars.append(ch)
        idx += 1

    if title_depth != 0:
        return None

    while idx < len(stripped) and stripped[idx].isspace():
        idx += 1
    if idx >= len(stripped) or stripped[idx] != "(":
        return None
    idx += 1

    url_depth = 1
    url_chars: List[str] = []
    escaped = False
    while idx < len(stripped):
        ch = stripped[idx]
        if escaped:
            url_chars.append(ch)
            escaped = False
            idx += 1
            continue
        if ch == "\\":
            escaped = True
            idx += 1
            continue
        if ch == "(":
            url_depth += 1
            url_chars.append(ch)
            idx += 1
            continue
        if ch == ")":
            url_depth -= 1
            if url_depth == 0:
                idx += 1
                break
            url_chars.append(ch)
            idx += 1
            continue
        url_chars.append(ch)
        idx += 1

    if url_depth != 0:
        return None
    if stripped[idx:].strip():
        return None

    title = "".join(title_chars).strip()
    url = "".join(url_chars).strip()
    if not title or not url:
        return None
    return title, url


def extract_items(
    markdown: str,
    *,
    normalize_url_fn: Callable[[str], str] = normalize_url,
    domain_of_fn: Callable[[str], str] = domain_of,
) -> List[Item]:
    items: List[Item] = []
    current_browser: Optional[str] = None

    for line in markdown.splitlines():
        if line.startswith("## "):
            if line.startswith("## Chrome"):
                current_browser = "chrome"
            elif line.startswith("## Safari"):
                current_browser = "safari"
            elif line.startswith("## Firefox"):
                current_browser = "firefox"
        if line.startswith("### "):
            continue

        parsed = parse_markdown_link_line(line)
        if parsed is None:
            continue

        title, url = parsed
        clean_url = normalize_url_fn(url)
        items.append(
            Item(
                title=title,
                url=url,
                norm_url=clean_url,
                clean_url=clean_url,
                domain=domain_of_fn(clean_url),
                browser=current_browser,
            )
        )

    return items


def extract_created_ts(src_path: Path, fallback: str) -> str:
    try:
        head = src_path.read_text(encoding="utf-8", errors="replace").splitlines()[:30]
    except Exception:
        return fallback

    for line in head:
        match = re.match(r'^created:\s*"?(.+?)"?$', line.strip())
        if match:
            return match.group(1)
    return fallback


def extract_frontmatter_value(src_path: Path, key: str) -> Optional[str]:
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
        match = pattern.match(line.strip())
        if match:
            return match.group(1)
    return None
