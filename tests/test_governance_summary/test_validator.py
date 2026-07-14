"""Tests for governance summary validation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from hunter.governance_summary.models import (
    BLOCKED,
    BROKEN_REVIEW_CHAIN,
    DUPLICATE_REVIEW_RECORD,
    GATE_DECISION_NO_GO,
    GATE_REVIEW_REQUIRED,
    INVALID_GATE_REPORT,
    INVALID_TIMESTAMP,
    MISSING_GATE_REPORT,
    MISSING_REQUIRED_FINGERPRINT,
    MISSING_REVIEW_CHAIN,
    READY_FOR_RESEARCH_HANDOFF,
    REVIEW_REQUIRED,
    TAMPERED_REVIEW_RECORD,
    UNSAFE_GOVERNANCE_FLAG,
    GovernanceSummaryConfig,
)
from hunter.governance_summary.validator import (
    build_review_chain_facts,
    validate_evaluated_at,
    validate_gate_report,
    validate_review_records,
)
from hunter.human_review_registry.models import (
    APPROVE_FOR_RESEARCH,
    HUMAN_REVIEW_REGISTRY_VERSION,
    HumanReviewInput,
    HumanReviewRegistryConfig,
)
from hunter.research_decision_gate.models import (
    GO,
    NEEDS_REVIEW,
    NO_GO,
    RESEARCH_DECISION_GATE_VERSION,
    DecisionSourceSummary,
    ResearchDecisionGateConfig,
    ResearchDecisionGateReport,
)


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def config(tmp_path: Path) -> GovernanceSummaryConfig:
    return GovernanceSummaryConfig(
        output_dir=tmp_path / "data",
        report_output_dir=tmp_path / "reports",
    )


def _make_gate_report(
    decision: str = GO,
    fingerprint: str = "gate-fp",
    research_only: bool = True,
    human_approval_required: bool = True,
    now: datetime | None = None,
) -> ResearchDecisionGateReport:
    now = now or datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    summary = DecisionSourceSummary(
        source_name="risk_context",
        present=True,
        accepted=True,
        fresh=True,
        fingerprint="rc-fp",
        reason_codes=(),
    )
    return ResearchDecisionGateReport(
        version=RESEARCH_DECISION_GATE_VERSION,
        decision=decision,  # type: ignore[arg-type]
        decision_fingerprint=fingerprint,
        evaluated_at=now,
        risk_context_summary=summary,
        universe_summary=summary,
        strategy_contract_summary=summary,
        blocking_reason_codes=(),
        review_reason_codes=(),
        safety_flags=MappingProxyType(
            {
                "research_only": research_only,
                "human_approval_required": human_approval_required,
                "automatic_execution_allowed": False,
                "runtime_config_mutation_allowed": False,
                "live_trading_allowed": False,
            }
        ),
        research_only=research_only,
        human_approval_required=human_approval_required,
    )


def _make_review_input(decision: str = APPROVE_FOR_RESEARCH, note: str = "approved for research") -> HumanReviewInput:
    return HumanReviewInput(
        reviewer_identity="reviewer-a",
        reviewer_decision=decision,  # type: ignore[arg-type]
        review_note=note,
    )


def _make_record(
    gate_report: ResearchDecisionGateReport,
    review_input: HumanReviewInput,
    created_at: datetime,
    previous_record: HumanReviewRecord | None = None,  # type: ignore[name-defined]
) -> HumanReviewRecord:  # type: ignore[name-defined]
    from hunter.human_review_registry.engine import build_human_review_record

    kwargs: dict = {}
    if previous_record is not None:
        kwargs["previous_record"] = previous_record
    return build_human_review_record(
        decision_report=gate_report,
        review_input=review_input,
        config=HumanReviewRegistryConfig(),
        created_at=created_at,
        **kwargs,
    )


class TestValidateGateReport:
    def test_missing_gate_report(self) -> None:
        assert validate_gate_report(None) == (MISSING_GATE_REPORT,)

    def test_invalid_gate_report(self) -> None:
        assert INVALID_GATE_REPORT in validate_gate_report(object())

    def test_go_is_valid(self, now: datetime) -> None:
        report = _make_gate_report(decision=GO, now=now)
        assert validate_gate_report(report) == ()

    def test_no_go_blocked(self, now: datetime) -> None:
        report = _make_gate_report(decision=NO_GO, now=now)
        assert GATE_DECISION_NO_GO in validate_gate_report(report)

    def test_needs_review(self, now: datetime) -> None:
        report = _make_gate_report(decision=NEEDS_REVIEW, now=now)
        assert GATE_REVIEW_REQUIRED in validate_gate_report(report)

    def test_missing_fingerprint(self, now: datetime) -> None:
        class FakeReport:
            decision = GO
            decision_fingerprint = ""
            research_only = True
            human_approval_required = True

        assert MISSING_REQUIRED_FINGERPRINT in validate_gate_report(FakeReport())

    def test_unsafe_research_flag(self) -> None:
        class FakeReport:
            decision = GO
            decision_fingerprint = "fp"
            research_only = False
            human_approval_required = True

        assert UNSAFE_GOVERNANCE_FLAG in validate_gate_report(FakeReport())

    def test_unsafe_approval_flag(self) -> None:
        class FakeReport:
            decision = GO
            decision_fingerprint = "fp"
            research_only = True
            human_approval_required = False

        assert UNSAFE_GOVERNANCE_FLAG in validate_gate_report(FakeReport())


class TestValidateReviewRecords:
    def test_empty_chain_required(self, config: GovernanceSummaryConfig) -> None:
        assert validate_review_records((), config) == (MISSING_REVIEW_CHAIN,)

    def test_empty_chain_optional(self) -> None:
        cfg = GovernanceSummaryConfig(require_review_chain=False)
        assert validate_review_records((), cfg) == ()

    def test_valid_chain(self, now: datetime) -> None:
        gate = _make_gate_report(now=now)
        r1 = _make_record(gate, _make_review_input(), now)
        assert validate_review_records((r1,), config=GovernanceSummaryConfig()) == ()

    def test_broken_chain(self, now: datetime) -> None:
        from hunter.human_review_registry.chain import compute_record_fingerprint
        from hunter.human_review_registry.models import HumanReviewRecord

        gate = _make_gate_report(now=now)
        r1 = _make_record(gate, _make_review_input(), now)
        # Build r2 with a valid fingerprint but pointing to the wrong previous
        # record fingerprint, so the chain link is broken without tampering.
        r2_fp = compute_record_fingerprint(
            source_decision_fingerprint=gate.decision_fingerprint,
            source_decision=GO,
            reviewer_identity="reviewer-a",
            reviewer_decision=APPROVE_FOR_RESEARCH,
            review_note="second approval note",
            created_at=now,
            previous_record_fingerprint="wrong-fp",
            accepted=True,
            human_approval_recorded=True,
            execution_approval_granted=False,
        )
        r2 = HumanReviewRecord(
            version=HUMAN_REVIEW_REGISTRY_VERSION,
            source_decision_fingerprint=gate.decision_fingerprint,
            source_decision=GO,
            reviewer_identity="reviewer-a",
            reviewer_decision=APPROVE_FOR_RESEARCH,
            review_note="second approval note",
            created_at=now,
            previous_record_fingerprint="wrong-fp",
            record_fingerprint=r2_fp,
            accepted=True,
            human_approval_recorded=True,
            execution_approval_granted=False,
            reason_codes=("REVIEW_APPROVED_FOR_RESEARCH",),
        )
        reasons = validate_review_records((r1, r2), config=GovernanceSummaryConfig())
        assert BROKEN_REVIEW_CHAIN in reasons

    def test_tampered_record(self, now: datetime) -> None:
        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(), now)
        # Mutate via object.__setattr__ because dataclass is frozen
        object.__setattr__(record, "reviewer_identity", "tampered")
        reasons = validate_review_records((record,), config=GovernanceSummaryConfig())
        assert TAMPERED_REVIEW_RECORD in reasons

    def test_duplicate_record(self, now: datetime) -> None:
        gate = _make_gate_report(now=now)
        r1 = _make_record(gate, _make_review_input(), now)
        r2 = _make_record(gate, _make_review_input(), now)
        reasons = validate_review_records((r1, r2), config=GovernanceSummaryConfig())
        assert DUPLICATE_REVIEW_RECORD in reasons


class TestValidateEvaluatedAt:
    def test_valid(self, config: GovernanceSummaryConfig) -> None:
        assert validate_evaluated_at(datetime.now(timezone.utc), config) == ()

    def test_naive_datetime(self, config: GovernanceSummaryConfig) -> None:
        assert validate_evaluated_at(datetime.now(), config) == (INVALID_TIMESTAMP,)

    def test_not_datetime(self, config: GovernanceSummaryConfig) -> None:
        assert validate_evaluated_at("now", config) == (INVALID_TIMESTAMP,)


class TestBuildReviewChainFacts:
    def test_empty(self) -> None:
        facts = build_review_chain_facts(())
        assert facts["total_records"] == 0
        assert facts["accepted_records_count"] == 0

    def test_counts(self, now: datetime) -> None:
        gate = _make_gate_report(now=now)
        r1 = _make_record(gate, _make_review_input(), now)
        facts = build_review_chain_facts((r1,))
        assert facts["total_records"] == 1
        assert facts["accepted_records_count"] == 1
        assert len(facts["accepted_records"]) == 1
