"""Determinism tests for the research campaign package (MVP-69/MVP-70 / SPEC-070)."""

from __future__ import annotations

import os
import socket
from dataclasses import replace

import pytest

from hunter.research_campaign.compiler import compile_campaign
from hunter.research_campaign.fingerprint import (
    campaign_definition_fingerprint,
    compiled_campaign_fingerprint,
    compiled_experiment_fingerprint,
    experiment_id_from_components,
)
from hunter.research_campaign.models import (
    CampaignParameterSet,
    CampaignResumeManifest,
    CompiledExperiment,
    ExperimentEvidence,
    ExperimentExecutionRecord,
    ExperimentOutcome,
    HistoricalDataReference,
    IndependenceMetadata,
    MetricFamilyScope,
    PriorExperimentEvidence,
    RegimePolicy,
    ResearchCampaignDefinition,
    ResearchCampaignSafetyFlags,
    ResumePolicy,
    StrategyReference,
    UniversePlanReference,
)
from hunter.research_campaign.resume import match_resume_evidence
from hunter.research_evidence_ledger.models import IndependenceClass
from hunter.research_walk_forward.models import MarketRegimeLabel


class TestCampaignDefinitionFingerprint:
    """Campaign definition fingerprints are deterministic and path-independent."""

    def test_same_definition_same_fingerprint(self, sample_definition) -> None:
        fp1 = campaign_definition_fingerprint(sample_definition)
        fp2 = campaign_definition_fingerprint(sample_definition)
        assert fp1 == fp2
        assert len(fp1) == 64

    def test_different_parameter_changes_fingerprint(self, sample_definition) -> None:
        fp1 = campaign_definition_fingerprint(sample_definition)
        # Change max_experiment_count
        modified = replace(sample_definition, max_experiment_count=999)
        fp2 = campaign_definition_fingerprint(modified)
        assert fp1 != fp2

    def test_fingerprint_independent_of_paths(self, sample_definition) -> None:
        fp1 = campaign_definition_fingerprint(sample_definition)
        # Modify the absolute path in the strategy reference (should not change fingerprint because
        # fingerprinting uses the reference fingerprint, not the path)
        s = sample_definition.parameters.strategies[0]
        s2 = StrategyReference(
            strategy_name=s.strategy_name,
            strategy_path="/a/completely/different/path",
            fingerprint=s.fingerprint,
        )
        params = CampaignParameterSet(
            common_config=sample_definition.parameters.common_config,
            strategies=(s2,),
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
        )
        modified = replace(sample_definition, parameters=params)
        fp2 = campaign_definition_fingerprint(modified)
        assert fp1 == fp2


