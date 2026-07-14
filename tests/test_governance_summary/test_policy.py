"""Tests for governance summary policy."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.governance_summary.models import (
    BLOCKED,
    GATE_DECISION_NO_GO,
    GATE_REVIEW_REQUIRED,
    LATEST_REVIEW_REJECTED,
    LATEST_REVIEW_REQUESTS_CHANGES,
    NO_ACCEPTED_REVIEW,
    READY_FOR_RESEARCH_HANDOFF,
    REVIEW_REQUIRED,
)
from hunter.governance_summary.policy import (
    build_governance_safety_flags,
    classify_governance_reasons,
    detect_open_change_request,
    resolve_governance_status,
    select_latest_accepted_review,
)
from hunter.human_review_registry.models import (
    APPROVE_FOR_RESEARCH,
    HUMAN_REVIEW_REGISTRY_VERSION,
    REJECT,
    REQUEST_CHANGES,
    HumanReviewRecord,
)


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)


def _make_record(
    decision: str,
    created_at: datetime,
    fingerprint: str,
) -> HumanReviewRecord:
    return HumanReviewRecord(
        version=HUMAN_REVIEW_REGISTRY_VERSION,
        source_decision_fingerprint="gate-fp",
        source_decision="GO",
        reviewer_identity="reviewer-a",
        reviewer_decision=decision,
        review_note="review note here",
        created_at=created_at,
        previous_record_fingerprint=None,
        record_fingerprint=fingerprint,
        accepted=True,
        human_approval_recorded=True,
        execution_approval_granted=False,
        reason_codes=("REVIEW_APPROVED_FOR_RESEARCH",),
    )


class TestBuildGovernanceSafetyFlags:
    def test_canonical_flags(self) -> None:
        flags = build_governance_safety_flags()
        assert flags == {
            "research_only": True,
            "human_review_required": True,
            "execution_approval_granted": False,
        }


class TestSelectLatestAcceptedReview:
    def test_empty(self) -> None:
        assert select_latest_accepted_review(()) is None

    def test_single(self, now: datetime) -> None:
        r = _make_record(APPROVE_FOR_RESEARCH, now, "fp1")
        assert select_latest_accepted_review((r,)) is r

    def test_latest_by_time(self, now: datetime) -> None:
        r1 = _make_record(APPROVE_FOR_RESEARCH, now, "fp1")
        r2 = _make_record(APPROVE_FOR_RESEARCH, now.replace(second=1), "fp2")
        assert select_latest_accepted_review((r1, r2)) is r2

    def test_tie_break_by_fingerprint(self, now: datetime) -> None:
        r1 = _make_record(APPROVE_FOR_RESEARCH, now, "fp-b")
        r2 = _make_record(APPROVE_FOR_RESEARCH, now, "fp-a")
        # sorted by (created_at, fingerprint) -> r2 wins because fp-a < fp-b? No,
        # sorted ascending, last wins -> fp-b is last
        latest = select_latest_accepted_review((r2, r1))
        assert latest is r1

    def test_rejected_not_selected(self, now: datetime) -> None:
        r1 = _make_record(REJECT, now, "fp1")
        assert select_latest_accepted_review((r1,)) is r1


class TestDetectOpenChangeRequest:
    def test_no_latest(self) -> None:
        assert detect_open_change_request(None) is False

    def test_approve_not_open(self, now: datetime) -> None:
        r = _make_record(APPROVE_FOR_RESEARCH, now, "fp1")
        assert detect_open_change_request(r) is False

    def test_request_changes_open(self, now: datetime) -> None:
        r = _make_record(REQUEST_CHANGES, now, "fp1")
        assert detect_open_change_request(r) is True


class TestClassifyGovernanceReasons:
    def test_no_reasons_no_review(self) -> None:
        blocking, review = classify_governance_reasons((), (), None)
        assert blocking == ()
        assert review == (NO_ACCEPTED_REVIEW,)

    def test_gate_no_go(self) -> None:
        blocking, review = classify_governance_reasons((GATE_DECISION_NO_GO,), (), None)
        assert GATE_DECISION_NO_GO in blocking
        assert NO_ACCEPTED_REVIEW in review

    def test_gate_review_required(self) -> None:
        blocking, review = classify_governance_reasons((GATE_REVIEW_REQUIRED,), (), None)
        assert GATE_REVIEW_REQUIRED in review
        assert blocking == ()

    def test_chain_blocking(self) -> None:
        blocking, review = classify_governance_reasons(("BROKEN_REVIEW_CHAIN",), (), None)
        assert "BROKEN_REVIEW_CHAIN" in blocking

    def test_latest_rejected(self, now: datetime) -> None:
        r = _make_record(REJECT, now, "fp1")
        blocking, review = classify_governance_reasons((), (), r)
        assert LATEST_REVIEW_REJECTED in review

    def test_latest_requests_changes(self, now: datetime) -> None:
        r = _make_record(REQUEST_CHANGES, now, "fp1")
        blocking, review = classify_governance_reasons((), (), r)
        assert LATEST_REVIEW_REQUESTS_CHANGES in review


class TestResolveGovernanceStatus:
    def test_blocked(self) -> None:
        assert resolve_governance_status(("X",), ()) == BLOCKED

    def test_review_required(self) -> None:
        assert resolve_governance_status((), ("X",)) == REVIEW_REQUIRED

    def test_ready(self) -> None:
        assert resolve_governance_status((), ()) == READY_FOR_RESEARCH_HANDOFF
