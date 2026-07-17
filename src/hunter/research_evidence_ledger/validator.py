"""Input validation for the research evidence ledger (MVP-68 / SPEC-069)."""

from __future__ import annotations

from hunter.research_evidence_ledger.models import (
    EvidenceLedgerRegistrationError,
    EvidenceLedgerSafetyError,
    EvidenceLedgerSafetyFlags,
    EvidenceLedgerValidationError,
    ExperimentRegistration,
)


def validate_registration(registration: ExperimentRegistration) -> None:
    """Validate an experiment registration for internal consistency.

    Raises EvidenceLedgerValidationError or EvidenceLedgerRegistrationError
    if the registration is invalid.
    """
    if not isinstance(registration, ExperimentRegistration):
        raise EvidenceLedgerRegistrationError(
            "registration must be an ExperimentRegistration",
            reason_code="INVALID_REGISTRATION",
        )
    # experiment_id already validated in __post_init__
    # Check for non-empty hypothesis
    if not registration.hypothesis.strip():
        raise EvidenceLedgerRegistrationError(
            "hypothesis must be non-empty",
            reason_code="INVALID_REGISTRATION",
        )
    # Check metric family
    if not registration.metric_family:
        raise EvidenceLedgerRegistrationError(
            "metric_family must not be empty",
            reason_code="INVALID_REGISTRATION",
        )
    for m in registration.metric_family:
        if not isinstance(m, str) or not m.strip():
            raise EvidenceLedgerRegistrationError(
                f"invalid metric name in metric_family: {m!r}",
                reason_code="INVALID_REGISTRATION",
            )


def validate_safety_flags(flags: EvidenceLedgerSafetyFlags) -> None:
    """Validate safety flags enforce research-only constraints."""
    if not isinstance(flags, EvidenceLedgerSafetyFlags):
        raise EvidenceLedgerSafetyError(
            "flags must be an EvidenceLedgerSafetyFlags instance",
            reason_code="INHERITED_SAFETY_VIOLATION",
        )
    if not flags.research_only:
        raise EvidenceLedgerSafetyError(
            "research_only must be True",
            reason_code="INHERITED_SAFETY_VIOLATION",
        )
    if flags.execution_approval_granted:
        raise EvidenceLedgerSafetyError(
            "execution_approval_granted must be False",
            reason_code="INHERITED_SAFETY_VIOLATION",
        )
    if flags.production_approval_granted:
        raise EvidenceLedgerSafetyError(
            "production_approval_granted must be False",
            reason_code="INHERITED_SAFETY_VIOLATION",
        )
    if flags.live_trading_allowed:
        raise EvidenceLedgerSafetyError(
            "live_trading_allowed must be False",
            reason_code="INHERITED_SAFETY_VIOLATION",
        )
    if flags.automatic_execution_allowed:
        raise EvidenceLedgerSafetyError(
            "automatic_execution_allowed must be False",
            reason_code="INHERITED_SAFETY_VIOLATION",
        )
    if not flags.human_approval_required:
        raise EvidenceLedgerSafetyError(
            "human_approval_required must be True",
            reason_code="INHERITED_SAFETY_VIOLATION",
        )


def validate_raw_value(value: float | str | None) -> None:
    """Validate a raw evidence value is in [0, 1] when present.

    Raises EvidenceLedgerValidationError if the value is outside [0, 1].
    None values are allowed (unavailable evidence).
    """
    if value is None:
        return
    from decimal import Decimal
    v = Decimal(str(value))
    if v < Decimal("0") or v > Decimal("1"):
        raise EvidenceLedgerValidationError(
            f"raw evidence value must be in [0, 1], got {v}",
            reason_code="ADJUSTMENT_INVALID_INPUT",
        )
