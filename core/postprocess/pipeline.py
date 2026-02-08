"""Main pipeline orchestration for clean note generation."""

import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from core.renderer.renderer import render_markdown

from .classify_local import classify_local
from .coerce import safe_action, safe_kind, safe_score, safe_topic
from .models import Item
from .parsing import extract_created_ts
from .urls import default_kind_action, is_sensitive_url


def build_clean_note(
    src_path: Path,
    items: List[Item],
    dump_id: Optional[str] = None,
    *,
    llm_enabled: bool,
    resolve_openai_api_key_fn: Callable[[], Optional[str]],
    classify_with_llm_fn: Callable[[List[Tuple[int, Item]], Dict[str, int], str], Dict[int, dict]],
    classify_local_fn: Callable[[Item], dict] = classify_local,
    is_sensitive_url_fn: Callable[[str], bool] = is_sensitive_url,
    default_kind_action_fn: Callable[[str], Tuple[str, str]] = default_kind_action,
    safe_topic_fn: Callable[[object, str], str] = safe_topic,
    safe_kind_fn: Callable[[object], str] = safe_kind,
    safe_action_fn: Callable[[object], str] = safe_action,
    safe_score_fn: Callable[[object], Optional[int]] = safe_score,
    extract_created_ts_fn: Callable[[Path, str], str] = extract_created_ts,
    render_markdown_fn=render_markdown,
    stderr=sys.stderr,
) -> Tuple[str, dict]:
    indexed_items = list(enumerate(items))
    url_to_idx = {item.norm_url: idx for idx, item in indexed_items}
    sensitive_items: Dict[int, bool] = {
        idx: is_sensitive_url_fn(item.clean_url) for idx, item in indexed_items
    }
    indexed_for_cls = [(idx, item) for idx, item in indexed_items if not sensitive_items[idx]]

    cls_map: Dict[int, dict] = {}
    use_llm = llm_enabled
    if use_llm:
        api_key = resolve_openai_api_key_fn()
        if not api_key:
            use_llm = False
            print(
                "LLM disabled: OpenAI API key not found; using local classifier.",
                file=stderr,
            )
        else:
            cls_map = classify_with_llm_fn(indexed_for_cls, url_to_idx, api_key)

    use_local_classifier = not use_llm
    enriched: List[dict] = []

    for idx, item in indexed_items:
        cls = cls_map.get(idx, {})
        if sensitive_items.get(idx):
            kind, action = default_kind_action_fn(item.clean_url)
            topic = safe_topic_fn(None, item.domain)
            score = 3
        elif cls:
            topic = safe_topic_fn(cls.get("topic"), item.domain)
            kind = safe_kind_fn(cls.get("kind"))
            action = safe_action_fn(cls.get("action"))
            score = safe_score_fn(cls.get("score"))
        elif use_local_classifier:
            local = classify_local_fn(item)
            topic = safe_topic_fn(local.get("topic"), item.domain)
            kind = safe_kind_fn(local.get("kind"))
            action = safe_action_fn(local.get("action"))
            score = safe_score_fn(local.get("score"))
        else:
            topic = safe_topic_fn(None, item.domain)
            kind = safe_kind_fn(None)
            action = safe_action_fn(None)
            score = safe_score_fn(None)

        enriched.append(
            {
                "title": item.title,
                "url": item.clean_url,
                "domain": item.domain,
                "browser": item.browser,
                "kind": kind,
                "topics": [
                    {
                        "slug": topic,
                        "title": topic.replace("-", " ").title(),
                        "confidence": 0.8,
                    }
                ],
                "intent": {
                    "action": action,
                    "confidence": (score or 3) / 5,
                },
                "flags": {},
            }
        )

    ts = extract_created_ts_fn(src_path, fallback=time.strftime("%Y-%m-%d %H-%M-%S"))
    meta = {
        "created": ts,
        "source": src_path.name,
        "allowlistPatterns": [],
        "skipPrefixes": [],
    }
    if dump_id:
        meta["tabdump_id"] = dump_id

    counts = {
        "total": len(enriched),
        "dumped": len(enriched),
        "closed": 0,
        "kept": 0,
    }
    payload = {
        "meta": meta,
        "counts": counts,
        "items": enriched,
    }

    markdown = render_markdown_fn(payload, cfg={})
    return markdown, meta
