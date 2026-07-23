"""Errors for the SPEC-076 outcome-evaluation pipeline."""


class OutcomeEvaluationError(Exception):
    """Base error for the research outcome-evaluation pipeline."""


class SnapshotValidationError(OutcomeEvaluationError):
    """Immutable JSON snapshot audit artifact failed structural validation."""


class PriceSourceError(OutcomeEvaluationError):
    """Fatal Feather price-source failure (e.g. missing data-dir)."""


class EvaluationStoreError(OutcomeEvaluationError):
    """Append-only store failure (conflicting existing content, I/O error)."""
