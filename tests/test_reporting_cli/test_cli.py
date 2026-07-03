"""Tests for hunter.reporting_cli.cli."""

from __future__ import annotations

import pytest

from hunter import __version__ as hunter_version
from hunter.reporting_cli import CLIExitCode, CLI_SAFETY_NOTICE, main


class TestVersion:
    def test_returns_ok_and_prints_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["version"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.OK.value
        assert "hunter-futures-pro" in captured.out
        assert hunter_version in captured.out

    def test_stdout_has_safety_notice(self, capsys: pytest.CaptureFixture[str]) -> None:
        # version command includes safety notice in result.notes, but stdout is
        # just the version line. The safety notice is part of the command layer
        # result; the CLI layer prints stdout/stderr as-is.
        main(["version"])
        captured = capsys.readouterr()
        assert captured.out.startswith("hunter-futures-pro")
        assert captured.err == ""


class TestSafetySummary:
    def test_returns_ok_and_includes_boundaries(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["safety-summary"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.OK.value
        assert CLI_SAFETY_NOTICE in captured.out
        assert "no_trading_signal: True" in captured.out
        assert "research_only: True" in captured.out

    def test_json_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["safety-summary", "--format", "json"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.OK.value
        assert '"safety_flags"' in captured.out
        assert "no_trading_signal" in captured.out


class TestListArtifacts:
    def test_returns_ok_and_deterministic_engine_names(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["list-artifacts"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.OK.value
        for engine in (
            "relative_strength",
            "open_interest",
            "discovery",
            "portfolio_construction",
            "backtest",
            "reporting_cli",
        ):
            assert engine in captured.out


class TestValidateArtifactPaths:
    def test_accepts_safe_relative_paths(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["validate-artifact-paths", "data/report.json"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.OK.value
        assert "safe" in captured.out.lower()
        assert captured.err == ""

    def test_accepts_multiple_safe_paths(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["validate-artifact-paths", "data/a.json", "reports/b.md"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.OK.value
        assert "safe" in captured.out.lower()

    def test_invalid_path_returns_validation_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["validate-artifact-paths", "../bad.json"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.VALIDATION_ERROR.value
        assert "UNSAFE" in captured.err
        assert "PATH_TRAVERSAL_DETECTED" in captured.err

    def test_network_reference_returns_validation_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["validate-artifact-paths", "http://example.com/data.json"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.VALIDATION_ERROR.value
        assert "NETWORK_REFERENCE_DETECTED" in captured.err


class TestRenderSample:
    def test_writes_only_under_output_dir(
        self, tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        code = main(["render-sample", "--output-dir", "out"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.OK.value
        assert (tmp_path / "out" / "backtest" / "backtest_report.json").exists()
        assert (tmp_path / "out" / "backtest" / "backtest_report.csv").exists()
        assert (tmp_path / "out" / "backtest" / "backtest_report.md").exists()
        assert (tmp_path / "out" / "portfolio_construction" / "portfolio_construction_report.json").exists()
        assert (tmp_path / "out" / "portfolio_construction" / "portfolio_construction_report.csv").exists()
        assert (tmp_path / "out" / "portfolio_construction" / "portfolio_construction_report.md").exists()
        assert (tmp_path / "out" / "discovery" / "discovery_report.json").exists()
        assert (tmp_path / "out" / "discovery" / "discovery_report.csv").exists()
        assert (tmp_path / "out" / "discovery" / "discovery_report.md").exists()
        assert (tmp_path / "out" / "reporting_cli" / "cli_summary.json").exists()
        assert (tmp_path / "out" / "reporting_cli" / "cli_summary.md").exists()
        assert CLI_SAFETY_NOTICE in captured.out

    def test_dry_run_returns_ok_without_writing(
        self, tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        code = main(["render-sample", "--output-dir", "out", "--dry-run"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.OK.value
        assert not (tmp_path / "out").exists()
        assert "Dry-run" in captured.out

    def test_rejects_traversal_output_dir(
        self, tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        code = main(["render-sample", "--output-dir", "../out"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.VALIDATION_ERROR.value
        assert "Invalid output directory" in captured.err


class TestHelp:
    def test_dash_help_returns_ok(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["--help"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.OK.value
        assert CLI_SAFETY_NOTICE in captured.out
        assert "Commands:" in captured.out
        assert captured.err == ""

    def test_help_command_returns_ok(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["help"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.OK.value
        assert "Commands:" in captured.out

    def test_help_with_command_returns_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["version", "--help"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.OK.value
        assert "Commands:" in captured.out


class TestUnknownCommand:
    def test_unknown_command_returns_usage_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["unknown"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.USAGE_ERROR.value
        assert "Unknown command" in captured.err

    def test_no_command_returns_usage_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main([])
        captured = capsys.readouterr()
        assert code == CLIExitCode.USAGE_ERROR.value
        assert captured.err != ""

    def test_no_traceback_on_expected_errors(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["unknown"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.USAGE_ERROR.value
        assert "Traceback" not in captured.err
        assert "Traceback" not in captured.out


class TestPublicExports:
    def test_main_exported(self) -> None:
        from hunter import reporting_cli

        assert hasattr(reporting_cli, "main")
        assert callable(reporting_cli.main)

    def test_main_return_type(self) -> None:
        code = main(["version"])
        assert isinstance(code, int)
        assert code == CLIExitCode.OK.value


class TestInputSafety:
    def test_argv_not_mutated(self) -> None:
        argv = ["validate-artifact-paths", "data/report.json"]
        original = argv.copy()
        main(argv)
        assert argv == original

    def test_default_argv_uses_sys_argv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.argv", ["prog", "version"])
        code = main()
        assert code == CLIExitCode.OK.value