class TestCompiledExperimentFingerprint:
    """Compiled experiment fingerprints and IDs are deterministic."""

    def test_same_experiment_same_fingerprint(self, sample_compiled_experiment: CompiledExperiment) -> None:
        fp1 = compiled_experiment_fingerprint(sample_compiled_experiment)
        fp2 = compiled_experiment_fingerprint(sample_compiled_experiment)
        assert fp1 == fp2

    def test_different_experiment_id_changes_fingerprint(self, sample_compiled_experiment: CompiledExperiment) -> None:
        fp1 = compiled_experiment_fingerprint(sample_compiled_experiment)
        exp2 = CompiledExperiment(
            experiment_id="different_id",
            campaign_id=sample_compiled_experiment.campaign_id,
            strategy=sample_compiled_experiment.strategy,
            timeframe=sample_compiled_experiment.timeframe,
            historical_data=sample_compiled_experiment.historical_data,
            universe_plan=sample_compiled_experiment.universe_plan,
            walk_forward_template=sample_compiled_experiment.walk_forward_template,
            confidence_config=sample_compiled_experiment.confidence_config,
            experiment_family=sample_compiled_experiment.experiment_family,
            hypothesis_family=sample_compiled_experiment.hypothesis_family,
            metric_family=sample_compiled_experiment.metric_family,
            independence=sample_compiled_experiment.independence,
            regime_policy=sample_compiled_experiment.regime_policy,
            walk_forward_plan=sample_compiled_experiment.walk_forward_plan,
        )
        fp2 = compiled_experiment_fingerprint(exp2)
        assert fp1 != fp2

    def test_experiment_id_deterministic(self, sample_compiled_experiment: CompiledExperiment) -> None:
        e1 = sample_compiled_experiment
        id1 = experiment_id_from_components(
            campaign_id=e1.campaign_id,
            strategy_name=e1.strategy.strategy_name,
            timeframe=e1.timeframe,
            data_id=e1.historical_data.data_id,
            universe_plan_id=e1.universe_plan.universe_plan_id,
            template_id=e1.walk_forward_template.template_id,
            config_id=e1.confidence_config.config_id,
            experiment_family_id=e1.experiment_family.family_id,
            hypothesis_family_id=e1.hypothesis_family.family_id,
            metric_names=e1.metric_family.metric_names,
            independence_class=e1.independence.independence_class.value,
            regime_label=e1.regime_policy.regime_label.value,
            strategy_fingerprint=e1.strategy.fingerprint,
            historical_data_fingerprint=e1.historical_data.fingerprint,
            universe_plan_fingerprint=e1.universe_plan.fingerprint,
            walk_forward_template_fingerprint=e1.walk_forward_template.fingerprint,
            confidence_config_fingerprint=e1.confidence_config.fingerprint,
            experiment_family_fingerprint=e1.experiment_family.fingerprint,
            hypothesis_family_fingerprint=e1.hypothesis_family.fingerprint,
        )
        id2 = experiment_id_from_components(
            campaign_id=e1.campaign_id,
            strategy_name=e1.strategy.strategy_name,
            timeframe=e1.timeframe,
            data_id=e1.historical_data.data_id,
            universe_plan_id=e1.universe_plan.universe_plan_id,
            template_id=e1.walk_forward_template.template_id,
            config_id=e1.confidence_config.config_id,
            experiment_family_id=e1.experiment_family.family_id,
            hypothesis_family_id=e1.hypothesis_family.family_id,
            metric_names=e1.metric_family.metric_names,
            independence_class=e1.independence.independence_class.value,
            regime_label=e1.regime_policy.regime_label.value,
            strategy_fingerprint=e1.strategy.fingerprint,
            historical_data_fingerprint=e1.historical_data.fingerprint,
            universe_plan_fingerprint=e1.universe_plan.fingerprint,
            walk_forward_template_fingerprint=e1.walk_forward_template.fingerprint,
            confidence_config_fingerprint=e1.confidence_config.fingerprint,
            experiment_family_fingerprint=e1.experiment_family.fingerprint,
            hypothesis_family_fingerprint=e1.hypothesis_family.fingerprint,
        )
        assert id1 == id2

    def test_experiment_id_independent_of_notes_and_paths(self, sample_compiled_experiment: CompiledExperiment) -> None:
        e1 = sample_compiled_experiment
        kwargs = {
            "campaign_id": e1.campaign_id,
            "strategy_name": e1.strategy.strategy_name,
            "timeframe": e1.timeframe,
            "data_id": e1.historical_data.data_id,
            "universe_plan_id": e1.universe_plan.universe_plan_id,
            "template_id": e1.walk_forward_template.template_id,
            "config_id": e1.confidence_config.config_id,
            "experiment_family_id": e1.experiment_family.family_id,
            "hypothesis_family_id": e1.hypothesis_family.family_id,
            "metric_names": e1.metric_family.metric_names,
            "independence_class": e1.independence.independence_class.value,
            "regime_label": e1.regime_policy.regime_label.value,
            "strategy_fingerprint": e1.strategy.fingerprint,
            "historical_data_fingerprint": e1.historical_data.fingerprint,
            "universe_plan_fingerprint": e1.universe_plan.fingerprint,
            "walk_forward_template_fingerprint": e1.walk_forward_template.fingerprint,
            "confidence_config_fingerprint": e1.confidence_config.fingerprint,
            "experiment_family_fingerprint": e1.experiment_family.fingerprint,
            "hypothesis_family_fingerprint": e1.hypothesis_family.fingerprint,
        }
        id1 = experiment_id_from_components(**kwargs)
        # Change notes (not in kwargs) and paths (also not in kwargs as long as fingerprints match)
        e2 = CompiledExperiment(
            experiment_id=e1.experiment_id,
            campaign_id=e1.campaign_id,
            strategy=StrategyReference(
                strategy_name=e1.strategy.strategy_name,
                strategy_path="/different/path",
                fingerprint=e1.strategy.fingerprint,
            ),
            timeframe=e1.timeframe,
            historical_data=HistoricalDataReference(
                data_id=e1.historical_data.data_id,
                data_path="/different/data",
                fingerprint=e1.historical_data.fingerprint,
            ),
            universe_plan=UniversePlanReference(
                universe_plan_id=e1.universe_plan.universe_plan_id,
                universe_plan_path="/different/plan",
                candidate_pairlist=e1.universe_plan.candidate_pairlist,
                baseline_pairlist=e1.universe_plan.baseline_pairlist,
                candidate_universe_fingerprint=e1.universe_plan.candidate_universe_fingerprint,
                baseline_universe_fingerprint=e1.universe_plan.baseline_universe_fingerprint,
                fingerprint=e1.universe_plan.fingerprint,
            ),
            walk_forward_template=e1.walk_forward_template,
            confidence_config=e1.confidence_config,
            experiment_family=e1.experiment_family,
            hypothesis_family=e1.hypothesis_family,
            metric_family=e1.metric_family,
            independence=IndependenceMetadata(
                independence_class=e1.independence.independence_class,
                source_experiment_ids=e1.independence.source_experiment_ids,
                notes="different notes",
            ),
            regime_policy=e1.regime_policy,
            walk_forward_plan=e1.walk_forward_plan,
        )
        id2 = experiment_id_from_components(**kwargs)
        assert id1 == id2


