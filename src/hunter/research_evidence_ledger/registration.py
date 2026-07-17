"""Experiment registration for the research evidence ledger (MVP-68 / SPEC-069)."""

from __future__ import annotations

from hunter.research_evidence_ledger.fingerprint import registration_fingerprint
from hunter.research_evidence_ledger.models import (
    EvidenceLedgerRegistrationError,
    EvidenceLedgerSafetyFlags,
    ExperimentRegistration,
    ExperimentStatus,
    IndependenceClass,
)
from hunter.research_evidence_ledger.validator import (
    validate_registration,
    validate_safety_flags,
)


def create_registration(
    experiment_id: str,
    hypothesis: str,
    strategy_name: str,
    universe_plan: str,
    timeframe: str,
    walk_forward_plan_fingerprint: str,
    metric_family: tuple[str, ...],
    independence: IndependenceClass = IndependenceClass.UNKNOWN,
    hypothesis_family_id: str = "",
    experiment_family_id: str = "",
    confidence_config_fingerprint: str = "",
    regime_policy: str = "",
    direction_policy: str = "",
    notes: str = "",
    safety_flags: EvidenceLedgerSafetyFlags | None = None,
) -> ExperimentRegistration:
    """Create a new experiment registration with a deterministic fingerprint."""
    if safety_flags is None:
        safety_flags = EvidenceLedgerSafetyFlags()
    validate_safety_flags(safety_flags)

    reg = ExperimentRegistration(
        experiment_id=experiment_id,
        hypothesis=hypothesis,
        strategy_name=strategy_name,
        universe_plan=universe_plan,
        timeframe=timeframe,
        walk_forward_plan_fingerprint=walk_forward_plan_fingerprint,
        metric_family=metric_family,
        independence=independence,
        status=ExperimentStatus.REGISTERED,
        hypothesis_family_id=hypothesis_family_id,
        experiment_family_id=experiment_family_id,
        confidence_config_fingerprint=confidence_config_fingerprint,
        regime_policy=regime_policy,
        direction_policy=direction_policy,
        notes=notes,
        safety_flags=safety_flags,
    )

    # Compute fingerprint (before validation so fingerprint is set)
    fp = registration_fingerprint(reg)
    object.__setattr__(reg, "fingerprint", fp)

    validate_registration(reg)
    return reg


def update_registration_status(
    registration: ExperimentRegistration,
    new_status: ExperimentStatus,
) -> ExperimentRegistration:
    """Return a new registration with an updated status.

    The caller must ensure the original registration is not mutated.
    Returns a new ExperimentRegistration with the updated status
    and a new fingerprint.
    """
    kwargs = dict(registration.__dict__)
    kwargs["status"] = new_status
    # Reconstruct with new status
    new_reg = ExperimentRegistration(**kwargs)
    fp = registration_fingerprint(new_reg)
    object.__setattr__(new_reg, "fingerprint", fp)
    return new_reg
