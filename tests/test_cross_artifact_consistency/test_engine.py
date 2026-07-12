"""Tests for the Cross-Artifact Consistency Engine evaluator."""

from __future__ import annotations

import sys
from typing import Mapping

import pytest

from src.hunter.cross_artifact_consistency.engine import (
    evaluate_cross_artifact_consistency,
    validate_no_forbidden_modules,
)
from src.hunter.cross_artifact_consistency.models import (
    ArtifactRef,
    ArtifactSummary,
    ConsistencyReasonCode,
    ConsistencySeverity,
    ConsistencyState,
    CrossArtifactConsistencyConfig,
    CrossArtifactConsistencyInput,
)



def _artifact(
    artifact_id: str,
    artifact_kind: str = "observation",
    artifact_state: str = "READY",
    upstream_ids: tuple[str, ...] = (),
    downstream_ids: tuple[str, ...] = (),
    decision_ids: tuple[str, ...] = (),
    review_ids: tuple[str, ...] = (),
    report_ids: tuple[str, ...] = (),
    content_hash: str | None = None,
    content_length: int | None = None,
    mvp: str | None = None,
    spec: str | None = None,
    metadata: Mapping[str, object] | None = None,
    opaque_ref: ArtifactRef | None = None,
) -> ArtifactSummary:
    return ArtifactSummary(
        artifact_id=artifact_id,
        artifact_kind=artifact_kind,
        artifact_state=artifact_state,
        upstream_ids=upstream_ids,
        downstream_ids=downstream_ids,
        decision_ids=decision_ids,
        review_ids=review_ids,
        report_ids=report_ids,
        content_hash=content_hash,
        content_length=content_length,
        mvp=mvp,
        spec=spec,
        metadata=metadata,
        opaque_ref=opaque_ref
        if opaque_ref is not None
        else ArtifactRef(
            ref_id=artifact_id,
            ref_kind="opaque",
            opaque_value=f"reports/{artifact_id}.json",
        ),
    )



def test_empty_allow_empty_true() -> None:
    inp = CrossArtifactConsistencyInput(
        artifacts=(),
        config=CrossArtifactConsistencyConfig(allow_empty=True),
    )
    report = evaluate_cross_artifact_consistency(inp)
    assert report.state == ConsistencyState.NOT_APPLICABLE
    assert any(
        f.reason_code == ConsistencyReasonCode.NO_ARTIFACTS for f in report.findings
    )



def test_empty_allow_empty_false() -> None:
    inp = CrossArtifactConsistencyInput(
        artifacts=(),
        config=CrossArtifactConsistencyConfig(allow_empty=False),
    )
    report = evaluate_cross_artifact_consistency(inp)
    assert report.state == ConsistencyState.BLOCKED
    assert any(
        f.reason_code == ConsistencyReasonCode.NO_ARTIFACTS for f in report.findings
    )



def test_duplicate_artifact_id() -> None:
    a = _artifact(artifact_id="a1")
    inp = CrossArtifactConsistencyInput(artifacts=(a, a))
    report = evaluate_cross_artifact_consistency(inp)
    assert report.state == ConsistencyState.BLOCKED
    assert any(
        f.reason_code == ConsistencyReasonCode.DUPLICATE_ARTIFACT_ID
        for f in report.findings
    )



def test_missing_upstream_strict() -> None:
    a = _artifact(artifact_id="a1", upstream_ids=("missing",))
    inp = CrossArtifactConsistencyInput(artifacts=(a,))
    report = evaluate_cross_artifact_consistency(inp)
    assert report.state == ConsistencyState.BLOCKED
    assert any(
        f.reason_code == ConsistencyReasonCode.MISSING_UPSTREAM_REFERENCE
        and f.severity == ConsistencySeverity.BLOCKING
        for f in report.findings
    )



def test_missing_upstream_non_strict() -> None:
    a = _artifact(artifact_id="a1", upstream_ids=("missing",))
    config = CrossArtifactConsistencyConfig(strict=False)
    inp = CrossArtifactConsistencyInput(artifacts=(a,), config=config)
    report = evaluate_cross_artifact_consistency(inp)
    assert report.state == ConsistencyState.DEGRADED
    assert any(
        f.reason_code == ConsistencyReasonCode.MISSING_UPSTREAM_REFERENCE
        and f.severity == ConsistencySeverity.WARNING
        for f in report.findings
    )



