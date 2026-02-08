"""Shared text normalization helpers."""

from __future__ import annotations

import re


def slugify_kebab(value: str, *, fallback: str = "misc") -> str:
    """Normalize text to lowercase kebab-case with a stable fallback."""
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or fallback
