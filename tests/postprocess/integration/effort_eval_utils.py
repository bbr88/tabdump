"""Shared helpers for effort estimation benchmark tests."""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib.parse import urlsplit

from core.tab_policy.effort import effort_distance, normalize_effort, resolve_effort

ROOT_DIR = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures" / "effort_eval"
GOLD_EFFORT_V1_PATH = FIXTURE_DIR / "gold_effort_v1.json"

EFFORT_THRESHOLDS = {
    "exact": 0.80,
    "within_one_band": 0.96,
}
PER_KIND_EXACT_THRESHOLD = 0.70
PER_KIND_MIN_CASES = 10
STRUCTURAL_COLLAPSE_KINDS: Tuple[str, ...] = ("video", "docs", "article", "repo", "tool")


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def should_enforce_effort_thresholds() -> bool:
    return _env_flag("TABDUMP_EVAL_ENFORCE_EFFORT", default=False)


def resolve_effort_fixture_path() -> Path:
    override = os.environ.get("TABDUMP_EFFORT_GOLD_FIXTURE", "").strip()
    if override:
        return Path(override).expanduser()
    return GOLD_EFFORT_V1_PATH


def load_effort_fixture() -> dict:
    path = resolve_effort_fixture_path()
    return json.loads(path.read_text(encoding="utf-8"))


def load_effort_cases() -> List[dict]:
    data = load_effort_fixture()
    cases = data.get("cases")
    if not isinstance(cases, list):
        raise AssertionError(f"Invalid effort fixture format in {resolve_effort_fixture_path()}")
    return cases


def _accepted_efforts(case: dict) -> set[str]:
    expected = normalize_effort(case.get("expected_effort"))
    if expected is None:
        raise AssertionError(f"Case '{case.get('id')}' has invalid expected_effort")

    accepted = {expected}
    raw = case.get("accepted_efforts")
    if isinstance(raw, list):
        for candidate in raw:
            normalized = normalize_effort(candidate)
            if normalized:
                accepted.add(normalized)
    return accepted


def predict_effort_resolver(cases: Iterable[dict]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for case in cases:
        case_id = str(case["id"])
        url = str(case["url"])
        domain = urlsplit(url).hostname or ""
        effort = resolve_effort(
            kind=str(case.get("kind", "")),
            action=str(case.get("action", "")),
            title=str(case.get("title", "")),
            url=url,
            domain=domain,
            provided_effort=case.get("provided_effort"),
        )
        out[case_id] = effort
    return out


def evaluate_effort(cases: Iterable[dict], predictions: Dict[str, str]) -> dict:
    case_list = list(cases)
    total = len(case_list)
    if total == 0:
        raise AssertionError("No effort eval cases found.")

    exact_hits = 0
    within_one_hits = 0
    mismatches_exact: List[str] = []
    mismatches_within_one: List[str] = []

    confusion = defaultdict(Counter)
    per_kind_total = Counter()
    per_kind_hits = Counter()
    predicted_bands_by_kind: Dict[str, set[str]] = defaultdict(set)

    for case in case_list:
        case_id = str(case["id"])
        kind = str(case.get("kind", "")).strip().lower()
        expected = normalize_effort(case.get("expected_effort"))
        if expected is None:
            raise AssertionError(f"Case '{case_id}' has invalid expected_effort")
        accepted = _accepted_efforts(case)

        got_raw = predictions.get(case_id)
        got = normalize_effort(got_raw) or "medium"
        confusion[expected][got] += 1
        per_kind_total[kind] += 1
        predicted_bands_by_kind[kind].add(got)

        if got in accepted:
            exact_hits += 1
            per_kind_hits[kind] += 1
        else:
            mismatches_exact.append(case_id)

        distances = [effort_distance(got, accepted_effort) for accepted_effort in accepted]
        min_distance = min(distance for distance in distances if distance is not None)
        if min_distance <= 1:
            within_one_hits += 1
        else:
            mismatches_within_one.append(case_id)

    per_kind_exact = {
        kind: (per_kind_hits[kind] / per_kind_total[kind]) for kind in sorted(per_kind_total)
    }

    return {
        "total": total,
        "accuracy": {
            "exact": exact_hits / total,
            "within_one_band": within_one_hits / total,
        },
        "mismatches": {
            "exact": mismatches_exact,
            "within_one_band": mismatches_within_one,
        },
        "confusion": {
            expected: {pred: counter.get(pred, 0) for pred in ("quick", "medium", "deep")}
            for expected, counter in confusion.items()
        },
        "per_kind": {
            "total": dict(per_kind_total),
            "exact": per_kind_exact,
            "predicted_bands": {kind: sorted(bands) for kind, bands in predicted_bands_by_kind.items()},
        },
    }


def format_confusion(confusion: Dict[str, Dict[str, int]]) -> List[str]:
    rows = ["expected\\\\pred quick medium deep"]
    for expected in ("quick", "medium", "deep"):
        row = confusion.get(expected, {})
        rows.append(
            f"{expected:>7} {int(row.get('quick', 0)):>5} {int(row.get('medium', 0)):>6} {int(row.get('deep', 0)):>4}"
        )
    return rows