def test_orphan_downstream() -> None:
    a = _artifact(artifact_id="a1", downstream_ids=("orphan",))
    inp = CrossArtifactConsistencyInput(artifacts=(a,))
    report = evaluate_cross_artifact_consistency(inp)
    assert any(
        f.reason_code == ConsistencyReasonCode.ORPHAN_DOWNSTREAM_REFERENCE
        for f in report.findings
    )



def test_inconsistent_state_transition() -> None:
    upstream = _artifact(artifact_id="up", artifact_state="BLOCKED")
    downstream = _artifact(
        artifact_id="down",
        artifact_state="READY",
        upstream_ids=("up",),
    )
    inp = CrossArtifactConsistencyInput(artifacts=(upstream, downstream))
    report = evaluate_cross_artifact_consistency(inp)
    assert any(
        f.reason_code == ConsistencyReasonCode.INCONSISTENT_STATE_TRANSITION
        for f in report.findings
    )



def test_contradictory_link_upsteam_not_reciprocal() -> None:
    a = _artifact(artifact_id="a1", upstream_ids=("a2",))
    b = _artifact(artifact_id="a2", downstream_ids=())
    inp = CrossArtifactConsistencyInput(artifacts=(a, b))
    report = evaluate_cross_artifact_consistency(inp)
    assert any(
        f.reason_code == ConsistencyReasonCode.CONTRADICTORY_METADATA
        for f in report.findings
    )



def test_contradictory_link_downstream_not_reciprocal() -> None:
    a = _artifact(artifact_id="a1", downstream_ids=("a2",))
    b = _artifact(artifact_id="a2", upstream_ids=())
    inp = CrossArtifactConsistencyInput(artifacts=(a, b))
    report = evaluate_cross_artifact_consistency(inp)
    assert any(
        f.reason_code == ConsistencyReasonCode.CONTRADICTORY_METADATA
        for f in report.findings
    )



def test_malformed_content_length() -> None:
    a = _artifact(artifact_id="a1", content_length=-1)
    inp = CrossArtifactConsistencyInput(artifacts=(a,))
    report = evaluate_cross_artifact_consistency(inp)
    assert report.state == ConsistencyState.BLOCKED
    assert any(
        f.reason_code == ConsistencyReasonCode.MALFORMED_METADATA
        for f in report.findings
    )



def test_hash_length_mismatch_hash_only() -> None:
    a = _artifact(artifact_id="a1", content_hash="abc", content_length=None)
    inp = CrossArtifactConsistencyInput(artifacts=(a,))
    report = evaluate_cross_artifact_consistency(inp)
    assert any(
        f.reason_code == ConsistencyReasonCode.HASH_LENGTH_MISMATCH
        for f in report.findings
    )



def test_hash_length_mismatch_length_only() -> None:
    a = _artifact(artifact_id="a1", content_hash=None, content_length=100)
    inp = CrossArtifactConsistencyInput(artifacts=(a,))
    report = evaluate_cross_artifact_consistency(inp)
    assert any(
        f.reason_code == ConsistencyReasonCode.HASH_LENGTH_MISMATCH
        for f in report.findings
    )



def test_hash_length_ok() -> None:
    a = _artifact(artifact_id="a1", content_hash="abc", content_length=100)
    inp = CrossArtifactConsistencyInput(artifacts=(a,))
    report = evaluate_cross_artifact_consistency(inp)
    assert all(
        f.reason_code != ConsistencyReasonCode.HASH_LENGTH_MISMATCH
        for f in report.findings
    )



def test_unsupported_artifact_kind() -> None:
    a = _artifact(artifact_id="a1", artifact_kind="unknown_kind")
    inp = CrossArtifactConsistencyInput(artifacts=(a,))
    report = evaluate_cross_artifact_consistency(inp)
    assert report.state == ConsistencyState.BLOCKED
    assert any(
        f.reason_code == ConsistencyReasonCode.UNSUPPORTED_ARTIFACT_KIND
        for f in report.findings
    )



def test_mvp_spec_mismatch() -> None:
    a = _artifact(artifact_id="a1", mvp="MVP-47", spec="SPEC-045")
    inp = CrossArtifactConsistencyInput(artifacts=(a,))
    report = evaluate_cross_artifact_consistency(inp)
    assert any(
        f.reason_code == ConsistencyReasonCode.MVP_SPEC_MISMATCH
        for f in report.findings
    )



