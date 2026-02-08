"""URL utilities and sensitivity checks."""

import ipaddress
import urllib.parse
from typing import Iterable, Tuple

from .constants import AUTH_PATH_HINTS, SENSITIVE_HOSTS, SENSITIVE_QUERY_KEYS, TRACKING_PARAMS


def normalize_url(url: str) -> str:
    url = url.strip()
    try:
        parsed = urllib.parse.urlsplit(url)
    except Exception:
        return url

    if not parsed.netloc:
        return url

    query_items = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered = []
    for key, value in query_items:
        key_lower = key.lower()
        if key_lower.startswith("utm_") or key_lower in TRACKING_PARAMS:
            continue
        filtered.append((key, value))
    filtered.sort(key=lambda kv: (kv[0], kv[1]))
    query = urllib.parse.urlencode(filtered, doseq=True)

    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))


def domain_of(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
        return (parsed.netloc or "").lower() or "(unknown)"
    except Exception:
        return "(unknown)"


def host_matches_base(host: str, base: str) -> bool:
    host = host.strip().lower()
    base = base.strip().lower()
    if not host or not base:
        return False
    if host == base:
        return True
    return host.endswith("." + base)


def is_private_or_loopback_host(host: str) -> bool:
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


def matches_sensitive_host_or_path(
    host: str,
    path: str,
    sensitive_hosts: Iterable[str] = SENSITIVE_HOSTS,
) -> bool:
    host = (host or "").strip().lower()
    path = (path or "").strip().lower()
    for marker in sensitive_hosts:
        needle = str(marker).strip().lower()
        if not needle:
            continue
        if "/" in needle:
            marker_host, marker_path = needle.split("/", 1)
            marker_path = "/" + marker_path
            if host_matches_base(host, marker_host) and path.startswith(marker_path):
                return True
            continue
        if host_matches_base(host, needle):
            return True
    return False


def is_sensitive_url(
    url: str,
    sensitive_hosts: Iterable[str] = SENSITIVE_HOSTS,
    auth_path_hints: Iterable[str] = AUTH_PATH_HINTS,
    sensitive_query_keys: Iterable[str] = SENSITIVE_QUERY_KEYS,
) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url)
    except Exception:
        return True

    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        return True

    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()
    if not host:
        return True
    if matches_sensitive_host_or_path(host, path, sensitive_hosts=sensitive_hosts):
        return True
    if is_private_or_loopback_host(host):
        return True

    lower_url = url.lower()
    if any(hint in lower_url for hint in auth_path_hints):
        return True

    sensitive_keys = {key.strip().lower() for key in sensitive_query_keys}
    for key, _ in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        if key.strip().lower() in sensitive_keys:
            return True
    return False


def default_kind_action(
    url: str,
    auth_path_hints: Iterable[str] = AUTH_PATH_HINTS,
    sensitive_hosts: Iterable[str] = SENSITIVE_HOSTS,
) -> Tuple[str, str]:
    lower_url = url.lower()
    try:
        parsed = urllib.parse.urlsplit(url)
    except Exception:
        return "internal", "ignore"

    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()
    if not host:
        return "internal", "ignore"

    if scheme == "file" or is_private_or_loopback_host(host):
        return "local", "ignore"
    if any(hint in lower_url for hint in auth_path_hints) or matches_sensitive_host_or_path(
        host,
        path,
        sensitive_hosts=sensitive_hosts,
    ):
        return "auth", "ignore"
    if scheme not in {"http", "https"}:
        return "internal", "ignore"
    return "misc", "triage"
