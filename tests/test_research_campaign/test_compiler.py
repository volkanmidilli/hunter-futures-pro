"""Tests for research_campaign compiler (MVP-69/MVP-70)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.research_campaign.compiler import compile_campaign
from hunter.research_campaign.errors import (
    ResearchCampaignCompilationError,
    ResearchCampaignFilterError,
)
from hunter.research_campaign.filters import filter_combinations
from hunter.research_campaign.models import (
    CampaignExecutionPolicy,
    CampaignFilterRule,
    CampaignOutputPolicy,
    CampaignParameterSet,
    CompiledCampaign,
    CompiledExperiment,
    FilterOperator,
    ResearchCampaignDefinition,
    ResearchCampaignSafetyFlags,
    ResumePolicy,
)


def _make_multi_param_set(
    strategy_names: tuple[str, ...],
    timeframes: tuple[str, ...],
    common_config,
    data_ref,
    universe_ref,
    wf_template_ref,
    confidence_config_ref,
    exp_family_ref,
    hyp_family_ref,
    metric_scope,
    independence,
    regime_policy,
) -> CampaignParameterSet:
    """Helper to build a parameter set with multiple strategy/timeframe values."""
    from hunter.research_campaign.models import StrategyReference

    strategies = tuple(
        StrategyReference(strategy_name=s, strategy_path=f"/tmp/strat/{s}", fingerprint=s)
        for s in strategy_names
    )
    return CampaignParameterSet(
        common_config=common_config,
        strategies=strategies,
        timeframes=timeframes,
        historical_data=(data_ref,),
        universe_plans=(universe_ref,),
        walk_forward_templates=(wf_template_ref,),
        confidence_configs=(confidence_config_ref,),
        experiment_families=(exp_family_ref,),
        hypothesis_families=(hyp_family_ref,),
        metric_families=(metric_scope,),
        independence_metadata=(independence,),
        regime_policies=(regime_policy,),
    )


class TestCompileCampaignCartesianProduct:
    """Verify the Cartesian product expansion produces the correct count."""

    def test_2_strategies_2_timeframes_4_experiments(
        self,
        sample_common_config,
        sample_data_ref,
        sample_universe_ref,
        sample_wf_template_ref,
        sample_confidence_config_ref,
        sample_exp_family_ref,
        sample_hyp_family_ref,
        sample_metric_scope,
        sample_independence,
        sample_regime_policy,
        sample_output_policy,
    ) -> None:
        """2 strategies x 2 timeframes x 1 everything else = 4 experiments."""
        params = _make_multi_param_set(
            strategy_names=("strat_a", "strat_b"),
            timeframes=("1h", "4h"),
            common_config=sample_common_config,
            data_ref=sample_data_ref,
            universe_ref=sample_universe_ref,
            wf_template_ref=sample_wf_template_ref,
            confidence_config_ref=sample_confidence_config_ref,
            exp_family_ref=sample_exp_family_ref,
            hyp_family_ref=sample_hyp_family_ref,
            metric_scope=sample_metric_scope,
            independence=sample_independence,
            regime_policy=sample_regime_policy,
        )
        definition = ResearchCampaignDefinition(
            campaign_id="cartesian_test",
            campaign_schema_version="0.69.0-dev",
            parameters=params,
            max_experiment_count=100,
            execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
            output_policy=sample_output_policy,
        )

        result = compile_campaign(definition, compile_only=True)
        assert isinstance(result, CompiledCampaign)
        assert result.experiment_count == 4
        assert len(result.experiments) == 4

    def test_1x1_product(
        self,
        sample_definition,
    ) -> None:
        """1 of each dimension = 1 experiment."""
        result = compile_campaign(sample_definition, compile_only=True)
        assert isinstance(result, CompiledCampaign)
        assert result.experiment_count == 1


class TestCompileCampaignFilters:
    """Test that include/exclude filter rules work during compilation."""

    def test_include_rule_selects_strategy(
        self,
        sample_common_config,
        sample_data_ref,
        sample_universe_ref,
        sample_wf_template_ref,
        sample_confidence_config_ref,
        sample_exp_family_ref,
        sample_hyp_family_ref,
        sample_metric_scope,
        sample_independence,
        sample_regime_policy,
        sample_output_policy,
    ) -> None:
        """Include rule for 'strat_a' selects only that strategy."""
        params = _make_multi_param_set(
            strategy_names=("strat_a", "strat_b"),
            timeframes=("1h",),
            common_config=sample_common_config,
            data_ref=sample_data_ref,
            universe_ref=sample_universe_ref,
            wf_template_ref=sample_wf_template_ref,
            confidence_config_ref=sample_confidence_config_ref,
            exp_family_ref=sample_exp_family_ref,
            hyp_family_ref=sample_hyp_family_ref,
            metric_scope=sample_metric_scope,
            independence=sample_independence,
            regime_policy=sample_regime_policy,
        )
        params = CampaignParameterSet(
            common_config=params.common_config,
            strategies=params.strategies,
            timeframes=params.timeframes,
            historical_data=params.historical_data,
            universe_plans=params.universe_plans,
            walk_forward_templates=params.walk_forward_templates,
            confidence_configs=params.confidence_configs,
            experiment_families=params.experiment_families,
            hypothesis_families=params.hypothesis_families,
            metric_families=params.metric_families,
            independence_metadata=params.independence_metadata,
            regime_policies=params.regime_policies,
            include_rules=(
                CampaignFilterRule(
                    field="strategy_name",
                    operator=FilterOperator.EQUALS,
                    value="strat_a",
                    action="include",
                ),
            ),
        )
        definition = ResearchCampaignDefinition(
            campaign_id="filter_test",
            campaign_schema_version="0.69.0-dev",
            parameters=params,
            max_experiment_count=10,
            execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
            output_policy=sample_output_policy,
        )
        result = compile_campaign(definition, compile_only=True)
        assert isinstance(result, CompiledCampaign)
        assert result.experiment_count == 1
        assert result.experiments[0].strategy.strategy_name == "strat_a"

    def test_exclude_rule_removes_strategy(
        self,
        sample_common_config,
        sample_data_ref,
        sample_universe_ref,
        sample_wf_template_ref,
        sample_confidence_config_ref,
        sample_exp_family_ref,
        sample_hyp_family_ref,
        sample_metric_scope,
        sample_independence,
        sample_regime_policy,
        sample_output_policy,
    ) -> None:
        """Exclude rule for 'strat_b' removes that strategy."""
        params = _make_multi_param_set(
            strategy_names=("strat_a", "strat_b"),
            timeframes=("1h",),
            common_config=sample_common_config,
            data_ref=sample_data_ref,
            universe_ref=sample_universe_ref,
            wf_template_ref=sample_wf_template_ref,
            confidence_config_ref=sample_confidence_config_ref,
            exp_family_ref=sample_exp_family_ref,
            hyp_family_ref=sample_hyp_family_ref,
            metric_scope=sample_metric_scope,
            independence=sample_independence,
            regime_policy=sample_regime_policy,
        )
        params = CampaignParameterSet(
            common_config=params.common_config,
            strategies=params.strategies,
            timeframes=params.timeframes,
            historical_data=params.historical_data,
            universe_plans=params.universe_plans,
            walk_forward_templates=params.walk_forward_templates,
            confidence_configs=params.confidence_configs,
            experiment_families=params.experiment_families,
            hypothesis_families=params.hypothesis_families,
            metric_families=params.metric_families,
            independence_metadata=params.independence_metadata,
            regime_policies=params.regime_policies,
            exclude_rules=(
                CampaignFilterRule(
                    field="strategy_name",
                    operator=FilterOperator.EQUALS,
                    value="strat_b",
                    action="exclude",
                ),
            ),
        )
        definition = ResearchCampaignDefinition(
            campaign_id="filter_test_exclude",
            campaign_schema_version="0.69.0-dev",
            parameters=params,
            max_experiment_count=10,
            execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
            output_policy=sample_output_policy,
        )
        result = compile_campaign(definition, compile_only=True)
        assert isinstance(result, CompiledCampaign)
        assert result.experiment_count == 1
        assert result.experiments[0].strategy.strategy_name == "strat_a"


class TestCompileCampaignContradictoryRules:
    """Test that contradictory filter rules raise during compilation."""

    def test_contradictory_include_exclude_raises(
        self,
        sample_definition,
    ) -> None:
        """Same field/value include+exclude raises."""
        from hunter.research_campaign.filters import check_contradictory_rules

        inc = CampaignFilterRule(
            field="strategy_name",
            operator=FilterOperator.EQUALS,
            value="strat_a",
            action="include",
        )
        exc = CampaignFilterRule(
            field="strategy_name",
            operator=FilterOperator.EQUALS,
            value="strat_a",
            action="exclude",
        )
        with pytest.raises(ResearchCampaignFilterError, match="Contradictory"):
            check_contradictory_rules((inc, exc))


class TestCompileCampaignDuplicateExperiments:
    """Test that duplicate logical experiments raise."""

    def test_duplicate_experiments_raises(
        self,
        sample_common_config,
        sample_data_ref,
        sample_universe_ref,
        sample_wf_template_ref,
        sample_confidence_config_ref,
        sample_exp_family_ref,
        sample_hyp_family_ref,
        sample_metric_scope,
        sample_independence,
        sample_regime_policy,
        sample_output_policy,
    ) -> None:
        """Two identical parameter values produce duplicates → error."""
        params = CampaignParameterSet(
            common_config=sample_common_config,
            strategies=(
                __import__("hunter.research_campaign.models", fromlist=["StrategyReference"])
                .StrategyReference(
                    strategy_name="dup_strat",
                    strategy_path="/tmp/dup",
                    fingerprint="fp_dup",
                ),
                __import__("hunter.research_campaign.models", fromlist=["StrategyReference"])
                .StrategyReference(
                    strategy_name="dup_strat",
                    strategy_path="/tmp/dup2",
                    fingerprint="fp_dup",
                ),
            ),
            timeframes=("1h",),
            historical_data=(sample_data_ref,),
            universe_plans=(sample_universe_ref,),
            walk_forward_templates=(sample_wf_template_ref,),
            confidence_configs=(sample_confidence_config_ref,),
            experiment_families=(sample_exp_family_ref,),
            hypothesis_families=(sample_hyp_family_ref,),
            metric_families=(sample_metric_scope,),
            independence_metadata=(sample_independence,),
            regime_policies=(sample_regime_policy,),
        )
        definition = ResearchCampaignDefinition(
            campaign_id="dup_test",
            campaign_schema_version="0.69.0-dev",
            parameters=params,
            max_experiment_count=10,
            execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
            output_policy=sample_output_policy,
        )
        with pytest.raises(ResearchCampaignCompilationError, match="Duplicate logical experiment"):
            compile_campaign(definition, compile_only=True)


class TestCompileCampaignMaxCount:
    """Test that max_experiment_count is enforced."""

    def test_max_count_enforced(
        self,
        sample_common_config,
        sample_data_ref,
        sample_universe_ref,
        sample_wf_template_ref,
        sample_confidence_config_ref,
        sample_exp_family_ref,
        sample_hyp_family_ref,
        sample_metric_scope,
        sample_independence,
        sample_regime_policy,
        sample_output_policy,
    ) -> None:
        """Product size 4 exceeds max_experiment_count=2 → error."""
        params = _make_multi_param_set(
            strategy_names=("strat_a", "strat_b"),
            timeframes=("1h", "4h"),
            common_config=sample_common_config,
            data_ref=sample_data_ref,
            universe_ref=sample_universe_ref,
            wf_template_ref=sample_wf_template_ref,
            confidence_config_ref=sample_confidence_config_ref,
            exp_family_ref=sample_exp_family_ref,
            hyp_family_ref=sample_hyp_family_ref,
            metric_scope=sample_metric_scope,
            independence=sample_independence,
            regime_policy=sample_regime_policy,
        )
        definition = ResearchCampaignDefinition(
            campaign_id="max_count_test",
            campaign_schema_version="0.69.0-dev",
            parameters=params,
            max_experiment_count=2,
            execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
            output_policy=sample_output_policy,
        )
        with pytest.raises(ResearchCampaignCompilationError, match="max_experiment_count"):
            compile_campaign(definition, compile_only=True)


class TestCompileCampaignCompileOnly:
    """Test that compile-only mode returns CompiledCampaign only."""

    def test_compile_only_returns_compiled_campaign(
        self,
        sample_definition,
    ) -> None:
        """compile_only=True returns only CompiledCampaign, not a tuple."""
        result = compile_campaign(sample_definition, compile_only=True)
        assert isinstance(result, CompiledCampaign)
        assert not isinstance(result, tuple)

    def test_default_returns_tuple(
        self,
        sample_definition,
    ) -> None:
        """compile_only=False (default) returns (CompiledCampaign, RegistrationSet)."""
        result = compile_campaign(sample_definition)
        assert isinstance(result, tuple)
        assert len(result) == 2
        campaign, reg_set = result
        assert isinstance(campaign, CompiledCampaign)
        from hunter.research_campaign.models import CampaignRegistrationSet
        assert isinstance(reg_set, CampaignRegistrationSet)


class TestCompileCampaignFingerprints:
    """Test deterministic IDs and fingerprints."""

    def test_experiments_have_deterministic_ids(
        self,
        sample_definition,
    ) -> None:
        """Running compilation twice produces the same experiment IDs."""
        result1 = compile_campaign(sample_definition, compile_only=True)
        result2 = compile_campaign(sample_definition, compile_only=True)
        assert isinstance(result1, CompiledCampaign)
        assert isinstance(result2, CompiledCampaign)
        for e1, e2 in zip(result1.experiments, result2.experiments):
            assert e1.experiment_id == e2.experiment_id
            assert e1.fingerprint == e2.fingerprint

    def test_campaign_has_fingerprint(
        self,
        sample_definition,
    ) -> None:
        """CompiledCampaign fingerprint is non-empty."""
        result = compile_campaign(sample_definition, compile_only=True)
        assert isinstance(result, CompiledCampaign)
        assert result.fingerprint != ""

    def test_walk_forward_plan_has_fingerprint(
        self,
        sample_definition,
    ) -> None:
        """Each compiled experiment's walk_forward_plan has a non-empty fingerprint."""
        result = compile_campaign(sample_definition, compile_only=True)
        assert isinstance(result, CompiledCampaign)
        for exp in result.experiments:
            assert exp.walk_forward_plan.fingerprint != ""

    def test_fingerprint_stable(
        self,
        sample_common_config,
        sample_data_ref,
        sample_universe_ref,
        sample_wf_template_ref,
        sample_confidence_config_ref,
        sample_exp_family_ref,
        sample_hyp_family_ref,
        sample_metric_scope,
        sample_independence,
        sample_regime_policy,
        sample_output_policy,
    ) -> None:
        """Same inputs produce same campaign fingerprint."""
        params = _make_multi_param_set(
            strategy_names=("strat_a",),
            timeframes=("1h", "4h"),
            common_config=sample_common_config,
            data_ref=sample_data_ref,
            universe_ref=sample_universe_ref,
            wf_template_ref=sample_wf_template_ref,
            confidence_config_ref=sample_confidence_config_ref,
            exp_family_ref=sample_exp_family_ref,
            hyp_family_ref=sample_hyp_family_ref,
            metric_scope=sample_metric_scope,
            independence=sample_independence,
            regime_policy=sample_regime_policy,
        )
        def1 = ResearchCampaignDefinition(
            campaign_id="fp_stability",
            campaign_schema_version="0.69.0-dev",
            parameters=params,
            max_experiment_count=10,
            execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
            output_policy=sample_output_policy,
        )
        def2 = ResearchCampaignDefinition(
            campaign_id="fp_stability",
            campaign_schema_version="0.69.0-dev",
            parameters=params,
            max_experiment_count=10,
            execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
            output_policy=sample_output_policy,
        )
        r1 = compile_campaign(def1, compile_only=True)
        r2 = compile_campaign(def2, compile_only=True)
        assert isinstance(r1, CompiledCampaign)
        assert isinstance(r2, CompiledCampaign)
        assert r1.fingerprint == r2.fingerprint
        for e1, e2 in zip(r1.experiments, r2.experiments):
            assert e1.experiment_id == e2.experiment_id


