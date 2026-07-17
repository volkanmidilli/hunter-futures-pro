"""Public API for the walk-forward universe comparison harness (MVP-66 / SPEC-067)."""

from __future__ import annotations

from hunter.research_walk_forward.engine import (
    build_walk_forward_report,
    run_walk_forward_experiment,
)
from hunter.research_walk_forward.errors import (
    WalkForwardConfigError,
    WalkForwardError,
    WalkForwardLeakageError,
    WalkForwardRunnerError,
    WalkForwardSafetyError,
    WalkForwardValidationError,
    WalkForwardWriterError,
)
from hunter.research_walk_forward.models import (
    SPEC_VERSION,
    UNAVAILABLE,
    WALK_FORWARD_VERSION,
    ConsistencyState,
    ExperimentExecutionPolicy,
    MarketRegimeLabel,
    MetricAggregate,
    MetricDirection,
    RegimeAggregate,
    WalkForwardCommonConfig,
    WalkForwardExperimentPlan,
    WalkForwardExperimentReport,
    WalkForwardManifest,
    WalkForwardMode,
    WalkForwardSafetyFlags,
    WalkForwardWindow,
    WalkForwardWindowResult,
    WindowStatus,
)
from hunter.research_walk_forward.writer import (
    WalkForwardWriter,
    write_all_walk_forward_artifacts,
    write_walk_forward_report,
)

__all__ = [
    "WALK_FORWARD_VERSION",
    "SPEC_VERSION",
    "UNAVAILABLE",
    "WalkForwardMode",
    "WalkForwardCommonConfig",
    "WalkForwardWindow",
    "WalkForwardExperimentPlan",
    "WalkForwardWindowResult",
    "MetricAggregate",
    "RegimeAggregate",
    "WalkForwardManifest",
    "WalkForwardExperimentReport",
    "WalkForwardSafetyFlags",
    "ExperimentExecutionPolicy",
    "MarketRegimeLabel",
    "ConsistencyState",
    "MetricDirection",
    "WindowStatus",
    "WalkForwardError",
    "WalkForwardConfigError",
    "WalkForwardValidationError",
    "WalkForwardLeakageError",
    "WalkForwardRunnerError",
    "WalkForwardWriterError",
    "WalkForwardSafetyError",
    "run_walk_forward_experiment",
    "build_walk_forward_report",
    "WalkForwardWriter",
    "write_walk_forward_report",
    "write_all_walk_forward_artifacts",
]
