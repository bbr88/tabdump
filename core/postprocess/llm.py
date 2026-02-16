"""LLM helpers for tab classification."""

import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, TextIO, Tuple

from core.tab_policy.taxonomy import POSTPROCESS_ACTION_ORDER, POSTPROCESS_KIND_ORDER

from .models import Item
from .urls import normalize_url


def key_from_keychain(service: str, account: str) -> Optional[str]:
    security_path = "/usr/bin/security"
    if not Path(security_path).exists():
        return None

    cmd = [
        security_path,
        "find-generic-password",
        "-s",
        service,
        "-a",
        account,
        "-w",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    if proc.returncode != 0:
        return None

    value = proc.stdout.strip()
    return value or None


def resolve_openai_api_key(keychain_service: str, keychain_account: str) -> Optional[str]:
    value = key_from_keychain(keychain_service, keychain_account)
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
    *,
    keychain_service: str = "TabDump",
    keychain_account: str = "openai",
) -> dict:
    api_key = api_key or resolve_openai_api_key(keychain_service=keychain_service, keychain_account=keychain_account)
    if not api_key:
        raise RuntimeError(
            "OpenAI API key not found. Checked: "
            f"Keychain (service={keychain_service}, account={keychain_account}), "
            "env OPENAI_API_KEY."
        )

    model = model or os.environ.get("TABDUMP_TAG_MODEL") or "gpt-4.1-mini"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


def chunked(items: List, size: int) -> List[List]:
    if size <= 0:
        return [items]
    return [items[idx : idx + size] for idx in range(0, len(items), size)]


def call_with_retries(
    system: str,
    user: str,
    tries: int = 3,
    backoff_sec: float = 1.5,
    api_key: Optional[str] = None,
    *,
    openai_chat_json_fn=openai_chat_json,
) -> dict:
    last_err: Optional[Exception] = None
    for attempt in range(tries):
        try:
            return openai_chat_json_fn(system=system, user=user, api_key=api_key)
        except Exception as exc:
            last_err = exc
            if attempt == tries - 1:
                raise
            time.sleep(backoff_sec * (attempt + 1))

    if last_err is not None:
        raise last_err
    raise RuntimeError("LLM call failed with unknown error")


def classify_with_llm(
    indexed_for_cls: List[Tuple[int, Item]],
    url_to_idx: Dict[str, int],
    api_key: str,
    *,
    max_items: int = 0,
    chunk_size: int = 30,
    redact_llm: bool = True,
    redact_text_fn=None,
    redact_url_fn=None,
    call_with_retries_fn=call_with_retries,
    normalize_url_fn=normalize_url,
    stderr: Optional[TextIO] = None,
) -> Dict[int, dict]:
    system = "You are a strict classifier for browser tabs. Return ONLY valid JSON."
    cls_map: Dict[int, dict] = {}
    kind_values = ", ".join(POSTPROCESS_KIND_ORDER)
    action_values = ", ".join(POSTPROCESS_ACTION_ORDER)

    if max_items > 0 and len(indexed_for_cls) > max_items:
        indexed_for_cls = indexed_for_cls[:max_items]

    if redact_text_fn is None:
        redact_text_fn = lambda value: value
    if redact_url_fn is None:
        redact_url_fn = lambda value: value

    for chunk in chunked(indexed_for_cls, chunk_size):
        lines = []
        for idx, item in chunk:
            title = redact_text_fn(item.title) if redact_llm else item.title
            url = redact_url_fn(item.clean_url) if redact_llm else item.clean_url
            lines.append(f"- {idx} | {title} | {url} | {item.domain}")

        user = (
            "For each tab, provide:\n"
            "- topic: short, lowercase, kebab-case (e.g. distributed-systems, postgres, llm, finance, travel, food, shopping)\n"
            f"- kind: one of [{kind_values}]\n"
            f"- action: one of [{action_values}]\n"
            "- score: integer 1-5 (importance)\n\n"
            "- effort: one of [quick, medium, deep] (optional)\n\n"
            "Return JSON like:\n"
            "{\n"
            "  \"items\": [\n"
            "    {\"id\": 123, \"topic\": \"...\", \"kind\": \"...\", \"action\": \"...\", \"score\": 3, \"effort\": \"medium\"}\n"
            "  ]\n"
            "}\n\n"
            "Use the provided id as-is; do not invent ids.\n\n"
            + "\n".join(lines)
        )

        try:
            out = call_with_retries_fn(system=system, user=user, api_key=api_key)
        except Exception as exc:
            if stderr is not None:
                print(f"LLM classify failed (chunk size {len(chunk)}): {exc}", file=stderr)
            out = {"items": []}

        for item in out.get("items", []):
            if not isinstance(item, dict):
                continue

            idx_raw = item.get("id")
            idx: Optional[int] = None
            if idx_raw is not None:
                try:
                    idx = int(idx_raw)
                except Exception:
                    idx = None

            if idx is None:
                url = item.get("url")
                if url:
                    idx = url_to_idx.get(normalize_url_fn(str(url)))

            if idx is None:
                continue
            cls_map[idx] = item

    return cls_map
