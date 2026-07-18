"""Deterministic SHA-256 fingerprint functions for research campaign artifacts (MVP-69/MVP-70 / SPEC-070).

Every function produces a hex digest via ``json.dumps(..., sort_keys=True,
separators=(',', ':'), ensure_ascii=True)`` + ``hashlib.sha256``.

Excluded from all fingerprints: timestamps, notes, filesystem paths, PID,
hostname, labels, ``generated_at`` / ``created_at``, and ``LedgerSnapshot``
objects (replaced by their own fingerprint).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from hunter.research_campaign.models import (
    CampaignArtifactManifest,
    CampaignCheckpoint,
    CampaignDossier,
    CampaignEvidenceSummary,
    CampaignExecutionManifest,
    CampaignOutputPolicy,
    CampaignParameterSet,
    CampaignRegistrationSet,
    CampaignResumeManifest,
    CampaignStatusSummary,
    CompiledCampaign,
    CompiledExperiment,
    ExperimentEvidence,
    ExperimentExecutionRecord,
    FamilyReference,
    HistoricalDataReference,
    IndependenceMetadata,
    MetricFamilyScope,
    RegimePolicy,
    ResearchCampaignDefinition,
    ResearchCampaignSafetyFlags,
    StatisticalConfidenceConfigReference,
    StrategyReference,
    UniversePlanReference,
    WalkForwardTemplateReference,
)
from hunter.research_evidence_ledger.models import LedgerSnapshot
from hunter.research_walk_forward.models import WalkForwardCommonConfig

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_FINGERPRINT_EXPERIMENT_ID_PREFIX_LEN: int = 16


def _hash(payload: dict[str, Any]) -> str:
    """Deterministic SHA-256 hex digest of a JSON payload."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _safety_flags_to_dict(flags: ResearchCampaignSafetyFlags) -> dict[str, bool]:
    return {
        "research_only": flags.research_only,
        "execution_approval_granted": flags.execution_approval_granted,
        "production_approval_granted": flags.production_approval_granted,
        "live_trading_allowed": flags.live_trading_allowed,
        "automatic_execution_allowed": flags.automatic_execution_allowed,
        "human_approval_required": flags.human_approval_required,
        "no_action_commands_emitted": flags.no_action_commands_emitted,
        "no_network_connection": flags.no_network_connection,
        "no_database_connection": flags.no_database_connection,
        "no_exchange_connection": flags.no_exchange_connection,
        "no_remote_changes": flags.no_remote_changes,
        "no_parallel_execution": flags.no_parallel_execution,
        "no_direct_subprocess": flags.no_direct_subprocess,
        "no_strategy_mutation": flags.no_strategy_mutation,
        "no_universe_mutation": flags.no_universe_mutation,
        "no_config_mutation": flags.no_config_mutation,
    }


def _output_policy_to_dict(policy: CampaignOutputPolicy | None) -> dict[str, Any] | None:
    """Convert output policy to dict, excluding ``output_dir`` (a path)."""
    if policy is None:
        return None
    return {
        "overwrite": policy.overwrite,
        "write_checkpoints": policy.write_checkpoints,
        "checkpoint_version_policy": policy.checkpoint_version_policy,
    }


def _strategy_ref_to_dict(ref: StrategyReference) -> dict[str, Any]:
    """Strategy reference with fingerprint but without path."""
    return {
        "strategy_name": ref.strategy_name,
        "fingerprint": ref.fingerprint,
    }


def _historical_data_ref_to_dict(ref: HistoricalDataReference) -> dict[str, Any]:
    """Historical data reference with fingerprint but without path."""
    return {
        "data_id": ref.data_id,
        "fingerprint": ref.fingerprint,
    }


def _universe_plan_ref_to_dict(ref: UniversePlanReference) -> dict[str, Any]:
    """Universe plan reference with fingerprint but without path."""
    return {
        "universe_plan_id": ref.universe_plan_id,
        "fingerprint": ref.fingerprint,
    }


