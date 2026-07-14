"""Integration tests for the Human Review Decision Registry (MVP-60)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.human_review_registry import (
    APPROVE_FOR_RESEARCH,
    GO,
    HUMAN_REVIEW_REGISTRY_VERSION,
    NEEDS_REVIEW,
    NO_GO,
    REJECT,
    REQUEST_CHANGES,
    REVIEW_APPROVED_FOR_RESEARCH,
    REVIEW_REJECTED,
    HumanReviewInput,
    HumanReviewRegistryConfig,
    SAFETY_NOTICE,
    build_human_review_record,
    write_human_review_record,
)
from hunter.research_decision_gate.models import (
    DecisionSourceSummary,
    RESEARCH_DECISION_GATE_VERSION,
    ResearchDecisionGateReport,
)


def _source_summary(
    *,
    name: str,
    present: bool = True,
    accepted: bool = True,
    fresh: bool = True,
    fingerprint: str = "src-fp",
) -> DecisionSourceSummary:
    return DecisionSourceSummary(
        source_name=name,
        present=present,
        accepted=accepted,
        fresh=fresh,
        fingerprint=fingerprint,
        reason_codes=(),
    )


def _decision_report(decision: str = GO) -> ResearchDecisionGateReport:
    return ResearchDecisionGateReport(
        version=RESEARCH_DECISION_GATE_VERSION,
        decision=decision,  # type: ignore[arg-type]
        decision_fingerprint=f"decision-{decision}",
        evaluated_at=datetime(2026, 7, 14, 11, 0, 0, tzinfo=timezone.utc),
        risk_context_summary=_source_summary(name="risk_context"),
        universe_summary=_source_summary(name="universe"),
        strategy_contract_summary=_source_summary(name="strategy_contract"),
        blocking_reason_codes=(),
        review_reason_codes=(),
        safety_flags={"research_only": True, "human_approval_required": True},
        research_only=True,
        human_approval_required=True,
    )


def _registry_config(tmp_path: Path) -> HumanReviewRegistryConfig:
    return HumanReviewRegistryConfig(
        output_dir=tmp_path / "registry" / "data",
        report_output_dir=tmp_path / "registry" / "reports",
        min_review_note_length=20,
    )


def test_end_to_end_approve_for_research(tmp_path: Path) -> None:
    decision_report = _decision_report(GO)
    config = _registry_config(tmp_path)
    created_at = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    review_input = HumanReviewInput(
        reviewer_identity="alice",
        reviewer_decision=APPROVE_FOR_RESEARCH,
        review_note="This decision looks safe for research-only use.",
    )
    record = build_human_review_record(
        decision_report, review_input, config, created_at=created_at
    )
    assert record.accepted is True
    assert record.execution_approval_granted is False
    assert REVIEW_APPROVED_FOR_RESEARCH in record.reason_codes

    json_path, _, _, _ = write_human_review_record(record, config)
    assert json_path.exists()
    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["version"] == HUMAN_REVIEW_REGISTRY_VERSION
    assert parsed["accepted"] is True
    assert parsed["safety_notice"] == SAFETY_NOTICE


def test_end_to_end_reject_review(tmp_path: Path) -> None:
    decision_report = _decision_report(GO)
    config = _registry_config(tmp_path)
    created_at = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    review_input = HumanReviewInput(
        reviewer_identity="bob",
        reviewer_decision=REJECT,
        review_note="Rejecting this decision due to insufficient rationale.",
    )
    record = build_human_review_record(
        decision_report, review_input, config, created_at=created_at
    )
    assert record.accepted is True
    assert REVIEW_REJECTED in record.reason_codes


def test_end_to_end_no_go_approve_rejected(tmp_path: Path) -> None:
    decision_report = _decision_report(NO_GO)
    config = _registry_config(tmp_path)
    created_at = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    review_input = HumanReviewInput(
        reviewer_identity="alice",
        reviewer_decision=APPROVE_FOR_RESEARCH,
        review_note="This decision looks safe for research-only use.",
    )
    record = build_human_review_record(
        decision_report, review_input, config, created_at=created_at
    )
    assert record.accepted is False
    assert "NO_GO_APPROVAL_FORBIDDEN" in record.reason_codes


def test_end_to_end_needs_review_requires_note(tmp_path: Path) -> None:
    decision_report = _decision_report(NEEDS_REVIEW)
    config = _registry_config(tmp_path)
    created_at = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    review_input = HumanReviewInput(
        reviewer_identity="alice",
        reviewer_decision=APPROVE_FOR_RESEARCH,
        review_note="short",
    )
    record = build_human_review_record(
        decision_report, review_input, config, created_at=created_at
    )
    assert record.accepted is False
    assert "REVIEW_NOTE_TOO_SHORT" in record.reason_codes


def test_end_to_end_missing_input_rejected(tmp_path: Path) -> None:
    decision_report = _decision_report(GO)
    config = _registry_config(tmp_path)
    created_at = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    record = build_human_review_record(
        decision_report, None, config, created_at=created_at
    )
    assert record.accepted is False
    assert "MISSING_REVIEW_INPUT" in record.reason_codes


def test_end_to_end_chain_append(tmp_path: Path) -> None:
    decision_report = _decision_report(GO)
    config = _registry_config(tmp_path)
    created_at = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    first = build_human_review_record(
        decision_report,
        HumanReviewInput(
            reviewer_identity="alice",
            reviewer_decision=APPROVE_FOR_RESEARCH,
            review_note="Approved for research.",
        ),
        config,
        created_at=created_at,
    )
    second = build_human_review_record(
        decision_report,
        HumanReviewInput(
            reviewer_identity="bob",
            reviewer_decision=REQUEST_CHANGES,
            review_note="Requesting additional validation before approval.",
        ),
        config,
        existing_records=(first,),
        created_at=created_at,
    )
    assert second.accepted is True
    assert second.previous_record_fingerprint == first.record_fingerprint


def test_end_to_end_duplicate_review_rejected(tmp_path: Path) -> None:
    decision_report = _decision_report(GO)
    config = _registry_config(tmp_path)
    created_at = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    inp = HumanReviewInput(
        reviewer_identity="alice",
        reviewer_decision=APPROVE_FOR_RESEARCH,
        review_note="Approved for research.",
    )
    first = build_human_review_record(decision_report, inp, config, created_at=created_at)
    second = build_human_review_record(
        decision_report, inp, config, existing_records=(first,), created_at=created_at
    )
    assert second.accepted is False
    assert "DUPLICATE_REVIEW" in second.reason_codes


def test_markdown_report_contains_decision_fingerprint(tmp_path: Path) -> None:
    decision_report = _decision_report(GO)
    config = _registry_config(tmp_path)
    created_at = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    review_input = HumanReviewInput(
        reviewer_identity="alice",
        reviewer_decision=APPROVE_FOR_RESEARCH,
        review_note="Approved for research-only use.",
    )
    record = build_human_review_record(
        decision_report, review_input, config, created_at=created_at
    )
    _, md_path, _, _ = write_human_review_record(record, config)
    text = md_path.read_text(encoding="utf-8")
    assert str(record.source_decision_fingerprint) in text
    assert "**execution_approval_granted**: False" in text
