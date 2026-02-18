import re

import pytest

from tests.postprocess.integration.effort_eval_utils import (
    EFFORT_THRESHOLDS,
    PER_KIND_EXACT_THRESHOLD,
    PER_KIND_MIN_CASES,
    STRUCTURAL_COLLAPSE_KINDS,
    evaluate_effort,
    format_confusion,
    load_effort_cases,
    load_effort_fixture,
    predict_effort_resolver,
    should_enforce_effort_thresholds,
)


def test_effort_fixture_schema():
    fixture = load_effort_fixture()
    assert fixture["version"] == "v1"
    cases = fixture.get("cases")
    assert isinstance(cases, list)
    assert len(cases) >= 120

    ids = [str(case["id"]) for case in cases]
    assert len(ids) == len(set(ids))

    for case in cases:
        assert isinstance(case["title"], str) and case["title"].strip()
        assert isinstance(case["url"], str) and case["url"].startswith("http")
        assert isinstance(case["kind"], str) and case["kind"].strip()
        assert isinstance(case["action"], str) and case["action"].strip()
        assert case["expected_effort"] in {"quick", "medium", "deep"}
        accepted = case.get("accepted_efforts")
        if accepted is not None:
            assert isinstance(accepted, list) and accepted
            assert all(item in {"quick", "medium", "deep"} for item in accepted)
        provided = case.get("provided_effort")
        if provided is not None:
            assert provided in {"quick", "medium", "deep"}
        assert isinstance(case.get("rationale"), str) and case["rationale"].strip()
        assert re.fullmatch(r"[a-z0-9_\\-]+", str(case["id"]))


def test_effort_estimation_reports_metrics_and_confusion_matrix():
    cases = load_effort_cases()
    predictions = predict_effort_resolver(cases)
    metrics = evaluate_effort(cases, predictions)

    accuracy = metrics["accuracy"]
    print("\neffort-accuracy-vs-gold")
    print(
        f"resolver: exact={accuracy['exact']:.2%} "
        f"within_one_band={accuracy['within_one_band']:.2%}"
    )

    print("\neffort-per-kind-exact")
    per_kind_total = metrics["per_kind"]["total"]
    per_kind_exact = metrics["per_kind"]["exact"]
    for kind in sorted(per_kind_total):
        print(
            f"{kind}: n={per_kind_total[kind]} exact={per_kind_exact[kind]:.2%} "
            f"bands={metrics['per_kind']['predicted_bands'][kind]}"
        )

    print("\neffort-confusion-matrix")
    for line in format_confusion(metrics["confusion"]):
        print(line)

    for kind in STRUCTURAL_COLLAPSE_KINDS:
        bands = set(metrics["per_kind"]["predicted_bands"].get(kind, []))
        assert len(bands) >= 2, f"{kind} effort collapsed to {sorted(bands)}"

    if should_enforce_effort_thresholds():
        assert accuracy["exact"] >= EFFORT_THRESHOLDS["exact"], (
            f"exact effort accuracy {accuracy['exact']:.2%} below "
            f"{EFFORT_THRESHOLDS['exact']:.0%}; mismatches={metrics['mismatches']['exact']}"
        )
        assert accuracy["within_one_band"] >= EFFORT_THRESHOLDS["within_one_band"], (
            f"within_one_band effort accuracy {accuracy['within_one_band']:.2%} below "
            f"{EFFORT_THRESHOLDS['within_one_band']:.0%}; "
            f"mismatches={metrics['mismatches']['within_one_band']}"
        )
        for kind, total in metrics["per_kind"]["total"].items():
            if total < PER_KIND_MIN_CASES:
                continue
            exact = metrics["per_kind"]["exact"][kind]
            assert exact >= PER_KIND_EXACT_THRESHOLD, (
                f"{kind} effort exact accuracy {exact:.2%} below {PER_KIND_EXACT_THRESHOLD:.0%}"
            )


def test_effort_estimation_with_strict_thresholds_env(monkeypatch):
    monkeypatch.setenv("TABDUMP_EVAL_ENFORCE_EFFORT", "1")
    cases = load_effort_cases()
    predictions = predict_effort_resolver(cases)
    metrics = evaluate_effort(cases, predictions)

    assert metrics["accuracy"]["exact"] >= EFFORT_THRESHOLDS["exact"]
    assert metrics["accuracy"]["within_one_band"] >= EFFORT_THRESHOLDS["within_one_band"]
