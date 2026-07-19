"""Deterministic JSON and Markdown writers for the research backtest comparison harness (MVP-65 / SPEC-066)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonWriterError,
)
from hunter.research_backtest_comparison.models import (
    UNAVAILABLE,
    BacktestComparisonConfig,
    BacktestComparisonManifest,
    BacktestComparisonReport,
    BacktestComparisonResult,
    BacktestFairnessManifest,
    BacktestMetrics,
    BacktestRunResult,
    MetricInterpretation,
    ResearchBacktestSafetyFlags,
)
from hunter.research_backtest_comparison.redaction import redact_text


_SILENT_OVERWRITE = "SILENT_OVERWRITE_BLOCKED"
_WRITE_FAILED = "WRITE_FAILED"

_SAFETY_NOTICE = (
    "RESEARCH ONLY: This artifact is produced by the research backtest comparison harness. "
    "It runs only `freqtrade backtesting` as a subprocess, does not connect to exchanges, "
    "does not perform live or dry-run trading, and does not mutate strategy or config files. "
    "Human approval is required before any runtime or production use."
)

_FORBIDDEN_OUTPUT_ROOT = "FORBIDDEN_OUTPUT_ROOT"


def _project_root() -> Path:
    """Return the project root inferred from this file's location."""
    return Path(__file__).resolve().parents[3]


def _is_forbidden_output_path(path: Path) -> bool:
    """Return True if the resolved path is under the project ``data/`` or ``reports/`` directories."""
    resolved = path.resolve()
    root = _project_root()
    data_dir = root / "data"
    reports_dir = root / "reports"
    try:
        resolved.relative_to(data_dir)
        return True
    except ValueError:
        pass
    try:
        resolved.relative_to(reports_dir)
        return True
    except ValueError:
        pass
    return False


def _validate_output_path(path: Path) -> None:
    """Validate that ``path`` is not inside the project ``data/`` or ``reports/`` directories."""
    if _is_forbidden_output_path(path):
        raise ResearchBacktestComparisonWriterError(
            _FORBIDDEN_OUTPUT_ROOT, f"path is forbidden: {path}"
        )



def _serialize_value(value: Any) -> Any:
    """Serialize a value into a deterministic JSON-safe structure."""
    if value is None:
        return UNAVAILABLE
    if isinstance(value, MetricInterpretation):
        return value.value
    return str(value)


def _metrics_payload(metrics: BacktestMetrics) -> dict[str, Any]:
    """Return a deterministic JSON-safe dict for metrics."""
    return {
        "total_return_pct": _serialize_value(metrics.total_return_pct),
        "absolute_profit": _serialize_value(metrics.absolute_profit),
        "final_balance": _serialize_value(metrics.final_balance),
        "max_drawdown_pct": _serialize_value(metrics.max_drawdown_pct),
        "sharpe_ratio": _serialize_value(metrics.sharpe_ratio),
        "sortino_ratio": _serialize_value(metrics.sortino_ratio),
        "calmar_ratio": _serialize_value(metrics.calmar_ratio),
        "profit_factor": _serialize_value(metrics.profit_factor),
        "win_rate_pct": _serialize_value(metrics.win_rate_pct),
        "trade_count": metrics.trade_count,
        "avg_trade_duration": _serialize_value(metrics.avg_trade_duration),
        "fees_paid": _serialize_value(metrics.fees_paid),
        "parser_version": metrics.parser_version,
    }


def _run_result_payload(result: BacktestRunResult) -> dict[str, Any]:
    """Return a deterministic JSON-safe dict for a run result."""
    return {
        "label": result.label.value,
        "success": result.success,
        "metrics": _metrics_payload(result.metrics),
        "stdout": redact_text(result.stdout),
        "stderr": redact_text(result.stderr),
        "exit_code": result.exit_code,
        "workspace": str(result.workspace),
        "result_file": str(result.result_file) if result.result_file else None,
        "command": list(result.command),
        "command_fingerprint": result.command_fingerprint,
        "strategy_sha_before": result.strategy_sha_before,
        "strategy_sha_after": result.strategy_sha_after,
        "fingerprint": result.fingerprint,
        "reason_codes": result.reason_codes,
    }


