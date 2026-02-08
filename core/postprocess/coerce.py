"""Safe coercion helpers for classifier outputs."""

from typing import Optional


def safe_topic(value: object, domain: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if domain:
        return domain.replace(".", "-")
    return "misc"


def safe_kind(value: object) -> str:
    allowed = {"video", "repo", "paper", "docs", "article", "tool", "misc", "local", "auth", "internal"}
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in allowed:
            return candidate
    return "misc"


def safe_action(value: object) -> str:
    allowed = {"read", "watch", "reference", "build", "triage", "ignore", "deep_work"}
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in allowed:
            return candidate
    return "triage"


def safe_score(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        score = int(value)
    except Exception:
        return None
    if score < 0:
        score = 0
    if score > 5:
        score = 5
    return score


def safe_prio(value: object) -> Optional[str]:
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in {"p1", "p2", "p3"}:
            return candidate
    return None
