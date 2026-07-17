"""Public API for the walk-forward statistical confidence package (MVP-67 / SPEC-068)."""

from __future__ import annotations

from hunter.research_statistical_confidence.engine import (
    run_statistical_confidence,
)
from hunter.research_statistical_confidence.errors import (
    StatisticalConfidenceError,
    StatisticalConfidenceSafetyError,
    StatisticalConfidenceValidationError,
    StatisticalConfidenceWriterError,
)
from hunter.research_statistical_confidence.models import (
    SPEC_VERSION,
    STATISTICAL_CONFIDENCE_VERSION,
    UNAVAILABLE,
    BootstrapConfig,
    BootstrapInterval,
    ConfidenceState,
    ExperimentConfidenceReport,
    LeaveOneOutResult,
    MetricConfidenceResult,
    RegimeConfidenceResult,
    RobustnessCriteria,
    StatisticalConfidenceConfig,
    StatisticalConfidenceManifest,
    StatisticalConfidenceSafetyFlags,
)
from hunter.research_statistical_confidence.writer import (
    StatisticalConfidenceWriter,
    write_all_statistical_confidence_artifacts,
    write_experiment_confidence_report,
)

__all__ = [
    "STATISTICAL_CONFIDENCE_VERSION",
    "SPEC_VERSION",
    "UNAVAILABLE",
    "ConfidenceState",
    "BootstrapConfig",
    "RobustnessCriteria",
    "StatisticalConfidenceConfig",
    "BootstrapInterval",
    "LeaveOneOutResult",
    "MetricConfidenceResult",
    "RegimeConfidenceResult",
    "StatisticalConfidenceSafetyFlags",
    "StatisticalConfidenceManifest",
    "ExperimentConfidenceReport",
    "StatisticalConfidenceError",
    "StatisticalConfidenceValidationError",
    "StatisticalConfidenceSafetyError",
    "StatisticalConfidenceWriterError",
    "run_statistical_confidence",
    "StatisticalConfidenceWriter",
    "write_experiment_confidence_report",
    "write_all_statistical_confidence_artifacts",
]
