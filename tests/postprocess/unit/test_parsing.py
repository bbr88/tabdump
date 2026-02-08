from pathlib import Path

from core.postprocess.parsing import (
    extract_created_ts,
    extract_frontmatter_value,
    extract_items,
    parse_markdown_link_line,
)


def test_parse_markdown_link_line_simple():
    parsed = parse_markdown_link_line("- [Example](https://example.com)")
    assert parsed == ("Example", "https://example.com")


def test_parse_markdown_link_line_nested_title_and_url_parentheses():
    line = "- [A [nested] title](https://example.com/a_(b)/c)"
    parsed = parse_markdown_link_line(line)
    assert parsed == ("A [nested] title", "https://example.com/a_(b)/c")


def test_parse_markdown_link_line_rejects_trailing_garbage():
    assert parse_markdown_link_line("- [Example](https://example.com) trailing") is None


def test_parse_markdown_link_line_rejects_malformed_markdown():
    assert parse_markdown_link_line("- [Missing close(https://example.com)") is None
    assert parse_markdown_link_line("- [Title] https://example.com") is None
    assert parse_markdown_link_line("just text") is None


def test_extract_items_tracks_browser_and_ignores_window_headings():
    md = (
        "## Chrome\n"
        "### Window 1\n"
        "- [One](https://example.com/a)\n"
        "## Safari\n"
        "- [Two](https://example.com/b)\n"
        "## Firefox\n"
        "- [Three](https://example.com/c)\n"
    )

    items = extract_items(md)

    assert len(items) == 3
    assert items[0].browser == "chrome"
    assert items[1].browser == "safari"
    assert items[2].browser == "firefox"
    assert items[0].clean_url == "https://example.com/a"


def test_extract_items_uses_injected_url_functions():
    md = "## Chrome\n- [T](https://example.com/path?q=1)\n"

    items = extract_items(
        md,
        normalize_url_fn=lambda _: "normalized",
        domain_of_fn=lambda _: "domain.test",
    )

    assert len(items) == 1
    assert items[0].norm_url == "normalized"
    assert items[0].clean_url == "normalized"
    assert items[0].domain == "domain.test"


def test_extract_created_ts_from_frontmatter(tmp_path: Path):
    path = tmp_path / "dump.md"
    path.write_text(
        "---\ncreated: \"2026-02-07 00-00-00\"\n---\n",
        encoding="utf-8",
    )

    assert extract_created_ts(path, fallback="fallback") == "2026-02-07 00-00-00"


def test_extract_created_ts_falls_back_when_missing(tmp_path: Path):
    path = tmp_path / "dump.md"
    path.write_text("---\nnope: 1\n---\n", encoding="utf-8")

    assert extract_created_ts(path, fallback="fallback") == "fallback"


def test_extract_frontmatter_value_reads_only_frontmatter_block(tmp_path: Path):
    path = tmp_path / "dump.md"
    path.write_text(
        "---\n"
        "tabdump_id: \"abc-123\"\n"
        "---\n"
        "tabdump_id: not-this\n",
        encoding="utf-8",
    )

    assert extract_frontmatter_value(path, "tabdump_id") == "abc-123"


def test_extract_frontmatter_value_returns_none_without_frontmatter(tmp_path: Path):
    path = tmp_path / "dump.md"
    path.write_text("tabdump_id: abc-123\n", encoding="utf-8")

    assert extract_frontmatter_value(path, "tabdump_id") is None
