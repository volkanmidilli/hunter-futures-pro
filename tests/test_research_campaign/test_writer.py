"""Tests for the research campaign writer (MVP-69/MVP-70 / SPEC-070)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hunter.research_campaign.errors import ResearchCampaignWriterError
from hunter.research_campaign.models import (
    CampaignArtifactManifest,
    CampaignCheckpoint,
    CampaignDossier,
    CampaignEvidenceSummary,
    CampaignExecutionManifest,
    CampaignOutputPolicy,
    CampaignRegistrationSet,
    CampaignResumeManifest,
    CampaignStatus,
    CampaignStatusSummary,
    CompiledCampaign,
    ExperimentEvidence,
    ExperimentExecutionRecord,
    ExperimentOutcome,
    ResearchCampaignSafetyFlags,
)
from hunter.research_campaign.writer import (
    CampaignWriter,
    _redact_text,
    _write_json_atomic,
)


@pytest.fixture
def writer(tmp_path: Path) -> CampaignWriter:
    """Writer pointing to a safe temporary directory."""
    return CampaignWriter(output_dir=tmp_path)


class TestValidateOutputDir:
    """Output directory validation must reject data/ and reports/."""

    def test_rejects_data_dir(self, tmp_path: Path) -> None:
        with pytest.raises(ResearchCampaignWriterError) as exc_info:
            CampaignWriter(output_dir=tmp_path / "data" / "campaign")
        assert "data/" in str(exc_info.value)

    def test_rejects_reports_dir(self, tmp_path: Path) -> None:
        with pytest.raises(ResearchCampaignWriterError) as exc_info:
            CampaignWriter(output_dir=tmp_path / "reports" / "campaign")
        assert "reports/" in str(exc_info.value)

    def test_rejects_nested_data_dir(self, tmp_path: Path) -> None:
        with pytest.raises(ResearchCampaignWriterError) as exc_info:
            CampaignWriter(output_dir=tmp_path / "some" / "data" / "campaign")
        assert "data/" in str(exc_info.value)

    def test_accepts_valid_dir(self, tmp_path: Path) -> None:
        writer = CampaignWriter(output_dir=tmp_path / "campaign_output")
        assert writer.output_dir.exists()


class TestAtomicWrite:
    """Atomic JSON writes must be deterministic, overwrite-controlled, and clean."""

    def test_write_json_deterministic_sorted_keys(self, tmp_path: Path) -> None:
        path = tmp_path / "test.json"
        _write_json_atomic(path, {"z": 1, "a": 2, "m": 3}, overwrite=False)
        text = path.read_text(encoding="utf-8")
        # Keys should be sorted alphabetically
        assert text.index('"a"') < text.index('"m"') < text.index('"z"')

    def test_silent_overwrite_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "test.json"
        _write_json_atomic(path, {"a": 1}, overwrite=False)
        with pytest.raises(ResearchCampaignWriterError):
            _write_json_atomic(path, {"a": 2}, overwrite=False)

    def test_overwrite_allowed(self, tmp_path: Path) -> None:
        path = tmp_path / "test.json"
        _write_json_atomic(path, {"a": 1}, overwrite=False)
        _write_json_atomic(path, {"a": 2}, overwrite=True)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["a"] == 2

    def test_cleanup_tmp_on_failure(self, tmp_path: Path) -> None:
        path = tmp_path / "readonly.json"
        path.write_text("existing")
        # Make the directory read-only by removing write permission for the owner.
        tmp_path.chmod(0o555)
        try:
            with pytest.raises(ResearchCampaignWriterError):
                _write_json_atomic(path, {"a": 1}, overwrite=False)
        finally:
            tmp_path.chmod(0o755)
        # tmp file should be cleaned up
        assert not (tmp_path / "readonly.tmp").exists()


class TestRedaction:
    """Path and secret redaction."""

    def test_redacts_absolute_paths(self) -> None:
        text = "Path /home/user/secrets/file.txt is sensitive"
        redacted = _redact_text(text)
        assert "/home/user/secrets/file.txt" not in redacted

    def test_redacts_api_key_like_strings(self) -> None:
        text = "api_key=sk-abc123xyz token: bearer-secret-123 password=mypass"
        redacted = _redact_text(text)
        assert "sk-abc123xyz" not in redacted
        assert "bearer-secret-123" not in redacted
        assert "mypass" not in redacted

    def test_does_not_redact_innocent_strings(self) -> None:
        text = "research_only true"
        assert _redact_text(text) == text


class TestCampaignWriterArtifacts:
    """All artifact write methods should return existing paths."""

    def test_write_definition(self, writer: CampaignWriter, sample_definition) -> None:
        path = writer.write_definition(sample_definition)
        assert path.exists()
        assert path.name == "research_campaign_definition.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["campaign_id"] == sample_definition.campaign_id

    def test_write_compiled_matrix(self, writer: CampaignWriter, sample_compiled_campaign: CompiledCampaign) -> None:
        path = writer.write_compiled_matrix(sample_compiled_campaign)
        assert path.exists()
        assert path.name == "compiled_experiment_matrix.json"

    def test_write_campaign_registrations(
        self,
        writer: CampaignWriter,
        sample_compiled_campaign: CompiledCampaign,
    ) -> None:
        # Build a minimal registration set directly
        registration_set = CampaignRegistrationSet(
            campaign=sample_compiled_campaign,
            registrations=(),
            registration_by_experiment_id={},
            fingerprint="reg_set_fp",
        )
        path = writer.write_campaign_registrations(registration_set)
        assert path.exists()
        assert path.name == "campaign_registrations.json"

    def test_write_execution_manifest(
        self,
        writer: CampaignWriter,
        sample_definition,
        sample_compiled_campaign: CompiledCampaign,
    ) -> None:
        registration_set = CampaignRegistrationSet(
            campaign=sample_compiled_campaign,
            registrations=(),
            registration_by_experiment_id={},
            fingerprint="reg_set_fp",
        )
        manifest = CampaignExecutionManifest(
            campaign_definition=sample_definition,
            compiled_campaign=sample_compiled_campaign,
            registration_set=registration_set,
        )
        path = writer.write_execution_manifest(manifest)
        assert path.exists()
        assert path.name == "campaign_execution_manifest.json"

    def test_write_execution_records(self, writer: CampaignWriter) -> None:
        path = writer.write_execution_records(records=())
        assert path.exists()
        assert path.name == "campaign_execution_records.json"

    def test_write_resume_manifest(self, writer: CampaignWriter) -> None:
        resume = CampaignResumeManifest(
            campaign_fingerprint="camp_fp",
            prior_evidence=(),
        )
        path = writer.write_resume_manifest(resume)
        assert path.exists()
        assert path.name == "campaign_resume_manifest.json"

    def test_write_evidence_summary(self, writer: CampaignWriter) -> None:
        summary = CampaignEvidenceSummary(
            walk_forward_attempted=1,
            walk_forward_completed=1,
            confidence_attempted=1,
            confidence_completed=1,
            ledger_entries=1,
            ledger_snapshots=1,
        )
        path = writer.write_evidence_summary(summary)
        assert path.exists()

    def test_write_dossier(self, writer: CampaignWriter, sample_compiled_campaign: CompiledCampaign) -> None:
        summary = CampaignStatusSummary(total=1, completed=1, failed=0, blocked=0, timed_out=0, unsupported=0, insufficient_evidence=0, withdrawn=0, skipped_by_policy=0, stale_resume_evidence=0)
        evidence = CampaignEvidenceSummary(
            walk_forward_attempted=1,
            walk_forward_completed=1,
            confidence_attempted=1,
            confidence_completed=1,
            ledger_entries=1,
            ledger_snapshots=1,
        )
        dossier = CampaignDossier(
            campaign_id=sample_compiled_campaign.campaign.campaign_id,
            campaign_fingerprint="camp_fp",
            compiled_campaign_fingerprint=sample_compiled_campaign.fingerprint,
            status_summary=summary,
            evidence_summary=evidence,
            execution_records=(),
            safety_flags=ResearchCampaignSafetyFlags(),
        )
        path = writer.write_dossier(dossier)
        assert path.exists()
        assert path.name == "campaign_dossier.json"

    def test_write_dossier_markdown(self, writer: CampaignWriter, sample_compiled_campaign: CompiledCampaign) -> None:
        summary = CampaignStatusSummary(total=1, completed=1, failed=0, blocked=0, timed_out=0, unsupported=0, insufficient_evidence=0, withdrawn=0, skipped_by_policy=0, stale_resume_evidence=0)
        evidence = CampaignEvidenceSummary(
            walk_forward_attempted=1,
            walk_forward_completed=1,
            confidence_attempted=1,
            confidence_completed=1,
            ledger_entries=1,
            ledger_snapshots=1,
        )
        dossier = CampaignDossier(
            campaign_id=sample_compiled_campaign.campaign.campaign_id,
            campaign_fingerprint="camp_fp",
            compiled_campaign_fingerprint=sample_compiled_campaign.fingerprint,
            status_summary=summary,
            evidence_summary=evidence,
            execution_records=(),
            safety_flags=ResearchCampaignSafetyFlags(),
        )
        path = writer.write_dossier_markdown(dossier)
        assert path.exists()
        assert path.name == "campaign_dossier.md"
        md = path.read_text(encoding="utf-8")
        assert "research-only" in md.lower()

    def test_write_artifact_manifest(self, writer: CampaignWriter) -> None:
        path = writer.write_artifact_manifest(
            artifact_paths=(),
            dossier_fingerprint="doss_fp",
            campaign_id="camp",
        )
        assert path.exists()

    def test_write_all_campaign_artifacts(self, writer: CampaignWriter, sample_compiled_campaign: CompiledCampaign) -> None:
        registration_set = CampaignRegistrationSet(
            campaign=sample_compiled_campaign,
            registrations=(),
            registration_by_experiment_id={},
            fingerprint="reg_set_fp",
        )
        manifest = CampaignExecutionManifest(
            campaign_definition=sample_compiled_campaign.campaign,
            compiled_campaign=sample_compiled_campaign,
            registration_set=registration_set,
        )
        summary = CampaignStatusSummary(total=1, completed=1, failed=0, blocked=0, timed_out=0, unsupported=0, insufficient_evidence=0, withdrawn=0, skipped_by_policy=0, stale_resume_evidence=0)
        evidence = CampaignEvidenceSummary(
            walk_forward_attempted=1,
            walk_forward_completed=1,
            confidence_attempted=1,
            confidence_completed=1,
            ledger_entries=1,
            ledger_snapshots=1,
        )
        dossier = CampaignDossier(
            campaign_id=sample_compiled_campaign.campaign.campaign_id,
            campaign_fingerprint="camp_fp",
            compiled_campaign_fingerprint=sample_compiled_campaign.fingerprint,
            status_summary=summary,
            evidence_summary=evidence,
            execution_records=(),
            safety_flags=ResearchCampaignSafetyFlags(),
        )
        paths = writer.write_all_campaign_artifacts(
            definition=sample_compiled_campaign.campaign,
            compiled_campaign=sample_compiled_campaign,
            registration_set=registration_set,
            execution_manifest=manifest,
            execution_records=(),
            dossier=dossier,
            resume_manifest=CampaignResumeManifest(campaign_fingerprint="camp_fp", prior_evidence=()),
            evidence_summary=evidence,
        )
        assert len(paths) >= 9
        for p in paths:
            assert p.exists()


class TestCheckpointWriter:
    """Checkpoint writing after each experiment attempt."""

    def test_write_checkpoint(self, writer: CampaignWriter) -> None:
        from datetime import datetime, timezone
        record = ExperimentExecutionRecord(
            experiment_id="exp_1",
            campaign_id="camp_1",
            experiment_fingerprint="exp_fp",
            registration_fingerprint="reg_fp",
            outcome=ExperimentOutcome.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            evidence=ExperimentEvidence(),
            reason_codes=(),
        )
        path = writer.write_checkpoint(
            checkpoint_id="chk_1",
            campaign_id="camp_1",
            checkpoint_index=0,
            experiment_records=(record,),
            status=CampaignStatus.RUNNING,
        )
        assert path.exists()


class TestOutputPolicy:
    """Writer respects overwrite flag."""

    def test_writer_stores_overwrite_flag(self, tmp_path: Path) -> None:
        writer = CampaignWriter(output_dir=str(tmp_path / "out"), overwrite=True)
        assert writer.overwrite is True
