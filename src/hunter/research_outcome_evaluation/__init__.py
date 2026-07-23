"""SPEC-076 -- Ranking Outcome Evaluation and Calibration (Phase A).

Research-only evaluation of immutable JSON snapshot audit artifacts against
local 1h Feather price series.  Phase A is selected-only, descriptive-only
for overlapping cohorts, and never changes weights, parameters, algorithms,
execution behavior, snapshots, Feather data, network sources, or scheduling.
"""

from __future__ import annotations

from hunter.research_outcome_evaluation.engine import (
    CohortEvaluation,
    RunReport,
    run_outcome_evaluation,
)
from hunter.research_outcome_evaluation.errors import (
    EvaluationStoreError,
    OutcomeEvaluationError,
    PriceSourceError,
    SnapshotValidationError,
)
from hunter.research_outcome_evaluation.models import (
    BENCHMARK_BASE_SYMBOL,
    BENCHMARK_PAIR,
    DEFAULT_HORIZONS,
    DEFAULT_MIN_WINDOW_COVERAGE,
    NULL_REASON_CODES,
    OUTCOME_EVALUATION_VERSION,
    PHASE_A_EMITTED_STATES,
    PENDING_HORIZON,
    REASON_FIRST_SNAPSHOT,
    REASON_INSUFFICIENT_OBSERVATIONS,
    REASON_ZERO_DENOMINATOR,
    RESEARCH_NOTICE,
    SPEC_076,
    TOP_N_CUTS,
    OutcomeEvaluationConfig,
    OutcomeEvaluationSafetyFlags,
    PairObservationRecord,
    SnapshotSummaryRecord,
    TerminalState,
    pair_observation_to_dict,
    parse_decimal,
    parse_horizon_hours,
    snapshot_summary_to_dict,
)

from hunter.research_outcome_evaluation.price_source import (
    REQUIRED_OHLCV_COLUMNS,
    Candle,
    PriceSeries,
    build_price_source_map,
    load_price_series,
)
from hunter.research_outcome_evaluation.resolution import (
    PairEvaluation,
    WindowAnchors,
    compute_window_anchors,
    horizon_elapsed,
    resolve_series,
    transient_state,
)
from hunter.research_outcome_evaluation.snapshot_reader import (
    SnapshotCohort,
    SnapshotPairEntry,
    discover_snapshot_audits,
    load_snapshot_audit,
)

__version__ = OUTCOME_EVALUATION_VERSION

__all__ = [
    "BENCHMARK_BASE_SYMBOL",
    "BENCHMARK_PAIR",
    "DEFAULT_HORIZONS",
    "DEFAULT_MIN_WINDOW_COVERAGE",
    "NULL_REASON_CODES",
    "OUTCOME_EVALUATION_VERSION",
    "PHASE_A_EMITTED_STATES",
    "PENDING_HORIZON",
    "REASON_FIRST_SNAPSHOT",
    "REASON_INSUFFICIENT_OBSERVATIONS",
    "REASON_ZERO_DENOMINATOR",
    "RESEARCH_NOTICE",
    "SPEC_076",
    "TOP_N_CUTS",
    "EvaluationStoreError",
    "OutcomeEvaluationConfig",
    "OutcomeEvaluationError",
    "OutcomeEvaluationSafetyFlags",
    "PairObservationRecord",
    "PriceSeries",
    "PriceSourceError",
    "REQUIRED_OHLCV_COLUMNS",
    "Candle",
    "CohortEvaluation",
    "PairEvaluation",
    "RunReport",
    "SnapshotCohort",
    "SnapshotPairEntry",
    "SnapshotSummaryRecord",
    "SnapshotValidationError",
    "TerminalState",
    "WindowAnchors",
    "build_price_source_map",
    "compute_window_anchors",
    "discover_snapshot_audits",
    "horizon_elapsed",
    "load_price_series",
    "load_snapshot_audit",
    "pair_observation_to_dict",
    "parse_decimal",
    "parse_horizon_hours",
    "resolve_series",
    "run_outcome_evaluation",
    "snapshot_summary_to_dict",
    "transient_state",
]
