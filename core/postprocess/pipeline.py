"""Main pipeline orchestration for clean note generation."""

import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from core.renderer.renderer import render_markdown

from .classify_local import (
    classify_local,
    infer_local_action,
    is_action_compatible,
)
from .coerce import normalize_action, safe_action, safe_effort, safe_kind, safe_score, safe_topic
from .models import Item
from .parsing import extract_created_ts
from .urls import default_kind_action, is_sensitive_url

ACTION_POLICIES = {"raw", "derived", "hybrid"}


def _infer_effort(kind: str, action: str) -> str:
    kind_norm = str(kind or "").strip().lower()
    action_norm = str(action or "").strip().lower()
    if kind_norm in {"paper", "spec"} or action_norm == "deep_work":
        return "deep"
    if action_norm in {"reference", "watch", "ignore"}:
        return "quick"
    return "medium"


def _normalize_action_policy(value: str) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in ACTION_POLICIES:
        return candidate
    return "hybrid"


def _normalized_coverage_threshold(value: float) -> float:
    try:
        threshold = float(value)
    except Exception:
        return 0.7
    if threshold < 0.0:
        return 0.0
    if threshold > 1.0:
        return 1.0
    return threshold


def _resolve_llm_action(
    *,
    policy: str,
    raw_action: object,
    kind: str,
    item: Item,
    safe_action_fn: Callable[[object], str],
    normalize_action_fn: Callable[[object], Optional[str]],
    infer_local_action_fn: Callable[[str, Item], str],
    is_action_compatible_fn: Callable[[str, str], bool],
) -> str:
    policy_norm = _normalize_action_policy(policy)
    if policy_norm == "raw":
        return safe_action_fn(raw_action)

    derived = infer_local_action_fn(kind, item)
    if policy_norm == "derived":
        return safe_action_fn(derived)

    model_action = normalize_action_fn(raw_action)
    if model_action and is_action_compatible_fn(kind, model_action):
        return safe_action_fn(model_action)
    return safe_action_fn(derived)


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
    normalize_action_fn: Callable[[object], Optional[str]] = normalize_action,
    safe_score_fn: Callable[[object], Optional[int]] = safe_score,
    safe_effort_fn: Callable[[object], Optional[str]] = safe_effort,
    infer_local_action_fn: Callable[[str, Item], str] = infer_local_action,
    is_action_compatible_fn: Callable[[str, str], bool] = is_action_compatible,
    extract_created_ts_fn: Callable[[Path, str], str] = extract_created_ts,
    llm_action_policy: str = "hybrid",
    min_llm_coverage: float = 0.7,
    render_markdown_fn=render_markdown,
    render_cfg_override: Optional[dict] = None,
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

    non_sensitive_total = len(indexed_for_cls)
    mapped_non_sensitive = 0
    if use_llm:
        mapped_non_sensitive = sum(1 for idx, _ in indexed_for_cls if idx in cls_map)
    llm_coverage = (
        (mapped_non_sensitive / non_sensitive_total)
        if use_llm and non_sensitive_total > 0
        else 0.0
    )
    coverage_threshold = _normalized_coverage_threshold(min_llm_coverage)
    fallback_unmapped_to_local = use_llm and llm_coverage < coverage_threshold
    use_local_classifier = not use_llm

    diagnostics = {
        "llm_mapped": mapped_non_sensitive if use_llm else 0,
        "llm_unmapped": (non_sensitive_total - mapped_non_sensitive) if use_llm else 0,
        "llm_fallback_local": 0,
        "llm_defaulted": 0,
    }
    action_policy = _normalize_action_policy(llm_action_policy)

    enriched: List[dict] = []

    for idx, item in indexed_items:
        cls = cls_map.get(idx, {})
        if sensitive_items.get(idx):
            kind, action = default_kind_action_fn(item.clean_url)
            topic = safe_topic_fn(None, item.domain)
            score = 3
            effort = _infer_effort(kind, action)
        elif cls:
            topic = safe_topic_fn(cls.get("topic"), item.domain)
            kind = safe_kind_fn(cls.get("kind"))
            action = _resolve_llm_action(
                policy=action_policy,
                raw_action=cls.get("action"),
                kind=kind,
                item=item,
                safe_action_fn=safe_action_fn,
                normalize_action_fn=normalize_action_fn,
                infer_local_action_fn=infer_local_action_fn,
                is_action_compatible_fn=is_action_compatible_fn,
            )
            score = safe_score_fn(cls.get("score"))
            effort = safe_effort_fn(cls.get("effort")) or _infer_effort(kind, action)
        elif use_local_classifier or fallback_unmapped_to_local:
            if use_llm:
                diagnostics["llm_fallback_local"] += 1
            local = classify_local_fn(item)
            topic = safe_topic_fn(local.get("topic"), item.domain)
            kind = safe_kind_fn(local.get("kind"))
            action = safe_action_fn(local.get("action"))
            score = safe_score_fn(local.get("score"))
            effort = safe_effort_fn(local.get("effort")) or _infer_effort(kind, action)
        else:
            if use_llm:
                diagnostics["llm_defaulted"] += 1
            topic = safe_topic_fn(None, item.domain)
            kind = safe_kind_fn(None)
            action = safe_action_fn(None)
            score = safe_score_fn(None)
            effort = _infer_effort(kind, action)

        enriched.append(
            {
                "title": item.title,
                "url": item.clean_url,
                "domain": item.domain,
                "browser": item.browser,
                "kind": kind,
                "effort": effort,
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

    print(
        "LLM classify diagnostics: "
        f"requested={1 if llm_enabled else 0} "
        f"active={1 if use_llm else 0} "
        f"non_sensitive={non_sensitive_total} "
        f"mapped={diagnostics['llm_mapped']} "
        f"unmapped={diagnostics['llm_unmapped']} "
        f"coverage={llm_coverage:.2f} "
        f"min_coverage={coverage_threshold:.2f} "
        f"fallback_local={diagnostics['llm_fallback_local']} "
        f"defaulted={diagnostics['llm_defaulted']} "
        f"action_policy={action_policy}",
        file=stderr,
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

    markdown = render_markdown_fn(payload, cfg=render_cfg_override or {})
    return markdown, meta
