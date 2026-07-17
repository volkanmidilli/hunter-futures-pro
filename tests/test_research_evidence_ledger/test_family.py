"""Tests for evidence ledger family indexing (MVP-68)."""

from __future__ import annotations

from hunter.research_evidence_ledger.family import (
    build_experiment_families,
    build_hypothesis_families,
    build_metric_families,
)
from hunter.research_evidence_ledger.models import (
    EvidenceLedgerEntry,
    ExperimentRegistration,
    ExperimentStatus,
    IndependenceClass,
)


def _make_reg(
    experiment_id: str,
    hypothesis: str = "test hypothesis",
    strategy_name: str = "strat_a",
    universe_plan: str = "top_100",
    timeframe: str = "1h",
    walk_forward_plan_fingerprint: str = "wf_fp_1",
    metric_family: tuple[str, ...] = ("sharpe_ratio",),
) -> ExperimentRegistration:
    return ExperimentRegistration(
        experiment_id=experiment_id,
        hypothesis=hypothesis,
        strategy_name=strategy_name,
        universe_plan=universe_plan,
        timeframe=timeframe,
        walk_forward_plan_fingerprint=walk_forward_plan_fingerprint,
        metric_family=metric_family,
        independence=IndependenceClass.INDEPENDENT,
    )


def _make_entry(reg: ExperimentRegistration) -> EvidenceLedgerEntry:
    return EvidenceLedgerEntry(
        registration=reg,
        evidence=None,
        status=ExperimentStatus.REGISTERED,
    )


class TestHypothesisFamilies:
    def test_single_hypothesis(self) -> None:
        reg = _make_reg("exp_001", hypothesis="Hypothesis A")
        entry = _make_entry(reg)
        families = build_hypothesis_families((entry,))
        assert len(families) == 1
        assert families[0].hypothesis == "Hypothesis A"
        assert families[0].experiment_ids == ("exp_001",)
        assert "sharpe_ratio" in families[0].metric_names

    def test_multiple_hypotheses(self) -> None:
        entries = (
            _make_entry(_make_reg("exp_001", hypothesis="Hypothesis A")),
            _make_entry(_make_reg("exp_002", hypothesis="Hypothesis B")),
            _make_entry(_make_reg("exp_003", hypothesis="Hypothesis A")),
        )
        families = build_hypothesis_families(entries)
        assert len(families) == 2

        hf_a = next(f for f in families if f.hypothesis == "Hypothesis A")
        assert len(hf_a.experiment_ids) == 2
        assert hf_a.experiment_ids == ("exp_001", "exp_003")

    def test_deterministic_ordering(self) -> None:
        entries1 = (
            _make_entry(_make_reg("exp_b", hypothesis="B")),
            _make_entry(_make_reg("exp_a", hypothesis="A")),
        )
        entries2 = (
            _make_entry(_make_reg("exp_a", hypothesis="A")),
            _make_entry(_make_reg("exp_b", hypothesis="B")),
        )
        fam1 = build_hypothesis_families(entries1)
        fam2 = build_hypothesis_families(entries2)
        assert len(fam1) == len(fam2)
        for f1, f2 in zip(fam1, fam2):
            assert f1.fingerprint == f2.fingerprint

    def test_fingerprint_present(self) -> None:
        reg = _make_reg("exp_001", hypothesis="Test")
        entry = _make_entry(reg)
        families = build_hypothesis_families((entry,))
        assert len(families) == 1
        assert isinstance(families[0].fingerprint, str)
        assert len(families[0].fingerprint) > 0


class TestExperimentFamilies:
    def test_single_family(self) -> None:
        reg = _make_reg("exp_001")
        entry = _make_entry(reg)
        families = build_experiment_families((entry,))
        assert len(families) == 1
        assert families[0].strategy_name == "strat_a"

    def test_multiple_families(self) -> None:
        entries = (
            _make_entry(_make_reg("exp_001", strategy_name="strat_a", timeframe="1h")),
            _make_entry(_make_reg("exp_002", strategy_name="strat_b", timeframe="1h")),
            _make_entry(_make_reg("exp_003", strategy_name="strat_a", timeframe="4h")),
        )
        families = build_experiment_families(entries)
        assert len(families) == 3  # Different keys

    def test_deterministic(self) -> None:
        entries1 = (
            _make_entry(_make_reg("exp_b", strategy_name="B")),
            _make_entry(_make_reg("exp_a", strategy_name="A")),
        )
        entries2 = (
            _make_entry(_make_reg("exp_a", strategy_name="A")),
            _make_entry(_make_reg("exp_b", strategy_name="B")),
        )
        fam1 = build_experiment_families(entries1)
        fam2 = build_experiment_families(entries2)
        assert len(fam1) == len(fam2)

    def test_fingerprint_present(self) -> None:
        reg = _make_reg("exp_001")
        entry = _make_entry(reg)
        families = build_experiment_families((entry,))
        assert len(families) == 1
        assert isinstance(families[0].fingerprint, str)
        assert len(families[0].fingerprint) > 0


class TestMetricFamilies:
    def test_single_entry(self) -> None:
        reg = _make_reg("exp_001", metric_family=("sharpe_ratio", "sortino_ratio"))
        entry = _make_entry(reg)
        families = build_metric_families((entry,))
        assert len(families) == 1
        assert "sharpe_ratio" in families[0].metric_names
        assert "sortino_ratio" in families[0].metric_names

    def test_multiple_entries_merge_metrics(self) -> None:
        reg1 = _make_reg("exp_001", metric_family=("sharpe_ratio",))
        reg2 = _make_reg("exp_002", metric_family=("sortino_ratio", "calmar_ratio"))
        entries = (
            _make_entry(reg1),
            _make_entry(reg2),
        )
        families = build_metric_families(entries)
        assert len(families) == 1
        assert "sharpe_ratio" in families[0].metric_names
        assert "sortino_ratio" in families[0].metric_names
        assert "calmar_ratio" in families[0].metric_names

    def test_empty_entries(self) -> None:
        families = build_metric_families(())
        assert len(families) == 0

    def test_fingerprint_present(self) -> None:
        reg = _make_reg("exp_001", metric_family=("m1",))
        entry = _make_entry(reg)
        families = build_metric_families((entry,))
        assert len(families) == 1
        assert isinstance(families[0].fingerprint, str)
        assert len(families[0].fingerprint) > 0
