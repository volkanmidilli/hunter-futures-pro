"""Integration tests for the Governance Decision Summary Aggregator (MVP-61)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from hunter.governance_summary import (
    BLOCKED,
    BROKEN_REVIEW_CHAIN,
    DUPLICATE_REVIEW_RECORD,
    GATE_DECISION_NO_GO,
    GATE_REVIEW_REQUIRED,
    INVALID_TIMESTAMP,
    LATEST_REVIEW_REJECTED,
    LATEST_REVIEW_REQUESTS_CHANGES,
    NO_ACCEPTED_REVIEW,
    OPEN_CHANGE_REQUEST,
    READY_FOR_RESEARCH_HANDOFF,
    REVIEW_REQUIRED,
    TAMPERED_REVIEW_RECORD,
    UNSAFE_GOVERNANCE_FLAG,
    GovernanceSummaryConfig,
    build_governance_decision_summary,
    write_governance_decision_summary,
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
    ResearchDecisionGateReport,
)


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def config(tmp_path):
    return GovernanceSummaryConfig(
        output_dir=tmp_path / "data",
        report_output_dir=tmp_path / "reports",
    )


def _make_gate_report(
    decision: str = GO,
    fingerprint: str = "gate-fp",
    now: datetime | None = None,
    research_only: bool = True,
    human_approval_required: bool = True,
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


class TestGovernanceStatusMatrix:
    def test_go_approved_ready(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(), now)
        summary = build_governance_decision_summary(gate, [record], config, evaluated_at=now)
        assert summary.governance_status == READY_FOR_RESEARCH_HANDOFF
        assert summary.execution_approval_granted is False

    def test_go_no_accepted_review_required(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(now=now)
        summary = build_governance_decision_summary(gate, [], config, evaluated_at=now)
        assert summary.governance_status == REVIEW_REQUIRED
        assert NO_ACCEPTED_REVIEW in summary.review_reason_codes

    def test_go_rejected_review_required(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(REJECT), now)
        summary = build_governance_decision_summary(gate, [record], config, evaluated_at=now)
        assert summary.governance_status == REVIEW_REQUIRED
        assert LATEST_REVIEW_REJECTED in summary.review_reason_codes

    def test_go_change_request_review_required(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(REQUEST_CHANGES), now)
        summary = build_governance_decision_summary(gate, [record], config, evaluated_at=now)
        assert summary.governance_status == REVIEW_REQUIRED
        assert OPEN_CHANGE_REQUEST in summary.review_reason_codes
        assert LATEST_REVIEW_REQUESTS_CHANGES in summary.review_reason_codes

    def test_needs_review_with_approval_review_required(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(decision=NEEDS_REVIEW, now=now)
        record = _make_record(
            gate,
            _make_review_input(APPROVE_FOR_RESEARCH, "adequate note here"),
            now,
        )
        summary = build_governance_decision_summary(gate, [record], config, evaluated_at=now)
        assert summary.governance_status == REVIEW_REQUIRED
        assert GATE_REVIEW_REQUIRED in summary.review_reason_codes

    def test_no_go_approved_blocked(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(decision=NO_GO, now=now)
        record = _make_record(gate, _make_review_input(), now)
        summary = build_governance_decision_summary(gate, [record], config, evaluated_at=now)
        assert summary.governance_status == BLOCKED
        assert GATE_DECISION_NO_GO in summary.blocking_reason_codes

    def test_empty_chain(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(now=now)
        summary = build_governance_decision_summary(gate, [], config, evaluated_at=now)
        assert summary.governance_status == REVIEW_REQUIRED


class TestChainIntegrity:
    def test_broken_chain_blocked(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        from hunter.human_review_registry.chain import compute_record_fingerprint
        from hunter.human_review_registry.models import HumanReviewRecord

        gate = _make_gate_report(now=now)
        r1 = _make_record(gate, _make_review_input(), now)
        r2_fp = compute_record_fingerprint(
            source_decision_fingerprint=gate.decision_fingerprint,
            source_decision=GO,
            reviewer_identity="reviewer-a",
            reviewer_decision=APPROVE_FOR_RESEARCH,
            review_note="second approval",
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
            review_note="second approval",
            created_at=now,
            previous_record_fingerprint="wrong-fp",
            record_fingerprint=r2_fp,
            accepted=True,
            human_approval_recorded=True,
            execution_approval_granted=False,
            reason_codes=("REVIEW_APPROVED_FOR_RESEARCH",),
        )
        summary = build_governance_decision_summary(gate, [r1, r2], config, evaluated_at=now)
        assert summary.governance_status == BLOCKED
        assert BROKEN_REVIEW_CHAIN in summary.blocking_reason_codes

    def test_tampered_record_blocked(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(), now)
        object.__setattr__(record, "reviewer_identity", "tampered")
        summary = build_governance_decision_summary(gate, [record], config, evaluated_at=now)
        assert summary.governance_status == BLOCKED
        assert TAMPERED_REVIEW_RECORD in summary.blocking_reason_codes

    def test_duplicate_record_blocked(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(now=now)
        r1 = _make_record(gate, _make_review_input(), now)
        r2 = _make_record(gate, _make_review_input(), now)
        summary = build_governance_decision_summary(gate, [r1, r2], config, evaluated_at=now)
        assert summary.governance_status == BLOCKED
        assert DUPLICATE_REVIEW_RECORD in summary.blocking_reason_codes


class TestSafetyAndValidation:
    def test_unsafe_flag_blocked(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        class FakeReport:
            decision = GO
            decision_fingerprint = "fp"
            research_only = False
            human_approval_required = True

        summary = build_governance_decision_summary(FakeReport(), [], config, evaluated_at=now)
        assert summary.governance_status == BLOCKED
        assert UNSAFE_GOVERNANCE_FLAG in summary.blocking_reason_codes

    def test_invalid_timestamp(self, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report()
        with pytest.raises(ValueError):
            build_governance_decision_summary(
                gate, [], config, evaluated_at=datetime.now()
            )


class TestDeterminism:
    def test_build_deterministic(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(), now)
        s1 = build_governance_decision_summary(gate, [record], config, evaluated_at=now)
        s2 = build_governance_decision_summary(gate, [record], config, evaluated_at=now)
        assert s1.governance_fingerprint == s2.governance_fingerprint

    def test_serialization_deterministic(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        from hunter.governance_summary.writer import governance_decision_summary_to_json_text

        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(), now)
        s1 = build_governance_decision_summary(gate, [record], config, evaluated_at=now)
        t1 = governance_decision_summary_to_json_text(s1)
        t2 = governance_decision_summary_to_json_text(s1)
        assert t1 == t2

    def test_tie_breaker(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(now=now)
        r1 = _make_record(gate, _make_review_input(), now)
        # Older approve followed by newer change request
        r2_input = _make_review_input(REQUEST_CHANGES)
        r2 = _make_record(gate, r2_input, now.replace(second=1), previous_record=r1)
        summary = build_governance_decision_summary(gate, [r1, r2], config, evaluated_at=now.replace(second=1))
        assert summary.governance_status == REVIEW_REQUIRED
        assert summary.review_summary.latest_reviewer_decision == REQUEST_CHANGES


class TestWriterIntegration:
    def test_atomic_writer_cleanup(self, now: datetime, config: GovernanceSummaryConfig, monkeypatch) -> None:
        from hunter.governance_summary.writer import (
            GovernanceSummaryWriterError,
            write_governance_decision_summary,
        )

        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(), now)
        summary = build_governance_decision_summary(gate, [record], config, evaluated_at=now)
        monkeypatch.setattr(
            "hunter.governance_summary.writer.os.replace",
            lambda _src, _dst: (_ for _ in ()).throw(OSError("boom")),
        )
        with pytest.raises(GovernanceSummaryWriterError):
            write_governance_decision_summary(summary, config)
        temp = config.output_dir / config.json_filename
        assert not temp.with_suffix(f"{temp.suffix}.tmp").exists()

    def test_written_artifacts_contain_no_execution_approval(self, now: datetime, config: GovernanceSummaryConfig) -> None:
        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(), now)
        summary = build_governance_decision_summary(gate, [record], config, evaluated_at=now)
        json_path, md_path = write_governance_decision_summary(summary, config)
        json_data = json.loads(json_path.read_text())
        assert json_data["execution_approval_granted"] is False
        assert "not execution approval" in md_path.read_text()


class TestNoRuntimeBehavior:
    def test_no_freqtrade_import(self) -> None:
        import hunter.governance_summary as gs

        assert not hasattr(gs, "freqtrade")
