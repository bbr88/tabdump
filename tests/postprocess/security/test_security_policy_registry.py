"""Contract tests for security policy registry coverage and consistency."""

import re
from pathlib import Path

from tests.security_policy import POLICIES

TESTS_DIR = Path(__file__).resolve().parents[2]
POLICY_MARK_RE = re.compile(r"pytest\.mark\.policy\(\s*['\"](SEC-\d{3})['\"]\s*\)")


def _collect_policy_markers() -> set[str]:
    found: set[str] = set()
    for path in TESTS_DIR.rglob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        for match in POLICY_MARK_RE.findall(text):
            found.add(match)
    return found


def test_security_policy_ids_are_unique_and_well_formed():
    ids = list(POLICIES.keys())
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"SEC-\d{3}", pid) for pid in ids)


def test_every_policy_has_at_least_one_referencing_test():
    referenced = _collect_policy_markers()
    missing = sorted(set(POLICIES) - referenced)
    assert not missing, f"Policies missing test references: {', '.join(missing)}"


def test_all_policy_markers_reference_declared_policies():
    referenced = _collect_policy_markers()
    unknown = sorted(referenced - set(POLICIES))
    assert not unknown, f"Unknown policy IDs referenced in tests: {', '.join(unknown)}"
