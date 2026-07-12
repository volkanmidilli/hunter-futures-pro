"""Tests for the Cross-Artifact Consistency Report writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.hunter.cross_artifact_consistency import (
    consistency_report_to_dict,
    consistency_report_to_json,
    consistency_report_to_markdown,
)
from src.hunter.cross_artifact_consistency.models import (
    ArtifactRef,
    ArtifactSummary,
    ConsistencyDataQuality,
    ConsistencyFinding,
    ConsistencyReasonCode,
    ConsistencyReport,
    ConsistencySafetyFlags,
    ConsistencySeverity,
    ConsistencyState,
)
from src.hunter.cross_artifact_consistency.writer import (
    ConsistencyWriterError,
    ForbiddenPhraseLeakageError,
    validate_no_forbidden_modules,
)


_DEFAULT_SAFETY_FLAGS = ConsistencySafetyFlags()


def _make_report(
    *,
    state: ConsistencyState = ConsistencyState.OK,
    findings: tuple[ConsistencyFinding, ...] = (),
    artifacts: tuple[ArtifactSummary, ...] = (),
    metadata: dict[str, object] | None = None,
    reason_codes: tuple[ConsistencyReasonCode, ...] = (),
) -> ConsistencyReport:
    return ConsistencyReport(
        report_id="report-id",
        state=state,
        findings=findings,
        reason_codes=reason_codes,
        data_quality=ConsistencyDataQuality(
            artifact_count=len(artifacts),
            finding_count=len(findings),
            blocking_count=sum(
                1 for f in findings if f.severity == ConsistencySeverity.BLOCKING
            ),
            warning_count=sum(
                1 for f in findings if f.severity == ConsistencySeverity.WARNING
            ),
            info_count=sum(
                1 for f in findings if f.severity == ConsistencySeverity.INFO
            ),
        ),
        safety_flags=_DEFAULT_SAFETY_FLAGS,
        artifacts=artifacts,
        metadata=metadata,
    )


def test_dict_serialization_deterministic() -> None:
    report = _make_report()
    d1 = consistency_report_to_dict(report)
    d2 = consistency_report_to_dict(report)
    assert d1 == d2
    assert isinstance(d1, dict)
    assert d1["summary"]["state"] == "OK"


def test_json_serialization_deterministic() -> None:
    report = _make_report()
    j1 = consistency_report_to_json(report)
    j2 = consistency_report_to_json(report)
    assert j1 == j2
    parsed = json.loads(j1)
    assert parsed["summary"]["state"] == "OK"
    assert json.loads(j1) == json.loads(j2)


def test_markdown_serialization_deterministic() -> None:
    report = _make_report()
    m1 = consistency_report_to_markdown(report)
    m2 = consistency_report_to_markdown(report)
    assert m1 == m2
    assert "# Cross-Artifact Consistency Report" in m1


def test_all_states_serialize() -> None:
    for state in (
        ConsistencyState.OK,
        ConsistencyState.DEGRADED,
        ConsistencyState.BLOCKED,
        ConsistencyState.NOT_APPLICABLE,
    ):
        report = _make_report(state=state)
        d = consistency_report_to_dict(report)
        j = consistency_report_to_json(report)
        md = consistency_report_to_markdown(report)
        assert d["summary"]["state"] == state.value
        assert state.value in j
        assert state.value in md


def test_empty_findings() -> None:
    report = _make_report()
    md = consistency_report_to_markdown(report)
    assert "No findings found." in md
    d = consistency_report_to_dict(report)
    assert d["findings"] == []


def test_empty_artifacts_not_applicable() -> None:
    report = _make_report(state=ConsistencyState.NOT_APPLICABLE)
    md = consistency_report_to_markdown(report)
    assert "No artifacts provided." in md
    d = consistency_report_to_dict(report)
    assert d["artifacts"] == []
    assert d["summary"]["artifact_count"] == 0


def test_finding_serialization_with_evidence() -> None:
    finding = ConsistencyFinding(
        finding_id="finding-000001",
        rule_id="HASH_LENGTH_MISMATCH",
        artifact_ids=("artifact-a",),
        severity=ConsistencySeverity.WARNING,
        reason_code=ConsistencyReasonCode.HASH_LENGTH_MISMATCH,
        title="Hash/length mismatch",
        description="Artifact has mismatched hash and length.",
        evidence={"content_hash_present": True, "content_length_present": False},
    )
    report = _make_report(findings=(finding,))
    d = consistency_report_to_dict(report)
    assert d["findings"][0]["evidence"] == {
        "content_hash_present": True,
        "content_length_present": False,
    }
    j = json.loads(consistency_report_to_json(report))
    assert j["findings"][0]["severity"] == "WARNING"


def test_artifact_serialization_with_opaque_ref() -> None:
    ref = ArtifactRef(
        ref_id="ref-1",
        ref_kind="opaque",
        opaque_value="should-not-be-opened-or-validated",
        metadata={"path": "not-a-real-path"},
    )
    artifact = ArtifactSummary(
        artifact_id="artifact-a",
        artifact_kind="observation",
        artifact_state="READY",
        opaque_ref=ref,
    )
    report = _make_report(artifacts=(artifact,))
    d = consistency_report_to_dict(report)
    serialized_ref = d["artifacts"][0]["opaque_ref"]
    assert serialized_ref["opaque_value"] == "should-not-be-opened-or-validated"
    assert serialized_ref["ref_kind"] == "opaque"


def test_metadata_sorting() -> None:
    report = _make_report(metadata={"z": 1, "a": 2, "m": 3})
    d = consistency_report_to_dict(report)
    assert list(d["metadata"].keys()) == ["a", "m", "z"]
    j = json.loads(consistency_report_to_json(report))
    assert list(j["metadata"].keys()) == ["a", "m", "z"]


def test_datetime_serialization() -> None:
    dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    artifact = ArtifactSummary(
        artifact_id="artifact-a",
        artifact_kind="observation",
        artifact_state="READY",
        generated_at=dt,
    )
    report = _make_report(artifacts=(artifact,))
    d = consistency_report_to_dict(report)
    assert d["artifacts"][0]["generated_at"] == "2025-01-01T12:00:00+00:00"


def test_enum_serialization() -> None:
    finding = ConsistencyFinding(
        finding_id="finding-000001",
        rule_id="DUPLICATE_ARTIFACT_ID",
        artifact_ids=("artifact-a",),
        severity=ConsistencySeverity.BLOCKING,
        reason_code=ConsistencyReasonCode.DUPLICATE_ARTIFACT_ID,
        title="Duplicate ID",
        description="Duplicate artifact ID detected.",
    )
    report = _make_report(findings=(finding,))
    d = consistency_report_to_dict(report)
    assert d["findings"][0]["severity"] == "BLOCKING"
    assert d["findings"][0]["reason_code"] == "DUPLICATE_ARTIFACT_ID"
    assert d["summary"]["state"] == "OK"


def test_markdown_pipe_escaping() -> None:
    finding = ConsistencyFinding(
        finding_id="f1",
        rule_id="RULE",
        artifact_ids=("a|b",),
        severity=ConsistencySeverity.INFO,
        reason_code=ConsistencyReasonCode.OK,
        title="Title with | pipe",
        description="Description has | pipe too.",
    )
    report = _make_report(findings=(finding,))
    md = consistency_report_to_markdown(report)
    assert "a\\|b" in md
    assert "Title with \\| pipe" in md
    assert "Description has \\| pipe too" in md


def test_safety_notice_present() -> None:
    report = _make_report()
    d = consistency_report_to_dict(report)
    j = consistency_report_to_json(report)
    md = consistency_report_to_markdown(report)
    assert "audit-only" in d["safety_notice"]
    assert "audit-only" in j
    assert "audit-only" in md
    assert "No Authenticity Notice" in md


def test_no_forbidden_generated_body_claims() -> None:
    report = _make_report()
    texts = [
        json.dumps(consistency_report_to_dict(report)),
        consistency_report_to_json(report),
        consistency_report_to_markdown(report),
    ]
    forbidden = (
        "production readiness",
        "trading readiness",
        "live trading",
        "production approval",
        "trading approval",
        "execution approval",
        "certification",
        "recommendation",
        "suitability",
        "deploy to production",
        "place order",
        "submit order",
        "buy signal",
        "sell signal",
        "long signal",
        "short signal",
    )
    for text in texts:
        lower = text.lower()
        for term in forbidden:
            assert term not in lower, f"Forbidden term {term!r} found in generated text"


def test_no_forbidden_modules_in_writer() -> None:
    from src.hunter.cross_artifact_consistency import writer as writer_module

    forbidden = {"pathlib", "os", "subprocess", "socket", "urllib", "requests"}
    imported = set(writer_module.__dict__.keys())
    assert not imported.intersection(forbidden), imported.intersection(forbidden)


def test_writer_validate_no_forbidden_modules() -> None:
    validate_no_forbidden_modules()  # should not raise


def test_writer_does_not_mutate_report_input() -> None:
    report = _make_report()
    original = json.dumps(consistency_report_to_dict(report))
    consistency_report_to_dict(report)
    consistency_report_to_json(report)
    consistency_report_to_markdown(report)
    assert json.dumps(consistency_report_to_dict(report)) == original


def test_public_exports_include_writer_functions() -> None:
    import src.hunter.cross_artifact_consistency as pkg

    assert callable(pkg.consistency_report_to_dict)
    assert callable(pkg.consistency_report_to_json)
    assert callable(pkg.consistency_report_to_markdown)
    assert callable(pkg.validate_no_forbidden_writer_modules)
    assert pkg.ConsistencyWriterError is ConsistencyWriterError


def test_json_field_order_sorted() -> None:
    report = _make_report(metadata={"b": 1, "a": 2})
    text = consistency_report_to_json(report)
    assert text[1] == '""' or text.startswith('{\n  "')
    # With sort_keys=True, the first key is alphabetically first.
    assert text.startswith('{\n  "')


def test_markdown_table_for_artifacts() -> None:
    artifact = ArtifactSummary(
        artifact_id="artifact-a",
        artifact_kind="observation",
        artifact_state="READY",
        mvp="MVP-47",
        spec="SPEC-048",
    )
    report = _make_report(artifacts=(artifact,))
    md = consistency_report_to_markdown(report)
    assert "artifact_id" in md
    assert "artifact_kind" in md
    assert "artifact_state" in md
    assert "MVP-47" in md
    assert "SPEC-048" in md


def test_markdown_table_for_findings() -> None:
    finding = ConsistencyFinding(
        finding_id="finding-000001",
        rule_id="RULE",
        artifact_ids=("artifact-a",),
        severity=ConsistencySeverity.BLOCKING,
        reason_code=ConsistencyReasonCode.DUPLICATE_ARTIFACT_ID,
        title="Title",
        description="Description",
    )
    report = _make_report(findings=(finding,))
    md = consistency_report_to_markdown(report)
    assert "finding_id" in md
    assert "artifact_ids" in md
    assert "severity" in md
    assert "reason_code" in md


def test_reason_codes_serialize_sorted() -> None:
    report = _make_report(
        reason_codes=(
            ConsistencyReasonCode.HASH_LENGTH_MISMATCH,
            ConsistencyReasonCode.DUPLICATE_ARTIFACT_ID,
        ),
    )
    d = consistency_report_to_dict(report)
    assert d["reason_codes"] == ["DUPLICATE_ARTIFACT_ID", "HASH_LENGTH_MISMATCH"]