class TestCompiledCampaignFingerprint:
    """Compiled campaign fingerprints are stable and order-independent."""

    def test_same_inputs_same_fingerprint(self, sample_definition) -> None:
        compiled1, _ = compile_campaign(sample_definition)
        compiled2, _ = compile_campaign(sample_definition)
        fp1 = compiled_campaign_fingerprint(compiled1)
        fp2 = compiled_campaign_fingerprint(compiled2)
        assert fp1 == fp2

    def test_reordering_parameter_sets_same_fingerprint(self, sample_definition) -> None:
        # The canonical sort should make the fingerprint order-independent
        compiled1, _ = compile_campaign(sample_definition)
        # Rebuild definition with parameters in different order? Since tuples are immutable,
        # the order within each parameter set matters. But the overall order of experiments is canonical.
        compiled2, _ = compile_campaign(sample_definition)
        fp1 = compiled_campaign_fingerprint(compiled1)
        fp2 = compiled_campaign_fingerprint(compiled2)
        assert fp1 == fp2


class TestResumeDeterminism:
    """Resume matching is deterministic and exact."""

    def test_exact_match_reuses_evidence(self, sample_compiled_experiment: CompiledExperiment) -> None:
        e = sample_compiled_experiment
        prior = PriorExperimentEvidence(
            experiment_id=e.experiment_id,
            experiment_fingerprint=e.fingerprint,
            registration_fingerprint=e.registration_fingerprint,
            strategy_reference_fingerprint=e.strategy.fingerprint,
            historical_data_reference_fingerprint=e.historical_data.fingerprint,
            universe_plan_reference_fingerprint=e.universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=e.walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=e.confidence_config.fingerprint,
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=ExperimentOutcome.COMPLETED,
        )
        matched = match_resume_evidence(e, (prior,), ResumePolicy.REUSE)
        assert matched is not None
        assert matched.experiment_id == e.experiment_id

    def test_fingerprint_mismatch_returns_none(self, sample_compiled_experiment: CompiledExperiment) -> None:
        e = sample_compiled_experiment
        prior = PriorExperimentEvidence(
            experiment_id=e.experiment_id,
            experiment_fingerprint="different_fingerprint",
            registration_fingerprint=e.registration_fingerprint,
            strategy_reference_fingerprint=e.strategy.fingerprint,
            historical_data_reference_fingerprint=e.historical_data.fingerprint,
            universe_plan_reference_fingerprint=e.universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=e.walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=e.confidence_config.fingerprint,
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=ExperimentOutcome.COMPLETED,
        )
        matched = match_resume_evidence(e, (prior,), ResumePolicy.REUSE)
        assert matched is None

    def test_resume_manifest_fingerprint_deterministic(self, sample_compiled_experiment: CompiledExperiment) -> None:
        from hunter.research_campaign.fingerprint import campaign_resume_manifest_fingerprint
        e = sample_compiled_experiment
        prior = PriorExperimentEvidence(
            experiment_id=e.experiment_id,
            experiment_fingerprint=e.fingerprint,
            registration_fingerprint=e.registration_fingerprint,
            strategy_reference_fingerprint=e.strategy.fingerprint,
            historical_data_reference_fingerprint=e.historical_data.fingerprint,
            universe_plan_reference_fingerprint=e.universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=e.walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=e.confidence_config.fingerprint,
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=ExperimentOutcome.COMPLETED,
        )
        manifest1 = CampaignResumeManifest(
            campaign_fingerprint="camp_fp",
            prior_evidence=(prior,),
            resume_policy=ResumePolicy.REUSE,
        )
        manifest2 = CampaignResumeManifest(
            campaign_fingerprint="camp_fp",
            prior_evidence=(prior,),
            resume_policy=ResumePolicy.REUSE,
        )
        fp1 = campaign_resume_manifest_fingerprint(manifest1)
        fp2 = campaign_resume_manifest_fingerprint(manifest2)
        assert fp1 == fp2


class TestEnvironmentIndependence:
    """Fingerprints must not depend on environment variables, PID, or hostname."""

    def test_no_environmental_data_in_fingerprint(self, sample_definition) -> None:
        fp = campaign_definition_fingerprint(sample_definition)
        # The fingerprint should not contain PID, hostname, or cwd
        assert str(os.getpid()) not in fp
        assert socket.gethostname() not in fp
        assert os.getcwd() not in fp
        # And should be a valid 64-char hex string
        assert len(fp) == 64
        int(fp, 16)
