"""Integration tests for hunter.reporting_cli.

MVP-29 — Local Research Reporting CLI.

These tests exercise end-to-end flows across the CLI, command, and writer
layers without monkeypatching source internals. They verify determinism,
safety boundaries, and public API behavior using only local, deterministic
fixtures and tmp_path for file writes.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import hunter
import pytest

from hunter.reporting_cli import (
    CLICommandKind,
    CLICommandResult,
    CLIExitCode,
    CLIInvocation,
    CLIOutputFormat,
    CLI_SAFETY_NOTICE,
    dispatch_command,
    main,
    run_list_artifacts_command,
    run_render_sample_command,
    run_safety_summary_command,
    run_validate_artifact_paths_command,
    run_version_command,
)


class TestEndToEndCommandDispatch:
    """Dispatch flow: CLIInvocation -> dispatch_command -> command core."""

    def test_version_dispatch(self) -> None:
        inv = CLIInvocation(command=CLICommandKind.VERSION.value)
        result = dispatch_command(inv)
        assert isinstance(result, CLICommandResult)
        assert result.exit_code == CLIExitCode.OK
        assert result.command == "version"
        assert "hunter-futures-pro" in result.stdout
        assert result.data["version"] == hunter.__version__

    def test_safety_summary_dispatch(self) -> None:
        inv = CLIInvocation(command=CLICommandKind.SAFETY_SUMMARY.value)
        result = dispatch_command(inv)
        assert result.exit_code == CLIExitCode.OK
        assert CLI_SAFETY_NOTICE in result.stdout
        assert result.safety_flags.is_safe is True
        assert "RESEARCH_ONLY" in result.reason_codes
        assert "NOT_TRADING_ADVICE" in result.reason_codes

    def test_list_artifacts_dispatch(self) -> None:
        inv = CLIInvocation(command=CLICommandKind.LIST_ARTIFACTS.value)
        result = dispatch_command(inv)
        assert result.exit_code == CLIExitCode.OK
        engine_ids = [a["engine_id"] for a in result.data["artifacts"]]
        assert set(engine_ids) == {
            "relative_strength",
            "open_interest",
            "discovery",
            "portfolio_construction",
            "backtest",
            "reporting_cli",
        }

    def test_validate_artifact_paths_dispatch(self) -> None:
        inv = CLIInvocation(
            command=CLICommandKind.VALIDATE_ARTIFACT_PATHS.value,
            args=["data/report.json", "reports/summary.md"],
        )
        result = dispatch_command(inv)
        assert result.exit_code == CLIExitCode.OK
        assert result.data["valid"] is True
        assert result.data["paths"] == ("data/report.json", "reports/summary.md")

    def test_render_sample_dispatch_writes_under_output_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        inv = CLIInvocation(command=CLICommandKind.RENDER_SAMPLE.value, output_dir="out")
        result = dispatch_command(inv)
        assert result.exit_code == CLIExitCode.OK
        assert (tmp_path / "out" / "backtest" / "backtest_report.json").exists()
        assert (tmp_path / "out" / "reporting_cli" / "cli_summary.md").exists()
        for p in result.output_paths:
            assert Path(p).is_relative_to("out")


class TestEndToEndMain:
    """Full CLI main flow: argv -> main -> stdout/stderr -> exit code."""

    def test_main_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["version"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.OK.value
        assert captured.out.startswith("hunter-futures-pro")
        assert captured.err == ""

    def test_main_safety_summary(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["safety-summary"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.OK.value
        assert CLI_SAFETY_NOTICE in captured.out
        assert "research_only: True" in captured.out
        assert captured.err == ""

    def test_main_list_artifacts(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["list-artifacts"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.OK.value
        for engine in ("backtest", "discovery", "portfolio_construction", "relative_strength", "open_interest", "reporting_cli"):
            assert engine in captured.out
        assert captured.err == ""


class TestValidateArtifactPathsIntegration:
    """Path validation as seen through the full CLI surface."""

    def test_main_accepts_safe_relative_paths(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["validate-artifact-paths", "data/report.json"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.OK.value
        assert "safe" in captured.out.lower()
        assert captured.err == ""

    def test_main_rejects_parent_traversal(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["validate-artifact-paths", "../etc/passwd"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.VALIDATION_ERROR.value
        assert "UNSAFE" in captured.err
        assert "PATH_TRAVERSAL_DETECTED" in captured.err
        assert "Traceback" not in captured.err

    def test_main_rejects_network_prefix(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = main(["validate-artifact-paths", "http://example.com/data.json"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.VALIDATION_ERROR.value
        assert "NETWORK_REFERENCE_DETECTED" in captured.err
        assert "Traceback" not in captured.err

    def test_main_rejects_absolute_path_outside_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        target = outside / "file.json"
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)
        code = main(["validate-artifact-paths", str(target)])
        captured = capsys.readouterr()
        assert code == CLIExitCode.VALIDATION_ERROR.value
        assert "INVALID_PATH" in captured.err
        assert "Traceback" not in captured.err


class TestRenderSampleIntegration:
    """render-sample end-to-end file output verification."""

    def test_creates_expected_layout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        code = main(["render-sample", "--output-dir", "out"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.OK.value

        expected = [
            tmp_path / "out" / "backtest" / "backtest_report.json",
            tmp_path / "out" / "backtest" / "backtest_report.csv",
            tmp_path / "out" / "backtest" / "backtest_report.md",
            tmp_path / "out" / "portfolio_construction" / "portfolio_construction_report.json",
            tmp_path / "out" / "portfolio_construction" / "portfolio_construction_report.csv",
            tmp_path / "out" / "portfolio_construction" / "portfolio_construction_report.md",
            tmp_path / "out" / "discovery" / "discovery_report.json",
            tmp_path / "out" / "discovery" / "discovery_report.csv",
            tmp_path / "out" / "discovery" / "discovery_report.md",
            tmp_path / "out" / "reporting_cli" / "cli_summary.json",
            tmp_path / "out" / "reporting_cli" / "cli_summary.md",
        ]
        for path in expected:
            assert path.exists(), f"expected artifact missing: {path}"
        assert CLI_SAFETY_NOTICE in captured.out

    def test_json_csv_markdown_are_well_formed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        main(["render-sample", "--output-dir", "out"])

        backtest_json = tmp_path / "out" / "backtest" / "backtest_report.json"
        data = json.loads(backtest_json.read_text(encoding="utf-8"))
        assert "report_id" in data

        backtest_csv = tmp_path / "out" / "backtest" / "backtest_report.csv"
        csv_text = backtest_csv.read_text(encoding="utf-8")
        rows = list(csv.reader(csv_text.splitlines()))
        assert len(rows) >= 2

        summary_md = tmp_path / "out" / "reporting_cli" / "cli_summary.md"
        md_text = summary_md.read_text(encoding="utf-8")
        assert md_text.startswith("#")
        assert CLI_SAFETY_NOTICE in md_text

    def test_writes_only_under_output_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        main(["render-sample", "--output-dir", "out"])
        # No writes to the default data/ directory, which would be outside tmp_path.
        assert not (tmp_path / "data" / "reporting_cli" / "samples").exists()

    def test_dry_run_returns_ok_without_writing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        code = main(["render-sample", "--output-dir", "out", "--dry-run"])
        captured = capsys.readouterr()
        assert code == CLIExitCode.OK.value
        assert not (tmp_path / "out").exists()
        assert "Dry-run" in captured.out


class TestDeterminism:
    """Identical inputs produce identical outputs across separate runs."""

    def test_render_sample_outputs_identical_in_separate_dirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        main(["render-sample", "--output-dir", "a"])
        main(["render-sample", "--output-dir", "b"])

        a_json = json.loads((tmp_path / "a" / "backtest" / "backtest_report.json").read_text())
        b_json = json.loads((tmp_path / "b" / "backtest" / "backtest_report.json").read_text())
        assert a_json == b_json

        a_md = (tmp_path / "a" / "reporting_cli" / "cli_summary.md").read_text()
        b_md = (tmp_path / "b" / "reporting_cli" / "cli_summary.md").read_text()
        assert a_md == b_md

    def test_list_artifacts_output_is_stable(self, capsys: pytest.CaptureFixture[str]) -> None:
        code1 = main(["list-artifacts"])
        captured1 = capsys.readouterr()
        code2 = main(["list-artifacts"])
        captured2 = capsys.readouterr()
        assert code1 == code2 == CLIExitCode.OK.value
        assert captured1.out == captured2.out


class TestSafetyBoundaries:
    """CLI outputs are research-only and contain no actionable instructions."""

    def test_research_only_language_present(self, capsys: pytest.CaptureFixture[str]) -> None:
        # Commands whose stdout surface renders the safety notice through main().
        commands_with_notice: tuple[tuple[str, list[str]], ...] = (
            ("safety-summary", []),
            ("list-artifacts", []),
            ("render-sample", ["--output-dir", "out", "--dry-run"]),
        )
        for command, args in commands_with_notice:
            main([command, *args])
            captured = capsys.readouterr()
            assert CLI_SAFETY_NOTICE in captured.out or CLI_SAFETY_NOTICE in captured.err

        # Help text also carries the safety notice.
        main(["--help"])
        captured = capsys.readouterr()
        assert CLI_SAFETY_NOTICE in captured.out

    def test_no_action_commands_in_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        # Standalone action verbs that should not appear outside the safety notice.
        # The safety notice itself uses negative phrasing ("does not place orders");
        # this test guards against positive actionable instructions leaking in.
        action_words = ("buy", "sell", "hold", "rebalance", "submit", "enter", "exit")
        for command in ("version", "safety-summary", "list-artifacts", "validate-artifact-paths", "render-sample"):
            if command == "render-sample":
                main([command, "--output-dir", "out", "--dry-run"])
            elif command == "validate-artifact-paths":
                main([command, "data/report.json"])
            else:
                main([command])
            captured = capsys.readouterr()
            combined = (captured.out + captured.err).lower()
            for word in action_words:
                assert word not in combined, f"unexpected action word '{word}' in {command} output"


class TestPublicApiAndInputSafety:
    """Public API surface and input immutability."""

    def test_all_expected_public_exports_are_callable(self) -> None:
        assert callable(main)
        assert callable(dispatch_command)
        assert callable(run_version_command)
        assert callable(run_safety_summary_command)
        assert callable(run_list_artifacts_command)
        assert callable(run_validate_artifact_paths_command)
        assert callable(run_render_sample_command)

    def test_public_models_and_enums(self) -> None:
        assert CLIExitCode.OK.value == 0
        assert CLIOutputFormat.TEXT.value == "TEXT"
        assert CLICommandKind.VERSION.value == "version"

    def test_argv_input_not_mutated(self) -> None:
        argv = ["validate-artifact-paths", "data/report.json"]
        original = argv.copy()
        main(argv)
        assert argv == original
