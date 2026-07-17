"""Tests for research_campaign ordering (MVP-69/MVP-70)."""

from __future__ import annotations

from decimal import Decimal

from hunter.research_campaign.models import (
    CompiledExperiment,
    FamilyReference,
    HistoricalDataReference,
    IndependenceMetadata,
    MetricFamilyScope,
    RegimePolicy,
    StatisticalConfidenceConfigReference,
    StrategyReference,
    UniversePlanReference,
    WalkForwardTemplateReference,
)
from hunter.research_campaign.ordering import (
    canonical_sort_experiments,
    canonical_sort_key_for_combination,
)
from hunter.research_evidence_ledger.models import IndependenceClass
from hunter.research_statistical_confidence.models import (
    BootstrapConfig,
    RobustnessCriteria,
    StatisticalConfidenceConfig,
)
from hunter.research_walk_forward.models import (
    MarketRegimeLabel,
    WalkForwardCommonConfig,
    WalkForwardExperimentPlan,
    WalkForwardMode,
    WalkForwardSafetyFlags,
    WalkForwardWindow,
)


def _make_minimal_experiment(
    experiment_id: str,
    campaign_id: str,
    fingerprint: str,
    plan_fingerprint: str = "plan_fp",
    strategy_name: str = "s",
    timeframe: str = "1h",
    data_id: str = "d",
    universe_plan_id: str = "u",
    template_id: str = "t",
    config_id: str = "c",
    experiment_family_id: str = "ef",
    hypothesis_family_id: str = "hf",
    metric_names: tuple[str, ...] = ("m1",),
    independence_class: str = "INDEPENDENT",
    regime_label: str = "UNKNOWN",
) -> CompiledExperiment:
    """Helper to create a CompiledExperiment with minimal boilerplate."""
    window = WalkForwardWindow(
        selection_start="2024-01-01",
        selection_end="2024-06-01",
        evaluation_start="2024-06-01",
        evaluation_end="2024-12-01",
    )
    common = WalkForwardCommonConfig(
        strategy_name=strategy_name,
        strategy_path="/tmp/s",
        data_path="/tmp/d",
        timeframe=timeframe,
        balance=Decimal("10000"),
        stake=Decimal("100"),
        max_open_trades=5,
        fee=Decimal("0.001"),
        executable_path="/tmp/e",
    )
    plan = WalkForwardExperimentPlan(
        mode=WalkForwardMode.ROLLING,
        windows=(window,),
        common=common,
        contiguous=False,
        safety_flags=WalkForwardSafetyFlags(),
        fingerprint=plan_fingerprint,
    )

    strat = StrategyReference(strategy_name=strategy_name, strategy_path="/tmp/s")
    data = HistoricalDataReference(data_id=data_id, data_path="/tmp/d")
    uni = UniversePlanReference(
        universe_plan_id=universe_plan_id,
        universe_plan_path="/tmp/u",
        candidate_pairlist=(),
        baseline_pairlist=(),
        candidate_universe_fingerprint="c",
        baseline_universe_fingerprint="b",
    )
    tmpl = WalkForwardTemplateReference(
        template_id=template_id, mode="ROLLING", windows=(window,)
    )

    bootstrap = BootstrapConfig(seed=1, iterations=10)
    robustness = RobustnessCriteria(
        sign_share_threshold=Decimal("0.8"),
        maximum_influence_ratio=Decimal("0.3"),
        confidence_level=Decimal("0.95"),
    )
    sc_config = StatisticalConfidenceConfig(
        minimum_available_window_count=3,
        confidence_level=Decimal("0.95"),
        bootstrap=bootstrap,
        robustness=robustness,
    )
    conf_ref = StatisticalConfidenceConfigReference(
        config_id=config_id, config=sc_config
    )

    ef = FamilyReference(family_id=experiment_family_id, family_type="experiment")
    hf = FamilyReference(family_id=hypothesis_family_id, family_type="hypothesis")
    ms = MetricFamilyScope(metric_names=metric_names)
    ind = IndependenceMetadata(independence_class=IndependenceClass(independence_class))
    rp = RegimePolicy(regime_label=MarketRegimeLabel(regime_label))

    return CompiledExperiment(
        experiment_id=experiment_id,
        campaign_id=campaign_id,
        strategy=strat,
        timeframe=timeframe,
        historical_data=data,
        universe_plan=uni,
        walk_forward_template=tmpl,
        confidence_config=conf_ref,
        experiment_family=ef,
        hypothesis_family=hf,
        metric_family=ms,
        independence=ind,
        regime_policy=rp,
        walk_forward_plan=plan,
        fingerprint=fingerprint,
    )


