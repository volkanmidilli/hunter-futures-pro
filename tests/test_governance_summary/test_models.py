"""Tests for governance summary models."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.governance_summary.models import (
    BLOCKED,
    BROKEN_REVIEW_CHAIN,
    CONTRADICTORY_GOVERNANCE_STATE,
    DEFAULT_JSON_FILENAME,
    DEFAULT_MARKDOWN_FILENAME,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REPORT_OUTPUT_DIR,
    DEFAULT_REQUIRE_REVIEW_CHAIN,
    DUPLICATE_REVIEW_RECORD,
    GATE_DECISION_NO_GO,
    GATE_REVIEW_REQUIRED,
    GOVERNANCE_BLOCKING_REASON_CODES,
    GOVERNANCE_REASON_CODES,
    GOVERNANCE_REVIEW_REQUIRED_REASON_CODES,
    GOVERNANCE_STATUSES,
    GOVERNANCE_SUMMARY_VERSION,
    GovernanceDecisionSummary,
    GovernanceReviewSummary,
    GovernanceSummaryConfig,
    GovernanceSummaryError,
    INCOMPLETE_PROVENANCE,
    INVALID_GATE_REPORT,
    INVALID_TIMESTAMP,
    LATEST_REVIEW_REJECTED,
    LATEST_REVIEW_REQUESTS_CHANGES,
    MISSING_GATE_REPORT,
    MISSING_REQUIRED_FINGERPRINT,
    MISSING_REVIEW_CHAIN,
    NO_ACCEPTED_REVIEW,
    OPEN_CHANGE_REQUEST,
    READY_FOR_RESEARCH_HANDOFF,
    REVIEW_REQUIRED,
    TAMPERED_REVIEW_RECORD,
    UNKNOWN_NON_BLOCKING_FIELD,
    UNSAFE_GOVERNANCE_FLAG,
)


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def config(tmp_path: Path) -> GovernanceSummaryConfig:
    return GovernanceSummaryConfig(
        require_review_chain=True,
        output_dir=tmp_path / "data",
        report_output_dir=tmp_path / "reports",
        json_filename="summary.json",
        markdown_filename="summary.md",
    )


@pytest.fixture
def review_summary(now: datetime) -> GovernanceReviewSummary:
    return GovernanceReviewSummary(
        total_records=2,
        accepted_records=1,
        rejected_attempts=1,
        chain_valid=True,
        latest_accepted_record_fingerprint="fp-latest",
        latest_reviewer_identity="reviewer-a",
        latest_reviewer_decision="APPROVE_FOR_RESEARCH",
        latest_review_created_at=now,
        open_change_request_count=0,
        source_decision_fingerprints=("fp1", "fp2"),
        reason_codes=(),
    )


class TestVersionAndConstants:
    def test_version(self) -> None:
        assert GOVERNANCE_SUMMARY_VERSION == "0.61.0-dev"

    def test_statuses(self) -> None:
        assert GOVERNANCE_STATUSES == {
            READY_FOR_RESEARCH_HANDOFF,
            REVIEW_REQUIRED,
            BLOCKED,
        }

    def test_blocking_reason_codes(self) -> None:
        assert GOVERNANCE_BLOCKING_REASON_CODES == {
            MISSING_GATE_REPORT,
            INVALID_GATE_REPORT,
            GATE_DECISION_NO_GO,
            MISSING_REVIEW_CHAIN,
            BROKEN_REVIEW_CHAIN,
            TAMPERED_REVIEW_RECORD,
            DUPLICATE_REVIEW_RECORD,
            CONTRADICTORY_GOVERNANCE_STATE,
            MISSING_REQUIRED_FINGERPRINT,
            UNSAFE_GOVERNANCE_FLAG,
            INVALID_TIMESTAMP,
        }

    def test_review_required_reason_codes(self) -> None:
        assert GOVERNANCE_REVIEW_REQUIRED_REASON_CODES == {
            NO_ACCEPTED_REVIEW,
            GATE_REVIEW_REQUIRED,
            OPEN_CHANGE_REQUEST,
            LATEST_REVIEW_REJECTED,
            LATEST_REVIEW_REQUESTS_CHANGES,
            INCOMPLETE_PROVENANCE,
            UNKNOWN_NON_BLOCKING_FIELD,
        }

    def test_all_reason_codes_disjoint(self) -> None:
        assert not (
            GOVERNANCE_BLOCKING_REASON_CODES & GOVERNANCE_REVIEW_REQUIRED_REASON_CODES
        )
        assert GOVERNANCE_REASON_CODES == (
            GOVERNANCE_BLOCKING_REASON_CODES | GOVERNANCE_REVIEW_REQUIRED_REASON_CODES
        )

    def test_defaults(self) -> None:
        assert DEFAULT_REQUIRE_REVIEW_CHAIN is True
        assert DEFAULT_OUTPUT_DIR == Path("data/governance_summary")
        assert DEFAULT_REPORT_OUTPUT_DIR == Path("reports/governance_summary")
        assert DEFAULT_JSON_FILENAME == "latest_governance_summary.json"
        assert DEFAULT_MARKDOWN_FILENAME == "latest_governance_summary.md"


class TestGovernanceSummaryConfig:
    def test_default(self) -> None:
        cfg = GovernanceSummaryConfig.default()
        assert cfg.require_review_chain is True
        assert cfg.output_dir == DEFAULT_OUTPUT_DIR
        assert cfg.report_output_dir == DEFAULT_REPORT_OUTPUT_DIR

    def test_coerces_path_strings(self, tmp_path: Path) -> None:
        cfg = GovernanceSummaryConfig(
            output_dir=str(tmp_path / "data"),
            report_output_dir=str(tmp_path / "reports"),
        )
        assert isinstance(cfg.output_dir, Path)
        assert isinstance(cfg.report_output_dir, Path)

    def test_invalid_require_review_chain(self) -> None:
        with pytest.raises(ValueError):
            GovernanceSummaryConfig(require_review_chain="yes")

    def test_empty_json_filename(self) -> None:
        with pytest.raises(ValueError):
            GovernanceSummaryConfig(json_filename="")

    def test_empty_markdown_filename(self) -> None:
        with pytest.raises(ValueError):
            GovernanceSummaryConfig(markdown_filename="")

    def test_metadata_coerced(self) -> None:
        cfg = GovernanceSummaryConfig(metadata={"key": [1, 2, {"nested": True}]})
        assert cfg.metadata == {"key": [1, 2, {"nested": True}]}

    def test_metadata_rejects_non_json(self) -> None:
        with pytest.raises(TypeError):
            GovernanceSummaryConfig(metadata={"key": object()})


class TestGovernanceReviewSummary:
    def test_valid(self, now: datetime) -> None:
        summary = GovernanceReviewSummary(
            total_records=0,
            accepted_records=0,
            rejected_attempts=0,
            chain_valid=True,
            latest_accepted_record_fingerprint=None,
            latest_reviewer_identity=None,
            latest_reviewer_decision=None,
            latest_review_created_at=None,
            open_change_request_count=0,
            source_decision_fingerprints=(),
            reason_codes=(),
        )
        assert summary.total_records == 0

    def test_reason_codes_validated(self) -> None:
        with pytest.raises(ValueError):
            GovernanceReviewSummary(
                total_records=1,
                accepted_records=1,
                rejected_attempts=0,
                chain_valid=True,
                latest_accepted_record_fingerprint="fp",
                latest_reviewer_identity="r",
                latest_reviewer_decision="APPROVE_FOR_RESEARCH",
                latest_review_created_at=datetime.now(timezone.utc),
                open_change_request_count=0,
                source_decision_fingerprints=(),
                reason_codes=("UNKNOWN_CODE",),
            )

    def test_tuple_coercion(self, now: datetime) -> None:
        summary = GovernanceReviewSummary(
            total_records=1,
            accepted_records=1,
            rejected_attempts=0,
            chain_valid=True,
            latest_accepted_record_fingerprint="fp",
            latest_reviewer_identity="r",
            latest_reviewer_decision="APPROVE_FOR_RESEARCH",
            latest_review_created_at=now,
            open_change_request_count=0,
            source_decision_fingerprints=["fp1"],
            reason_codes=[NO_ACCEPTED_REVIEW],
        )
        assert isinstance(summary.source_decision_fingerprints, tuple)
        assert isinstance(summary.reason_codes, tuple)


class TestGovernanceDecisionSummary:
    def test_valid(self, now: datetime, review_summary: GovernanceReviewSummary) -> None:
        summary = GovernanceDecisionSummary(
            version=GOVERNANCE_SUMMARY_VERSION,
            governance_status=READY_FOR_RESEARCH_HANDOFF,
            governance_fingerprint="fp-governance",
            evaluated_at=now,
            gate_decision="GO",
            gate_decision_fingerprint="fp-gate",
            review_summary=review_summary,
            blocking_reason_codes=(),
            review_reason_codes=(),
            research_only=True,
            human_review_required=True,
            execution_approval_granted=False,
        )
        assert summary.governance_status == READY_FOR_RESEARCH_HANDOFF

    def test_invalid_status(self, now: datetime, review_summary: GovernanceReviewSummary) -> None:
        with pytest.raises(ValueError):
            GovernanceDecisionSummary(
                version=GOVERNANCE_SUMMARY_VERSION,
                governance_status="APPROVED",
                governance_fingerprint="fp",
                evaluated_at=now,
                gate_decision="GO",
                gate_decision_fingerprint="fp-gate",
                review_summary=review_summary,
                blocking_reason_codes=(),
                review_reason_codes=(),
                research_only=True,
                human_review_required=True,
                execution_approval_granted=False,
            )

    def test_safety_invariants(self, now: datetime, review_summary: GovernanceReviewSummary) -> None:
        with pytest.raises(ValueError):
            GovernanceDecisionSummary(
                version=GOVERNANCE_SUMMARY_VERSION,
                governance_status=READY_FOR_RESEARCH_HANDOFF,
                governance_fingerprint="fp",
                evaluated_at=now,
                gate_decision="GO",
                gate_decision_fingerprint="fp-gate",
                review_summary=review_summary,
                blocking_reason_codes=(),
                review_reason_codes=(),
                research_only=False,
                human_review_required=True,
                execution_approval_granted=False,
            )

    def test_execution_approval_must_be_false(
        self, now: datetime, review_summary: GovernanceReviewSummary
    ) -> None:
        with pytest.raises(ValueError):
            GovernanceDecisionSummary(
                version=GOVERNANCE_SUMMARY_VERSION,
                governance_status=READY_FOR_RESEARCH_HANDOFF,
                governance_fingerprint="fp",
                evaluated_at=now,
                gate_decision="GO",
                gate_decision_fingerprint="fp-gate",
                review_summary=review_summary,
                blocking_reason_codes=(),
                review_reason_codes=(),
                research_only=True,
                human_review_required=True,
                execution_approval_granted=True,
            )

    def test_blocking_reason_codes_validated(
        self, now: datetime, review_summary: GovernanceReviewSummary
    ) -> None:
        with pytest.raises(ValueError):
            GovernanceDecisionSummary(
                version=GOVERNANCE_SUMMARY_VERSION,
                governance_status=BLOCKED,
                governance_fingerprint="fp",
                evaluated_at=now,
                gate_decision="NO_GO",
                gate_decision_fingerprint="fp-gate",
                review_summary=review_summary,
                blocking_reason_codes=("UNKNOWN",),
                review_reason_codes=(),
                research_only=True,
                human_review_required=True,
                execution_approval_granted=False,
            )

    def test_review_reason_codes_validated(
        self, now: datetime, review_summary: GovernanceReviewSummary
    ) -> None:
        with pytest.raises(ValueError):
            GovernanceDecisionSummary(
                version=GOVERNANCE_SUMMARY_VERSION,
                governance_status=REVIEW_REQUIRED,
                governance_fingerprint="fp",
                evaluated_at=now,
                gate_decision="NEEDS_REVIEW",
                gate_decision_fingerprint="fp-gate",
                review_summary=review_summary,
                blocking_reason_codes=(),
                review_reason_codes=("UNKNOWN",),
                research_only=True,
                human_review_required=True,
                execution_approval_granted=False,
            )


class TestGovernanceSummaryError:
    def test_reason_code(self) -> None:
        err = GovernanceSummaryError("msg", reason_code="CODE")
        assert err.reason_code == "CODE"