def _wf_template_ref_to_dict(ref: WalkForwardTemplateReference) -> dict[str, Any]:
    """Walk-forward template reference (no windows details — rely on fingerprint)."""
    return {
        "template_id": ref.template_id,
        "mode": ref.mode,
        "contiguous": ref.contiguous,
        "fingerprint": ref.fingerprint,
    }


def _confidence_config_ref_to_dict(ref: StatisticalConfidenceConfigReference) -> dict[str, Any]:
    return {
        "config_id": ref.config_id,
        "fingerprint": ref.fingerprint,
    }


def _family_ref_to_dict(ref: FamilyReference) -> dict[str, Any]:
    return {
        "family_id": ref.family_id,
        "family_type": ref.family_type,
        "fingerprint": ref.fingerprint,
    }


def _metric_scope_to_dict(scope: MetricFamilyScope) -> dict[str, Any]:
    return {
        "metric_names": scope.metric_names,
        "direction_policy": scope.direction_policy,
    }


def _independence_to_dict(meta: IndependenceMetadata) -> dict[str, Any]:
    """Independence metadata excluding ``notes``."""
    return {
        "independence_class": meta.independence_class.value,
        "source_experiment_ids": meta.source_experiment_ids,
    }


def _regime_to_dict(policy: RegimePolicy) -> dict[str, Any]:
    return {
        "regime_label": policy.regime_label.value,
        "required": policy.required,
    }


# ---------------------------------------------------------------------------
# Parameter-set fingerprint (helper)
# ---------------------------------------------------------------------------


def _parameters_to_dict(params: CampaignParameterSet) -> dict[str, Any]:
    """Canonical parameter-set representation excluding paths / notes."""
    return {
        "common_config": _common_config_to_dict(params.common_config),
        "strategies": tuple(_strategy_ref_to_dict(s) for s in params.strategies),
        "timeframes": params.timeframes,
        "historical_data": tuple(_historical_data_ref_to_dict(d) for d in params.historical_data),
        "universe_plans": tuple(_universe_plan_ref_to_dict(u) for u in params.universe_plans),
        "walk_forward_templates": tuple(_wf_template_ref_to_dict(w) for w in params.walk_forward_templates),
        "confidence_configs": tuple(_confidence_config_ref_to_dict(c) for c in params.confidence_configs),
        "experiment_families": tuple(_family_ref_to_dict(f) for f in params.experiment_families),
        "hypothesis_families": tuple(_family_ref_to_dict(f) for f in params.hypothesis_families),
        "metric_families": tuple(_metric_scope_to_dict(m) for m in params.metric_families),
        "independence_metadata": tuple(_independence_to_dict(ind) for ind in params.independence_metadata),
        "regime_policies": tuple(_regime_to_dict(r) for r in params.regime_policies),
        "include_rules": tuple(
            {"field": r.field, "operator": r.operator.value, "value": _rule_value(r), "action": r.action}
            for r in params.include_rules
        ),
        "exclude_rules": tuple(
            {"field": r.field, "operator": r.operator.value, "value": _rule_value(r), "action": r.action}
            for r in params.exclude_rules
        ),
    }


def _common_config_to_dict(common: WalkForwardCommonConfig) -> dict[str, Any]:
    """Common config fingerprint payload excluding filesystem paths."""
    return {
        "balance": str(common.balance),
        "stake": str(common.stake),
        "max_open_trades": common.max_open_trades,
        "fee": str(common.fee),
        "protections": common.protections,
        "timeout_seconds": common.timeout_seconds,
        "contiguous_placeholder": True,  # contiguous is on the template, not common config
    }


def _rule_value(rule: Any) -> Any:
    """Normalize rule value for JSON serialization (tuples → lists)."""
    v = rule.value
    if isinstance(v, tuple):
        return list(v)
    return v


# ---------------------------------------------------------------------------
# Evidence payload builder (excludes LedgerSnapshot objects)
# ---------------------------------------------------------------------------


