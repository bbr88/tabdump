"""Shared effort estimation semantics for postprocess and renderer stages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit

from .actions import canonical_action

EFFORT_TO_LEVEL = {
    "quick": 0,
    "medium": 1,
    "deep": 2,
}
LEVEL_TO_EFFORT = {value: key for key, value in EFFORT_TO_LEVEL.items()}

DEEP_CONTENT_HINTS = (
    "full course",
    "complete guide",
    "comprehensive guide",
    "masterclass",
    "deep dive",
    "end-to-end",
    "step-by-step",
    "longform",
    "long-form",
    "playbook",
    "handbook",
)
QUICK_CONTENT_HINTS = (
    "trailer",
    "teaser",
    "clip",
    "highlights",
    "recap",
    "shorts",
    "overview",
    "faq",
    "quickstart",
    "cheat sheet",
    "abstract",
    "summary",
)
DEEP_COMPLEXITY_HINTS = (
    "setup",
    "configure",
    "configuration",
    "migration",
    "integration",
    "implementation",
    "workflow",
    "multi-step",
    "project plan",
    "roadmap",
    "curriculum",
    "itinerary",
    "budget plan",
    "workout plan",
    "application form",
    "checkout flow",
)
QUICK_COMPLEXITY_HINTS = (
    "landing page",
    "home page",
    "signin",
    "sign in",
    "login",
    "profile",
    "settings",
    "readme",
    "changelog",
)

KIND_DEEP_HINTS = {
    "video": ("full lecture", "full lesson", "full workshop"),
    "music": ("full concert", "live set", "full set"),
    "docs": ("complete handbook", "learning path", "full tutorial"),
    "article": ("long read", "case study", "ultimate guide"),
    "repo": ("architecture", "deploy", "infrastructure"),
    "tool": ("onboarding flow", "workspace setup", "automation workflow"),
    "auth": ("verification flow", "account recovery"),
    "local": ("local setup", "local migration"),
    "internal": ("internal rollout", "internal process"),
}
KIND_QUICK_HINTS = {
    "video": ("intro", "preview"),
    "music": ("single", "sample"),
    "docs": ("reference card",),
    "article": ("news brief",),
    "repo": ("issues", "issue", "bug report"),
    "tool": ("dashboard", "catalog"),
    "misc": ("showcase", "gallery"),
}

_HMS_PATTERN = re.compile(r"\b(\d{1,2}):([0-5]\d):([0-5]\d)\b")
_HOUR_PATTERN = re.compile(r"(?<!\d)(\d{1,2}(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours)\b")
_HOUR_DASH_PATTERN = re.compile(r"(?<!\d)(\d{1,2})-hour\b")
_MIN_PATTERN = re.compile(r"(?<!\d)(\d{1,3})\s*(?:m|min|mins|minute|minutes)\b")
_HOUR_MIN_PATTERN = re.compile(
    r"(?<!\d)(\d{1,2})\s*(?:h|hr|hrs|hour|hours)\s*(\d{1,2})\s*(?:m|min|mins|minute|minutes)\b"
)


@dataclass(frozen=True)
class EffortDecision:
    effort: str
    derived_effort: str
    derived_level: int
    final_level: int
    provided_effort: Optional[str]
    reasons: tuple[str, ...]


def normalize_effort(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if candidate in EFFORT_TO_LEVEL:
        return candidate
    return None


def effort_distance(lhs: str, rhs: str) -> Optional[int]:
    lhs_norm = normalize_effort(lhs)
    rhs_norm = normalize_effort(rhs)
    if lhs_norm is None or rhs_norm is None:
        return None
    return abs(EFFORT_TO_LEVEL[lhs_norm] - EFFORT_TO_LEVEL[rhs_norm])


def _first_match(blob: str, hints: tuple[str, ...]) -> Optional[str]:
    for hint in hints:
        if hint and hint in blob:
            return hint
    return None


def _duration_minutes(blob: str) -> Optional[float]:
    values = []
    for match in _HOUR_MIN_PATTERN.finditer(blob):
        values.append(float(match.group(1)) * 60.0 + float(match.group(2)))
    for match in _HMS_PATTERN.finditer(blob):
        values.append(float(match.group(1)) * 60.0 + float(match.group(2)) + float(match.group(3)) / 60.0)
    for match in _HOUR_PATTERN.finditer(blob):
        values.append(float(match.group(1)) * 60.0)
    for match in _HOUR_DASH_PATTERN.finditer(blob):
        values.append(float(match.group(1)) * 60.0)
    for match in _MIN_PATTERN.finditer(blob):
        values.append(float(match.group(1)))
    if not values:
        return None
    return max(values)


def _clamp_level(level: int) -> int:
    if level < 0:
        return 0
    if level > 2:
        return 2
    return level


def _base_level(kind: str, action: str) -> tuple[int, str]:
    kind_norm = str(kind or "").strip().lower()
    action_norm = canonical_action(action or "")

    if kind_norm in {"auth", "local", "internal"}:
        return 0, "base:sensitive_or_local"
    if kind_norm in {"paper", "spec"} or action_norm == "deep_work":
        return 2, "base:deep_kind_or_action"
    return 1, "base:general"


def _build_blob(*, title: str, url: str, domain: str) -> str:
    title_norm = str(title or "").lower()
    url_norm = str(url or "").lower()
    host = str(domain or "").strip().lower()
    if not host and url_norm:
        try:
            host = (urlsplit(url_norm).hostname or "").lower()
        except Exception:
            host = ""
    return f"{title_norm} {url_norm} {host}"


def resolve_effort_decision(
    *,
    kind: str,
    action: str,
    title: str,
    url: str,
    domain: str,
    provided_effort: object = None,
) -> EffortDecision:
    level, base_reason = _base_level(kind, action)
    reasons = [base_reason]
    kind_norm = str(kind or "").strip().lower()
    blob = _build_blob(title=title, url=url, domain=domain)

    if _first_match(blob, DEEP_CONTENT_HINTS):
        level += 1
        reasons.append("signal:deep_content")
    if _first_match(blob, QUICK_CONTENT_HINTS):
        level -= 1
        reasons.append("signal:quick_content")

    duration_minutes = _duration_minutes(blob)
    if duration_minutes is not None:
        if duration_minutes >= 180.0:
            level += 2
            reasons.append("signal:duration_very_long")
        elif duration_minutes >= 90.0:
            level += 1
            reasons.append("signal:duration_long")
        elif duration_minutes <= 20.0:
            level -= 1
            reasons.append("signal:duration_short")

    if _first_match(blob, DEEP_COMPLEXITY_HINTS):
        level += 1
        reasons.append("signal:complexity_deep")
    if _first_match(blob, QUICK_COMPLEXITY_HINTS):
        level -= 1
        reasons.append("signal:complexity_quick")

    deep_kind_hints = tuple(KIND_DEEP_HINTS.get(kind_norm, ()))
    quick_kind_hints = tuple(KIND_QUICK_HINTS.get(kind_norm, ()))
    if deep_kind_hints and _first_match(blob, deep_kind_hints):
        level += 1
        reasons.append("signal:kind_deep")
    if quick_kind_hints and _first_match(blob, quick_kind_hints):
        level -= 1
        reasons.append("signal:kind_quick")

    derived_level = _clamp_level(level)
    derived_effort = LEVEL_TO_EFFORT[derived_level]

    advisory = normalize_effort(provided_effort)
    if advisory is None:
        final_level = derived_level
    else:
        advisory_level = EFFORT_TO_LEVEL[advisory]
        if abs(advisory_level - derived_level) <= 1:
            final_level = advisory_level
            reasons.append("advisory:accepted")
        else:
            final_level = derived_level
            reasons.append("advisory:rejected")

    effort = LEVEL_TO_EFFORT[final_level]
    return EffortDecision(
        effort=effort,
        derived_effort=derived_effort,
        derived_level=derived_level,
        final_level=final_level,
        provided_effort=advisory,
        reasons=tuple(reasons),
    )


def resolve_effort(
    kind: str,
    action: str,
    title: str,
    url: str,
    domain: str,
    provided_effort: object = None,
) -> str:
    decision = resolve_effort_decision(
        kind=kind,
        action=action,
        title=title,
        url=url,
        domain=domain,
        provided_effort=provided_effort,
    )
    return decision.effort