def _comparison_payload(comparison: BacktestComparisonResult) -> dict[str, Any]:
    """Return a deterministic JSON-safe dict for the comparison."""
    return {
        "comparison_fingerprint": comparison.comparison_fingerprint,
        "trade_sufficiency": comparison.trade_sufficiency,
        "metric_deltas": {
            k: _serialize_value(v) for k, v in comparison.metric_deltas.items()
        },
        "interpretations": {
            k: v.value for k, v in comparison.interpretations.items()
        },
        "reason_codes": comparison.reason_codes,
    }


def _safety_flags_payload(flags: ResearchBacktestSafetyFlags) -> dict[str, bool]:
    """Return the canonical safety flags payload in deterministic order."""
    return {
        "research_only": flags.research_only,
        "execution_approval_granted": flags.execution_approval_granted,
        "production_approval_granted": flags.production_approval_granted,
        "live_trading_allowed": flags.live_trading_allowed,
        "automatic_execution_allowed": flags.automatic_execution_allowed,
        "human_approval_required": flags.human_approval_required,
        "no_action_commands_emitted": flags.no_action_commands_emitted,
        "no_network_connection": flags.no_network_connection,
        "no_database_connection": flags.no_database_connection,
        "no_exchange_connection": flags.no_exchange_connection,
        "no_automatic_config_mutation": flags.no_automatic_config_mutation,
        "no_open_interest_synthesis": flags.no_open_interest_synthesis,
        "no_remote_changes": flags.no_remote_changes,
        "no_freqtrade_runtime_connection": flags.no_freqtrade_runtime_connection,
        "human_research_only": flags.human_research_only,
    }


def _fairness_payload(fairness: BacktestFairnessManifest) -> dict[str, Any]:
    """Return a deterministic JSON-safe dict for the fairness manifest."""
    return {
        "strategy_name": fairness.strategy_name,
        "strategy_fingerprint": fairness.strategy_fingerprint,
        "data_fingerprint": fairness.data_fingerprint,
        "timeframe": fairness.timeframe,
        "timerange": fairness.timerange,
        "balance": str(fairness.balance),
        "stake": str(fairness.stake),
        "max_open_trades": fairness.max_open_trades,
        "fee": str(fairness.fee),
        "protections": fairness.protections,
        "assumptions_equal": fairness.assumptions_equal,
        "pairlist_only_difference": fairness.pairlist_only_difference,
        "fairness_fingerprint": fairness.fairness_fingerprint,
        "reason_codes": fairness.reason_codes,
    }


def _write_json_atomic(
    path: Path,
    payload: dict[str, Any],
    *,
    indent: int | None = 2,
    sort_keys: bool = True,
    overwrite: bool = False,
) -> None:
    """Write a JSON file atomically via a temporary file and os.replace."""
    if path.exists() and not overwrite:
        raise ResearchBacktestComparisonWriterError(
            f"Refusing to silently overwrite existing file: {path}",
            reason_code=_SILENT_OVERWRITE,
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=indent, sort_keys=sort_keys, ensure_ascii=True, default=str)

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            suffix=".tmp",
        ) as tmp:
            tmp.write(text)
            tmp_path = Path(tmp.name)
        tmp_path.chmod(0o644)
        os.replace(tmp_path, path)
    except Exception as exc:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise ResearchBacktestComparisonWriterError(
            f"Failed to write {path}: {exc}", reason_code=_WRITE_FAILED
        ) from exc


