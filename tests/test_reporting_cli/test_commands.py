"""Tests for hunter.reporting_cli.commands."""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
from types import MappingProxyType

import hunter
import pytest

from hunter.reporting_cli import (
    CLICommandKind,
    CLICommandResult,
    CLIExitCode,
    CLIInvocation,
    CLIOutputFormat,
    CLI_SAFETY_NOTICE,
    build_baseline_safety_flags,
    dispatch_command,
    run_list_artifacts_command,
    run_render_sample_command,
    run_safety_summary_command,
    run_validate_artifact_paths_command,
    run_version_command,
)
from hunter.reporting_cli.models import CLIArtifactSummary, CLISafetyFlags


class TestVersionCommand:
    def test_returns_project_version(self) -> None:
        inv = CLIInvocation(command="version")
        result = run_version_command(inv)
        assert result.exit_code == CLIExitCode.OK
        assert "0.28.0" in result.stdout

    def test_result_has_data(self) -> None:
        inv = CLIInvocation(command="version")
        result = run_version_command(inv)
        assert result.data["version"] == hunter.__version__

    def test_deterministic_across_runs(self) -> None:
        r1 = run_version_command(CLIInvocation(command="version"))
        r2 = run_version_command(CLIInvocation(command="version"))
        assert r1 == r2

    def test_no_file_access(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def make_fail(name: str):
            def fail(*args, **kwargs):
                frame = inspect.currentframe()
                if frame is not None:
                    frame = frame.f_back
                while frame is not None:
                    module_name = frame.f_globals.get("__name__", "")
                    if module_name == "hunter.reporting_cli.commands":
                        raise AssertionError(
                            f"{name} must not be called from reporting_cli.commands"
                        )
                    frame = frame.f_back

            return fail

        monkeypatch.setattr(os.path, "exists", make_fail("os.path.exists"))
        monkeypatch.setattr(os.path, "islink", make_fail("os.path.islink"))
        monkeypatch.setattr(os.path, "realpath", make_fail("os.path.realpath"))
        monkeypatch.setattr(os.path, "getsize", make_fail("os.path.getsize"))
        monkeypatch.setattr(os, "stat", make_fail("os.stat"))

        result = run_version_command(CLIInvocation(command="version"))
        assert result.exit_code == CLIExitCode.OK


class TestSafetySummaryCommand:
    def test_text_format(self) -> None:
        inv = CLIInvocation(command="safety-summary", output_format=CLIOutputFormat.TEXT)
        result = run_safety_summary_command(inv)
        assert result.exit_code == CLIExitCode.OK
        assert CLI_SAFETY_NOTICE in result.stdout
        assert "no_trading_signal: True" in result.stdout
        assert result.safety_flags.is_safe is True

    def test_json_format(self) -> None:
        inv = CLIInvocation(command="safety-summary", output_format=CLIOutputFormat.JSON)
        result = run_safety_summary_command(inv)
        assert result.exit_code == CLIExitCode.OK
        parsed = json.loads(result.stdout)
        assert parsed["safety_flags"]["no_trading_signal"] is True
        assert parsed["safety_flags"]["research_only"] is True

    def test_markdown_format(self) -> None:
        inv = CLIInvocation(command="safety-summary", output_format=CLIOutputFormat.MARKDOWN)
        result = run_safety_summary_command(inv)
        assert result.exit_code == CLIExitCode.OK
        assert result.stdout.startswith("# Reporting CLI Safety Summary")
        assert CLI_SAFETY_NOTICE in result.stdout

    def test_deterministic_across_runs(self) -> None:
        r1 = run_safety_summary_command(CLIInvocation(command="safety-summary"))
        r2 = run_safety_summary_command(CLIInvocation(command="safety-summary"))
        assert r1 == r2


class TestListArtifactsCommand:
    def test_returns_all_engines(self) -> None:
        inv = CLIInvocation(command="list-artifacts")
        result = run_list_artifacts_command(inv)
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

    def test_artifact_paths_are_strings(self) -> None:
        inv = CLIInvocation(command="list-artifacts")
        result = run_list_artifacts_command(inv)
        for artifact in result.data["artifacts"]:
            assert isinstance(artifact["default_path"], str)

    def test_no_files_opened(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def make_fail(name: str):
            def fail(*args, **kwargs):
                frame = inspect.currentframe()
                if frame is not None:
                    frame = frame.f_back
                while frame is not None:
                    module_name = frame.f_globals.get("__name__", "")
                    if module_name == "hunter.reporting_cli.commands":
                        raise AssertionError(
                            f"{name} must not be called from reporting_cli.commands"
                        )
                    frame = frame.f_back

            return fail

        monkeypatch.setattr(os.path, "exists", make_fail("os.path.exists"))
        monkeypatch.setattr(os.path, "islink", make_fail("os.path.islink"))
        monkeypatch.setattr(os.path, "realpath", make_fail("os.path.realpath"))
        monkeypatch.setattr(os.path, "getsize", make_fail("os.path.getsize"))
        monkeypatch.setattr(os, "stat", make_fail("os.stat"))

        inv = CLIInvocation(command="list-artifacts")
        result = run_list_artifacts_command(inv)
        assert result.exit_code == CLIExitCode.OK

    def test_paths_are_local_opaque_strings(self) -> None:
        inv = CLIInvocation(command="list-artifacts")
        result = run_list_artifacts_command(inv)
        for artifact in result.data["artifacts"]:
            path = artifact["default_path"]
            assert "http" not in path
            assert "://" not in path


class TestValidateArtifactPathsCommand:
    def test_accepts_safe_relative_paths(self) -> None:
        inv = CLIInvocation(command="validate-artifact-paths", args=["data/report.json"])
        result = run_validate_artifact_paths_command(inv)
        assert result.exit_code == CLIExitCode.OK
        assert result.data["valid"] is True
        assert result.data["paths"] == ("data/report.json",)

    def test_accepts_multiple_safe_paths(self) -> None:
        inv = CLIInvocation(command="validate-artifact-paths", args=["data/a.json", "reports/b.md"])
        result = run_validate_artifact_paths_command(inv)
        assert result.exit_code == CLIExitCode.OK
        assert result.data["valid"] is True
        assert result.data["paths"] == ("data/a.json", "reports/b.md")

    def test_rejects_empty_paths(self) -> None:
        inv = CLIInvocation(command="validate-artifact-paths", args=[""])
        result = run_validate_artifact_paths_command(inv)
        assert result.exit_code == CLIExitCode.VALIDATION_ERROR
        assert result.data["valid"] is False
        assert len(result.data["failures"]) == 1

    def test_rejects_parent_traversal(self) -> None:
        inv = CLIInvocation(command="validate-artifact-paths", args=["../etc/passwd"])
        result = run_validate_artifact_paths_command(inv)
        assert result.exit_code == CLIExitCode.VALIDATION_ERROR
        assert result.safety_flags.has_traversal_attempt is True

    def test_rejects_network_prefix(self) -> None:
        inv = CLIInvocation(command="validate-artifact-paths", args=["http://example.com/data.json"])
        result = run_validate_artifact_paths_command(inv)
        assert result.exit_code == CLIExitCode.VALIDATION_ERROR
        assert result.safety_flags.has_network_reference is True

    def test_rejects_https_prefix(self) -> None:
        inv = CLIInvocation(command="validate-artifact-paths", args=["https://example.com/data.json"])
        result = run_validate_artifact_paths_command(inv)
        assert result.exit_code == CLIExitCode.VALIDATION_ERROR

    def test_rejects_absolute_outside_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        target = outside / "file.json"
        cwd = tmp_path / "cwd"
        cwd.mkdir(exist_ok=True)
        monkeypatch.chdir(cwd)
        inv = CLIInvocation(command="validate-artifact-paths", args=[str(target)])
        result = run_validate_artifact_paths_command(inv)
        assert result.exit_code == CLIExitCode.VALIDATION_ERROR
        assert result.safety_flags.has_invalid_path is True

    def test_accepts_absolute_inside_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        inside = tmp_path / "data"
        inside.mkdir()
        target = inside / "file.json"
        monkeypatch.chdir(tmp_path)
        inv = CLIInvocation(command="validate-artifact-paths", args=[str(target)])
        result = run_validate_artifact_paths_command(inv)
        assert result.exit_code == CLIExitCode.OK

    def test_partial_invalid_returns_validation_error(self) -> None:
        inv = CLIInvocation(command="validate-artifact-paths", args=["data/report.json", "../bad.json"])
        result = run_validate_artifact_paths_command(inv)
        assert result.exit_code == CLIExitCode.VALIDATION_ERROR
        assert result.data["valid"] is False
        assert len(result.data["failures"]) == 1

    def test_no_files_opened(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def make_fail(name: str):
            def fail(*args, **kwargs):
                frame = inspect.currentframe()
                if frame is not None:
                    frame = frame.f_back
                while frame is not None:
                    module_name = frame.f_globals.get("__name__", "")
                    if module_name == "hunter.reporting_cli.commands":
                        raise AssertionError(
                            f"{name} must not be called from reporting_cli.commands"
                        )
                    frame = frame.f_back

            return fail

        monkeypatch.setattr(os.path, "exists", make_fail("os.path.exists"))
        monkeypatch.setattr(os.path, "islink", make_fail("os.path.islink"))
        monkeypatch.setattr(os.path, "realpath", make_fail("os.path.realpath"))
        monkeypatch.setattr(os.path, "getsize", make_fail("os.path.getsize"))
        monkeypatch.setattr(os, "stat", make_fail("os.stat"))

        inv = CLIInvocation(command="validate-artifact-paths", args=["data/report.json"])
        result = run_validate_artifact_paths_command(inv)
        assert result.exit_code == CLIExitCode.OK

    def test_input_args_not_mutated(self) -> None:
        args = ["data/report.json"]
        inv = CLIInvocation(command="validate-artifact-paths", args=args)
        run_validate_artifact_paths_command(inv)
        assert args == ["data/report.json"]


class TestRenderSampleCommand:
    def _chdir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

    def test_writes_expected_artifacts(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._chdir(tmp_path, monkeypatch)
        inv = CLIInvocation(command="render-sample", output_dir="out")
        result = run_render_sample_command(inv)
        assert result.exit_code == CLIExitCode.OK
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

    def test_dry_run_returns_paths_without_writing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._chdir(tmp_path, monkeypatch)
        inv = CLIInvocation(command="render-sample", output_dir="out", dry_run=True)
        result = run_render_sample_command(inv)
        assert result.exit_code == CLIExitCode.OK
        assert result.data["dry_run"] is True
        assert (tmp_path / "out" / "backtest" / "backtest_report.json").exists() is False
        assert len(result.output_paths) == 11

    def test_output_paths_under_output_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._chdir(tmp_path, monkeypatch)
        inv = CLIInvocation(command="render-sample", output_dir="out")
        result = run_render_sample_command(inv)
        for p in result.output_paths:
            assert Path(p).is_relative_to("out")

    def test_outputs_labeled_research_only(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._chdir(tmp_path, monkeypatch)
        inv = CLIInvocation(command="render-sample", output_dir="out")
        result = run_render_sample_command(inv)
        assert CLI_SAFETY_NOTICE in result.stdout

    def test_no_writes_outside_output_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._chdir(tmp_path, monkeypatch)
        inv = CLIInvocation(command="render-sample", output_dir="out")
        run_render_sample_command(inv)
        assert not (tmp_path / "data" / "reporting_cli" / "samples").exists()

    def test_rejects_invalid_output_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._chdir(tmp_path, monkeypatch)
        inv = CLIInvocation(command="render-sample", output_dir="http://example.com/out")
        result = run_render_sample_command(inv)
        assert result.exit_code == CLIExitCode.VALIDATION_ERROR
        assert result.safety_flags.has_network_reference is True

    def test_rejects_traversal_output_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._chdir(tmp_path, monkeypatch)
        inv = CLIInvocation(command="render-sample", output_dir="../out")
        result = run_render_sample_command(inv)
        assert result.exit_code == CLIExitCode.VALIDATION_ERROR
        assert result.safety_flags.has_traversal_attempt is True

    def test_deterministic_across_runs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._chdir(tmp_path, monkeypatch)
        inv1 = CLIInvocation(command="render-sample", output_dir="a")
        inv2 = CLIInvocation(command="render-sample", output_dir="b")
        r1 = run_render_sample_command(inv1)
        r2 = run_render_sample_command(inv2)
        assert r1.data["reports"] == r2.data["reports"]
        assert r1.exit_code == r2.exit_code


class TestDispatchCommand:
    def test_unknown_command(self) -> None:
        inv = CLIInvocation(command="unknown")
        result = dispatch_command(inv)
        assert result.exit_code == CLIExitCode.USAGE_ERROR
        assert "unknown command" in result.stderr.lower()

    def test_dispatches_version(self) -> None:
        inv = CLIInvocation(command="version")
        result = dispatch_command(inv)
        assert result.exit_code == CLIExitCode.OK
        assert "0.28.0" in result.stdout

    def test_dispatches_safety_summary(self) -> None:
        inv = CLIInvocation(command="safety-summary")
        result = dispatch_command(inv)
        assert result.exit_code == CLIExitCode.OK
        assert CLI_SAFETY_NOTICE in result.stdout

    def test_invocation_args_not_mutated(self) -> None:
        args = ["data/a.json"]
        inv = CLIInvocation(command="validate-artifact-paths", args=args)
        dispatch_command(inv)
        assert args == ["data/a.json"]


class TestPublicExports:
    def test_all_expected_exports(self) -> None:
        from hunter import reporting_cli

        assert hasattr(reporting_cli, "CLICommandResult")
        assert hasattr(reporting_cli, "CLIExitCode")
        assert hasattr(reporting_cli, "CLIOutputFormat")
        assert hasattr(reporting_cli, "CLICommandKind")
        assert hasattr(reporting_cli, "CLIInvocation")
        assert hasattr(reporting_cli, "CLIArtifactSummary")
        assert hasattr(reporting_cli, "CLISafetyFlags")
        assert hasattr(reporting_cli, "run_version_command")
        assert hasattr(reporting_cli, "run_safety_summary_command")
        assert hasattr(reporting_cli, "run_list_artifacts_command")
        assert hasattr(reporting_cli, "run_validate_artifact_paths_command")
        assert hasattr(reporting_cli, "run_render_sample_command")
        assert hasattr(reporting_cli, "dispatch_command")
        assert hasattr(reporting_cli, "REPORTING_CLI_VERSION")
        assert hasattr(reporting_cli, "REPORTING_CLI_REASON_CODES")

    def test_version_constant(self) -> None:
        from hunter.reporting_cli import REPORTING_CLI_VERSION

        assert REPORTING_CLI_VERSION == "0.29.0-dev"
