"""Resume manifest building and evidence matching for compiled campaigns (MVP-69 / SPEC-070)."""

from __future__ import annotations

from hunter.research_campaign.fingerprint import campaign_definition_fingerprint
from hunter.research_campaign.models import (
    CampaignResumeManifest,
    CompiledCampaign,
    CompiledExperiment,
    ExperimentEvidence,
    ExperimentExecutionRecord,
    ExperimentOutcome,
    PriorExperimentEvidence,
    ResearchCampaignDefinition,
    ResearchCampaignSafetyFlags,
    ResumePolicy,
)


def build_resume_manifest(
    campaign_definition: ResearchCampaignDefinition,
    compiled_campaign: CompiledCampaign,
    records: tuple[ExperimentExecutionRecord, ...],
    resume_policy: ResumePolicy,
) -> CampaignResumeManifest:
    """Build a ``CampaignResumeManifest`` from prior execution records.

    Parameters
    ----------
    campaign_definition : ResearchCampaignDefinition
        The original campaign definition.
    compiled_campaign : CompiledCampaign
        The compiled campaign (used for reference fingerprint lookups).
    records : tuple[ExperimentExecutionRecord, ...]
        Prior execution records with completed (or reusable) outcomes.
    resume_policy : ResumePolicy
        How to handle stale or missing evidence on resume.

    Returns
    -------
    CampaignResumeManifest
        Immutable resume manifest.
    """
    campaign_fp = campaign_definition_fingerprint(campaign_definition)

    compiled_by_id: dict[str, CompiledExperiment] = {
        e.experiment_id: e for e in compiled_campaign.experiments
    }

    prior_evidence_list: list[PriorExperimentEvidence] = []
    for rec in records:
        # Only include COMPLETED or other reusable outcomes.
        if rec.outcome not in (
            ExperimentOutcome.COMPLETED,
            ExperimentOutcome.INSUFFICIENT_EVIDENCE,
        ):
            continue

        compiled_exp = compiled_by_id.get(rec.experiment_id)
        if compiled_exp is None:
            continue

        evidence = rec.evidence
        prior = PriorExperimentEvidence(
            experiment_id=rec.experiment_id,
            experiment_fingerprint=rec.experiment_fingerprint,
            registration_fingerprint=rec.registration_fingerprint,
            strategy_reference_fingerprint=compiled_exp.strategy.fingerprint,
            historical_data_reference_fingerprint=compiled_exp.historical_data.fingerprint,
            universe_plan_reference_fingerprint=compiled_exp.universe_plan.fingerprint,
            walk_forward_template_reference_fingerprint=compiled_exp.walk_forward_template.fingerprint,
            confidence_config_reference_fingerprint=compiled_exp.confidence_config.fingerprint,
            walk_forward_report_fingerprint=evidence.walk_forward_report_fingerprint,
            confidence_report_fingerprint=evidence.confidence_report_fingerprint,
            ledger_entry_fingerprint=evidence.ledger_entry_fingerprint,
            ledger_snapshot_fingerprint=evidence.ledger_snapshot_fingerprint,
            inherited_safety_invariants=ResearchCampaignSafetyFlags(),
            outcome=rec.outcome,
            evidence=evidence,
        )
        prior_evidence_list.append(prior)

    manifest = CampaignResumeManifest(
        campaign_fingerprint=campaign_fp,
        prior_evidence=tuple(prior_evidence_list),
        resume_policy=resume_policy,
        fingerprint="",
        reason_codes=(),
    )

    # Compute manifest fingerprint.
    from hunter.research_campaign.fingerprint import (
        campaign_resume_manifest_fingerprint,
    )

    fp = campaign_resume_manifest_fingerprint(manifest)
    object.__setattr__(manifest, "fingerprint", fp)
    return manifest


def match_resume_evidence(
    compiled_experiment: CompiledExperiment,
    prior_evidence: tuple[PriorExperimentEvidence, ...],
    resume_policy: ResumePolicy,
) -> PriorExperimentEvidence | None:
    """Find matching prior evidence for a compiled experiment.

    An exact match requires *all* fingerprint fields to match between the
    compiled experiment and the prior evidence record.

    Parameters
    ----------
    compiled_experiment : CompiledExperiment
        The experiment to match.
    prior_evidence : tuple[PriorExperimentEvidence, ...]
        Prior evidence records from the resume manifest.
    resume_policy : ResumePolicy
        Resume policy governing matching behaviour.

    Returns
    -------
    PriorExperimentEvidence | None
        The matching prior evidence, or None if no exact match exists.
    """
    for prior in prior_evidence:
        # experiment_id must match.
        if prior.experiment_id != compiled_experiment.experiment_id:
            continue

        # The compiled experiment fingerprint must match the prior's.
        if prior.experiment_fingerprint != compiled_experiment.fingerprint:
            continue

        # All reference-level fingerprint fields must match exactly.
        if prior.registration_fingerprint != compiled_experiment.registration_fingerprint:
            continue
        if prior.strategy_reference_fingerprint != compiled_experiment.strategy.fingerprint:
            continue
        if (
            prior.historical_data_reference_fingerprint
            != compiled_experiment.historical_data.fingerprint
        ):
            continue
        if (
            prior.universe_plan_reference_fingerprint
            != compiled_experiment.universe_plan.fingerprint
        ):
            continue
        if (
            prior.walk_forward_template_reference_fingerprint
            != compiled_experiment.walk_forward_template.fingerprint
        ):
            continue
        if (
            prior.confidence_config_reference_fingerprint
            != compiled_experiment.confidence_config.fingerprint
        ):
            continue

        # Walk-forward / confidence / ledger fingerprints must be present in the
        # prior evidence (non-empty) for a completed run to be reusable.
        if not prior.walk_forward_report_fingerprint:
            continue
        if not prior.confidence_report_fingerprint:
            continue
        if not prior.ledger_entry_fingerprint:
            continue

        # Inherited safety invariants must match (both default fail-closed flags).
        if prior.inherited_safety_invariants != ResearchCampaignSafetyFlags():
            continue

        # All checks passed — exact match.
        return prior

    return None


def _prior_has_full_evidence(prior: PriorExperimentEvidence) -> bool:
    """Return True if the prior record contains all required fingerprints."""
    return bool(
        prior.experiment_fingerprint
        and prior.registration_fingerprint
        and prior.strategy_reference_fingerprint
        and prior.historical_data_reference_fingerprint
        and prior.universe_plan_reference_fingerprint
        and prior.walk_forward_template_reference_fingerprint
        and prior.confidence_config_reference_fingerprint
        and prior.walk_forward_report_fingerprint
        and prior.confidence_report_fingerprint
        and prior.ledger_entry_fingerprint
    )
