"""Rule-based local tab classification."""

import re
import urllib.parse
from typing import Optional

from core.tab_policy.text import slugify_kebab

from .constants import (
    BLOG_HINTS,
    CODE_HOST_DOMAINS,
    CODE_HOST_RESERVED_PATHS,
    DEEP_READ_HINTS,
    DOC_HINTS,
    DOC_HOST_OVERRIDES,
    GO_CONTEXT_HINTS,
    LOW_SIGNAL_HINTS,
    MCP_HINTS,
    MUSIC_KEYWORD_HINTS,
    MUSIC_HINT_DOMAINS,
    PAPER_HINTS,
    PROJECT_HINTS,
    REFERENCE_HINTS,
    SOCIAL_DOMAINS,
    TOOL_DOMAINS,
    TOPIC_KEYWORDS,
    UI_UX_HINTS,
    VIDEO_KEYWORD_HINTS,
    VIDEO_DOMAINS,
)
from .models import Item
from .urls import host_matches_base


def slugify_topic(value: str) -> str:
    return slugify_kebab(value, fallback="misc")


def topic_from_host(host: str) -> Optional[str]:
    host = (host or "").strip().lower()
    if not host:
        return None
    if any(host_matches_base(host, base) for base in SOCIAL_DOMAINS):
        return None

    host = host.split(":", 1)[0]
    parts = [p for p in host.split(".") if p and p != "www"]
    if len(parts) < 2:
        return None

    if parts[-1] in {"com", "org", "net", "io", "ai", "dev", "app", "co"}:
        stem = parts[-2]
    else:
        stem = parts[0]
    return slugify_topic(stem)


def needle_in_blob(topic: str, needle: str, blob: str) -> bool:
    if not needle:
        return False
    if topic == "go" and needle == "go":
        if re.search(r"\bgo\b", blob) is None:
            return False
        return any(hint in blob for hint in GO_CONTEXT_HINTS)
    return needle in blob


def topic_from_keywords(text_blob: str) -> Optional[str]:
    blob = (text_blob or "").lower()
    for topic, needles in TOPIC_KEYWORDS:
        for needle in needles:
            if needle_in_blob(topic, needle, blob):
                return topic
    if any(hint in blob for hint in UI_UX_HINTS):
        return "ui-ux"
    if any(hint in blob for hint in PROJECT_HINTS):
        return "project-management"
    if any(hint in blob for hint in PAPER_HINTS):
        return "research"
    return None


def _path_matches_hint(path: str, hint: str) -> bool:
    """Match docs/blog hints on path segment boundaries, not arbitrary substrings."""
    if not path or not hint:
        return False
    if hint.endswith("/"):
        return hint in path
    return path == hint or path.startswith(hint + "/")


def _blob_matches_hint(blob: str, hint: str) -> bool:
    if not blob or not hint:
        return False
    if re.search(r"[a-z0-9]", hint) and re.fullmatch(r"[a-z0-9-]+", hint):
        return re.search(rf"(?<![a-z0-9]){re.escape(hint)}(?![a-z0-9])", blob) is not None
    return hint in blob


def infer_local_kind(item: Item) -> str:
    url = item.clean_url
    try:
        parsed = urllib.parse.urlsplit(url)
    except Exception:
        return "misc"

    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()
    title = (item.title or "").lower()
    blob = f"{host} {path} {title}"

    code_host = any(host_matches_base(host, base) for base in CODE_HOST_DOMAINS)
    first_path = ""
    parts = [part for part in path.split("/") if part]
    if parts:
        first_path = parts[0].lower()

    if path.endswith(".pdf") or any(hint in blob for hint in PAPER_HINTS):
        return "paper"
    if any(_path_matches_hint(path, hint) for hint in BLOG_HINTS):
        return "article"
    if any(host_matches_base(host, base) for base in MUSIC_HINT_DOMAINS):
        return "music"
    if any(host_matches_base(host, base) for base in VIDEO_DOMAINS):
        return "video"
    if any(_blob_matches_hint(blob, hint) for hint in MUSIC_KEYWORD_HINTS):
        return "music"
    if any(_blob_matches_hint(blob, hint) for hint in VIDEO_KEYWORD_HINTS):
        return "video"
    if host_matches_base(host, "huggingface.co") and "/learn/" in path:
        return "docs"
    if host in DOC_HOST_OVERRIDES:
        return "docs"
    if code_host and first_path not in CODE_HOST_RESERVED_PATHS:
        return "repo"
    if any(hint in blob for hint in PROJECT_HINTS):
        return "tool"
    if any(hint in blob for hint in MCP_HINTS):
        return "tool"
    if any(host_matches_base(host, base) for base in TOOL_DOMAINS):
        return "tool"
    if host.startswith("docs.") or any(_path_matches_hint(path, hint) for hint in DOC_HINTS):
        return "docs"
    if any(_blob_matches_hint(blob, hint) for hint in REFERENCE_HINTS):
        return "docs"
    return "article"


def infer_local_action(kind: str, item: Item) -> str:
    lower = f"{item.title} {item.clean_url}".lower()
    if kind in {"video", "music"}:
        return "watch"
    if kind == "repo":
        if "/issues/" in lower or "/pull/" in lower or "/pulls/" in lower:
            return "triage"
        return "build"
    if kind == "tool":
        if any(hint in lower for hint in PROJECT_HINTS):
            return "build"
        return "triage"
    if kind in {"docs", "paper", "article"}:
        if kind == "paper" and any(hint in lower for hint in DEEP_READ_HINTS):
            return "deep_work"
        if any(hint in lower for hint in REFERENCE_HINTS):
            return "reference"
        return "read"
    return "triage"


def infer_local_score(kind: str, action: str, item: Item) -> int:
    score = {
        "paper": 5,
        "docs": 4,
        "repo": 4,
        "article": 3,
        "tool": 3,
        "video": 3,
        "music": 3,
        "misc": 2,
    }.get(kind, 3)

    if action == "build":
        score += 1
    elif action == "watch":
        score -= 1

    lower = f"{item.title} {item.clean_url}".lower()
    host = (urllib.parse.urlsplit(item.clean_url).hostname or "").lower()
    if any(host_matches_base(host, base) for base in SOCIAL_DOMAINS):
        score -= 1

    deep_read_hit = any(hint in lower for hint in DEEP_READ_HINTS)
    if deep_read_hit:
        score += 1
    if any(hint in lower for hint in UI_UX_HINTS):
        score += 1
    if any(hint in lower for hint in PROJECT_HINTS):
        score += 1
    if any(hint in lower for hint in LOW_SIGNAL_HINTS):
        score -= 1

    if kind == "paper" and deep_read_hit:
        score = max(score, 5)

    if score < 1:
        score = 1
    if score > 5:
        score = 5
    return score


def classify_local(item: Item) -> dict:
    kind = infer_local_kind(item)
    action = infer_local_action(kind, item)
    score = infer_local_score(kind, action, item)
    blob = f"{item.title} {item.clean_url}"
    topic = topic_from_keywords(blob) or topic_from_host(item.domain) or "misc"
    return {"topic": slugify_topic(topic), "kind": kind, "action": action, "score": score}
