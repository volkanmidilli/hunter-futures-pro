"""Tests for governance handoff provenance validator (MVP-62 Step 2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from hunter.governance_handoff.models import (
    GATE_FINGERPRINT_MISMATCH,
    GOVERNANCE_FINGERPRINT_MISMATCH,
    INVALID_GATE_REPORT,
    INVALID_GOVERNANCE_SUMMARY,
    INVALID_REVIEW_RECORD,
    INVALID_TIMESTAMP,
    MISSING_GATE_REPORT,
    MISSING_GOVERNANCE_SUMMARY,
    MISSING_LATEST_ACCEPTED_REVIEW,
    MISSING_REQUIRED_FINGERPRINT,
    REVIEW_FINGERPRINT_MISMATCH,
    SOURCE_VERSION_MISMATCH,
    UNSAFE_HANDOFF_FLAG,
    GovernanceHandoffConfig,
)
from hunter.governance_handoff.validator import (
    validate_all,
    validate_built_at,
    validate_gate_report,
    validate_governance_summary,
    validate_latest_review,
    validate_provenance_links,
    validate_safety_flags,
    validate_source_versions,
)


@dataclass(frozen=True)
class FakeGovernanceSummary:
    governance_fingerprint: str
    gate_decision_fingerprint: str
    governance_status: str
    review_summary: object | None
    research_only: bool = True
    execution_approval_granted: bool = False


@dataclass(frozen=True)
class FakeReviewSummary:
    latest_accepted_record_fingerprint: str | None


@dataclass(frozen=True)
class FakeGateReport:
    decision: str
    decision_fingerprint: str
    research_only: bool = True
    human_approval_required: bool = True
    execution_approval_granted: bool = False


@dataclass(frozen=True)
class FakeReviewRecord:
    record_fingerprint: str
    accepted: bool
    human_approval_recorded: bool
    execution_approval_granted: bool
    reviewer_decision: str
    source_decision_fingerprint: str
    created_at: datetime


def test_validate_built_at_ok():
    assert validate_built_at(datetime.now(timezone.utc)) == ()


def test_validate_built_at_rejects_naive():
    assert validate_built_at(datetime.utcnow()) == (INVALID_TIMESTAMP,)


def test_validate_built_at_rejects_non_datetime():
    assert validate_built_at("now") == (INVALID_TIMESTAMP,)


def test_validate_governance_summary_ok():
    summary = FakeGovernanceSummary(
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status="READY_FOR_RESEARCH_HANDOFF",
        review_summary=FakeReviewSummary("review1"),
    )
    assert validate_governance_summary(summary) == ()


def test_validate_governance_summary_missing():
    assert validate_governance_summary(None) == (MISSING_GOVERNANCE_SUMMARY,)


def test_validate_governance_summary_invalid_type():
    assert validate_governance_summary("not-a-summary") == (INVALID_GOVERNANCE_SUMMARY,)


def test_validate_governance_summary_missing_fingerprints():
    summary = FakeGovernanceSummary(
        governance_fingerprint="",
        gate_decision_fingerprint="gate1",
        governance_status="READY_FOR_RESEARCH_HANDOFF",
        review_summary=FakeReviewSummary("review1"),
    )
    assert MISSING_REQUIRED_FINGERPRINT in validate_governance_summary(summary)


def test_validate_governance_summary_invalid_status():
    summary = FakeGovernanceSummary(
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status="UNKNOWN",
        review_summary=FakeReviewSummary("review1"),
    )
    assert INVALID_GOVERNANCE_SUMMARY in validate_governance_summary(summary)


def test_validate_governance_summary_missing_review_summary():
    summary = FakeGovernanceSummary(
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status="READY_FOR_RESEARCH_HANDOFF",
        review_summary=None,
    )
    assert INVALID_GOVERNANCE_SUMMARY in validate_governance_summary(summary)


def test_validate_governance_summary_unsafe_flag():
    summary = FakeGovernanceSummary(
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status="READY_FOR_RESEARCH_HANDOFF",
        review_summary=FakeReviewSummary("review1"),
        research_only=False,
    )
    assert UNSAFE_HANDOFF_FLAG in validate_governance_summary(summary)


def test_validate_gate_report_ok():
    gate = FakeGateReport(decision="GO", decision_fingerprint="gate1")
    assert validate_gate_report(gate) == ()


def test_validate_gate_report_missing():
    assert validate_gate_report(None) == (MISSING_GATE_REPORT,)


def test_validate_gate_report_invalid_type():
    assert validate_gate_report(123) == (INVALID_GATE_REPORT,)


def test_validate_gate_report_invalid_decision():
    gate = FakeGateReport(decision="MAYBE", decision_fingerprint="gate1")
    assert INVALID_GATE_REPORT in validate_gate_report(gate)


def test_validate_gate_report_missing_fingerprint():
    gate = FakeGateReport(decision="GO", decision_fingerprint="")
    assert MISSING_REQUIRED_FINGERPRINT in validate_gate_report(gate)


def test_validate_gate_report_unsafe_flag():
    gate = FakeGateReport(
        decision="GO",
        decision_fingerprint="gate1",
        human_approval_required=False,
    )
    assert UNSAFE_HANDOFF_FLAG in validate_gate_report(gate)


def test_validate_latest_review_ok():
    review = FakeReviewRecord(
        record_fingerprint="review1",
        accepted=True,
        human_approval_recorded=True,
        execution_approval_granted=False,
        reviewer_decision="APPROVE_FOR_RESEARCH",
        source_decision_fingerprint="gate1",
        created_at=datetime.now(timezone.utc),
    )
    assert validate_latest_review(review, GovernanceHandoffConfig()) == ()


def test_validate_latest_review_missing_required():
    assert validate_latest_review(None, GovernanceHandoffConfig()) == (
        MISSING_LATEST_ACCEPTED_REVIEW,
    )


def test_validate_latest_review_missing_not_required():
    cfg = GovernanceHandoffConfig(require_latest_accepted_review=False)
    assert validate_latest_review(None, cfg) == ()


def test_validate_latest_review_invalid_type():
    assert validate_latest_review("not-a-record", GovernanceHandoffConfig()) == (
        INVALID_REVIEW_RECORD,
    )


def test_validate_latest_review_not_accepted():
    review = FakeReviewRecord(
        record_fingerprint="review1",
        accepted=False,
        human_approval_recorded=True,
        execution_approval_granted=False,
        reviewer_decision="APPROVE_FOR_RESEARCH",
        source_decision_fingerprint="gate1",
        created_at=datetime.now(timezone.utc),
    )
    assert INVALID_REVIEW_RECORD in validate_latest_review(review, GovernanceHandoffConfig())


def test_validate_latest_review_missing_human_approval_recorded():
    review = FakeReviewRecord(
        record_fingerprint="review1",
        accepted=True,
        human_approval_recorded=False,
        execution_approval_granted=False,
        reviewer_decision="APPROVE_FOR_RESEARCH",
        source_decision_fingerprint="gate1",
        created_at=datetime.now(timezone.utc),
    )
    assert INVALID_REVIEW_RECORD in validate_latest_review(review, GovernanceHandoffConfig())


def test_validate_latest_review_execution_approval_granted():
    review = FakeReviewRecord(
        record_fingerprint="review1",
        accepted=True,
        human_approval_recorded=True,
        execution_approval_granted=True,
        reviewer_decision="APPROVE_FOR_RESEARCH",
        source_decision_fingerprint="gate1",
        created_at=datetime.now(timezone.utc),
    )
    assert UNSAFE_HANDOFF_FLAG in validate_latest_review(review, GovernanceHandoffConfig())


def test_validate_latest_review_naive_timestamp():
    review = FakeReviewRecord(
        record_fingerprint="review1",
        accepted=True,
        human_approval_recorded=True,
        execution_approval_granted=False,
        reviewer_decision="APPROVE_FOR_RESEARCH",
        source_decision_fingerprint="gate1",
        created_at=datetime.utcnow(),
    )
    assert INVALID_TIMESTAMP in validate_latest_review(review, GovernanceHandoffConfig())


def test_validate_source_versions_ok():
    assert validate_source_versions({"gate": "0.59.0-dev"}) == ()


def test_validate_source_versions_missing():
    assert validate_source_versions(None) == (SOURCE_VERSION_MISMATCH,)


def test_validate_source_versions_empty_name():
    assert validate_source_versions({"": "0.59.0-dev"}) == (SOURCE_VERSION_MISMATCH,)


def test_validate_source_versions_empty_version():
    assert validate_source_versions({"gate": ""}) == (SOURCE_VERSION_MISMATCH,)


def test_validate_safety_flags_ok():
    assert validate_safety_flags(
        {
            "research_only": True,
            "execution_approval_granted": False,
            "production_approval_granted": False,
            "live_trading_allowed": False,
            "automatic_execution_allowed": False,
        }
    ) == ()


def test_validate_safety_flags_missing():
    assert validate_safety_flags(None) == (UNSAFE_HANDOFF_FLAG,)


def test_validate_safety_flags_contradiction():
    assert (
        validate_safety_flags(
            {
                "research_only": False,
                "execution_approval_granted": False,
                "production_approval_granted": False,
                "live_trading_allowed": False,
                "automatic_execution_allowed": False,
            }
        )
        == (UNSAFE_HANDOFF_FLAG,)
    )


def test_validate_provenance_links_ok():
    summary = FakeGovernanceSummary(
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status="READY_FOR_RESEARCH_HANDOFF",
        review_summary=FakeReviewSummary("review1"),
    )
    gate = FakeGateReport(decision="GO", decision_fingerprint="gate1")
    review = FakeReviewRecord(
        record_fingerprint="review1",
        accepted=True,
        human_approval_recorded=True,
        execution_approval_granted=False,
        reviewer_decision="APPROVE_FOR_RESEARCH",
        source_decision_fingerprint="gate1",
        created_at=datetime.now(timezone.utc),
    )
    assert validate_provenance_links(summary, gate, review) == ()


def test_validate_provenance_links_gate_mismatch():
    summary = FakeGovernanceSummary(
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate-OTHER",
        governance_status="READY_FOR_RESEARCH_HANDOFF",
        review_summary=FakeReviewSummary("review1"),
    )
    gate = FakeGateReport(decision="GO", decision_fingerprint="gate1")
    assert validate_provenance_links(summary, gate, None) == (GATE_FINGERPRINT_MISMATCH,)


def test_validate_provenance_links_review_mismatch():
    summary = FakeGovernanceSummary(
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status="READY_FOR_RESEARCH_HANDOFF",
        review_summary=FakeReviewSummary("review-OTHER"),
    )
    review = FakeReviewRecord(
        record_fingerprint="review1",
        accepted=True,
        human_approval_recorded=True,
        execution_approval_granted=False,
        reviewer_decision="APPROVE_FOR_RESEARCH",
        source_decision_fingerprint="gate1",
        created_at=datetime.now(timezone.utc),
    )
    assert validate_provenance_links(summary, None, review) == (REVIEW_FINGERPRINT_MISMATCH,)


def test_validate_provenance_links_source_fingerprint_mismatch():
    summary = FakeGovernanceSummary(
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status="READY_FOR_RESEARCH_HANDOFF",
        review_summary=FakeReviewSummary("review1"),
    )
    gate = FakeGateReport(decision="GO", decision_fingerprint="gate1")
    review = FakeReviewRecord(
        record_fingerprint="review1",
        accepted=True,
        human_approval_recorded=True,
        execution_approval_granted=False,
        reviewer_decision="APPROVE_FOR_RESEARCH",
        source_decision_fingerprint="gate-OTHER",
        created_at=datetime.now(timezone.utc),
    )
    assert validate_provenance_links(summary, gate, review) == (
        GOVERNANCE_FINGERPRINT_MISMATCH,
    )


def test_validate_all_ready():
    summary = FakeGovernanceSummary(
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status="READY_FOR_RESEARCH_HANDOFF",
        review_summary=FakeReviewSummary("review1"),
    )
    gate = FakeGateReport(decision="GO", decision_fingerprint="gate1")
    review = FakeReviewRecord(
        record_fingerprint="review1",
        accepted=True,
        human_approval_recorded=True,
        execution_approval_granted=False,
        reviewer_decision="APPROVE_FOR_RESEARCH",
        source_decision_fingerprint="gate1",
        created_at=datetime.now(timezone.utc),
    )
    assert validate_all(summary, gate, review, GovernanceHandoffConfig(), built_at=datetime.now(timezone.utc)) == ()


def test_validate_all_missing_inputs():
    assert validate_all(None, None, None, GovernanceHandoffConfig(), built_at=datetime.now(timezone.utc)) == (
        MISSING_GATE_REPORT,
        MISSING_GOVERNANCE_SUMMARY,
        MISSING_LATEST_ACCEPTED_REVIEW,
    )


def test_validate_all_dedupes_reasons():
    summary = FakeGovernanceSummary(
        governance_fingerprint="",
        gate_decision_fingerprint="gate1",
        governance_status="READY_FOR_RESEARCH_HANDOFF",
        review_summary=FakeReviewSummary("review1"),
    )
    gate = FakeGateReport(decision="GO", decision_fingerprint="")
    review = FakeReviewRecord(
        record_fingerprint="",
        accepted=True,
        human_approval_recorded=True,
        execution_approval_granted=False,
        reviewer_decision="APPROVE_FOR_RESEARCH",
        source_decision_fingerprint="gate1",
        created_at=datetime.now(timezone.utc),
    )
    reasons = validate_all(summary, gate, review, GovernanceHandoffConfig(), built_at=datetime.now(timezone.utc))
    assert reasons.count(MISSING_REQUIRED_FINGERPRINT) == 1