class BacktestComparisonWriter:
    """Writes deterministic JSON and Markdown research backtest comparison artifacts."""

    def __init__(
        self,
        *,
        output_dir: str | Path,
        data_dir: str | Path | None = None,
        indent: int | None = 2,
        sort_keys: bool = True,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.data_dir = Path(data_dir) if data_dir is not None else self.output_dir / "data"
        self.indent = indent
        self.sort_keys = sort_keys

        _validate_output_path(self.output_dir)
        _validate_output_path(self.data_dir)

    def _report_payload(self, report: BacktestComparisonReport) -> dict[str, Any]:
        """Convert a report into a deterministic JSON-safe payload."""
        return {
            "version": report.version,
            "spec_version": report.spec_version,
            "research_backtest_comparison_version": report.research_backtest_comparison_version,
            "fingerprint": report.fingerprint,
            "human_approval_required": report.human_approval_required,
            "research_only": report.research_only,
            "generated_at": report.metadata.get("generated_at", ""),
            "config": {
                "strategy_name": report.config.strategy_name,
                "timeframe": report.config.timeframe,
                "timerange": report.config.timerange,
                "balance": str(report.config.balance),
                "stake": str(report.config.stake),
                "max_open_trades": report.config.max_open_trades,
                "fee": str(report.config.fee),
                "protections": report.config.protections,
            },
            "manifest": {
                "version": report.manifest.version,
                "spec_version": report.manifest.spec_version,
                "research_backtest_comparison_version": report.manifest.research_backtest_comparison_version,
                "generated_at": report.manifest.generated_at.isoformat(),
                "config_fingerprint": report.manifest.config_fingerprint,
                "strategy_fingerprint": report.manifest.strategy_fingerprint,
                "candidate_pairlist_fingerprint": report.manifest.candidate_pairlist_fingerprint,
                "baseline_pairlist_fingerprint": report.manifest.baseline_pairlist_fingerprint,
                "candidate_result_fingerprint": report.manifest.candidate_result_fingerprint,
                "baseline_result_fingerprint": report.manifest.baseline_result_fingerprint,
                "comparison_fingerprint": report.manifest.comparison_fingerprint,
                "safety_flags": _safety_flags_payload(report.manifest.safety_flags),
                "reason_codes": report.manifest.reason_codes,
            },
            "candidate": _run_result_payload(report.candidate),
            "baseline": _run_result_payload(report.baseline),
            "comparison": _comparison_payload(report.comparison),
            "fairness": _fairness_payload(report.fairness),
            "safety_flags": _safety_flags_payload(report.safety_flags),
            "reason_codes": report.reason_codes,
            "metadata": dict(report.metadata),
            "safety_notice": _SAFETY_NOTICE,
        }

    def write_report(
        self, report: BacktestComparisonReport, *, overwrite: bool = False
    ) -> Path:
        """Write the top-level comparison report as JSON."""
        filename = f"backtest_comparison_report_{report.fingerprint}.json"
        path = self.output_dir / filename
        _write_json_atomic(
            path,
            self._report_payload(report),
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def write_manifest(
        self, report: BacktestComparisonReport, *, overwrite: bool = False
    ) -> Path:
        """Write a lightweight manifest summarizing the report."""
        filename = f"backtest_comparison_report_{report.fingerprint}.json"
        manifest = {
            "version": report.version,
            "spec_version": report.spec_version,
            "research_backtest_comparison_version": report.research_backtest_comparison_version,
            "fingerprint": report.fingerprint,
            "report_path": f"reports/research_backtest_comparison/{filename}",
            "candidate_pair_count": len(report.candidate.pairlist),
            "baseline_pair_count": len(report.baseline.pairlist),
            "human_approval_required": report.human_approval_required,
            "research_only": report.research_only,
            "safety_notice": _SAFETY_NOTICE,
        }
        path = self.data_dir / "backtest_comparison_manifest.json"
        _write_json_atomic(
            path,
            manifest,
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def write_candidate_metrics(
        self, report: BacktestComparisonReport, *, overwrite: bool = False
    ) -> Path:
        """Write candidate metrics as JSON."""
        filename = f"candidate_metrics_{report.comparison.candidate.fingerprint}.json"
        path = self.output_dir / filename
        _write_json_atomic(
            path,
            _run_result_payload(report.candidate),
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def write_baseline_metrics(
        self, report: BacktestComparisonReport, *, overwrite: bool = False
    ) -> Path:
        """Write baseline metrics as JSON."""
        filename = f"baseline_metrics_{report.comparison.baseline.fingerprint}.json"
        path = self.output_dir / filename
        _write_json_atomic(
            path,
            _run_result_payload(report.baseline),
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def write_comparison(
        self, report: BacktestComparisonReport, *, overwrite: bool = False
    ) -> Path:
        """Write comparison metrics as JSON."""
        filename = f"comparison_{report.comparison.comparison_fingerprint}.json"
        path = self.output_dir / filename
        _write_json_atomic(
            path,
            _comparison_payload(report.comparison),
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def write_fairness_manifest(
        self, report: BacktestComparisonReport, *, overwrite: bool = False
    ) -> Path:
        """Write fairness manifest as JSON."""
        filename = f"fairness_{report.fairness.fairness_fingerprint}.json"
        path = self.output_dir / filename
        _write_json_atomic(
            path,
            _fairness_payload(report.fairness),
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def _markdown_report(self, report: BacktestComparisonReport) -> str:
        """Render a Markdown summary of the report."""
        lines = [
            "# Research Backtest Comparison Report",
            "",
            "> **Research only.** Human approval required before any runtime use.",
            "",
            f"- **Version:** `{report.version}`",
            f"- **Spec:** `{report.spec_version}`",
            f"- **Fingerprint:** `{report.fingerprint}`",
            "",
            "## Candidate vs Baseline",
            "",
            "| Metric | Candidate | Baseline | Delta | Interpretation |",
            "|--------|-----------|----------|-------|----------------|",
        ]
        for name in (
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
            c = _serialize_value(getattr(report.candidate.metrics, name))
            b = _serialize_value(getattr(report.baseline.metrics, name))
            d = _serialize_value(report.comparison.metric_deltas.get(name))
            i = report.comparison.interpretations.get(name, MetricInterpretation.UNAVAILABLE).value
            lines.append(f"| {name} | {c} | {b} | {d} | {i} |")
        lines.extend(["", f"- **Trade sufficiency:** {report.comparison.trade_sufficiency}", ""])
        lines.extend(["", _SAFETY_NOTICE, ""])
        return "\n".join(lines)

    def write_markdown(
        self, report: BacktestComparisonReport, *, overwrite: bool = False
    ) -> Path:
        """Write the Markdown summary of the report."""
        filename = f"backtest_comparison_report_{report.fingerprint}.md"
        path = self.output_dir / filename
        if path.exists() and not overwrite:
            raise ResearchBacktestComparisonWriterError(
                f"Refusing to silently overwrite existing file: {path}",
                reason_code=_SILENT_OVERWRITE,
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        text = self._markdown_report(report)
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                delete=False,
                suffix=".tmp",
            ) as tmp:
                tmp.write(text)
                tmp_path = Path(tmp.name)
            tmp_path.chmod(0o644)
            os.replace(tmp_path, path)
        except Exception as exc:
            if tmp_path is not None and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise ResearchBacktestComparisonWriterError(
                f"Failed to write {path}: {exc}", reason_code=_WRITE_FAILED
            ) from exc
        return path

    def write_all(self, report: BacktestComparisonReport) -> dict[str, Path]:
        """Write all JSON and Markdown artifacts plus the report and manifest."""
        return {
            "report": self.write_report(report),
            "manifest": self.write_manifest(report),
            "candidate_metrics": self.write_candidate_metrics(report),
            "baseline_metrics": self.write_baseline_metrics(report),
            "comparison": self.write_comparison(report),
            "fairness_manifest": self.write_fairness_manifest(report),
            "markdown": self.write_markdown(report),
        }

    def write(self, report: BacktestComparisonReport) -> tuple[Path, Path]:
        """Write the top-level report and manifest; return their paths."""
        return self.write_report(report), self.write_manifest(report)


def write_backtest_comparison_report(
    report: BacktestComparisonReport,
    *,
    output_dir: str | Path,
    data_dir: str | Path | None = None,
) -> tuple[Path, Path]:
    """Convenience function to write a backtest comparison report and manifest."""
    writer = BacktestComparisonWriter(output_dir=output_dir, data_dir=data_dir)
    return writer.write(report)


def write_all_backtest_comparison_artifacts(
    report: BacktestComparisonReport,
    *,
    output_dir: str | Path,
    data_dir: str | Path | None = None,
) -> dict[str, Path]:
    """Convenience function to write all backtest comparison artifacts."""
    writer = BacktestComparisonWriter(output_dir=output_dir, data_dir=data_dir)
    return writer.write_all(report)