def test_mvp_spec_match() -> None:
    a = _artifact(artifact_id="a1", mvp="MVP-47", spec="SPEC-048")
    inp = CrossArtifactConsistencyInput(artifacts=(a,))
    report = evaluate_cross_artifact_consistency(inp)
    assert all(
        f.reason_code != ConsistencyReasonCode.MVP_SPEC_MISMATCH
        for f in report.findings
    )



def test_decision_log_queue_mismatch() -> None:
    log = _artifact(
        artifact_id="log1",
        artifact_kind="human_review_decision_log",
        decision_ids=("q1", "q2"),
    )
    inp = CrossArtifactConsistencyInput(artifacts=(log,))
    report = evaluate_cross_artifact_consistency(inp)
    assert any(
        f.reason_code == ConsistencyReasonCode.DECISION_LOG_QUEUE_MISMATCH
        for f in report.findings
    )



def test_decision_log_queue_match() -> None:
    log = _artifact(
        artifact_id="log1",
        artifact_kind="human_review_decision_log",
        decision_ids=("q1",),
    )
    queue = _artifact(
        artifact_id="q1",
        artifact_kind="human_review_queue",
        review_ids=("q1",),
    )
    inp = CrossArtifactConsistencyInput(artifacts=(log, queue))
    report = evaluate_cross_artifact_consistency(inp)
    assert all(
        f.reason_code != ConsistencyReasonCode.DECISION_LOG_QUEUE_MISMATCH
        for f in report.findings
    )



def test_audit_bundle_export_mismatch() -> None:
    export = _artifact(
        artifact_id="exp1",
        artifact_kind="audit_bundle_export",
        report_ids=("bundle1",),
    )
    inp = CrossArtifactConsistencyInput(artifacts=(export,))
    report = evaluate_cross_artifact_consistency(inp)
    assert any(
        f.reason_code == ConsistencyReasonCode.AUDIT_BUNDLE_EXPORT_MISMATCH
        for f in report.findings
    )



def test_audit_bundle_export_match() -> None:
    bundle = _artifact(
        artifact_id="bundle1",
        artifact_kind="audit_bundle",
    )
    export = _artifact(
        artifact_id="exp1",
        artifact_kind="audit_bundle_export",
        report_ids=("bundle1",),
    )
    inp = CrossArtifactConsistencyInput(artifacts=(bundle, export))
    report = evaluate_cross_artifact_consistency(inp)
    assert all(
        f.reason_code != ConsistencyReasonCode.AUDIT_BUNDLE_EXPORT_MISMATCH
        for f in report.findings
    )



def test_verification_export_mismatch() -> None:
    verification = _artifact(
        artifact_id="ver1",
        artifact_kind="audit_bundle_export_verification",
        report_ids=("exp1",),
    )
    inp = CrossArtifactConsistencyInput(artifacts=(verification,))
    report = evaluate_cross_artifact_consistency(inp)
    assert any(
        f.reason_code == ConsistencyReasonCode.VERIFICATION_EXPORT_MISMATCH
        for f in report.findings
    )



def test_verification_export_match() -> None:
    export = _artifact(
        artifact_id="exp1",
        artifact_kind="audit_bundle_export",
    )
    verification = _artifact(
        artifact_id="ver1",
        artifact_kind="audit_bundle_export_verification",
        report_ids=("exp1",),
    )
    inp = CrossArtifactConsistencyInput(artifacts=(export, verification))
    report = evaluate_cross_artifact_consistency(inp)
    assert all(
        f.reason_code != ConsistencyReasonCode.VERIFICATION_EXPORT_MISMATCH
        for f in report.findings
    )



def test_stale_project_memory_warning() -> None:
    a = _artifact(artifact_id="a1")
    config = CrossArtifactConsistencyConfig(check_stale_project_memory=True)
    inp = CrossArtifactConsistencyInput(
        artifacts=(a,),
        config=config,
        metadata={
            "version": "0.45.0-dev",
            "tags": ["v0.46.0-dev", "v0.45.0-dev"],
        },
    )
    report = evaluate_cross_artifact_consistency(inp)
    assert any(
        f.reason_code == ConsistencyReasonCode.STALE_PROJECT_MEMORY
        for f in report.findings
    )



