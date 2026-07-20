"""Writer for real Freqtrade compatibility artifacts (SPEC-072)."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from hunter.research_backtest_comparison.models import (
    FreqtradeCompatibilityManifest,
    FreqtradeCompatibilityReport,
    RESEARCH_BACKTEST_COMPARISON_VERSION,
    UNAVAILABLE,
)
from hunter.research_backtest_comparison.redaction import redact_text
from hunter.research_backtest_comparison.writer import _write_json_atomic


class FreqtradeCompatibilityWriter:
    """Write compatibility manifest, JSON report, and markdown report."""

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _manifest_path(self) -> Path:
        return self.output_dir / "freqtrade_compatibility_manifest.json"

    def _report_json_path(self) -> Path:
        return self.output_dir / "freqtrade_compatibility_report.json"

    def _report_markdown_path(self) -> Path:
        return self.output_dir / "freqtrade_compatibility_report.md"

    def write_manifest(self, manifest: FreqtradeCompatibilityManifest) -> Path:
        """Write the compatibility manifest as JSON."""
        path = self._manifest_path()
        _write_json_atomic(path, _manifest_payload(manifest))
        return path

    def write_report_json(self, report: FreqtradeCompatibilityReport) -> Path:
        """Write the compatibility report as JSON."""
        path = self._report_json_path()
        _write_json_atomic(path, _report_payload(report))
        return path

    def write_report_markdown(self, report: FreqtradeCompatibilityReport) -> Path:
        """Write the compatibility report as Markdown."""
        path = self._report_markdown_path()
        path.write_text(_report_markdown(report), encoding="utf-8")
        return path

    def write_all(self, report: FreqtradeCompatibilityReport) -> dict[str, Path]:
        """Write manifest, JSON report, and markdown report."""
        return {
            "manifest": self.write_manifest(report.manifest),
            "report_json": self.write_report_json(report),
            "report_markdown": self.write_report_markdown(report),
        }


def write_all_compatibility_artifacts(
    report: FreqtradeCompatibilityReport,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Write all compatibility artifacts for a report."""
    writer = FreqtradeCompatibilityWriter(output_dir)
    return writer.write_all(report)