def _experiment_evidence_to_dict(evidence: ExperimentEvidence) -> dict[str, Any]:
    """Convert experiment evidence, replacing LedgerSnapshot with its fingerprint."""
    d: dict[str, Any] = {}
    if evidence.walk_forward_report is not None:
        d["walk_forward_report_fingerprint"] = evidence.walk_forward_report_fingerprint
    if evidence.confidence_report is not None:
        d["confidence_report_fingerprint"] = evidence.confidence_report_fingerprint
    if evidence.ledger_entry is not None:
        d["ledger_entry_fingerprint"] = evidence.ledger_entry_fingerprint
    if evidence.ledger_snapshot is not None:
        # Use fingerprint instead of serializing the full snapshot object.
        d["ledger_snapshot_fingerprint"] = evidence.ledger_snapshot_fingerprint
    return d


# ---------------------------------------------------------------------------
# Public fingerprint functions
# ---------------------------------------------------------------------------


def campaign_definition_fingerprint(definition: ResearchCampaignDefinition) -> str:
    """Deterministic fingerprint for a campaign definition.

    Excludes: ``fingerprint``, ``metadata`` (labels).
    """
    payload: dict[str, Any] = {
        "campaign_id": definition.campaign_id,
        "campaign_schema_version": definition.campaign_schema_version,
        "parameters": _parameters_to_dict(definition.parameters),
        "max_experiment_count": definition.max_experiment_count,
        "execution_policy": definition.execution_policy.value,
        "stop_after_n_failures": definition.stop_after_n_failures,
        "resume_policy": definition.resume_policy.value,
        "output_policy": _output_policy_to_dict(definition.output_policy),
        "safety_flags": _safety_flags_to_dict(definition.safety_flags),
        "reason_codes": definition.reason_codes,
    }
    return _hash(payload)


def compiled_experiment_fingerprint(experiment: CompiledExperiment) -> str:
    """Deterministic fingerprint for a compiled experiment.

    Excludes: the object's own ``fingerprint`` field.
    """
    payload: dict[str, Any] = {
        "experiment_id": experiment.experiment_id,
        "campaign_id": experiment.campaign_id,
        "strategy": _strategy_ref_to_dict(experiment.strategy),
        "timeframe": experiment.timeframe,
        "historical_data": _historical_data_ref_to_dict(experiment.historical_data),
        "universe_plan": _universe_plan_ref_to_dict(experiment.universe_plan),
        "walk_forward_template": _wf_template_ref_to_dict(experiment.walk_forward_template),
        "confidence_config": _confidence_config_ref_to_dict(experiment.confidence_config),
        "experiment_family": _family_ref_to_dict(experiment.experiment_family),
        "hypothesis_family": _family_ref_to_dict(experiment.hypothesis_family),
        "metric_family": _metric_scope_to_dict(experiment.metric_family),
        "independence": _independence_to_dict(experiment.independence),
        "regime_policy": _regime_to_dict(experiment.regime_policy),
        "walk_forward_plan_fingerprint": experiment.walk_forward_plan.fingerprint,
        "registration_fingerprint": experiment.registration_fingerprint,
    }
    return _hash(payload)


def compiled_campaign_fingerprint(campaign: CompiledCampaign) -> str:
    """Deterministic fingerprint for a compiled campaign.

    Excludes: ``compile_timestamp`` (timestamp), ``reason_codes``
    are included; but ``generated_at`` timestamps are excluded.
    """
    payload: dict[str, Any] = {
        "campaign_definition_fingerprint": campaign.campaign.fingerprint,
        "experiments": tuple(
            compiled_experiment_fingerprint(e) for e in campaign.experiments
        ),
        "experiment_count": campaign.experiment_count,
        "excluded_count": campaign.excluded_count,
        "reason_codes": campaign.reason_codes,
    }
    return _hash(payload)


