"""Integration tests for the Research Audit Aggregate Health Report engine and writer."""

from __future__ import annotations

import json
from typing import Any

import pytest

from hunter.research_audit_health import (
    HealthArtifactSummary,
    HealthConfig,
    HealthInput,
    HealthReasonCode,
    HealthState,
    WriterForbiddenPhraseLeakageError,
    evaluate_research_audit_health,
    health_report_to_dict,
    health_report_to_json,
    health_report_to_markdown,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _summary(
    artifact_id: str,
    family: str = "research_audit_snapshot",
    source_state: str = "OK",
    score: float | None = 95.0,
    mvp: str | None = "MVP-48",
    spec: str | None = "SPEC-049",
    ref: str | None = "ref://opaque",
    metadata: dict[str, object] | None = None,
) -> HealthArtifactSummary:
    return HealthArtifactSummary(
        artifact_id=artifact_id,
        family=family,
        source_state=source_state,
        score=score,
        mvp=mvp,
        spec=spec,
        ref=ref,
        metadata=metadata,
    )


def _input(
    *summaries: HealthArtifactSummary,
    metadata: dict[str, object] | None = None,
    **config_kwargs: Any,
) -> HealthInput:
    return HealthInput(
        summaries=tuple(summaries),
        config=HealthConfig(**config_kwargs),
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# OK path
# ---------------------------------------------------------------------------


def test_ok_multiple_families_end_to_end() -> None:
    """A healthy snapshot family and catalog family aggregate to OK."""
    snap = _summary("snap-1", family="research_audit_snapshot")
    cat = _summary("cat-1", family="research_audit_catalog")

    report = evaluate_research_audit_health(_input(snap, cat))
    assert report.state == HealthState.OK
    assert report.data_quality.blocking_count == 0
    assert report.data_quality.warning_count == 0
    assert {r.family for r in report.family_rollups} == {
        "research_audit_snapshot",
        "research_audit_catalog",
    }

    # Dict output is stable and JSON-compatible.
    data = health_report_to_dict(report)
    assert data["state"] == HealthState.OK.value
    assert data["report_id"] == report.report_id
    assert data["kind"] == "research_audit_health_report"
    assert data["safety_notice"] is not None
    assert data["no_authenticity_notice"] is not None

    # JSON output parses back to the same shape.
    json_text = health_report_to_json(report)
    parsed = json.loads(json_text)
    assert parsed["report_id"] == report.report_id
    assert parsed["state"] == HealthState.OK.value

    # Markdown output includes the families and safety notice.
    md = health_report_to_markdown(report)
    assert "# Research Audit Aggregate Health Report" in md
    assert "## Safety Notice" in md
    assert "snap-1" in md or "research_audit_snapshot" in md
    assert "cat-1" in md or "research_audit_catalog" in md


# ---------------------------------------------------------------------------
# DEGRADED path
# ---------------------------------------------------------------------------


def test_degraded_stale_source_state_roundtrip() -> None:
    """A stale source degrades the aggregate and the writer reflects it."""
    stale = _summary("snap-1", source_state="STALE", score=80.0)
    ok = _summary("snap-2", source_state="OK", score=95.0)

    report = evaluate_research_audit_health(_input(stale, ok))
    assert report.state == HealthState.DEGRADED
    assert any(
        f.reason_code == HealthReasonCode.STALE_SOURCE_STATE for f in report.findings
    )
    assert report.data_quality.warning_count >= 1

    data = health_report_to_dict(report)
    assert data["state"] == HealthState.DEGRADED.value
    assert data["data_quality"]["warning_count"] >= 1

    md = health_report_to_markdown(report)
    assert "DEGRADED" in md
    assert "STALE" in md


# ---------------------------------------------------------------------------
# BLOCKED path
# ---------------------------------------------------------------------------


def test_blocked_forbidden_phrase_in_metadata() -> None:
    """A forbidden readiness phrase in metadata blocks the report and the writer refuses to serialize it."""
    bad = _summary(
        "snap-1",
        metadata={"note": "This artifact shows production readiness"},
    )

    report = evaluate_research_audit_health(_input(bad))
    assert report.state == HealthState.BLOCKED
    assert any(
        f.reason_code == HealthReasonCode.FORBIDDEN_PHRASE_LEAKAGE
        for f in report.findings
    )
    assert report.data_quality.blocking_count >= 1

    # The writer should refuse to serialize a blocked report with the forbidden phrase still in metadata.
    with pytest.raises(WriterForbiddenPhraseLeakageError):
        health_report_to_json(report)
    with pytest.raises(WriterForbiddenPhraseLeakageError):
        health_report_to_markdown(report)


def test_blocked_inconsistent_score_and_writer() -> None:
    """An inconsistent score blocks, and the writer still fails on the leaked phrase."""
    bad = _summary(
        "snap-1",
        score=10.0,
        metadata={"note": "recommendation to buy"},
    )

    report = evaluate_research_audit_health(_input(bad))
    assert report.state == HealthState.BLOCKED

    # The writer guard catches the leaked phrase in the report metadata.
    with pytest.raises(WriterForbiddenPhraseLeakageError):
        health_report_to_dict(report)


# ---------------------------------------------------------------------------
# NOT_APPLICABLE path
# ---------------------------------------------------------------------------


def test_not_applicable_empty_input() -> None:
    """An empty allowed input yields NOT_APPLICABLE and serializes cleanly."""
    report = evaluate_research_audit_health(_input(allow_empty=True))
    assert report.state == HealthState.NOT_APPLICABLE
    assert report.data_quality.summary_count == 0

    data = health_report_to_dict(report)
    assert data["state"] == HealthState.NOT_APPLICABLE.value
    assert any(
        f["reason_code"] == HealthReasonCode.NO_ARTIFACTS.value for f in data["findings"]
    )

    md = health_report_to_markdown(report)
    assert "NOT_APPLICABLE" in md
    assert "## Findings" in md


# ---------------------------------------------------------------------------
# Multi-family scenarios
# ---------------------------------------------------------------------------


def test_multi_family_with_required_family_missing() -> None:
    """Two families present but a third required one is missing."""
    snap = _summary("snap-1", family="research_audit_snapshot")
    cat = _summary("cat-1", family="research_audit_catalog")
    config = HealthConfig(
        required_families=("research_audit_snapshot", "research_audit_catalog", "review_search"),
        strict=False,
    )

    report = evaluate_research_audit_health(
        HealthInput(summaries=(snap, cat), config=config)
    )
    assert report.state == HealthState.DEGRADED
    assert any(
        f.reason_code == HealthReasonCode.MISSING_REQUIRED_FAMILY for f in report.findings
    )

    # Writer still serializes the degraded report.
    data = health_report_to_dict(report)
    assert data["state"] == HealthState.DEGRADED.value
    families = {r["family"] for r in data["family_rollups"]}
    assert families == {"research_audit_snapshot", "research_audit_catalog"}


# ---------------------------------------------------------------------------
# Determinism and safety
# ---------------------------------------------------------------------------


def test_end_to_end_determinism() -> None:
    """The same inputs in different order produce the same report and serialized output."""
    a = _summary("snap-1", family="research_audit_snapshot")
    b = _summary("cat-1", family="research_audit_catalog")
    c = _summary("review-1", family="review_search")

    report1 = evaluate_research_audit_health(_input(a, b, c))
    report2 = evaluate_research_audit_health(_input(c, a, b))

    assert report1.report_id == report2.report_id

    json1 = health_report_to_json(report1)
    json2 = health_report_to_json(report2)
    assert json1 == json2

    md1 = health_report_to_markdown(report1)
    md2 = health_report_to_markdown(report2)
    assert md1 == md2


def test_safety_flags_preserved_in_output() -> None:
    """Safety flags are preserved in all output formats."""
    snap = _summary("snap-1")
    report = evaluate_research_audit_health(_input(snap))

    data = health_report_to_dict(report)
    assert data["safety_flags"]["audit_only"] is True
    assert data["safety_flags"]["opaque_refs_only"] is True
    assert data["safety_flags"]["filesystem_access"] is False
    assert data["safety_flags"]["network_access"] is False
    assert data["safety_flags"]["runtime_execution"] is False
    assert data["safety_flags"]["trading_signal"] is False

    md = health_report_to_markdown(report)
    assert "Safety Flags" in md
    assert "audit_only" in md


def test_reason_code_counts_in_markdown() -> None:
    """Reason code counts appear in Markdown."""
    a = _summary("snap-1")
    b = _summary("snap-2", source_state="BLOCKED")
    report = evaluate_research_audit_health(_input(a, b))

    md = health_report_to_markdown(report)
    assert "## Reason Code Counts" in md
    assert "OK" in md
    assert "BLOCKING_SOURCE_STATE" in md


def test_metadata_preserved_roundtrip() -> None:
    """Caller metadata survives the engine -> writer roundtrip."""
    snap = _summary("snap-1")
    report = evaluate_research_audit_health(
        _input(snap, metadata={"run_id": "run-123", "project": "MVP-48"})
    )

    data = health_report_to_dict(report)
    assert data["metadata"] == {"project": "MVP-48", "run_id": "run-123"}

    parsed = json.loads(health_report_to_json(report))
    assert parsed["metadata"] == {"project": "MVP-48", "run_id": "run-123"}
