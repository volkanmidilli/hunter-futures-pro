"""Pre-registration record creation for compiled campaigns (MVP-69 / SPEC-070)."""

from __future__ import annotations

from types import MappingProxyType

from hunter.research_campaign.fingerprint import registration_set_fingerprint
from hunter.research_campaign.models import (
    CampaignRegistrationSet,
    CompiledCampaign,
    CompiledExperiment,
)
from hunter.research_evidence_ledger.fingerprint import (
    registration_fingerprint as ledger_registration_fingerprint,
)
from hunter.research_evidence_ledger.models import (
    EvidenceLedgerSafetyFlags,
    ExperimentRegistration,
    ExperimentStatus,
    IndependenceClass,
)
from hunter.research_walk_forward.models import MarketRegimeLabel


def create_campaign_registration_set(
    compiled_campaign: CompiledCampaign,
) -> CampaignRegistrationSet:
    """Create pre-registration records for every experiment in a compiled campaign.

    Parameters
    ----------
    compiled_campaign : CompiledCampaign
        The compiled campaign whose experiments will be registered.

    Returns
    -------
    CampaignRegistrationSet
        Immutable pre-registration set with fingerprints.
    """
    registrations: list[ExperimentRegistration] = []

    for compiled_exp in compiled_campaign.experiments:
        # Build hypothesis string: "{campaign_id}:{experiment_id}"
        hypothesis = f"{compiled_exp.campaign_id}:{compiled_exp.experiment_id}"

        # Determine independence class value.
        ind_class = compiled_exp.independence.independence_class
        if isinstance(ind_class, IndependenceClass):
            independence = ind_class
        else:
            independence = IndependenceClass(str(ind_class))

        # Determine regime label string for direction_policy/regime_policy
        # (not directly needed for registration but used for registration fields).
        regime_label = compiled_exp.regime_policy.regime_label
        if isinstance(regime_label, MarketRegimeLabel):
            regime_policy_str = regime_label.value
        else:
            regime_policy_str = str(regime_label)

        # Build the ExperimentRegistration (no fingerprint yet).
        reg = ExperimentRegistration(
            experiment_id=compiled_exp.experiment_id,
            hypothesis=hypothesis,
            strategy_name=compiled_exp.strategy.strategy_name,
            universe_plan=compiled_exp.universe_plan.universe_plan_id,
            timeframe=compiled_exp.timeframe,
            walk_forward_plan_fingerprint=compiled_exp.walk_forward_plan.fingerprint,
            metric_family=compiled_exp.metric_family.metric_names,
            independence=independence,
            status=ExperimentStatus.REGISTERED,
            hypothesis_family_id=compiled_exp.hypothesis_family.family_id,
            experiment_family_id=compiled_exp.experiment_family.family_id,
            confidence_config_fingerprint=compiled_exp.confidence_config.fingerprint,
            regime_policy=regime_policy_str,
            direction_policy=compiled_exp.metric_family.direction_policy,
            notes="",
            safety_flags=EvidenceLedgerSafetyFlags(),
            reason_codes=(),
            metadata={},
        )

        # Compute the registration fingerprint.
        fp = ledger_registration_fingerprint(reg)
        object.__setattr__(reg, "fingerprint", fp)

        # Update the compiled experiment's registration_fingerprint.
        object.__setattr__(
            compiled_exp,
            "registration_fingerprint",
            fp,
        )

        registrations.append(reg)

    # Build registration_by_experiment_id mapping.
    reg_by_id: dict[str, ExperimentRegistration] = {
        r.experiment_id: r for r in registrations
    }

    registration_set = CampaignRegistrationSet(
        campaign=compiled_campaign,
        registrations=tuple(registrations),
        registration_by_experiment_id=MappingProxyType(reg_by_id),
        fingerprint="",
    )

    # Compute registration set fingerprint.
    rs_fp = registration_set_fingerprint(registration_set)
    object.__setattr__(registration_set, "fingerprint", rs_fp)

    return registration_set
