"""Cross-Artifact Consistency Engine.

This module implements a pure, deterministic, I/O-free consistency evaluator
for caller-provided in-memory artifact summaries and opaque references. It does
not import filesystem, network, subprocess, or runtime execution modules.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict
from typing import Any

from .models import (
    ArtifactRef,
    ArtifactSummary,
    ConsistencyDataQuality,
    ConsistencyFinding,
    ConsistencyReasonCode,
    ConsistencyReport,
    ConsistencySafetyFlags,
    ConsistencySeverity,
    ConsistencyState,
    CrossArtifactConsistencyConfig,
    CrossArtifactConsistencyInput,
)


class ConsistencyEngineError(Exception):
    """Base exception for the consistency engine."""


class ForbiddenPhraseLeakageError(ConsistencyEngineError):
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


def _raise_if_forbidden(text: str, terms: tuple[str, ...]) -> None:
    """Raise if any forbidden term appears in generated text.

    This check is intentionally narrow: it scans only the generated
    human-audit text produced by the engine itself, never external refs or
    opaque values. It does not strip negations or attempt semantic parsing.
    """
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


def _extract_spec_number(spec: str | None) -> int | None:
    """Extract a numeric SPEC number from e.g. 'SPEC-048'."""
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
    """Extract a numeric MVP number from e.g. 'MVP-47'."""
    if not mvp:
        return None
    prefix = "MVP-"
    if not mvp.startswith(prefix):
        return None
    try:
        return int(mvp[len(prefix) :])
    except ValueError:
        return None


def _build_index(artifacts: tuple[ArtifactSummary, ...]) -> dict[str, ArtifactSummary]:
    """Build a deterministic mapping from artifact_id to artifact summary."""
    return {a.artifact_id: a for a in sorted(artifacts, key=lambda a: a.artifact_id)}


def _sort_findings(
    findings: list[ConsistencyFinding],
) -> tuple[ConsistencyFinding, ...]:
    """Return findings in a stable, deterministic order by finding ID."""
    return tuple(sorted(findings, key=lambda f: f.finding_id))


def _make_no_artifacts_finding(allow_empty: bool) -> ConsistencyFinding:
    """Return the finding for an empty input set."""
    if allow_empty:
        severity = ConsistencySeverity.INFO
        state = ConsistencyState.NOT_APPLICABLE
    else:
        severity = ConsistencySeverity.BLOCKING
        state = ConsistencyState.BLOCKED
    return ConsistencyFinding(
        finding_id="finding-000000",
        rule_id="NO_ARTIFACTS",
        artifact_ids=(),
        severity=severity,
        reason_code=ConsistencyReasonCode.NO_ARTIFACTS,
        title="No artifact summaries provided",
        description=(
            "The input contains no artifact summaries. "
            f"allow_empty={allow_empty} so the run is treated as {state.value}."
        ),
        evidence={"allow_empty": allow_empty},
    )


def _check_forbidden_phrases(
    artifacts: tuple[ArtifactSummary, ...],
    findings: list[ConsistencyFinding],
    config: CrossArtifactConsistencyConfig,
) -> list[ConsistencyFinding]:
    """Scan generated text and caller metadata for forbidden phrases.

    This check scans both the engine-generated text and the caller-provided
    metadata values. It never inspects opaque_ref values or external paths.
    """
    generated_parts: list[str] = []
    for artifact in artifacts:
        generated_parts.append(artifact.artifact_id)
        generated_parts.append(artifact.artifact_kind)
        generated_parts.append(artifact.artifact_state)
        if artifact.mvp:
            generated_parts.append(artifact.mvp)
        if artifact.spec:
            generated_parts.append(artifact.spec)
        if artifact.produced_by:
            generated_parts.append(artifact.produced_by)
        if artifact.metadata is not None:
            generated_parts.extend(_flatten_forbidden_scan(artifact.metadata))
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
            ConsistencyFinding(
                finding_id="finding-forbidden",
                rule_id="FORBIDDEN_PHRASE_LEAKAGE",
                artifact_ids=(),
                severity=ConsistencySeverity.BLOCKING,
                reason_code=ConsistencyReasonCode.FORBIDDEN_PHRASE_LEAKAGE,
                title="Forbidden phrase detected in generated text or metadata",
                description=str(exc),
                evidence={"detail": str(exc)},
            )
        )
    return findings


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


def evaluate_cross_artifact_consistency(
    input_obj: CrossArtifactConsistencyInput,
) -> ConsistencyReport:
    """Evaluate cross-artifact consistency for caller-provided summaries.

    This function is pure and deterministic. It performs no filesystem, network,
    or runtime actions. All artifact references are treated as opaque strings.
    """
    config = input_obj.config
    artifacts = tuple(
        sorted(input_obj.artifacts, key=lambda a: a.artifact_id)
    )
    metadata = input_obj.metadata

    findings: list[ConsistencyFinding] = []
    checks_performed = 0

    if not artifacts:
        findings.append(_make_no_artifacts_finding(config.allow_empty))
        checks_performed += 1
    else:
        artifact_index = _build_index(artifacts)
        artifact_ids = frozenset(artifact_index.keys())
        seen_ids: Counter[str] = Counter()

        # Check 1: duplicate artifact IDs and per-artifact metadata checks.
        for artifact in artifacts:
            seen_ids[artifact.artifact_id] += 1

            # Content length must be non-negative if present.
            if artifact.content_length is not None and artifact.content_length < 0:
                findings.append(
                    ConsistencyFinding(
                        finding_id="",
                        rule_id="MALFORMED_METADATA",
                        artifact_ids=(artifact.artifact_id,),
                        severity=ConsistencySeverity.BLOCKING,
                        reason_code=ConsistencyReasonCode.MALFORMED_METADATA,
                        title="Malformed content length",
                        description=(
                            f"Artifact {artifact.artifact_id!r} has a negative "
                            f"content_length ({artifact.content_length})."
                        ),
                        evidence={"content_length": artifact.content_length},
                    )
                )

            # Hash/length must be present together or absent together.
            if (artifact.content_hash is None) != (artifact.content_length is None):
                findings.append(
                    ConsistencyFinding(
                        finding_id="",
                        rule_id="HASH_LENGTH_MISMATCH",
                        artifact_ids=(artifact.artifact_id,),
                        severity=ConsistencySeverity.BLOCKING,
                        reason_code=ConsistencyReasonCode.HASH_LENGTH_MISMATCH,
                        title="Hash/length metadata mismatch",
                        description=(
                            f"Artifact {artifact.artifact_id!r} has content_hash "
                            f"and content_length that are not both present or both absent."
                        ),
                        evidence={
                            "content_hash_present": artifact.content_hash is not None,
                            "content_length_present": artifact.content_length is not None,
                        },
                    )
                )

            # Artifact kind must be supported when a list is configured.
            if (
                config.allowed_artifact_kinds
                and artifact.artifact_kind not in config.allowed_artifact_kinds
            ):
                findings.append(
                    ConsistencyFinding(
                        finding_id="",
                        rule_id="UNSUPPORTED_ARTIFACT_KIND",
                        artifact_ids=(artifact.artifact_id,),
                        severity=ConsistencySeverity.BLOCKING,
                        reason_code=ConsistencyReasonCode.UNSUPPORTED_ARTIFACT_KIND,
                        title="Unsupported artifact kind",
                        description=(
                            f"Artifact {artifact.artifact_id!r} has unsupported "
                            f"kind {artifact.artifact_kind!r}."
                        ),
                        evidence={
                            "artifact_kind": artifact.artifact_kind,
                            "allowed_artifact_kinds": config.allowed_artifact_kinds,
                        },
                    )
                )

            # MVP/spec mapping consistency (e.g. SPEC-048 for MVP-47).
            mvp_number = _extract_mvp_number(artifact.mvp)
            spec_number = _extract_spec_number(artifact.spec)
            if mvp_number is not None and spec_number is not None:
                if spec_number != mvp_number + 1:
                    findings.append(
                        ConsistencyFinding(
                            finding_id="",
                            rule_id="MVP_SPEC_MISMATCH",
                            artifact_ids=(artifact.artifact_id,),
                            severity=ConsistencySeverity.WARNING,
                            reason_code=ConsistencyReasonCode.MVP_SPEC_MISMATCH,
                            title="MVP/spec metadata mismatch",
                            description=(
                                f"Artifact {artifact.artifact_id!r} has mvp "
                                f"{artifact.mvp!r} and spec {artifact.spec!r}; "
                                f"expected SPEC-{mvp_number + 1}."
                            ),
                            evidence={
                                "mvp": artifact.mvp,
                                "spec": artifact.spec,
                                "expected_spec": f"SPEC-{mvp_number + 1}",
                            },
                        )
                    )

        duplicate_ids = {aid for aid, count in seen_ids.items() if count > 1}
        for dup_id in sorted(duplicate_ids):
            findings.append(
                ConsistencyFinding(
                    finding_id="",
                    rule_id="DUPLICATE_ARTIFACT_ID",
                    artifact_ids=(dup_id,),
                    severity=ConsistencySeverity.BLOCKING,
                    reason_code=ConsistencyReasonCode.DUPLICATE_ARTIFACT_ID,
                    title="Duplicate artifact ID",
                    description=(
                        f"Artifact ID {dup_id!r} appears more than once in the input."
                    ),
                    evidence={"count": seen_ids[dup_id]},
                )
            )
        checks_performed += 1

        # Check 2: upstream/downstream references.
        for artifact in artifacts:
            for upstream_id in sorted(artifact.upstream_ids):
                if upstream_id not in artifact_ids:
                    severity = (
                        ConsistencySeverity.BLOCKING
                        if config.strict
                        else ConsistencySeverity.WARNING
                    )
                    findings.append(
                        ConsistencyFinding(
                            finding_id="",
                            rule_id="MISSING_UPSTREAM_REFERENCE",
                            artifact_ids=(artifact.artifact_id, upstream_id),
                            severity=severity,
                            reason_code=ConsistencyReasonCode.MISSING_UPSTREAM_REFERENCE,
                            title="Missing upstream reference",
                            description=(
                                f"Artifact {artifact.artifact_id!r} references "
                                f"upstream {upstream_id!r} which is not present."
                            ),
                            evidence={
                                "artifact_id": artifact.artifact_id,
                                "upstream_id": upstream_id,
                                "strict": config.strict,
                            },
                        )
                    )
                else:
                    upstream = artifact_index[upstream_id]
                    # State transition: upstream blocked but downstream ready.
                    if (
                        upstream.artifact_state.upper() in {"BLOCKED", "FAILED"}
                        and artifact.artifact_state.upper() in {"READY", "OK"}
                    ):
                        findings.append(
                            ConsistencyFinding(
                                finding_id="",
                                rule_id="INCONSISTENT_STATE_TRANSITION",
                                artifact_ids=(upstream_id, artifact.artifact_id),
                                severity=ConsistencySeverity.BLOCKING,
                                reason_code=ConsistencyReasonCode.INCONSISTENT_STATE_TRANSITION,
                                title="Inconsistent state transition",
                                description=(
                                    f"Upstream {upstream_id!r} is "
                                    f"{upstream.artifact_state!r} but downstream "
                                    f"{artifact.artifact_id!r} is "
                                    f"{artifact.artifact_state!r}."
                                ),
                                evidence={
                                    "upstream_id": upstream_id,
                                    "upstream_state": upstream.artifact_state,
                                    "downstream_id": artifact.artifact_id,
                                    "downstream_state": artifact.artifact_state,
                                },
                            )
                        )

            for downstream_id in sorted(artifact.downstream_ids):
                if downstream_id not in artifact_ids:
                    findings.append(
                        ConsistencyFinding(
                            finding_id="",
                            rule_id="ORPHAN_DOWNSTREAM_REFERENCE",
                            artifact_ids=(artifact.artifact_id, downstream_id),
                            severity=ConsistencySeverity.WARNING,
                            reason_code=ConsistencyReasonCode.ORPHAN_DOWNSTREAM_REFERENCE,
                            title="Orphan downstream reference",
                            description=(
                                f"Artifact {artifact.artifact_id!r} references "
                                f"downstream {downstream_id!r} which is not present."
                            ),
                            evidence={
                                "artifact_id": artifact.artifact_id,
                                "downstream_id": downstream_id,
                            },
                        )
                    )

            # Link direction contradictions: if A is upstream of B, B should list A as downstream.
            for upstream_id in sorted(artifact.upstream_ids):
                if upstream_id in artifact_ids:
                    upstream = artifact_index[upstream_id]
                    if artifact.artifact_id not in upstream.downstream_ids:
                        findings.append(
                            ConsistencyFinding(
                                finding_id="",
                                rule_id="CONTRADICTORY_METADATA",
                                artifact_ids=(artifact.artifact_id, upstream_id),
                                severity=ConsistencySeverity.WARNING,
                                reason_code=ConsistencyReasonCode.CONTRADICTORY_METADATA,
                                title="Contradictory upstream/downstream link",
                                description=(
                                    f"Artifact {artifact.artifact_id!r} lists "
                                    f"{upstream_id!r} as upstream, but "
                                    f"{upstream_id!r} does not list "
                                    f"{artifact.artifact_id!r} as downstream."
                                ),
                                evidence={
                                    "artifact_id": artifact.artifact_id,
                                    "upstream_id": upstream_id,
                                },
                            )
                        )

            # If A lists B as downstream, B should list A as upstream.
            for downstream_id in sorted(artifact.downstream_ids):
                if downstream_id in artifact_ids:
                    downstream = artifact_index[downstream_id]
                    if artifact.artifact_id not in downstream.upstream_ids:
                        findings.append(
                            ConsistencyFinding(
                                finding_id="",
                                rule_id="CONTRADICTORY_METADATA",
                                artifact_ids=(artifact.artifact_id, downstream_id),
                                severity=ConsistencySeverity.WARNING,
                                reason_code=ConsistencyReasonCode.CONTRADICTORY_METADATA,
                                title="Contradictory downstream/upstream link",
                                description=(
                                    f"Artifact {artifact.artifact_id!r} lists "
                                    f"{downstream_id!r} as downstream, but "
                                    f"{downstream_id!r} does not list "
                                    f"{artifact.artifact_id!r} as upstream."
                                ),
                                evidence={
                                    "artifact_id": artifact.artifact_id,
                                    "downstream_id": downstream_id,
                                },
                            )
                        )
        checks_performed += 1

        # Check 3: semantic family-specific checks using metadata only.
        queue_ids: set[str] = set()
        bundle_ids: set[str] = set()
        export_ids: set[str] = set()
        for artifact in artifacts:
            if artifact.artifact_kind == "human_review_queue":
                queue_ids.add(artifact.artifact_id)
                queue_ids.update(artifact.review_ids)
            if artifact.artifact_kind == "audit_bundle":
                bundle_ids.add(artifact.artifact_id)
            if artifact.artifact_kind == "audit_bundle_export":
                export_ids.add(artifact.artifact_id)

        for artifact in artifacts:
            # Decision log vs queue mismatch.
            if artifact.artifact_kind == "human_review_decision_log":
                referenced_ids = set(artifact.decision_ids)
                missing = referenced_ids - queue_ids
                if missing:
                    findings.append(
                        ConsistencyFinding(
                            finding_id="",
                            rule_id="DECISION_LOG_QUEUE_MISMATCH",
                            artifact_ids=(artifact.artifact_id,) + tuple(sorted(missing)),
                            severity=ConsistencySeverity.WARNING,
                            reason_code=ConsistencyReasonCode.DECISION_LOG_QUEUE_MISMATCH,
                            title="Decision log vs queue mismatch",
                            description=(
                                f"Decision log {artifact.artifact_id!r} references "
                                f"queue IDs that are not present: {sorted(missing)}."
                            ),
                            evidence={
                                "artifact_id": artifact.artifact_id,
                                "missing_ids": sorted(missing),
                            },
                        )
                    )

            # Audit bundle export vs bundle mismatch.
            if artifact.artifact_kind == "audit_bundle_export":
                referenced_bundles = set(artifact.report_ids)
                missing = referenced_bundles - bundle_ids
                if missing:
                    findings.append(
                        ConsistencyFinding(
                            finding_id="",
                            rule_id="AUDIT_BUNDLE_EXPORT_MISMATCH",
                            artifact_ids=(artifact.artifact_id,) + tuple(sorted(missing)),
                            severity=ConsistencySeverity.WARNING,
                            reason_code=ConsistencyReasonCode.AUDIT_BUNDLE_EXPORT_MISMATCH,
                            title="Audit bundle export mismatch",
                            description=(
                                f"Audit bundle export {artifact.artifact_id!r} references "
                                f"bundle IDs that are not present: {sorted(missing)}."
                            ),
                            evidence={
                                "artifact_id": artifact.artifact_id,
                                "missing_bundle_ids": sorted(missing),
                            },
                        )
                    )

            # Verification report vs export mismatch.
            if artifact.artifact_kind == "audit_bundle_export_verification":
                referenced_exports = set(artifact.report_ids)
                missing = referenced_exports - export_ids
                if missing:
                    findings.append(
                        ConsistencyFinding(
                            finding_id="",
                            rule_id="VERIFICATION_EXPORT_MISMATCH",
                            artifact_ids=(artifact.artifact_id,) + tuple(sorted(missing)),
                            severity=ConsistencySeverity.WARNING,
                            reason_code=ConsistencyReasonCode.VERIFICATION_EXPORT_MISMATCH,
                            title="Verification export mismatch",
                            description=(
                                f"Verification report {artifact.artifact_id!r} references "
                                f"export IDs that are not present: {sorted(missing)}."
                            ),
                            evidence={
                                "artifact_id": artifact.artifact_id,
                                "missing_export_ids": sorted(missing),
                            },
                        )
                    )
        checks_performed += 1

        # Check 4: optional stale project-memory warning.
        if config.check_stale_project_memory and metadata:
            version = metadata.get("version")
            tags = metadata.get("tags")
            if version and tags and isinstance(tags, (list, tuple, set)):
                latest_tag = None
                for tag in sorted(tags, reverse=True):
                    if isinstance(tag, str) and tag.startswith("v0.") and tag.endswith("-dev"):
                        latest_tag = tag
                        break
                expected_version = latest_tag[1:] if latest_tag else None
                if expected_version and version != expected_version:
                    findings.append(
                        ConsistencyFinding(
                            finding_id="",
                            rule_id="STALE_PROJECT_MEMORY",
                            artifact_ids=(),
                            severity=ConsistencySeverity.WARNING,
                            reason_code=ConsistencyReasonCode.STALE_PROJECT_MEMORY,
                            title="Stale project-memory marker",
                            description=(
                                f"Version metadata {version!r} does not match the "
                                f"latest dev tag {latest_tag!r}."
                            ),
                            evidence={
                                "version": version,
                                "latest_tag": latest_tag,
                                "expected_version": expected_version,
                            },
                        )
                    )
        checks_performed += 1

    # Assign stable finding IDs.
    findings = [
        ConsistencyFinding(
            finding_id=_next_finding_id(idx),
            rule_id=f.rule_id,
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
    findings = _check_forbidden_phrases(artifacts, findings, config)

    # Compute aggregate state.
    if not artifacts and config.allow_empty:
        state = ConsistencyState.NOT_APPLICABLE
    elif any(f.severity == ConsistencySeverity.BLOCKING for f in findings):
        state = ConsistencyState.BLOCKED
    elif any(
        f.severity in {ConsistencySeverity.WARNING, ConsistencySeverity.INFO}
        for f in findings
    ):
        state = ConsistencyState.DEGRADED
    else:
        state = ConsistencyState.OK

    # Data quality counters.
    blocking_count = sum(1 for f in findings if f.severity == ConsistencySeverity.BLOCKING)
    warning_count = sum(1 for f in findings if f.severity == ConsistencySeverity.WARNING)
    info_count = sum(1 for f in findings if f.severity == ConsistencySeverity.INFO)
    duplicate_id_count = sum(
        1 for f in findings if f.reason_code == ConsistencyReasonCode.DUPLICATE_ARTIFACT_ID
    )
    missing_upstream_count = sum(
        1 for f in findings if f.reason_code == ConsistencyReasonCode.MISSING_UPSTREAM_REFERENCE
    )
    orphan_downstream_count = sum(
        1 for f in findings if f.reason_code == ConsistencyReasonCode.ORPHAN_DOWNSTREAM_REFERENCE
    )
    malformed_metadata_count = sum(
        1 for f in findings if f.reason_code == ConsistencyReasonCode.MALFORMED_METADATA
    )
    unsupported_kind_count = sum(
        1 for f in findings if f.reason_code == ConsistencyReasonCode.UNSUPPORTED_ARTIFACT_KIND
    )

    data_quality = ConsistencyDataQuality(
        artifact_count=len(artifacts),
        finding_count=len(findings),
        blocking_count=blocking_count,
        warning_count=warning_count,
        info_count=info_count,
        duplicate_id_count=duplicate_id_count,
        missing_upstream_count=missing_upstream_count,
        orphan_downstream_count=orphan_downstream_count,
        malformed_metadata_count=malformed_metadata_count,
        unsupported_kind_count=unsupported_kind_count,
        checks_performed=checks_performed,
    )

    reason_codes = tuple(
        sorted(
            frozenset(f.reason_code for f in findings),
            key=lambda rc: rc.value,
        )
    )

    safety_flags = ConsistencySafetyFlags()

    # Deterministic report ID derived from canonical JSON of inputs and findings.
    report_id = _canonical_json_hash(
        {
            "artifacts": artifacts,
            "config": config,
            "findings": findings,
            "state": state,
            "reason_codes": reason_codes,
        }
    )

    return ConsistencyReport(
        report_id=report_id,
        state=state,
        findings=tuple(findings),
        reason_codes=reason_codes,
        data_quality=data_quality,
        safety_flags=safety_flags,
        artifacts=artifacts,
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
        raise ConsistencyEngineError(
            f"Forbidden modules imported in the engine scope: {sorted(intersection)}"
        )