class TestCompileCampaignZeroResult:
    """Test that a zero-result campaign raises ZERO_EXPERIMENT_CAMPAIGN."""

    def test_all_excluded_raises(
        self,
        sample_definition,
    ) -> None:
        """If all experiments are excluded by filter, compilation raises."""
        from hunter.research_campaign.models import CampaignFilterRule, FilterOperator

        # Add an exclude-all rule.
        params = CampaignParameterSet(
            common_config=sample_definition.parameters.common_config,
            strategies=sample_definition.parameters.strategies,
            timeframes=sample_definition.parameters.timeframes,
            historical_data=sample_definition.parameters.historical_data,
            universe_plans=sample_definition.parameters.universe_plans,
            walk_forward_templates=sample_definition.parameters.walk_forward_templates,
            confidence_configs=sample_definition.parameters.confidence_configs,
            experiment_families=sample_definition.parameters.experiment_families,
            hypothesis_families=sample_definition.parameters.hypothesis_families,
            metric_families=sample_definition.parameters.metric_families,
            independence_metadata=sample_definition.parameters.independence_metadata,
            regime_policies=sample_definition.parameters.regime_policies,
            exclude_rules=(
                CampaignFilterRule(
                    field="strategy_name",
                    operator=FilterOperator.EQUALS,
                    value=sample_definition.parameters.strategies[0].strategy_name,
                    action="exclude",
                ),
            ),
        )
        definition = ResearchCampaignDefinition(
            campaign_id="zero_test",
            campaign_schema_version="0.69.0-dev",
            parameters=params,
            max_experiment_count=10,
            execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
            output_policy=sample_definition.output_policy,
        )
        with pytest.raises(ResearchCampaignCompilationError, match="zero experiments"):
            compile_campaign(definition, compile_only=True)


