"""Tests for resume manifest building and evidence matching (MVP-69 / SPEC-070).

No subprocess, threading, network, eval, exec, or dynamic code.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.research_campaign.models import (
    CampaignResumeManifest,
    CompiledExperiment,
    ExperimentEvidence,
    ExperimentExecutionRecord,
    ExperimentOutcome,
    PriorExperimentEvidence,
    ResearchCampaignSafetyFlags,
    ResumePolicy,
)
from hunter.research_campaign.resume import (
    build_resume_manifest,
    match_resume_evidence,
)


# ===========================================================================
# Helpers
# ===========================================================================


def _make_record(
    compiled_exp: CompiledExperiment,
    outcome: ExperimentOutcome = ExperimentOutcome.COMPLETED,
) -> ExperimentExecutionRecord:
    """Create a minimal ExperimentExecutionRecord from a compiled experiment."""
    now = datetime.now(timezone.utc)
    evidence = ExperimentEvidence(
        walk_forward_report_fingerprint="wf_fp_001",
        confidence_report_fingerprint="conf_fp_001",
        ledger_entry_fingerprint="le_fp_001",
    )
    return ExperimentExecutionRecord(
        experiment_id=compiled_exp.experiment_id,
        campaign_id=compiled_exp.campaign_id,
        experiment_fingerprint=compiled_exp.fingerprint,
        registration_fingerprint=compiled_exp.registration_fingerprint,
        outcome=outcome,
        started_at=now,
        completed_at=now,
        evidence=evidence,
        reason_codes=(),
        notes="",
    )


# ===========================================================================
# build_resume_manifest
# ===========================================================================


class TestBuildResumeManifest:
    def test_builds_manifest_with_campaign_fingerprint(
        self,
        sample_definition,
        sample_compiled_campaign,
        sample_compiled_experiment,
    ) -> None:
        """Manifest has campaign_fingerprint and prior_evidence."""
        record = _make_record(sample_compiled_experiment)
        manifest = build_resume_manifest(
            sample_definition,
            sample_compiled_campaign,
            (record,),
            ResumePolicy.REUSE,
        )
        assert isinstance(manifest, CampaignResumeManifest)
        assert manifest.campaign_fingerprint is not None
        assert len(manifest.campaign_fingerprint) > 0
        assert len(manifest.prior_evidence) == 1

    def test_prior_evidence_includes_completed_records(
        self,
        sample_definition,
        sample_compiled_campaign,
        sample_compiled_experiment,
    ) -> None:
        """COMPLETED records produce prior evidence entries."""
        record = _make_record(sample_compiled_experiment)
        manifest = build_resume_manifest(
            sample_definition,
            sample_compiled_campaign,
            (record,),
            ResumePolicy.REUSE,
        )
        assert len(manifest.prior_evidence) == 1
        prior = manifest.prior_evidence[0]
        assert prior.experiment_id == record.experiment_id
        assert prior.experiment_fingerprint == record.experiment_fingerprint
        assert prior.registration_fingerprint == record.registration_fingerprint

    def test_failed_records_excluded(
        self,
        sample_definition,
        sample_compiled_campaign,
        sample_compiled_experiment,
    ) -> None:
        """FAILED records should NOT appear in prior_evidence."""
        record = _make_record(
            sample_compiled_experiment, ExperimentOutcome.FAILED
        )
        manifest = build_resume_manifest(
            sample_definition,
            sample_compiled_campaign,
            (record,),
            ResumePolicy.REUSE,
        )
        assert len(manifest.prior_evidence) == 0

    def test_insufficient_evidence_included(
        self,
        sample_definition,
        sample_compiled_campaign,
        sample_compiled_experiment,
    ) -> None:
        """INSUFFICIENT_EVIDENCE records should appear in prior_evidence."""
        record = _make_record(
            sample_compiled_experiment, ExperimentOutcome.INSUFFICIENT_EVIDENCE
        )
        manifest = build_resume_manifest(
            sample_definition,
            sample_compiled_campaign,
            (record,),
            ResumePolicy.REUSE,
        )
        assert len(manifest.prior_evidence) == 1


# ===========================================================================
# match_resume_evidence
# ===========================================================================


class TestMatchResumeEvidence:
    def test_returns_prior_when_all_fingerprints_match(
        self, sample_compiled_experiment
    ) -> None:
        """Returns PriorExperimentEvidence when all fingerprint fields match."""
        prior = PriorExperimentEvidence(
            experiment_id=sample_compiled_experiment.experiment_id,
            experiment_fingerprint=sample_compiled_experiment.fingerprint,
            registration_fingerprint=sample_compiled_experiment.registration_fingerprint,
            strategy_reference_fingerprint=sample_compiled_experiment.strategy.fingerprint,
            historical_data_reference_fingerprint=sample_compiled_experiment.historical_data.fingerprint,
            universe_plan_reference_fingerprint=sample_compiled_experiment.universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=sample_compiled_experiment.walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=sample_compiled_experiment.confidence_config.fingerprint,
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            ledger_snapshot_fingerprint="ls_fp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=ExperimentOutcome.COMPLETED,
            evidence=None,
        )
        result = match_resume_evidence(
            sample_compiled_experiment,
            (prior,),
            ResumePolicy.REUSE,
        )
        assert result is not None
        assert result.experiment_id == sample_compiled_experiment.experiment_id

    def test_returns_none_when_experiment_id_differs(
        self, sample_compiled_experiment
    ) -> None:
        """Returns None when experiment_id differs."""
        prior = PriorExperimentEvidence(
            experiment_id="different_id",
            experiment_fingerprint=sample_compiled_experiment.fingerprint,
            registration_fingerprint=sample_compiled_experiment.registration_fingerprint,
            strategy_reference_fingerprint=sample_compiled_experiment.strategy.fingerprint,
            historical_data_reference_fingerprint=sample_compiled_experiment.historical_data.fingerprint,
            universe_plan_reference_fingerprint=sample_compiled_experiment.universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=sample_compiled_experiment.walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=sample_compiled_experiment.confidence_config.fingerprint,
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            ledger_snapshot_fingerprint="ls_fp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=ExperimentOutcome.COMPLETED,
            evidence=None,
        )
        result = match_resume_evidence(
            sample_compiled_experiment,
            (prior,),
            ResumePolicy.REUSE,
        )
        assert result is None

    def test_returns_none_when_experiment_fingerprint_differs(
        self, sample_compiled_experiment
    ) -> None:
        """Returns None when experiment_fingerprint differs."""
        prior = PriorExperimentEvidence(
            experiment_id=sample_compiled_experiment.experiment_id,
            experiment_fingerprint="different_fp",
            registration_fingerprint=sample_compiled_experiment.registration_fingerprint,
            strategy_reference_fingerprint=sample_compiled_experiment.strategy.fingerprint,
            historical_data_reference_fingerprint=sample_compiled_experiment.historical_data.fingerprint,
            universe_plan_reference_fingerprint=sample_compiled_experiment.universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=sample_compiled_experiment.walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=sample_compiled_experiment.confidence_config.fingerprint,
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            ledger_snapshot_fingerprint="ls_fp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=ExperimentOutcome.COMPLETED,
            evidence=None,
        )
        result = match_resume_evidence(
            sample_compiled_experiment,
            (prior,),
            ResumePolicy.REUSE,
        )
        assert result is None

    def test_returns_none_when_registration_fingerprint_differs(
        self, sample_compiled_experiment
    ) -> None:
        """Returns None when registration_fingerprint differs."""
        prior = PriorExperimentEvidence(
            experiment_id=sample_compiled_experiment.experiment_id,
            experiment_fingerprint=sample_compiled_experiment.fingerprint,
            registration_fingerprint="different_reg_fp",
            strategy_reference_fingerprint=sample_compiled_experiment.strategy.fingerprint,
            historical_data_reference_fingerprint=sample_compiled_experiment.historical_data.fingerprint,
            universe_plan_reference_fingerprint=sample_compiled_experiment.universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=sample_compiled_experiment.walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=sample_compiled_experiment.confidence_config.fingerprint,
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            ledger_snapshot_fingerprint="ls_fp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=ExperimentOutcome.COMPLETED,
            evidence=None,
        )
        result = match_resume_evidence(
            sample_compiled_experiment,
            (prior,),
            ResumePolicy.REUSE,
        )
        assert result is None

    def test_returns_none_when_strategy_fingerprint_differs(
        self, sample_compiled_experiment
    ) -> None:
        """Returns None when strategy reference fingerprint differs."""
        prior = PriorExperimentEvidence(
            experiment_id=sample_compiled_experiment.experiment_id,
            experiment_fingerprint=sample_compiled_experiment.fingerprint,
            registration_fingerprint=sample_compiled_experiment.registration_fingerprint,
            strategy_reference_fingerprint="diff_strat_fp",
            historical_data_reference_fingerprint=sample_compiled_experiment.historical_data.fingerprint,
            universe_plan_reference_fingerprint=sample_compiled_experiment.universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=sample_compiled_experiment.walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=sample_compiled_experiment.confidence_config.fingerprint,
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            ledger_snapshot_fingerprint="ls_fp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=ExperimentOutcome.COMPLETED,
            evidence=None,
        )
        result = match_resume_evidence(
            sample_compiled_experiment,
            (prior,),
            ResumePolicy.REUSE,
        )
        assert result is None

    def test_returns_none_when_historical_data_ref_differs(
        self, sample_compiled_experiment
    ) -> None:
        """Returns None when historical data ref fingerprint differs."""
        prior = PriorExperimentEvidence(
            experiment_id=sample_compiled_experiment.experiment_id,
            experiment_fingerprint=sample_compiled_experiment.fingerprint,
            registration_fingerprint=sample_compiled_experiment.registration_fingerprint,
            strategy_reference_fingerprint=sample_compiled_experiment.strategy.fingerprint,
            historical_data_reference_fingerprint="diff_data_fp",
            universe_plan_reference_fingerprint=sample_compiled_experiment.universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=sample_compiled_experiment.walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=sample_compiled_experiment.confidence_config.fingerprint,
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            ledger_snapshot_fingerprint="ls_fp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=ExperimentOutcome.COMPLETED,
            evidence=None,
        )
        result = match_resume_evidence(
            sample_compiled_experiment,
            (prior,),
            ResumePolicy.REUSE,
        )
        assert result is None

    def test_block_policy_with_stale_evidence(
        self, sample_compiled_experiment
    ) -> None:
        """BLOCK policy: no match means None is returned (stale evidence)."""
        prior = PriorExperimentEvidence(
            experiment_id=sample_compiled_experiment.experiment_id,
            experiment_fingerprint="stale_fp",
            registration_fingerprint=sample_compiled_experiment.registration_fingerprint,
            strategy_reference_fingerprint=sample_compiled_experiment.strategy.fingerprint,
            historical_data_reference_fingerprint=sample_compiled_experiment.historical_data.fingerprint,
            universe_plan_reference_fingerprint=sample_compiled_experiment.universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=sample_compiled_experiment.walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=sample_compiled_experiment.confidence_config.fingerprint,
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            ledger_snapshot_fingerprint="ls_fp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=ExperimentOutcome.COMPLETED,
            evidence=None,
        )
        # With BLOCK policy, no exact match → None.
        result = match_resume_evidence(
            sample_compiled_experiment,
            (prior,),
            ResumePolicy.BLOCK,
        )
        assert result is None

    def test_reuse_completed_reruns_stale(
        self, sample_compiled_experiment
    ) -> None:
        """REUSE identifies matching evidence; stale evidence returns None."""
        # Matching prior
        matching_prior = PriorExperimentEvidence(
            experiment_id=sample_compiled_experiment.experiment_id,
            experiment_fingerprint=sample_compiled_experiment.fingerprint,
            registration_fingerprint=sample_compiled_experiment.registration_fingerprint,
            strategy_reference_fingerprint=sample_compiled_experiment.strategy.fingerprint,
            historical_data_reference_fingerprint=sample_compiled_experiment.historical_data.fingerprint,
            universe_plan_reference_fingerprint=sample_compiled_experiment.universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=sample_compiled_experiment.walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=sample_compiled_experiment.confidence_config.fingerprint,
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            ledger_snapshot_fingerprint="ls_fp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=ExperimentOutcome.COMPLETED,
            evidence=None,
        )
        result = match_resume_evidence(
            sample_compiled_experiment,
            (matching_prior,),
            ResumePolicy.REUSE,
        )
        assert result is not None  # Reuse matching

        # Stale prior (fingerprint differs)
        stale_prior = PriorExperimentEvidence(
            experiment_id=sample_compiled_experiment.experiment_id,
            experiment_fingerprint="stale_fp",
            registration_fingerprint=sample_compiled_experiment.registration_fingerprint,
            strategy_reference_fingerprint=sample_compiled_experiment.strategy.fingerprint,
            historical_data_reference_fingerprint=sample_compiled_experiment.historical_data.fingerprint,
            universe_plan_reference_fingerprint=sample_compiled_experiment.universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=sample_compiled_experiment.walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=sample_compiled_experiment.confidence_config.fingerprint,
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            ledger_snapshot_fingerprint="ls_fp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=ExperimentOutcome.COMPLETED,
            evidence=None,
        )
        result = match_resume_evidence(
            sample_compiled_experiment,
            (stale_prior,),
            ResumePolicy.RERUN,
        )
        assert result is None  # Rerun stale
