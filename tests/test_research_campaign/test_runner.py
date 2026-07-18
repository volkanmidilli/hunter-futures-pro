"""Tests for run_campaign_sequential — the sequential batch runner (MVP-70 / SPEC-070).

No subprocess, threading, network, eval, exec, or dynamic code.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hunter.research_campaign.compiler import compile_campaign
from hunter.research_campaign.engine import build_campaign_execution_manifest
from hunter.research_campaign.errors import ResearchCampaignRunnerError
from hunter.research_campaign.models import (
    CampaignExecutionManifest,
    CampaignExecutionPolicy,
    CampaignOutputPolicy,
    CampaignParameterSet,
    CampaignRegistrationSet,
    CampaignResumeManifest,
    CampaignStatus,
    CompiledCampaign,
    ExperimentExecutionRecord,
    ExperimentOutcome,
    PriorExperimentEvidence,
    ResearchCampaignDefinition,
    ResearchCampaignSafetyFlags,
    ResumePolicy,
)
from hunter.research_campaign.runner import run_campaign_sequential
from hunter.research_walk_forward.models import (
    WalkForwardExperimentReport,
)


# ===========================================================================
# Fixtures — built once per session, reused across tests
# ===========================================================================


@pytest.fixture(scope="module")
def compiled_and_registered(
    sample_definition: ResearchCampaignDefinition,
) -> tuple[CompiledCampaign, CampaignRegistrationSet]:
    """Compile a campaign definition once and return (campaign, reg_set)."""
    compiled, reg_set = compile_campaign(sample_definition, compile_only=False)
    return compiled, reg_set


@pytest.fixture(scope="module")
def execution_manifest(
    sample_definition: ResearchCampaignDefinition,
    compiled_and_registered: tuple[CompiledCampaign, CampaignRegistrationSet],
) -> CampaignExecutionManifest:
    """Build the execution manifest."""
    compiled, reg_set = compiled_and_registered
    return build_campaign_execution_manifest(sample_definition, compiled, reg_set)


# ===========================================================================
# COLLECT_ALL
# ===========================================================================


class TestCollectAll:
    """COLLECT_ALL: runs all experiments, produces COMPLETED."""

    def test_all_experiments_completed(
        self, execution_manifest: CampaignExecutionManifest
    ) -> None:
        """Under COLLECT_ALL, all experiments produce COMPLETED records."""
        mock_wf_report = MagicMock(spec=WalkForwardExperimentReport)
        mock_wf_report.fingerprint = "wf_fp_001"
        mock_conf_report = MagicMock(fingerprint="conf_fp_001")
        mock_entry = MagicMock(fingerprint="entry_fp_001")
        mock_snapshot = MagicMock(fingerprint="snap_fp_001")

        with (
            patch(
                "hunter.research_campaign.runner.run_walk_forward_for_experiment",
                return_value=mock_wf_report,
            ) as mock_wf,
            patch(
                "hunter.research_campaign.runner.run_confidence_for_experiment",
                return_value=mock_conf_report,
            ) as mock_conf,
            patch(
                "hunter.research_campaign.runner.ingest_experiment_evidence",
                return_value=(mock_entry, mock_snapshot),
            ) as mock_ingest,
        ):
            dossier = run_campaign_sequential(execution_manifest)

        assert dossier is not None
        for rec in dossier.execution_records:
            assert rec.outcome == ExperimentOutcome.COMPLETED, (
                f"Expected COMPLETED, got {rec.outcome} for {rec.experiment_id}"
            )
        assert dossier.status_summary.total == len(execution_manifest.compiled_campaign.experiments)
        assert dossier.status_summary.completed == len(execution_manifest.compiled_campaign.experiments)

    def test_insufficient_evidence_on_incomplete_windows(
        self,
        execution_manifest: CampaignExecutionManifest,
    ) -> None:
        """Incomplete walk-forward windows produce INSUFFICIENT_EVIDENCE, not FAILED."""
        mock_wf_report = MagicMock(spec=WalkForwardExperimentReport)
        mock_wf_report.fingerprint = "wf_fp_001"

        from hunter.research_campaign.errors import ResearchCampaignRunnerError
        from hunter.research_campaign.models import MISSING_WALK_FORWARD_EVIDENCE

        with (
            patch(
                "hunter.research_campaign.runner.run_walk_forward_for_experiment",
                return_value=mock_wf_report,
            ) as mock_wf,
            patch(
                "hunter.research_campaign.runner.run_confidence_for_experiment",
                side_effect=ResearchCampaignRunnerError(
                    "incomplete windows",
                    reason_code=MISSING_WALK_FORWARD_EVIDENCE,
                ),
            ) as mock_conf,
        ):
            dossier = run_campaign_sequential(execution_manifest)

        assert dossier is not None
        for rec in dossier.execution_records:
            assert rec.outcome == ExperimentOutcome.INSUFFICIENT_EVIDENCE, (
                f"Expected INSUFFICIENT_EVIDENCE, got {rec.outcome}"
            )
            assert MISSING_WALK_FORWARD_EVIDENCE in rec.reason_codes
        mock_wf.assert_called_once()
        mock_conf.assert_called_once()


# ===========================================================================
# FAIL_FAST
# ===========================================================================


class TestFailFast:
    """FAIL_FAST: stops after first failure."""

    def test_stops_after_first_failure(
        self, sample_definition: ResearchCampaignDefinition
    ) -> None:
        """FAIL_FAST should mark remaining experiments as SKIPPED_BY_POLICY."""
        # Build a definition with FAIL_FAST
        ff_definition = ResearchCampaignDefinition(
            campaign_id="ff_test",
            campaign_schema_version=sample_definition.campaign_schema_version,
            parameters=sample_definition.parameters,
            max_experiment_count=10,
            execution_policy=CampaignExecutionPolicy.FAIL_FAST,
            stop_after_n_failures=None,
            resume_policy=ResumePolicy.RERUN,
            output_policy=sample_definition.output_policy,
            safety_flags=ResearchCampaignSafetyFlags(),
            reason_codes=(),
            metadata={},
            fingerprint="",
        )
        compiled, reg_set = compile_campaign(ff_definition, compile_only=False)
        manifest = build_campaign_execution_manifest(ff_definition, compiled, reg_set)

        # Mock: first call fails, rest would pass but should be skipped
        mock_wf_report = MagicMock(spec=WalkForwardExperimentReport)
        mock_wf_report.fingerprint = "wf_fp_001"

        call_count = [0]

        def _failing_wf(*args: object, **kwargs: object) -> WalkForwardExperimentReport:
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("First experiment fails")
            return mock_wf_report

        with (
            patch(
                "hunter.research_campaign.runner.run_walk_forward_for_experiment",
                side_effect=_failing_wf,
            ),
        ):
            dossier = run_campaign_sequential(manifest)

        records = dossier.execution_records
        # First: FAILED
        assert records[0].outcome == ExperimentOutcome.FAILED
        # Remaining: SKIPPED_BY_POLICY
        for rec in records[1:]:
            assert rec.outcome == ExperimentOutcome.SKIPPED_BY_POLICY, (
                f"Expected SKIPPED_BY_POLICY, got {rec.outcome}"
            )
        assert dossier.status_summary.skipped_by_policy == len(records) - 1
        assert dossier.status_summary.failed == 1


# ===========================================================================
# STOP_AFTER_N_FAILURES
# ===========================================================================


class TestStopAfterNFailures:
    """STOP_AFTER_N_FAILURES: stops after N failures."""

    def test_stops_after_n_failures(
        self, sample_definition: ResearchCampaignDefinition
    ) -> None:
        """After N failures, remaining experiments get SKIPPED_BY_POLICY."""
        # Need at least 3 experiments to test this properly
        # The sample has 1, so create one with 2 strategies → 2 experiments
        params = sample_definition.parameters
        # Add a second strategy (different name)
        second_strategy = params.strategies[0]
        # Need a truly different strategy to avoid duplicate detection
        from hunter.research_campaign.models import StrategyReference

        second_strat = StrategyReference(
            strategy_name="test_strategy_b",
            strategy_path="/tmp/strategies/test_b",
            fingerprint="strat_fp_002",
        )
        expanded_params = CampaignParameterSet(
            common_config=params.common_config,
            strategies=(params.strategies[0], second_strat),
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
        saf_definition = ResearchCampaignDefinition(
            campaign_id="saf_test",
            campaign_schema_version=sample_definition.campaign_schema_version,
            parameters=expanded_params,
            max_experiment_count=10,
            execution_policy=CampaignExecutionPolicy.STOP_AFTER_N_FAILURES,
            stop_after_n_failures=1,
            resume_policy=ResumePolicy.RERUN,
            output_policy=sample_definition.output_policy,
            safety_flags=ResearchCampaignSafetyFlags(),
            reason_codes=(),
            metadata={},
            fingerprint="",
        )
        compiled, reg_set = compile_campaign(saf_definition, compile_only=False)
        manifest = build_campaign_execution_manifest(saf_definition, compiled, reg_set)

        assert len(compiled.experiments) >= 2, "Need at least 2 experiments"

        call_count = [0]

        def _failing_wf(*args: object, **kwargs: object) -> WalkForwardExperimentReport:
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("First experiment fails")
            return MagicMock(spec=WalkForwardExperimentReport, fingerprint="wf_fp")

        with (
            patch(
                "hunter.research_campaign.runner.run_walk_forward_for_experiment",
                side_effect=_failing_wf,
            ),
        ):
            dossier = run_campaign_sequential(manifest)

        records = dossier.execution_records
        # First experiment: FAILED (stop_after=1, so after 1 failure)
        assert records[0].outcome == ExperimentOutcome.FAILED
        # Remaining: SKIPPED_BY_POLICY
        for rec in records[1:]:
            assert rec.outcome == ExperimentOutcome.SKIPPED_BY_POLICY
        assert dossier.status_summary.skipped_by_policy == len(records) - 1


# ===========================================================================
# Checkpoint writing
# ===========================================================================


class TestCheckpointWriting:
    """Checkpoints are written when a writer is provided."""

    def test_checkpoints_written(
        self, execution_manifest: CampaignExecutionManifest, tmp_path: Path
    ) -> None:
        """Checkpoints should be written for each experiment."""
        mock_writer = MagicMock()
        mock_writer.write_checkpoint = MagicMock()

        mock_wf_report = MagicMock(spec=WalkForwardExperimentReport)
        mock_wf_report.fingerprint = "wf_fp_002"
        mock_conf_report = MagicMock(fingerprint="conf_fp_002")
        mock_entry = MagicMock(fingerprint="entry_fp_002")
        mock_snapshot = MagicMock(fingerprint="snap_fp_002")

        with (
            patch(
                "hunter.research_campaign.runner.run_walk_forward_for_experiment",
                return_value=mock_wf_report,
            ),
            patch(
                "hunter.research_campaign.runner.run_confidence_for_experiment",
                return_value=mock_conf_report,
            ),
            patch(
                "hunter.research_campaign.runner.ingest_experiment_evidence",
                return_value=(mock_entry, mock_snapshot),
            ),
        ):
            dossier = run_campaign_sequential(
                execution_manifest,
                writer=mock_writer,
                run_id="test_run",
            )

        # One checkpoint per experiment
        num_experiments = len(execution_manifest.compiled_campaign.experiments)
        assert mock_writer.write_checkpoint.call_count == num_experiments


# ===========================================================================
# Resume — reusing evidence
# ===========================================================================


class TestResumeReusesEvidence:
    """Resume correctly reuses evidence when all fingerprints match."""

    def test_resume_reuses_completed_evidence(
        self,
        sample_definition: ResearchCampaignDefinition,
        compiled_and_registered: tuple[CompiledCampaign, CampaignRegistrationSet],
    ) -> None:
        """When prior evidence matches exactly, records are COMPLETED via reuse."""
        compiled, reg_set = compiled_and_registered
        manifest = build_campaign_execution_manifest(sample_definition, compiled, reg_set)

        # Build a resume manifest with matching prior evidence
        from hunter.research_campaign.fingerprint import (
            campaign_resume_manifest_fingerprint,
        )

        compiled_exp = compiled.experiments[0]
        prior = PriorExperimentEvidence(
            experiment_id=compiled_exp.experiment_id,
            experiment_fingerprint=compiled_exp.fingerprint,
            registration_fingerprint=compiled_exp.registration_fingerprint,
            strategy_reference_fingerprint=compiled_exp.strategy.fingerprint,
            historical_data_reference_fingerprint=compiled_exp.historical_data.fingerprint,
            universe_plan_reference_fingerprint=compiled_exp.universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=compiled_exp.walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=compiled_exp.confidence_config.fingerprint,
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            ledger_snapshot_fingerprint="ls_fp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=ExperimentOutcome.COMPLETED,
            evidence=None,
        )
        from hunter.research_campaign.resume import build_resume_manifest

        resume_manifest = build_resume_manifest(
            sample_definition,
            compiled,
            (),
            ResumePolicy.REUSE,
        )
        # Manually add prior evidence and update fingerprint
        resume_manifest = CampaignResumeManifest(
            campaign_fingerprint=resume_manifest.campaign_fingerprint,
            prior_evidence=(prior,),
            resume_policy=ResumePolicy.REUSE,
            fingerprint="",
            reason_codes=(),
        )
        fp = campaign_resume_manifest_fingerprint(resume_manifest)
        object.__setattr__(resume_manifest, "fingerprint", fp)

        # Run — should reuse evidence without calling integration functions
        with (
            patch(
                "hunter.research_campaign.runner.run_walk_forward_for_experiment",
            ) as mock_wf,
            patch(
                "hunter.research_campaign.runner.run_confidence_for_experiment",
            ) as mock_conf,
            patch(
                "hunter.research_campaign.runner.ingest_experiment_evidence",
            ) as mock_ingest,
        ):
            dossier = run_campaign_sequential(
                manifest,
                resume_manifest=resume_manifest,
            )

        # Should have COMPLETED records
        for rec in dossier.execution_records:
            assert rec.outcome == ExperimentOutcome.COMPLETED, (
                f"Expected COMPLETED via reuse, got {rec.outcome}"
            )

        # Integration functions should NOT have been called (evidence reused)
        mock_wf.assert_not_called()
        mock_conf.assert_not_called()
        mock_ingest.assert_not_called()

    def test_resume_does_not_accept_wrong_fingerprint(
        self,
        sample_definition: ResearchCampaignDefinition,
        compiled_and_registered: tuple[CompiledCampaign, CampaignRegistrationSet],
    ) -> None:
        """When fingerprints don't match, the experiment is rerun."""
        compiled, reg_set = compiled_and_registered
        manifest = build_campaign_execution_manifest(sample_definition, compiled, reg_set)

        from hunter.research_campaign.fingerprint import (
            campaign_resume_manifest_fingerprint,
        )

        # Build a resume manifest with STALE prior (wrong experiment fingerprint)
        prior = PriorExperimentEvidence(
            experiment_id=compiled.experiments[0].experiment_id,
            experiment_fingerprint="stale_exp_fp",
            registration_fingerprint=compiled.experiments[0].registration_fingerprint,
            strategy_reference_fingerprint=compiled.experiments[0].strategy.fingerprint,
            historical_data_reference_fingerprint=compiled.experiments[0].historical_data.fingerprint,
            universe_plan_reference_fingerprint=compiled.experiments[0].universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=compiled.experiments[0].walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=compiled.experiments[0].confidence_config.fingerprint,
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            ledger_snapshot_fingerprint="ls_fp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=ExperimentOutcome.COMPLETED,
            evidence=None,
        )
        resume_manifest = CampaignResumeManifest(
            campaign_fingerprint="dummy_fp",
            prior_evidence=(prior,),
            resume_policy=ResumePolicy.REUSE,
            fingerprint="",
            reason_codes=(),
        )
        fp = campaign_resume_manifest_fingerprint(resume_manifest)
        object.__setattr__(resume_manifest, "fingerprint", fp)

        mock_wf_report = MagicMock(spec=WalkForwardExperimentReport)
        mock_wf_report.fingerprint = "wf_fp"
        mock_conf_report = MagicMock(fingerprint="conf_fp")
        mock_entry = MagicMock(fingerprint="entry_fp")
        mock_snapshot = MagicMock(fingerprint="snap_fp")

        # Should still run integration since stale doesn't match
        with (
            patch(
                "hunter.research_campaign.runner.run_walk_forward_for_experiment",
                return_value=mock_wf_report,
            ) as mock_wf,
            patch(
                "hunter.research_campaign.runner.run_confidence_for_experiment",
                return_value=mock_conf_report,
            ) as mock_conf,
            patch(
                "hunter.research_campaign.runner.ingest_experiment_evidence",
                return_value=(mock_entry, mock_snapshot),
            ) as mock_ingest,
        ):
            dossier = run_campaign_sequential(
                manifest,
                resume_manifest=resume_manifest,
            )

        # Should have COMPLETED records (rerun fresh)
        for rec in dossier.execution_records:
            assert rec.outcome == ExperimentOutcome.COMPLETED

        # Integration functions SHOULD have been called (stale → rerun)
        mock_wf.assert_called()
        mock_conf.assert_called()
        mock_ingest.assert_called()

    def test_rerun_policy_ignores_matching_prior_evidence(
        self,
        sample_definition: ResearchCampaignDefinition,
        compiled_and_registered: tuple[CompiledCampaign, CampaignRegistrationSet],
    ) -> None:
        """RERUN policy must ignore matching prior evidence and execute fresh."""
        compiled, reg_set = compiled_and_registered
        manifest = build_campaign_execution_manifest(sample_definition, compiled, reg_set)

        compiled_exp = compiled.experiments[0]
        prior = PriorExperimentEvidence(
            experiment_id=compiled_exp.experiment_id,
            experiment_fingerprint=compiled_exp.fingerprint,
            registration_fingerprint=compiled_exp.registration_fingerprint,
            strategy_reference_fingerprint=compiled_exp.strategy.fingerprint,
            historical_data_reference_fingerprint=compiled_exp.historical_data.fingerprint,
            universe_plan_reference_fingerprint=compiled_exp.universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=compiled_exp.walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=compiled_exp.confidence_config.fingerprint,
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            ledger_snapshot_fingerprint="ls_fp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=ExperimentOutcome.COMPLETED,
            evidence=None,
        )
        resume_manifest = CampaignResumeManifest(
            campaign_fingerprint=compiled.campaign.fingerprint,
            prior_evidence=(prior,),
            resume_policy=ResumePolicy.RERUN,
            fingerprint="",
            reason_codes=(),
        )
        from hunter.research_campaign.fingerprint import (
            campaign_resume_manifest_fingerprint,
        )
        fp = campaign_resume_manifest_fingerprint(resume_manifest)
        object.__setattr__(resume_manifest, "fingerprint", fp)

        mock_wf_report = MagicMock(spec=WalkForwardExperimentReport)
        mock_wf_report.fingerprint = "wf_fp"
        mock_conf_report = MagicMock(fingerprint="conf_fp")
        mock_entry = MagicMock(fingerprint="entry_fp")
        mock_snapshot = MagicMock(fingerprint="snap_fp")

        with (
            patch(
                "hunter.research_campaign.runner.run_walk_forward_for_experiment",
                return_value=mock_wf_report,
            ) as mock_wf,
            patch(
                "hunter.research_campaign.runner.run_confidence_for_experiment",
                return_value=mock_conf_report,
            ) as mock_conf,
            patch(
                "hunter.research_campaign.runner.ingest_experiment_evidence",
                return_value=(mock_entry, mock_snapshot),
            ) as mock_ingest,
        ):
            dossier = run_campaign_sequential(
                manifest,
                resume_manifest=resume_manifest,
            )

        for rec in dossier.execution_records:
            assert rec.outcome == ExperimentOutcome.COMPLETED
        mock_wf.assert_called()
        mock_conf.assert_called()
        mock_ingest.assert_called()

    def test_block_policy_blocks_without_matching_evidence(
        self,
        sample_definition: ResearchCampaignDefinition,
        compiled_and_registered: tuple[CompiledCampaign, CampaignRegistrationSet],
    ) -> None:
        """BLOCK policy without matching prior evidence must fail closed."""
        compiled, reg_set = compiled_and_registered
        manifest = build_campaign_execution_manifest(sample_definition, compiled, reg_set)

        resume_manifest = CampaignResumeManifest(
            campaign_fingerprint=compiled.campaign.fingerprint,
            prior_evidence=(),
            resume_policy=ResumePolicy.BLOCK,
            fingerprint="",
            reason_codes=(),
        )
        from hunter.research_campaign.fingerprint import (
            campaign_resume_manifest_fingerprint,
        )
        fp = campaign_resume_manifest_fingerprint(resume_manifest)
        object.__setattr__(resume_manifest, "fingerprint", fp)

        with (
            patch(
                "hunter.research_campaign.runner.run_walk_forward_for_experiment",
            ) as mock_wf,
            patch(
                "hunter.research_campaign.runner.run_confidence_for_experiment",
            ) as mock_conf,
            patch(
                "hunter.research_campaign.runner.ingest_experiment_evidence",
            ) as mock_ingest,
        ):
            dossier = run_campaign_sequential(
                manifest,
                resume_manifest=resume_manifest,
            )

        rec = dossier.execution_records[0]
        assert rec.outcome == ExperimentOutcome.STALE_RESUME_EVIDENCE
        assert "RESUME_BLOCK_MISSING_EVIDENCE" in rec.reason_codes
        mock_wf.assert_not_called()
        mock_conf.assert_not_called()
        mock_ingest.assert_not_called()

    def test_block_policy_reuses_matching_evidence(
        self,
        sample_definition: ResearchCampaignDefinition,
        compiled_and_registered: tuple[CompiledCampaign, CampaignRegistrationSet],
    ) -> None:
        """BLOCK policy with matching prior evidence must reuse it."""
        compiled, reg_set = compiled_and_registered
        manifest = build_campaign_execution_manifest(sample_definition, compiled, reg_set)

        compiled_exp = compiled.experiments[0]
        prior = PriorExperimentEvidence(
            experiment_id=compiled_exp.experiment_id,
            experiment_fingerprint=compiled_exp.fingerprint,
            registration_fingerprint=compiled_exp.registration_fingerprint,
            strategy_reference_fingerprint=compiled_exp.strategy.fingerprint,
            historical_data_reference_fingerprint=compiled_exp.historical_data.fingerprint,
            universe_plan_reference_fingerprint=compiled_exp.universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=compiled_exp.walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=compiled_exp.confidence_config.fingerprint,
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            ledger_snapshot_fingerprint="ls_fp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=ExperimentOutcome.COMPLETED,
            evidence=None,
        )
        resume_manifest = CampaignResumeManifest(
            campaign_fingerprint=compiled.campaign.fingerprint,
            prior_evidence=(prior,),
            resume_policy=ResumePolicy.BLOCK,
            fingerprint="",
            reason_codes=(),
        )
        from hunter.research_campaign.fingerprint import (
            campaign_resume_manifest_fingerprint,
        )
        fp = campaign_resume_manifest_fingerprint(resume_manifest)
        object.__setattr__(resume_manifest, "fingerprint", fp)

        with (
            patch(
                "hunter.research_campaign.runner.run_walk_forward_for_experiment",
            ) as mock_wf,
            patch(
                "hunter.research_campaign.runner.run_confidence_for_experiment",
            ) as mock_conf,
            patch(
                "hunter.research_campaign.runner.ingest_experiment_evidence",
            ) as mock_ingest,
        ):
            dossier = run_campaign_sequential(
                manifest,
                resume_manifest=resume_manifest,
            )

        for rec in dossier.execution_records:
            assert rec.outcome == ExperimentOutcome.COMPLETED
        mock_wf.assert_not_called()
        mock_conf.assert_not_called()
        mock_ingest.assert_not_called()


