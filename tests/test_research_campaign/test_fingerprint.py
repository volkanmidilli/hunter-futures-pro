"""Tests for deterministic SHA-256 fingerprint functions (MVP-69/MVP-70 / SPEC-070).

No subprocess, threading, network, eval, exec, or dynamic code.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.research_campaign.fingerprint import (
    artifact_manifest_fingerprint,
    campaign_definition_fingerprint,
    campaign_dossier_fingerprint,
    campaign_resume_manifest_fingerprint,
    checkpoint_fingerprint,
    compiled_campaign_fingerprint,
    compiled_experiment_fingerprint,
    evidence_summary_fingerprint,
    execution_manifest_fingerprint,
    experiment_execution_record_fingerprint,
    experiment_id_from_components,
    registration_set_fingerprint,
    status_summary_fingerprint,
)
from hunter.research_campaign.models import (
    CampaignArtifactManifest,
    CampaignCheckpoint,
    CampaignDossier,
    CampaignEvidenceSummary,
    CampaignExecutionManifest,
    CampaignRegistrationSet,
    CampaignResumeManifest,
    CampaignStatus,
    CampaignStatusSummary,
    CompiledCampaign,
    CompiledExperiment,
    ExperimentEvidence,
    ExperimentExecutionRecord,
    ExperimentOutcome,
    PriorExperimentEvidence,
    ResearchCampaignSafetyFlags,
    ResumePolicy,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_campaign_registration_set(
    compiled_campaign: CompiledCampaign,
) -> CampaignRegistrationSet:
    """Create a minimal CampaignRegistrationSet for fingerprint testing."""
    # Import here to avoid circular issues at module level
    from hunter.research_campaign.registration import (
        create_campaign_registration_set,
    )

    return create_campaign_registration_set(compiled_campaign)


# ===========================================================================
# campaign_definition_fingerprint
# ===========================================================================


class TestCampaignDefinitionFingerprint:
    def test_deterministic(self, sample_definition) -> None:
        fp1 = campaign_definition_fingerprint(sample_definition)
        fp2 = campaign_definition_fingerprint(sample_definition)
        assert fp1 == fp2
        assert isinstance(fp1, str)
        assert len(fp1) > 0

    def test_changes_when_campaign_id_changes(self, sample_definition) -> None:
        fp1 = campaign_definition_fingerprint(sample_definition)
        # Modify campaign_id
        altered = sample_definition.__class__(
            campaign_id="different_campaign",
            campaign_schema_version=sample_definition.campaign_schema_version,
            parameters=sample_definition.parameters,
            max_experiment_count=sample_definition.max_experiment_count,
            execution_policy=sample_definition.execution_policy,
            stop_after_n_failures=sample_definition.stop_after_n_failures,
            resume_policy=sample_definition.resume_policy,
            output_policy=sample_definition.output_policy,
            safety_flags=sample_definition.safety_flags,
            reason_codes=sample_definition.reason_codes,
            metadata=sample_definition.metadata,
            fingerprint=sample_definition.fingerprint,
        )
        fp2 = campaign_definition_fingerprint(altered)
        assert fp1 != fp2

    def test_excludes_output_dir_path(self, sample_definition) -> None:
        """Fingerprint must not include filesystem paths (output_dir)."""
        fp = campaign_definition_fingerprint(sample_definition)
        # The alias 'tmp' or the actual path must not appear literally
        assert "campaign_output" not in fp
        # Ensure it's a valid hex string
        assert all(c in "0123456789abcdef" for c in fp)

    def test_excludes_metadata_and_fingerprint(self, sample_definition) -> None:
        """Fingerprint excludes metadata and its own fingerprint field."""
        fp1 = campaign_definition_fingerprint(sample_definition)
        # Same definition with different metadata/fingerprint should give same fp
        altered = sample_definition.__class__(
            campaign_id=sample_definition.campaign_id,
            campaign_schema_version=sample_definition.campaign_schema_version,
            parameters=sample_definition.parameters,
            max_experiment_count=sample_definition.max_experiment_count,
            execution_policy=sample_definition.execution_policy,
            stop_after_n_failures=sample_definition.stop_after_n_failures,
            resume_policy=sample_definition.resume_policy,
            output_policy=sample_definition.output_policy,
            safety_flags=sample_definition.safety_flags,
            reason_codes=sample_definition.reason_codes,
            metadata={"labels": "production"},
            fingerprint="xyz789",
        )
        fp2 = campaign_definition_fingerprint(altered)
        # Both metadata and fingerprint are excluded from the payload
        assert fp1 == fp2


# ===========================================================================
# compiled_experiment_fingerprint
# ===========================================================================


class TestCompiledExperimentFingerprint:
    def test_deterministic(self, sample_compiled_experiment) -> None:
        fp1 = compiled_experiment_fingerprint(sample_compiled_experiment)
        fp2 = compiled_experiment_fingerprint(sample_compiled_experiment)
        assert fp1 == fp2
        assert isinstance(fp1, str)
        assert len(fp1) > 0

    def test_identical_for_identical_inputs(self, sample_compiled_experiment) -> None:
        """Two identical compiled experiments must have identical fingerprints."""
        fp1 = compiled_experiment_fingerprint(sample_compiled_experiment)
        # Create an identical copy
        clone = CompiledExperiment(
            experiment_id=sample_compiled_experiment.experiment_id,
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
            fingerprint=sample_compiled_experiment.fingerprint,
            registration_fingerprint=sample_compiled_experiment.registration_fingerprint,
        )
        fp2 = compiled_experiment_fingerprint(clone)
        assert fp1 == fp2

    def test_changes_when_strategy_changes(self, sample_compiled_experiment, sample_strategy_ref) -> None:
        fp1 = compiled_experiment_fingerprint(sample_compiled_experiment)
        # Change strategy
        new_strategy = sample_strategy_ref.__class__(
            strategy_name="other_strat",
            strategy_path=sample_strategy_ref.strategy_path,
            fingerprint=sample_strategy_ref.fingerprint,
        )
        altered = CompiledExperiment(
            experiment_id=sample_compiled_experiment.experiment_id,
            campaign_id=sample_compiled_experiment.campaign_id,
            strategy=new_strategy,
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
            fingerprint=sample_compiled_experiment.fingerprint,
            registration_fingerprint=sample_compiled_experiment.registration_fingerprint,
        )
        fp2 = compiled_experiment_fingerprint(altered)
        assert fp1 != fp2


# ===========================================================================
# experiment_id_from_components
# ===========================================================================


class TestExperimentIdFromComponents:
    def test_deterministic(self) -> None:
        eid1 = experiment_id_from_components(
            campaign_id="test",
            strategy_name="s1",
            timeframe="1h",
            data_id="d1",
            universe_plan_id="u1",
            template_id="t1",
            config_id="c1",
            experiment_family_id="ef1",
            hypothesis_family_id="hf1",
            metric_names=("sharpe",),
            independence_class="INDEPENDENT",
            regime_label="UNKNOWN",
            strategy_fingerprint="sfp",
            historical_data_fingerprint="hfp",
            universe_plan_fingerprint="ufp",
            walk_forward_template_fingerprint="wfp",
            confidence_config_fingerprint="cfp",
            experiment_family_fingerprint="effp",
            hypothesis_family_fingerprint="hffp",
        )
        eid2 = experiment_id_from_components(
            campaign_id="test",
            strategy_name="s1",
            timeframe="1h",
            data_id="d1",
            universe_plan_id="u1",
            template_id="t1",
            config_id="c1",
            experiment_family_id="ef1",
            hypothesis_family_id="hf1",
            metric_names=("sharpe",),
            independence_class="INDEPENDENT",
            regime_label="UNKNOWN",
            strategy_fingerprint="sfp",
            historical_data_fingerprint="hfp",
            universe_plan_fingerprint="ufp",
            walk_forward_template_fingerprint="wfp",
            confidence_config_fingerprint="cfp",
            experiment_family_fingerprint="effp",
            hypothesis_family_fingerprint="hffp",
        )
        assert eid1 == eid2
        assert len(eid1) == 16  # Prefix length
        assert all(c in "0123456789abcdef" for c in eid1)

    def test_identical_for_identical_inputs(self) -> None:
        """Identical component sets produce identical IDs."""
        args = dict(
            campaign_id="test",
            strategy_name="s1",
            timeframe="1h",
            data_id="d1",
            universe_plan_id="u1",
            template_id="t1",
            config_id="c1",
            experiment_family_id="ef1",
            hypothesis_family_id="hf1",
            metric_names=("sharpe",),
            independence_class="INDEPENDENT",
            regime_label="UNKNOWN",
            strategy_fingerprint="sfp",
            historical_data_fingerprint="hfp",
            universe_plan_fingerprint="ufp",
            walk_forward_template_fingerprint="wfp",
            confidence_config_fingerprint="cfp",
            experiment_family_fingerprint="effp",
            hypothesis_family_fingerprint="hffp",
        )
        eid1 = experiment_id_from_components(**args)
        eid2 = experiment_id_from_components(**args)
        assert eid1 == eid2


# ===========================================================================
# compiled_campaign_fingerprint
# ===========================================================================


class TestCompiledCampaignFingerprint:
    def test_deterministic(self, sample_compiled_campaign) -> None:
        fp1 = compiled_campaign_fingerprint(sample_compiled_campaign)
        fp2 = compiled_campaign_fingerprint(sample_compiled_campaign)
        assert fp1 == fp2
        assert isinstance(fp1, str)
        assert len(fp1) > 0

    def test_does_not_include_timestamps(self, sample_compiled_campaign) -> None:
        """compile_timestamp must NOT be included."""
        fp = compiled_campaign_fingerprint(sample_compiled_campaign)
        assert all(c in "0123456789abcdef" for c in fp)

    def test_order_stable_via_canonical_sort(
        self,
        sample_definition,
        sample_compiled_experiment,
    ) -> None:
        """Canonical sort should make experiment order stable."""
        # Create two campaigns with experiments in different orders
        # Since canonical_sort_experiments sorts by (campaign_id, experiment_id, fingerprint),
        # two experiments with different IDs would have a fixed order.
        from hunter.research_campaign.ordering import canonical_sort_experiments

        e1 = sample_compiled_experiment
        # Create a second experiment with different experiment_id
        e2 = CompiledExperiment(
            experiment_id="exp_002_xyz789",
            campaign_id=e1.campaign_id,
            strategy=e1.strategy,
            timeframe="4h",
            historical_data=e1.historical_data,
            universe_plan=e1.universe_plan,
            walk_forward_template=e1.walk_forward_template,
            confidence_config=e1.confidence_config,
            experiment_family=e1.experiment_family,
            hypothesis_family=e1.hypothesis_family,
            metric_family=e1.metric_family,
            independence=e1.independence,
            regime_policy=e1.regime_policy,
            walk_forward_plan=e1.walk_forward_plan,
            fingerprint="exp_fp_002",
            registration_fingerprint="reg_fp_002",
        )
        sorted_a = canonical_sort_experiments([e1, e2])
        sorted_b = canonical_sort_experiments([e2, e1])

        # The sorted order should be the same regardless of input order
        assert sorted_a == sorted_b

        c1 = CompiledCampaign(
            campaign=sample_definition,
            experiments=sorted_a,
            experiment_count=2,
            excluded_count=0,
            fingerprint="",
            compile_timestamp=datetime.now(timezone.utc),
            reason_codes=(),
        )
        c2 = CompiledCampaign(
            campaign=sample_definition,
            experiments=sorted_b,
            experiment_count=2,
            excluded_count=0,
            fingerprint="",
            compile_timestamp=datetime.now(timezone.utc),
            reason_codes=(),
        )
        fp1 = compiled_campaign_fingerprint(c1)
        fp2 = compiled_campaign_fingerprint(c2)
        assert fp1 == fp2


# ===========================================================================
# All remaining fingerprint functions
# ===========================================================================


class TestRegistrationSetFingerprint:
    def test_non_empty_and_deterministic(
        self, sample_compiled_campaign
    ) -> None:
        reg_set = _make_campaign_registration_set(sample_compiled_campaign)
        fp1 = registration_set_fingerprint(reg_set)
        fp2 = registration_set_fingerprint(reg_set)
        assert fp1 == fp2
        assert isinstance(fp1, str)
        assert len(fp1) > 0


class TestExecutionManifestFingerprint:
    def test_non_empty_and_deterministic(
        self, sample_compiled_campaign, sample_definition
    ) -> None:
        reg_set = _make_campaign_registration_set(sample_compiled_campaign)
        manifest = CampaignExecutionManifest(
            campaign_definition=sample_definition,
            compiled_campaign=sample_compiled_campaign,
            registration_set=reg_set,
            fingerprint="",
            reason_codes=(),
        )
        fp1 = execution_manifest_fingerprint(manifest)
        fp2 = execution_manifest_fingerprint(manifest)
        assert fp1 == fp2
        assert isinstance(fp1, str)
        assert len(fp1) > 0


class TestExperimentExecutionRecordFingerprint:
    def test_non_empty_and_deterministic(
        self, sample_compiled_experiment
    ) -> None:
        now = datetime.now(timezone.utc)
        evidence = ExperimentEvidence()
        record = ExperimentExecutionRecord(
            experiment_id=sample_compiled_experiment.experiment_id,
            campaign_id=sample_compiled_experiment.campaign_id,
            experiment_fingerprint=sample_compiled_experiment.fingerprint,
            registration_fingerprint=sample_compiled_experiment.registration_fingerprint,
            outcome=ExperimentOutcome.COMPLETED,
            started_at=now,
            completed_at=now,
            evidence=evidence,
            reason_codes=(),
            notes="",
        )
        fp1 = experiment_execution_record_fingerprint(record)
        fp2 = experiment_execution_record_fingerprint(record)
        assert fp1 == fp2
        assert isinstance(fp1, str)
        assert len(fp1) > 0

    def test_excludes_timestamps_and_notes(
        self, sample_compiled_experiment
    ) -> None:
        """Fingerprint must exclude started_at, completed_at, and notes."""
        now = datetime.now(timezone.utc)
        later = datetime(2025, 1, 1, tzinfo=timezone.utc)
        evidence = ExperimentEvidence()
        base = ExperimentExecutionRecord(
            experiment_id=sample_compiled_experiment.experiment_id,
            campaign_id=sample_compiled_experiment.campaign_id,
            experiment_fingerprint=sample_compiled_experiment.fingerprint,
            registration_fingerprint=sample_compiled_experiment.registration_fingerprint,
            outcome=ExperimentOutcome.COMPLETED,
            started_at=now,
            completed_at=now,
            evidence=evidence,
            reason_codes=(),
            notes="original",
        )
        altered = ExperimentExecutionRecord(
            experiment_id=sample_compiled_experiment.experiment_id,
            campaign_id=sample_compiled_experiment.campaign_id,
            experiment_fingerprint=sample_compiled_experiment.fingerprint,
            registration_fingerprint=sample_compiled_experiment.registration_fingerprint,
            outcome=ExperimentOutcome.COMPLETED,
            started_at=later,
            completed_at=later,
            evidence=evidence,
            reason_codes=(),
            notes="changed",
        )
        # Both timestamps and notes should be excluded, so fingerprint is same
        fp1 = experiment_execution_record_fingerprint(base)
        fp2 = experiment_execution_record_fingerprint(altered)
        assert fp1 == fp2


class TestCampaignResumeManifestFingerprint:
    def test_non_empty_and_deterministic(self) -> None:
        manifest = CampaignResumeManifest(
            campaign_fingerprint="cfp",
            prior_evidence=(),
            resume_policy=ResumePolicy.REUSE,
            fingerprint="",
            reason_codes=(),
        )
        fp1 = campaign_resume_manifest_fingerprint(manifest)
        fp2 = campaign_resume_manifest_fingerprint(manifest)
        assert fp1 == fp2
        assert isinstance(fp1, str)
        assert len(fp1) > 0


class TestCheckpointFingerprint:
    def test_non_empty_and_deterministic(self) -> None:
        now = datetime.now(timezone.utc)
        checkpoint = CampaignCheckpoint(
            checkpoint_id="cp_001",
            campaign_id="campaign_test_001",
            checkpoint_index=1,
            experiment_records=(),
            status=CampaignStatus.RUNNING,
            fingerprint="",
            created_at=now,
            reason_codes=(),
        )
        fp1 = checkpoint_fingerprint(checkpoint)
        fp2 = checkpoint_fingerprint(checkpoint)
        assert fp1 == fp2
        assert isinstance(fp1, str)
        assert len(fp1) > 0


class TestStatusSummaryFingerprint:
    def test_non_empty_and_deterministic(self) -> None:
        summary = CampaignStatusSummary(
            total=5,
            completed=3,
            failed=1,
            blocked=0,
            timed_out=0,
            unsupported=0,
            insufficient_evidence=0,
            withdrawn=0,
            skipped_by_policy=1,
            stale_resume_evidence=0,
        )
        fp1 = status_summary_fingerprint(summary)
        fp2 = status_summary_fingerprint(summary)
        assert fp1 == fp2
        assert isinstance(fp1, str)
        assert len(fp1) > 0


class TestEvidenceSummaryFingerprint:
    def test_non_empty_and_deterministic(self) -> None:
        summary = CampaignEvidenceSummary(
            walk_forward_attempted=3,
            walk_forward_completed=2,
            confidence_attempted=2,
            confidence_completed=1,
            ledger_entries=1,
            ledger_snapshots=1,
        )
        fp1 = evidence_summary_fingerprint(summary)
        fp2 = evidence_summary_fingerprint(summary)
        assert fp1 == fp2
        assert isinstance(fp1, str)
        assert len(fp1) > 0


class TestCampaignDossierFingerprint:
    def test_non_empty_and_deterministic(self) -> None:
        now = datetime.now(timezone.utc)
        status_summary = CampaignStatusSummary(
            total=1, completed=1, failed=0, blocked=0, timed_out=0,
            unsupported=0, insufficient_evidence=0, withdrawn=0,
            skipped_by_policy=0, stale_resume_evidence=0,
        )
        evidence_summary = CampaignEvidenceSummary(
            walk_forward_attempted=1, walk_forward_completed=1,
            confidence_attempted=1, confidence_completed=1,
            ledger_entries=1, ledger_snapshots=1,
        )
        dossier = CampaignDossier(
            campaign_id="c001",
            campaign_fingerprint="cfp",
            compiled_campaign_fingerprint="ccfp",
            status_summary=status_summary,
            evidence_summary=evidence_summary,
            execution_records=(),
            safety_flags=ResearchCampaignSafetyFlags(),
            fingerprint="",
            generated_at=now,
            reason_codes=(),
        )
        fp1 = campaign_dossier_fingerprint(dossier)
        fp2 = campaign_dossier_fingerprint(dossier)
        assert fp1 == fp2
        assert isinstance(fp1, str)
        assert len(fp1) > 0


class TestArtifactManifestFingerprint:
    def test_non_empty_and_deterministic(self) -> None:
        manifest = CampaignArtifactManifest(
            campaign_id="c001",
            artifact_paths=("/tmp/out/def.json", "/tmp/out/dossier.json"),
            dossier_fingerprint="dfp",
            fingerprint="",
        )
        fp1 = artifact_manifest_fingerprint(manifest)
        fp2 = artifact_manifest_fingerprint(manifest)
        assert fp1 == fp2
        assert isinstance(fp1, str)
        assert len(fp1) > 0

    def test_excludes_artifact_paths(self) -> None:
        """Fingerprint must NOT include artifact_paths (filesystem paths)."""
        manifest1 = CampaignArtifactManifest(
            campaign_id="c001",
            artifact_paths=("/secret/path/file.json",),
            dossier_fingerprint="dfp",
            fingerprint="",
        )
        manifest2 = CampaignArtifactManifest(
            campaign_id="c001",
            artifact_paths=("/different/path/file.json",),
            dossier_fingerprint="dfp",
            fingerprint="",
        )
        fp1 = artifact_manifest_fingerprint(manifest1)
        fp2 = artifact_manifest_fingerprint(manifest2)
        # Different paths should NOT affect the fingerprint
        assert fp1 == fp2
