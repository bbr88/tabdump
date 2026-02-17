from core.postprocess.coerce import (
    normalize_action,
    safe_action,
    safe_effort,
    safe_kind,
    safe_prio,
    safe_score,
    safe_topic,
)


def test_safe_topic_prefers_non_empty_string_then_domain_then_misc():
    assert safe_topic("python", "example.com") == "python"
    assert safe_topic("  ", "example.com") == "example-com"
    assert safe_topic(None, "") == "misc"


def test_safe_kind_accepts_known_values_only():
    assert safe_kind("Docs") == "docs"
    assert safe_kind("music") == "music"
    assert safe_kind("unknown") == "misc"
    assert safe_kind(None) == "misc"


def test_safe_action_accepts_known_values_only():
    assert safe_action("Build") == "build"
    assert safe_action("listen") == "watch"
    assert safe_action("browse") == "read"
    assert safe_action("view") == "read"
    assert safe_action("unknown") == "triage"
    assert safe_action(None) == "triage"


def test_normalize_action_supports_aliases_and_unknowns():
    assert normalize_action("listen") == "watch"
    assert normalize_action("build") == "build"
    assert normalize_action("unknown") is None
    assert normalize_action(None) is None


def test_safe_score_parses_and_clamps():
    assert safe_score("4") == 4
    assert safe_score(10) == 5
    assert safe_score(-2) == 0
    assert safe_score("bad") is None
    assert safe_score(None) is None


def test_safe_effort_accepts_known_values_only():
    assert safe_effort("Quick") == "quick"
    assert safe_effort("medium") == "medium"
    assert safe_effort("deep") == "deep"
    assert safe_effort("slow") is None
    assert safe_effort(None) is None


def test_safe_prio_accepts_known_priorities():
    assert safe_prio("P1") == "p1"
    assert safe_prio("p3") == "p3"
    assert safe_prio("p4") is None
    assert safe_prio(None) is None
