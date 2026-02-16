import itertools
import os

import pytest

from core.postprocess import llm
from tests.postprocess.integration.classifier_eval_utils import (
    ACCURACY_THRESHOLDS,
    DEFAULT_MODEL_MATRIX,
    PAIRWISE_THRESHOLDS,
    evaluate_against_gold,
    evaluate_pairwise,
    load_gold_cases,
    predict_local,
    run_live_llm_predictions,
    write_frozen_predictions,
)

pytestmark = pytest.mark.live_llm


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def _model_matrix() -> list[str]:
    raw = os.environ.get("TABDUMP_LLM_COMPARE_MODELS", "")
    if not raw.strip():
        return list(DEFAULT_MODEL_MATRIX)
    return [part.strip() for part in raw.split(",") if part.strip()]


def test_live_classifier_matrix_reports_accuracy_and_pairwise_agreement():
    if not _env_flag("TABDUMP_LIVE_LLM_EVAL"):
        pytest.skip("Set TABDUMP_LIVE_LLM_EVAL=1 to run live classifier evaluation.")

    api_key = llm.resolve_openai_api_key("TabDump", "openai")
    if not api_key:
        pytest.skip("OpenAI API key not configured.")

    cases = load_gold_cases()
    models = _model_matrix()
    local_predictions = predict_local(cases)

    live_predictions = {}
    for model in models:
        live_predictions[model] = run_live_llm_predictions(cases, model=model, api_key=api_key)

    print("\nclassifier-accuracy-vs-gold")
    for label, predictions in [("local", local_predictions), *live_predictions.items()]:
        metrics = evaluate_against_gold(cases, predictions)
        accuracy = metrics["accuracy"]
        print(
            f"{label}: topic={accuracy['topic']:.2%} kind={accuracy['kind']:.2%} "
            f"action(raw)={accuracy['action_raw']:.2%} "
            f"action(kind-derived)={accuracy['action_kind_derived']:.2%} "
            f"score±1={accuracy['score_within_1']:.2%}"
        )

    print("\npairwise-kind-action-agreement")
    all_predictions = {"local": local_predictions, **live_predictions}
    for left, right in itertools.combinations(sorted(all_predictions), 2):
        pair = evaluate_pairwise(cases, all_predictions[left], all_predictions[right])
        print(f"{left} vs {right}: kind={pair['kind']:.2%} action={pair['action']:.2%}")

    if _env_flag("TABDUMP_LIVE_LLM_ENFORCE_THRESHOLDS"):
        for model, predictions in live_predictions.items():
            metrics = evaluate_against_gold(cases, predictions)
            for field, threshold in ACCURACY_THRESHOLDS.items():
                assert metrics["accuracy"][field] >= threshold, (
                    f"{model} {field} accuracy {metrics['accuracy'][field]:.2%} below {threshold:.0%}; "
                    f"mismatches={metrics['mismatches'][field]}"
                )

        for left, right in itertools.combinations(sorted(all_predictions), 2):
            pair = evaluate_pairwise(cases, all_predictions[left], all_predictions[right])
            for field, threshold in PAIRWISE_THRESHOLDS.items():
                assert pair[field] >= threshold, (
                    f"{left} vs {right} {field} agreement {pair[field]:.2%} below {threshold:.0%}; "
                    f"mismatches={pair['mismatches'][field]}"
                )

    if _env_flag("TABDUMP_REFRESH_LLM_FIXTURES"):
        required_models = set(DEFAULT_MODEL_MATRIX)
        present_models = set(live_predictions)
        missing = sorted(required_models - present_models)
        if missing:
            pytest.fail(
                "Cannot refresh frozen fixtures without the default model matrix. "
                f"Missing: {missing}"
            )
        write_frozen_predictions({model: live_predictions[model] for model in DEFAULT_MODEL_MATRIX})