class TestCanonicalSortKeyForCombination:
    """Test that canonical_sort_key_for_combination returns consistent tuples."""

    def test_returns_tuple(self) -> None:
        combo = {
            "strategy_name": "a",
            "timeframe": "1h",
            "data_id": "d1",
            "universe_plan_id": "u1",
            "template_id": "t1",
            "config_id": "c1",
            "experiment_family_id": "ef1",
            "hypothesis_family_id": "hf1",
            "metric_names": ("sharpe_ratio",),
            "independence_class": "INDEPENDENT",
            "regime_label": "UNKNOWN",
        }
        key = canonical_sort_key_for_combination(combo)
        assert isinstance(key, tuple)

    def test_tuple_fields_are_tuples_of_strings(self) -> None:
        combo = {
            "strategy_name": "a",
            "timeframe": "1h",
            "data_id": "d1",
            "universe_plan_id": "u1",
            "template_id": "t1",
            "config_id": "c1",
            "experiment_family_id": "ef1",
            "hypothesis_family_id": "hf1",
            "metric_names": ("sharpe_ratio", "sortino_ratio"),
            "independence_class": "INDEPENDENT",
            "regime_label": "UNKNOWN",
        }
        key = canonical_sort_key_for_combination(combo)
        for part in key:
            assert isinstance(part, tuple)
            for s in part:
                assert isinstance(s, str)

    def test_deterministic(self) -> None:
        """Same input produces same key."""
        combo = {
            "strategy_name": "a",
            "timeframe": "1h",
            "data_id": "d1",
            "universe_plan_id": "u1",
            "template_id": "t1",
            "config_id": "c1",
            "experiment_family_id": "ef1",
            "hypothesis_family_id": "hf1",
            "metric_names": ("m1",),
            "independence_class": "IND",
            "regime_label": "BULL",
        }
        key1 = canonical_sort_key_for_combination(combo)
        key2 = canonical_sort_key_for_combination(combo)
        assert key1 == key2

    def test_fields_sorted_as_expected(self) -> None:
        """The first key part should be strategy_name."""
        combo = {
            "strategy_name": "z_strat",
            "timeframe": "1h",
            "data_id": "d1",
            "universe_plan_id": "u1",
            "template_id": "t1",
            "config_id": "c1",
            "experiment_family_id": "ef1",
            "hypothesis_family_id": "hf1",
            "metric_names": ("m1",),
            "independence_class": "IND",
            "regime_label": "BULL",
        }
        key = canonical_sort_key_for_combination(combo)
        assert key[0] == ("z_strat",)


class TestCanonicalSortExperiments:
    """Test that canonical_sort_experiments sorts by (campaign_id, experiment_id, fingerprint)."""

    def test_returns_tuple(self, sample_compiled_experiment) -> None:
        experiments = [sample_compiled_experiment]
        result = canonical_sort_experiments(experiments)
        assert isinstance(result, tuple)

    def test_sorted_by_campaign_id_then_experiment_id(self) -> None:
        """Verify sorted order by (campaign_id, experiment_id, fingerprint)."""
        e1 = _make_minimal_experiment("exp_c", "camp_b", "fp_2")
        e2 = _make_minimal_experiment("exp_a", "camp_b", "fp_1")
        e3 = _make_minimal_experiment("exp_b", "camp_a", "fp_3")
        e4 = _make_minimal_experiment("exp_a", "camp_a", "fp_0")

        unsorted = [e1, e2, e3, e4]
        sorted_result = canonical_sort_experiments(unsorted)

        # Expected: camp_a/exp_a/fp_0, camp_a/exp_b/fp_3, camp_b/exp_a/fp_1, camp_b/exp_c/fp_2
        assert len(sorted_result) == 4
        assert sorted_result[0].experiment_id == "exp_a"
        assert sorted_result[0].campaign_id == "camp_a"
        assert sorted_result[0].fingerprint == "fp_0"
        assert sorted_result[1].experiment_id == "exp_b"
        assert sorted_result[1].campaign_id == "camp_a"
        assert sorted_result[2].experiment_id == "exp_a"
        assert sorted_result[2].campaign_id == "camp_b"
        assert sorted_result[2].fingerprint == "fp_1"
        assert sorted_result[3].experiment_id == "exp_c"
        assert sorted_result[3].campaign_id == "camp_b"

    def test_reordering_returns_same_order(self) -> None:
        """Reordering the input list yields the same sorted output."""
        e1 = _make_minimal_experiment("exp_b", "camp_a", "fp_2")
        e2 = _make_minimal_experiment("exp_a", "camp_a", "fp_1")
        e3 = _make_minimal_experiment("exp_c", "camp_a", "fp_3")

        order1 = canonical_sort_experiments([e1, e2, e3])
        order2 = canonical_sort_experiments([e3, e1, e2])
        order3 = canonical_sort_experiments([e2, e3, e1])

        assert order1 == order2
        assert order2 == order3
