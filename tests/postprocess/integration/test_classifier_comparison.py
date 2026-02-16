import itertools
import re

import pytest

from core.postprocess import llm as llm_module
from core.tab_policy.taxonomy import POSTPROCESS_ACTIONS, POSTPROCESS_KINDS
from tests.postprocess.integration.classifier_eval_utils import (
    ACCURACY_THRESHOLDS,
    DEFAULT_MODEL_MATRIX,
    PAIRWISE_THRESHOLDS,
    load_frozen_predictions,
    load_gold_cases,
    load_gold_fixture,
    predict_local,
    evaluate_against_gold,
    evaluate_pairwise,
    run_live_llm_predictions,
)


def _assert_accuracy(label: str, metrics: dict):
    accuracy = metrics["accuracy"]
    mismatches = metrics["mismatches"]
    for field, threshold in ACCURACY_THRESHOLDS.items():
        actual = accuracy[field]
        assert actual >= threshold, (
            f"{label} {field} accuracy {actual:.2%} below {threshold:.0%}; "
            f"mismatches={mismatches[field]}"
        )


def _assert_pairwise(label: str, pair_metrics: dict):
    for field, threshold in PAIRWISE_THRESHOLDS.items():
        actual = pair_metrics[field]
        assert actual >= threshold, (
            f"{label} {field} agreement {actual:.2%} below {threshold:.0%}; "
            f"mismatches={pair_metrics['mismatches'][field]}"
        )


def test_classifier_eval_gold_fixture_schema():
    fixture = load_gold_fixture()
    assert fixture["version"] == "v1"
    assert isinstance(fixture["cases"], list)
    assert len(fixture["cases"]) == 24

    ids = [str(case["id"]) for case in fixture["cases"]]
    assert len(ids) == len(set(ids))

    for case in fixture["cases"]:
        assert isinstance(case["title"], str) and case["title"].strip()
        assert isinstance(case["url"], str) and case["url"].startswith("http")
        expected = case["expected"]
        assert {"topic", "kind", "action", "score"} <= set(expected)
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(expected["topic"]))
        assert expected["kind"] in POSTPROCESS_KINDS
        assert expected["action"] in POSTPROCESS_ACTIONS
        assert isinstance(expected["score"], int)
        assert 1 <= expected["score"] <= 5


def test_local_classifier_accuracy_against_generic_gold():
    cases = load_gold_cases()
    predictions = predict_local(cases)
    metrics = evaluate_against_gold(cases, predictions)

    _assert_accuracy("local", metrics)


@pytest.mark.parametrize("model_name", DEFAULT_MODEL_MATRIX)
def test_frozen_llm_model_accuracy_against_generic_gold(model_name: str):
    cases = load_gold_cases()
    frozen = load_frozen_predictions(cases)
    predictions = frozen[model_name]
    metrics = evaluate_against_gold(cases, predictions)

    _assert_accuracy(model_name, metrics)


def test_pairwise_kind_action_agreement_between_local_and_frozen_models():
    cases = load_gold_cases()
    local = predict_local(cases)
    frozen = load_frozen_predictions(cases)
    all_predictions = {"local": local, **frozen}

    for left, right in itertools.combinations(sorted(all_predictions), 2):
        pair_metrics = evaluate_pairwise(cases, all_predictions[left], all_predictions[right])
        _assert_pairwise(f"{left} vs {right}", pair_metrics)


def test_run_live_predictions_fails_when_no_items_are_mapped(monkeypatch):
    cases = load_gold_cases()[:1]

    monkeypatch.setattr(llm_module, "classify_with_llm", lambda *args, **kwargs: {})

    with pytest.raises(RuntimeError) as exc:
        run_live_llm_predictions(cases, model="gpt-5-mini", api_key="k")

    assert "0 mapped classifications" in str(exc.value)
