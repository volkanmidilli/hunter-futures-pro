"""Deterministic JSON and Markdown writers for the statistical confidence package (MVP-67 / SPEC-068)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from hunter.research_statistical_confidence.errors import (
    StatisticalConfidenceWriterError,
)
from hunter.research_statistical_confidence.fingerprint import (
    _serialize_value,
    config_fingerprint,
    metric_results_fingerprint,
    regime_results_fingerprint,
    safety_flags_fingerprint,
)
from hunter.research_statistical_confidence.models import (
    UNAVAILABLE,
    ConfidenceState,
    ExperimentConfidenceReport,
    MetricConfidenceResult,
    RegimeConfidenceResult,
    StatisticalConfidenceConfig,
    StatisticalConfidenceManifest,
    StatisticalConfidenceSafetyFlags,
)

_SILENT_OVERWRITE = "SILENT_OVERWRITE_BLOCKED"
_WRITE_FAILED = "WRITE_FAILED"
_FORBIDDEN_OUTPUT_ROOT = "FORBIDDEN_OUTPUT_ROOT"
_MISSING_OUTPUT_DIR = "MISSING_OUTPUT_DIR"


class _MissingOutputDir:
    """Sentinel indicating no output_dir was supplied."""


_MISSING_OUTPUT_DIR_SENTINEL = _MissingOutputDir()

_MANDATORY_NOTICE = (
    "This artifact is research-only and summarizes statistical stability "
    "of historical walk-forward comparisons.\n"
    "Bootstrap intervals, sensitivity results, regime summaries, "
    "and confidence classifications are descriptive research evidence only. "
    "They do not prove profitability and do not authorize execution, "
    "production deployment, live trading, automatic execution, "
    "strategy selection, universe selection, order placement, "
    "signal generation, strategy mutation, universe mutation, "
    "or position changes.\n"
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
        raise StatisticalConfidenceWriterError(
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
        raise StatisticalConfidenceWriterError(
            f"Failed to write {path}: {exc}", reason_code=_WRITE_FAILED
        ) from exc


def _config_payload(config: StatisticalConfidenceConfig) -> dict[str, Any]:
    """Return a deterministic JSON-safe dict for config."""
    return {
        "minimum_available_window_count": config.minimum_available_window_count,
        "confidence_level": str(config.confidence_level),
        "bootstrap": {
            "seed": config.bootstrap.seed,
            "iterations": config.bootstrap.iterations,
        },
        "robustness": {
            "sign_share_threshold": str(config.robustness.sign_share_threshold),
            "maximum_influence_ratio": str(config.robustness.maximum_influence_ratio),
            "confidence_level": str(config.robustness.confidence_level),
        },
    }


def _metric_result_payload(result: MetricConfidenceResult) -> dict[str, Any]:
    """Return a deterministic JSON-safe dict for a metric confidence result."""
    return {
        "metric_name": result.metric_name,
        "available_count": result.available_count,
        "unavailable_count": result.unavailable_count,
        "mean": _serialize_value(result.mean),
        "median": _serialize_value(result.median),
        "std_dev": _serialize_value(result.std_dev),
        "mad": _serialize_value(result.mad),
        "min": _serialize_value(result.min),
        "max": _serialize_value(result.max),
        "q1": _serialize_value(result.q1),
        "q3": _serialize_value(result.q3),
        "iqr": _serialize_value(result.iqr),
        "positive_share": str(result.positive_share),
        "negative_share": str(result.negative_share),
        "zero_share": str(result.zero_share),
        "bootstrap_mean_ci": _serialize_value(result.bootstrap_mean_ci) if result.bootstrap_mean_ci else UNAVAILABLE,
        "bootstrap_median_ci": _serialize_value(result.bootstrap_median_ci) if result.bootstrap_median_ci else UNAVAILABLE,
        "loo": _serialize_value(result.loo) if result.loo else UNAVAILABLE,
        "confidence_state": result.confidence_state.value,
        "reason_codes": sorted(result.reason_codes),
    }


def _regime_result_payload(result: RegimeConfidenceResult) -> dict[str, Any]:
    """Return a deterministic JSON-safe dict for a regime confidence result."""
    return {
        "regime_label": result.regime_label.value,
        "available_count": result.available_count,
        "metric_results": {
            name: _metric_result_payload(mr)
            for name, mr in sorted(result.metric_results.items())
        },
        "status_counts": dict(sorted(result.status_counts.items())),
        "fingerprint": result.fingerprint,
        "reason_codes": sorted(result.reason_codes),
    }


def _manifest_payload(manifest: StatisticalConfidenceManifest) -> dict[str, Any]:
    """Return a deterministic JSON-safe dict for the manifest."""
    return {
        "version": manifest.version,
        "spec_version": manifest.spec_version,
        "statistical_confidence_version": manifest.statistical_confidence_version,
        "generated_at": manifest.generated_at.isoformat(),
        "config_fingerprint": manifest.config_fingerprint,
        "metric_results_fingerprint": manifest.metric_results_fingerprint,
        "regime_results_fingerprint": manifest.regime_results_fingerprint,
        "overall_fingerprint": manifest.overall_fingerprint,
        "safety_flags": {
            "research_only": manifest.safety_flags.research_only,
            "execution_approval_granted": manifest.safety_flags.execution_approval_granted,
            "production_approval_granted": manifest.safety_flags.production_approval_granted,
            "live_trading_allowed": manifest.safety_flags.live_trading_allowed,
            "automatic_execution_allowed": manifest.safety_flags.automatic_execution_allowed,
            "human_approval_required": manifest.safety_flags.human_approval_required,
            "no_direct_subprocess": manifest.safety_flags.no_direct_subprocess,
            "no_parallel_execution": manifest.safety_flags.no_parallel_execution,
            "no_network_connection": manifest.safety_flags.no_network_connection,
            "no_database_connection": manifest.safety_flags.no_database_connection,
            "no_exchange_connection": manifest.safety_flags.no_exchange_connection,
            "no_remote_changes": manifest.safety_flags.no_remote_changes,
            "no_action_commands_emitted": manifest.safety_flags.no_action_commands_emitted,
        },
        "reason_codes": sorted(manifest.reason_codes),
    }


def _report_payload(report: ExperimentConfidenceReport) -> dict[str, Any]:
    """Return a deterministic JSON-safe dict for the confidence report."""
    return {
        "version": report.version,
        "spec_version": report.spec_version,
        "statistical_confidence_version": report.statistical_confidence_version,
        "source_report_fingerprint": report.source_report_fingerprint,
        "config": _config_payload(report.config),
        "metric_results": {
            name: _metric_result_payload(mr)
            for name, mr in sorted(report.metric_results.items())
        },
        "regime_results": {
            name: _regime_result_payload(rr)
            for name, rr in sorted(report.regime_results.items())
        },
        "manifest": _manifest_payload(report.manifest),
        "safety_flags": {
            "research_only": report.safety_flags.research_only,
            "execution_approval_granted": report.safety_flags.execution_approval_granted,
            "production_approval_granted": report.safety_flags.production_approval_granted,
            "live_trading_allowed": report.safety_flags.live_trading_allowed,
            "automatic_execution_allowed": report.safety_flags.automatic_execution_allowed,
            "human_approval_required": report.safety_flags.human_approval_required,
            "no_direct_subprocess": report.safety_flags.no_direct_subprocess,
            "no_parallel_execution": report.safety_flags.no_parallel_execution,
            "no_network_connection": report.safety_flags.no_network_connection,
            "no_database_connection": report.safety_flags.no_database_connection,
            "no_exchange_connection": report.safety_flags.no_exchange_connection,
            "no_remote_changes": report.safety_flags.no_remote_changes,
            "no_action_commands_emitted": report.safety_flags.no_action_commands_emitted,
        },
        "fingerprint": report.fingerprint,
        "human_approval_required": report.human_approval_required,
        "research_only": report.research_only,
        "reason_codes": sorted(report.reason_codes),
        "mandatory_notice": _MANDATORY_NOTICE,
    }


class StatisticalConfidenceWriter:
    """Writes deterministic JSON and Markdown statistical confidence artifacts."""

    def __init__(
        self,
        *,
        output_dir: str | Path | _MissingOutputDir = _MISSING_OUTPUT_DIR_SENTINEL,
        indent: int | None = 2,
        sort_keys: bool = True,
    ) -> None:
        if isinstance(output_dir, _MissingOutputDir):
            raise StatisticalConfidenceWriterError(
                "output_dir is mandatory; pass an explicit safe output directory",
                reason_code=_MISSING_OUTPUT_DIR,
            )
        if output_dir is None or str(output_dir).strip() == "":
            raise StatisticalConfidenceWriterError(
                "output_dir cannot be empty or None",
                reason_code=_MISSING_OUTPUT_DIR,
            )
        self.output_dir = Path(output_dir)
        self.indent = indent
        self.sort_keys = sort_keys

    def _reject_forbidden_paths(self, path: Path) -> None:
        """Reject writes under data/ or reports/."""
        path_parts = path.resolve().parts
        if "data" in path_parts or "reports" in path_parts:
            for forbidden_root in ("data", "reports"):
                if forbidden_root in path_parts:
                    raise StatisticalConfidenceWriterError(
                        f"Refusing to write under {forbidden_root}/: {path}",
                        reason_code=_FORBIDDEN_OUTPUT_ROOT,
                    )

    def write_config(
        self, config: StatisticalConfidenceConfig, *, overwrite: bool = False
    ) -> Path:
        """Write the config as JSON."""
        path = self.output_dir / "statistical_confidence_config.json"
        self._reject_forbidden_paths(path)
        _write_json_atomic(
            path,
            _config_payload(config),
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def write_metric_results(
        self, report: ExperimentConfidenceReport, *, overwrite: bool = False
    ) -> Path:
        """Write metric confidence results as JSON."""
        path = self.output_dir / "metric_confidence_results.json"
        self._reject_forbidden_paths(path)
        payload = {
            "metric_results": {
                name: _metric_result_payload(mr)
                for name, mr in sorted(report.metric_results.items())
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

    def write_regime_results(
        self, report: ExperimentConfidenceReport, *, overwrite: bool = False
    ) -> Path:
        """Write regime confidence results as JSON."""
        path = self.output_dir / "regime_confidence_results.json"
        self._reject_forbidden_paths(path)
        payload = {
            "regime_results": {
                name: _regime_result_payload(rr)
                for name, rr in sorted(report.regime_results.items())
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

    def write_report(
        self, report: ExperimentConfidenceReport, *, overwrite: bool = False
    ) -> Path:
        """Write the experiment confidence report as JSON."""
        path = self.output_dir / "experiment_confidence_report.json"
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
        self, report: ExperimentConfidenceReport, *, overwrite: bool = False
    ) -> Path:
        """Write the statistical confidence manifest as JSON."""
        path = self.output_dir / "statistical_confidence_manifest.json"
        self._reject_forbidden_paths(path)
        _write_json_atomic(
            path,
            _manifest_payload(report.manifest),
            indent=self.indent,
            sort_keys=self.sort_keys,
            overwrite=overwrite,
        )
        return path

    def _markdown_report(self, report: ExperimentConfidenceReport) -> str:
        """Render a deterministic Markdown summary."""
        lines = [
            "# Walk-Forward Statistical Confidence Report",
            "",
            "> **Research only.** Human approval required before any runtime use.",
            "",
            f"- **Version:** `{report.version}`",
            f"- **Spec:** `{report.spec_version}`",
            f"- **Fingerprint:** `{report.fingerprint}`",
            f"- **Source Report Fingerprint:** `{report.source_report_fingerprint}`",
            "",
            "## Metric Confidence Results",
            "",
            "| Metric | Windows (Avail/Total) | Mean | Median | Std Dev | Positive Share | Negative Share | Confidence State |",
            "|--------|----------------------|------|--------|---------|---------------|---------------|------------------|",
        ]
        for name, mr in sorted(report.metric_results.items()):
            total = mr.available_count + mr.unavailable_count
            lines.append(
                f"| {name} | {mr.available_count}/{total} | "
                f"{_serialize_value(mr.mean)} | {_serialize_value(mr.median)} | "
                f"{_serialize_value(mr.std_dev)} | {str(mr.positive_share)} | "
                f"{str(mr.negative_share)} | {mr.confidence_state.value} |"
            )

        lines.extend(["", "## Regime Results", ""])
        if report.regime_results:
            for regime_name, rr in sorted(report.regime_results.items()):
                lines.append(f"- **{regime_name}:** {rr.available_count} available windows")
                for metric_name, mr in sorted(rr.metric_results.items()):
                    lines.append(
                        f"  - {metric_name}: {mr.confidence_state.value} "
                        f"({mr.available_count} windows)"
                    )
        else:
            lines.append("- No regime results.")

        lines.extend(["", "## Reason Codes", ""])
        all_codes: set[str] = set()
        for mr in report.metric_results.values():
            all_codes.update(mr.reason_codes)
        if all_codes:
            for code in sorted(all_codes):
                lines.append(f"- `{code}`")
        else:
            lines.append("- None")

        lines.extend(["", "## Mandatory Notice", "", _MANDATORY_NOTICE, ""])
        return "\n".join(lines)

    def write_markdown(
        self, report: ExperimentConfidenceReport, *, overwrite: bool = False
    ) -> Path:
        """Write the Markdown summary of the statistical confidence report."""
        path = self.output_dir / "experiment_confidence_report.md"
        self._reject_forbidden_paths(path)
        if path.exists() and not overwrite:
            raise StatisticalConfidenceWriterError(
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
            raise StatisticalConfidenceWriterError(
                f"Failed to write {path}: {exc}", reason_code=_WRITE_FAILED
            ) from exc
        return path

    def write_all(
        self, report: ExperimentConfidenceReport, *, overwrite: bool = False
    ) -> dict[str, Path]:
        """Write all JSON and Markdown statistical confidence artifacts."""
        return {
            "config": self.write_config(report.config, overwrite=overwrite),
            "metric_results": self.write_metric_results(report, overwrite=overwrite),
            "regime_results": self.write_regime_results(report, overwrite=overwrite),
            "report": self.write_report(report, overwrite=overwrite),
            "manifest": self.write_manifest(report, overwrite=overwrite),
            "markdown": self.write_markdown(report, overwrite=overwrite),
        }


def write_experiment_confidence_report(
    report: ExperimentConfidenceReport,
    *,
    output_dir: str | Path | _MissingOutputDir = _MISSING_OUTPUT_DIR_SENTINEL,
) -> tuple[Path, Path]:
    """Convenience function to write the report and manifest.

    Args:
        report: The experiment confidence report to write.
        output_dir: Mandatory explicit safe output directory.
    """
    writer = StatisticalConfidenceWriter(output_dir=output_dir)
    return writer.write_report(report), writer.write_manifest(report)


def write_all_statistical_confidence_artifacts(
    report: ExperimentConfidenceReport,
    *,
    output_dir: str | Path | _MissingOutputDir = _MISSING_OUTPUT_DIR_SENTINEL,
) -> dict[str, Path]:
    """Convenience function to write all statistical confidence artifacts.

    Args:
        report: The experiment confidence report to write.
        output_dir: Mandatory explicit safe output directory.
    """
    writer = StatisticalConfidenceWriter(output_dir=output_dir)
    return writer.write_all(report)
