"""Tests for governance summary writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from hunter.governance_summary.models import (
    READY_FOR_RESEARCH_HANDOFF,
    GovernanceDecisionSummary,
    GovernanceReviewSummary,
    GovernanceSummaryConfig,
)
from hunter.governance_summary.writer import (
    GovernanceSummaryWriterError,
    governance_decision_summary_to_dict,
    governance_decision_summary_to_json_text,
    governance_decision_summary_to_markdown_text,
    write_governance_decision_summary,
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


@pytest.fixture
def summary(now: datetime, config: GovernanceSummaryConfig) -> GovernanceDecisionSummary:
    review_summary = GovernanceReviewSummary(
        total_records=1,
        accepted_records=1,
        rejected_attempts=0,
        chain_valid=True,
        latest_accepted_record_fingerprint="fp-latest",
        latest_reviewer_identity="reviewer-a",
        latest_reviewer_decision="APPROVE_FOR_RESEARCH",
        latest_review_created_at=now,
        open_change_request_count=0,
        source_decision_fingerprints=("fp-gate",),
        reason_codes=(),
    )
    return GovernanceDecisionSummary(
        version="0.61.0-dev",
        governance_status=READY_FOR_RESEARCH_HANDOFF,
        governance_fingerprint="fp-summary",
        evaluated_at=now,
        gate_decision="GO",
        gate_decision_fingerprint="fp-gate",
        review_summary=review_summary,
        blocking_reason_codes=(),
        review_reason_codes=(),
        research_only=True,
        human_review_required=True,
        execution_approval_granted=False,
        metadata=MappingProxyType({"run_id": "r1"}),
    )


class TestToDict:
    def test_contains_key_fields(self, summary: GovernanceDecisionSummary) -> None:
        data = governance_decision_summary_to_dict(summary)
        assert data["governance_status"] == READY_FOR_RESEARCH_HANDOFF
        assert data["research_only"] is True
        assert data["execution_approval_granted"] is False
        assert "safety_notice" in data

    def test_evaluated_at_iso(self, summary: GovernanceDecisionSummary) -> None:
        data = governance_decision_summary_to_dict(summary)
        assert data["evaluated_at"] == "2026-07-14T12:00:00+00:00"


class TestToJsonText:
    def test_deterministic(self, summary: GovernanceDecisionSummary) -> None:
        t1 = governance_decision_summary_to_json_text(summary)
        t2 = governance_decision_summary_to_json_text(summary)
        assert t1 == t2
        data = json.loads(t1)
        assert data["governance_status"] == READY_FOR_RESEARCH_HANDOFF

    def test_sorted_keys(self, summary: GovernanceDecisionSummary) -> None:
        text = governance_decision_summary_to_json_text(summary)
        data = json.loads(text)
        assert list(data.keys()) == sorted(data.keys())


class TestToMarkdownText:
    def test_contains_status(self, summary: GovernanceDecisionSummary) -> None:
        text = governance_decision_summary_to_markdown_text(summary)
        assert READY_FOR_RESEARCH_HANDOFF in text

    def test_contains_safety_notice(self, summary: GovernanceDecisionSummary) -> None:
        text = governance_decision_summary_to_markdown_text(summary)
        assert "not execution approval" in text

    def test_contains_artifact_paths(self, summary: GovernanceDecisionSummary) -> None:
        text = governance_decision_summary_to_markdown_text(
            summary,
            json_path=Path("data/summary.json"),
            markdown_path=Path("reports/summary.md"),
        )
        assert "data/summary.json" in text
        assert "reports/summary.md" in text


class TestWriteGovernanceDecisionSummary:
    def test_writes_both_files(self, summary: GovernanceDecisionSummary, config: GovernanceSummaryConfig) -> None:
        json_path, md_path = write_governance_decision_summary(summary, config)
        assert json_path.exists()
        assert md_path.exists()
        data = json.loads(json_path.read_text())
        assert data["governance_status"] == READY_FOR_RESEARCH_HANDOFF
        assert "not execution approval" in md_path.read_text()

    def test_atomic_cleanup_on_failure(self, summary: GovernanceDecisionSummary, config: GovernanceSummaryConfig, monkeypatch) -> None:
        monkeypatch.setattr(
            "hunter.governance_summary.writer.os.replace",
            lambda _src, _dst: (_ for _ in ()).throw(OSError("boom")),
        )
        with pytest.raises(GovernanceSummaryWriterError):
            write_governance_decision_summary(summary, config)
        # Temp file should be cleaned up
        temp = config.output_dir / config.json_filename
        temp_with_suffix = temp.with_suffix(f"{temp.suffix}.tmp")
        assert not temp_with_suffix.exists()
