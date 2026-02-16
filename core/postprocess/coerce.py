"""Safe coercion helpers for classifier outputs."""

from typing import Optional

from core.tab_policy.taxonomy import POSTPROCESS_ACTIONS, POSTPROCESS_KINDS


def safe_topic(value: object, domain: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if domain:
        return domain.replace(".", "-")
    return "misc"


def safe_kind(value: object) -> str:
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in POSTPROCESS_KINDS:
            return candidate
    return "misc"


def safe_action(value: object) -> str:
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in POSTPROCESS_ACTIONS:
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


def safe_effort(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if candidate in {"quick", "medium", "deep"}:
        return candidate
    return None


def safe_prio(value: object) -> Optional[str]:
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in {"p1", "p2", "p3"}:
            return candidate
    return None
