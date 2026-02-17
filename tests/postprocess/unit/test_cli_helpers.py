from pathlib import Path

from core.postprocess import cli


def test_env_flag_reads_truthy_values_and_defaults(monkeypatch):
    monkeypatch.delenv("TABDUMP_TEST_FLAG", raising=False)
    assert cli._env_flag("TABDUMP_TEST_FLAG", default=False) is False
    assert cli._env_flag("TABDUMP_TEST_FLAG", default=True) is True

    monkeypatch.setenv("TABDUMP_TEST_FLAG", "yes")
    assert cli._env_flag("TABDUMP_TEST_FLAG", default=False) is True

    monkeypatch.setenv("TABDUMP_TEST_FLAG", "0")
    assert cli._env_flag("TABDUMP_TEST_FLAG", default=True) is False


def test_env_choice_validates_against_allowed_values(monkeypatch):
    monkeypatch.delenv("TABDUMP_TEST_CHOICE", raising=False)
    assert cli._env_choice("TABDUMP_TEST_CHOICE", {"raw", "hybrid"}, "hybrid") == "hybrid"

    monkeypatch.setenv("TABDUMP_TEST_CHOICE", "raw")
    assert cli._env_choice("TABDUMP_TEST_CHOICE", {"raw", "hybrid"}, "hybrid") == "raw"

    monkeypatch.setenv("TABDUMP_TEST_CHOICE", "unsupported")
    assert cli._env_choice("TABDUMP_TEST_CHOICE", {"raw", "hybrid"}, "hybrid") == "hybrid"


def test_env_float_parses_and_clamps(monkeypatch):
    monkeypatch.delenv("TABDUMP_TEST_FLOAT", raising=False)
    assert cli._env_float("TABDUMP_TEST_FLOAT", 0.7, minimum=0.0, maximum=1.0) == 0.7

    monkeypatch.setenv("TABDUMP_TEST_FLOAT", "0.9")
    assert cli._env_float("TABDUMP_TEST_FLOAT", 0.7, minimum=0.0, maximum=1.0) == 0.9

    monkeypatch.setenv("TABDUMP_TEST_FLOAT", "2.0")
    assert cli._env_float("TABDUMP_TEST_FLOAT", 0.7, minimum=0.0, maximum=1.0) == 1.0

    monkeypatch.setenv("TABDUMP_TEST_FLOAT", "bad")
    assert cli._env_float("TABDUMP_TEST_FLOAT", 0.7, minimum=0.0, maximum=1.0) == 0.7


def test_find_root_prefers_nearest_candidate_with_renderer(tmp_path: Path):
    fake_cli = tmp_path / "core" / "postprocess" / "cli.py"
    fake_cli.parent.mkdir(parents=True)
    fake_cli.write_text("# stub", encoding="utf-8")

    renderer_path = tmp_path / "core" / "renderer" / "renderer.py"
    renderer_path.parent.mkdir(parents=True)
    renderer_path.write_text("# renderer", encoding="utf-8")

    assert cli._find_root(fake_cli) == tmp_path


def test_find_root_falls_back_when_no_candidate_found(tmp_path: Path):
    fake_cli = tmp_path / "a" / "b" / "cli.py"
    fake_cli.parent.mkdir(parents=True)
    fake_cli.write_text("# stub", encoding="utf-8")

    # Fallback branch returns path.parent.parent when no candidate contains core/renderer/renderer.py.
    assert cli._find_root(fake_cli) == fake_cli.parent.parent
