"""Tests for governance summary engine."""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from hunter.governance_summary.engine import (
    build_governance_decision_summary,
    compute_governance_fingerprint,
)
from hunter.governance_summary.models import (
    BLOCKED,
    GATE_DECISION_NO_GO,
    GATE_REVIEW_REQUIRED,
    LATEST_REVIEW_REJECTED,
    LATEST_REVIEW_REQUESTS_CHANGES,
    NO_ACCEPTED_REVIEW,
    OPEN_CHANGE_REQUEST,
    READY_FOR_RESEARCH_HANDOFF,
    REVIEW_REQUIRED,
    GovernanceSummaryConfig,
)
from hunter.human_review_registry.models import (
    APPROVE_FOR_RESEARCH,
    HUMAN_REVIEW_REGISTRY_VERSION,
    REJECT,
    REQUEST_CHANGES,
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
def config(tmp_path) -> GovernanceSummaryConfig:
    return GovernanceSummaryConfig(
        output_dir=tmp_path / "data",
        report_output_dir=tmp_path / "reports",
    )


def _make_gate_report(
    decision: str = GO,
    fingerprint: str = "gate-fp",
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
                "research_only": True,
                "human_approval_required": True,
                "automatic_execution_allowed": False,
                "runtime_config_mutation_allowed": False,
                "live_trading_allowed": False,
            }
        ),
        research_only=True,
        human_approval_required=True,
    )


def _make_review_input(
    decision: str = APPROVE_FOR_RESEARCH,
    note: str = "approved for research",
) -> HumanReviewInput:
    return HumanReviewInput(
        reviewer_identity="reviewer-a",
        reviewer_decision=decision,  # type: ignore[arg-type]
        review_note=note,
    )


def _make_record(
    gate_report: ResearchDecisionGateReport,
    review_input: HumanReviewInput,
    created_at: datetime,
    previous_record=None,  # type: ignore
):
    from hunter.human_review_registry.engine import build_human_review_record

    kwargs = {}
    if previous_record is not None:
        kwargs["previous_record"] = previous_record
    return build_human_review_record(
        decision_report=gate_report,
        review_input=review_input,
        config=HumanReviewRegistryConfig(),
        created_at=created_at,
        **kwargs,
    )


class TestComputeGovernanceFingerprint:
    def test_deterministic(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        fp1 = compute_governance_fingerprint(
            gate_decision=GO,
            gate_decision_fingerprint="gate-fp",
            review_fingerprints=("r1",),
            latest_accepted_record_fingerprint="r1",
            governance_status=READY_FOR_RESEARCH_HANDOFF,
            blocking_reason_codes=(),
            review_reason_codes=(),
            safety_flags={"research_only": True},
            config=config,
            evaluated_at=now,
        )
        fp2 = compute_governance_fingerprint(
            gate_decision=GO,
            gate_decision_fingerprint="gate-fp",
            review_fingerprints=("r1",),
            latest_accepted_record_fingerprint="r1",
            governance_status=READY_FOR_RESEARCH_HANDOFF,
            blocking_reason_codes=(),
            review_reason_codes=(),
            safety_flags={"research_only": True},
            config=config,
            evaluated_at=now,
        )
        assert fp1 == fp2
        assert len(fp1) == 64

    def test_different_evaluated_at(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        fp1 = compute_governance_fingerprint(
            gate_decision=GO,
            gate_decision_fingerprint="gate-fp",
            review_fingerprints=(),
            latest_accepted_record_fingerprint=None,
            governance_status=REVIEW_REQUIRED,
            blocking_reason_codes=(),
            review_reason_codes=(NO_ACCEPTED_REVIEW,),
            safety_flags={"research_only": True},
            config=config,
            evaluated_at=now,
        )
        fp2 = compute_governance_fingerprint(
            gate_decision=GO,
            gate_decision_fingerprint="gate-fp",
            review_fingerprints=(),
            latest_accepted_record_fingerprint=None,
            governance_status=REVIEW_REQUIRED,
            blocking_reason_codes=(),
            review_reason_codes=(NO_ACCEPTED_REVIEW,),
            safety_flags={"research_only": True},
            config=config,
            evaluated_at=now.replace(second=1),
        )
        assert fp1 != fp2


class TestBuildGovernanceDecisionSummary:
    def test_go_approved_ready(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(), now)
        summary = build_governance_decision_summary(
            gate, [record], config, evaluated_at=now
        )
        assert summary.governance_status == READY_FOR_RESEARCH_HANDOFF
        assert summary.research_only is True
        assert summary.execution_approval_granted is False

    def test_go_no_accepted_review(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(now=now)
        summary = build_governance_decision_summary(
            gate, [], config, evaluated_at=now
        )
        assert summary.governance_status == REVIEW_REQUIRED
        assert NO_ACCEPTED_REVIEW in summary.review_reason_codes

    def test_go_rejected_review(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(REJECT), now)
        summary = build_governance_decision_summary(
            gate, [record], config, evaluated_at=now
        )
        assert summary.governance_status == REVIEW_REQUIRED
        assert LATEST_REVIEW_REJECTED in summary.review_reason_codes

    def test_go_change_request(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(REQUEST_CHANGES), now)
        summary = build_governance_decision_summary(
            gate, [record], config, evaluated_at=now
        )
        assert summary.governance_status == REVIEW_REQUIRED
        assert OPEN_CHANGE_REQUEST in summary.review_reason_codes
        assert LATEST_REVIEW_REQUESTS_CHANGES in summary.review_reason_codes

    def test_needs_review_with_approval(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(decision=NEEDS_REVIEW, now=now)
        record = _make_record(
            gate,
            _make_review_input(APPROVE_FOR_RESEARCH, "adequate note here"),
            now,
        )
        summary = build_governance_decision_summary(
            gate, [record], config, evaluated_at=now
        )
        assert summary.governance_status == REVIEW_REQUIRED
        assert GATE_REVIEW_REQUIRED in summary.review_reason_codes

    def test_no_go_blocked(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(decision=NO_GO, now=now)
        record = _make_record(gate, _make_review_input(), now)
        summary = build_governance_decision_summary(
            gate, [record], config, evaluated_at=now
        )
        assert summary.governance_status == BLOCKED
        assert GATE_DECISION_NO_GO in summary.blocking_reason_codes

    def test_missing_gate_blocked(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        summary = build_governance_decision_summary(
            None, [], config, evaluated_at=now
        )
        assert summary.governance_status == BLOCKED

    def test_invalid_timestamp(self, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report()
        with pytest.raises(ValueError):
            build_governance_decision_summary(
                gate, [], config, evaluated_at=datetime.now()
            )

    def test_deterministic(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(), now)
        s1 = build_governance_decision_summary(
            gate, [record], config, evaluated_at=now
        )
        s2 = build_governance_decision_summary(
            gate, [record], config, evaluated_at=now
        )
        assert s1.governance_fingerprint == s2.governance_fingerprint
