"""Shared pytest fixtures for research_campaign tests (MVP-69/MVP-70)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from hunter.research_campaign.models import (
    CampaignExecutionPolicy,
    CampaignFilterRule,
    CampaignOutputPolicy,
    CampaignParameterSet,
    CampaignResumeManifest,
    CampaignStatusSummary,
    CampaignEvidenceSummary,
    CampaignDossier,
    CompiledCampaign,
    CompiledExperiment,
    ExperimentEvidence,
    ExperimentExecutionRecord,
    ExperimentOutcome,
    FamilyReference,
    FilterOperator,
    HistoricalDataReference,
    IndependenceMetadata,
    MetricFamilyScope,
    PriorExperimentEvidence,
    RegimePolicy,
    ResearchCampaignDefinition,
    ResearchCampaignSafetyFlags,
    ResumePolicy,
    StatisticalConfidenceConfigReference,
    StrategyReference,
    UniversePlanReference,
    WalkForwardTemplateReference,
    CampaignStatus,
)
from hunter.research_evidence_ledger.models import IndependenceClass
from hunter.research_statistical_confidence.models import (
    BootstrapConfig,
    RobustnessCriteria,
    StatisticalConfidenceConfig,
)
from hunter.research_walk_forward.fingerprint import (
    plan_fingerprint as wf_plan_fingerprint,
)
from hunter.research_walk_forward.models import (
    MarketRegimeLabel,
    WalkForwardCommonConfig,
    WalkForwardExperimentPlan,
    WalkForwardMode,
    WalkForwardSafetyFlags,
    WalkForwardWindow,
)


@pytest.fixture(scope="session")
def sample_strategy_ref() -> StrategyReference:
    return StrategyReference(
        strategy_name="test_strategy",
        strategy_path="/tmp/strategies/test",
        fingerprint="strat_fp_001",
    )


@pytest.fixture(scope="session")
def sample_data_ref() -> HistoricalDataReference:
    return HistoricalDataReference(
        data_id="ohlcv_1h",
        data_path="/tmp/data/ohlcv_1h",
        fingerprint="data_fp_001",
    )


@pytest.fixture(scope="session")
def sample_universe_ref() -> UniversePlanReference:
    return UniversePlanReference(
        universe_plan_id="uni_plan_a",
        universe_plan_path="/tmp/plans/uni_plan_a",
        candidate_pairlist=("BTC/USDT", "ETH/USDT"),
        baseline_pairlist=("BTC/USDT",),
        candidate_universe_fingerprint="cand_fp_001",
        baseline_universe_fingerprint="base_fp_001",
        fingerprint="uni_fp_001",
    )


@pytest.fixture(scope="session")
def sample_wf_window() -> WalkForwardWindow:
    return WalkForwardWindow(
        selection_start="2024-01-01",
        selection_end="2024-06-01",
        evaluation_start="2024-06-01",
        evaluation_end="2024-12-01",
        regime_label=MarketRegimeLabel.UNKNOWN,
    )


@pytest.fixture(scope="session")
def sample_wf_template_ref(sample_wf_window) -> WalkForwardTemplateReference:
    return WalkForwardTemplateReference(
        template_id="wf_rolling_001",
        mode="ROLLING",
        windows=(sample_wf_window,),
        contiguous=False,
        fingerprint="wf_tmpl_fp_001",
    )


@pytest.fixture(scope="session")
def sample_common_config() -> WalkForwardCommonConfig:
    return WalkForwardCommonConfig(
        strategy_name="test_strategy",
        strategy_path="/tmp/strategies/test",
        data_path="/tmp/data/ohlcv_1h",
        timeframe="1h",
        balance=Decimal("10000"),
        stake=Decimal("100"),
        max_open_trades=5,
        fee=Decimal("0.001"),
        executable_path="/usr/bin/freqtrade",
        protections=(),
        timeout_seconds=300,
    )


@pytest.fixture(scope="session")
def sample_bootstrap_config() -> BootstrapConfig:
    return BootstrapConfig(seed=1, iterations=10)


@pytest.fixture(scope="session")
def sample_robustness_criteria() -> RobustnessCriteria:
    return RobustnessCriteria(
        sign_share_threshold=Decimal("0.8"),
        maximum_influence_ratio=Decimal("0.3"),
        confidence_level=Decimal("0.95"),
    )


@pytest.fixture(scope="session")
def sample_confidence_config(
    sample_bootstrap_config,
    sample_robustness_criteria,
) -> StatisticalConfidenceConfig:
    return StatisticalConfidenceConfig(
        minimum_available_window_count=3,
        confidence_level=Decimal("0.95"),
        bootstrap=sample_bootstrap_config,
        robustness=sample_robustness_criteria,
    )


@pytest.fixture(scope="session")
def sample_confidence_config_ref(
    sample_confidence_config,
) -> StatisticalConfidenceConfigReference:
    return StatisticalConfidenceConfigReference(
        config_id="conf_a",
        config=sample_confidence_config,
        fingerprint="conf_fp_001",
    )


@pytest.fixture(scope="session")
def sample_exp_family_ref() -> FamilyReference:
    return FamilyReference(
        family_id="exp_fam_a",
        family_type="experiment",
        fingerprint="exp_fam_fp_001",
    )


@pytest.fixture(scope="session")
def sample_hyp_family_ref() -> FamilyReference:
    return FamilyReference(
        family_id="hyp_fam_a",
        family_type="hypothesis",
        fingerprint="hyp_fam_fp_001",
    )


@pytest.fixture(scope="session")
def sample_metric_scope() -> MetricFamilyScope:
    return MetricFamilyScope(
        metric_names=("sharpe_ratio", "sortino_ratio"),
        direction_policy="ANY",
    )


@pytest.fixture(scope="session")
def sample_independence() -> IndependenceMetadata:
    return IndependenceMetadata(
        independence_class=IndependenceClass.INDEPENDENT,
        source_experiment_ids=(),
        notes="",
    )


@pytest.fixture(scope="session")
def sample_regime_policy() -> RegimePolicy:
    return RegimePolicy(
        regime_label=MarketRegimeLabel.UNKNOWN,
        required=False,
    )


@pytest.fixture(scope="session")
def sample_output_policy() -> CampaignOutputPolicy:
    return CampaignOutputPolicy(
        output_dir="/tmp/campaign_output",
        overwrite=False,
        write_checkpoints=True,
        checkpoint_version_policy="SEQUENTIAL",
    )


@pytest.fixture(scope="session")
def sample_param_set(
    sample_strategy_ref,
    sample_data_ref,
    sample_universe_ref,
    sample_wf_template_ref,
    sample_confidence_config_ref,
    sample_exp_family_ref,
    sample_hyp_family_ref,
    sample_metric_scope,
    sample_independence,
    sample_regime_policy,
    sample_common_config,
) -> CampaignParameterSet:
    return CampaignParameterSet(
        common_config=sample_common_config,
        strategies=(sample_strategy_ref,),
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


@pytest.fixture(scope="session")
def sample_definition(
    sample_param_set,
    sample_output_policy,
) -> ResearchCampaignDefinition:
    return ResearchCampaignDefinition(
        campaign_id="campaign_test_001",
        campaign_schema_version="0.69.0-dev",
        parameters=sample_param_set,
        max_experiment_count=10,
        execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
        stop_after_n_failures=None,
        resume_policy=ResumePolicy.RERUN,
        output_policy=sample_output_policy,
        safety_flags=ResearchCampaignSafetyFlags(),
        reason_codes=(),
        metadata={},
        fingerprint="",
    )


@pytest.fixture(scope="session")
def sample_wf_plan(
    sample_common_config,
    sample_wf_window,
) -> WalkForwardExperimentPlan:
    plan = WalkForwardExperimentPlan(
        mode=WalkForwardMode.ROLLING,
        windows=(sample_wf_window,),
        common=sample_common_config,
        contiguous=False,
        safety_flags=WalkForwardSafetyFlags(),
        fingerprint="",
        reason_codes=(),
        metadata={},
    )
    # Compute deterministic fingerprint.
    fp = wf_plan_fingerprint(plan)
    return WalkForwardExperimentPlan(
        mode=plan.mode,
        windows=plan.windows,
        common=plan.common,
        contiguous=plan.contiguous,
        safety_flags=plan.safety_flags,
        fingerprint=fp,
        reason_codes=plan.reason_codes,
        metadata=plan.metadata,
    )


@pytest.fixture(scope="session")
def sample_compiled_experiment(
    sample_strategy_ref,
    sample_data_ref,
    sample_universe_ref,
    sample_wf_template_ref,
    sample_confidence_config_ref,
    sample_exp_family_ref,
    sample_hyp_family_ref,
    sample_metric_scope,
    sample_independence,
    sample_regime_policy,
    sample_wf_plan,
) -> CompiledExperiment:
    return CompiledExperiment(
        experiment_id="exp_001_abc123",
        campaign_id="campaign_test_001",
        strategy=sample_strategy_ref,
        timeframe="1h",
        historical_data=sample_data_ref,
        universe_plan=sample_universe_ref,
        walk_forward_template=sample_wf_template_ref,
        confidence_config=sample_confidence_config_ref,
        experiment_family=sample_exp_family_ref,
        hypothesis_family=sample_hyp_family_ref,
        metric_family=sample_metric_scope,
        independence=sample_independence,
        regime_policy=sample_regime_policy,
        walk_forward_plan=sample_wf_plan,
        fingerprint="exp_fp_001",
        registration_fingerprint="reg_fp_001",
    )


@pytest.fixture(scope="session")
def sample_compiled_campaign(
    sample_definition,
    sample_compiled_experiment,
) -> CompiledCampaign:
    return CompiledCampaign(
        campaign=sample_definition,
        experiments=(sample_compiled_experiment,),
        experiment_count=1,
        excluded_count=0,
        fingerprint="cc_fp_001",
        compile_timestamp=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        reason_codes=(),
    )
