"""Pytest configuration for shared test markers and policy validation."""

from pathlib import Path

import pytest

from tests.security_policy import POLICIES


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "policy(policy_id): map a test to a security policy ID from tests/security_policy.py",
    )
    config.addinivalue_line(
        "markers",
        "live_llm: runs live OpenAI-backed classifier comparison tests (opt-in only).",
    )


def _requires_policy_marker(item) -> bool:
    path = getattr(item, "path", None)
    if path is None:
        path = Path(str(getattr(item, "fspath", "")))
    return Path(str(path)).name == "test_postprocess_security_policy.py"


def pytest_collection_modifyitems(config, items):
    known_ids = set(POLICIES)
    for item in items:
        policy_markers = list(item.iter_markers(name="policy"))

        if _requires_policy_marker(item) and not policy_markers:
            raise pytest.UsageError(
                f"Missing policy marker on {item.nodeid}. "
                "All tests in test_postprocess_security_policy.py must declare @pytest.mark.policy('SEC-xxx')."
            )

        for marker in policy_markers:
            if marker.kwargs or len(marker.args) != 1:
                raise pytest.UsageError(
                    f"Invalid policy marker on {item.nodeid}. Use @pytest.mark.policy('SEC-xxx')."
                )
            policy_id = marker.args[0]
            if not isinstance(policy_id, str):
                raise pytest.UsageError(
                    f"Invalid policy marker on {item.nodeid}. policy_id must be a string."
                )
            if policy_id not in known_ids:
                raise pytest.UsageError(
                    f"Unknown policy id '{policy_id}' on {item.nodeid}. "
                    "Add it to tests/security_policy.py."
                )