def experiment_id_from_components(
    campaign_id: str,
    strategy_name: str,
    timeframe: str,
    data_id: str,
    universe_plan_id: str,
    template_id: str,
    config_id: str,
    experiment_family_id: str,
    hypothesis_family_id: str,
    metric_names: tuple[str, ...],
    independence_class: str,
    regime_label: str,
    strategy_fingerprint: str,
    historical_data_fingerprint: str,
    universe_plan_fingerprint: str,
    walk_forward_template_fingerprint: str,
    confidence_config_fingerprint: str,
    experiment_family_fingerprint: str,
    hypothesis_family_fingerprint: str,
) -> str:
    """Deterministic experiment ID derived from canonical components.

    Returns a hex prefix (first 16 characters) suitable as an
    ``experiment_id``.
    """
    payload: dict[str, Any] = {
        "campaign_id": campaign_id,
        "strategy_name": strategy_name,
        "timeframe": timeframe,
        "data_id": data_id,
        "universe_plan_id": universe_plan_id,
        "template_id": template_id,
        "config_id": config_id,
        "experiment_family_id": experiment_family_id,
        "hypothesis_family_id": hypothesis_family_id,
        "metric_names": metric_names,
        "independence_class": independence_class,
        "regime_label": regime_label,
        "strategy_fingerprint": strategy_fingerprint,
        "historical_data_fingerprint": historical_data_fingerprint,
        "universe_plan_fingerprint": universe_plan_fingerprint,
        "walk_forward_template_fingerprint": walk_forward_template_fingerprint,
        "confidence_config_fingerprint": confidence_config_fingerprint,
        "experiment_family_fingerprint": experiment_family_fingerprint,
        "hypothesis_family_fingerprint": hypothesis_family_fingerprint,
    }
    return _hash(payload)[:_FINGERPRINT_EXPERIMENT_ID_PREFIX_LEN]


def registration_set_fingerprint(registration_set: CampaignRegistrationSet) -> str:
    """Deterministic fingerprint for a campaign registration set."""
    payload: dict[str, Any] = {
        "campaign_fingerprint": registration_set.campaign.fingerprint,
        "registrations": tuple(
            r.fingerprint for r in registration_set.registrations
        ),
        "registration_by_experiment_id_fingerprints": {
            eid: reg.fingerprint
            for eid, reg in registration_set.registration_by_experiment_id.items()
        },
    }
    return _hash(payload)


def execution_manifest_fingerprint(manifest: CampaignExecutionManifest) -> str:
    """Deterministic fingerprint for a campaign execution manifest.

    Excludes: ``created_at`` (timestamp).
    """
    payload: dict[str, Any] = {
        "campaign_definition_fingerprint": manifest.campaign_definition.fingerprint,
        "compiled_campaign_fingerprint": manifest.compiled_campaign.fingerprint,
        "registration_set_fingerprint": manifest.registration_set.fingerprint,
        "reason_codes": manifest.reason_codes,
    }
    return _hash(payload)


def experiment_execution_record_fingerprint(record: ExperimentExecutionRecord) -> str:
    """Deterministic fingerprint for an experiment execution record.

    Excludes: ``started_at``, ``completed_at`` (timestamps), ``notes``.
    """
    payload: dict[str, Any] = {
        "experiment_id": record.experiment_id,
        "campaign_id": record.campaign_id,
        "experiment_fingerprint": record.experiment_fingerprint,
        "registration_fingerprint": record.registration_fingerprint,
        "outcome": record.outcome.value,
        "evidence": _experiment_evidence_to_dict(record.evidence),
        "reason_codes": record.reason_codes,
    }
    return _hash(payload)


def campaign_resume_manifest_fingerprint(manifest: CampaignResumeManifest) -> str:
    """Deterministic fingerprint for a campaign resume manifest.

    Excludes: ``created_at`` (timestamp).
    """
    prior_list: list[dict[str, Any]] = []
    for prior in manifest.prior_evidence:
        prior_list.append({
            "experiment_id": prior.experiment_id,
            "experiment_fingerprint": prior.experiment_fingerprint,
            "registration_fingerprint": prior.registration_fingerprint,
            "strategy_reference_fingerprint": prior.strategy_reference_fingerprint,
            "historical_data_reference_fingerprint": prior.historical_data_reference_fingerprint,
            "universe_plan_reference_fingerprint": prior.universe_plan_reference_fingerprint,
            "walk_forward_template_reference_fingerprint": prior.walk_forward_template_reference_fingerprint,
            "confidence_config_reference_fingerprint": prior.confidence_config_reference_fingerprint,
            "walk_forward_report_fingerprint": prior.walk_forward_report_fingerprint,
            "confidence_report_fingerprint": prior.confidence_report_fingerprint,
            "ledger_entry_fingerprint": prior.ledger_entry_fingerprint,
            "ledger_snapshot_fingerprint": prior.ledger_snapshot_fingerprint,
            "inherited_safety_invariants": _safety_flags_to_dict(prior.inherited_safety_invariants),
            "outcome": prior.outcome.value,
        })

    payload: dict[str, Any] = {
        "campaign_fingerprint": manifest.campaign_fingerprint,
        "prior_evidence": prior_list,
        "resume_policy": manifest.resume_policy.value,
        "reason_codes": manifest.reason_codes,
    }
    return _hash(payload)


