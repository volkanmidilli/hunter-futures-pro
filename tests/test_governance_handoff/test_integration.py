"""Integration tests for the Research Governance Handoff Package Builder (MVP-62)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from hunter.governance_handoff import (
    BLOCKED,
    MISSING_LATEST_ACCEPTED_REVIEW,
    READY_FOR_RESEARCH_HANDOFF,
    REVIEW_FINGERPRINT_MISMATCH,
    REVIEW_REQUIRED,
    GovernanceHandoffConfig,
    build_research_governance_handoff_package,
    write_research_governance_handoff_package,
)
from hunter.governance_handoff.writer import (
    research_governance_handoff_package_to_json_text,
)
from hunter.governance_summary import (
    GovernanceSummaryConfig,
    build_governance_decision_summary,
)
from hunter.human_review_registry.models import (
    APPROVE_FOR_RESEARCH,
    HumanReviewInput,
    HumanReviewRegistryConfig,
)
from hunter.research_decision_gate.models import (
    GO,
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
    return GovernanceHandoffConfig(
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


def _make_ready_summary_without_review(
    gate_report: ResearchDecisionGateReport,
    now: datetime,
):
    """Return a GovernanceDecisionSummary in READY_FOR_RESEARCH_HANDOFF with no review."""
    from types import MappingProxyType
    from hunter.governance_summary.models import (
        GOVERNANCE_SUMMARY_VERSION,
        GovernanceDecisionSummary,
        GovernanceReviewSummary,
    )

    return GovernanceDecisionSummary(
        version=GOVERNANCE_SUMMARY_VERSION,
        governance_fingerprint="gov-fp",
        gate_decision_fingerprint=gate_report.decision_fingerprint,
        governance_status=READY_FOR_RESEARCH_HANDOFF,
        review_summary=GovernanceReviewSummary(
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
        ),
        gate_decision=GO,
        blocking_reason_codes=(),
        review_reason_codes=(),
        research_only=True,
        human_review_required=True,
        execution_approval_granted=False,
        metadata=MappingProxyType({"run_id": "run-no-review"}),
        evaluated_at=now,
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


class TestHandoffMatrix:
    def test_ready_path_allows_handoff(self, now: datetime, config: GovernanceHandoffConfig) -> None:
        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(), now)
        summary = build_governance_decision_summary(
            gate, [record], GovernanceSummaryConfig(), evaluated_at=now
        )
        assert summary.governance_status == READY_FOR_RESEARCH_HANDOFF

        package = build_research_governance_handoff_package(
            summary, gate, record, config, built_at=now, metadata={"run_id": "run-1"}
        )
        assert package.governance_status == READY_FOR_RESEARCH_HANDOFF
        assert package.handoff_allowed is True
        assert package.research_only is True
        assert package.execution_approval_granted is False
        assert package.production_approval_granted is False

    def test_no_go_gate_blocks_handoff(self, now: datetime, config: GovernanceHandoffConfig) -> None:
        gate = _make_gate_report(decision=NO_GO, now=now)
        record = _make_record(gate, _make_review_input(), now)
        summary = build_governance_decision_summary(
            gate, [record], GovernanceSummaryConfig(), evaluated_at=now
        )
        package = build_research_governance_handoff_package(
            summary, gate, record, config, built_at=now, metadata={"run_id": "run-1"}
        )
        assert package.governance_status == BLOCKED
        assert package.handoff_allowed is False

    def test_missing_required_review_blocks_handoff(
        self, now: datetime, config: GovernanceHandoffConfig
    ) -> None:
        gate = _make_gate_report(now=now)
        summary = build_governance_decision_summary(
            gate, [], GovernanceSummaryConfig(), evaluated_at=now
        )
        package = build_research_governance_handoff_package(
            summary, gate, None, config, built_at=now, metadata={"run_id": "run-1"}
        )
        assert package.governance_status == REVIEW_REQUIRED
        assert package.handoff_allowed is False
        assert MISSING_LATEST_ACCEPTED_REVIEW in package.blocking_reason_codes

    def test_review_fingerprint_mismatch_blocks_handoff(
        self, now: datetime, config: GovernanceHandoffConfig
    ) -> None:
        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(), now)
        summary = build_governance_decision_summary(
            gate, [record], GovernanceSummaryConfig(), evaluated_at=now
        )
        # Tamper the record fingerprint
        object.__setattr__(record, "record_fingerprint", "tampered-fp")
        package = build_research_governance_handoff_package(
            summary, gate, record, config, built_at=now, metadata={"run_id": "run-1"}
        )
        assert package.handoff_allowed is False
        assert REVIEW_FINGERPRINT_MISMATCH in package.blocking_reason_codes

    def test_review_not_required_by_config_allows_handoff(
        self, now: datetime, config: GovernanceHandoffConfig
    ) -> None:
        gate = _make_gate_report(now=now)
        summary = _make_ready_summary_without_review(gate, now)
        handoff_cfg = GovernanceHandoffConfig(require_latest_accepted_review=False)
        package = build_research_governance_handoff_package(
            summary, gate, None, handoff_cfg, built_at=now, metadata={"run_id": "run-1"}
        )
        assert package.governance_status == READY_FOR_RESEARCH_HANDOFF
        assert package.handoff_allowed is True
        assert package.review_source is None


class TestDeterminism:
    def test_package_fingerprint_deterministic(
        self, now: datetime, config: GovernanceHandoffConfig
    ) -> None:
        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(), now)
        summary = build_governance_decision_summary(
            gate, [record], GovernanceSummaryConfig(), evaluated_at=now
        )
        p1 = build_research_governance_handoff_package(
            summary, gate, record, config, built_at=now, metadata={"run_id": "run-1"}
        )
        p2 = build_research_governance_handoff_package(
            summary, gate, record, config, built_at=now, metadata={"run_id": "run-1"}
        )
        assert p1.package_fingerprint == p2.package_fingerprint

    def test_serialization_deterministic(
        self, now: datetime, config: GovernanceHandoffConfig
    ) -> None:
        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(), now)
        summary = build_governance_decision_summary(
            gate, [record], GovernanceSummaryConfig(), evaluated_at=now
        )
        package = build_research_governance_handoff_package(
            summary, gate, record, config, built_at=now, metadata={"run_id": "run-1"}
        )
        t1 = research_governance_handoff_package_to_json_text(package)
        t2 = research_governance_handoff_package_to_json_text(package)
        assert t1 == t2


class TestWriterIntegration:
    def test_writes_json_and_markdown(
        self, now: datetime, config: GovernanceHandoffConfig
    ) -> None:
        gate = _make_gate_report(now=now)
        record = _make_record(gate, _make_review_input(), now)
        summary = build_governance_decision_summary(
            gate, [record], GovernanceSummaryConfig(), evaluated_at=now
        )
        package = build_research_governance_handoff_package(
            summary, gate, record, config, built_at=now, metadata={"run_id": "run-1"}
        )
        json_path, md_path = write_research_governance_handoff_package(package, config)
        assert json_path.exists()
        assert md_path.exists()
        data = json.loads(json_path.read_text())
        assert data["version"] == package.version
        assert data["package_fingerprint"] == package.package_fingerprint
        assert data["handoff_allowed"] is True
        assert data["research_only"] is True
        assert "safety_notice" in data
        md_text = md_path.read_text()
        assert "Research Governance Handoff Package" in md_text
        assert package.package_fingerprint in md_text

    def test_blocked_package_still_serializes(
        self, now: datetime, config: GovernanceHandoffConfig
    ) -> None:
        gate = _make_gate_report(now=now)
        summary = build_governance_decision_summary(
            gate, [], GovernanceSummaryConfig(), evaluated_at=now
        )
        package = build_research_governance_handoff_package(
            summary, gate, None, config, built_at=now, metadata={"run_id": "run-1"}
        )
        assert package.handoff_allowed is False
        json_path, md_path = write_research_governance_handoff_package(package, config)
        assert json_path.exists()
        assert md_path.exists()
        data = json.loads(json_path.read_text())
        assert data["handoff_allowed"] is False
        assert MISSING_LATEST_ACCEPTED_REVIEW in data["blocking_reason_codes"]
