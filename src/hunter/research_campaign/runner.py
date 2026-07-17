"""Sequential campaign runner — iterates compiled experiments, runs MVP-66/67/68, and builds dossier (MVP-70 / SPEC-070).

No subprocess, threading, network, eval, exec, or dynamic code.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hunter.research_campaign.errors import (
    ResearchCampaignRunnerError,
)
from hunter.research_campaign.integration import (
    ingest_experiment_evidence,
    run_confidence_for_experiment,
    run_walk_forward_for_experiment,
)
from hunter.research_campaign.models import (
    MISSING_WALK_FORWARD_EVIDENCE,
    RESUME_FINGERPRINT_MISMATCH,
    RUNNER_ERROR,
    CampaignDossier,
    CampaignEvidenceSummary,
    CampaignExecutionManifest,
    CampaignExecutionPolicy,
    CampaignResumeManifest,
    CampaignStatus,
    CampaignStatusSummary,
    CompiledCampaign,
    CompiledExperiment,
    ExperimentEvidence,
    ExperimentExecutionRecord,
    ExperimentOutcome,
    ResearchCampaignSafetyFlags,
)
from hunter.research_campaign.resume import match_resume_evidence
from hunter.research_campaign.writer import CampaignWriter
from hunter.research_evidence_ledger.engine import EvidenceLedgerEngine
from hunter.research_evidence_ledger.models import (
    ExperimentRegistration,
)
from hunter.research_walk_forward.models import (
    ExperimentExecutionPolicy,
    WalkForwardExperimentReport,
)


def _build_status_summary(
    records: tuple[ExperimentExecutionRecord, ...],
) -> CampaignStatusSummary:
    """Build a CampaignStatusSummary from execution records."""
    total = len(records)
    completed = sum(1 for r in records if r.outcome == ExperimentOutcome.COMPLETED)
    failed = sum(1 for r in records if r.outcome == ExperimentOutcome.FAILED)
    blocked = sum(1 for r in records if r.outcome == ExperimentOutcome.BLOCKED)
    timed_out = sum(1 for r in records if r.outcome == ExperimentOutcome.TIMED_OUT)
    unsupported = sum(1 for r in records if r.outcome == ExperimentOutcome.UNSUPPORTED)
    insufficient_evidence = sum(
        1 for r in records if r.outcome == ExperimentOutcome.INSUFFICIENT_EVIDENCE
    )
    withdrawn = sum(1 for r in records if r.outcome == ExperimentOutcome.WITHDRAWN)
    skipped_by_policy = sum(
        1 for r in records if r.outcome == ExperimentOutcome.SKIPPED_BY_POLICY
    )
    stale_resume_evidence = sum(
        1 for r in records if r.outcome == ExperimentOutcome.STALE_RESUME_EVIDENCE
    )

    summary = CampaignStatusSummary(
        total=total,
        completed=completed,
        failed=failed,
        blocked=blocked,
        timed_out=timed_out,
        unsupported=unsupported,
        insufficient_evidence=insufficient_evidence,
        withdrawn=withdrawn,
        skipped_by_policy=skipped_by_policy,
        stale_resume_evidence=stale_resume_evidence,
    )

    from hunter.research_campaign.fingerprint import status_summary_fingerprint
    fp = status_summary_fingerprint(summary)
    object.__setattr__(summary, "fingerprint", fp)
    return summary


def _build_evidence_summary(
    records: tuple[ExperimentExecutionRecord, ...],
) -> CampaignEvidenceSummary:
    """Build a CampaignEvidenceSummary from execution records."""
    walk_forward_attempted = sum(
        1 for r in records if r.evidence.walk_forward_report is not None
    )
    walk_forward_completed = sum(
        1
        for r in records
        if r.evidence.walk_forward_report is not None
        and r.outcome == ExperimentOutcome.COMPLETED
    )
    confidence_attempted = sum(
        1 for r in records if r.evidence.confidence_report is not None
    )
    confidence_completed = sum(
        1
        for r in records
        if r.evidence.confidence_report is not None
        and r.outcome == ExperimentOutcome.COMPLETED
    )
    ledger_entries = sum(
        1 for r in records if r.evidence.ledger_entry is not None
    )
    ledger_snapshots = sum(
        1 for r in records if r.evidence.ledger_snapshot is not None
    )

    summary = CampaignEvidenceSummary(
        walk_forward_attempted=walk_forward_attempted,
        walk_forward_completed=walk_forward_completed,
        confidence_attempted=confidence_attempted,
        confidence_completed=confidence_completed,
        ledger_entries=ledger_entries,
        ledger_snapshots=ledger_snapshots,
    )

    from hunter.research_campaign.fingerprint import (
        evidence_summary_fingerprint,
    )
    fp = evidence_summary_fingerprint(summary)
    object.__setattr__(summary, "fingerprint", fp)
    return summary


def _build_dossier(
    campaign_definition: object,
    compiled_campaign: CompiledCampaign,
    records: tuple[ExperimentExecutionRecord, ...],
    status: CampaignStatus,
) -> CampaignDossier:
    """Build a CampaignDossier from records."""
    status_summary = _build_status_summary(records)
    evidence_summary = _build_evidence_summary(records)

    dossier = CampaignDossier(
        campaign_id=compiled_campaign.campaign.campaign_id,
        campaign_fingerprint=compiled_campaign.campaign.fingerprint,
        compiled_campaign_fingerprint=compiled_campaign.fingerprint,
        status_summary=status_summary,
        evidence_summary=evidence_summary,
        execution_records=records,
        safety_flags=ResearchCampaignSafetyFlags(),
        fingerprint="",
        reason_codes=(),
    )

    from hunter.research_campaign.fingerprint import (
        campaign_dossier_fingerprint,
    )
    fp = campaign_dossier_fingerprint(dossier)
    object.__setattr__(dossier, "fingerprint", fp)
    return dossier


def run_campaign_sequential(
    manifest: CampaignExecutionManifest,
    resume_manifest: CampaignResumeManifest | None = None,
    *,
    writer: CampaignWriter | None = None,
    run_id: str | None = None,
) -> CampaignDossier:
    """Execute a compiled campaign sequentially, experiment by experiment.

    Parameters
    ----------
    manifest : CampaignExecutionManifest
        The execution manifest with compiled campaign and registrations.
    resume_manifest : CampaignResumeManifest | None
        Optional resume manifest with prior evidence.
    writer : CampaignWriter | None
        Optional writer for checkpoint persistence.
    run_id : str | None
        Optional run identifier.

    Returns
    -------
    CampaignDossier
        Final dossier with all execution records and summaries.
    """
    compiled_campaign: CompiledCampaign = manifest.compiled_campaign
    registration_set = manifest.registration_set
    definition = manifest.campaign_definition

    records: list[ExperimentExecutionRecord] = []
    ledger_engine = EvidenceLedgerEngine()
    failure_count: int = 0
    stopped: bool = False
    final_status: CampaignStatus = CampaignStatus.COMPLETED

    # Determine prior evidence from resume manifest.
    prior_evidence = (
        resume_manifest.prior_evidence if resume_manifest is not None else ()
    )
    resume_policy = (
        resume_manifest.resume_policy
        if resume_manifest is not None
        else definition.resume_policy
    )

    for compiled_exp in compiled_campaign.experiments:
        if stopped:
            # Apply stop policy: mark remaining as SKIPPED_BY_POLICY.
            rec = _build_skipped_record(compiled_exp, definition.campaign_id)
            records.append(rec)
            if writer is not None:
                writer.write_checkpoint(
                    checkpoint_id=f"cp-{run_id or 'run'}-{len(records)}",
                    campaign_id=definition.campaign_id,
                    checkpoint_index=len(records),
                    experiment_records=tuple(records),
                    status=CampaignStatus.STOPPED,
                )
            continue

        started_at = datetime.now(timezone.utc)

        # Get registration for this experiment.
        reg = registration_set.registration_by_experiment_id.get(
            compiled_exp.experiment_id
        )
        if reg is None:
            # Missing registration — record BLOCKED.
            rec = _build_failed_record(
                compiled_exp,
                definition.campaign_id,
                started_at,
                ExperimentOutcome.BLOCKED,
                ("MISSING_REGISTRATION",),
            )
            records.append(rec)
            failure_count += 1
            stopped = _check_stop_policy(
                definition, failure_count, rec.outcome
            )
            if writer is not None:
                writer.write_checkpoint(
                    checkpoint_id=f"cp-{run_id or 'run'}-{len(records)}",
                    campaign_id=definition.campaign_id,
                    checkpoint_index=len(records),
                    experiment_records=tuple(records),
                    status=CampaignStatus.RUNNING,
                )
            continue

        # Validate registration fingerprint.
        if reg.fingerprint != compiled_exp.registration_fingerprint:
            # Registration drift or mismatch.
            rec = _build_failed_record(
                compiled_exp,
                definition.campaign_id,
                started_at,
                ExperimentOutcome.STALE_RESUME_EVIDENCE,
                (RESUME_FINGERPRINT_MISMATCH,),
            )
            records.append(rec)
            failure_count += 1
            stopped = _check_stop_policy(
                definition, failure_count, rec.outcome
            )
            if writer is not None:
                writer.write_checkpoint(
                    checkpoint_id=f"cp-{run_id or 'run'}-{len(records)}",
                    campaign_id=definition.campaign_id,
                    checkpoint_index=len(records),
                    experiment_records=tuple(records),
                    status=CampaignStatus.RUNNING,
                )
            continue

        # Check for resume match.
        matched = match_resume_evidence(
            compiled_exp, prior_evidence, resume_policy
        )
        if matched is not None:
            # Reuse prior evidence.
            completed_at = datetime.now(timezone.utc)
            evidence = ExperimentEvidence(
                walk_forward_report=(
                    matched.evidence.walk_forward_report
                    if matched.evidence is not None
                    else None
                ),
                confidence_report=(
                    matched.evidence.confidence_report
                    if matched.evidence is not None
                    else None
                ),
                ledger_entry=(
                    matched.evidence.ledger_entry
                    if matched.evidence is not None
                    else None
                ),
                ledger_snapshot=(
                    matched.evidence.ledger_snapshot
                    if matched.evidence is not None
                    else None
                ),
                walk_forward_report_fingerprint=(
                    matched.walk_forward_report_fingerprint
                ),
                confidence_report_fingerprint=(
                    matched.confidence_report_fingerprint
                ),
                ledger_entry_fingerprint=matched.ledger_entry_fingerprint,
                ledger_snapshot_fingerprint=(
                    matched.evidence.ledger_snapshot_fingerprint
                    if matched.evidence is not None
                    else ""
                ),
            )
            rec = _build_record(
                compiled_exp,
                definition.campaign_id,
                started_at,
                completed_at,
                ExperimentOutcome.COMPLETED,
                evidence,
                (),
            )
            records.append(rec)
            if writer is not None:
                writer.write_checkpoint(
                    checkpoint_id=f"cp-{run_id or 'run'}-{len(records)}",
                    campaign_id=definition.campaign_id,
                    checkpoint_index=len(records),
                    experiment_records=tuple(records),
                    status=CampaignStatus.RUNNING,
                )
            continue

        # Run MVP-66 walk-forward.
        try:
            wf_report = run_walk_forward_for_experiment(
                compiled_exp,
                execution_policy=ExperimentExecutionPolicy.COLLECT_ALL,  # placeholder; definition.execution_policy maps to campaign-level, wf uses ExperimentExecutionPolicy
            )
        except Exception as exc:
            completed_at = datetime.now(timezone.utc)
            outcome = _classify_exception_outcome(exc)
            rec = _build_failed_record(
                compiled_exp,
                definition.campaign_id,
                completed_at,
                outcome,
                (RUNNER_ERROR,),
            )
            records.append(rec)
            failure_count += 1
            stopped = _check_stop_policy(
                definition, failure_count, rec.outcome
            )
            if writer is not None:
                writer.write_checkpoint(
                    checkpoint_id=f"cp-{run_id or 'run'}-{len(records)}",
                    campaign_id=definition.campaign_id,
                    checkpoint_index=len(records),
                    experiment_records=tuple(records),
                    status=CampaignStatus.RUNNING,
                )
            continue

        # Run MVP-67 confidence.
        try:
            confidence_report = run_confidence_for_experiment(
                wf_report, compiled_exp
            )
        except ResearchCampaignRunnerError:
            # Insufficient evidence (incomplete windows) — record as INSUFFICIENT_EVIDENCE
            completed_at = datetime.now(timezone.utc)
            evidence = ExperimentEvidence(
                walk_forward_report=wf_report,
                walk_forward_report_fingerprint=str(wf_report.fingerprint),
            )
            rec = _build_record(
                compiled_exp,
                definition.campaign_id,
                started_at,
                completed_at,
                ExperimentOutcome.INSUFFICIENT_EVIDENCE,
                evidence,
                (MISSING_WALK_FORWARD_EVIDENCE,),
            )
            records.append(rec)
            if writer is not None:
                writer.write_checkpoint(
                    checkpoint_id=f"cp-{run_id or 'run'}-{len(records)}",
                    campaign_id=definition.campaign_id,
                    checkpoint_index=len(records),
                    experiment_records=tuple(records),
                    status=CampaignStatus.RUNNING,
                )
            continue
        except Exception as exc:
            completed_at = datetime.now(timezone.utc)
            outcome = _classify_exception_outcome(exc)
            evidence = ExperimentEvidence(
                walk_forward_report=wf_report,
                walk_forward_report_fingerprint=str(wf_report.fingerprint),
            )
            rec = _build_record(
                compiled_exp,
                definition.campaign_id,
                started_at,
                completed_at,
                outcome,
                evidence,
                (RUNNER_ERROR,),
            )
            records.append(rec)
            failure_count += 1
            stopped = _check_stop_policy(
                definition, failure_count, rec.outcome
            )
            if writer is not None:
                writer.write_checkpoint(
                    checkpoint_id=f"cp-{run_id or 'run'}-{len(records)}",
                    campaign_id=definition.campaign_id,
                    checkpoint_index=len(records),
                    experiment_records=tuple(records),
                    status=CampaignStatus.RUNNING,
                )
            continue

        # Ingest into MVP-68 ledger.
        try:
            entry, snapshot = ingest_experiment_evidence(
                engine=ledger_engine,
                compiled_experiment=compiled_exp,
                registration=reg,
                walk_forward_report=wf_report,
                confidence_report=confidence_report,
            )
        except Exception as exc:
            completed_at = datetime.now(timezone.utc)
            evidence = ExperimentEvidence(
                walk_forward_report=wf_report,
                confidence_report=confidence_report,
                walk_forward_report_fingerprint=str(wf_report.fingerprint),
                confidence_report_fingerprint=str(confidence_report.fingerprint),
            )
            rec = _build_record(
                compiled_exp,
                definition.campaign_id,
                started_at,
                completed_at,
                ExperimentOutcome.FAILED,
                evidence,
                (RUNNER_ERROR,),
            )
            records.append(rec)
            failure_count += 1
            stopped = _check_stop_policy(
                definition, failure_count, rec.outcome
            )
            if writer is not None:
                writer.write_checkpoint(
                    checkpoint_id=f"cp-{run_id or 'run'}-{len(records)}",
                    campaign_id=definition.campaign_id,
                    checkpoint_index=len(records),
                    experiment_records=tuple(records),
                    status=CampaignStatus.RUNNING,
                )
            continue

        # COMPLETED.
        completed_at = datetime.now(timezone.utc)
        evidence = ExperimentEvidence(
            walk_forward_report=wf_report,
            confidence_report=confidence_report,
            ledger_entry=entry,
            ledger_snapshot=snapshot,
            walk_forward_report_fingerprint=str(wf_report.fingerprint),
            confidence_report_fingerprint=str(confidence_report.fingerprint),
            ledger_entry_fingerprint=str(entry.fingerprint),
            ledger_snapshot_fingerprint=str(snapshot.fingerprint),
        )
        rec = _build_record(
            compiled_exp,
            definition.campaign_id,
            started_at,
            completed_at,
            ExperimentOutcome.COMPLETED,
            evidence,
            (),
        )
        records.append(rec)
        if writer is not None:
            writer.write_checkpoint(
                checkpoint_id=f"cp-{run_id or 'run'}-{len(records)}",
                campaign_id=definition.campaign_id,
                checkpoint_index=len(records),
                experiment_records=tuple(records),
                status=CampaignStatus.RUNNING,
            )

    # Determine final status.
    if stopped:
        final_status = CampaignStatus.STOPPED
    elif any(
        r.outcome in (
            ExperimentOutcome.FAILED,
            ExperimentOutcome.BLOCKED,
            ExperimentOutcome.TIMED_OUT,
        )
        for r in records
    ):
        final_status = CampaignStatus.COMPLETED  # Completed with failures still counts as COMPLETED
    else:
        final_status = CampaignStatus.COMPLETED

    dossier = _build_dossier(
        definition, compiled_campaign, tuple(records), final_status
    )
    return dossier


def _build_record(
    compiled_exp: CompiledExperiment,
    campaign_id: str,
    started_at: datetime,
    completed_at: datetime,
    outcome: ExperimentOutcome,
    evidence: ExperimentEvidence,
    reason_codes: tuple[str, ...],
) -> ExperimentExecutionRecord:
    """Build an ExperimentExecutionRecord with deterministic fingerprint."""
    rec = ExperimentExecutionRecord(
        experiment_id=compiled_exp.experiment_id,
        campaign_id=campaign_id,
        experiment_fingerprint=compiled_exp.fingerprint,
        registration_fingerprint=compiled_exp.registration_fingerprint,
        outcome=outcome,
        started_at=started_at,
        completed_at=completed_at,
        evidence=evidence,
        reason_codes=reason_codes,
        notes="",
    )

    from hunter.research_campaign.fingerprint import (
        experiment_execution_record_fingerprint,
    )

    fp = experiment_execution_record_fingerprint(rec)
    object.__setattr__(rec, "fingerprint", fp)
    return rec


def _build_failed_record(
    compiled_exp: CompiledExperiment,
    campaign_id: str,
    timestamp: datetime,
    outcome: ExperimentOutcome,
    reason_codes: tuple[str, ...],
) -> ExperimentExecutionRecord:
    """Build a failed record with no evidence."""
    evidence = ExperimentEvidence()
    return _build_record(
        compiled_exp,
        campaign_id,
        timestamp,
        timestamp,
        outcome,
        evidence,
        reason_codes,
    )


def _build_skipped_record(
    compiled_exp: CompiledExperiment,
    campaign_id: str,
) -> ExperimentExecutionRecord:
    """Build a SKIPPED_BY_POLICY record."""
    now = datetime.now(timezone.utc)
    evidence = ExperimentEvidence()
    return _build_record(
        compiled_exp,
        campaign_id,
        now,
        now,
        ExperimentOutcome.SKIPPED_BY_POLICY,
        evidence,
        ("STOPPED_BY_POLICY",),
    )


def _check_stop_policy(
    definition: object,
    failure_count: int,
    last_outcome: ExperimentOutcome,
) -> bool:
    """Check whether the stop policy triggers.

    Returns True if execution should stop.
    """
    policy = definition.execution_policy  # type: ignore[attr-defined]

    if policy == CampaignExecutionPolicy.COLLECT_ALL:
        return False

    if policy == CampaignExecutionPolicy.FAIL_FAST:
        if last_outcome in (
            ExperimentOutcome.FAILED,
            ExperimentOutcome.BLOCKED,
            ExperimentOutcome.TIMED_OUT,
        ):
            return True
        return False

    if policy == CampaignExecutionPolicy.STOP_AFTER_N_FAILURES:
        threshold = definition.stop_after_n_failures  # type: ignore[attr-defined]
        if threshold is not None and failure_count >= threshold:
            return True
        return False

    return False


def _classify_exception_outcome(exc: Exception) -> ExperimentOutcome:
    """Classify an exception into an ExperimentOutcome."""
    exc_name = type(exc).__name__
    exc_msg = str(exc).upper()

    if "TIMEOUT" in exc_msg or "TIMED_OUT" in exc_msg:
        return ExperimentOutcome.TIMED_OUT
    if "UNSUPPORTED" in exc_msg:
        return ExperimentOutcome.UNSUPPORTED
    if "BLOCKED" in exc_msg:
        return ExperimentOutcome.BLOCKED
    if "INSUFFICIENT" in exc_msg:
        return ExperimentOutcome.INSUFFICIENT_EVIDENCE

    return ExperimentOutcome.FAILED
