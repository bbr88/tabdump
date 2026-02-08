"""Shared hostname matching helpers."""

from __future__ import annotations


def host_matches_base(
    host: str,
    base: str,
    *,
    enable_suffix: bool = True,
    strip_www_host: bool = False,
) -> bool:
    host_norm = str(host or "").strip().lower()
    base_norm = str(base or "").strip().lower()
    if not host_norm or not base_norm:
        return False

    if strip_www_host and host_norm.startswith("www."):
        host_norm = host_norm[4:]

    if host_norm == base_norm:
        return True
    return bool(enable_suffix and host_norm.endswith("." + base_norm))
