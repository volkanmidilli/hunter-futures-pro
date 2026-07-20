"""Real Freqtrade compatibility smoke-test harness (SPEC-072)."""

from __future__ import annotations

import datetime
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from hunter.research_backtest_comparison.command_builder import (
    build_backtest_command,
    command_fingerprint,
)
from hunter.research_backtest_comparison.compatibility_validator import (
    validate_external_resources as _validate_external_resources,
)
from hunter.research_backtest_comparison.config_builder import (
    build_freqtrade_config,
    write_freqtrade_config,
)
from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonParserError,
    ResearchBacktestComparisonRunnerError,
    ResearchBacktestComparisonValidationError,
)
from hunter.research_backtest_comparison.executable import (
    validate_executable,
    verify_executable_supports_backtesting,
)
from hunter.research_backtest_comparison.export_parser import parse_real_export
from hunter.research_backtest_comparison.fingerprint import (
    config_fingerprint,
    data_fingerprint,
    metrics_fingerprint,
    strategy_fingerprint,
)
from hunter.research_backtest_comparison.models import (
    COMPATIBILITY_EXECUTED_FAIL,
    COMPATIBILITY_EXECUTED_PASS,
    COMPATIBILITY_INVALID_EXTERNAL_FIXTURE,
    COMPATIBILITY_NOT_EXECUTED,
    COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
    COMPATIBILITY_UNSUPPORTED_VERSION,
    REAL_FREQTRADE_COMPATIBILITY_NOT_EXECUTED,
    UNAVAILABLE,
    BacktestArmInput,
    BacktestArmLabel,
    BacktestComparisonConfig,
    BacktestMetrics,
    BacktestRunResult,
    CompatibilityStatus,
    FreqtradeCompatibilityInput,
    FreqtradeCompatibilityManifest,
    FreqtradeCompatibilityReport,
    FreqtradeCompatibilityResult,
    FreqtradeExecutableInfo,
    ResearchBacktestSafetyFlags,
    RESEARCH_BACKTEST_COMPARISON_VERSION,
    SPEC_VERSION,
)
from hunter.research_backtest_comparison.redaction import redact_text
from hunter.research_backtest_comparison.result_locator import locate_latest_backtest_result
from hunter.research_backtest_comparison.runner import run_backtest_arm
from hunter.research_backtest_comparison.validator import validate_strategy_class_name
from hunter.research_backtest_comparison.workspace import BacktestWorkspace


# Maximum bytes captured from stdout/stderr for reports.
# Sentinel command fingerprint when no command is built.
_NO_COMMAND_FINGERPRINT = "no-command-executed"
_MAX_CAPTURE_BYTES = 32_768


def _run_freqtrade_version(
    executable_path: Path,
    timeout_seconds: int = 30,
) -> tuple[bool, str, FreqtradeExecutableInfo]:
    """Run ``freqtrade --version`` and return support status."""
    info = validate_executable(executable_path, timeout_seconds=timeout_seconds)
    if not info.is_valid:
        return False, "executable did not report a valid version", info

    try:
        verify_executable_supports_backtesting(info)
    except Exception as exc:
        return False, str(exc), info

    return True, "", info


def _bounded_text(value: str | None, max_bytes: int = _MAX_CAPTURE_BYTES) -> str:
    """Truncate text to a bounded byte count and redact secrets."""
    if value is None:
        return ""
    text = redact_text(value)
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return truncated + "\n[TRUNCATED]"


def _write_hunter_metadata(
    workspace: BacktestWorkspace,
    input: FreqtradeCompatibilityInput,
) -> Path:
    """Write Hunter research metadata outside the Freqtrade config."""
    metadata = {
        "research_only": True,
        "execution_approval_granted": False,
        "production_approval_granted": False,
        "live_trading_allowed": False,
        "automatic_execution_allowed": False,
        "human_approval_required": True,
        "input_fingerprint": input.fingerprint(),
        "version": RESEARCH_BACKTEST_COMPARISON_VERSION,
        "spec_version": SPEC_VERSION,
    }
    path = workspace.evidence_path / "hunter_metadata.json"
    path.write_text(json.dumps(metadata, sort_keys=True, indent=2), encoding="utf-8")
    return path


