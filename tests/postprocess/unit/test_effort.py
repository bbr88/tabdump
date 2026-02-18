from core.tab_policy.effort import (
    effort_distance,
    normalize_effort,
    resolve_effort,
    resolve_effort_decision,
)


def test_normalize_effort_and_distance_helpers():
    assert normalize_effort(" Quick ") == "quick"
    assert normalize_effort("slow") is None
    assert effort_distance("quick", "deep") == 2
    assert effort_distance("medium", "deep") == 1
    assert effort_distance("invalid", "deep") is None


def test_video_effort_varies_from_clip_to_full_course():
    quick = resolve_effort(
        kind="video",
        action="watch",
        title="Movie trailer 2 min",
        url="https://media.example/trailer",
        domain="media.example",
    )
    deep = resolve_effort(
        kind="video",
        action="watch",
        title="Full course personal finance 4h",
        url="https://academy.example/full-course",
        domain="academy.example",
    )
    assert quick == "quick"
    assert deep == "deep"


def test_docs_and_article_effort_handles_reference_and_longform():
    docs_quick = resolve_effort(
        kind="docs",
        action="reference",
        title="API reference cheat sheet",
        url="https://docs.example/reference",
        domain="docs.example",
    )
    docs_deep = resolve_effort(
        kind="docs",
        action="read",
        title="Complete guide to retirement planning",
        url="https://docs.example/guide",
        domain="docs.example",
    )
    article_medium = resolve_effort(
        kind="article",
        action="read",
        title="How to negotiate salary",
        url="https://blog.example/post",
        domain="blog.example",
    )
    assert docs_quick == "quick"
    assert docs_deep == "deep"
    assert article_medium == "medium"


def test_repo_and_tool_effort_handles_glance_vs_workflow():
    repo_quick = resolve_effort(
        kind="repo",
        action="triage",
        title="Issue triage board",
        url="https://projects.example/repo/issues",
        domain="projects.example",
    )
    repo_deep = resolve_effort(
        kind="repo",
        action="build",
        title="Architecture migration plan",
        url="https://projects.example/repo/migration",
        domain="projects.example",
    )
    tool_quick = resolve_effort(
        kind="tool",
        action="triage",
        title="Calendar dashboard",
        url="https://apps.example/calendar",
        domain="apps.example",
    )
    tool_deep = resolve_effort(
        kind="tool",
        action="build",
        title="End-to-end automation workflow setup",
        url="https://apps.example/workflow",
        domain="apps.example",
    )
    assert repo_quick == "quick"
    assert repo_deep == "deep"
    assert tool_quick == "quick"
    assert tool_deep == "deep"


def test_paper_and_sensitive_kinds():
    paper_medium = resolve_effort(
        kind="paper",
        action="read",
        title="Research paper abstract summary",
        url="https://research.example/summary.pdf",
        domain="research.example",
    )
    paper_deep = resolve_effort(
        kind="paper",
        action="deep_work",
        title="Curriculum research workshop",
        url="https://research.example/workshop.pdf",
        domain="research.example",
    )
    auth_quick = resolve_effort(
        kind="auth",
        action="ignore",
        title="Account login",
        url="https://auth.example/login",
        domain="auth.example",
    )
    auth_medium = resolve_effort(
        kind="auth",
        action="triage",
        title="Billing setup workflow",
        url="https://auth.example/billing-setup",
        domain="auth.example",
    )
    assert paper_medium == "medium"
    assert paper_deep == "deep"
    assert auth_quick == "quick"
    assert auth_medium == "medium"


def test_duration_parsing_variants():
    long_hms = resolve_effort(
        kind="video",
        action="watch",
        title="Workshop 03:20:00",
        url="https://media.example/workshop",
        domain="media.example",
    )
    short_minutes = resolve_effort(
        kind="article",
        action="read",
        title="Quick recap 12 min",
        url="https://blog.example/recap",
        domain="blog.example",
    )
    assert long_hms == "deep"
    assert short_minutes == "quick"


def test_provided_effort_is_advisory_with_guardrails():
    accepted = resolve_effort_decision(
        kind="tool",
        action="build",
        title="Planning dashboard overview",
        url="https://apps.example/planner",
        domain="apps.example",
        provided_effort="quick",
    )
    rejected = resolve_effort_decision(
        kind="video",
        action="watch",
        title="Full course 4h",
        url="https://academy.example/full-course",
        domain="academy.example",
        provided_effort="quick",
    )
    assert accepted.effort == "quick"
    assert "advisory:accepted" in accepted.reasons
    assert rejected.effort == "deep"
    assert "advisory:rejected" in rejected.reasons
