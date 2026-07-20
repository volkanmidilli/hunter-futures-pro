"""Research methodology validation engine and writer (SPEC-072)."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from hunter.research_statistical_confidence.fingerprint import _serialize_value
from hunter.research_statistical_confidence.methodology import (
    PolicyResult,
    ResearchMethodologyPolicy,
)
from hunter.research_statistical_confidence.models import (
    STATISTICAL_CONFIDENCE_VERSION,
    SPEC_VERSION,
    StatisticalConfidenceSafetyFlags,
    UNAVAILABLE,
)
from hunter.research_statistical_confidence.writer import (
    _redact_path,
    _redact_secrets,
    _write_json_atomic,
)
from hunter.research_walk_forward.models import WalkForwardWindowResult


@dataclass(frozen=True)
class MethodologyValidationReport:
    """Top-level methodology validation report."""

    version: str
    spec_version: str
    created_at: str
    safety_flags: StatisticalConfidenceSafetyFlags
    policy_results: tuple[PolicyResult, ...]
    overall_passed: bool
    reason_codes: tuple[str, ...]
    fingerprint: str
    mandatory_notice: str = field(
        default=(
            "This artifact is research-only and validates methodology assumptions "
            "for walk-forward comparisons. It does not authorize execution, production "
            "deployment, live trading, automatic execution, or strategy selection. "
            "Human review remains required."
        )
    )

    def __post_init__(self) -> None:
        if not self.version or not self.spec_version:
            raise ValueError("version and spec_version are required")
        if not self.policy_results:
            raise ValueError("policy_results must not be empty")


@dataclass(frozen=True)
class MethodologyPolicyArtifact:
    """Container for the methodology policy JSON artifact."""

    version: str
    spec_version: str
    created_at: str
    safety_flags: StatisticalConfidenceSafetyFlags
    policies: tuple[PolicyResult, ...]
    reason_codes: tuple[str, ...]


def _safety_flags_payload(flags: StatisticalConfidenceSafetyFlags) -> dict[str, bool]:
    return {
        "research_only": flags.research_only,
        "execution_approval_granted": flags.execution_approval_granted,
        "production_approval_granted": flags.production_approval_granted,
        "live_trading_allowed": flags.live_trading_allowed,
        "automatic_execution_allowed": flags.automatic_execution_allowed,
        "human_approval_required": flags.human_approval_required,
        "no_direct_subprocess": flags.no_direct_subprocess,
        "no_parallel_execution": flags.no_parallel_execution,
        "no_network_connection": flags.no_network_connection,
        "no_database_connection": flags.no_database_connection,
        "no_exchange_connection": flags.no_exchange_connection,
        "no_remote_changes": flags.no_remote_changes,
        "no_action_commands_emitted": flags.no_action_commands_emitted,
    }


def _policy_result_payload(result: PolicyResult) -> dict[str, Any]:
    return {
        "policy": result.policy,
        "passed": result.passed,
        "reason_codes": sorted(result.reason_codes),
        "details": _serialize_value(result.details),
    }


def _policy_payload(policy: ResearchMethodologyPolicy) -> dict[str, Any]:
    """Serialize a ResearchMethodologyPolicy to a deterministic dict."""
    return {
        "no_trade_policy": {
            "flag_baseline": policy.no_trade_policy.flag_baseline,
            "flag_candidate": policy.no_trade_policy.flag_candidate,
        },
        "insufficient_evidence_policy": {
            "min_trades_per_window": policy.insufficient_evidence_policy.min_trades_per_window,
            "min_available_windows": policy.insufficient_evidence_policy.min_available_windows,
        },
        "window_dependence_policy": {
            "allow_overlap": policy.window_dependence_policy.allow_overlap,
        },
    }


def _build_methodology_validation_report(
    policy_results: tuple[PolicyResult, ...],
    safety_flags: StatisticalConfidenceSafetyFlags | None = None,
) -> MethodologyValidationReport:
    """Build a methodology validation report from individual policy results."""
    reason_codes: list[str] = []
    for result in policy_results:
        reason_codes.extend(result.reason_codes)

    overall_passed = all(result.passed for result in policy_results)
    unique_reason_codes = tuple(sorted(set(reason_codes)))

    payload = {
        "version": STATISTICAL_CONFIDENCE_VERSION,
        "spec_version": SPEC_VERSION,
        "policy_results": [_policy_result_payload(r) for r in policy_results],
        "overall_passed": overall_passed,
        "reason_codes": list(unique_reason_codes),
    }

    import hashlib
    import json

    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    fingerprint = hashlib.sha256(text.encode("utf-8")).hexdigest()

    return MethodologyValidationReport(
        version=STATISTICAL_CONFIDENCE_VERSION,
        spec_version=SPEC_VERSION,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        safety_flags=safety_flags or StatisticalConfidenceSafetyFlags(),
        policy_results=policy_results,
        overall_passed=overall_passed,
        reason_codes=unique_reason_codes,
        fingerprint=fingerprint,
    )


def _methodology_validation_payload(report: MethodologyValidationReport) -> dict[str, Any]:
    return {
        "version": report.version,
        "spec_version": report.spec_version,
        "created_at": report.created_at,
        "safety_flags": _safety_flags_payload(report.safety_flags),
        "policy_results": [_policy_result_payload(r) for r in report.policy_results],
        "overall_passed": report.overall_passed,
        "reason_codes": sorted(report.reason_codes),
        "fingerprint": report.fingerprint,
        "mandatory_notice": report.mandatory_notice,
    }


def _policy_artifact_payload(policy: ResearchMethodologyPolicy) -> dict[str, Any]:
    return {
        "version": STATISTICAL_CONFIDENCE_VERSION,
        "spec_version": SPEC_VERSION,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "safety_flags": _safety_flags_payload(StatisticalConfidenceSafetyFlags()),
        "policies": _policy_payload(policy),
        "reason_codes": [],
    }


def build_methodology_validation_report(
    windows: tuple[WalkForwardWindowResult, ...],
    *,
    metric_deltas: dict[str, list[Decimal]] | None = None,
    min_trades_per_window: int = 1,
    min_available_windows: int = 1,
    allow_overlapping_windows: bool = False,
    safety_flags: StatisticalConfidenceSafetyFlags | None = None,
) -> MethodologyValidationReport:
    """Run the full methodology policy suite on walk-forward window results."""
    policy = ResearchMethodologyPolicy(
        min_trades_per_window=min_trades_per_window,
        min_available_windows=min_available_windows,
        allow_overlapping_windows=allow_overlapping_windows,
    )
    policy_results = policy.apply(windows, metric_deltas=metric_deltas)
    return _build_methodology_validation_report(
        policy_results,
        safety_flags=safety_flags,
    )


class MethodologyValidationWriter:
    """Write methodology validation artifacts."""

    def __init__(
        self,
        *,
        output_dir: str | Path,
        indent: int | None = 2,
        sort_keys: bool = True,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.indent = indent
        self.sort_keys = sort_keys

    def _policy_path(self) -> Path:
        return self.output_dir / "research_methodology_policy.json"

    def _validation_path(self) -> Path:
        return self.output_dir / "research_methodology_validation.json"

    def _markdown_path(self) -> Path:
        return self.output_dir / "research_methodology_validation.md"

    def write_policy(
        self,
        policy: ResearchMethodologyPolicy,
        *,
        overwrite: bool = False,
    ) -> Path:
        """Write the research methodology policy JSON artifact."""
        path = self._policy_path()
        payload = _policy_artifact_payload(policy)
        _write_json_atomic(path, payload, indent=self.indent, sort_keys=self.sort_keys, overwrite=overwrite)
        return path

    def write_validation(
        self,
        report: MethodologyValidationReport,
        *,
        overwrite: bool = False,
    ) -> Path:
        """Write the methodology validation JSON report."""
        path = self._validation_path()
        payload = _methodology_validation_payload(report)
        _write_json_atomic(path, payload, indent=self.indent, sort_keys=self.sort_keys, overwrite=overwrite)
        return path

    def write_markdown(
        self,
        report: MethodologyValidationReport,
        *,
        overwrite: bool = False,
    ) -> Path:
        """Write the methodology validation Markdown report."""
        path = self._markdown_path()
        if path.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite {path}")
        text = _build_methodology_markdown(report)
        text = _redact_secrets(text)
        path.write_text(text, encoding="utf-8")
        return path

    def write_all(
        self,
        policy: ResearchMethodologyPolicy,
        report: MethodologyValidationReport,
        *,
        overwrite: bool = False,
    ) -> dict[str, Path]:
        """Write policy, validation JSON, and Markdown artifacts."""
        return {
            "policy": self.write_policy(policy, overwrite=overwrite),
            "validation": self.write_validation(report, overwrite=overwrite),
            "markdown": self.write_markdown(report, overwrite=overwrite),
        }


def _build_methodology_markdown(report: MethodologyValidationReport) -> str:
    lines = [
        "# Research Methodology Validation Report",
        "",
        f"- **Version:** `{report.version}`",
        f"- **Spec:** `{report.spec_version}`",
        f"- **Created:** `{report.created_at}`",
        f"- **Overall Passed:** `{report.overall_passed}`",
        f"- **Fingerprint:** `{report.fingerprint}`",
        "",
        "## Safety Flags",
        "",
        "| Flag | Value |",
        "|------|-------|",
    ]
    flags = report.safety_flags
    lines.extend(
        [
            f"| research_only | {flags.research_only} |",
            f"| execution_approval_granted | {flags.execution_approval_granted} |",
            f"| production_approval_granted | {flags.production_approval_granted} |",
            f"| live_trading_allowed | {flags.live_trading_allowed} |",
            f"| automatic_execution_allowed | {flags.automatic_execution_allowed} |",
            f"| human_approval_required | {flags.human_approval_required} |",
        ]
    )
    lines.extend(
        [
            "",
            "## Policy Results",
            "",
            "| Policy | Passed | Reason Codes |",
            "|--------|--------|--------------|",
        ]
    )
    for result in report.policy_results:
        codes = ", ".join(f"`{c}`" for c in result.reason_codes) or "_none_"
        lines.append(f"| {result.policy} | {result.passed} | {codes} |")

    lines.extend(
        [
            "",
            "## Reason Codes",
            "",
        ]
    )
    if report.reason_codes:
        for code in report.reason_codes:
            lines.append(f"- `{code}`")
    else:
        lines.append("- _none_")

    lines.extend(
        [
            "",
            "## Mandatory Notice",
            "",
            report.mandatory_notice,
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def write_all_methodology_artifacts(
    policy: ResearchMethodologyPolicy,
    report: MethodologyValidationReport,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> dict[str, Path]:
    """Convenience function to write all methodology validation artifacts."""
    writer = MethodologyValidationWriter(output_dir=output_dir)
    return writer.write_all(policy, report, overwrite=overwrite)