def _build_backtest_comparison_config(
    input: FreqtradeCompatibilityInput,
    strategy_path: Path,
    data_path: Path | None = None,
) -> BacktestComparisonConfig:
    # data_path overrides input.data_path when given — points Freqtrade at the
    # isolated, workspace-materialized copy of manifest-validated fixture
    # files rather than the raw caller-controlled directory.
    """Build a BacktestComparisonConfig from compatibility input."""
    return BacktestComparisonConfig(
        strategy_name=input.strategy_name,
        strategy_path=strategy_path,
        data_path=data_path if data_path is not None else input.data_path,
        timeframe=input.timeframe,
        timerange=input.timerange,
        balance=Decimal(input.starting_balance) if input.starting_balance is not None else Decimal("1000"),
        stake=Decimal(input.stake) if input.stake is not None else Decimal("100"),
        max_open_trades=input.max_open_trades or 1,
        fee=Decimal(input.fee) if input.fee is not None else Decimal("0.001"),
        protections=tuple(input.protections) if input.protections else (),
        executable_path=input.executable_path,
        exchange_identifier=input.exchange_identifier,
        trading_mode=input.trading_mode,
    )


def _report_fingerprint(
    input: FreqtradeCompatibilityInput,
    result: FreqtradeCompatibilityResult,
) -> str:
    """Return a deterministic fingerprint of the report."""
    payload = {
        "input_fingerprint": input.fingerprint(),
        "status": result.status.value,
        "command_fingerprint": result.command_fingerprint,
        "strategy_fingerprint": result.strategy_fingerprint,
        "data_fingerprint": result.data_fingerprint,
        "export_schema": result.export_schema,
        "raw_export_fingerprint": result.raw_export_fingerprint,
        "reason_codes": result.reason_codes,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_freqtrade_compatibility_smoke_test(
    input: FreqtradeCompatibilityInput,
    *,
    retain_workspace_on_failure: bool = False,
    fixture_manifest: Any | None = None,
) -> FreqtradeCompatibilityReport:
    """Run a single-arm real Freqtrade compatibility smoke test.

    The test is skipped with status ``NOT_EXECUTED`` if any external resource is
    missing. Only the allowed ``freqtrade backtesting`` subcommand is invoked. All
    safety invariants are enforced and recorded in the metadata evidence file.

    When *fixture_manifest* (an ``ExternalFixtureManifest``) is given, only its
    declared, hash-validated files are copied into an isolated workspace
    directory and Freqtrade is pointed at that materialized copy — never at
    ``input.data_path`` directly. When omitted, ``input.data_path`` is used
    as-is (back-compatible with callers that have no external fixture
    manifest, e.g. synthetic test data).

    Returns a ``FreqtradeCompatibilityReport`` containing the manifest, status,
    and bounded stdout/stderr.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now.isoformat()
    reason_codes: list[str] = []
    status = CompatibilityStatus.NOT_EXECUTED
    executable_info: FreqtradeExecutableInfo | None = None
    metrics: BacktestMetrics | None = None
    command: tuple[str, ...] = ()
    command_fp = _NO_COMMAND_FINGERPRINT
    config_fp: str | None = None
    data_fp: str | None = None
    strategy_fp: str | None = None
    export_schema: str | None = None
    raw_export_fp: str | None = None
    stdout_text = ""
    stderr_text = ""
    exit_code: int = -1
    runtime_config: dict[str, Any] | None = None
    workspace_path: str | None = None
    evidence_paths: dict[str, str] = {}

    # Stage 1: external resource validation (no execution if invalid).
    status, executable_info, rc = _validate_external_resources(input)
    reason_codes.extend(rc)
    if status != CompatibilityStatus.NOT_EXECUTED:
        result = FreqtradeCompatibilityResult(
            status=CompatibilityStatus.INVALID_EXTERNAL_FIXTURE
            if status == CompatibilityStatus.INVALID_EXTERNAL_FIXTURE
            else CompatibilityStatus.NOT_EXECUTED,
            executable_info=executable_info,
            strategy_fingerprint=None,
            data_fingerprint=None,
            command=(),
            command_fingerprint=_NO_COMMAND_FINGERPRINT,
            runtime_config=None,
            export_schema=None,
            parsed_metrics=None,
            raw_export_fingerprint=None,
            stdout="",
            stderr="",
            exit_code=-1,
            reason_codes=tuple(reason_codes) if reason_codes else (COMPATIBILITY_NOT_EXECUTED,),
        )
        manifest = FreqtradeCompatibilityManifest(
            version=RESEARCH_BACKTEST_COMPARISON_VERSION,
            spec_version=SPEC_VERSION,
            research_backtest_comparison_version=RESEARCH_BACKTEST_COMPARISON_VERSION,
            generated_at=now,
            compatibility_status=result.status,
            executable_version=executable_info.version if executable_info else None,
            executable_fingerprint=None,
            strategy_fingerprint=None,
            data_fingerprint=None,
            command_fingerprint=_NO_COMMAND_FINGERPRINT,
            raw_export_fingerprint=None,
            parsed_metrics_fingerprint=None,
            safety_flags=ResearchBacktestSafetyFlags(),
            reason_codes=result.reason_codes,
        )
        return FreqtradeCompatibilityReport(
            version=RESEARCH_BACKTEST_COMPARISON_VERSION,
            spec_version=SPEC_VERSION,
            research_backtest_comparison_version=RESEARCH_BACKTEST_COMPARISON_VERSION,
            created_at=start_time,
            input=input,
            result=result,
            manifest=manifest,
            safety_flags=ResearchBacktestSafetyFlags(),
            fingerprint=_report_fingerprint(input, result),
            reason_codes=result.reason_codes,
        )

    assert executable_info is not None
    assert input is not None

    # Verify version/backtesting support explicitly.
    supported, version_message, executable_info = _run_freqtrade_version(
        input.executable_path,
        timeout_seconds=input.timeout_seconds,
    )
    if not supported:
        reason_codes.append(COMPATIBILITY_UNSUPPORTED_VERSION)
        reason_codes.append(REAL_FREQTRADE_COMPATIBILITY_NOT_EXECUTED)
        result = FreqtradeCompatibilityResult(
            status=CompatibilityStatus.UNSUPPORTED_VERSION,
            executable_info=executable_info,
            strategy_fingerprint=None,
            data_fingerprint=None,
            command=(str(input.executable_path), "--version"),
            command_fingerprint=command_fingerprint((str(input.executable_path), "--version")),
            runtime_config=None,
            export_schema=None,
            parsed_metrics=None,
            raw_export_fingerprint=None,
            stdout=_bounded_text(version_message),
            stderr="",
            exit_code=-1,
            reason_codes=tuple(reason_codes),
        )
        manifest = FreqtradeCompatibilityManifest(
            version=RESEARCH_BACKTEST_COMPARISON_VERSION,
            spec_version=SPEC_VERSION,
            research_backtest_comparison_version=RESEARCH_BACKTEST_COMPARISON_VERSION,
            generated_at=now,
            compatibility_status=result.status,
            executable_version=executable_info.version if executable_info else None,
            executable_fingerprint=None,
            strategy_fingerprint=None,
            data_fingerprint=None,
            command_fingerprint=result.command_fingerprint,
            raw_export_fingerprint=None,
            parsed_metrics_fingerprint=None,
            safety_flags=ResearchBacktestSafetyFlags(),
            reason_codes=result.reason_codes,
        )
        return FreqtradeCompatibilityReport(
            version=RESEARCH_BACKTEST_COMPARISON_VERSION,
            spec_version=SPEC_VERSION,
            research_backtest_comparison_version=RESEARCH_BACKTEST_COMPARISON_VERSION,
            created_at=start_time,
            input=input,
            result=result,
            manifest=manifest,
            safety_flags=ResearchBacktestSafetyFlags(),
            fingerprint=_report_fingerprint(input, result),
            reason_codes=result.reason_codes,
        )

    workspace: BacktestWorkspace | None = None
    try:
        workspace = BacktestWorkspace(
            prefix="hunter_compat_",
            retain_on_failure=retain_workspace_on_failure,
        )
        workspace.create()
        workspace_path = str(workspace.path)

        # Stage 3: stage strategy and validate class name.
        validate_strategy_class_name(input.strategy_path, input.strategy_name)
        staged_path = workspace.stage_strategy(input.strategy_path)
        strategy_fp = strategy_fingerprint(input.strategy_path)
        data_fp = data_fingerprint(input.data_path)

        # Materialize only manifest-validated fixture files into the isolated
        # workspace when an external fixture manifest is provided. Freqtrade
        # is always pointed at this materialized copy, never at the raw
        # caller-controlled input.data_path directly.
        materialized_data_path: Path | None = None
        if fixture_manifest is not None:
            materialized_data_path = workspace.materialize_fixture_data(
                input.data_path, fixture_manifest
            )

        # Build comparison config and arm.
        comparison_config = _build_backtest_comparison_config(
            input, staged_path, data_path=materialized_data_path
        )
        config_fp = config_fingerprint(comparison_config)
        arm = BacktestArmInput(
            pairlist=tuple(input.pairs),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint=data_fp,
        )

        # Write Freqtrade config and Hunter metadata outside it.
        write_freqtrade_config(comparison_config, arm, workspace)
        _write_hunter_metadata(workspace, input)
        evidence_paths["hunter_metadata"] = str(workspace.evidence_path / "hunter_metadata.json")
        evidence_paths["freqtrade_config"] = str(workspace.config_path)
        runtime_config = json.loads(workspace.config_path.read_text(encoding="utf-8"))

        # Build command and run it.
        command_list = build_backtest_command(comparison_config, workspace)
        command = tuple(command_list)
        command_fp = command_fingerprint(command_list)

        run_result = run_backtest_arm(
            comparison_config,
            arm,
            workspace,
        )
        stdout_text = run_result.stdout or ""
        stderr_text = run_result.stderr or ""
        exit_code = run_result.exit_code
        if run_result.exit_code != 0:
            reason_codes.append(COMPATIBILITY_EXECUTED_FAIL)
            status = CompatibilityStatus.EXECUTED_FAIL
        else:
            status = CompatibilityStatus.EXECUTED_PASS

        # Locate and parse real export.
        try:
            result_path = locate_latest_backtest_result(workspace.backtest_results_dir, workspace.path)
            metrics, export_schema, raw_export_fp = parse_real_export(
                result_path,
                strategy_name=input.strategy_name,
                start_balance=input.starting_balance,
            )
            if metrics.trade_count == 0:
                # Zero-trade run is valid but still a pass at the compatibility level.
                pass
        except ResearchBacktestComparisonParserError as exc:
            reason_codes.append(COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA)
            if exc.reason_code is not None:
                reason_codes.append(exc.reason_code)
            status = CompatibilityStatus.UNSUPPORTED_EXPORT_SCHEMA
            metrics = None
        except ResearchBacktestComparisonRunnerError as exc:
            reason_codes.append(COMPATIBILITY_EXECUTED_FAIL)
            if exc.reason_code is not None:
                reason_codes.append(exc.reason_code)
            status = CompatibilityStatus.EXECUTED_FAIL
            metrics = None

    except ResearchBacktestComparisonValidationError as exc:
        reason_codes.append(COMPATIBILITY_INVALID_EXTERNAL_FIXTURE)
        reason_codes.append(REAL_FREQTRADE_COMPATIBILITY_NOT_EXECUTED)
        status = CompatibilityStatus.INVALID_EXTERNAL_FIXTURE
        stdout_text = exc.args[0] if exc.args else ""
    except Exception as exc:
        reason_codes.append(COMPATIBILITY_EXECUTED_FAIL)
        rc = getattr(exc, "reason_code", None)
        if rc is not None:
            reason_codes.append(rc)
        status = CompatibilityStatus.EXECUTED_FAIL
        stderr_text = str(exc)

    finally:
        if workspace is not None and not retain_workspace_on_failure:
            workspace.cleanup()

    parsed_metrics_fp = metrics_fingerprint(metrics) if metrics is not None else None
    result = FreqtradeCompatibilityResult(
        status=status,
        executable_info=executable_info,
        strategy_fingerprint=strategy_fp,
        data_fingerprint=data_fp,
        command=command,
        command_fingerprint=command_fp,
        runtime_config=runtime_config,
        export_schema=export_schema,
        parsed_metrics=metrics,
        raw_export_fingerprint=raw_export_fp,
        stdout=_bounded_text(stdout_text),
        stderr=_bounded_text(stderr_text),
        exit_code=exit_code,
        reason_codes=tuple(reason_codes) if reason_codes else (COMPATIBILITY_NOT_EXECUTED,),
    )

    manifest = FreqtradeCompatibilityManifest(
        version=RESEARCH_BACKTEST_COMPARISON_VERSION,
        spec_version=SPEC_VERSION,
        research_backtest_comparison_version=RESEARCH_BACKTEST_COMPARISON_VERSION,
        generated_at=now,
        compatibility_status=status,
        executable_version=executable_info.version if executable_info else None,
        executable_fingerprint=None,
        strategy_fingerprint=strategy_fp,
        data_fingerprint=data_fp,
        command_fingerprint=command_fp,
        raw_export_fingerprint=raw_export_fp,
        parsed_metrics_fingerprint=parsed_metrics_fp,
        safety_flags=ResearchBacktestSafetyFlags(),
        reason_codes=result.reason_codes,
    )

    return FreqtradeCompatibilityReport(
        version=RESEARCH_BACKTEST_COMPARISON_VERSION,
        spec_version=SPEC_VERSION,
        research_backtest_comparison_version=RESEARCH_BACKTEST_COMPARISON_VERSION,
        created_at=start_time,
        input=input,
        result=result,
        manifest=manifest,
        safety_flags=ResearchBacktestSafetyFlags(),
        fingerprint=_report_fingerprint(input, result),
        reason_codes=result.reason_codes,
    )