def checkpoint_fingerprint(checkpoint: CampaignCheckpoint) -> str:
    """Deterministic fingerprint for a campaign checkpoint.

    Excludes: ``created_at`` (timestamp).
    """
    payload: dict[str, Any] = {
        "checkpoint_id": checkpoint.checkpoint_id,
        "campaign_id": checkpoint.campaign_id,
        "checkpoint_index": checkpoint.checkpoint_index,
        "previous_checkpoint_fingerprint": checkpoint.previous_checkpoint_fingerprint,
        "experiment_records": tuple(
            experiment_execution_record_fingerprint(r)
            for r in checkpoint.experiment_records
        ),
        "status": checkpoint.status.value,
        "reason_codes": checkpoint.reason_codes,
    }
    return _hash(payload)


def status_summary_fingerprint(summary: CampaignStatusSummary) -> str:
    """Deterministic fingerprint for a status summary."""
    payload: dict[str, Any] = {
        "total": summary.total,
        "completed": summary.completed,
        "failed": summary.failed,
        "blocked": summary.blocked,
        "timed_out": summary.timed_out,
        "unsupported": summary.unsupported,
        "insufficient_evidence": summary.insufficient_evidence,
        "withdrawn": summary.withdrawn,
        "skipped_by_policy": summary.skipped_by_policy,
        "stale_resume_evidence": summary.stale_resume_evidence,
    }
    return _hash(payload)


def evidence_summary_fingerprint(summary: CampaignEvidenceSummary) -> str:
    """Deterministic fingerprint for an evidence summary."""
    payload: dict[str, Any] = {
        "walk_forward_attempted": summary.walk_forward_attempted,
        "walk_forward_completed": summary.walk_forward_completed,
        "confidence_attempted": summary.confidence_attempted,
        "confidence_completed": summary.confidence_completed,
        "ledger_entries": summary.ledger_entries,
        "ledger_snapshots": summary.ledger_snapshots,
    }
    return _hash(payload)


def campaign_dossier_fingerprint(dossier: CampaignDossier) -> str:
    """Deterministic fingerprint for a campaign dossier.

    Excludes: ``generated_at`` (timestamp).
    """
    payload: dict[str, Any] = {
        "campaign_id": dossier.campaign_id,
        "campaign_fingerprint": dossier.campaign_fingerprint,
        "compiled_campaign_fingerprint": dossier.compiled_campaign_fingerprint,
        "status_summary_fingerprint": status_summary_fingerprint(dossier.status_summary),
        "evidence_summary_fingerprint": evidence_summary_fingerprint(dossier.evidence_summary),
        "execution_records": tuple(
            experiment_execution_record_fingerprint(r)
            for r in dossier.execution_records
        ),
        "safety_flags": _safety_flags_to_dict(dossier.safety_flags),
        "reason_codes": dossier.reason_codes,
    }
    return _hash(payload)


def artifact_manifest_fingerprint(manifest: CampaignArtifactManifest) -> str:
    """Deterministic fingerprint for an artifact manifest.

    Excludes: ``generated_at`` (timestamp).  ``artifact_paths``
    (paths) are excluded per spec — only the dossier fingerprint
    and campaign_id are hashed.
    """
    payload: dict[str, Any] = {
        "campaign_id": manifest.campaign_id,
        "dossier_fingerprint": manifest.dossier_fingerprint,
    }
    return _hash(payload)
