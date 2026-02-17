"""LLM helpers for tab classification."""

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, TextIO, Tuple

from core.tab_policy.taxonomy import POSTPROCESS_ACTION_ORDER, POSTPROCESS_KIND_ORDER

from .coerce import normalize_action
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


def _temperature_value() -> Optional[float]:
    raw = os.environ.get("TABDUMP_TAG_TEMPERATURE", "0.2")
    if raw is None:
        return 0.2
    value = str(raw).strip()
    if not value:
        return None
    return float(value)


def _post_chat_completion(payload: dict, api_key: str) -> dict:
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""

        detail = f"HTTP {exc.code}"
        if body:
            parsed = None
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = None

            if isinstance(parsed, dict):
                err = parsed.get("error")
                if isinstance(err, dict):
                    msg = err.get("message")
                    param = err.get("param")
                    code = err.get("code")
                    parts = [piece for piece in [msg, f"param={param}" if param else None, f"code={code}" if code else None] if piece]
                    detail = " | ".join(parts) if parts else body[:500]
                else:
                    detail = body[:500]
            else:
                detail = body[:500]

        raise RuntimeError(f"OpenAI chat completion failed: {detail}") from exc


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
    }
    temperature = _temperature_value()
    if temperature is not None:
        payload["temperature"] = temperature

    try:
        data = _post_chat_completion(payload=payload, api_key=api_key)
    except RuntimeError as exc:
        text = str(exc).lower()
        if "temperature" in payload and "temperature" in text and "unsupported" in text:
            payload.pop("temperature", None)
            data = _post_chat_completion(payload=payload, api_key=api_key)
        else:
            raise

    content = data["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except Exception as exc:
        raise RuntimeError(f"OpenAI response is not valid JSON content: {str(content)[:500]}") from exc


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
    allowed_kinds = set(POSTPROCESS_KIND_ORDER)

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
            "Action rubric (choose enum only; do not use synonyms):\n"
            "- video/music -> watch\n"
            "- repo -> triage or build\n"
            "- tool -> triage or build\n"
            "- article/docs -> read or reference\n"
            "- paper -> read, reference, or deep_work\n"
            "- misc/local/internal/auth -> triage or ignore\n\n"
            "Return JSON like:\n"
            "{\n"
            "  \"items\": [\n"
            "    {\"id\": 123, \"topic\": \"...\", \"kind\": \"...\", \"action\": \"...\", \"score\": 3, \"effort\": \"medium\"}\n"
            "  ]\n"
            "}\n\n"
            "Use the provided id as-is; do not invent ids.\n\n"
            "Do not output action synonyms like listen, browse, or view.\n\n"
            + "\n".join(lines)
        )

        try:
            out = call_with_retries_fn(system=system, user=user, api_key=api_key)
        except Exception as exc:
            if stderr is not None:
                print(f"LLM classify failed (chunk size {len(chunk)}): {exc}", file=stderr)
            out = {"items": []}

        raw_items = out.get("items", [])
        if not isinstance(raw_items, list):
            raw_items = []

        chunk_invalid_kind = 0
        chunk_invalid_action = 0
        chunk_invalid_item_id = 0
        chunk_mapped = 0

        for item in raw_items:
            if not isinstance(item, dict):
                chunk_invalid_item_id += 1
                continue

            raw_kind = item.get("kind")
            if not (isinstance(raw_kind, str) and raw_kind.strip().lower() in allowed_kinds):
                chunk_invalid_kind += 1

            if normalize_action(item.get("action")) is None:
                chunk_invalid_action += 1

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
                chunk_invalid_item_id += 1
                continue
            cls_map[idx] = item
            chunk_mapped += 1

        if stderr is not None:
            print(
                "LLM classify chunk diagnostics: "
                f"input={len(chunk)} "
                f"response_items={len(raw_items)} "
                f"mapped={chunk_mapped} "
                f"invalid_kind={chunk_invalid_kind} "
                f"invalid_action={chunk_invalid_action} "
                f"invalid_item_id={chunk_invalid_item_id}",
                file=stderr,
            )

    return cls_map
