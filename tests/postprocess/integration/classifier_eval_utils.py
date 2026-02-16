"""Shared helpers for classifier comparison tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib.parse import urlsplit

from core.postprocess.classify_local import classify_local
from core.postprocess.coerce import safe_action, safe_kind, safe_score, safe_topic
from core.postprocess.models import Item
from core.postprocess.urls import normalize_url
from core.tab_policy.text import slugify_kebab

ROOT_DIR = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures" / "classifier_eval"
GOLD_FIXTURE_PATH = FIXTURE_DIR / "gold_generic_v1.json"
FROZEN_FIXTURE_PATH = FIXTURE_DIR / "llm_predictions_frozen_v1.json"

DEFAULT_MODEL_MATRIX: Tuple[str, ...] = ("gpt-4.1-mini", "gpt-4.1", "gpt-5-nano")
ACCURACY_THRESHOLDS = {
    "kind": 0.80,
    "action": 0.80,
    "topic": 0.70,
    "score_within_1": 0.85,
}
PAIRWISE_THRESHOLDS = {
    "kind": 0.75,
    "action": 0.75,
}


def _topic_slug(value: str) -> str:
    return slugify_kebab(value, fallback="misc")


def _canonicalize(raw: object, *, domain: str) -> dict:
    payload = raw if isinstance(raw, dict) else {}
    score = safe_score(payload.get("score"))
    return {
        "topic": _topic_slug(safe_topic(payload.get("topic"), domain)),
        "kind": safe_kind(payload.get("kind")),
        "action": safe_action(payload.get("action")),
        "score": score if score is not None else 3,
    }


def load_gold_fixture() -> dict:
    return json.loads(GOLD_FIXTURE_PATH.read_text(encoding="utf-8"))


def load_gold_cases() -> List[dict]:
    data = load_gold_fixture()
    cases = data.get("cases")
    if not isinstance(cases, list):
        raise AssertionError(f"Invalid gold fixture format in {GOLD_FIXTURE_PATH}")
    return cases


def build_item(case: dict) -> Item:
    url = str(case["url"])
    clean = normalize_url(url)
    domain = urlsplit(clean).hostname or ""
    return Item(
        title=str(case["title"]),
        url=url,
        norm_url=clean,
        clean_url=clean,
        domain=domain,
        browser=None,
    )


def expected_by_case(cases: Iterable[dict]) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for case in cases:
        case_id = str(case["id"])
        item = build_item(case)
        out[case_id] = _canonicalize(case.get("expected", {}), domain=item.domain)
    return out


def predict_local(cases: Iterable[dict]) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for case in cases:
        case_id = str(case["id"])
        item = build_item(case)
        out[case_id] = _canonicalize(classify_local(item), domain=item.domain)
    return out


def load_frozen_predictions(cases: Iterable[dict]) -> Dict[str, Dict[str, dict]]:
    data = json.loads(FROZEN_FIXTURE_PATH.read_text(encoding="utf-8"))
    raw_models = data.get("models")
    if not isinstance(raw_models, dict):
        raise AssertionError(f"Invalid frozen fixture format in {FROZEN_FIXTURE_PATH}")

    case_list = list(cases)
    case_ids = {str(case["id"]) for case in case_list}

    models: Dict[str, Dict[str, dict]] = {}
    for model_name, raw_predictions in raw_models.items():
        if not isinstance(raw_predictions, dict):
            raise AssertionError(f"Invalid model payload for '{model_name}' in {FROZEN_FIXTURE_PATH}")
        extra = sorted(set(raw_predictions) - case_ids)
        if extra:
            raise AssertionError(f"Unexpected case ids for model '{model_name}': {extra}")
        missing = sorted(case_ids - set(raw_predictions))
        if missing:
            raise AssertionError(f"Missing case ids for model '{model_name}': {missing}")

        model_out: Dict[str, dict] = {}
        for case in case_list:
            case_id = str(case["id"])
            item = build_item(case)
            model_out[case_id] = _canonicalize(raw_predictions.get(case_id, {}), domain=item.domain)
        models[str(model_name)] = model_out
    return models


def evaluate_against_gold(cases: Iterable[dict], predictions: Dict[str, dict]) -> dict:
    expected = expected_by_case(cases)
    case_list = list(cases)
    total = len(case_list)
    if total == 0:
        raise AssertionError("No classifier eval cases found.")

    topic_hits = 0
    kind_hits = 0
    action_hits = 0
    score_hits = 0

    mismatches = {
        "topic": [],
        "kind": [],
        "action": [],
        "score_within_1": [],
    }
    for case in case_list:
        case_id = str(case["id"])
        exp = expected[case_id]
        got = predictions.get(case_id)
        if got is None:
            item = build_item(case)
            got = _canonicalize({}, domain=item.domain)

        if got["topic"] == exp["topic"]:
            topic_hits += 1
        else:
            mismatches["topic"].append(case_id)

        if got["kind"] == exp["kind"]:
            kind_hits += 1
        else:
            mismatches["kind"].append(case_id)

        if got["action"] == exp["action"]:
            action_hits += 1
        else:
            mismatches["action"].append(case_id)

        if abs(int(got["score"]) - int(exp["score"])) <= 1:
            score_hits += 1
        else:
            mismatches["score_within_1"].append(case_id)

    return {
        "total": total,
        "accuracy": {
            "topic": topic_hits / total,
            "kind": kind_hits / total,
            "action": action_hits / total,
            "score_within_1": score_hits / total,
        },
        "mismatches": mismatches,
    }


def evaluate_pairwise(cases: Iterable[dict], lhs: Dict[str, dict], rhs: Dict[str, dict]) -> dict:
    case_list = list(cases)
    total = len(case_list)
    if total == 0:
        raise AssertionError("No classifier eval cases found.")

    kind_hits = 0
    action_hits = 0
    kind_mismatch = []
    action_mismatch = []

    for case in case_list:
        case_id = str(case["id"])
        left = lhs.get(case_id) or {}
        right = rhs.get(case_id) or {}

        if left.get("kind") == right.get("kind"):
            kind_hits += 1
        else:
            kind_mismatch.append(case_id)

        if left.get("action") == right.get("action"):
            action_hits += 1
        else:
            action_mismatch.append(case_id)

    return {
        "kind": kind_hits / total,
        "action": action_hits / total,
        "mismatches": {
            "kind": kind_mismatch,
            "action": action_mismatch,
        },
    }


def run_live_llm_predictions(cases: Iterable[dict], *, model: str, api_key: str) -> Dict[str, dict]:
    from core.postprocess import llm

    case_list = list(cases)
    items = [build_item(case) for case in case_list]
    indexed = list(enumerate(items))
    url_to_idx = {item.norm_url: idx for idx, item in indexed}

    def _call(_system: str, _user: str, _api_key: str):
        return llm.openai_chat_json(
            _system,
            _user,
            model=model,
            api_key=_api_key,
        )

    cls_map = llm.classify_with_llm(
        indexed_for_cls=indexed,
        url_to_idx=url_to_idx,
        api_key=api_key,
        max_items=0,
        chunk_size=30,
        redact_llm=False,
        call_with_retries_fn=lambda system, user, api_key: _call(system, user, api_key),
    )

    out: Dict[str, dict] = {}
    for idx, case in enumerate(case_list):
        case_id = str(case["id"])
        item = items[idx]
        out[case_id] = _canonicalize(cls_map.get(idx, {}), domain=item.domain)
    return out


def write_frozen_predictions(model_predictions: Dict[str, Dict[str, dict]]) -> None:
    payload = {
        "version": "v1",
        "models": model_predictions,
    }
    FROZEN_FIXTURE_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
