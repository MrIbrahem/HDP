"""
Unit tests for src/cli/__init__.py module.

Classes to test: Cli
"""

import argparse
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from src.cli import Cli
from src.config import DEFAULT_CATEGORIES

BASE_PAGE = "User:Base/page"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.base_page = BASE_PAGE
    return settings


@pytest.fixture
def cli(mock_settings: MagicMock) -> Cli:
    return Cli(settings=mock_settings)


@dataclass
class MockDeps:
    setup_logging: MagicMock
    service_class: MagicMock
    service: MagicMock


@pytest.fixture
def mock_deps(monkeypatch: pytest.MonkeyPatch) -> MockDeps:
    """Patch ``setup_logging`` and ``HdpService`` inside ``src.cli``."""
    mock_setup_logging = MagicMock()
    monkeypatch.setattr("src.cli.setup_logging", mock_setup_logging)

    mock_service = MagicMock()
    mock_service.generate.return_value = "generated text"
    mock_service.update.return_value = "updated text"

    mock_service_class = MagicMock()
    mock_service_class.load.return_value = mock_service
    monkeypatch.setattr("src.cli.HdpService", mock_service_class)

    return MockDeps(
        setup_logging=mock_setup_logging,
        service_class=mock_service_class,
        service=mock_service,
    )