class TestCompileCampaignExcludedCount:
    """Verify excluded_count is tracked correctly."""

    def test_excluded_count_reflects_filtered(
        self,
        sample_common_config,
        sample_data_ref,
        sample_universe_ref,
        sample_wf_template_ref,
        sample_confidence_config_ref,
        sample_exp_family_ref,
        sample_hyp_family_ref,
        sample_metric_scope,
        sample_independence,
        sample_regime_policy,
        sample_output_policy,
    ) -> None:
        """When 1 of 2 strategies is excluded, excluded_count should be 1."""
        params = _make_multi_param_set(
            strategy_names=("strat_a", "strat_b"),
            timeframes=("1h",),
            common_config=sample_common_config,
            data_ref=sample_data_ref,
            universe_ref=sample_universe_ref,
            wf_template_ref=sample_wf_template_ref,
            confidence_config_ref=sample_confidence_config_ref,
            exp_family_ref=sample_exp_family_ref,
            hyp_family_ref=sample_hyp_family_ref,
            metric_scope=sample_metric_scope,
            independence=sample_independence,
            regime_policy=sample_regime_policy,
        )
        params = CampaignParameterSet(
            common_config=params.common_config,
            strategies=params.strategies,
            timeframes=params.timeframes,
            historical_data=params.historical_data,
            universe_plans=params.universe_plans,
            walk_forward_templates=params.walk_forward_templates,
            confidence_configs=params.confidence_configs,
            experiment_families=params.experiment_families,
            hypothesis_families=params.hypothesis_families,
            metric_families=params.metric_families,
            independence_metadata=params.independence_metadata,
            regime_policies=params.regime_policies,
            exclude_rules=(
                CampaignFilterRule(
                    field="strategy_name",
                    operator=FilterOperator.EQUALS,
                    value="strat_b",
                    action="exclude",
                ),
            ),
        )
        definition = ResearchCampaignDefinition(
            campaign_id="excluded_count_test",
            campaign_schema_version="0.69.0-dev",
            parameters=params,
            max_experiment_count=10,
            execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
            output_policy=sample_output_policy,
        )
        result = compile_campaign(definition, compile_only=True)
        assert isinstance(result, CompiledCampaign)
        assert result.experiment_count == 1  # Only strat_a
        assert result.excluded_count == 1  # strat_b was excluded
