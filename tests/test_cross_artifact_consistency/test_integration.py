"""Integration tests for the Cross-Artifact Consistency Engine."""

from __future__ import annotations

import json

from src.hunter.cross_artifact_consistency import (
    consistency_report_to_dict,
    consistency_report_to_json,
    consistency_report_to_markdown,
    evaluate_cross_artifact_consistency,
)
from src.hunter.cross_artifact_consistency.engine import (
    validate_no_forbidden_modules as validate_no_forbidden_engine_modules,
)
from src.hunter.cross_artifact_consistency.models import (
    ArtifactRef,
    ArtifactSummary,
    ConsistencyReasonCode,
    ConsistencySeverity,
    ConsistencyState,
    CrossArtifactConsistencyConfig,
    CrossArtifactConsistencyInput,
    DEFAULT_FORBIDDEN_TERMS,
)
from src.hunter.cross_artifact_consistency.writer import (
    validate_no_forbidden_modules as validate_no_forbidden_writer_modules,
)


def _config(**kwargs) -> CrossArtifactConsistencyConfig:
    return CrossArtifactConsistencyConfig(**kwargs)


def _input(
    *artifacts: ArtifactSummary,
    metadata: dict[str, object] | None = None,
    **config_kwargs,
) -> CrossArtifactConsistencyInput:
    return CrossArtifactConsistencyInput(
        config=_config(**config_kwargs),
        artifacts=tuple(artifacts),
        metadata=metadata,
    )


def _artifact(
    artifact_id: str,
    kind: str = "observation",
    state: str = "READY",
    upstream: tuple[str, ...] = (),
    downstream: tuple[str, ...] = (),
    decision_ids: tuple[str, ...] = (),
    review_ids: tuple[str, ...] = (),
    report_ids: tuple[str, ...] = (),
    content_hash: str | None = None,
    content_length: int | None = None,
    mvp: str | None = None,
    spec: str | None = None,
    produced_by: str | None = None,
    opaque_value: str = "ref://opaque",
) -> ArtifactSummary:
    return ArtifactSummary(
        artifact_id=artifact_id,
        artifact_kind=kind,
        artifact_state=state,
        upstream_ids=upstream,
        downstream_ids=downstream,
        decision_ids=decision_ids,
        review_ids=review_ids,
        report_ids=report_ids,
        content_hash=content_hash,
        content_length=content_length,
        mvp=mvp,
        spec=spec,
        produced_by=produced_by,
        opaque_ref=ArtifactRef(
            ref_id=artifact_id,
            ref_kind="opaque",
            opaque_value=opaque_value,
        ),
    )


# ---------------------------------------------------------------------------
# OK path
# ---------------------------------------------------------------------------


def test_ok_coherent_chain() -> None:
    """A coherent chain of observation -> review -> audit bundle should be OK."""
    observation = _artifact(
        "observation-1",
        kind="observation",
        state="READY",
        downstream=("review-1",),
        content_hash="abc",
        content_length=3,
        mvp="MVP-47",
        spec="SPEC-048",
    )
    review = _artifact(
        "review-1",
        kind="review_record",
        state="READY",
        upstream=("observation-1",),
        downstream=("bundle-1",),
        content_hash="def",
        content_length=3,
        mvp="MVP-47",
        spec="SPEC-048",
    )
    bundle = _artifact(
        "bundle-1",
        kind="audit_bundle",
        state="READY",
        upstream=("review-1",),
        content_hash="ghi",
        content_length=3,
        mvp="MVP-47",
        spec="SPEC-048",
    )

    report = evaluate_cross_artifact_consistency(_input(observation, review, bundle))

    assert report.state == ConsistencyState.OK
    assert report.data_quality.finding_count == 0
    assert report.data_quality.blocking_count == 0
    assert report.data_quality.warning_count == 0
    assert report.data_quality.info_count == 0
    assert len(report.artifacts) == 3
    assert report.safety_flags.audit_only is True
    assert report.safety_flags.filesystem_access is False
    assert report.safety_flags.network_access is False
    assert report.safety_flags.trading_signal is False


# ---------------------------------------------------------------------------
# BLOCKED paths
# ---------------------------------------------------------------------------


def test_blocked_missing_upstream_strict() -> None:
    """Missing upstream reference in strict mode should block the report."""
    downstream = _artifact(
        "downstream-1",
        kind="observation",
        state="READY",
        upstream=("missing-upstream",),
        content_hash="abc",
        content_length=3,
    )

    report = evaluate_cross_artifact_consistency(_input(downstream, strict=True))

    assert report.state == ConsistencyState.BLOCKED
    assert any(
        f.reason_code == ConsistencyReasonCode.MISSING_UPSTREAM_REFERENCE
        for f in report.findings
    )


