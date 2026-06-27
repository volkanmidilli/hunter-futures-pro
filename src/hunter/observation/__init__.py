"""Public API exports for MVP-10 observation package."""

from hunter.observation.engine import (
    build_observation_report,
    build_observation_safety_flags,
    build_observation_window,
    build_signal_observation,
    has_unsafe_metadata,
)
from hunter.observation.models import (
    DEFAULT_BLOCKED,
    DRY_RUN_DISABLED,
    EMPTY_OBSERVATION_WINDOW,
    FORBIDDEN_METADATA_KEYS,
    INVALID_INPUT,
    LEVERAGE_ENABLED,
    LIVE_TRADING_ENABLED,
    MISSING_INPUT,
    OBSERVATION_ERROR,
    REAL_ORDERS_ENABLED,
    REPORT_GENERATION_BLOCKED,
    REASON_CODES,
    SHORTING_ENABLED,
    UNSAFE_METADATA,
    UNSUPPORTED_INPUT_VERSION,
    ObservationConfig,
    ObservationDataQuality,
    ObservationReport,
    ObservationSafetyFlags,
    ObservationSignal,
    ObservationState,
    ObservationWindow,
    ReportFormat,
    SignalObservation,
)
from hunter.observation.writer import (
    DEFAULT_OBSERVATION_JSON_REPORT_PATH,
    DEFAULT_OBSERVATION_MARKDOWN_REPORT_PATH,
    atomic_write_json_report,
    atomic_write_markdown_report,
    observation_report_to_dict,
    observation_report_to_markdown,
    write_observation_reports,
)

__all__ = [
    # Enums
    "ObservationState",
    "ObservationSignal",
    "ReportFormat",
    # Models
    "ObservationConfig",
    "ObservationDataQuality",
    "ObservationReport",
    "ObservationSafetyFlags",
    "ObservationWindow",
    "SignalObservation",
    # Engine functions
    "build_signal_observation",
    "build_observation_window",
    "build_observation_report",
    "build_observation_safety_flags",
    "has_unsafe_metadata",
    # Writer functions
    "observation_report_to_dict",
    "observation_report_to_markdown",
    "atomic_write_json_report",
    "atomic_write_markdown_report",
    "write_observation_reports",
    # Writer constants
    "DEFAULT_OBSERVATION_JSON_REPORT_PATH",
    "DEFAULT_OBSERVATION_MARKDOWN_REPORT_PATH",
    # Constants
    "REASON_CODES",
    "FORBIDDEN_METADATA_KEYS",
    "MISSING_INPUT",
    "INVALID_INPUT",
    "UNSUPPORTED_INPUT_VERSION",
    "DRY_RUN_DISABLED",
    "LIVE_TRADING_ENABLED",
    "REAL_ORDERS_ENABLED",
    "LEVERAGE_ENABLED",
    "SHORTING_ENABLED",
    "EMPTY_OBSERVATION_WINDOW",
    "UNSAFE_METADATA",
    "REPORT_GENERATION_BLOCKED",
    "OBSERVATION_ERROR",
    "DEFAULT_BLOCKED",
]
