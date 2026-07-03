"""Tests for hunter.reporting_cli.models."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from hunter.reporting_cli import (
    CLICommandKind,
    CLICommandResult,
    CLIExitCode,
    CLIInvocation,
    CLIOutputFormat,
    CLIArtifactSummary,
    CLISafetyFlags,
    REPORTING_CLI_REASON_CODES,
    REPORTING_CLI_VERSION,
)


class TestEnums:
    def test_exit_codes(self) -> None:
        assert CLIExitCode.OK.value == 0
        assert CLIExitCode.USAGE_ERROR.value == 2
        assert CLIExitCode.VALIDATION_ERROR.value == 3
        assert CLIExitCode.UNSAFE_CONTENT.value == 4
        assert CLIExitCode.INTERNAL_ERROR.value == 5

    def test_output_formats(self) -> None:
        assert CLIOutputFormat.JSON.value == "JSON"
        assert CLIOutputFormat.MARKDOWN.value == "MARKDOWN"
        assert CLIOutputFormat.TEXT.value == "TEXT"

    def test_command_kinds(self) -> None:
        assert CLICommandKind.VERSION.value == "version"
        assert CLICommandKind.SAFETY_SUMMARY.value == "safety-summary"
        assert CLICommandKind.LIST_ARTIFACTS.value == "list-artifacts"
        assert CLICommandKind.RENDER_SAMPLE.value == "render-sample"
        assert CLICommandKind.VALIDATE_ARTIFACT_PATHS.value == "validate-artifact-paths"

    def test_version_constant(self) -> None:
        assert REPORTING_CLI_VERSION == "0.29.0-dev"

    def test_reason_codes(self) -> None:
        assert "OK" in REPORTING_CLI_REASON_CODES
        assert "UNKNOWN_COMMAND" in REPORTING_CLI_REASON_CODES
        assert "VALIDATION_ERROR" in REPORTING_CLI_REASON_CODES
        assert "INVALID_PATH" in REPORTING_CLI_REASON_CODES
        assert "PATH_TRAVERSAL_DETECTED" in REPORTING_CLI_REASON_CODES
        assert "NETWORK_REFERENCE_DETECTED" in REPORTING_CLI_REASON_CODES


class TestCLISafetyFlags:
    def test_baseline_is_safe(self) -> None:
        flags = CLISafetyFlags()
        assert flags.is_safe is True

    def test_unsafe_content_breaks_safe(self) -> None:
        flags = CLISafetyFlags(has_unsafe_content=True)
        assert flags.is_safe is False

    def test_invalid_path_breaks_safe(self) -> None:
        flags = CLISafetyFlags(has_invalid_path=True)
        assert flags.is_safe is False

    def test_no_flag_false_breaks_safe(self) -> None:
        flags = CLISafetyFlags(no_network_connection=False)
        assert flags.is_safe is False

    def test_research_only_false_breaks_safe(self) -> None:
        flags = CLISafetyFlags(research_only=False)
        assert flags.is_safe is False

    def test_not_trading_advice_false_breaks_safe(self) -> None:
        flags = CLISafetyFlags(not_trading_advice=False)
        assert flags.is_safe is False

    def test_all_required_flags_present(self) -> None:
        # Sanity check that the programmatic is_safe covers all no_/not_/has_ fields.
        fields = CLISafetyFlags.__dataclass_fields__
        assert any(name.startswith("no_") for name in fields)
        assert any(name.startswith("has_") for name in fields)
        assert "research_only" in fields
        assert "not_trading_advice" in fields


class TestCLIArtifactSummary:
    def test_defaults(self) -> None:
        summary = CLIArtifactSummary(
            engine_id="backtest",
            artifact_kind="json_report",
            default_path="data/backtest/latest_backtest_report.json",
        )
        assert summary.engine_id == "backtest"
        assert summary.artifact_kind == "json_report"
        assert summary.path_is_opaque_string is True
        assert isinstance(summary.metadata, MappingProxyType)

    def test_empty_engine_id_raises(self) -> None:
        with pytest.raises(ValueError):
            CLIArtifactSummary(engine_id="", artifact_kind="json_report", default_path="x")

    def test_empty_artifact_kind_raises(self) -> None:
        with pytest.raises(ValueError):
            CLIArtifactSummary(engine_id="backtest", artifact_kind="", default_path="x")

    def test_metadata_coerced(self) -> None:
        summary = CLIArtifactSummary(
            engine_id="backtest",
            artifact_kind="json_report",
            default_path="x",
            metadata={"note": "opaque"},
        )
        assert dict(summary.metadata) == {"note": "opaque"}


class TestCLIInvocation:
    def test_defaults(self) -> None:
        inv = CLIInvocation(command="version")
        assert inv.command == "version"
        assert inv.args == ()
        assert inv.output_dir is None
        assert inv.output_format == CLIOutputFormat.TEXT
        assert inv.dry_run is False
        assert isinstance(inv.metadata, MappingProxyType)

    def test_args_coerced_to_tuple(self) -> None:
        inv = CLIInvocation(command="validate-artifact-paths", args=["a", "b"])
        assert inv.args == ("a", "b")

    def test_empty_command_raises(self) -> None:
        with pytest.raises(ValueError):
            CLIInvocation(command="")

    def test_input_not_mutated(self) -> None:
        args = ["a", "b"]
        metadata = {"k": "v"}
        inv = CLIInvocation(command="validate-artifact-paths", args=args, metadata=metadata)
        assert args == ["a", "b"]
        assert metadata == {"k": "v"}
        assert inv.args == ("a", "b")


class TestCLICommandResult:
    def test_defaults(self) -> None:
        result = CLICommandResult(
            command="version",
            exit_code=CLIExitCode.OK,
            stdout="",
            stderr="",
        )
        assert result.command == "version"
        assert result.exit_code == CLIExitCode.OK
        assert result.output_paths == ()
        assert result.reason_codes == ()
        assert result.notes == ()
        assert isinstance(result.data, MappingProxyType)
        assert dict(result.data) == {}

    def test_sequences_coerced(self) -> None:
        result = CLICommandResult(
            command="version",
            exit_code=CLIExitCode.OK,
            stdout="",
            stderr="",
            output_paths=["a", "b"],
            reason_codes=["OK"],
            notes=["note"],
            data={"version": "0.28.0-dev"},
        )
        assert result.output_paths == ("a", "b")
        assert result.reason_codes == ("OK",)
        assert result.notes == ("note",)
        assert dict(result.data) == {"version": "0.28.0-dev"}

    def test_invalid_exit_code_raises(self) -> None:
        with pytest.raises(ValueError):
            CLICommandResult(command="version", exit_code=0, stdout="", stderr="")  # type: ignore[arg-type]

    def test_data_mapping_coerced(self) -> None:
        result = CLICommandResult(
            command="version",
            exit_code=CLIExitCode.OK,
            stdout="",
            stderr="",
            data={"version": "0.28.0-dev"},
        )
        assert isinstance(result.data, MappingProxyType)
