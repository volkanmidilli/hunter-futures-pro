"""Pure command implementations for hunter.reporting_cli.

MVP-29 — Local Research Reporting CLI.

All command functions are deterministic and return CLICommandResult. They do not
open, read, follow, traverse, or execute files or paths unless explicitly
required to write local output. They never connect to networks, exchanges, APIs,
databases, or external services, and never emit trading or execution commands.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any

from hunter import __version__ as hunter_version
from hunter.backtest import (
    BacktestAllocationMode,
    BacktestCandidateDecision,
    BacktestInput,
    BacktestPriceBar,
    BacktestRunConfig,
    build_backtest_report,
    write_backtest_report,
)
from hunter.discovery import (
    DEFAULT_CSV_PATH as DISCOVERY_DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH as DISCOVERY_DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH as DISCOVERY_DEFAULT_MD_PATH,
    DiscoveryConfig,
    DiscoveryInput,
    DiscoveryOpenInterestSummary,
    DiscoveryRelativeStrengthSummary,
    build_discovery_report,
    write_discovery_report,
)
from hunter.open_interest import (
    DEFAULT_CSV_PATH as OPEN_INTEREST_DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH as OPEN_INTEREST_DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH as OPEN_INTEREST_DEFAULT_MD_PATH,
)
from hunter.portfolio_construction import (
    DEFAULT_CSV_PATH as PORTFOLIO_DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH as PORTFOLIO_DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH as PORTFOLIO_DEFAULT_MD_PATH,
    PortfolioConstructionConfig,
    PortfolioConstructionInput,
    PortfolioDiscoverySummary,
    build_portfolio_construction_report,
    write_portfolio_construction_report,
)
from hunter.relative_strength import (
    DEFAULT_CSV_PATH as RELATIVE_STRENGTH_DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH as RELATIVE_STRENGTH_DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH as RELATIVE_STRENGTH_DEFAULT_MD_PATH,
)

from hunter.reporting_cli.models import (
    CLICommandKind,
    CLICommandResult,
    CLIArtifactSummary,
    CLIExitCode,
    CLIInvocation,
    CLIOutputFormat,
    CLISafetyFlags,
    REPORTING_CLI_REASON_CODES,
    REPORTING_CLI_VERSION,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


CLI_SAFETY_NOTICE = (
    "This Local Research Reporting CLI is a human-audit / research-only tool. "
    "It is not a trading signal, not trade approval, not strategy approval, "
    "not execution approval, not portfolio approval, and not universe approval. "
    "It does not connect to exchanges, networks, APIs, live data, or databases. "
    "It does not place orders, suggest orders, emit action commands, or produce "
    "Freqtrade input. All outputs are local research artifacts only."
)

DEFAULT_RENDER_SAMPLE_OUTPUT_DIR = Path("data/reporting_cli/samples")

_FIXED_GENERATED_AT = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Safety / path helpers
# ---------------------------------------------------------------------------


def build_baseline_safety_flags() -> CLISafetyFlags:
    """Return a CLISafetyFlags with all baseline invariants set to safe."""
    return CLISafetyFlags()


def _is_safe_local_path(value: str, cwd: str | None = None) -> tuple[bool, str]:
    """Validate a path string as a safe local path without filesystem access.

    This is a string-only validator. It does not open, read, follow, traverse, or
    execute the path. Symlink detection is intentionally not performed here
    because it requires filesystem access; symlinks are not followed by the CLI.
    """
    if not isinstance(value, str) or not value.strip():
        return False, "INVALID_PATH"

    # Reject network / URL-like strings.
    if "//" in value or "://" in value:
        return False, "NETWORK_REFERENCE_DETECTED"
    lower = value.lower()
    if lower.startswith(("http://", "https://", "ftp://", "ftps://", "sftp://")):
        return False, "NETWORK_REFERENCE_DETECTED"

    # Reject parent traversal segments. Normalization is string-only.
    normalized = os.path.normpath(value)
    parts = normalized.split(os.sep)
    if ".." in parts:
        return False, "PATH_TRAVERSAL_DETECTED"

    # Reject absolute paths outside the current working directory.
    if os.path.isabs(value):
        if cwd is None:
            cwd = os.getcwd()
        norm_cwd = os.path.normpath(cwd)
        norm_value = os.path.normpath(value)
        if norm_value != norm_cwd and not norm_value.startswith(norm_cwd + os.sep):
            return False, "INVALID_PATH"

    return True, ""


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------


def _result(
    command: str,
    exit_code: CLIExitCode,
    stdout: str = "",
    stderr: str = "",
    output_paths: Sequence[str] | None = None,
    data: Mapping[str, Any] | None = None,
    safety_flags: CLISafetyFlags | None = None,
    reason_codes: Sequence[str] | None = None,
    notes: Sequence[str] | None = None,
) -> CLICommandResult:
    """Build a deterministic CLICommandResult."""
    return CLICommandResult(
        command=command,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        output_paths=tuple(output_paths) if output_paths is not None else (),
        data=MappingProxyType(dict(data)) if data is not None else MappingProxyType({}),
        safety_flags=safety_flags if safety_flags is not None else build_baseline_safety_flags(),
        reason_codes=tuple(reason_codes) if reason_codes is not None else (),
        notes=tuple(notes) if notes is not None else (),
    )


# ---------------------------------------------------------------------------
# Command: version
# ---------------------------------------------------------------------------


def run_version_command(invocation: CLIInvocation) -> CLICommandResult:
    """Return the project version as a structured CLI result."""
    version = hunter_version
    stdout = f"hunter-futures-pro {version}"
    return _result(
        command=invocation.command,
        exit_code=CLIExitCode.OK,
        stdout=stdout,
        data={"version": version},
        reason_codes=("OK", "RESEARCH_ONLY", "NOT_TRADING_ADVICE"),
        notes=(CLI_SAFETY_NOTICE,),
    )


# ---------------------------------------------------------------------------
# Command: safety-summary
# ---------------------------------------------------------------------------


def run_safety_summary_command(invocation: CLIInvocation) -> CLICommandResult:
    """Return a deterministic research-only safety summary."""
    flags = build_baseline_safety_flags()
    data = {"safety_flags": asdict(flags)}

    if invocation.output_format == CLIOutputFormat.JSON:
        stdout = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    elif invocation.output_format == CLIOutputFormat.MARKDOWN:
        lines = [
            "# Reporting CLI Safety Summary",
            "",
            f"> {CLI_SAFETY_NOTICE}",
            "",
            "## Safety Flags",
            "",
        ]
        for key, value in sorted(asdict(flags).items()):
            lines.append(f"- **{key}**: {value}")
        lines.append("")
        stdout = "\n".join(lines)
    else:
        lines = [CLI_SAFETY_NOTICE, ""]
        for key, value in sorted(asdict(flags).items()):
            lines.append(f"{key}: {value}")
        lines.append("")
        stdout = "\n".join(lines)

    return _result(
        command=invocation.command,
        exit_code=CLIExitCode.OK,
        stdout=stdout,
        data=data,
        reason_codes=("OK", "RESEARCH_ONLY", "NOT_TRADING_ADVICE"),
        notes=(CLI_SAFETY_NOTICE,),
    )


# ---------------------------------------------------------------------------
# Command: list-artifacts
# ---------------------------------------------------------------------------


def _artifact_summary(engine_id: str, kind: str, default_path: str) -> CLIArtifactSummary:
    return CLIArtifactSummary(
        engine_id=engine_id,
        artifact_kind=kind,
        default_path=default_path,
        path_is_opaque_string=True,
    )


def run_list_artifacts_command(invocation: CLIInvocation) -> CLICommandResult:
    """Return a deterministic list of opaque artifact path summaries."""
    summaries: list[CLIArtifactSummary] = []

    # Relative strength
    summaries.append(_artifact_summary("relative_strength", "json_report", str(RELATIVE_STRENGTH_DEFAULT_JSON_PATH)))
    summaries.append(_artifact_summary("relative_strength", "csv_results", str(RELATIVE_STRENGTH_DEFAULT_CSV_PATH)))
    summaries.append(_artifact_summary("relative_strength", "markdown_report", str(RELATIVE_STRENGTH_DEFAULT_MD_PATH)))

    # Open interest
    summaries.append(_artifact_summary("open_interest", "json_report", str(OPEN_INTEREST_DEFAULT_JSON_PATH)))
    summaries.append(_artifact_summary("open_interest", "csv_results", str(OPEN_INTEREST_DEFAULT_CSV_PATH)))
    summaries.append(_artifact_summary("open_interest", "markdown_report", str(OPEN_INTEREST_DEFAULT_MD_PATH)))

    # Discovery
    summaries.append(_artifact_summary("discovery", "json_report", str(DISCOVERY_DEFAULT_JSON_PATH)))
    summaries.append(_artifact_summary("discovery", "csv_results", str(DISCOVERY_DEFAULT_CSV_PATH)))
    summaries.append(_artifact_summary("discovery", "markdown_report", str(DISCOVERY_DEFAULT_MD_PATH)))

    # Portfolio construction
    summaries.append(_artifact_summary("portfolio_construction", "json_report", str(PORTFOLIO_DEFAULT_JSON_PATH)))
    summaries.append(_artifact_summary("portfolio_construction", "csv_results", str(PORTFOLIO_DEFAULT_CSV_PATH)))
    summaries.append(_artifact_summary("portfolio_construction", "markdown_report", str(PORTFOLIO_DEFAULT_MD_PATH)))

    # Backtest
    from hunter.backtest.writer import (
        DEFAULT_CSV_PATH as BACKTEST_DEFAULT_CSV_PATH,
        DEFAULT_JSON_PATH as BACKTEST_DEFAULT_JSON_PATH,
        DEFAULT_MD_PATH as BACKTEST_DEFAULT_MD_PATH,
    )
    summaries.append(_artifact_summary("backtest", "json_report", str(BACKTEST_DEFAULT_JSON_PATH)))
    summaries.append(_artifact_summary("backtest", "csv_results", str(BACKTEST_DEFAULT_CSV_PATH)))
    summaries.append(_artifact_summary("backtest", "markdown_report", str(BACKTEST_DEFAULT_MD_PATH)))

    # Reporting CLI own summary artifacts
    summaries.append(_artifact_summary("reporting_cli", "json_summary", str(DEFAULT_RENDER_SAMPLE_OUTPUT_DIR / "reporting_cli" / "cli_summary.json")))
    summaries.append(_artifact_summary("reporting_cli", "markdown_summary", str(DEFAULT_RENDER_SAMPLE_OUTPUT_DIR / "reporting_cli" / "cli_summary.md")))

    data = {
        "artifacts": [
            {
                "engine_id": s.engine_id,
                "artifact_kind": s.artifact_kind,
                "default_path": s.default_path,
                "path_is_opaque_string": s.path_is_opaque_string,
                "metadata": dict(s.metadata),
            }
            for s in summaries
        ]
    }

    stdout_lines = ["# Reporting CLI Artifacts", "", f"> {CLI_SAFETY_NOTICE}", ""]
    for s in summaries:
        stdout_lines.append(f"{s.engine_id}/{s.artifact_kind}: {s.default_path}")
    stdout_lines.append("")
    stdout = "\n".join(stdout_lines)

    return _result(
        command=invocation.command,
        exit_code=CLIExitCode.OK,
        stdout=stdout,
        data=data,
        reason_codes=("OK", "RESEARCH_ONLY", "NOT_TRADING_ADVICE", "OPAQUE_PATH_ONLY"),
        notes=(CLI_SAFETY_NOTICE,),
    )


# ---------------------------------------------------------------------------
# Command: validate-artifact-paths
# ---------------------------------------------------------------------------


def run_validate_artifact_paths_command(invocation: CLIInvocation) -> CLICommandResult:
    """Validate caller-provided path strings without filesystem access."""
    flags = build_baseline_safety_flags()
    failures: list[tuple[str, str]] = []
    cwd = os.getcwd()

    for path in invocation.args:
        ok, reason = _is_safe_local_path(path, cwd=cwd)
        if not ok:
            failures.append((path, reason))
            if reason == "PATH_TRAVERSAL_DETECTED":
                flags = CLISafetyFlags(
                    has_traversal_attempt=True,
                    has_invalid_path=True,
                )
            elif reason == "NETWORK_REFERENCE_DETECTED":
                flags = CLISafetyFlags(
                    has_network_reference=True,
                    has_invalid_path=True,
                )
            else:
                flags = CLISafetyFlags(has_invalid_path=True)

    if failures:
        failure_lines = [f"UNSAFE: {path} ({reason})" for path, reason in failures]
        stderr = "\n".join(failure_lines) + "\n"
        return _result(
            command=invocation.command,
            exit_code=CLIExitCode.VALIDATION_ERROR,
            stdout="",
            stderr=stderr,
            data={"valid": False, "failures": failure_lines},
            safety_flags=flags,
            reason_codes=("VALIDATION_ERROR", "INVALID_PATH") + tuple(reason for _, reason in failures),
            notes=(CLI_SAFETY_NOTICE,),
        )

    stdout = "All paths are safe local strings.\n"
    return _result(
        command=invocation.command,
        exit_code=CLIExitCode.OK,
        stdout=stdout,
        data={"valid": True, "paths": tuple(invocation.args)},
        reason_codes=("OK", "RESEARCH_ONLY", "NOT_TRADING_ADVICE", "OPAQUE_PATH_ONLY"),
        notes=(CLI_SAFETY_NOTICE,),
    )


# ---------------------------------------------------------------------------
# Command: render-sample fixtures
# ---------------------------------------------------------------------------


def _fixed_backtest_input(pair: str, closes: list[float]) -> BacktestInput:
    """Build a deterministic BacktestInput from in-memory values."""
    bars = tuple(
        BacktestPriceBar(
            pair=pair,
            timestamp=datetime(2020, 1, day + 1, tzinfo=timezone.utc),
            close=close,
        )
        for day, close in enumerate(closes)
    )
    decision = BacktestCandidateDecision(
        pair=pair,
        state="INCLUDED",
        classification="CORE_RESEARCH_ALLOCATION",
        final_weight_pct=0.0,
    )
    return BacktestInput(
        pair=pair,
        decision=decision,
        price_bars=bars,
    )


def _fixed_discovery_input(pair: str) -> DiscoveryInput:
    """Build a deterministic DiscoveryInput from in-memory values."""
    rs = DiscoveryRelativeStrengthSummary(
        pair=pair,
        state="READY",
        decision="OUTPERFORMER",
        total_score=80.0,
    )
    oi = DiscoveryOpenInterestSummary(
        pair=pair,
        state="READY",
        positioning="PRICE_UP_OI_UP",
        trend="EXPANDING",
        funding_context="POSITIVE",
        total_score=70.0,
    )
    return DiscoveryInput(
        pair=pair,
        relative_strength=rs,
        open_interest=oi,
    )


def _fixed_portfolio_input(pair: str) -> PortfolioConstructionInput:
    """Build a deterministic PortfolioConstructionInput from in-memory values."""
    discovery = PortfolioDiscoverySummary(
        pair=pair,
        state="CANDIDATE",
        classification="STRONG_RESEARCH_CANDIDATE",
        discovery_score=80.0,
    )
    return PortfolioConstructionInput(
        pair=pair,
        discovery=discovery,
    )


# ---------------------------------------------------------------------------
# Command: render-sample
# ---------------------------------------------------------------------------


def run_render_sample_command(invocation: CLIInvocation) -> CLICommandResult:
    """Write deterministic in-memory sample reports under output_dir."""
    # Validate output directory path string.
    output_dir_str = invocation.output_dir or str(DEFAULT_RENDER_SAMPLE_OUTPUT_DIR)
    cwd = os.getcwd()
    ok, reason = _is_safe_local_path(output_dir_str, cwd=cwd)
    if not ok:
        flags = build_baseline_safety_flags()
        if reason == "PATH_TRAVERSAL_DETECTED":
            flags = CLISafetyFlags(has_traversal_attempt=True, has_invalid_path=True)
        elif reason == "NETWORK_REFERENCE_DETECTED":
            flags = CLISafetyFlags(has_network_reference=True, has_invalid_path=True)
        else:
            flags = CLISafetyFlags(has_invalid_path=True)
        return _result(
            command=invocation.command,
            exit_code=CLIExitCode.VALIDATION_ERROR,
            stdout="",
            stderr=f"Invalid output directory: {output_dir_str} ({reason})\n",
            data={"valid": False, "reason": reason},
            safety_flags=flags,
            reason_codes=("VALIDATION_ERROR", "INVALID_PATH", reason),
            notes=(CLI_SAFETY_NOTICE,),
        )

    output_dir = Path(output_dir_str)

    # Build reports from in-memory fixtures.
    backtest_inputs = [
        _fixed_backtest_input("A", [100.0, 110.0, 121.0]),
        _fixed_backtest_input("B", [200.0, 190.0, 180.0]),
    ]
    backtest_config = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
    backtest_report = build_backtest_report(
        backtest_inputs,
        backtest_config,
        report_id="render-sample-backtest",
        generated_at=_FIXED_GENERATED_AT,
    )

    discovery_inputs = [
        _fixed_discovery_input("BTCUSDT"),
        _fixed_discovery_input("ETHUSDT"),
    ]
    discovery_report = build_discovery_report(
        inputs=discovery_inputs,
        config=DiscoveryConfig(),
        report_id="render-sample-discovery",
        generated_at=_FIXED_GENERATED_AT,
    )

    portfolio_inputs = [
        _fixed_portfolio_input("SOL/USDT:USDT"),
        _fixed_portfolio_input("BTC/USDT:USDT"),
    ]
    portfolio_report = build_portfolio_construction_report(
        inputs=portfolio_inputs,
        config=PortfolioConstructionConfig(),
        report_id="render-sample-portfolio-construction",
        generated_at=_FIXED_GENERATED_AT,
    )

    # Construct deterministic output paths under output_dir.
    backtest_dir = output_dir / "backtest"
    backtest_json = backtest_dir / "backtest_report.json"
    backtest_csv = backtest_dir / "backtest_report.csv"
    backtest_md = backtest_dir / "backtest_report.md"

    portfolio_dir = output_dir / "portfolio_construction"
    portfolio_json = portfolio_dir / "portfolio_construction_report.json"
    portfolio_csv = portfolio_dir / "portfolio_construction_report.csv"
    portfolio_md = portfolio_dir / "portfolio_construction_report.md"

    discovery_dir = output_dir / "discovery"
    discovery_json = discovery_dir / "discovery_report.json"
    discovery_csv = discovery_dir / "discovery_report.csv"
    discovery_md = discovery_dir / "discovery_report.md"

    cli_dir = output_dir / "reporting_cli"
    cli_summary_json = cli_dir / "cli_summary.json"
    cli_summary_md = cli_dir / "cli_summary.md"

    output_paths: list[str] = []
    if not invocation.dry_run:
        # Write engine reports via existing writers.
        write_backtest_report(
            backtest_report,
            json_path=backtest_json,
            csv_path=backtest_csv,
            md_path=backtest_md,
        )
        output_paths.extend([str(backtest_json), str(backtest_csv), str(backtest_md)])

        write_discovery_report(
            discovery_report,
            json_path=discovery_json,
            csv_path=discovery_csv,
            md_path=discovery_md,
        )
        output_paths.extend([str(discovery_json), str(discovery_csv), str(discovery_md)])

        write_portfolio_construction_report(
            portfolio_report,
            json_path=portfolio_json,
            csv_path=portfolio_csv,
            md_path=portfolio_md,
        )
        output_paths.extend([str(portfolio_json), str(portfolio_csv), str(portfolio_md)])

        # Write CLI summary artifacts.
        cli_dir.mkdir(parents=True, exist_ok=True)
        summary_data = {
            "reporting_cli_version": REPORTING_CLI_VERSION,
            "generated_at": _FIXED_GENERATED_AT.isoformat(),
            "safety_notice": CLI_SAFETY_NOTICE,
            "reports": [
                {
                    "engine_id": "backtest",
                    "report_id": backtest_report.report_id,
                    "version": backtest_report.version,
                },
                {
                    "engine_id": "discovery",
                    "report_id": discovery_report.report_id,
                    "version": discovery_report.version,
                },
                {
                    "engine_id": "portfolio_construction",
                    "report_id": portfolio_report.report_id,
                    "version": portfolio_report.version,
                },
            ],
        }
        json_text = json.dumps(summary_data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        cli_summary_json.write_text(json_text, encoding="utf-8")

        md_lines = [
            "# Reporting CLI Sample Summary",
            "",
            f"> {CLI_SAFETY_NOTICE}",
            "",
            "## Rendered Sample Reports",
            "",
            "| Engine | Report ID | Version |",
            "|--------|-----------|---------|",
            f"| backtest | {backtest_report.report_id} | {backtest_report.version} |",
            f"| discovery | {discovery_report.report_id} | {discovery_report.version} |",
            f"| portfolio_construction | {portfolio_report.report_id} | {portfolio_report.version} |",
            "",
        ]
        cli_summary_md.write_text("\n".join(md_lines), encoding="utf-8")
        output_paths.extend([str(cli_summary_json), str(cli_summary_md)])
    else:
        output_paths.extend([
            str(backtest_json), str(backtest_csv), str(backtest_md),
            str(portfolio_json), str(portfolio_csv), str(portfolio_md),
            str(discovery_json), str(discovery_csv), str(discovery_md),
            str(cli_summary_json), str(cli_summary_md),
        ])

    stdout_lines = [CLI_SAFETY_NOTICE, ""]
    if invocation.dry_run:
        stdout_lines.append("Dry-run: no files were written. The following paths would be produced:")
    else:
        stdout_lines.append("Sample reports written to:")
    for p in output_paths:
        stdout_lines.append(f"  {p}")
    stdout_lines.append("")
    stdout = "\n".join(stdout_lines)

    data = {
        "dry_run": invocation.dry_run,
        "output_dir": str(output_dir),
        "reports": [
            {
                "engine_id": "backtest",
                "report_id": backtest_report.report_id,
                "version": backtest_report.version,
            },
            {
                "engine_id": "discovery",
                "report_id": discovery_report.report_id,
                "version": discovery_report.version,
            },
            {
                "engine_id": "portfolio_construction",
                "report_id": portfolio_report.report_id,
                "version": portfolio_report.version,
            },
        ],
    }

    return _result(
        command=invocation.command,
        exit_code=CLIExitCode.OK,
        stdout=stdout,
        output_paths=tuple(output_paths),
        data=data,
        reason_codes=("OK", "RESEARCH_ONLY", "NOT_TRADING_ADVICE", "NO_FILE_INGESTION"),
        notes=(CLI_SAFETY_NOTICE,),
    )


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------


def dispatch_command(invocation: CLIInvocation) -> CLICommandResult:
    """Dispatch a CLIInvocation to the appropriate command function."""
    known = {kind.value for kind in CLICommandKind}
    if invocation.command not in known:
        flags = CLISafetyFlags(has_unsafe_content=False)
        return _result(
            command=invocation.command,
            exit_code=CLIExitCode.USAGE_ERROR,
            stdout="",
            stderr=f"Unknown command: {invocation.command}\n",
            data={"valid": False},
            safety_flags=flags,
            reason_codes=("USAGE_ERROR", "UNKNOWN_COMMAND"),
            notes=(CLI_SAFETY_NOTICE,),
        )

    if invocation.command == CLICommandKind.VERSION.value:
        return run_version_command(invocation)
    if invocation.command == CLICommandKind.SAFETY_SUMMARY.value:
        return run_safety_summary_command(invocation)
    if invocation.command == CLICommandKind.LIST_ARTIFACTS.value:
        return run_list_artifacts_command(invocation)
    if invocation.command == CLICommandKind.VALIDATE_ARTIFACT_PATHS.value:
        return run_validate_artifact_paths_command(invocation)
    if invocation.command == CLICommandKind.RENDER_SAMPLE.value:
        return run_render_sample_command(invocation)

    # Fallback: should not be reachable because of the known-command check.
    flags = CLISafetyFlags(has_unsafe_content=False)
    return _result(
        command=invocation.command,
        exit_code=CLIExitCode.INTERNAL_ERROR,
        stdout="",
        stderr=f"Internal dispatch error: {invocation.command}\n",
        data={"valid": False},
        safety_flags=flags,
        reason_codes=("INTERNAL_ERROR",),
        notes=(CLI_SAFETY_NOTICE,),
    )
