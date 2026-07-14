"""Tests for governance handoff package engine (MVP-62 Step 4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from hunter.governance_handoff.engine import (
    build_research_governance_handoff_package,
    compute_package_fingerprint,
)
from hunter.governance_handoff.models import (
    BLOCKED,
    GATE_FINGERPRINT_MISMATCH,
    GOVERNANCE_FINGERPRINT_MISMATCH,
    GOVERNANCE_HANDOFF_VERSION,
    GOVERNANCE_REVIEW_REQUIRED,
    MISSING_GATE_REPORT,
    MISSING_GOVERNANCE_SUMMARY,
    MISSING_LATEST_ACCEPTED_REVIEW,
    READY_FOR_RESEARCH_HANDOFF,
    REVIEW_FINGERPRINT_MISMATCH,
    REVIEW_REQUIRED,
    GovernanceHandoffConfig,
    GovernanceHandoffError,
    HandoffSourceReference,
)


@dataclass(frozen=True)
class FakeReviewSummary:
    latest_accepted_record_fingerprint: str | None


@dataclass(frozen=True)
class FakeGovernanceSummary:
    version: str
    governance_fingerprint: str
    gate_decision_fingerprint: str
    governance_status: str
    review_summary: object
    research_only: bool = True
    execution_approval_granted: bool = False


@dataclass(frozen=True)
class FakeGateReport:
    version: str
    decision: str
    decision_fingerprint: str
    research_only: bool = True
    human_approval_required: bool = True
    execution_approval_granted: bool = False


@dataclass(frozen=True)
class FakeReviewRecord:
    version: str
    record_fingerprint: str
    source_decision_fingerprint: str
    accepted: bool
    human_approval_recorded: bool
    execution_approval_granted: bool
    reviewer_decision: str
    created_at: datetime


def _ready_inputs():
    summary = FakeGovernanceSummary(
        version="0.61.0-dev",
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status=READY_FOR_RESEARCH_HANDOFF,
        review_summary=FakeReviewSummary("review1"),
    )
    gate = FakeGateReport(
        version="0.59.0-dev",
        decision="GO",
        decision_fingerprint="gate1",
    )
    review = FakeReviewRecord(
        version="0.60.0-dev",
        record_fingerprint="review1",
        source_decision_fingerprint="gate1",
        accepted=True,
        human_approval_recorded=True,
        execution_approval_granted=False,
        reviewer_decision="APPROVE_FOR_RESEARCH",
        created_at=datetime.now(timezone.utc),
    )
    return summary, gate, review


def test_build_ready_package():
    summary, gate, review = _ready_inputs()
    built_at = datetime.now(timezone.utc)
    package = build_research_governance_handoff_package(
        summary,
        gate,
        review,
        GovernanceHandoffConfig(),
        built_at=built_at,
        metadata={"run_id": "r1"},
    )
    assert package.version == GOVERNANCE_HANDOFF_VERSION
    assert package.governance_status == READY_FOR_RESEARCH_HANDOFF
    assert package.handoff_allowed is True
    assert package.research_only is True
    assert package.execution_approval_granted is False
    assert package.production_approval_granted is False
    assert package.blocking_reason_codes == ()
    assert package.review_reason_codes == ()
    assert package.manifest.package_fingerprint == package.package_fingerprint


def test_build_blocked_missing_inputs():
    built_at = datetime.now(timezone.utc)
    package = build_research_governance_handoff_package(
        None,
        None,
        None,
        GovernanceHandoffConfig(),
        built_at=built_at,
    )
    assert package.governance_status == BLOCKED
    assert package.handoff_allowed is False
    assert MISSING_GOVERNANCE_SUMMARY in package.blocking_reason_codes
    assert MISSING_GATE_REPORT in package.blocking_reason_codes
    assert MISSING_LATEST_ACCEPTED_REVIEW in package.blocking_reason_codes


def test_build_review_required_governance():
    summary = FakeGovernanceSummary(
        version="0.61.0-dev",
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status=REVIEW_REQUIRED,
        review_summary=FakeReviewSummary("review1"),
    )
    gate = FakeGateReport(
        version="0.59.0-dev",
        decision="GO",
        decision_fingerprint="gate1",
    )
    review = FakeReviewRecord(
        version="0.60.0-dev",
        record_fingerprint="review1",
        source_decision_fingerprint="gate1",
        accepted=True,
        human_approval_recorded=True,
        execution_approval_granted=False,
        reviewer_decision="APPROVE_FOR_RESEARCH",
        created_at=datetime.now(timezone.utc),
    )
    package = build_research_governance_handoff_package(
        summary,
        gate,
        review,
        GovernanceHandoffConfig(),
        built_at=datetime.now(timezone.utc),
    )
    assert package.governance_status == REVIEW_REQUIRED
    assert package.handoff_allowed is False
    assert GOVERNANCE_REVIEW_REQUIRED in package.review_reason_codes


def test_build_gate_fingerprint_mismatch():
    summary, gate, review = _ready_inputs()
    summary = FakeGovernanceSummary(
        version="0.61.0-dev",
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate-OTHER",
        governance_status=READY_FOR_RESEARCH_HANDOFF,
        review_summary=FakeReviewSummary("review1"),
    )
    package = build_research_governance_handoff_package(
        summary,
        gate,
        review,
        GovernanceHandoffConfig(),
        built_at=datetime.now(timezone.utc),
    )
    assert GATE_FINGERPRINT_MISMATCH in package.blocking_reason_codes
    assert package.handoff_allowed is False


def test_build_review_fingerprint_mismatch():
    summary, gate, review = _ready_inputs()
    summary = FakeGovernanceSummary(
        version="0.61.0-dev",
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status=READY_FOR_RESEARCH_HANDOFF,
        review_summary=FakeReviewSummary("review-OTHER"),
    )
    package = build_research_governance_handoff_package(
        summary,
        gate,
        review,
        GovernanceHandoffConfig(),
        built_at=datetime.now(timezone.utc),
    )
    assert REVIEW_FINGERPRINT_MISMATCH in package.blocking_reason_codes
    assert package.handoff_allowed is False


def test_build_source_fingerprint_mismatch():
    summary, gate, review = _ready_inputs()
    review = FakeReviewRecord(
        version="0.60.0-dev",
        record_fingerprint="review1",
        source_decision_fingerprint="gate-OTHER",
        accepted=True,
        human_approval_recorded=True,
        execution_approval_granted=False,
        reviewer_decision="APPROVE_FOR_RESEARCH",
        created_at=datetime.now(timezone.utc),
    )
    package = build_research_governance_handoff_package(
        summary,
        gate,
        review,
        GovernanceHandoffConfig(),
        built_at=datetime.now(timezone.utc),
    )
    assert GOVERNANCE_FINGERPRINT_MISMATCH in package.blocking_reason_codes
    assert package.handoff_allowed is False


def test_build_missing_review_not_required():
    summary, gate, _ = _ready_inputs()
    summary = FakeGovernanceSummary(
        version="0.61.0-dev",
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status=READY_FOR_RESEARCH_HANDOFF,
        review_summary=FakeReviewSummary(None),
    )
    cfg = GovernanceHandoffConfig(require_latest_accepted_review=False)
    package = build_research_governance_handoff_package(
        summary,
        gate,
        None,
        cfg,
        built_at=datetime.now(timezone.utc),
        metadata={"note": "review waived by config"},
    )
    assert package.review_source is None
    assert package.governance_status == READY_FOR_RESEARCH_HANDOFF
    assert package.handoff_allowed is True


def test_build_rejects_invalid_config():
    with pytest.raises(GovernanceHandoffError):
        build_research_governance_handoff_package(
            None,
            None,
            None,
            config="not-a-config",  # type: ignore[arg-type]
            built_at=datetime.now(timezone.utc),
        )


def test_build_rejects_naive_built_at():
    summary, gate, review = _ready_inputs()
    with pytest.raises(ValueError):
        build_research_governance_handoff_package(
            summary,
            gate,
            review,
            GovernanceHandoffConfig(),
            built_at=datetime.utcnow(),
        )


def test_package_fingerprint_determinism():
    summary, gate, review = _ready_inputs()
    built_at = datetime.fromisoformat("2026-07-14T12:00:00+00:00")
    cfg = GovernanceHandoffConfig()
    package1 = build_research_governance_handoff_package(
        summary, gate, review, cfg, built_at=built_at, metadata={"run_id": "r1"}
    )
    package2 = build_research_governance_handoff_package(
        summary, gate, review, cfg, built_at=built_at, metadata={"run_id": "r1"}
    )
    assert package1.package_fingerprint == package2.package_fingerprint


def test_package_fingerprint_differs_with_inputs():
    summary, gate, review = _ready_inputs()
    built_at = datetime.fromisoformat("2026-07-14T12:00:00+00:00")
    cfg = GovernanceHandoffConfig()
    package1 = build_research_governance_handoff_package(
        summary, gate, review, cfg, built_at=built_at, metadata={"run_id": "r1"}
    )
    summary2 = FakeGovernanceSummary(
        version="0.61.0-dev",
        governance_fingerprint="gov2",
        gate_decision_fingerprint="gate1",
        governance_status=READY_FOR_RESEARCH_HANDOFF,
        review_summary=FakeReviewSummary("review1"),
    )
    package2 = build_research_governance_handoff_package(
        summary2, gate, review, cfg, built_at=built_at, metadata={"run_id": "r1"}
    )
    assert package1.package_fingerprint != package2.package_fingerprint


def test_compute_package_fingerprint_signature():
    gov = HandoffSourceReference(
        source_name="governance_summary",
        source_version="0.61.0-dev",
        fingerprint="gov1",
        accepted=True,
        reason_codes=(),
    )
    gate = HandoffSourceReference(
        source_name="research_decision_gate",
        source_version="0.59.0-dev",
        fingerprint="gate1",
        accepted=True,
        reason_codes=(),
    )
    review = HandoffSourceReference(
        source_name="human_review_registry",
        source_version="0.60.0-dev",
        fingerprint="review1",
        accepted=True,
        reason_codes=(),
    )
    fp = compute_package_fingerprint(
        governance_status=READY_FOR_RESEARCH_HANDOFF,
        handoff_allowed=True,
        governance_source=gov,
        gate_source=gate,
        review_source=review,
        blocking_reason_codes=(),
        review_reason_codes=(),
        safety_flags={"research_only": True},
        artifact_filenames={"json": "x.json"},
        source_versions={"governance_summary": "0.61.0-dev"},
        config=GovernanceHandoffConfig(),
        built_at=datetime.fromisoformat("2026-07-14T12:00:00+00:00"),
    )
    assert isinstance(fp, str)
    assert len(fp) == 64
