"""Tests for research_campaign models (MVP-69/MVP-70)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

import pytest

from hunter.research_campaign.errors import ResearchCampaignDefinitionError

from hunter.research_campaign.models import (
    CampaignArtifactManifest,
    CampaignCheckpoint,
    CampaignDossier,
    CampaignEvidenceSummary,
    CampaignExecutionManifest,
    CampaignExecutionPolicy,
    CampaignFilterRule,
    CampaignOutputPolicy,
    CampaignParameterSet,
    CampaignRegistrationSet,
    CampaignResumeManifest,
    CampaignStatus,
    CampaignStatusSummary,
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


# ---------------------------------------------------------------------------
# ResearchCampaignSafetyFlags
# ---------------------------------------------------------------------------


class TestResearchCampaignSafetyFlags:
    def test_default_flags(self) -> None:
        flags = ResearchCampaignSafetyFlags()
        assert flags.research_only is True
        assert flags.execution_approval_granted is False
        assert flags.production_approval_granted is False
        assert flags.live_trading_allowed is False
        assert flags.automatic_execution_allowed is False
        assert flags.human_approval_required is True
        assert flags.no_action_commands_emitted is True
        assert flags.no_network_connection is True
        assert flags.no_database_connection is True
        assert flags.no_exchange_connection is True
        assert flags.no_remote_changes is True
        assert flags.no_parallel_execution is True
        assert flags.no_direct_subprocess is True
        assert flags.no_strategy_mutation is True
        assert flags.no_universe_mutation is True
        assert flags.no_config_mutation is True

    def test_research_only_false_raises(self) -> None:
        with pytest.raises(ValueError, match="research_only must be True"):
            ResearchCampaignSafetyFlags(research_only=False)

    def test_execution_approval_granted_raises(self) -> None:
        with pytest.raises(ValueError, match="execution_approval_granted must be False"):
            ResearchCampaignSafetyFlags(execution_approval_granted=True)

    def test_production_approval_granted_raises(self) -> None:
        with pytest.raises(ValueError, match="production_approval_granted must be False"):
            ResearchCampaignSafetyFlags(production_approval_granted=True)

    def test_live_trading_allowed_raises(self) -> None:
        with pytest.raises(ValueError, match="live_trading_allowed must be False"):
            ResearchCampaignSafetyFlags(live_trading_allowed=True)

    def test_automatic_execution_allowed_raises(self) -> None:
        with pytest.raises(ValueError, match="automatic_execution_allowed must be False"):
            ResearchCampaignSafetyFlags(automatic_execution_allowed=True)

    def test_human_approval_required_false_raises(self) -> None:
        with pytest.raises(ValueError, match="human_approval_required must be True"):
            ResearchCampaignSafetyFlags(human_approval_required=False)

    def test_no_direct_subprocess_false_raises(self) -> None:
        with pytest.raises(ValueError, match="no_direct_subprocess must be True"):
            ResearchCampaignSafetyFlags(no_direct_subprocess=False)

    def test_no_parallel_execution_false_raises(self) -> None:
        with pytest.raises(ValueError, match="no_parallel_execution must be True"):
            ResearchCampaignSafetyFlags(no_parallel_execution=False)

    def test_frozen(self) -> None:
        flags = ResearchCampaignSafetyFlags()
        with pytest.raises(AttributeError):
            flags.research_only = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CampaignFilterRule
# ---------------------------------------------------------------------------


class TestCampaignFilterRule:
    def test_valid_rule(self) -> None:
        rule = CampaignFilterRule(
            field="strategy_name",
            operator=FilterOperator.EQUALS,
            value="test_strategy",
            action="include",
        )
        assert rule.field == "strategy_name"
        assert rule.operator == FilterOperator.EQUALS
        assert rule.value == "test_strategy"
        assert rule.action == "include"

    def test_empty_field_raises(self) -> None:
        with pytest.raises(ValueError, match="field must be a non-empty string"):
            CampaignFilterRule(
                field="",
                operator=FilterOperator.EQUALS,
                value="x",
                action="include",
            )

    def test_invalid_action_raises(self) -> None:
        with pytest.raises(ValueError, match="action must be 'include' or 'exclude'"):
            CampaignFilterRule(
                field="strategy_name",
                operator=FilterOperator.EQUALS,
                value="x",
                action="invalid",
            )

    def test_operator_from_string(self) -> None:
        rule = CampaignFilterRule(
            field="timeframe",
            operator="EQUALS",
            value="1h",
            action="include",
        )
        assert rule.operator == FilterOperator.EQUALS

    def test_in_requires_tuple(self) -> None:
        with pytest.raises(ValueError, match="IN requires a tuple value"):
            CampaignFilterRule(
                field="timeframe",
                operator=FilterOperator.IN,
                value="not_a_tuple",
                action="include",
            )

    def test_not_in_requires_tuple(self) -> None:
        with pytest.raises(ValueError, match="NOT_IN requires a tuple value"):
            CampaignFilterRule(
                field="timeframe",
                operator=FilterOperator.NOT_IN,
                value="not_a_tuple",
                action="include",
            )


# ---------------------------------------------------------------------------
# CampaignParameterSet
# ---------------------------------------------------------------------------


class TestCampaignParameterSet:
    def test_empty_strategies_raises(self, sample_common_config) -> None:
        with pytest.raises(ValueError, match="strategies must not be empty"):
            CampaignParameterSet(
                common_config=sample_common_config,
                strategies=(),
                timeframes=("1h",),
                historical_data=(),
                universe_plans=(),
                walk_forward_templates=(),
                confidence_configs=(),
                experiment_families=(),
                hypothesis_families=(),
                metric_families=(),
                independence_metadata=(),
                regime_policies=(),
            )

    def test_empty_timeframes_raises(self, sample_common_config, sample_strategy_ref) -> None:
        with pytest.raises(ValueError, match="timeframes must not be empty"):
            CampaignParameterSet(
                common_config=sample_common_config,
                strategies=(sample_strategy_ref,),
                timeframes=(),
                historical_data=(),
                universe_plans=(),
                walk_forward_templates=(),
                confidence_configs=(),
                experiment_families=(),
                hypothesis_families=(),
                metric_families=(),
                independence_metadata=(),
                regime_policies=(),
            )

    def test_list_instead_of_tuple_raises(self, sample_common_config) -> None:
        with pytest.raises(ValueError, match="strategies must be a tuple"):
            CampaignParameterSet(
                common_config=sample_common_config,
                strategies=["not_a_tuple"],  # type: ignore[arg-type]
                timeframes=("1h",),
                historical_data=(),
                universe_plans=(),
                walk_forward_templates=(),
                confidence_configs=(),
                experiment_families=(),
                hypothesis_families=(),
                metric_families=(),
                independence_metadata=(),
                regime_policies=(),
            )

    def test_valid_param_set(self, sample_param_set) -> None:
        assert isinstance(sample_param_set.strategies, tuple)
        assert len(sample_param_set.strategies) == 1
        assert len(sample_param_set.timeframes) == 1
        assert len(sample_param_set.historical_data) == 1


# ---------------------------------------------------------------------------
# CampaignOutputPolicy
# ---------------------------------------------------------------------------


class TestCampaignOutputPolicy:
    def test_output_dir_coercion(self) -> None:
        policy = CampaignOutputPolicy(output_dir=Path("/tmp/test_out"))
        assert isinstance(policy.output_dir, str)
        assert "/tmp/test_out" in policy.output_dir

    def test_invalid_checkpoint_policy(self) -> None:
        with pytest.raises(ValueError, match="checkpoint_version_policy"):
            CampaignOutputPolicy(
                output_dir="/tmp/out",
                checkpoint_version_policy="INVALID",
            )


# ---------------------------------------------------------------------------
# ResearchCampaignDefinition
# ---------------------------------------------------------------------------


class TestResearchCampaignDefinition:
    def test_valid_definition(self, sample_definition) -> None:
        assert sample_definition.campaign_id == "campaign_test_001"
        assert sample_definition.execution_policy == CampaignExecutionPolicy.COLLECT_ALL
        assert sample_definition.resume_policy == ResumePolicy.RERUN

    def test_empty_campaign_id_raises(self, sample_param_set, sample_output_policy) -> None:
        with pytest.raises(ValueError, match="campaign_id must be a non-empty string"):
            ResearchCampaignDefinition(
                campaign_id="",
                campaign_schema_version="0.69.0-dev",
                parameters=sample_param_set,
                max_experiment_count=10,
                execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
                output_policy=sample_output_policy,
            )

    def test_negative_max_experiment_count_raises(
        self, sample_param_set, sample_output_policy
    ) -> None:
        with pytest.raises(ResearchCampaignDefinitionError, match="max_experiment_count must be a positive integer"):
            ResearchCampaignDefinition(
                campaign_id="test",
                campaign_schema_version="0.69.0-dev",
                parameters=sample_param_set,
                max_experiment_count=0,
                execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
                output_policy=sample_output_policy,
            )

    def test_stop_after_n_failures_requires_positive(
        self, sample_param_set, sample_output_policy
    ) -> None:
        """STOP_AFTER_N_FAILURES requires a positive threshold."""
        with pytest.raises(ValueError, match="stop_after_n_failures must be a positive integer"):
            ResearchCampaignDefinition(
                campaign_id="test",
                campaign_schema_version="0.69.0-dev",
                parameters=sample_param_set,
                max_experiment_count=10,
                execution_policy=CampaignExecutionPolicy.STOP_AFTER_N_FAILURES,
                stop_after_n_failures=0,
                output_policy=sample_output_policy,
            )

    def test_stop_after_n_failures_none_raises(
        self, sample_param_set, sample_output_policy
    ) -> None:
        with pytest.raises(ValueError, match="stop_after_n_failures must be a positive integer"):
            ResearchCampaignDefinition(
                campaign_id="test",
                campaign_schema_version="0.69.0-dev",
                parameters=sample_param_set,
                max_experiment_count=10,
                execution_policy=CampaignExecutionPolicy.STOP_AFTER_N_FAILURES,
                stop_after_n_failures=None,
                output_policy=sample_output_policy,
            )

    def test_stop_after_n_failures_with_wrong_policy_raises(
        self, sample_param_set, sample_output_policy
    ) -> None:
        with pytest.raises(ValueError, match="stop_after_n_failures must be None"):
            ResearchCampaignDefinition(
                campaign_id="test",
                campaign_schema_version="0.69.0-dev",
                parameters=sample_param_set,
                max_experiment_count=10,
                execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
                stop_after_n_failures=3,
                output_policy=sample_output_policy,
            )

    def test_resume_policy_defaults_to_rerun(self, sample_param_set, sample_output_policy) -> None:
        definition = ResearchCampaignDefinition(
            campaign_id="test",
            campaign_schema_version="0.69.0-dev",
            parameters=sample_param_set,
            max_experiment_count=10,
            execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
            output_policy=sample_output_policy,
        )
        assert definition.resume_policy == ResumePolicy.RERUN

    def test_resume_policy_from_string(self, sample_param_set, sample_output_policy) -> None:
        definition = ResearchCampaignDefinition(
            campaign_id="test",
            campaign_schema_version="0.69.0-dev",
            parameters=sample_param_set,
            max_experiment_count=10,
            execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
            output_policy=sample_output_policy,
            resume_policy="REUSE",
        )
        assert definition.resume_policy == ResumePolicy.REUSE

    def test_execution_policy_from_string(self, sample_param_set, sample_output_policy) -> None:
        definition = ResearchCampaignDefinition(
            campaign_id="test",
            campaign_schema_version="0.69.0-dev",
            parameters=sample_param_set,
            max_experiment_count=10,
            execution_policy="FAIL_FAST",
            output_policy=sample_output_policy,
        )
        assert definition.execution_policy == CampaignExecutionPolicy.FAIL_FAST

    def test_reason_codes_coerced(self, sample_param_set, sample_output_policy) -> None:
        definition = ResearchCampaignDefinition(
            campaign_id="test",
            campaign_schema_version="0.69.0-dev",
            parameters=sample_param_set,
            max_experiment_count=10,
            execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
            output_policy=sample_output_policy,
            reason_codes=("CODE_A", "CODE_B"),
        )
        assert definition.reason_codes == ("CODE_A", "CODE_B")


# ---------------------------------------------------------------------------
# CompiledExperiment
# ---------------------------------------------------------------------------


class TestCompiledExperiment:
    def test_valid_experiment(self, sample_compiled_experiment) -> None:
        assert isinstance(sample_compiled_experiment.experiment_id, str)
        assert sample_compiled_experiment.campaign_id == "campaign_test_001"

    def test_empty_experiment_id_raises(
        self,
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
    ) -> None:
        with pytest.raises(ValueError, match="experiment_id must be a non-empty string"):
            CompiledExperiment(
                experiment_id="",
                campaign_id="test",
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
            )

    def test_empty_campaign_id_raises(
        self,
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
    ) -> None:
        with pytest.raises(ValueError, match="campaign_id must be a non-empty string"):
            CompiledExperiment(
                experiment_id="exp_001",
                campaign_id="",
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
            )


# ---------------------------------------------------------------------------
# CompiledCampaign
# ---------------------------------------------------------------------------


class TestCompiledCampaign:
    def test_experiment_count_mismatch_raises(self, sample_definition) -> None:
        with pytest.raises(ValueError, match="experiment_count must match len"):
            CompiledCampaign(
                campaign=sample_definition,
                experiments=(),
                experiment_count=1,
                excluded_count=0,
                fingerprint="fp",
                compile_timestamp=datetime.now(timezone.utc),
                reason_codes=(),
            )

    def test_zero_count_matches_empty(self, sample_definition) -> None:
        CompiledCampaign(
            campaign=sample_definition,
            experiments=(),
            experiment_count=0,
            excluded_count=0,
            fingerprint="fp",
            compile_timestamp=datetime.now(timezone.utc),
            reason_codes=(),
        )

    def test_valid_compiled(self, sample_compiled_campaign) -> None:
        assert sample_compiled_campaign.experiment_count == 1
        assert len(sample_compiled_campaign.experiments) == 1


# ---------------------------------------------------------------------------
# ExperimentOutcome coercion
# ---------------------------------------------------------------------------


class TestExperimentOutcomeCoercion:
    def test_outcome_from_string(self) -> None:
        record = ExperimentExecutionRecord(
            experiment_id="exp_001",
            campaign_id="camp_test",
            experiment_fingerprint="fp1",
            registration_fingerprint="fp2",
            outcome="COMPLETED",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            evidence=ExperimentEvidence(),
            reason_codes=(),
            notes="",
        )
        assert record.outcome == ExperimentOutcome.COMPLETED

    def test_outcome_from_enum(self) -> None:
        record = ExperimentExecutionRecord(
            experiment_id="exp_001",
            campaign_id="camp_test",
            experiment_fingerprint="fp1",
            registration_fingerprint="fp2",
            outcome=ExperimentOutcome.FAILED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            evidence=ExperimentEvidence(),
            reason_codes=(),
            notes="",
        )
        assert record.outcome == ExperimentOutcome.FAILED

    def test_invalid_outcome_string_raises(self) -> None:
        with pytest.raises(ValueError, match="'INVALID_OUTCOME'"):
            ExperimentExecutionRecord(
                experiment_id="exp_001",
                campaign_id="camp_test",
                experiment_fingerprint="fp1",
                registration_fingerprint="fp2",
                outcome="INVALID_OUTCOME",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                evidence=ExperimentEvidence(),
                reason_codes=(),
                notes="",
            )

    def test_prior_outcome_from_string(self) -> None:
        prior = PriorExperimentEvidence(
            experiment_id="exp_001",
            experiment_fingerprint="fp1",
            registration_fingerprint="fp2",
            strategy_reference_fingerprint="sfp",
            historical_data_reference_fingerprint="hfp",
            universe_plan_reference_fingerprint="ufp",
            walk_forward_template_reference_fingerprint="wtfp",
            confidence_config_reference_fingerprint="cfp",
            walk_forward_report_fingerprint="wrfp",
            confidence_report_fingerprint="crfp",
            ledger_entry_fingerprint="lfp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome="FAILED",
        )
        assert prior.outcome == ExperimentOutcome.FAILED

    def test_checkpoint_status_from_string(self) -> None:
        checkpoint = CampaignCheckpoint(
            checkpoint_id="cp_001",
            campaign_id="camp_test",
            checkpoint_index=0,
            experiment_records=(),
            status="RUNNING",
        )
        assert checkpoint.status == CampaignStatus.RUNNING

    def test_campaign_resume_manifest_policy_default(self) -> None:
        manifest = CampaignResumeManifest(
            campaign_fingerprint="fp",
            prior_evidence=(),
        )
        assert manifest.resume_policy == ResumePolicy.RERUN

    def test_campaign_resume_manifest_policy_from_string(self) -> None:
        manifest = CampaignResumeManifest(
            campaign_fingerprint="fp",
            prior_evidence=(),
            resume_policy="REUSE",
        )
        assert manifest.resume_policy == ResumePolicy.REUSE


# ---------------------------------------------------------------------------
# CampaignExecutionManifest
# ---------------------------------------------------------------------------


class TestCampaignExecutionManifest:
    def test_valid_manifest(self, sample_definition, sample_compiled_campaign) -> None:
        reg_set = CampaignRegistrationSet(
            campaign=sample_compiled_campaign,
            registrations=(),
        )
        manifest = CampaignExecutionManifest(
            campaign_definition=sample_definition,
            compiled_campaign=sample_compiled_campaign,
            registration_set=reg_set,
        )
        assert manifest.campaign_definition is sample_definition
        assert manifest.compiled_campaign is sample_compiled_campaign


# ---------------------------------------------------------------------------
# CampaignStatusSummary
# ---------------------------------------------------------------------------


class TestCampaignStatusSummary:
    def test_valid_summary(self) -> None:
        summary = CampaignStatusSummary(
            total=5,
            completed=3,
            failed=1,
            blocked=0,
            timed_out=1,
            unsupported=0,
            insufficient_evidence=0,
            withdrawn=0,
            skipped_by_policy=0,
            stale_resume_evidence=0,
        )
        assert summary.total == 5
        assert summary.completed == 3


# ---------------------------------------------------------------------------
# CampaignEvidenceSummary
# ---------------------------------------------------------------------------


class TestCampaignEvidenceSummary:
    def test_valid_summary(self) -> None:
        summary = CampaignEvidenceSummary(
            walk_forward_attempted=5,
            walk_forward_completed=4,
            confidence_attempted=5,
            confidence_completed=3,
            ledger_entries=5,
            ledger_snapshots=2,
        )
        assert summary.walk_forward_attempted == 5
        assert summary.confidence_completed == 3


# ---------------------------------------------------------------------------
# CampaignDossier
# ---------------------------------------------------------------------------


class TestCampaignDossier:
    def test_valid_dossier(self) -> None:
        status = CampaignStatusSummary(
            total=1, completed=1, failed=0, blocked=0, timed_out=0,
            unsupported=0, insufficient_evidence=0, withdrawn=0,
            skipped_by_policy=0, stale_resume_evidence=0,
        )
        evidence = CampaignEvidenceSummary(
            walk_forward_attempted=1, walk_forward_completed=1,
            confidence_attempted=1, confidence_completed=1,
            ledger_entries=1, ledger_snapshots=1,
        )
        dossier = CampaignDossier(
            campaign_id="camp_test",
            campaign_fingerprint="cfp",
            compiled_campaign_fingerprint="ccfp",
            status_summary=status,
            evidence_summary=evidence,
            execution_records=(),
            safety_flags=ResearchCampaignSafetyFlags(),
        )
        assert dossier.campaign_id == "camp_test"
        assert dossier.safety_flags.research_only is True


# ---------------------------------------------------------------------------
# Additional safety / coercion tests
# ---------------------------------------------------------------------------


class TestSafetyFlagFailClosed:
    """Verify safety flags are fail-closed (default safe)."""

    def test_default_is_safe(self) -> None:
        flags = ResearchCampaignSafetyFlags()
        # All dangerous flags default to False/True appropriately
        assert flags.live_trading_allowed is False
        assert flags.automatic_execution_allowed is False
        assert flags.execution_approval_granted is False
        assert flags.production_approval_granted is False

    def test_research_only_cannot_be_disabled(self) -> None:
        with pytest.raises(ValueError, match="research_only must be True"):
            ResearchCampaignSafetyFlags(research_only=False)


class TestStringFieldValidation:
    def test_strategy_ref_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="strategy_name must be a non-empty string"):
            StrategyReference(strategy_name="", strategy_path="/tmp/s")

    def test_data_ref_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="data_id must be a non-empty string"):
            HistoricalDataReference(data_id="", data_path="/tmp/d")

    def test_universe_ref_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="universe_plan_id must be a non-empty string"):
            UniversePlanReference(
                universe_plan_id="",
                universe_plan_path="/tmp/u",
                candidate_pairlist=(),
                baseline_pairlist=(),
                candidate_universe_fingerprint="c",
                baseline_universe_fingerprint="b",
            )

    def test_wf_template_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="template_id must be a non-empty string"):
            WalkForwardTemplateReference(
                template_id="",
                mode="ROLLING",
                windows=(),
            )

    def test_confidence_config_ref_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="config_id must be a non-empty string"):
            StatisticalConfidenceConfigReference(
                config_id="",
                config=StatisticalConfidenceConfig(
                    minimum_available_window_count=3,
                    confidence_level=Decimal("0.95"),
                    bootstrap=BootstrapConfig(seed=1, iterations=10),
                    robustness=RobustnessCriteria(
                        sign_share_threshold=Decimal("0.8"),
                        maximum_influence_ratio=Decimal("0.3"),
                        confidence_level=Decimal("0.95"),
                    ),
                ),
            )

    def test_family_ref_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="family_id must be a non-empty string"):
            FamilyReference(family_id="", family_type="experiment")

    def test_metric_scope_empty_direction_policy_raises(self) -> None:
        with pytest.raises(ValueError, match="direction_policy must be a non-empty string"):
            MetricFamilyScope(metric_names=("a",), direction_policy="")


class TestReferenceCoercion:
    def test_strategy_ref_path_coercion(self) -> None:
        ref = StrategyReference(
            strategy_name="s1",
            strategy_path=Path("/tmp/strategies/s1"),
        )
        assert isinstance(ref.strategy_path, str)

    def test_data_ref_path_coercion(self) -> None:
        ref = HistoricalDataReference(
            data_id="d1",
            data_path=Path("/tmp/data/d1"),
        )
        assert isinstance(ref.data_path, str)

    def test_universe_ref_pairlist_coercion(self) -> None:
        ref = UniversePlanReference(
            universe_plan_id="u1",
            universe_plan_path="/tmp/u",
            candidate_pairlist=["BTC/USDT", "ETH/USDT"],
            baseline_pairlist=["BTC/USDT"],
            candidate_universe_fingerprint="c",
            baseline_universe_fingerprint="b",
        )
        assert isinstance(ref.candidate_pairlist, tuple)
        assert ref.candidate_pairlist == ("BTC/USDT", "ETH/USDT")

    def test_output_policy_path_coercion(self) -> None:
        policy = CampaignOutputPolicy(output_dir=Path("/tmp/out"))
        assert isinstance(policy.output_dir, str)


class TestMappingProxyTypeCoercion:
    def test_metadata_coercion(self, sample_param_set, sample_output_policy) -> None:
        definition = ResearchCampaignDefinition(
            campaign_id="test",
            campaign_schema_version="0.69.0-dev",
            parameters=sample_param_set,
            max_experiment_count=10,
            execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
            output_policy=sample_output_policy,
            metadata={"key": "value"},
        )
        assert isinstance(definition.metadata, MappingProxyType)

    def test_registration_set_mapping(self, sample_compiled_campaign) -> None:
        reg_set = CampaignRegistrationSet(
            campaign=sample_compiled_campaign,
            registrations=(),
            registration_by_experiment_id={"e1": "test"},
        )
        assert isinstance(reg_set.registration_by_experiment_id, MappingProxyType)


class TestCampaignCheckpoint:
    def test_valid_checkpoint(self) -> None:
        checkpoint = CampaignCheckpoint(
            checkpoint_id="cp_001",
            campaign_id="camp_test",
            checkpoint_index=0,
            experiment_records=(),
            status=CampaignStatus.PENDING,
        )
        assert checkpoint.checkpoint_index == 0
        assert checkpoint.status == CampaignStatus.PENDING

    def test_status_from_string(self) -> None:
        checkpoint = CampaignCheckpoint(
            checkpoint_id="cp_002",
            campaign_id="camp_test",
            checkpoint_index=1,
            experiment_records=(),
            status="COMPLETED",
        )
        assert checkpoint.status == CampaignStatus.COMPLETED


class TestCampaignArtifactManifest:
    def test_valid_manifest(self) -> None:
        manifest = CampaignArtifactManifest(
            campaign_id="camp_test",
            artifact_paths=("/tmp/out/dossier.json",),
            dossier_fingerprint="dfp",
        )
        assert manifest.campaign_id == "camp_test"


class TestExperimentEvidence:
    def test_default_empty(self) -> None:
        evidence = ExperimentEvidence()
        assert evidence.walk_forward_report is None
        assert evidence.confidence_report is None