def test_no_stale_project_memory_when_disabled() -> None:
    a = _artifact(artifact_id="a1")
    config = CrossArtifactConsistencyConfig(check_stale_project_memory=False)
    inp = CrossArtifactConsistencyInput(
        artifacts=(a,),
        config=config,
        metadata={
            "version": "0.45.0-dev",
            "tags": ["v0.46.0-dev"],
        },
    )
    report = evaluate_cross_artifact_consistency(inp)
    assert all(
        f.reason_code != ConsistencyReasonCode.STALE_PROJECT_MEMORY
        for f in report.findings
    )



def test_forbidden_phrase_leakage() -> None:
    a = _artifact(
        artifact_id="a1",
        artifact_state="READY",
        metadata={"note": "production readiness"},
    )
    inp = CrossArtifactConsistencyInput(artifacts=(a,))
    report = evaluate_cross_artifact_consistency(inp)
    assert report.state == ConsistencyState.BLOCKED
    assert any(
        f.reason_code == ConsistencyReasonCode.FORBIDDEN_PHRASE_LEAKAGE
        for f in report.findings
    )



def test_determinism_repeated_calls() -> None:
    a = _artifact(artifact_id="a1", upstream_ids=("a2",))
    b = _artifact(artifact_id="a2", artifact_state="BLOCKED")
    inp = CrossArtifactConsistencyInput(artifacts=(a, b))
    report1 = evaluate_cross_artifact_consistency(inp)
    report2 = evaluate_cross_artifact_consistency(inp)
    assert report1 == report2
    assert report1.report_id == report2.report_id



def test_report_id_changes_when_input_changes() -> None:
    a = _artifact(artifact_id="a1")
    inp1 = CrossArtifactConsistencyInput(artifacts=(a,))
    report1 = evaluate_cross_artifact_consistency(inp1)

    b = _artifact(artifact_id="a2")
    inp2 = CrossArtifactConsistencyInput(artifacts=(a, b))
    report2 = evaluate_cross_artifact_consistency(inp2)

    assert report1.report_id != report2.report_id



def test_findings_are_stable_sorted() -> None:
    a = _artifact(artifact_id="a1", upstream_ids=("missing",))
    b = _artifact(
        artifact_id="a2",
        artifact_state="READY",
        upstream_ids=("a1",),
    )
    inp = CrossArtifactConsistencyInput(artifacts=(b, a))
    report = evaluate_cross_artifact_consistency(inp)
    finding_ids = [f.finding_id for f in report.findings]
    assert finding_ids == sorted(finding_ids)



def test_safety_flags_are_true_and_false() -> None:
    a = _artifact(artifact_id="a1")
    inp = CrossArtifactConsistencyInput(artifacts=(a,))
    report = evaluate_cross_artifact_consistency(inp)
    flags = report.safety_flags
    assert flags.audit_only is True
    assert flags.opaque_refs_only is True
    assert flags.filesystem_access is False
    assert flags.network_access is False
    assert flags.runtime_execution is False
    assert flags.trading_signal is False



def test_engine_does_not_import_forbidden_modules() -> None:
    assert "src.hunter.cross_artifact_consistency.engine" in sys.modules
    validate_no_forbidden_modules()



def test_opaque_refs_are_not_read_or_opened() -> None:
    ref = ArtifactRef(
        ref_id="r1",
        ref_kind="file",
        opaque_value="data/should_not_be_opened.json",
    )
    a = _artifact(artifact_id="a1", opaque_ref=ref)
    inp = CrossArtifactConsistencyInput(artifacts=(a,))
    report = evaluate_cross_artifact_consistency(inp)
    assert report.state == ConsistencyState.OK



def test_no_filesystem_network_runtime_module_imports() -> None:
    engine_module = sys.modules["src.hunter.cross_artifact_consistency.engine"]
    module_globals = set(engine_module.__dict__.keys())
    forbidden = {"pathlib", "os", "subprocess", "socket", "urllib", "requests"}
    for name in forbidden:
        assert name not in module_globals, f"forbidden module {name!r} in engine globals"



def test_no_trading_runtime_readiness_claim_in_generated_text() -> None:
    a = _artifact(artifact_id="a1")
    inp = CrossArtifactConsistencyInput(artifacts=(a,))
    report = evaluate_cross_artifact_consistency(inp)
    combined_text = " ".join(
        [f.title + " " + f.description for f in report.findings]
    ).lower()
    for term in CrossArtifactConsistencyConfig().forbidden_terms:
        assert term not in combined_text, f"forbidden term {term!r} leaked"
