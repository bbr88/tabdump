#!/usr/bin/env python3
"""Post-process a TabDump markdown file.

Pipeline:
- Parse Markdown links
- Deduplicate URLs
- Classify/enrich (topic/kind/action/score) via local rules or optional LLM
- Pretty render into a structured Markdown note
- Write companion note: "<orig stem> (clean).md"
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def _find_root(path: Path) -> Path:
    candidates = [
        path.parent,
        path.parent.parent,
        path.parent.parent.parent,
    ]
    for candidate in candidates:
        renderer_root = candidate / "core" / "renderer"
        if (renderer_root / "renderer.py").exists():
            return candidate
    return path.parent.parent


ROOT = _find_root(Path(__file__).resolve())
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from core.postprocess.classify_local import (
    classify_local as _classify_local_impl,
    infer_local_action as _infer_local_action_impl,
    infer_local_kind as _infer_local_kind_impl,
    infer_local_score as _infer_local_score_impl,
    needle_in_blob as _needle_in_blob_impl,
    slugify_topic as _slugify_topic_impl,
    topic_from_host as _topic_from_host_impl,
    topic_from_keywords as _topic_from_keywords_impl,
)
from core.postprocess.coerce import (
    safe_action as _safe_action_impl,
    safe_kind as _safe_kind_impl,
    safe_prio as _safe_prio_impl,
    safe_score as _safe_score_impl,
    safe_topic as _safe_topic_impl,
)
from core.postprocess.llm import (
    call_with_retries as _call_with_retries_impl,
    chunked as _chunked_impl,
    classify_with_llm as _classify_with_llm_impl,
    key_from_keychain as _key_from_keychain_impl,
    openai_chat_json as _openai_chat_json_impl,
)
from core.postprocess.models import Item
from core.postprocess.parsing import (
    extract_created_ts as _extract_created_ts_impl,
    extract_frontmatter_value as _extract_frontmatter_value_impl,
    extract_items as _extract_items_impl,
    parse_markdown_link_line as _parse_markdown_link_line,
)
from core.postprocess.pipeline import build_clean_note as _build_clean_note_impl
from core.postprocess.redaction import (
    redact_text_for_llm as _redact_text_for_llm_impl,
    redact_url_for_llm as _redact_url_for_llm_impl,
)
from core.postprocess.urls import (
    default_kind_action as _default_kind_action_impl,
    domain_of,
    host_matches_base as _host_matches_base_impl,
    is_sensitive_url as _is_sensitive_url_impl,
    is_private_or_loopback_host as _is_private_or_loopback_host_impl,
    matches_sensitive_host_or_path as _matches_sensitive_host_or_path_impl,
    normalize_url,
)
from core.renderer.renderer import render_markdown  # type: ignore


REDACT_LLM = os.environ.get("TABDUMP_LLM_REDACT", "1").strip().lower() not in {"0", "false", "no"}
REDACT_QUERY = os.environ.get("TABDUMP_LLM_REDACT_QUERY", "1").strip().lower() not in {"0", "false", "no"}
MAX_LLM_TITLE = int(os.environ.get("TABDUMP_LLM_TITLE_MAX", "200") or 0)
MAX_ITEMS = int(os.environ.get("TABDUMP_MAX_ITEMS", "0") or 0)
LLM_ENABLED = _env_flag("TABDUMP_LLM_ENABLED", default=False)
KEYCHAIN_SERVICE = os.environ.get("TABDUMP_KEYCHAIN_SERVICE", "TabDump")
KEYCHAIN_ACCOUNT = os.environ.get("TABDUMP_KEYCHAIN_ACCOUNT", "openai")


def redact_text_for_llm(text: str) -> str:
    return _redact_text_for_llm_impl(text, max_title=MAX_LLM_TITLE)


def redact_url_for_llm(url: str) -> str:
    return _redact_url_for_llm_impl(url, redact_query=REDACT_QUERY)


def extract_items(md: str) -> List[Item]:
    return _extract_items_impl(md)


def _key_from_keychain() -> Optional[str]:
    return _key_from_keychain_impl(service=KEYCHAIN_SERVICE, account=KEYCHAIN_ACCOUNT)


def resolve_openai_api_key() -> Optional[str]:
    value = _key_from_keychain()
    if value:
        return value
    value = os.environ.get("OPENAI_API_KEY")
    if value:
        value = value.strip()
    return value or None


def openai_chat_json(
    system: str,
    user: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> dict:
    api_key = api_key or resolve_openai_api_key()
    if not api_key:
        raise RuntimeError(
            "OpenAI API key not found. Checked: "
            f"Keychain (service={KEYCHAIN_SERVICE}, account={KEYCHAIN_ACCOUNT}), "
            "env OPENAI_API_KEY."
        )
    return _openai_chat_json_impl(
        system=system,
        user=user,
        model=model,
        api_key=api_key,
        keychain_service=KEYCHAIN_SERVICE,
        keychain_account=KEYCHAIN_ACCOUNT,
    )


def _safe_topic(value: object, domain: str) -> str:
    return _safe_topic_impl(value, domain)


def _safe_kind(value: object) -> str:
    return _safe_kind_impl(value)


def _safe_action(value: object) -> str:
    return _safe_action_impl(value)


def _safe_score(value: object) -> Optional[int]:
    return _safe_score_impl(value)


def _safe_prio(value: object) -> Optional[str]:
    return _safe_prio_impl(value)


def _extract_created_ts(src_path: Path, fallback: str) -> str:
    return _extract_created_ts_impl(src_path, fallback)


def _extract_frontmatter_value(src_path: Path, key: str) -> Optional[str]:
    return _extract_frontmatter_value_impl(src_path, key)


def _chunked(items: List, size: int) -> List[List]:
    return _chunked_impl(items, size)


def _call_with_retries(
    system: str,
    user: str,
    tries: int = 3,
    backoff_sec: float = 1.5,
    api_key: Optional[str] = None,
) -> dict:
    return _call_with_retries_impl(
        system=system,
        user=user,
        tries=tries,
        backoff_sec=backoff_sec,
        api_key=api_key,
        openai_chat_json_fn=openai_chat_json,
    )


def _is_sensitive_url(url: str) -> bool:
    return _is_sensitive_url_impl(url)


def _default_kind_action(url: str) -> Tuple[str, str]:
    return _default_kind_action_impl(url)


def _is_private_or_loopback_host(host: str) -> bool:
    return _is_private_or_loopback_host_impl(host)


def _matches_sensitive_host_or_path(host: str, path: str) -> bool:
    return _matches_sensitive_host_or_path_impl(host, path)


def _host_matches_base(host: str, base: str) -> bool:
    return _host_matches_base_impl(host, base)


def _slugify_topic(value: str) -> str:
    return _slugify_topic_impl(value)


def _topic_from_host(host: str) -> Optional[str]:
    return _topic_from_host_impl(host)


def _topic_from_keywords(text_blob: str) -> Optional[str]:
    return _topic_from_keywords_impl(text_blob)


def _needle_in_blob(topic: str, needle: str, blob: str) -> bool:
    return _needle_in_blob_impl(topic, needle, blob)


def _infer_local_kind(item: Item) -> str:
    return _infer_local_kind_impl(item)


def _infer_local_action(kind: str, item: Item) -> str:
    return _infer_local_action_impl(kind, item)


def _infer_local_score(kind: str, action: str, item: Item) -> int:
    return _infer_local_score_impl(kind, action, item)


def _classify_local(item: Item) -> dict:
    return _classify_local_impl(item)


def _classify_with_llm(
    indexed_for_cls: List[Tuple[int, Item]],
    url_to_idx: Dict[str, int],
    api_key: str,
) -> Dict[int, dict]:
    chunk_size = int(os.environ.get("TABDUMP_CLASSIFY_CHUNK", "30"))
    return _classify_with_llm_impl(
        indexed_for_cls=indexed_for_cls,
        url_to_idx=url_to_idx,
        api_key=api_key,
        max_items=MAX_ITEMS,
        chunk_size=chunk_size,
        redact_llm=REDACT_LLM,
        redact_text_fn=redact_text_for_llm,
        redact_url_fn=redact_url_for_llm,
        call_with_retries_fn=_call_with_retries,
        stderr=sys.stderr,
    )


def build_clean_note(src_path: Path, items: List[Item], dump_id: Optional[str] = None) -> Tuple[str, dict]:
    return _build_clean_note_impl(
        src_path=src_path,
        items=items,
        dump_id=dump_id,
        llm_enabled=LLM_ENABLED,
        resolve_openai_api_key_fn=resolve_openai_api_key,
        classify_with_llm_fn=_classify_with_llm,
        classify_local_fn=_classify_local,
        is_sensitive_url_fn=_is_sensitive_url,
        default_kind_action_fn=_default_kind_action,
        safe_topic_fn=_safe_topic,
        safe_kind_fn=_safe_kind,
        safe_action_fn=_safe_action,
        safe_score_fn=_safe_score,
        extract_created_ts_fn=_extract_created_ts,
        render_markdown_fn=render_markdown,
        stderr=sys.stderr,
    )


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        exe = Path(argv[0]).name if argv else "cli.py"
        print(f"usage: {exe} <path-to-tabdump-md>", file=sys.stderr)
        return 2

    src = Path(argv[1]).expanduser().resolve()
    md = src.read_text(encoding="utf-8", errors="replace")
    dump_id = _extract_frontmatter_value(src, "tabdump_id")
    if not dump_id:
        print("Missing tabdump_id frontmatter; refusing to postprocess.", file=sys.stderr)
        return 4

    items = extract_items(md)
    if not items:
        print("No tab items found in the note; nothing to do.", file=sys.stderr)
        return 3

    clean_text, _fm = build_clean_note(src, items, dump_id=dump_id)
    clean_path = src.with_name(src.stem + " (clean)" + src.suffix)
    clean_path.write_text(clean_text, encoding="utf-8")
    print(str(clean_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
