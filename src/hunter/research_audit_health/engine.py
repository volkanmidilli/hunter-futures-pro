"""Research Audit Aggregate Health Engine.

This module implements a pure, deterministic, I/O-free aggregate health
evaluator for caller-provided in-memory artifact summaries. It does not import
filesystem, network, subprocess, or runtime execution modules.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from typing import Any

from .models import (
    HealthArtifactSummary,
    HealthConfig,
    HealthDataQuality,
    HealthFamilyRollup,
    HealthFinding,
    HealthInput,
    HealthReasonCode,
    HealthReport,
    HealthSafetyFlags,
    HealthScore,
    HealthSeverity,
    HealthState,
)


class HealthEngineError(Exception):
    """Base exception for the health engine."""


class ForbiddenPhraseLeakageError(HealthEngineError):
    """Raised when generated text contains forbidden readiness/runtime phrases."""


_FORBIDDEN_MODULES = frozenset(
    {
        "pathlib",
        "os",
        "subprocess",
        "socket",
        "urllib",
        "requests",
    }
)


_SOURCE_STATE_BLOCKING = frozenset(
    {"BLOCKED", "FAILED", "ERROR", "CRITICAL"}
)

_SOURCE_STATE_DEGRADED = frozenset(
    {"DEGRADED", "WARNING", "STALE", "STALE"}
)

_SOURCE_STATE_STALE = frozenset(
    {"STALE", "EXPIRED", "OUTDATED"}
)


def _raise_if_forbidden(text: str, terms: tuple[str, ...]) -> None:
    """Raise if any forbidden term appears in generated text."""
    lower = text.lower()
    for term in terms:
        if term in lower:
            raise ForbiddenPhraseLeakageError(
                f"Forbidden phrase detected in generated text: {term!r}"
            )


def _to_json_serializable(value: Any) -> Any:  # noqa: ANN401
    """Recursively convert model values into JSON-serializable primitives."""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, tuple):
        return [_to_json_serializable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_json_serializable(v) for k, v in value.items()}
    if hasattr(value, "value") and isinstance(value.value, str):
        return value.value
    if hasattr(value, "__dict__"):
        return _to_json_serializable(asdict(value))
    return str(value)


def _canonical_json_hash(obj: Any) -> str:  # noqa: ANN401
    """Return a stable SHA-256 hash of the canonical JSON representation."""
    serialized = json.dumps(
        _to_json_serializable(obj),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _next_finding_id(index: int) -> str:
    """Return a deterministic finding ID."""
    return f"finding-{index:06d}"


def _sort_findings(
    findings: list[HealthFinding],
) -> tuple[HealthFinding, ...]:
    """Return findings in a stable, deterministic order by finding ID."""
    return tuple(sorted(findings, key=lambda f: f.finding_id))


def _flatten_forbidden_scan(value: Any) -> list[str]:  # noqa: ANN401
    """Recursively flatten a mapping or sequence into strings for scanning."""
    result: list[str] = []
    if isinstance(value, str):
        result.append(value)
    elif isinstance(value, (list, tuple)):
        for item in value:
            result.extend(_flatten_forbidden_scan(item))
    elif isinstance(value, dict):
        for v in value.values():
            result.extend(_flatten_forbidden_scan(v))
    elif value is not None:
        result.append(str(value))
    return result


def _check_forbidden_phrases(
    summaries: tuple[HealthArtifactSummary, ...],
    findings: list[HealthFinding],
    config: HealthConfig,
) -> list[HealthFinding]:
    """Scan generated text and caller metadata for forbidden phrases.

    This check scans engine-generated text and caller-provided metadata
    values. It never inspects opaque ref values or external paths.
    """
    generated_parts: list[str] = []
    for summary in summaries:
        generated_parts.append(summary.artifact_id)
        generated_parts.append(summary.family)
        generated_parts.append(summary.source_state)
        if summary.mvp:
            generated_parts.append(summary.mvp)
        if summary.spec:
            generated_parts.append(summary.spec)
        if summary.produced_by:
            generated_parts.append(summary.produced_by)
        if summary.metadata is not None:
            generated_parts.extend(_flatten_forbidden_scan(summary.metadata))
    for finding in findings:
        generated_parts.append(finding.title)
        generated_parts.append(finding.description)
        if finding.evidence is not None:
            generated_parts.extend(_flatten_forbidden_scan(finding.evidence))
    combined_text = "\n".join(generated_parts)

    try:
        _raise_if_forbidden(combined_text, config.forbidden_terms)
    except ForbiddenPhraseLeakageError as exc:
        findings.append(
            HealthFinding(
                finding_id="finding-forbidden",
                rule_id="FORBIDDEN_PHRASE_LEAKAGE",
                family="",
                artifact_ids=(),
                severity=HealthSeverity.BLOCKING,
                reason_code=HealthReasonCode.FORBIDDEN_PHRASE_LEAKAGE,
                title="Forbidden phrase detected in generated text or metadata",
                description=str(exc),
                evidence={"detail": str(exc)},
            )
        )
    return findings


def _make_no_artifacts_finding(allow_empty: bool) -> HealthFinding:
    """Return the finding for an empty input set."""
    if allow_empty:
        severity = HealthSeverity.INFO
        state = HealthState.NOT_APPLICABLE
    else:
        severity = HealthSeverity.BLOCKING
        state = HealthState.BLOCKED
    return HealthFinding(
        finding_id="finding-000000",
        rule_id="NO_ARTIFACTS",
        family="",
        artifact_ids=(),
        severity=severity,
        reason_code=HealthReasonCode.NO_ARTIFACTS,
        title="No artifact summaries provided",
        description=(
            "The input contains no artifact summaries. "
            f"allow_empty={allow_empty} so the run is treated as {state.value}."
        ),
        evidence={"allow_empty": allow_empty},
    )


def _make_ok_finding() -> HealthFinding:
    """Return an informational OK finding when no issues are found."""
    return HealthFinding(
        finding_id="finding-000000",
        rule_id="OK",
        family="",
        artifact_ids=(),
        severity=HealthSeverity.INFO,
        reason_code=HealthReasonCode.OK,
        title="Aggregate health is OK",
        description="No blocking, warning, or stale findings were detected.",
        evidence=None,
    )


def _extract_spec_number(spec: str | None) -> int | None:
    """Extract a numeric SPEC number from e.g. 'SPEC-049'."""
    if not spec:
        return None
    prefix = "SPEC-"
    if not spec.startswith(prefix):
        return None
    try:
        return int(spec[len(prefix) :])
    except ValueError:
        return None


def _extract_mvp_number(mvp: str | None) -> int | None:
    """Extract a numeric MVP number from e.g. 'MVP-48'."""
    if not mvp:
        return None
    prefix = "MVP-"
    if not mvp.startswith(prefix):
        return None
    try:
        return int(mvp[len(prefix) :])
    except ValueError:
        return None


def _classify_source_state(state: str) -> HealthSeverity | None:
    """Map a source state string to a severity."""
    upper = state.upper()
    if upper in _SOURCE_STATE_BLOCKING:
        return HealthSeverity.BLOCKING
    if upper in _SOURCE_STATE_DEGRADED or upper in _SOURCE_STATE_STALE:
        return HealthSeverity.WARNING
    return None


def _check_summaries(
    summaries: tuple[HealthArtifactSummary, ...],
    config: HealthConfig,
) -> list[HealthFinding]:
    """Run all per-summary and cross-summary checks."""
    findings: list[HealthFinding] = []

    if not summaries:
        findings.append(_make_no_artifacts_finding(config.allow_empty))
        # Even with no summaries, report any missing required families so callers
        # see the full set of violations when empty input is disallowed or strict.
        present_families: set[str] = set()
        for family in config.required_families:
            if family not in present_families:
                severity = HealthSeverity.BLOCKING if config.strict else HealthSeverity.WARNING
                findings.append(
                    HealthFinding(
                        finding_id="",
                        rule_id="MISSING_REQUIRED_FAMILY",
                        family=family,
                        artifact_ids=(),
                        severity=severity,
                        reason_code=HealthReasonCode.MISSING_REQUIRED_FAMILY,
                        title="Missing required artifact family",
                        description=f"Required family {family!r} is not present in the input.",
                        evidence={"required_family": family},
                    )
                )
        return findings

    seen_ids: Counter[str] = Counter()

    for summary in summaries:
        seen_ids[summary.artifact_id] += 1

        # Semantic score consistency: a very low score with an OK state or a high
        # score with a BLOCKED state is treated as inconsistent input.
        if summary.score is not None:
            inconsistent = False
            if summary.source_state.upper() == "OK" and summary.score < 50.0:
                inconsistent = True
            if summary.source_state.upper() == "BLOCKED" and summary.score > 50.0:
                inconsistent = True
            if inconsistent:
                findings.append(
                    HealthFinding(
                        finding_id="",
                        rule_id="INCONSISTENT_SCORE_INPUT",
                        family=summary.family,
                        artifact_ids=(summary.artifact_id,),
                        severity=HealthSeverity.BLOCKING,
                        reason_code=HealthReasonCode.INCONSISTENT_SCORE_INPUT,
                        title="Inconsistent score input",
                        description=(
                            f"Artifact {summary.artifact_id!r} has source_state "
                            f"{summary.source_state!r} and score {summary.score}, which are "
                            "inconsistent."
                        ),
                        evidence={"score": summary.score, "source_state": summary.source_state},
                    )
                )

        # Source state classification.
        source_severity = _classify_source_state(summary.source_state)
        if source_severity == HealthSeverity.BLOCKING:
            findings.append(
                HealthFinding(
                    finding_id="",
                    rule_id="BLOCKING_SOURCE_STATE",
                    family=summary.family,
                    artifact_ids=(summary.artifact_id,),
                    severity=HealthSeverity.BLOCKING,
                    reason_code=HealthReasonCode.BLOCKING_SOURCE_STATE,
                    title="Blocking source state",
                    description=(
                        f"Artifact {summary.artifact_id!r} reports a blocking "
                        f"source state {summary.source_state!r}."
                    ),
                    evidence={"source_state": summary.source_state},
                )
            )
        elif source_severity == HealthSeverity.WARNING:
            # Stale states are classified as WARNING but get a distinct reason code.
            upper = summary.source_state.upper()
            if upper in _SOURCE_STATE_STALE:
                reason_code = HealthReasonCode.STALE_SOURCE_STATE
                title = "Stale source state"
                description = (
                    f"Artifact {summary.artifact_id!r} reports a stale source state "
                    f"{summary.source_state!r}."
                )
            else:
                reason_code = HealthReasonCode.DEGRADED_SOURCE_STATE
                title = "Degraded source state"
                description = (
                    f"Artifact {summary.artifact_id!r} reports a degraded source state "
                    f"{summary.source_state!r}."
                )
            findings.append(
                HealthFinding(
                    finding_id="",
                    rule_id=reason_code.value,
                    family=summary.family,
                    artifact_ids=(summary.artifact_id,),
                    severity=HealthSeverity.WARNING,
                    reason_code=reason_code,
                    title=title,
                    description=description,
                    evidence={"source_state": summary.source_state},
                )
            )

        # Family must be allowed when a list is configured.
        if (
            config.allowed_families
            and summary.family not in config.allowed_families
        ):
            severity = (
                HealthSeverity.BLOCKING
                if config.strict
                else HealthSeverity.WARNING
            )
            findings.append(
                HealthFinding(
                    finding_id="",
                    rule_id="UNSUPPORTED_ARTIFACT_FAMILY",
                    family=summary.family,
                    artifact_ids=(summary.artifact_id,),
                    severity=severity,
                    reason_code=HealthReasonCode.UNSUPPORTED_ARTIFACT_FAMILY,
                    title="Unsupported artifact family",
                    description=(
                        f"Artifact {summary.artifact_id!r} belongs to family "
                        f"{summary.family!r} which is not in the allowed list."
                    ),
                    evidence={
                        "family": summary.family,
                        "allowed_families": config.allowed_families,
                    },
                )
            )

        # MVP/spec mapping consistency (e.g. SPEC-049 for MVP-048).
        mvp_number = _extract_mvp_number(summary.mvp)
        spec_number = _extract_spec_number(summary.spec)
        if mvp_number is not None and spec_number is not None:
            if spec_number != mvp_number + 1:
                findings.append(
                    HealthFinding(
                        finding_id="",
                        rule_id="CONTRADICTORY_METADATA",
                        family=summary.family,
                        artifact_ids=(summary.artifact_id,),
                        severity=HealthSeverity.WARNING,
                        reason_code=HealthReasonCode.CONTRADICTORY_METADATA,
                        title="Contradictory MVP/spec metadata",
                        description=(
                            f"Artifact {summary.artifact_id!r} has mvp "
                            f"{summary.mvp!r} and spec {summary.spec!r}; "
                            f"expected SPEC-{mvp_number + 1}."
                        ),
                        evidence={
                            "mvp": summary.mvp,
                            "spec": summary.spec,
                            "expected_spec": f"SPEC-{mvp_number + 1}",
                        },
                    )
                )

        # Malformed metadata: generated_at must be a datetime if present.
        if summary.generated_at is not None and not isinstance(
            summary.generated_at, datetime
        ):
            findings.append(
                HealthFinding(
                    finding_id="",
                    rule_id="MALFORMED_METADATA",
                    family=summary.family,
                    artifact_ids=(summary.artifact_id,),
                    severity=HealthSeverity.BLOCKING,
                    reason_code=HealthReasonCode.MALFORMED_METADATA,
                    title="Malformed metadata",
                    description=(
                        f"Artifact {summary.artifact_id!r} has generated_at of "
                        f"type {type(summary.generated_at).__name__}, expected datetime."
                    ),
                    evidence={"generated_at_type": type(summary.generated_at).__name__},
                )
            )

    # Duplicate artifact IDs.
    duplicate_ids = {aid for aid, count in seen_ids.items() if count > 1}
    for dup_id in sorted(duplicate_ids):
        findings.append(
            HealthFinding(
                finding_id="",
                rule_id="DUPLICATE_ARTIFACT_ID",
                family="",
                artifact_ids=(dup_id,),
                severity=HealthSeverity.BLOCKING,
                reason_code=HealthReasonCode.DUPLICATE_ARTIFACT_ID,
                title="Duplicate artifact ID",
                description=(
                    f"Artifact ID {dup_id!r} appears more than once in the input."
                ),
                evidence={"count": seen_ids[dup_id]},
            )
        )

    # Missing required families.
    present_families = frozenset(s.family for s in summaries)
    for required_family in sorted(config.required_families):
        if required_family not in present_families:
            severity = (
                HealthSeverity.BLOCKING
                if config.strict
                else HealthSeverity.WARNING
            )
            findings.append(
                HealthFinding(
                    finding_id="",
                    rule_id="MISSING_REQUIRED_FAMILY",
                    family=required_family,
                    artifact_ids=(),
                    severity=severity,
                    reason_code=HealthReasonCode.MISSING_REQUIRED_FAMILY,
                    title="Missing required family",
                    description=(
                        f"Required family {required_family!r} is not present in input."
                    ),
                    evidence={"required_family": required_family},
                )
            )

    return findings


def _compute_family_rollups(
    summaries: tuple[HealthArtifactSummary, ...],
    findings: tuple[HealthFinding, ...],
    config: HealthConfig,
) -> tuple[HealthFamilyRollup, ...]:
    """Compute per-family health rollups."""
    families = sorted(frozenset(s.family for s in summaries))
    family_to_findings: dict[str, list[HealthFinding]] = {f: [] for f in families}
    for finding in findings:
        if finding.family in family_to_findings:
            family_to_findings[finding.family].append(finding)

    rollups: list[HealthFamilyRollup] = []
    for family in families:
        family_findings = family_to_findings[family]
        counts = Counter(f.reason_code.value for f in family_findings)
        # Add OK count for the OK reason code if present, otherwise zero.
        counts.setdefault(HealthReasonCode.OK.value, 0)
        blocking = sum(
            1 for f in family_findings if f.severity == HealthSeverity.BLOCKING
        )
        warning = sum(
            1 for f in family_findings if f.severity == HealthSeverity.WARNING
        )
        info = sum(
            1 for f in family_findings if f.severity == HealthSeverity.INFO
        )
        if blocking:
            state = HealthState.BLOCKED
        elif warning or info:
            state = HealthState.DEGRADED
        else:
            state = HealthState.OK

        penalty = sum(
            config.severity_penalties[f.severity] for f in family_findings
        )
        raw_score = 100 - penalty
        score_value = max(0.0, min(100.0, float(raw_score)))
        weight = max(
            1.0,
            float(
                sum(config.severity_weights[f.severity] for f in family_findings)
            ),
        )
        score = HealthScore(
            value=score_value,
            weight=weight,
            contributing_families=(family,),
            breakdown={
                "blocking": blocking,
                "warning": warning,
                "info": info,
                "penalty": penalty,
            },
        )
        summary_parts = [f"family={family}"]
        if state == HealthState.OK:
            summary_parts.append("health=OK")
        else:
            summary_parts.append(f"state={state.value}")
            summary_parts.append(f"findings={len(family_findings)}")
        rollups.append(
            HealthFamilyRollup(
                family=family,
                state=state,
                score=score,
                finding_count=len(family_findings),
                reason_code_counts=dict(counts),
                summary="; ".join(summary_parts),
            )
        )
    return tuple(rollups)


def _compute_aggregate_score(
    family_rollups: tuple[HealthFamilyRollup, ...],
) -> HealthScore:
    """Compute a severity-weighted aggregate score from family rollups."""
    if not family_rollups:
        return HealthScore(
            value=0.0,
            weight=0.0,
            contributing_families=(),
            breakdown={"empty": True},
        )
    total_weight = sum(rollup.score.weight for rollup in family_rollups)
    if total_weight <= 0:
        return HealthScore(
            value=0.0,
            weight=0.0,
            contributing_families=(),
            breakdown={"zero_weight": True},
        )
    weighted_sum = sum(
        rollup.score.value * rollup.score.weight for rollup in family_rollups
    )
    value = max(0.0, min(100.0, weighted_sum / total_weight))
    return HealthScore(
        value=value,
        weight=total_weight,
        contributing_families=tuple(r.family for r in family_rollups),
        breakdown={
            "weighted_sum": weighted_sum,
            "total_weight": total_weight,
        },
    )


def _compute_aggregate_state(
    findings: tuple[HealthFinding, ...],
    allow_empty: bool,
    summaries: tuple[HealthArtifactSummary, ...],
) -> HealthState:
    """Determine the aggregate health state."""
    if not summaries and allow_empty:
        return HealthState.NOT_APPLICABLE
    if any(f.severity == HealthSeverity.BLOCKING for f in findings):
        return HealthState.BLOCKED
    if any(f.severity == HealthSeverity.WARNING for f in findings):
        return HealthState.DEGRADED
    if any(f.severity == HealthSeverity.INFO for f in findings) and not any(
        f.reason_code == HealthReasonCode.OK for f in findings
    ):
        return HealthState.DEGRADED
    return HealthState.OK


def evaluate_research_audit_health(input_obj: HealthInput) -> HealthReport:
    """Evaluate aggregate health for caller-provided artifact summaries.

    This function is pure and deterministic. It performs no filesystem, network,
    or runtime actions. All artifact references are treated as opaque strings.
    """
    config = input_obj.config
    summaries = tuple(sorted(input_obj.summaries, key=lambda s: s.artifact_id))
    metadata = input_obj.metadata

    checks_performed = 0
    findings: list[HealthFinding] = _check_summaries(summaries, config)
    checks_performed += 5  # duplicate, source-state, family, mvp/spec, malformed checks

    # Assign stable finding IDs before forbidden-phrase scan.
    findings = [
        HealthFinding(
            finding_id=_next_finding_id(idx),
            rule_id=f.rule_id,
            family=f.family,
            artifact_ids=f.artifact_ids,
            severity=f.severity,
            reason_code=f.reason_code,
            title=f.title,
            description=f.description,
            evidence=f.evidence,
        )
        for idx, f in enumerate(findings, start=1)
    ]
    findings = list(_sort_findings(findings))

    # Final forbidden-phrase check on generated text.
    findings = _check_forbidden_phrases(summaries, findings, config)
    checks_performed += 1

    # Add OK finding if the aggregate state is OK so reason-code counts are explicit.
    if not any(f.severity == HealthSeverity.BLOCKING for f in findings) and not any(
        f.severity == HealthSeverity.WARNING for f in findings
    ):
        ok_finding = _make_ok_finding()
        findings = [ok_finding] + findings
        findings = list(_sort_findings(findings))

    findings_tuple = tuple(findings)

    family_rollups = _compute_family_rollups(summaries, findings_tuple, config)
    aggregate_score = _compute_aggregate_score(family_rollups)
    state = _compute_aggregate_state(
        findings_tuple, config.allow_empty, summaries
    )

    # Adjust aggregate score if empty/NOT_APPLICABLE to avoid implying health.
    if state == HealthState.NOT_APPLICABLE:
        aggregate_score = HealthScore(
            value=0.0,
            weight=0.0,
            contributing_families=(),
            breakdown={"not_applicable": True},
        )

    # Count findings by severity.
    blocking_count = sum(1 for f in findings_tuple if f.severity == HealthSeverity.BLOCKING)
    warning_count = sum(1 for f in findings_tuple if f.severity == HealthSeverity.WARNING)
    info_count = sum(1 for f in findings_tuple if f.severity == HealthSeverity.INFO)

    # Reason-code counts, sorted by reason code.
    reason_code_counts = dict(
        sorted(
            Counter(f.reason_code.value for f in findings_tuple).items(),
            key=lambda item: item[0],
        )
    )
    # Ensure OK is present in the count map even when zero.
    reason_code_counts.setdefault(HealthReasonCode.OK.value, 0)
    # Re-sort after default.
    reason_code_counts = dict(sorted(reason_code_counts.items(), key=lambda item: item[0]))

    data_quality = HealthDataQuality(
        summary_count=len(summaries),
        family_count=len(frozenset(s.family for s in summaries)),
        finding_count=len(findings_tuple),
        blocking_count=blocking_count,
        warning_count=warning_count,
        info_count=info_count,
        reason_code_counts=reason_code_counts,
        checks_performed=checks_performed,
        skipped_count=0,
    )

    safety_flags = HealthSafetyFlags()

    # Deterministic report ID derived from canonical JSON of inputs and outputs.
    report_id = _canonical_json_hash(
        {
            "summaries": summaries,
            "config": config,
            "findings": findings_tuple,
            "family_rollups": family_rollups,
            "state": state,
            "aggregate_score": aggregate_score,
            "reason_code_counts": reason_code_counts,
            "data_quality": data_quality,
        }
    )

    return HealthReport(
        report_id=report_id,
        state=state,
        aggregate_score=aggregate_score,
        family_rollups=family_rollups,
        findings=findings_tuple,
        reason_code_counts=reason_code_counts,
        data_quality=data_quality,
        safety_flags=safety_flags,
        metadata=metadata,
    )


def validate_no_forbidden_modules() -> None:
    """Raise if the engine module imported any forbidden I/O or runtime modules.

    This checks the engine module's own global namespace, not the entire
    sys.modules dictionary, because pytest and other tooling may legitimately
    import filesystem or network modules for test orchestration.
    """
    import sys

    from . import engine as engine_module

    imported = frozenset(engine_module.__dict__.keys())
    intersection = imported & _FORBIDDEN_MODULES
    if intersection:
        raise HealthEngineError(
            f"Forbidden modules imported in the engine scope: {sorted(intersection)}"
        )
