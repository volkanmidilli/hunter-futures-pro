"""Observation engine for MVP-10 Dry-Run Research Observation & Reports.

Builds SignalObservation and ObservationReport from MVP-9 shell metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hunter.observation.models import (
    DEFAULT_BLOCKED,
    DRY_RUN_DISABLED,
    EMPTY_OBSERVATION_WINDOW,
    INVALID_INPUT,
    LEVERAGE_ENABLED,
    LIVE_TRADING_ENABLED,
    MISSING_INPUT,
    OBSERVATION_ERROR,
    REAL_ORDERS_ENABLED,
    REPORT_GENERATION_BLOCKED,
    SHORTING_ENABLED,
    UNSAFE_METADATA,
    UNSUPPORTED_INPUT_VERSION,
    FORBIDDEN_METADATA_KEYS,
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


# ---------------------------------------------------------------------------
# Engine functions
# ---------------------------------------------------------------------------


def build_signal_observation(
    shell_metadata: dict[str, object] | None,
    config: ObservationConfig | None = None,
    now: datetime | None = None,
) -> SignalObservation:
    """Build a SignalObservation from MVP-9 shell metadata.

    Fail-closed: returns BLOCKED observation on any validation failure.
    Does not repair, infer, upgrade, or feed output back to execution paths.
    """
    if config is None:
        config = ObservationConfig()
    if now is None:
        now = datetime.now(timezone.utc)

    try:
        # Priority 1: None input
        if shell_metadata is None:
            return SignalObservation.blocked((MISSING_INPUT,), now)

        # Priority 2: Validate input is a dict with required fields
        if not isinstance(shell_metadata, dict):
            return SignalObservation.blocked((INVALID_INPUT,), now)

        required_fields = {
            "shell_state",
            "signal_exposure",
            "reason_codes",
            "hunter_research_signal",
            "hunter_research_reason",
            "hunter_shell_state",
            "hunter_signal_exposure",
        }
        if not required_fields.issubset(shell_metadata.keys()):
            return SignalObservation.blocked((INVALID_INPUT,), now)

        # Priority 3: Check version
        version = shell_metadata.get("version", "")
        if version != config.input_version:
            return SignalObservation.blocked((UNSUPPORTED_INPUT_VERSION,), now)

        # Priority 4-8: Safety flags (defense-in-depth re-check of MVP-9)
        safety_checks = [
            ("dry_run", True, DRY_RUN_DISABLED),
            ("live_trading_enabled", False, LIVE_TRADING_ENABLED),
            ("real_orders_enabled", False, REAL_ORDERS_ENABLED),
            ("leverage_enabled", False, LEVERAGE_ENABLED),
            ("shorting_enabled", False, SHORTING_ENABLED),
        ]
        for field_name, expected, reason in safety_checks:
            value = shell_metadata.get(field_name)
            if value != expected:
                return SignalObservation.blocked((reason,), now)

        # Check metadata for forbidden keys
        metadata = shell_metadata.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        if has_unsafe_metadata(metadata):
            return SignalObservation.blocked((UNSAFE_METADATA,), now)

        # Determine signal from hunter_research_signal
        hunter_signal = shell_metadata.get("hunter_research_signal", "NONE")
        if hunter_signal == "LONG_RESEARCH":
            signal = ObservationSignal.LONG_RESEARCH
            state = ObservationState.READY
            reason = ("LONG_RESEARCH_OBSERVED",)
        elif hunter_signal == "SHORT_RESEARCH":
            signal = ObservationSignal.SHORT_RESEARCH
            state = ObservationState.READY
            reason = ("SHORT_RESEARCH_OBSERVED",)
        else:
            signal = ObservationSignal.NONE
            state = ObservationState.BLOCKED
            reason = (DEFAULT_BLOCKED,)

        return SignalObservation(
            timestamp=now,
            observation_state=state,
            signal=signal,
            source_shell_state=str(shell_metadata.get("hunter_shell_state", "UNKNOWN")),
            source_signal_exposure=str(shell_metadata.get("hunter_signal_exposure", "BLOCKED")),
            reason_codes=reason,
            metadata=metadata,
            safety_flags=build_observation_safety_flags(config),
            version="1.0",
        )

    except Exception:
        return SignalObservation.blocked((OBSERVATION_ERROR,), now)


def build_observation_window(
    observations: tuple[SignalObservation, ...],
    started_at: datetime,
    ended_at: datetime,
    window_id: str = "default",
) -> ObservationWindow:
    """Build an ObservationWindow from a tuple of SignalObservations."""
    return ObservationWindow(
        started_at=started_at,
        ended_at=ended_at,
        observations=observations,
        window_id=window_id,
    )


def build_observation_report(
    window: ObservationWindow,
    config: ObservationConfig | None = None,
    generated_at: datetime | None = None,
) -> ObservationReport:
    """Build an ObservationReport from an ObservationWindow.

    Fail-closed: empty window or unsafe metadata produces blocked report.
    Reports are human-review artifacts only and must not trigger action.
    """
    if config is None:
        config = ObservationConfig()
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)

    try:
        # Fail-closed: empty window
        if len(window.observations) == 0:
            return ObservationReport.blocked(
                (EMPTY_OBSERVATION_WINDOW,),
                window=window,
                generated_at=generated_at,
            )

        # Check for unsafe metadata in any observation
        for obs in window.observations:
            if has_unsafe_metadata(obs.metadata):
                return ObservationReport.blocked(
                    (UNSAFE_METADATA,),
                    window=window,
                    generated_at=generated_at,
                )

        # Build summary
        long_count = sum(
            1 for obs in window.observations if obs.signal == ObservationSignal.LONG_RESEARCH
        )
        short_count = sum(
            1 for obs in window.observations if obs.signal == ObservationSignal.SHORT_RESEARCH
        )
        none_count = sum(
            1 for obs in window.observations if obs.signal == ObservationSignal.NONE
        )
        blocked_count = sum(
            1
            for obs in window.observations
            if obs.observation_state == ObservationState.BLOCKED
        )
        unknown_count = sum(
            1
            for obs in window.observations
            if obs.observation_state == ObservationState.UNKNOWN
        )

        # Reason frequency
        reason_counts: dict[str, int] = {}
        for obs in window.observations:
            for reason in obs.reason_codes:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

        summary = {
            "total_observations": len(window.observations),
            "long_research_count": long_count,
            "short_research_count": short_count,
            "none_count": none_count,
            "blocked_count": blocked_count,
            "unknown_count": unknown_count,
            "reason_counts": reason_counts,
        }

        # Determine report state
        all_ready = all(
            obs.observation_state == ObservationState.READY for obs in window.observations
        )
        report_state = ObservationState.READY if all_ready else ObservationState.BLOCKED

        # Data quality
        data_quality = ObservationDataQuality(
            input_present=True,
            input_valid=all_ready,
            input_version_supported=all_ready,
            observation_count=len(window.observations),
            blocked_count=blocked_count,
            unknown_count=unknown_count,
            reason="VALID" if all_ready else "BLOCKED_OBSERVATIONS_PRESENT",
        )

        # Report formats from config
        formats: list[ObservationReport] = []
        if config.allow_json_report:
            formats.append(ReportFormat.JSON)
        if config.allow_markdown_report:
            formats.append(ReportFormat.MARKDOWN)
        if not formats:
            formats.append(ReportFormat.JSON)

        return ObservationReport(
            generated_at=generated_at,
            report_state=report_state,
            window=window,
            summary=summary,
            data_quality=data_quality,
            safety_flags=build_observation_safety_flags(config),
            report_formats=tuple(formats),
            reason_codes=("REPORT_GENERATED",) if all_ready else (REPORT_GENERATION_BLOCKED,),
            version="1.0",
        )

    except Exception:
        return ObservationReport.blocked(
            (OBSERVATION_ERROR,),
            window=window,
            generated_at=generated_at,
        )


def build_observation_safety_flags(config: ObservationConfig) -> ObservationSafetyFlags:
    """Build safety flags from config."""
    return ObservationSafetyFlags(
        dry_run=True,
        live_trading_enabled=False,
        real_orders_enabled=False,
        leverage_enabled=False,
        shorting_enabled=False,
        execution_feedback_allowed=False,
        network_calls_allowed=False,
        database_persistence_allowed=False,
        realtime_streaming_allowed=False,
        api_keys_allowed=False,
    )


def has_unsafe_metadata(metadata: dict[str, object]) -> bool:
    """Check if metadata contains forbidden keys."""
    if not isinstance(metadata, dict):
        return False
    for key in metadata:
        if key in FORBIDDEN_METADATA_KEYS:
            return True
    return False
