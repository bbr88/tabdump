"""LLM input redaction helpers."""

import re
import urllib.parse

CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
SENSITIVE_KV_RE = re.compile(
    r"(?i)\b(token|secret|api[-_]?key|auth|session|password|passwd|code|sig|signature)\s*[:=]\s*([^\s&]+)"
)


def strip_control_chars(value: str) -> str:
    return CONTROL_CHARS_RE.sub("", value)


def redact_text_for_llm(text: str, max_title: int = 0) -> str:
    text = strip_control_chars(text)
    text = SENSITIVE_KV_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    if max_title > 0 and len(text) > max_title:
        text = text[:max_title] + "..."
    return text


def redact_url_for_llm(url: str, redact_query: bool = True) -> str:
    url = url.strip()
    try:
        parsed = urllib.parse.urlsplit(url)
    except Exception:
        return url

    if not parsed.netloc:
        return url

    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    query = ""
    if parsed.query:
        if redact_query:
            keys = [key for key, _ in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)]
            query = urllib.parse.urlencode([(key, "REDACTED") for key in keys], doseq=True)
        else:
            query = parsed.query

    return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))
