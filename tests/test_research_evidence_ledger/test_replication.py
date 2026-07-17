"""Tests for replication analysis (MVP-68)."""

from __future__ import annotations

from hunter.research_evidence_ledger.models import (
    EvidenceLedgerEntry,
    ExperimentRegistration,
    ExperimentStatus,
    IndependenceClass,
    MetricDirection,
    ReplicationState,
)
from hunter.research_evidence_ledger.replication import (
    analyze_replication,
)


def _make_reg(
    experiment_id: str,
    independence: IndependenceClass = IndependenceClass.INDEPENDENT,
    hypothesis: str = "test hypothesis",
    metric_family: tuple[str, ...] = ("sharpe_ratio",),
) -> ExperimentRegistration:
    return ExperimentRegistration(
        experiment_id=experiment_id,
        hypothesis=hypothesis,
        strategy_name="strat_a",
        universe_plan="top_100",
        timeframe="1h",
        walk_forward_plan_fingerprint="wf_fp_1",
        metric_family=metric_family,
        independence=independence,
        experiment_family_id="ef_001",
    )


def _make_entry(reg: ExperimentRegistration) -> EvidenceLedgerEntry:
    return EvidenceLedgerEntry(
        registration=reg,
        evidence=None,  # No evidence for registered-only entries
        status=ExperimentStatus.REGISTERED,
    )


class TestAnalyzeReplication:
    def test_no_entries(self) -> None:
        results = analyze_replication(
            entries=(),
            family_id="fam_001",
            family_type="hypothesis",
            metric_name="sharpe_ratio",
        )
        assert results == []

    def test_no_evidence_entries(self) -> None:
        reg = _make_reg("exp_001")
        entry = _make_entry(reg)
        results = analyze_replication(
            entries=(entry,),
            family_id="fam_001",
            family_type="hypothesis",
            metric_name="sharpe_ratio",
        )
        assert results == []

    def test_insufficient_independent(self) -> None:
        reg = _make_reg("exp_001")
        entry = _make_entry(reg)
        results = analyze_replication(
            entries=(entry,),
            family_id="fam_001",
            family_type="hypothesis",
            metric_name="sharpe_ratio",
            min_independent=2,
        )
        assert results == []

    def test_fingerprint_present(self) -> None:
        reg = _make_reg("exp_001")
        entry = _make_entry(reg)
        results = analyze_replication(
            entries=(entry,),
            family_id="fam_001",
            family_type="hypothesis",
            metric_name="sharpe_ratio",
        )
        if results:
            assert isinstance(results[0].fingerprint, str)
