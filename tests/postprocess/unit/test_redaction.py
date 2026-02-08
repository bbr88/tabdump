from core.postprocess.redaction import redact_text_for_llm, redact_url_for_llm, strip_control_chars


def test_strip_control_chars():
    assert strip_control_chars("ab\x00cd\x1fef") == "abcdef"


def test_redact_text_for_llm_redacts_sensitive_keys_and_truncates():
    text = "token=abc secret:xyz hello"
    out = redact_text_for_llm(text, max_title=18)

    assert "abc" not in out
    assert "xyz" not in out
    assert "token=[REDACTED]" in out
    assert out.endswith("...")


def test_redact_url_for_llm_redacts_query_values_by_default():
    out = redact_url_for_llm("https://example.com/cb?token=abc&foo=bar")

    assert out == "https://example.com/cb?token=REDACTED&foo=REDACTED"


def test_redact_url_for_llm_can_preserve_query_when_disabled():
    out = redact_url_for_llm("https://example.com/cb?token=abc&foo=bar", redact_query=False)
    assert out == "https://example.com/cb?token=abc&foo=bar"


def test_redact_url_for_llm_returns_non_network_values_unchanged():
    assert redact_url_for_llm("just-a-value") == "just-a-value"
