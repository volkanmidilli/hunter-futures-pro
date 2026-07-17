"""Drift detection for the research evidence ledger (MVP-68 / SPEC-069)."""

from __future__ import annotations

from hunter.research_evidence_ledger.models import (
    DRIFT_DETECTED,
    DRIFT_IN_CONFIDENCE_CONFIG,
    DRIFT_IN_DIRECTION_POLICY,
    DRIFT_IN_METRIC_FAMILY,
    DRIFT_IN_REGIME_POLICY,
    DRIFT_IN_STRATEGY,
    DRIFT_IN_TIMEFRAME,
    DRIFT_IN_UNIVERSE_PLAN,
    DRIFT_IN_WALK_FORWARD_PLAN,
    EvidenceLedgerDriftError,
    ExperimentRegistration,
)


class DriftDetector:
    """Detect plan drift across experiment registrations.

    Tracks the first-seen registration for each experiment family and
    detects when a subsequent registration differs in key fields.
    """

    def __init__(self) -> None:
        # First-seen baseline per family
        self._baselines: dict[str, ExperimentRegistration] = {}

    def _get_family_key(self, registration: ExperimentRegistration) -> str:
        """Derive the experiment family key from the registration."""
        return registration.experiment_family_id or registration.strategy_name

    def check_drift(self, registration: ExperimentRegistration) -> None:
        """Check for drift against the family baseline.

        Raises EvidenceLedgerDriftError if drift is detected.
        """
        key = self._get_family_key(registration)
        if key not in self._baselines:
            return  # First registration in family — no drift possible

        baseline = self._baselines[key]

        issues: list[str] = []

        if registration.strategy_name != baseline.strategy_name:
            issues.append(DRIFT_IN_STRATEGY)
        if registration.universe_plan != baseline.universe_plan:
            issues.append(DRIFT_IN_UNIVERSE_PLAN)
        if registration.timeframe != baseline.timeframe:
            issues.append(DRIFT_IN_TIMEFRAME)
        if registration.walk_forward_plan_fingerprint != baseline.walk_forward_plan_fingerprint:
            issues.append(DRIFT_IN_WALK_FORWARD_PLAN)
        if registration.metric_family != baseline.metric_family:
            issues.append(DRIFT_IN_METRIC_FAMILY)
        if registration.confidence_config_fingerprint != baseline.confidence_config_fingerprint:
            issues.append(DRIFT_IN_CONFIDENCE_CONFIG)
        if registration.regime_policy != baseline.regime_policy:
            issues.append(DRIFT_IN_REGIME_POLICY)
        if registration.direction_policy != baseline.direction_policy:
            issues.append(DRIFT_IN_DIRECTION_POLICY)

        if issues:
            raise EvidenceLedgerDriftError(
                f"Drift detected for family {key}: {', '.join(issues)}",
                reason_code=DRIFT_DETECTED,
            )

    def set_baseline(self, registration: ExperimentRegistration) -> None:
        """Set or update the baseline for a family."""
        key = self._get_family_key(registration)
        if key not in self._baselines:
            self._baselines[key] = registration
