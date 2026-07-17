"""Deterministic JSON and Markdown writers for the walk-forward harness (MVP-66 / SPEC-067)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from hunter.research_walk_forward.errors import WalkForwardWriterError
from hunter.research_walk_forward.models import (
    UNAVAILABLE,
    ConsistencyState,
    MarketRegimeLabel,
    MetricAggregate,
    RegimeAggregate,
    WalkForwardExperimentPlan,
    WalkForwardExperimentReport,
    WalkForwardManifest,
    WalkForwardWindowResult,
)

_SILENT_OVERWRITE = "SILENT_OVERWRITE_BLOCKED"
_WRITE_FAILED = "WRITE_FAILED"
_FORBIDDEN_OUTPUT_ROOT = "FORBIDDEN_OUTPUT_ROOT"

_MANDATORY_NOTICE = (
    "This artifact is research-only and is based on historical walk-forward backtesting.\n"
    "Past performance does not guarantee future results.\n"
    "Window consistency, regime summaries, and metric deltas are descriptive evidence only.\n"
    "They do not authorize execution, production deployment, live trading,\n"
    "automatic execution, order placement, signal generation,\n"
    "strategy mutation, universe mutation, or position changes.\n"
    "Human review remains required."
)


def _redact_path(path: str | Path) -> str:
    """Redact home and temp paths from a string representation."""
    import re

    path_str = str(path)
    path_str = re.sub(r"/home/[^/\s]+", "/home/[REDACTED]", path_str)
    path_str = re.sub(r"/tmp/[A-Za-z0-9_./-]+", "/tmp/[REDACTED]", path_str)
    return path_str


def _redact_secrets(text: str) -> str:
    """Redact common secret patterns from text."""
    import re

    if not text:
        return ""
    patterns = (
        (r"api_?key\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{16,})['\"]?", "api_key=[REDACTED]"),
        (r"secret\s*[:=]\s*['\"]?([A-Za-z0-9/+=_\-]{16,})['\"]?", "secret=[REDACTED]"),
        (r"password\s*[:=]\s*['\"]?([^\s'\"]+)['\"]?", "password=[REDACTED]"),
        (r"token\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{16,})['\"]?", "token=[REDACTED]"),
    )
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _serialize_value(value: Any) -> Any:
    """Serialize a value into a deterministic JSON-safe structure."""
    if value is None:
        return UNAVAILABLE
    if isinstance(value, (ConsistencyState, MarketRegimeLabel)):
        return value.value
    return str(value)


def _metric_aggregate_payload(aggregate: MetricAggregate) -> dict[str, Any]:
    """Return a deterministic JSON-safe dict for a metric aggregate."""
    return {
        "metric_name": aggregate.metric_name,
        "available_count": aggregate.available_count,
        "unavailable_count": aggregate.unavailable_count,
        "candidate_higher_count": aggregate.candidate_higher_count,
        "baseline_higher_count": aggregate.baseline_higher_count,
        "equal_count": aggregate.equal_count,
        "mean": _serialize_value(aggregate.mean),
        "median": _serialize_value(aggregate.median),
        "min": _serialize_value(aggregate.min),
        "max": _serialize_value(aggregate.max),
        "q1": _serialize_value(aggregate.q1),
        "q3": _serialize_value(aggregate.q3),
        "iqr": _serialize_value(aggregate.iqr),
        "positive_delta_share": _serialize_value(aggregate.positive_delta_share),
        "negative_delta_share": _serialize_value(aggregate.negative_delta_share),
        "zero_delta_share": _serialize_value(aggregate.zero_delta_share),
        "consistency_state": _serialize_value(aggregate.consistency_state),
        "reason_codes": aggregate.reason_codes,
    }


def _regime_aggregate_payload(aggregate: RegimeAggregate) -> dict[str, Any]:
    """Return a deterministic JSON-safe dict for a regime aggregate."""
    return {
        "regime_label": aggregate.regime_label.value,
        "window_count": aggregate.window_count,
        "completed_count": aggregate.completed_count,
        "failed_count": aggregate.failed_count,
        "blocked_count": aggregate.blocked_count,
        "timed_out_count": aggregate.timed_out_count,
        "unsupported_count": aggregate.unsupported_count,
        "insufficient_count": aggregate.insufficient_count,
        "metric_aggregates": {
            name: _metric_aggregate_payload(agg)
            for name, agg in sorted(aggregate.metric_aggregates.items())
        },
        "fingerprint": aggregate.fingerprint,
        "reason_codes": aggregate.reason_codes,
    }


def _window_result_payload(window: WalkForwardWindowResult) -> dict[str, Any]:
    """Return a deterministic JSON-safe dict for a window result."""
    return {
        "window_index": window.window_index,
        "status": window.status.value,
        "selection_start": window.window.selection_start,
        "selection_end": window.window.selection_end,
        "evaluation_start": window.window.evaluation_start,
        "evaluation_end": window.window.evaluation_end,
        "regime_label": window.window.regime_label.value,
        "candidate_metrics": {k: _serialize_value(v) for k, v in sorted(window.candidate_metrics.items())},
        "baseline_metrics": {k: _serialize_value(v) for k, v in sorted(window.baseline_metrics.items())},
        "metric_deltas": {k: _serialize_value(v) for k, v in sorted(window.metric_deltas.items())},
        "metric_directions": {k: _serialize_value(v) for k, v in sorted(window.metric_directions.items())},
        "comparison_fingerprint": window.comparison_fingerprint,
        "candidate_fingerprint": window.candidate_fingerprint,
        "baseline_fingerprint": window.baseline_fingerprint,
        "fingerprint": window.fingerprint,
        "reason_codes": window.reason_codes,
    }


def _plan_payload(plan: WalkForwardExperimentPlan) -> dict[str, Any]:
    """Return a deterministic JSON-safe dict for the experiment plan."""
    return {
        "mode": plan.mode.value,
        "contiguous": plan.contiguous,
        "windows": [
            {
                "selection_start": window.selection_start,
                "selection_end": window.selection_end,
                "evaluation_start": window.evaluation_start,
                "evaluation_end": window.evaluation_end,
                "regime_label": window.regime_label.value,
            }
            for window in plan.windows
        ],
        "common": {
            "strategy_name": plan.common.strategy_name,
            "strategy_path": _redact_path(plan.common.strategy_path),
            "data_path": _redact_path(plan.common.data_path),
            "timeframe": plan.common.timeframe,
            "balance": str(plan.common.balance),
            "stake": str(plan.common.stake),
            "max_open_trades": plan.common.max_open_trades,
            "fee": str(plan.common.fee),
            "executable_path": _redact_path(plan.common.executable_path),
            "protections": plan.common.protections,
            "timeout_seconds": plan.common.timeout_seconds,
        },
        "safety_flags": {
            "research_only": plan.safety_flags.research_only,
            "execution_approval_granted": plan.safety_flags.execution_approval_granted,
            "production_approval_granted": plan.safety_flags.production_approval_granted,
            "live_trading_allowed": plan.safety_flags.live_trading_allowed,
            "automatic_execution_allowed": plan.safety_flags.automatic_execution_allowed,
            "human_approval_required": plan.safety_flags.human_approval_required,
        },
        "fingerprint": plan.fingerprint,
        "reason_codes": plan.reason_codes,
    }


def _report_payload(report: WalkForwardExperimentReport) -> dict[str, Any]:
    """Return a deterministic JSON-safe dict for the top-level report."""
    return {
        "version": report.version,
        "spec_version": report.spec_version,
        "walk_forward_version": report.walk_forward_version,
        "fingerprint": report.fingerprint,
        "human_approval_required": report.human_approval_required,
        "research_only": report.research_only,
        "plan": _plan_payload(report.plan),
        "window_results": [_window_result_payload(w) for w in report.window_results],
        "metric_aggregates": {
            name: _metric_aggregate_payload(agg)
            for name, agg in sorted(report.metric_aggregates.items())
        },
        "regime_aggregates": [
            _regime_aggregate_payload(agg) for agg in report.regime_aggregates
        ],
        "manifest": {
            "version": report.manifest.version,
            "spec_version": report.manifest.spec_version,
            "walk_forward_version": report.manifest.walk_forward_version,
            "generated_at": report.manifest.generated_at.isoformat(),
            "plan_fingerprint": report.manifest.plan_fingerprint,
            "overall_aggregate_fingerprint": report.manifest.overall_aggregate_fingerprint,
            "regime_aggregate_fingerprint": report.manifest.regime_aggregate_fingerprint,
            "safety_flags": {
                "research_only": report.manifest.safety_flags.research_only,
                "execution_approval_granted": report.manifest.safety_flags.execution_approval_granted,
                "production_approval_granted": report.manifest.safety_flags.production_approval_granted,
                "live_trading_allowed": report.manifest.safety_flags.live_trading_allowed,
                "automatic_execution_allowed": report.manifest.safety_flags.automatic_execution_allowed,
                "human_approval_required": report.manifest.safety_flags.human_approval_required,
            },
            "reason_codes": report.manifest.reason_codes,
        },
        "safety_flags": {
            "research_only": report.safety_flags.research_only,
            "execution_approval_granted": report.safety_flags.execution_approval_granted,
            "production_approval_granted": report.safety_flags.production_approval_granted,
            "live_trading_allowed": report.safety_flags.live_trading_allowed,
            "automatic_execution_allowed": report.safety_flags.automatic_execution_allowed,
            "human_approval_required": report.safety_flags.human_approval_required,
        },
        "reason_codes": report.reason_codes,
        "mandatory_notice": _MANDATORY_NOTICE,
    }


def _manifest_payload(report: WalkForwardExperimentReport) -> dict[str, Any]:
    """Return a deterministic JSON-safe manifest payload."""
    return {
        "version": report.manifest.version,
        "spec_version": report.manifest.spec_version,
        "walk_forward_version": report.manifest.walk_forward_version,
        "generated_at": report.manifest.generated_at.isoformat(),
        "plan_fingerprint": report.manifest.plan_fingerprint,
        "overall_aggregate_fingerprint": report.manifest.overall_aggregate_fingerprint,
        "regime_aggregate_fingerprint": report.manifest.regime_aggregate_fingerprint,
        "report_fingerprint": report.fingerprint,
        "window_count": len(report.window_results),
        "completed_count": sum(1 for w in report.window_results if w.status.value == "COMPLETED"),
        "failed_count": sum(1 for w in report.window_results if w.status.value == "FAILED"),
        "human_approval_required": report.human_approval_required,
        "research_only": report.research_only,
        "mandatory_notice": _MANDATORY_NOTICE,
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
        raise WalkForwardWriterError(
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
        raise WalkForwardWriterError(
            f"Failed to write {path}: {exc}", reason_code=_WRITE_FAILED
        ) from exc


class WalkForwardWriter:
    """Writes deterministic JSON and Markdown walk-forward artifacts."""

    def __init__(
        self,
        *,
        output_dir: str | Path = "reports/research_walk_forward",
        indent: int | None = 2,
        sort_keys: bool = True,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.indent = indent
        self.sort_keys = sort_keys

    def _reject_forbidden_paths(self, path: Path) -> None:
        """Reject writes under data/ or reports/."""
        for forbidden_root in ("data", "reports"):
            try:
                path.relative_to(Path(forbidden_root))
                raise WalkForwardWriterError(
                    f"Refusing to write under {forbidden_root}/: {path}",
                    reason_code=_FORBIDDEN_OUTPUT_ROOT,
                )
            except ValueError:
                pass

    def write_plan(
        self, report: WalkForwardExperimentReport, *, overwrite: bool = False
    ) -> Path:
        """Write the experiment plan as JSON."""
        path = self.output_dir / "walk_forward_experiment_plan.json"
        self._reject_forbidden_paths(path)
        _write_json_atomic(
            path,
            _plan_payload(report.plan),
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def write_window_results(
        self, report: WalkForwardExperimentReport, *, overwrite: bool = False
    ) -> Path:
        """Write per-window results as JSON."""
        path = self.output_dir / "walk_forward_window_results.json"
        self._reject_forbidden_paths(path)
        payload = {
            "window_count": len(report.window_results),
            "windows": [_window_result_payload(w) for w in report.window_results],
        }
        _write_json_atomic(
            path,
            payload,
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def write_metric_aggregates(
        self, report: WalkForwardExperimentReport, *, overwrite: bool = False
    ) -> Path:
        """Write overall metric aggregates as JSON."""
        path = self.output_dir / "walk_forward_metric_aggregates.json"
        self._reject_forbidden_paths(path)
        payload = {
            "metric_aggregates": {
                name: _metric_aggregate_payload(agg)
                for name, agg in sorted(report.metric_aggregates.items())
            }
        }
        _write_json_atomic(
            path,
            payload,
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def write_regime_aggregates(
        self, report: WalkForwardExperimentReport, *, overwrite: bool = False
    ) -> Path:
        """Write regime aggregates as JSON."""
        path = self.output_dir / "walk_forward_regime_aggregates.json"
        self._reject_forbidden_paths(path)
        payload = {
            "regime_aggregates": [
                _regime_aggregate_payload(agg) for agg in report.regime_aggregates
            ]
        }
        _write_json_atomic(
            path,
            payload,
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def write_report(
        self, report: WalkForwardExperimentReport, *, overwrite: bool = False
    ) -> Path:
        """Write the top-level experiment report as JSON."""
        path = self.output_dir / "walk_forward_experiment_report.json"
        self._reject_forbidden_paths(path)
        _write_json_atomic(
            path,
            _report_payload(report),
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def write_manifest(
        self, report: WalkForwardExperimentReport, *, overwrite: bool = False
    ) -> Path:
        """Write the experiment manifest as JSON."""
        path = self.output_dir / "walk_forward_manifest.json"
        self._reject_forbidden_paths(path)
        _write_json_atomic(
            path,
            _manifest_payload(report),
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def _markdown_report(self, report: WalkForwardExperimentReport) -> str:
        """Render a deterministic Markdown summary."""
        lines = [
            "# Walk-Forward Universe Comparison and Regime Evaluation Report",
            "",
            "> **Research only.** Human approval required before any runtime use.",
            "",
            f"- **Version:** `{report.version}`",
            f"- **Spec:** `{report.spec_version}`",
            f"- **Fingerprint:** `{report.fingerprint}`",
            f"- **Mode:** `{report.plan.mode.value}`",
            f"- **Windows:** {len(report.window_results)}",
            "",
            "## Overall Metric Aggregates",
            "",
            "| Metric | Available | Candidate Higher | Baseline Higher | Equal | Mean | Median | Min | Max | Q1 | Q3 | IQR | Consistency |",
            "|--------|-----------|------------------|-----------------|-------|------|--------|-----|-----|----|----|-----|-------------|",
        ]
        for name, agg in sorted(report.metric_aggregates.items()):
            lines.append(
                f"| {name} | {agg.available_count} | {agg.candidate_higher_count} | "
                f"{agg.baseline_higher_count} | {agg.equal_count} | "
                f"{_serialize_value(agg.mean)} | {_serialize_value(agg.median)} | "
                f"{_serialize_value(agg.min)} | {_serialize_value(agg.max)} | "
                f"{_serialize_value(agg.q1)} | {_serialize_value(agg.q3)} | "
                f"{_serialize_value(agg.iqr)} | {agg.consistency_state.value} |"
            )
        lines.extend(["", "## Regime Aggregates", ""])
        if report.regime_aggregates:
            for agg in report.regime_aggregates:
                lines.append(
                    f"- **{agg.regime_label.value}:** {agg.window_count} windows "
                    f"({agg.completed_count} completed, {agg.failed_count} failed, "
                    f"{agg.insufficient_count} insufficient)"
                )
        else:
            lines.append("- No regime aggregates.")
        lines.extend(["", "## Window Results", ""])
        for window in report.window_results:
            lines.append(
                f"- Window {window.window_index}: {window.status.value} | "
                f"{window.window.selection_start}-{window.window.selection_end} -> "
                f"{window.window.evaluation_start}-{window.window.evaluation_end} | "
                f"regime={window.window.regime_label.value}"
            )
        lines.extend(["", "## Mandatory Notice", "", _MANDATORY_NOTICE, ""])
        return "\n".join(lines)

    def write_markdown(
        self, report: WalkForwardExperimentReport, *, overwrite: bool = False
    ) -> Path:
        """Write the Markdown summary of the report."""
        path = self.output_dir / "walk_forward_experiment_report.md"
        self._reject_forbidden_paths(path)
        if path.exists() and not overwrite:
            raise WalkForwardWriterError(
                f"Refusing to silently overwrite existing file: {path}",
                reason_code=_SILENT_OVERWRITE,
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        text = self._markdown_report(report)
        text = _redact_secrets(text)
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
            raise WalkForwardWriterError(
                f"Failed to write {path}: {exc}", reason_code=_WRITE_FAILED
            ) from exc
        return path

    def write_all(self, report: WalkForwardExperimentReport) -> dict[str, Path]:
        """Write all JSON and Markdown artifacts."""
        return {
            "plan": self.write_plan(report),
            "window_results": self.write_window_results(report),
            "metric_aggregates": self.write_metric_aggregates(report),
            "regime_aggregates": self.write_regime_aggregates(report),
            "report": self.write_report(report),
            "manifest": self.write_manifest(report),
            "markdown": self.write_markdown(report),
        }

    def write(self, report: WalkForwardExperimentReport) -> tuple[Path, Path]:
        """Write the report and manifest; return their paths."""
        return self.write_report(report), self.write_manifest(report)


def write_walk_forward_report(
    report: WalkForwardExperimentReport,
    *,
    output_dir: str | Path = "reports/research_walk_forward",
) -> tuple[Path, Path]:
    """Convenience function to write the report and manifest."""
    writer = WalkForwardWriter(output_dir=output_dir)
    return writer.write(report)


def write_all_walk_forward_artifacts(
    report: WalkForwardExperimentReport,
    *,
    output_dir: str | Path = "reports/research_walk_forward",
) -> dict[str, Path]:
    """Convenience function to write all walk-forward artifacts."""
    writer = WalkForwardWriter(output_dir=output_dir)
    return writer.write_all(report)