def make_args(**overrides) -> argparse.Namespace:
    """Build a Namespace with the defaults of the ``generate`` command."""
    values = {
        "page": None,
        "output": "table.wiki",
        "unknown": "unknown",
        "sections": None,
        "test": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_uses_given_settings(self, mock_settings):
        assert Cli(settings=mock_settings).settings is mock_settings

    def test_loads_settings_from_env_when_none(self, monkeypatch):
        fake_settings = MagicMock()
        mock_settings_cls = MagicMock()
        mock_settings_cls.from_env.return_value = fake_settings
        monkeypatch.setattr("src.cli.Settings", mock_settings_cls)

        assert Cli().settings is fake_settings
        mock_settings_cls.from_env.assert_called_once_with()


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


class TestBuildParser:
    def test_returns_argument_parser(self, cli):
        parser = cli._build_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "hdp"

    def test_command_is_required(self, cli):
        with pytest.raises(SystemExit) as exc:
            cli._build_parser().parse_args([])
        assert exc.value.code == 2

    def test_unknown_command_rejected(self, cli):
        with pytest.raises(SystemExit) as exc:
            cli._build_parser().parse_args(["bogus"])
        assert exc.value.code == 2

    def test_log_level_default(self, cli):
        args = cli._build_parser().parse_args(["generate"])
        assert args.log_level == "INFO"

    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR"])
    def test_log_level_valid_choices(self, cli, level):
        args = cli._build_parser().parse_args(["--log-level", level, "generate"])
        assert args.log_level == level

    def test_log_level_invalid_choice(self, cli):
        with pytest.raises(SystemExit) as exc:
            cli._build_parser().parse_args(["--log-level", "TRACE", "generate"])
        assert exc.value.code == 2

    # --- generate ---

    def test_generate_defaults(self, cli):
        args = cli._build_parser().parse_args(["generate"])
        assert args.command == "generate"
        assert args.page is None
        assert args.output == "table.wiki"
        assert args.unknown == "unknown"
        assert args.sections is None
        assert args.offline is False
        assert args.no_recent is False
        assert args.last_edits is False

    def test_generate_custom_values(self, cli):
        args = cli._build_parser().parse_args(
            [
                "generate",
                "--page",
                "User:X/y",
                "--output",
                "out.wiki",
                "--unknown",
                "N/A",
                "--sections",
                "Alpha",
                "Category:Beta",
                "--offline",
                "--no-recent",
                "--last-edits",
            ]
        )
        assert args.page == "User:X/y"
        assert args.output == "out.wiki"
        assert args.unknown == "N/A"
        assert args.sections == ["Alpha", "Category:Beta"]
        assert args.offline is True
        assert args.no_recent is True
        assert args.last_edits is True

    def test_generate_help_mentions_base_page(self, cli, capsys):
        with pytest.raises(SystemExit) as exc:
            cli._build_parser().parse_args(["generate", "--help"])
        assert exc.value.code == 0
        assert BASE_PAGE in capsys.readouterr().out

    # --- update ---

    def test_update_defaults(self, cli):
        args = cli._build_parser().parse_args(["update"])
        assert args.command == "update"
        assert args.page == "User:Mr. Ibrahem/hdp"
        assert args.output == "Mr._Ibrahem_hdp.wiki"
        assert args.unknown == ""
        assert args.test is False
        assert args.sections is None

    def test_update_custom_values(self, cli):
        args = cli._build_parser().parse_args(
            [
                "update",
                "--page",
                "User:Other/page",
                "--output",
                "o.wiki",
                "--unknown",
                "?",
                "--test",
                "--sections",
                "One",
                "--offline",
            ]
        )
        assert args.page == "User:Other/page"
        assert args.output == "o.wiki"
        assert args.unknown == "?"
        assert args.test is True
        assert args.sections == ["One"]
        assert args.offline is True

    def test_sections_requires_at_least_one_value(self, cli):
        with pytest.raises(SystemExit):
            cli._build_parser().parse_args(["generate", "--sections"])


class TestAddSharedArgs:
    def test_adds_all_shared_options(self, cli):
        parser = argparse.ArgumentParser()
        cli.add_shared_args(parser)

        args = parser.parse_args([])
        assert args.sections is None
        assert args.offline is False
        assert args.no_recent is False
        assert args.last_edits is False

        args = parser.parse_args(["--sections", "A", "B", "--offline", "--no-recent", "--last-edits"])
        assert args.sections == ["A", "B"]
        assert args.offline is True
        assert args.no_recent is True
        assert args.last_edits is True


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------


class TestRun:
    def test_returns_1_when_service_not_loaded(self, cli, mock_deps):
        mock_deps.service_class.load.return_value = None

        assert cli.run(["generate"]) == 1
        mock_deps.service.generate.assert_not_called()
        mock_deps.service.update.assert_not_called()

    def test_loads_service_with_settings(self, cli, mock_settings, mock_deps):
        cli.run(["generate"])
        mock_deps.service_class.load.assert_called_once_with(settings=mock_settings)

    @pytest.mark.parametrize("level", ["DEBUG", "WARNING"])
    def test_configures_logging(self, cli, mock_deps, level):
        cli.run(["--log-level", level, "generate"])
        mock_deps.setup_logging.assert_called_once_with(level=level)

    def test_default_log_level(self, cli, mock_deps):
        cli.run(["update"])
        mock_deps.setup_logging.assert_called_once_with(level="INFO")

    def test_passes_parsed_args_to_set_args(self, cli, mock_deps):
        cli.run(["generate", "--offline", "--no-recent", "--last-edits"])

        mock_deps.service.set_args.assert_called_once()
        args = mock_deps.service.set_args.call_args.args[0]
        assert args.offline is True
        assert args.no_recent is True
        assert args.last_edits is True

    def test_dispatches_to_generate(self, cli, mock_deps):
        assert cli.run(["generate"]) == 0
        mock_deps.service.generate.assert_called_once()
        mock_deps.service.update.assert_not_called()

    def test_dispatches_to_update(self, cli, mock_deps):
        assert cli.run(["update"]) == 0
        mock_deps.service.update.assert_called_once()
        mock_deps.service.generate.assert_not_called()

    def test_propagates_command_failure(self, cli, mock_deps):
        mock_deps.service.generate.return_value = ""
        assert cli.run(["generate"]) == 1

    def test_unknown_command_prints_help_and_returns_2(self, cli, mock_deps, monkeypatch):
        fake_parser = MagicMock()
        fake_parser.parse_args.return_value = argparse.Namespace(command="other", log_level="INFO")
        monkeypatch.setattr(cli, "_build_parser", lambda: fake_parser)

        assert cli.run([]) == 2
        fake_parser.print_help.assert_called_once_with()

    def test_invalid_args_exit(self, cli, mock_deps):
        with pytest.raises(SystemExit) as exc:
            cli.run(["--log-level", "NOPE", "generate"])
        assert exc.value.code == 2
        mock_deps.service_class.load.assert_not_called()


# ---------------------------------------------------------------------------
# _cmd_generate
# ---------------------------------------------------------------------------


class TestCmdGenerate:
    def test_uses_base_page_when_page_not_given(self, cli, mock_deps):
        cli._cmd_generate(mock_deps.service, make_args())

        mock_deps.service.generate.assert_called_once_with(
            page_title=BASE_PAGE,
            section_names=list(DEFAULT_CATEGORIES),
            unknown="unknown",
        )

    def test_uses_custom_page(self, cli, mock_deps):
        cli._cmd_generate(mock_deps.service, make_args(page="User:Custom"))
        assert mock_deps.service.generate.call_args.kwargs["page_title"] == "User:Custom"

    def test_uses_custom_sections(self, cli, mock_deps):
        cli._cmd_generate(mock_deps.service, make_args(sections=["A", "Category:B"]))
        assert mock_deps.service.generate.call_args.kwargs["section_names"] == ["A", "Category:B"]

    def test_default_sections_are_a_copy(self, cli, mock_deps):
        cli._cmd_generate(mock_deps.service, make_args())
        passed = mock_deps.service.generate.call_args.kwargs["section_names"]
        assert passed == list(DEFAULT_CATEGORIES)
        assert passed is not DEFAULT_CATEGORIES

    def test_passes_unknown_placeholder(self, cli, mock_deps):
        cli._cmd_generate(mock_deps.service, make_args(unknown="--"))
        assert mock_deps.service.generate.call_args.kwargs["unknown"] == "--"

    def test_writes_output_and_returns_0(self, cli, mock_settings, mock_deps):
        result = cli._cmd_generate(mock_deps.service, make_args(output="my.wiki"))

        assert result == 0
        mock_settings.write_to_cache_dir.assert_called_once_with("my.wiki", "generated text")

    @pytest.mark.parametrize("empty", ["", None])
    def test_empty_output_returns_1_without_writing(self, cli, mock_settings, mock_deps, empty):
        mock_deps.service.generate.return_value = empty

        assert cli._cmd_generate(mock_deps.service, make_args()) == 1
        mock_settings.write_to_cache_dir.assert_not_called()


# ---------------------------------------------------------------------------
# _cmd_update
# ---------------------------------------------------------------------------


def make_update_args(**overrides) -> argparse.Namespace:
    values = {
        "page": "User:Mr. Ibrahem/hdp",
        "output": "Mr._Ibrahem_hdp.wiki",
        "unknown": "",
        "sections": None,
        "test": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class TestCmdUpdate:
    def test_default_call(self, cli, mock_deps):
        cli._cmd_update(mock_deps.service, make_update_args())

        mock_deps.service.update.assert_called_once_with(
            page_title="User:Mr. Ibrahem/hdp",
            section_names=list(DEFAULT_CATEGORIES),
            unknown="",
        )

    def test_custom_page_and_sections(self, cli, mock_deps):
        cli._cmd_update(mock_deps.service, make_update_args(page="User:Z", sections=["S1"]))

        kwargs = mock_deps.service.update.call_args.kwargs
        assert kwargs["page_title"] == "User:Z"
        assert kwargs["section_names"] == ["S1"]

    def test_passes_unknown_placeholder(self, cli, mock_deps):
        cli._cmd_update(mock_deps.service, make_update_args(unknown="n/a"))
        assert mock_deps.service.update.call_args.kwargs["unknown"] == "n/a"

    def test_writes_output_and_returns_0(self, cli, mock_settings, mock_deps):
        result = cli._cmd_update(mock_deps.service, make_update_args(output="custom.wiki"))

        assert result == 0
        mock_settings.write_to_cache_dir.assert_called_once_with("custom.wiki", "updated text")

    def test_test_mode_overrides_page_and_sections(self, cli, mock_deps):
        cli._cmd_update(
            mock_deps.service,
            make_update_args(test=True, page="User:Ignored", sections=["Ignored"]),
        )

        kwargs = mock_deps.service.update.call_args.kwargs
        assert kwargs["page_title"] == "User:Mr. Ibrahem/test"
        assert kwargs["section_names"] == []

    def test_test_mode_renames_default_output(self, cli, mock_settings, mock_deps):
        cli._cmd_update(mock_deps.service, make_update_args(test=True))
        mock_settings.write_to_cache_dir.assert_called_once_with("test.wiki", "updated text")

    def test_test_mode_keeps_custom_output(self, cli, mock_settings, mock_deps):
        cli._cmd_update(mock_deps.service, make_update_args(test=True, output="mine.wiki"))
        mock_settings.write_to_cache_dir.assert_called_once_with("mine.wiki", "updated text")

    def test_non_test_mode_keeps_default_output(self, cli, mock_settings, mock_deps):
        cli._cmd_update(mock_deps.service, make_update_args(test=False))
        mock_settings.write_to_cache_dir.assert_called_once_with("Mr._Ibrahem_hdp.wiki", "updated text")

    @pytest.mark.parametrize("empty", ["", None])
    def test_empty_output_returns_1_without_writing(self, cli, mock_settings, mock_deps, empty):
        mock_deps.service.update.return_value = empty

        assert cli._cmd_update(mock_deps.service, make_update_args()) == 1
        mock_settings.write_to_cache_dir.assert_not_called()


# ---------------------------------------------------------------------------
# End-to-end through run()
# ---------------------------------------------------------------------------


class TestRunIntegration:
    def test_generate_full_flow(self, cli, mock_settings, mock_deps):
        code = cli.run(["generate", "--page", "User:P", "--sections", "A", "--output", "x.wiki", "--unknown", "?"])

        assert code == 0
        mock_deps.service.generate.assert_called_once_with(page_title="User:P", section_names=["A"], unknown="?")
        mock_settings.write_to_cache_dir.assert_called_once_with("x.wiki", "generated text")

    def test_update_test_flag_full_flow(self, cli, mock_settings, mock_deps):
        code = cli.run(["update", "--test"])

        assert code == 0
        mock_deps.service.update.assert_called_once_with(
            page_title="User:Mr. Ibrahem/test", section_names=[], unknown=""
        )
        mock_settings.write_to_cache_dir.assert_called_once_with("test.wiki", "updated text")


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


class TestMain:
    def test_main_runs_cli_with_argv(self, monkeypatch):
        from src import cli as cli_module

        mock_cli_instance = MagicMock()
        mock_cli_instance.run.return_value = 7
        mock_cli_class = MagicMock(return_value=mock_cli_instance)
        monkeypatch.setattr(cli_module, "Cli", mock_cli_class)

        assert cli_module.main(["generate"]) == 7
        mock_cli_class.assert_called_once_with()
        mock_cli_instance.run.assert_called_once_with(["generate"])

    def test_main_without_argv(self, monkeypatch):
        from src import cli as cli_module

        mock_cli_instance = MagicMock()
        mock_cli_instance.run.return_value = 0
        monkeypatch.setattr(cli_module, "Cli", MagicMock(return_value=mock_cli_instance))

        assert cli_module.main() == 0
        mock_cli_instance.run.assert_called_once_with(None)
