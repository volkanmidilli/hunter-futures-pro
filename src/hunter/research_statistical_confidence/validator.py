"""Config and source report validation for the statistical confidence package (MVP-67 / SPEC-068)."""

from __future__ import annotations

from decimal import Decimal

from hunter.research_statistical_confidence.models import (
    INVALID_CONFIG,
    INSUFFICIENT_DATA,
    MISSING_SOURCE_FINGERPRINT,
    INHERITED_SAFETY_VIOLATION,
    BootstrapConfig,
    RobustnessCriteria,
    StatisticalConfidenceConfig,
    StatisticalConfidenceSafetyError,
    StatisticalConfidenceValidationError,
)
from hunter.research_walk_forward.models import (
    WalkForwardExperimentReport,
)


def validate_config(config: StatisticalConfidenceConfig | None) -> None:
    """Validate the statistical confidence configuration.

    Raises:
        StatisticalConfidenceValidationError: If any config field is invalid.
    """
    if config is None:
        raise StatisticalConfidenceValidationError(
            "config is required", reason_code=INVALID_CONFIG
        )
    if not isinstance(config, StatisticalConfidenceConfig):
        raise StatisticalConfidenceValidationError(
            f"config must be a StatisticalConfidenceConfig, got {config!r}",
            reason_code=INVALID_CONFIG,
        )

    if config.minimum_available_window_count < 2:
        raise StatisticalConfidenceValidationError(
            f"minimum_available_window_count must be >= 2, got {config.minimum_available_window_count}",
            reason_code=INVALID_CONFIG,
        )

    cl = config.confidence_level
    if cl is None or cl <= Decimal("0") or cl >= Decimal("1"):
        raise StatisticalConfidenceValidationError(
            f"confidence_level must satisfy 0 < confidence_level < 1, got {cl}",
            reason_code=INVALID_CONFIG,
        )

    bootstrap = config.bootstrap
    if not isinstance(bootstrap, BootstrapConfig):
        raise StatisticalConfidenceValidationError(
            "bootstrap must be a BootstrapConfig", reason_code=INVALID_CONFIG
        )
    if not isinstance(bootstrap.seed, int):
        raise StatisticalConfidenceValidationError(
            "bootstrap.seed must be an integer", reason_code=INVALID_CONFIG
        )
    if bootstrap.iterations < 100:
        raise StatisticalConfidenceValidationError(
            f"bootstrap.iterations must be >= 100, got {bootstrap.iterations}",
            reason_code=INVALID_CONFIG,
        )

    robustness = config.robustness
    if not isinstance(robustness, RobustnessCriteria):
        raise StatisticalConfidenceValidationError(
            "robustness must be a RobustnessCriteria", reason_code=INVALID_CONFIG
        )

    sst = robustness.sign_share_threshold
    if sst is None or sst < Decimal("0.5") or sst > Decimal("1"):
        raise StatisticalConfidenceValidationError(
            f"sign_share_threshold must satisfy 0.5 <= sign_share_threshold <= 1, got {sst}",
            reason_code=INVALID_CONFIG,
        )

    mir = robustness.maximum_influence_ratio
    if mir is None or mir < Decimal("0") or mir > Decimal("1"):
        raise StatisticalConfidenceValidationError(
            f"maximum_influence_ratio must satisfy 0 <= maximum_influence_ratio <= 1, got {mir}",
            reason_code=INVALID_CONFIG,
        )

    rcl = robustness.confidence_level
    if rcl is None or rcl <= Decimal("0") or rcl >= Decimal("1"):
        raise StatisticalConfidenceValidationError(
            f"robustness.confidence_level must satisfy 0 < confidence_level < 1, got {rcl}",
            reason_code=INVALID_CONFIG,
        )


def validate_source_report(report: WalkForwardExperimentReport | None) -> None:
    """Validate the source walk-forward experiment report.

    Checks that the report is a valid WalkForwardExperimentReport with
    the required safety invariants.

    Raises:
        StatisticalConfidenceValidationError: If the report is invalid.
        StatisticalConfidenceSafetyError: If safety invariants are violated.
    """
    if report is None:
        raise StatisticalConfidenceValidationError(
            "source report is required", reason_code=MISSING_SOURCE_FINGERPRINT
        )
    if not isinstance(report, WalkForwardExperimentReport):
        raise StatisticalConfidenceValidationError(
            f"source must be a WalkForwardExperimentReport, got {report!r}",
            reason_code=MISSING_SOURCE_FINGERPRINT,
        )
    if not report.fingerprint or not report.fingerprint.strip():
        raise StatisticalConfidenceValidationError(
            "source report must have a non-empty fingerprint",
            reason_code=MISSING_SOURCE_FINGERPRINT,
        )

    # Validate inherited safety invariants
    flags = report.safety_flags
    violations: list[str] = []
    if not flags.research_only:
        violations.append("research_only must be True")
    if flags.execution_approval_granted:
        violations.append("execution_approval_granted must be False")
    if flags.production_approval_granted:
        violations.append("production_approval_granted must be False")
    if flags.live_trading_allowed:
        violations.append("live_trading_allowed must be False")
    if flags.automatic_execution_allowed:
        violations.append("automatic_execution_allowed must be False")
    if not flags.human_approval_required:
        violations.append("human_approval_required must be True")
    if not flags.no_direct_subprocess:
        violations.append("no_direct_subprocess must be True")
    if not flags.no_parallel_execution:
        violations.append("no_parallel_execution must be True")
    if violations:
        raise StatisticalConfidenceSafetyError(
            f"Source report safety invariant violation: {'; '.join(violations)}",
            reason_code=INHERITED_SAFETY_VIOLATION,
        )

    # Also check top-level report booleans
    if not report.research_only:
        raise StatisticalConfidenceSafetyError(
            "Source report must have research_only=True",
            reason_code=INHERITED_SAFETY_VIOLATION,
        )
    if not report.human_approval_required:
        raise StatisticalConfidenceSafetyError(
            "Source report must have human_approval_required=True",
            reason_code=INHERITED_SAFETY_VIOLATION,
        )

    # Check that there are window results
    if not report.window_results:
        raise StatisticalConfidenceValidationError(
            "Source report must contain at least one window result",
            reason_code=INSUFFICIENT_DATA,
        )