def write_backtest_comparison_report(
    report: FreqtradeCompatibilityReport,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Compatibility alias for write_all_compatibility_artifacts."""
    return write_all_compatibility_artifacts(report, output_dir)


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_value(value: Any) -> Any:
    """Serialize a value into a JSON-safe structure."""
    if value is None:
        return UNAVAILABLE
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [_serialize_value(v) for v in value]
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    return value


def _manifest_payload(manifest: FreqtradeCompatibilityManifest) -> dict[str, Any]:
    """Return a deterministic JSON-safe dict for the manifest."""
    return {
        "version": manifest.version,
        "spec_version": manifest.spec_version,
        "research_backtest_comparison_version": manifest.research_backtest_comparison_version,
        "generated_at": manifest.generated_at.isoformat(),
        "compatibility_status": manifest.compatibility_status.value,
        "executable_version": manifest.executable_version,
        "executable_fingerprint": manifest.executable_fingerprint,
        "strategy_fingerprint": manifest.strategy_fingerprint,
        "data_fingerprint": manifest.data_fingerprint,
        "command_fingerprint": manifest.command_fingerprint,
        "raw_export_fingerprint": manifest.raw_export_fingerprint,
        "parsed_metrics_fingerprint": manifest.parsed_metrics_fingerprint,
        "safety_flags": _serialize_value(asdict(manifest.safety_flags)),
        "reason_codes": manifest.reason_codes,
        "metadata": _serialize_value(manifest.metadata),
    }


def _report_payload(report: FreqtradeCompatibilityReport) -> dict[str, Any]:
    """Return a deterministic JSON-safe dict for the report."""
    result = asdict(report.result)
    result = _serialize_value(result)
    if isinstance(result, dict):
        result["status"] = report.result.status.value
    manifest = _manifest_payload(report.manifest)
    return {
        "version": report.version,
        "spec_version": report.spec_version,
        "research_backtest_comparison_version": report.research_backtest_comparison_version,
        "created_at": report.created_at,
        "input": _serialize_value(asdict(report.input)),
        "result": result,
        "manifest": manifest,
        "safety_flags": _serialize_value(asdict(report.safety_flags)),
        "fingerprint": report.fingerprint,
        "human_approval_required": report.human_approval_required,
        "research_only": report.research_only,
        "reason_codes": report.reason_codes,
        "metadata": _serialize_value(report.metadata),
        "_safety_notice": (
            "RESEARCH-ONLY: this artifact is for methodology validation and does not "
            "authorize live trading, automatic execution, or production deployment."
        ),
    }


def _metrics_text(metrics: Any) -> str:
    """Return a short markdown representation of parsed metrics."""
    if metrics is None:
        return "_Unavailable_"
    lines = [""]
    for field in (
        "total_return_pct",
        "absolute_profit",
        "final_balance",
        "max_drawdown_pct",
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
        "profit_factor",
        "win_rate_pct",
        "trade_count",
        "avg_trade_duration",
        "fees_paid",
    ):
        value = getattr(metrics, field, None)
        lines.append(f"- **{field}**: {value if value is not None else UNAVAILABLE}")
    return "\n".join(lines)


def _report_markdown(report: FreqtradeCompatibilityReport) -> str:
    """Render a human-readable markdown report."""
    lines = [
        "# Real Freqtrade Compatibility Report",
        "",
        f"- **Version**: {report.version}",
        f"- **Spec Version**: {report.spec_version}",
        f"- **Research Backtest Comparison Version**: {report.research_backtest_comparison_version}",
        f"- **Created At**: {report.created_at}",
        f"- **Fingerprint**: {report.fingerprint}",
        "",
        "## Safety Invariants",
        "",
        "| Invariant | Value |",
        "|---|---|",
        f"| research_only | {report.safety_flags.research_only} |",
        f"| execution_approval_granted | {report.safety_flags.execution_approval_granted} |",
        f"| production_approval_granted | {report.safety_flags.production_approval_granted} |",
        f"| live_trading_allowed | {report.safety_flags.live_trading_allowed} |",
        f"| automatic_execution_allowed | {report.safety_flags.automatic_execution_allowed} |",
        f"| human_approval_required | {report.safety_flags.human_approval_required} |",
        "",
        "## Status",
        "",
        f"- **Compatibility Status**: {report.result.status.value}",
        f"- **Reason Codes**: {', '.join(report.reason_codes) or UNAVAILABLE}",
        "",
        "## Input",
        "",
        f"- **Strategy**: {report.input.strategy_name}",
        f"- **Strategy Path**: {redact_text(str(report.input.strategy_path))}",
        f"- **Data Path**: {redact_text(str(report.input.data_path))}",
        f"- **Pairs**: {', '.join(report.input.pairs)}",
        f"- **Timeframe**: {report.input.timeframe}",
        f"- **Timerange**: {report.input.timerange}",
        f"- **Starting Balance**: {report.input.starting_balance}",
        f"- **Stake**: {report.input.stake}",
        f"- **Max Open Trades**: {report.input.max_open_trades}",
        f"- **Fee**: {report.input.fee}",
        "",
        "## Executable",
        "",
    ]
    if report.result.executable_info is not None:
        lines.extend(
            [
                f"- **Path**: {redact_text(str(report.result.executable_info.executable_path))}",
                f"- **Version**: {report.result.executable_info.version or UNAVAILABLE}",
                f"- **Valid**: {report.result.executable_info.is_valid}",
            ]
        )
    else:
        lines.append("- *No executable information available.*")
    lines.append("")

    lines.extend(
        [
            "## Command",
            "",
            f"```\n{' '.join(report.result.command) if report.result.command else UNAVAILABLE}\n```",
            "",
            f"- **Command Fingerprint**: {report.result.command_fingerprint}",
            f"- **Export Schema**: {report.result.export_schema or UNAVAILABLE}",
            f"- **Raw Export Fingerprint**: {report.result.raw_export_fingerprint or UNAVAILABLE}",
            f"- **Exit Code**: {report.result.exit_code}",
            "",
            "## Parsed Metrics",
            _metrics_text(report.result.parsed_metrics),
            "",
            "## Captured Output",
            "",
            "### stdout",
            "",
            "```",
            redact_text(report.result.stdout) or "_None_",
            "```",
            "",
            "### stderr",
            "",
            "```",
            redact_text(report.result.stderr) or "_None_",
            "```",
            "",
            "---",
            "",
            "**Closing statement**: This report was produced under the research-only safety "
            "invariants. It does not authorize live trading, automatic execution, production "
            "deployment, or any subprocess boundary beyond the explicit Freqtrade "
            "backtesting invocation.",
            "",
        ]
    )
    return "\n".join(lines)