# ===========================================================================
# BLOCK policy with stale evidence
# ===========================================================================


class TestBlockPolicyStale:
    """BLOCK policy should handle stale evidence correctly."""

    def test_block_with_stale_evidence(
        self, sample_definition: ResearchCampaignDefinition
    ) -> None:
        """BLOCK policy with stale fingerprint should fail closed."""
        compiled, reg_set = compile_campaign(sample_definition, compile_only=False)
        manifest = build_campaign_execution_manifest(sample_definition, compiled, reg_set)

        prior = PriorExperimentEvidence(
            experiment_id=compiled.experiments[0].experiment_id,
            experiment_fingerprint="stale_exp_fp",
            registration_fingerprint=compiled.experiments[0].registration_fingerprint,
            strategy_reference_fingerprint=compiled.experiments[0].strategy.fingerprint,
            historical_data_reference_fingerprint=compiled.experiments[0].historical_data.fingerprint,
            universe_plan_reference_fingerprint=compiled.experiments[0].universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=compiled.experiments[0].walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=compiled.experiments[0].confidence_config.fingerprint,
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            ledger_snapshot_fingerprint="ls_fp",
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=ExperimentOutcome.COMPLETED,
            evidence=None,
        )
        resume_manifest = CampaignResumeManifest(
            campaign_fingerprint=compiled.campaign.fingerprint,
            prior_evidence=(prior,),
            resume_policy=ResumePolicy.BLOCK,
            fingerprint="",
            reason_codes=(),
        )
        from hunter.research_campaign.fingerprint import (
            campaign_resume_manifest_fingerprint,
        )
        fp = campaign_resume_manifest_fingerprint(resume_manifest)
        object.__setattr__(resume_manifest, "fingerprint", fp)

        with (
            patch(
                "hunter.research_campaign.runner.run_walk_forward_for_experiment",
            ) as mock_wf,
            patch(
                "hunter.research_campaign.runner.run_confidence_for_experiment",
            ) as mock_conf,
            patch(
                "hunter.research_campaign.runner.ingest_experiment_evidence",
            ) as mock_ingest,
        ):
            dossier = run_campaign_sequential(manifest, resume_manifest=resume_manifest)

        rec = dossier.execution_records[0]
        assert rec.outcome == ExperimentOutcome.STALE_RESUME_EVIDENCE
        assert "RESUME_BLOCK_MISSING_EVIDENCE" in rec.reason_codes
        mock_wf.assert_not_called()
        mock_conf.assert_not_called()
        mock_ingest.assert_not_called()
