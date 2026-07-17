"""Tests for the research campaign engine (MVP-69/MVP-70 / SPEC-070)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hunter.research_campaign.engine import (
    build_campaign_execution_manifest,
    build_dossier,
    build_evidence_summary,
    build_status_summary,
    compile_campaign_definition,
    run_campaign,
)
from hunter.research_campaign.models import (
    CampaignCheckpoint,
    CampaignDossier,
    CampaignEvidenceSummary,
    CampaignExecutionManifest,
    CampaignExecutionPolicy,
    CampaignOutputPolicy,
    CampaignRegistrationSet,
    CampaignResumeManifest,
    CampaignStatus,
    CampaignStatusSummary,
    CompiledCampaign,
    CompiledExperiment,
    ExperimentEvidence,
    ExperimentExecutionRecord,
    ExperimentOutcome,
    ResearchCampaignSafetyFlags,
    ResumePolicy,
)
from hunter.research_campaign.writer import CampaignWriter


class TestCompileCampaignDefinition:
    """Campaign definition compilation end-to-end."""

    def test_returns_compiled_campaign(self, sample_definition) -> None:
        compiled = compile_campaign_definition(sample_definition)
        assert isinstance(compiled, CompiledCampaign)
        assert compiled.experiment_count == 1
        assert compiled.experiments[0].experiment_id
        assert compiled.experiments[0].fingerprint

    def test_multiple_strategies_and_timeframes(self, sample_definition) -> None:
        from hunter.research_campaign.models import CampaignParameterSet
        params = CampaignParameterSet(
            common_config=sample_definition.parameters.common_config,
            strategies=(
                sample_definition.parameters.strategies[0],
                sample_definition.parameters.strategies[0],
            ),  # duplicate would be filtered; but if fingerprints differ, this is different
            timeframes=("1h", "4h"),
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
        # Make second strategy distinct by changing fingerprint
        s2 = sample_definition.parameters.strategies[0]
        from hunter.research_campaign.models import StrategyReference
        s2_unique = StrategyReference(
            strategy_name=s2.strategy_name,
            strategy_path=s2.strategy_path,
            fingerprint="strat_fp_002",
        )
        params = CampaignParameterSet(
            common_config=sample_definition.parameters.common_config,
            strategies=(sample_definition.parameters.strategies[0], s2_unique),
            timeframes=("1h", "4h"),
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
        definition = replace(
            sample_definition,
            parameters=params,
            max_experiment_count=10,
        )
        compiled = compile_campaign_definition(definition)
        assert compiled.experiment_count == 4


class TestBuildExecutionManifest:
    """Execution manifest construction."""

    def test_builds_manifest(self, sample_definition) -> None:
        compiled = compile_campaign_definition(sample_definition)
        from hunter.research_campaign.registration import create_campaign_registration_set
        registration_set = create_campaign_registration_set(compiled)
        manifest = build_campaign_execution_manifest(
            sample_definition, compiled, registration_set
        )
        assert isinstance(manifest, CampaignExecutionManifest)
        assert manifest.fingerprint
        assert manifest.registration_set.fingerprint


class TestBuildStatusSummary:
    """Status summary counts outcomes."""

    def test_counts_outcomes(self, sample_compiled_experiment: CompiledExperiment) -> None:
        record = ExperimentExecutionRecord(
            experiment_id=sample_compiled_experiment.experiment_id,
            campaign_id=sample_compiled_experiment.campaign_id,
            experiment_fingerprint=sample_compiled_experiment.fingerprint,
            registration_fingerprint=sample_compiled_experiment.registration_fingerprint,
            outcome=ExperimentOutcome.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            evidence=ExperimentEvidence(),
            reason_codes=(),
        )
        summary = build_status_summary((record,))
        assert summary.total == 1
        assert summary.completed == 1
        assert summary.failed == 0


class TestBuildEvidenceSummary:
    """Evidence summary counts MVP-66/67/68 coverage."""

    def test_counts_evidence(self, sample_compiled_experiment: CompiledExperiment) -> None:
        evidence = ExperimentEvidence(
            walk_forward_report=sample_compiled_experiment.walk_forward_plan,  # non-None proxy
            confidence_report=None,  # would need a real ExperimentConfidenceReport
            ledger_entry=True,  # non-None proxy
            ledger_snapshot=True,  # non-None proxy
            walk_forward_report_fingerprint="wf_fp",
            confidence_report_fingerprint="cf_fp",
            ledger_entry_fingerprint="le_fp",
            ledger_snapshot_fingerprint="ls_fp",
        )
        record = ExperimentExecutionRecord(
            experiment_id=sample_compiled_experiment.experiment_id,
            campaign_id=sample_compiled_experiment.campaign_id,
            experiment_fingerprint=sample_compiled_experiment.fingerprint,
            registration_fingerprint=sample_compiled_experiment.registration_fingerprint,
            outcome=ExperimentOutcome.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            evidence=evidence,
            reason_codes=(),
        )
        summary = build_evidence_summary((record,))
        assert summary.walk_forward_attempted == 1
        assert summary.walk_forward_completed == 1
        assert summary.confidence_attempted == 0  # None object
        assert summary.confidence_completed == 0
        assert summary.ledger_entries == 1
        assert summary.ledger_snapshots == 1


class TestBuildDossier:
    """Dossier construction."""

    def test_builds_dossier(self, sample_compiled_campaign: CompiledCampaign) -> None:
        status = CampaignStatusSummary(total=1, completed=1, failed=0, blocked=0, timed_out=0, unsupported=0, insufficient_evidence=0, withdrawn=0, skipped_by_policy=0, stale_resume_evidence=0)
        evidence = CampaignEvidenceSummary(
            walk_forward_attempted=1,
            walk_forward_completed=1,
            confidence_attempted=1,
            confidence_completed=1,
            ledger_entries=1,
            ledger_snapshots=1,
        )
        dossier = build_dossier(
            records=(),
            status=CampaignStatus.COMPLETED,
            campaign_definition=sample_compiled_campaign.campaign,
            compiled_campaign=sample_compiled_campaign,
        )
        assert isinstance(dossier, CampaignDossier)
        assert dossier.fingerprint
        assert dossier.campaign_id == sample_compiled_campaign.campaign.campaign_id


class TestRunCampaignCompileOnly:
    """run_campaign with compile_only=True."""

    def test_compile_only_writes_definition_and_matrix(self, sample_definition, tmp_path: Path) -> None:
        output_dir = tmp_path / "compile_only_out"
        dossier = run_campaign(
            sample_definition,
            output_dir=str(output_dir),
            compile_only=True,
        )
        assert isinstance(dossier, CampaignDossier)
        assert (output_dir / "research_campaign_definition.json").exists()
        assert (output_dir / "compiled_experiment_matrix.json").exists()
        # Execution artifacts should not be written in compile-only mode
        assert not (output_dir / "campaign_execution_records.json").exists()


class TestRunCampaignFull:
    """run_campaign full execution (with mocked runner internals)."""

    def test_full_run_with_mocked_runner(
        self,
        sample_definition,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        output_dir = tmp_path / "full_run_out"

        # Mock the runner to avoid MVP-66 subprocess
        def mock_runner(manifest, resume_manifest=None, *, writer=None, run_id=None):
            record = ExperimentExecutionRecord(
                experiment_id=manifest.compiled_campaign.experiments[0].experiment_id,
                campaign_id=manifest.campaign_definition.campaign_id,
                experiment_fingerprint=manifest.compiled_campaign.experiments[0].fingerprint,
                registration_fingerprint=manifest.registration_set.registrations[0].fingerprint,
                outcome=ExperimentOutcome.COMPLETED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                evidence=ExperimentEvidence(
                    walk_forward_report_fingerprint="wf_fp",
                    confidence_report_fingerprint="cf_fp",
                    ledger_entry_fingerprint="le_fp",
                    ledger_snapshot_fingerprint="ls_fp",
                ),
                reason_codes=(),
            )
            return build_dossier(
                records=(record,),
                status=CampaignStatus.COMPLETED,
                campaign_definition=manifest.campaign_definition,
                compiled_campaign=manifest.compiled_campaign,
            )

        import hunter.research_campaign.engine as engine_mod
        monkeypatch.setattr(engine_mod, "run_campaign_sequential", mock_runner)

        dossier = run_campaign(
            sample_definition,
            output_dir=str(output_dir),
            compile_only=False,
        )
        assert isinstance(dossier, CampaignDossier)
        assert dossier.status_summary.completed == 1
        assert (output_dir / "campaign_dossier.json").exists()
        assert (output_dir / "campaign_dossier.md").exists()
