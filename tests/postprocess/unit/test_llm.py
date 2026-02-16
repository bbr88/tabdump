import json
import urllib.error
from io import BytesIO
from io import StringIO
from types import SimpleNamespace

import pytest

from core.postprocess import llm
from core.postprocess.models import Item
from core.postprocess.urls import normalize_url
from core.tab_policy.taxonomy import POSTPROCESS_ACTION_ORDER, POSTPROCESS_KIND_ORDER


def _item(i: int) -> Item:
    url = f"https://example.com/item/{i}?q=v{i}"
    clean = normalize_url(url)
    return Item(
        title=f"Title {i}",
        url=url,
        norm_url=clean,
        clean_url=clean,
        domain="example.com",
        browser=None,
    )


def test_key_from_keychain_success(monkeypatch):
    monkeypatch.setattr(llm.Path, "exists", lambda _self: True)
    monkeypatch.setattr(
        llm.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=" keychain-value \n"),
    )

    assert llm.key_from_keychain("Svc", "Acct") == "keychain-value"


def test_key_from_keychain_returns_none_on_missing_binary(monkeypatch):
    monkeypatch.setattr(llm.Path, "exists", lambda _self: False)
    assert llm.key_from_keychain("Svc", "Acct") is None


def test_resolve_openai_api_key_prefers_keychain(monkeypatch):
    monkeypatch.setattr(llm, "key_from_keychain", lambda *_args: "k")
    monkeypatch.setenv("OPENAI_API_KEY", "env")

    assert llm.resolve_openai_api_key("Svc", "Acct") == "k"


def test_resolve_openai_api_key_falls_back_to_env(monkeypatch):
    monkeypatch.setattr(llm, "key_from_keychain", lambda *_args: None)
    monkeypatch.setenv("OPENAI_API_KEY", "  env  ")

    assert llm.resolve_openai_api_key("Svc", "Acct") == "env"


def test_openai_chat_json_missing_key_raises(monkeypatch):
    monkeypatch.setattr(llm, "resolve_openai_api_key", lambda **_kwargs: None)

    with pytest.raises(RuntimeError) as exc:
        llm.openai_chat_json("sys", "user", keychain_service="Svc", keychain_account="Acct")

    msg = str(exc.value)
    assert "service=Svc, account=Acct" in msg
    assert "OPENAI_API_KEY" in msg


def test_openai_chat_json_happy_path(monkeypatch):
    captured = {}

    class DummyResp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            body = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"ok": True}),
                        }
                    }
                ]
            }
            return json.dumps(body).encode("utf-8")

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["auth"] = req.headers.get("Authorization")
        payload = json.loads(req.data.decode("utf-8"))
        captured["payload"] = payload
        return DummyResp()

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)

    out = llm.openai_chat_json("system", "user", model="gpt-4.1-mini", api_key="key")

    assert out == {"ok": True}
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["timeout"] == 120
    assert captured["auth"] == "Bearer key"
    assert captured["payload"]["model"] == "gpt-4.1-mini"


def test_openai_chat_json_retries_without_temperature_when_unsupported(monkeypatch):
    seen_payloads = []

    class DummyResp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            body = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"ok": True}),
                        }
                    }
                ]
            }
            return json.dumps(body).encode("utf-8")

    def fake_urlopen(req, timeout):
        payload = json.loads(req.data.decode("utf-8"))
        seen_payloads.append(payload)
        if len(seen_payloads) == 1:
            body = json.dumps(
                {
                    "error": {
                        "message": "Unsupported value: 'temperature'",
                        "param": "temperature",
                        "code": "unsupported_value",
                    }
                }
            ).encode("utf-8")
            raise urllib.error.HTTPError(
                req.full_url,
                400,
                "Bad Request",
                hdrs=None,
                fp=BytesIO(body),
            )
        return DummyResp()

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)

    out = llm.openai_chat_json("system", "user", model="gpt-5-mini", api_key="key")

    assert out == {"ok": True}
    assert len(seen_payloads) == 2
    assert "temperature" in seen_payloads[0]
    assert "temperature" not in seen_payloads[1]


def test_openai_chat_json_surfaces_http_error_details(monkeypatch):
    def fake_urlopen(req, timeout):
        body = json.dumps(
            {
                "error": {
                    "message": "Invalid request field",
                    "param": "messages",
                    "code": "invalid_request_error",
                }
            }
        ).encode("utf-8")
        raise urllib.error.HTTPError(
            req.full_url,
            400,
            "Bad Request",
            hdrs=None,
            fp=BytesIO(body),
        )

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError) as exc:
        llm.openai_chat_json("system", "user", model="gpt-4.1-mini", api_key="key")

    msg = str(exc.value)
    assert "Invalid request field" in msg
    assert "param=messages" in msg


def test_chunked_respects_size():
    assert llm.chunked([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    assert llm.chunked([1, 2], 0) == [[1, 2]]


def test_call_with_retries_retries_then_succeeds(monkeypatch):
    attempts = {"n": 0}
    sleeps = []

    def fake_call(**_kwargs):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("boom")
        return {"ok": True}

    monkeypatch.setattr(llm.time, "sleep", lambda value: sleeps.append(value))

    out = llm.call_with_retries("sys", "user", tries=3, backoff_sec=2.0, openai_chat_json_fn=fake_call)

    assert out == {"ok": True}
    assert attempts["n"] == 3
    assert sleeps == [2.0, 4.0]


def test_classify_with_llm_maps_by_id_and_url_with_redaction_and_max_items():
    items = [_item(0), _item(1), _item(2)]
    indexed = list(enumerate(items))
    url_to_idx = {it.norm_url: idx for idx, it in indexed}

    seen = {}

    def fake_call(system, user, api_key):
        seen["user"] = user
        assert api_key == "k"
        return {
            "items": [
                {"id": "1", "topic": "alpha", "kind": "repo", "action": "build", "score": 5},
                {"url": items[0].clean_url, "topic": "beta", "kind": "docs", "action": "read", "score": 4},
            ]
        }

    cls = llm.classify_with_llm(
        indexed_for_cls=indexed,
        url_to_idx=url_to_idx,
        api_key="k",
        max_items=2,
        chunk_size=50,
        redact_llm=True,
        redact_text_fn=lambda text: f"R<{text}>",
        redact_url_fn=lambda url: f"U<{url}>",
        call_with_retries_fn=fake_call,
    )

    assert "- 0 | R<Title 0> | U<https://example.com/item/0?q=v0> | example.com" in seen["user"]
    assert "- 2 |" not in seen["user"]
    assert f"- kind: one of [{', '.join(POSTPROCESS_KIND_ORDER)}]" in seen["user"]
    assert f"- action: one of [{', '.join(POSTPROCESS_ACTION_ORDER)}]" in seen["user"]
    assert cls[1]["kind"] == "repo"
    assert cls[0]["kind"] == "docs"


def test_classify_with_llm_logs_and_continues_on_chunk_failure():
    item = _item(0)
    stderr = StringIO()

    cls = llm.classify_with_llm(
        indexed_for_cls=[(0, item)],
        url_to_idx={item.norm_url: 0},
        api_key="k",
        call_with_retries_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("bad")),
        stderr=stderr,
    )

    assert cls == {}
    assert "LLM classify failed" in stderr.getvalue()
