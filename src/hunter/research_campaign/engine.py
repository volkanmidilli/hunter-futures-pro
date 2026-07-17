"""Convenience engine functions for the research campaign compiler and orchestrator (MVP-69/MVP-70 / SPEC-070).

No subprocess, threading, network, eval, exec, or dynamic code.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hunter.research_campaign.compiler import compile_campaign
from hunter.research_campaign.fingerprint import (
    campaign_definition_fingerprint,
    execution_manifest_fingerprint,
)
from hunter.research_campaign.models import (
    CampaignDossier,
    CampaignEvidenceSummary,
    CampaignExecutionManifest,
    CampaignResumeManifest,
    CampaignStatus,
    CampaignStatusSummary,
    CompiledCampaign,
    ExperimentExecutionRecord,
    ResearchCampaignDefinition,
)
from hunter.research_campaign.runner import run_campaign_sequential
from hunter.research_campaign.writer import CampaignWriter


def compile_campaign_definition(
    definition: ResearchCampaignDefinition,
) -> CompiledCampaign:
    """Compile a campaign definition into a ``CompiledCampaign``.

    This is a convenience wrapper around ``compile_campaign`` that
    discards the registration set (compile-only mode).

    Parameters
    ----------
    definition : ResearchCampaignDefinition
        The validated campaign definition.

    Returns
    -------
    CompiledCampaign
    """
    result = compile_campaign(definition, compile_only=True)
    # In compile_only mode, return is a single CompiledCampaign.
    return result  # type: ignore[return-value]


def build_campaign_execution_manifest(
    definition: ResearchCampaignDefinition,
    compiled_campaign: CompiledCampaign,
    registration_set: object,
) -> CampaignExecutionManifest:
    """Build a ``CampaignExecutionManifest`` from a definition, compiled campaign, and registration set.

    Parameters
    ----------
    definition : ResearchCampaignDefinition
        The original campaign definition.
    compiled_campaign : CompiledCampaign
        The compiled campaign.
    registration_set : CampaignRegistrationSet
        The pre-registration set.

    Returns
    -------
    CampaignExecutionManifest
    """
    from hunter.research_campaign.models import CampaignRegistrationSet

    if not isinstance(registration_set, CampaignRegistrationSet):
        raise TypeError(
            f"registration_set must be a CampaignRegistrationSet, "
            f"got {type(registration_set).__name__}"
        )

    manifest = CampaignExecutionManifest(
        campaign_definition=definition,
        compiled_campaign=compiled_campaign,
        registration_set=registration_set,
        fingerprint="",
        reason_codes=(),
    )

    fp = execution_manifest_fingerprint(manifest)
    object.__setattr__(manifest, "fingerprint", fp)
    return manifest


def run_campaign(
    definition: ResearchCampaignDefinition,
    *,
    output_dir: str | Path | None = None,
    resume_manifest: CampaignResumeManifest | None = None,
    compile_only: bool = False,
    run_id: str | None = None,
) -> CampaignDossier:
    """Orchestrate a full research campaign: compile, register, run, write.

    This is the main entry point for executing a research campaign from
    definition to dossier.

    Parameters
    ----------
    definition : ResearchCampaignDefinition
        The campaign definition.
    output_dir : str | Path | None
        Optional output directory for artifacts. If provided, all artifacts
        are written. If None, artifacts are not written.
    resume_manifest : CampaignResumeManifest | None
        Optional resume manifest for reusing prior evidence.
    compile_only : bool
        If True, compile only (no execution). Returns an empty dossier.
    run_id : str | None
        Optional run identifier for checkpoint naming.

    Returns
    -------
    CampaignDossier
        The final campaign dossier.
    """
    # 1. Compile the campaign.
    compiled, registration_set = compile_campaign(definition, compile_only=False)  # type: ignore[assignment]

    if compile_only:
        # Build a compile-only dossier.
        from hunter.research_campaign.fingerprint import (
            campaign_dossier_fingerprint,
        )

        empty_records: tuple[ExperimentExecutionRecord, ...] = ()
        status_summary = CampaignStatusSummary(
            total=0,
            completed=0,
            failed=0,
            blocked=0,
            timed_out=0,
            unsupported=0,
            insufficient_evidence=0,
            withdrawn=0,
            skipped_by_policy=0,
            stale_resume_evidence=0,
        )
        evidence_summary = CampaignEvidenceSummary(
            walk_forward_attempted=0,
            walk_forward_completed=0,
            confidence_attempted=0,
            confidence_completed=0,
            ledger_entries=0,
            ledger_snapshots=0,
        )
        dossier = CampaignDossier(
            campaign_id=definition.campaign_id,
            campaign_fingerprint=definition.fingerprint,
            compiled_campaign_fingerprint=compiled.fingerprint,
            status_summary=status_summary,
            evidence_summary=evidence_summary,
            execution_records=empty_records,
            safety_flags=definition.safety_flags,
            fingerprint="",
            reason_codes=(),
        )
        fp = campaign_dossier_fingerprint(dossier)
        object.__setattr__(dossier, "fingerprint", fp)

        # Write definition and compiled matrix only.
        if output_dir is not None:
            writer = CampaignWriter(
                output_dir=output_dir,
                overwrite=(
                    definition.output_policy.overwrite
                    if definition.output_policy is not None
                    else False
                ),
            )
            writer.write_definition(definition)
            writer.write_compiled_matrix(compiled)

        return dossier

    # 2. Build execution manifest.
    manifest = build_campaign_execution_manifest(
        definition=definition,
        compiled_campaign=compiled,
        registration_set=registration_set,
    )

    # 3. Run sequential.
    writer: CampaignWriter | None = None
    if output_dir is not None:
        writer = CampaignWriter(
            output_dir=output_dir,
            overwrite=(
                definition.output_policy.overwrite
                if definition.output_policy is not None
                else False
            ),
        )

    dossier = run_campaign_sequential(
        manifest=manifest,
        resume_manifest=resume_manifest,
        writer=writer,
        run_id=run_id,
    )

    # 4. Write all artifacts.
    if writer is not None:
        evidence_summary = dossier.evidence_summary
        writer.write_all_campaign_artifacts(
            definition=definition,
            compiled_campaign=compiled,
            registration_set=registration_set,
            execution_manifest=manifest,
            execution_records=dossier.execution_records,
            dossier=dossier,
            resume_manifest=resume_manifest,
            evidence_summary=evidence_summary,
        )

    return dossier


def build_dossier(
    records: tuple[ExperimentExecutionRecord, ...],
    status: CampaignStatus,
    campaign_definition: ResearchCampaignDefinition,
    compiled_campaign: CompiledCampaign,
) -> CampaignDossier:
    """Build a ``CampaignDossier`` from execution records.

    Parameters
    ----------
    records : tuple[ExperimentExecutionRecord, ...]
        Execution records from the runner.
    status : CampaignStatus
        Overall campaign status.
    campaign_definition : ResearchCampaignDefinition
        The campaign definition.
    compiled_campaign : CompiledCampaign
        The compiled campaign.

    Returns
    -------
    CampaignDossier
    """
    from hunter.research_campaign.runner import (
        _build_evidence_summary,
        _build_status_summary,
    )

    # Reuse internal builders from runner module.
    status_summary = _build_status_summary(records)
    evidence_summary = _build_evidence_summary(records)

    from hunter.research_campaign.fingerprint import (
        campaign_dossier_fingerprint,
    )

    dossier = CampaignDossier(
        campaign_id=campaign_definition.campaign_id,
        campaign_fingerprint=campaign_definition.fingerprint,
        compiled_campaign_fingerprint=compiled_campaign.fingerprint,
        status_summary=status_summary,
        evidence_summary=evidence_summary,
        execution_records=records,
        safety_flags=campaign_definition.safety_flags,
        fingerprint="",
        reason_codes=campaign_definition.reason_codes,
    )
    fp = campaign_dossier_fingerprint(dossier)
    object.__setattr__(dossier, "fingerprint", fp)
    return dossier


def build_status_summary(
    records: tuple[ExperimentExecutionRecord, ...],
) -> CampaignStatusSummary:
    """Build a ``CampaignStatusSummary`` from execution records.

    Parameters
    ----------
    records : tuple[ExperimentExecutionRecord, ...]
        Execution records.

    Returns
    -------
    CampaignStatusSummary
    """
    from hunter.research_campaign.runner import _build_status_summary

    return _build_status_summary(records)


def build_evidence_summary(
    records: tuple[ExperimentExecutionRecord, ...],
) -> CampaignEvidenceSummary:
    """Build a ``CampaignEvidenceSummary`` from execution records.

    Parameters
    ----------
    records : tuple[ExperimentExecutionRecord, ...]
        Execution records.

    Returns
    -------
    CampaignEvidenceSummary
    """
    from hunter.research_campaign.runner import _build_evidence_summary

    return _build_evidence_summary(records)
