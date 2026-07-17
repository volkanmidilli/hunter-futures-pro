"""Tests for campaign registration set creation (MVP-69 / SPEC-070).

No subprocess, threading, network, eval, exec, or dynamic code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hunter.research_campaign.compiler import compile_campaign
from hunter.research_campaign.errors import ResearchCampaignCompilationError
from hunter.research_campaign.fingerprint import registration_set_fingerprint
from hunter.research_campaign.models import (
    CampaignExecutionPolicy,
    CampaignParameterSet,
    ResearchCampaignDefinition,
    ResearchCampaignSafetyFlags,
    ResumePolicy,
)
from hunter.research_evidence_ledger.models import ExperimentStatus


class TestCreateCampaignRegistrationSet:
    """Tests for create_campaign_registration_set."""

    def test_builds_registration_for_each_experiment(
        self, sample_definition: ResearchCampaignDefinition
    ) -> None:
        """Every compiled experiment gets an ExperimentRegistration with status REGISTERED."""
        compiled, reg_set = compile_campaign(sample_definition, compile_only=False)

        assert len(compiled.experiments) == len(reg_set.registrations)
        for reg in reg_set.registrations:
            assert reg.status == ExperimentStatus.REGISTERED

    def test_registration_has_correct_fields(
        self, sample_definition: ResearchCampaignDefinition
    ) -> None:
        """Registration fields match the compiled experiment."""
        compiled, reg_set = compile_campaign(sample_definition, compile_only=False)

        compiled_exp = compiled.experiments[0]
        reg = reg_set.registrations[0]

        assert reg.experiment_id == compiled_exp.experiment_id
        assert reg.strategy_name == compiled_exp.strategy.strategy_name
        assert reg.universe_plan == compiled_exp.universe_plan.universe_plan_id
        assert reg.timeframe == compiled_exp.timeframe
        assert reg.walk_forward_plan_fingerprint == compiled_exp.walk_forward_plan.fingerprint
        assert reg.metric_family == compiled_exp.metric_family.metric_names
        assert reg.independence == compiled_exp.independence.independence_class
        assert reg.hypothesis_family_id == compiled_exp.hypothesis_family.family_id
        assert reg.experiment_family_id == compiled_exp.experiment_family.family_id
        assert reg.confidence_config_fingerprint == compiled_exp.confidence_config.fingerprint
        assert reg.fingerprint is not None and len(reg.fingerprint) > 0
        assert reg.direction_policy == compiled_exp.metric_family.direction_policy
        assert reg.hypothesis == f"{compiled_exp.campaign_id}:{compiled_exp.experiment_id}"

    def test_registration_fingerprint_assigned_to_experiment(
        self, sample_definition: ResearchCampaignDefinition
    ) -> None:
        """registration_fingerprint is set on each compiled experiment."""
        compiled, reg_set = compile_campaign(sample_definition, compile_only=False)

        for i, exp in enumerate(compiled.experiments):
            reg = reg_set.registrations[i]
            assert exp.registration_fingerprint == reg.fingerprint
            assert len(exp.registration_fingerprint) > 0

    def test_registration_set_fingerprint_is_non_empty(
        self, sample_definition: ResearchCampaignDefinition
    ) -> None:
        """The registration set has a non-empty fingerprint."""
        compiled, reg_set = compile_campaign(sample_definition, compile_only=False)

        assert reg_set.fingerprint is not None
        assert len(reg_set.fingerprint) > 0

    def test_duplicate_experiment_ids_rejected(
        self, sample_definition: ResearchCampaignDefinition
    ) -> None:
        """Compilation must reject duplicate logical experiments."""
        # The current sample_definition has 1 strategy × 1 timeframe × 1 data × ...
        # which produces 1 unique experiment. To trigger a duplicate, we can't
        # create identical parameter combinations. Instead, we add duplicate
        # parameters that produce identical experiments via our definition.
        # Since the compiler deduplicates by canonical combination key,
        # identical combos raise DUPLICATE_LOGICAL_EXPERIMENT.

        # Create a definition with the SAME parameters duplicated, which would
        # produce identical combinations and trigger the duplicate check.
        # We can do this by having two identical strategies.
        params = sample_definition.parameters
        dup_strategy = params.strategies[0]  # Same strategy as the existing one

        dup_params = CampaignParameterSet(
            common_config=params.common_config,
            strategies=(params.strategies[0], dup_strategy),  # Duplicate
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
        )
        dup_definition = ResearchCampaignDefinition(
            campaign_id="dup_test",
            campaign_schema_version=sample_definition.campaign_schema_version,
            parameters=dup_params,
            max_experiment_count=10,
            execution_policy=CampaignExecutionPolicy.COLLECT_ALL,
            stop_after_n_failures=None,
            resume_policy=ResumePolicy.RERUN,
            output_policy=sample_definition.output_policy,
            safety_flags=ResearchCampaignSafetyFlags(),
            reason_codes=(),
            metadata={},
            fingerprint="",
        )
        with pytest.raises(ResearchCampaignCompilationError) as excinfo:
            compile_campaign(dup_definition, compile_only=False)
        assert "DUPLICATE_LOGICAL_EXPERIMENT" in str(excinfo.value) or "Duplicate" in str(excinfo.value)

    def test_hypothesis_format(self, sample_definition: ResearchCampaignDefinition) -> None:
        """Hypothesis is formatted as campaign_id:experiment_id."""
        compiled, reg_set = compile_campaign(sample_definition, compile_only=False)
        for reg in reg_set.registrations:
            expected = f"{compiled.campaign.campaign_id}:{reg.experiment_id}"
            assert reg.hypothesis == expected