def test_blocked_duplicate_artifact_id() -> None:
    """Duplicate artifact IDs should block the report."""
    a1 = _artifact("same-id", kind="observation", state="READY")
    a2 = _artifact("same-id", kind="observation", state="READY")

    report = evaluate_cross_artifact_consistency(_input(a1, a2))

    assert report.state == ConsistencyState.BLOCKED
    assert any(
        f.reason_code == ConsistencyReasonCode.DUPLICATE_ARTIFACT_ID
        for f in report.findings
    )


def test_blocked_empty_input_not_allowed() -> None:
    """Empty input with allow_empty=False should block."""
    report = evaluate_cross_artifact_consistency(_input(allow_empty=False))

    assert report.state == ConsistencyState.BLOCKED
    assert any(
        f.reason_code == ConsistencyReasonCode.NO_ARTIFACTS for f in report.findings
    )


# ---------------------------------------------------------------------------
# DEGRADED paths
# ---------------------------------------------------------------------------


def test_degraded_contradictory_link() -> None:
    """A contradictory upstream/downstream link should degrade the report."""
    upstream = _artifact("upstream-1", kind="observation", state="READY")
    downstream = _artifact(
        "downstream-1",
        kind="observation",
        state="READY",
        upstream=("upstream-1",),
        content_hash="abc",
        content_length=3,
    )

    report = evaluate_cross_artifact_consistency(_input(upstream, downstream))

    assert report.state == ConsistencyState.DEGRADED
    assert any(
        f.reason_code == ConsistencyReasonCode.CONTRADICTORY_METADATA
        for f in report.findings
    )
    assert all(f.severity != ConsistencySeverity.BLOCKING for f in report.findings)


# ---------------------------------------------------------------------------
# NOT_APPLICABLE path
# ---------------------------------------------------------------------------


def test_not_applicable_empty_allowed() -> None:
    """Empty input with allow_empty=True should be NOT_APPLICABLE."""
    report = evaluate_cross_artifact_consistency(_input(allow_empty=True))

    assert report.state == ConsistencyState.NOT_APPLICABLE
    assert report.data_quality.finding_count == 1
    assert report.findings[0].reason_code == ConsistencyReasonCode.NO_ARTIFACTS


# ---------------------------------------------------------------------------
# Family-specific semantic checks
# ---------------------------------------------------------------------------


def test_decision_log_vs_queue_mismatch() -> None:
    """A decision log referencing a missing queue should degrade."""
    queue = _artifact("queue-1", kind="human_review_queue", state="READY")
    decision_log = _artifact(
        "decision-1",
        kind="human_review_decision_log",
        state="READY",
        decision_ids=("queue-1", "queue-2"),
    )

    report = evaluate_cross_artifact_consistency(_input(queue, decision_log))

    assert report.state == ConsistencyState.DEGRADED
    assert any(
        f.reason_code == ConsistencyReasonCode.DECISION_LOG_QUEUE_MISMATCH
        for f in report.findings
    )


def test_audit_bundle_export_vs_bundle_mismatch() -> None:
    """An export referencing a missing bundle should degrade."""
    bundle = _artifact("bundle-1", kind="audit_bundle", state="READY")
    export = _artifact(
        "export-1",
        kind="audit_bundle_export",
        state="READY",
        report_ids=("bundle-1", "bundle-2"),
    )

    report = evaluate_cross_artifact_consistency(_input(bundle, export))

    assert report.state == ConsistencyState.DEGRADED
    assert any(
        f.reason_code == ConsistencyReasonCode.AUDIT_BUNDLE_EXPORT_MISMATCH
        for f in report.findings
    )


def test_verification_vs_export_mismatch() -> None:
    """A verification report referencing a missing export should degrade."""
    export = _artifact("export-1", kind="audit_bundle_export", state="READY")
    verification = _artifact(
        "verify-1",
        kind="audit_bundle_export_verification",
        state="READY",
        report_ids=("export-1", "export-2"),
    )

    report = evaluate_cross_artifact_consistency(_input(export, verification))

    assert report.state == ConsistencyState.DEGRADED
    assert any(
        f.reason_code == ConsistencyReasonCode.VERIFICATION_EXPORT_MISMATCH
        for f in report.findings
    )


# ---------------------------------------------------------------------------
# Safety and determinism
# ---------------------------------------------------------------------------


def test_opaque_refs_remain_strings_only() -> None:
    """Opaque refs are emitted as strings and never opened or parsed."""
    artifact = _artifact(
        "artifact-1",
        kind="observation",
        state="READY",
        opaque_value="ref://internal/path/must/not/be/opened",
    )

    report = evaluate_cross_artifact_consistency(_input(artifact))
    d = consistency_report_to_dict(report)
    j = consistency_report_to_json(report)

    assert d["artifacts"][0]["opaque_ref"]["opaque_value"] == "ref://internal/path/must/not/be/opened"
    assert isinstance(d["artifacts"][0]["opaque_ref"]["opaque_value"], str)
    json.loads(j)  # confirms JSON-compatible serialization


def test_writer_deterministic_across_formats() -> None:
    """Writer outputs must be deterministic for the same report."""
    report = evaluate_cross_artifact_consistency(_input(_artifact("artifact-1")))

    d1 = consistency_report_to_dict(report)
    d2 = consistency_report_to_dict(report)
    j1 = consistency_report_to_json(report)
    j2 = consistency_report_to_json(report)
    m1 = consistency_report_to_markdown(report)
    m2 = consistency_report_to_markdown(report)

    assert d1 == d2
    assert j1 == j2
    assert m1 == m2
    assert json.loads(j1) == json.loads(j2)


def test_no_forbidden_claims_in_generated_output() -> None:
    """Generated dict, JSON, and Markdown must contain no forbidden claims."""
    report = evaluate_cross_artifact_consistency(_input(_artifact("artifact-1")))

    for output in (
        json.dumps(consistency_report_to_dict(report)),
        consistency_report_to_json(report),
        consistency_report_to_markdown(report),
    ):
        lower = output.lower()
        for term in DEFAULT_FORBIDDEN_TERMS:
            assert term not in lower, f"forbidden term {term!r} found in generated output"


def test_engine_and_writer_no_forbidden_modules() -> None:
    """Engine and writer must not import forbidden I/O/runtime modules."""
    validate_no_forbidden_engine_modules()
    validate_no_forbidden_writer_modules()


def test_repeated_calls_are_deterministic() -> None:
    """Repeated evaluation and serialization must produce identical output."""
    input_obj = _input(
        _artifact("artifact-1"),
        _artifact("artifact-2"),
    )

    r1 = evaluate_cross_artifact_consistency(input_obj)
    r2 = evaluate_cross_artifact_consistency(input_obj)

    assert r1 == r2
    assert r1.report_id == r2.report_id
    assert consistency_report_to_dict(r1) == consistency_report_to_dict(r2)
    assert consistency_report_to_json(r1) == consistency_report_to_json(r2)
    assert consistency_report_to_markdown(r1) == consistency_report_to_markdown(r2)


def test_markdown_has_all_sections() -> None:
    """Markdown output must contain all required sections."""
    report = evaluate_cross_artifact_consistency(_input(_artifact("artifact-1")))
    md = consistency_report_to_markdown(report)

    for section in (
        "Summary",
        "Reason Codes",
        "Data Quality",
        "Safety Flags",
        "Artifacts",
        "Findings",
        "Metadata",
        "Notes",
    ):
        assert f"## {section}" in md


def test_empty_findings_and_artifacts_explicit_in_markdown() -> None:
    """Markdown must explicitly state when there are no findings/artifacts."""
    report = evaluate_cross_artifact_consistency(_input(allow_empty=True))
    md = consistency_report_to_markdown(report)

    assert "No findings found." in md or "No artifacts" in md


def test_safety_flags_always_safe() -> None:
    """Safety flags in any integration report must assert a safe run."""
    ok_report = evaluate_cross_artifact_consistency(
        _input(_artifact("artifact-1"))
    )
    degraded_report = evaluate_cross_artifact_consistency(
        _input(
            _artifact("upstream-1"),
            _artifact("downstream-1", upstream=("upstream-1",)),
        )
    )
    blocked_report = evaluate_cross_artifact_consistency(
        _input(_artifact("a"), _artifact("a"))
    )

    for report in (ok_report, degraded_report, blocked_report):
        assert report.safety_flags.audit_only is True
        assert report.safety_flags.opaque_refs_only is True
        assert report.safety_flags.filesystem_access is False
        assert report.safety_flags.network_access is False
        assert report.safety_flags.runtime_execution is False
        assert report.safety_flags.trading_signal is False


def test_all_states_covered() -> None:
    """Integration must exercise all four aggregate states."""
    ok = evaluate_cross_artifact_consistency(
        _input(_artifact("a"))
    )
    assert ok.state == ConsistencyState.OK

    degraded = evaluate_cross_artifact_consistency(
        _input(
            _artifact("upstream-1"),
            _artifact("downstream-1", upstream=("upstream-1",)),
        )
    )
    assert degraded.state == ConsistencyState.DEGRADED

    blocked = evaluate_cross_artifact_consistency(
        _input(_artifact("a"), _artifact("a"))
    )
    assert blocked.state == ConsistencyState.BLOCKED

    not_applicable = evaluate_cross_artifact_consistency(_input(allow_empty=True))
    assert not_applicable.state == ConsistencyState.NOT_APPLICABLE
