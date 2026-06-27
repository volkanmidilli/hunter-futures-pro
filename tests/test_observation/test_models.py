"""Tests for observation models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

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


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------

class TestObservationState:
    def test_values(self) -> None:
        assert ObservationState.DISABLED == "DISABLED"
        assert ObservationState.READY == "READY"
        assert ObservationState.BLOCKED == "BLOCKED"
        assert ObservationState.UNKNOWN == "UNKNOWN"

    def test_membership(self) -> None:
        assert "READY" in [s.value for s in ObservationState]


class TestObservationSignal:
    def test_values(self) -> None:
        assert ObservationSignal.LONG_RESEARCH == "LONG_RESEARCH"
        assert ObservationSignal.SHORT_RESEARCH == "SHORT_RESEARCH"
        assert ObservationSignal.NONE == "NONE"


class TestReportFormat:
    def test_values(self) -> None:
        assert ReportFormat.JSON == "JSON"
        assert ReportFormat.MARKDOWN == "MARKDOWN"


# ---------------------------------------------------------------------------
# ObservationConfig tests
# ---------------------------------------------------------------------------

class TestObservationConfig:
    def test_defaults(self) -> None:
        config = ObservationConfig()
        assert config.input_version == "1.0"
        assert config.max_observation_age_seconds == 300
        assert config.allow_json_report is True
        assert config.allow_markdown_report is True
        assert config.allow_execution_feedback is False
        assert config.allow_network_calls is False

    def test_invalid_input_version_empty(self) -> None:
        with pytest.raises(ValueError, match="input_version"):
            ObservationConfig(input_version="")

    def test_invalid_max_age_zero(self) -> None:
        with pytest.raises(ValueError, match="max_observation_age_seconds"):
            ObservationConfig(max_observation_age_seconds=0)

    def test_invalid_max_age_negative(self) -> None:
        with pytest.raises(ValueError, match="max_observation_age_seconds"):
            ObservationConfig(max_observation_age_seconds=-1)

    def test_both_reports_disabled(self) -> None:
        with pytest.raises(ValueError, match="at least one report format"):
            ObservationConfig(allow_json_report=False, allow_markdown_report=False)

    def test_unsafe_execution_feedback(self) -> None:
        with pytest.raises(ValueError, match="allow_execution_feedback"):
            ObservationConfig(allow_execution_feedback=True)

    def test_unsafe_network_calls(self) -> None:
        with pytest.raises(ValueError, match="allow_network_calls"):
            ObservationConfig(allow_network_calls=True)

    def test_unsafe_database_persistence(self) -> None:
        with pytest.raises(ValueError, match="allow_database_persistence"):
            ObservationConfig(allow_database_persistence=True)

    def test_unsafe_realtime_streaming(self) -> None:
        with pytest.raises(ValueError, match="allow_realtime_streaming"):
            ObservationConfig(allow_realtime_streaming=True)

    def test_unsafe_api_keys(self) -> None:
        with pytest.raises(ValueError, match="allow_api_keys"):
            ObservationConfig(allow_api_keys=True)

    def test_unsafe_live_trading(self) -> None:
        with pytest.raises(ValueError, match="allow_live_trading"):
            ObservationConfig(allow_live_trading=True)

    def test_unsafe_real_orders(self) -> None:
        with pytest.raises(ValueError, match="allow_real_orders"):
            ObservationConfig(allow_real_orders=True)

    def test_unsafe_leverage(self) -> None:
        with pytest.raises(ValueError, match="allow_leverage"):
            ObservationConfig(allow_leverage=True)

    def test_unsafe_shorting(self) -> None:
        with pytest.raises(ValueError, match="allow_shorting"):
            ObservationConfig(allow_shorting=True)

    def test_immutable(self) -> None:
        config = ObservationConfig()
        with pytest.raises(AttributeError):
            config.input_version = "2.0"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ObservationSafetyFlags tests
# ---------------------------------------------------------------------------

class TestObservationSafetyFlags:
    def test_defaults(self) -> None:
        flags = ObservationSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.real_orders_enabled is False
        assert flags.leverage_enabled is False
        assert flags.shorting_enabled is False
        assert flags.execution_feedback_allowed is False
        assert flags.network_calls_allowed is False
        assert flags.database_persistence_allowed is False
        assert flags.realtime_streaming_allowed is False
        assert flags.api_keys_allowed is False

    def test_dry_run_false(self) -> None:
        with pytest.raises(ValueError, match="dry_run"):
            ObservationSafetyFlags(dry_run=False)

    def test_live_trading_true(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled"):
            ObservationSafetyFlags(live_trading_enabled=True)

    def test_real_orders_true(self) -> None:
        with pytest.raises(ValueError, match="real_orders_enabled"):
            ObservationSafetyFlags(real_orders_enabled=True)

    def test_leverage_true(self) -> None:
        with pytest.raises(ValueError, match="leverage_enabled"):
            ObservationSafetyFlags(leverage_enabled=True)

    def test_shorting_true(self) -> None:
        with pytest.raises(ValueError, match="shorting_enabled"):
            ObservationSafetyFlags(shorting_enabled=True)

    def test_execution_feedback_true(self) -> None:
        with pytest.raises(ValueError, match="execution_feedback_allowed"):
            ObservationSafetyFlags(execution_feedback_allowed=True)

    def test_network_calls_true(self) -> None:
        with pytest.raises(ValueError, match="network_calls_allowed"):
            ObservationSafetyFlags(network_calls_allowed=True)

    def test_database_persistence_true(self) -> None:
        with pytest.raises(ValueError, match="database_persistence_allowed"):
            ObservationSafetyFlags(database_persistence_allowed=True)

    def test_realtime_streaming_true(self) -> None:
        with pytest.raises(ValueError, match="realtime_streaming_allowed"):
            ObservationSafetyFlags(realtime_streaming_allowed=True)

    def test_api_keys_true(self) -> None:
        with pytest.raises(ValueError, match="api_keys_allowed"):
            ObservationSafetyFlags(api_keys_allowed=True)

    def test_immutable(self) -> None:
        flags = ObservationSafetyFlags()
        with pytest.raises(AttributeError):
            flags.dry_run = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SignalObservation tests
# ---------------------------------------------------------------------------

class TestSignalObservation:
    def test_valid(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        assert obs.timestamp == now
        assert obs.observation_state == ObservationState.READY
        assert obs.signal == ObservationSignal.LONG_RESEARCH

    def test_naive_timestamp(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            SignalObservation(
                timestamp=datetime(2025, 1, 1, 12, 0, 0),
                observation_state=ObservationState.READY,
                signal=ObservationSignal.LONG_RESEARCH,
                source_shell_state="DRY_RUN_READY",
                source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
                reason_codes=("LONG_RESEARCH_OBSERVED",),
            )

    def test_empty_source_shell_state(self) -> None:
        with pytest.raises(ValueError, match="source_shell_state"):
            SignalObservation(
                timestamp=datetime.now(timezone.utc),
                observation_state=ObservationState.READY,
                signal=ObservationSignal.LONG_RESEARCH,
                source_shell_state="",
                source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
                reason_codes=("LONG_RESEARCH_OBSERVED",),
            )

    def test_empty_source_signal_exposure(self) -> None:
        with pytest.raises(ValueError, match="source_signal_exposure"):
            SignalObservation(
                timestamp=datetime.now(timezone.utc),
                observation_state=ObservationState.READY,
                signal=ObservationSignal.LONG_RESEARCH,
                source_shell_state="DRY_RUN_READY",
                source_signal_exposure="",
                reason_codes=("LONG_RESEARCH_OBSERVED",),
            )

    def test_empty_reason_codes(self) -> None:
        with pytest.raises(ValueError, match="reason_codes"):
            SignalObservation(
                timestamp=datetime.now(timezone.utc),
                observation_state=ObservationState.READY,
                signal=ObservationSignal.LONG_RESEARCH,
                source_shell_state="DRY_RUN_READY",
                source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
                reason_codes=(),
            )

    def test_empty_version(self) -> None:
        with pytest.raises(ValueError, match="version"):
            SignalObservation(
                timestamp=datetime.now(timezone.utc),
                observation_state=ObservationState.READY,
                signal=ObservationSignal.LONG_RESEARCH,
                source_shell_state="DRY_RUN_READY",
                source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
                reason_codes=("LONG_RESEARCH_OBSERVED",),
                version="",
            )

    def test_non_ready_with_non_none_signal(self) -> None:
        with pytest.raises(ValueError, match="signal must be NONE"):
            SignalObservation(
                timestamp=datetime.now(timezone.utc),
                observation_state=ObservationState.BLOCKED,
                signal=ObservationSignal.LONG_RESEARCH,
                source_shell_state="BLOCKED",
                source_signal_exposure="BLOCKED",
                reason_codes=("BLOCKED",),
            )

    def test_blocked_with_none_signal(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.BLOCKED,
            signal=ObservationSignal.NONE,
            source_shell_state="BLOCKED",
            source_signal_exposure="BLOCKED",
            reason_codes=("BLOCKED",),
        )
        assert obs.signal == ObservationSignal.NONE

    def test_forbidden_metadata_key(self) -> None:
        with pytest.raises(ValueError, match="forbidden key"):
            SignalObservation(
                timestamp=datetime.now(timezone.utc),
                observation_state=ObservationState.READY,
                signal=ObservationSignal.LONG_RESEARCH,
                source_shell_state="DRY_RUN_READY",
                source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
                reason_codes=("LONG_RESEARCH_OBSERVED",),
                metadata={"enter_long": True},
            )

    def test_forbidden_metadata_api_key(self) -> None:
        with pytest.raises(ValueError, match="forbidden key"):
            SignalObservation(
                timestamp=datetime.now(timezone.utc),
                observation_state=ObservationState.READY,
                signal=ObservationSignal.LONG_RESEARCH,
                source_shell_state="DRY_RUN_READY",
                source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
                reason_codes=("LONG_RESEARCH_OBSERVED",),
                metadata={"api_key": "secret123"},
            )

    def test_immutable(self) -> None:
        obs = SignalObservation(
            timestamp=datetime.now(timezone.utc),
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        with pytest.raises(AttributeError):
            obs.signal = ObservationSignal.NONE  # type: ignore[misc]

    def test_blocked_factory(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation.blocked((MISSING_INPUT,), now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert obs.signal == ObservationSignal.NONE
        assert obs.source_shell_state == "UNKNOWN"
        assert obs.source_signal_exposure == "BLOCKED"
        assert obs.reason_codes == (MISSING_INPUT,)
        assert obs.version == "1.0"

    def test_blocked_factory_default_timestamp(self) -> None:
        obs = SignalObservation.blocked((INVALID_INPUT,))
        assert obs.timestamp.tzinfo is not None


# ---------------------------------------------------------------------------
# ObservationWindow tests
# ---------------------------------------------------------------------------

class TestObservationWindow:
    def test_valid(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        window = ObservationWindow(
            started_at=now,
            ended_at=now,
            observations=(obs,),
        )
        assert window.started_at == now
        assert len(window.observations) == 1

    def test_naive_started_at(self) -> None:
        with pytest.raises(ValueError, match="started_at"):
            ObservationWindow(
                started_at=datetime(2025, 1, 1, 12, 0, 0),
                ended_at=datetime.now(timezone.utc),
                observations=(),
            )

    def test_naive_ended_at(self) -> None:
        with pytest.raises(ValueError, match="ended_at"):
            ObservationWindow(
                started_at=datetime.now(timezone.utc),
                ended_at=datetime(2025, 1, 1, 12, 0, 0),
                observations=(),
            )

    def test_ended_before_started(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="ended_at"):
            ObservationWindow(
                started_at=now,
                ended_at=now.replace(year=now.year - 1),
                observations=(),
            )

    def test_empty_window_id(self) -> None:
        with pytest.raises(ValueError, match="window_id"):
            ObservationWindow(
                started_at=datetime.now(timezone.utc),
                ended_at=datetime.now(timezone.utc),
                observations=(),
                window_id="",
            )

    def test_immutable(self) -> None:
        window = ObservationWindow(
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            observations=(),
        )
        with pytest.raises(AttributeError):
            window.window_id = "new"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ObservationDataQuality tests
# ---------------------------------------------------------------------------

class TestObservationDataQuality:
    def test_defaults(self) -> None:
        dq = ObservationDataQuality()
        assert dq.input_present is False
        assert dq.observation_count == 0
        assert dq.reason == "NOT_EVALUATED"

    def test_negative_counts(self) -> None:
        with pytest.raises(ValueError, match="observation_count"):
            ObservationDataQuality(observation_count=-1)

    def test_negative_blocked_count(self) -> None:
        with pytest.raises(ValueError, match="blocked_count"):
            ObservationDataQuality(blocked_count=-1)

    def test_negative_unknown_count(self) -> None:
        with pytest.raises(ValueError, match="unknown_count"):
            ObservationDataQuality(unknown_count=-1)

    def test_empty_reason(self) -> None:
        with pytest.raises(ValueError, match="reason"):
            ObservationDataQuality(reason="")

    def test_immutable(self) -> None:
        dq = ObservationDataQuality()
        with pytest.raises(AttributeError):
            dq.observation_count = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ObservationReport tests
# ---------------------------------------------------------------------------

class TestObservationReport:
    def test_valid(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        window = ObservationWindow(
            started_at=now,
            ended_at=now,
            observations=(obs,),
        )
        report = ObservationReport(
            generated_at=now,
            report_state=ObservationState.READY,
            window=window,
            summary={"total_observations": 1},
        )
        assert report.generated_at == now
        assert report.report_state == ObservationState.READY

    def test_naive_generated_at(self) -> None:
        with pytest.raises(ValueError, match="generated_at"):
            ObservationReport(
                generated_at=datetime(2025, 1, 1, 12, 0, 0),
                report_state=ObservationState.READY,
                window=ObservationWindow(
                    started_at=datetime.now(timezone.utc),
                    ended_at=datetime.now(timezone.utc),
                    observations=(),
                ),
            )

    def test_empty_report_formats(self) -> None:
        with pytest.raises(ValueError, match="report_formats"):
            ObservationReport(
                generated_at=datetime.now(timezone.utc),
                report_state=ObservationState.READY,
                window=ObservationWindow(
                    started_at=datetime.now(timezone.utc),
                    ended_at=datetime.now(timezone.utc),
                    observations=(),
                ),
                report_formats=(),
            )

    def test_empty_reason_codes(self) -> None:
        with pytest.raises(ValueError, match="reason_codes"):
            ObservationReport(
                generated_at=datetime.now(timezone.utc),
                report_state=ObservationState.READY,
                window=ObservationWindow(
                    started_at=datetime.now(timezone.utc),
                    ended_at=datetime.now(timezone.utc),
                    observations=(),
                ),
                reason_codes=(),
            )

    def test_empty_version(self) -> None:
        with pytest.raises(ValueError, match="version"):
            ObservationReport(
                generated_at=datetime.now(timezone.utc),
                report_state=ObservationState.READY,
                window=ObservationWindow(
                    started_at=datetime.now(timezone.utc),
                    ended_at=datetime.now(timezone.utc),
                    observations=(),
                ),
                version="",
            )

    def test_blocked_report_with_actionable_summary(self) -> None:
        now = datetime.now(timezone.utc)
        # A blocked report with summary counts is allowed -- the report state clearly indicates BLOCKED
        report = ObservationReport(
            generated_at=now,
            report_state=ObservationState.BLOCKED,
            window=ObservationWindow(
                started_at=now,
                ended_at=now,
                observations=(),
            ),
            summary={"long_research_count": 1},
        )
        assert report.report_state == ObservationState.BLOCKED
        assert report.summary["long_research_count"] == 1

    def test_blocked_report_with_zero_counts(self) -> None:
        now = datetime.now(timezone.utc)
        report = ObservationReport(
            generated_at=now,
            report_state=ObservationState.BLOCKED,
            window=ObservationWindow(
                started_at=now,
                ended_at=now,
                observations=(),
            ),
            summary={"long_research_count": 0, "short_research_count": 0},
        )
        assert report.report_state == ObservationState.BLOCKED

    def test_immutable(self) -> None:
        now = datetime.now(timezone.utc)
        report = ObservationReport(
            generated_at=now,
            report_state=ObservationState.READY,
            window=ObservationWindow(
                started_at=now,
                ended_at=now,
                observations=(),
            ),
        )
        with pytest.raises(AttributeError):
            report.version = "2.0"  # type: ignore[misc]

    def test_blocked_factory(self) -> None:
        now = datetime.now(timezone.utc)
        report = ObservationReport.blocked((EMPTY_OBSERVATION_WINDOW,), generated_at=now)
        assert report.report_state == ObservationState.BLOCKED
        assert report.reason_codes == (EMPTY_OBSERVATION_WINDOW,)
        assert report.generated_at == now
        assert report.data_quality.reason == EMPTY_OBSERVATION_WINDOW

    def test_blocked_factory_default_timestamp(self) -> None:
        report = ObservationReport.blocked((DEFAULT_BLOCKED,))
        assert report.generated_at.tzinfo is not None

    def test_blocked_factory_default_window(self) -> None:
        report = ObservationReport.blocked((DEFAULT_BLOCKED,))
        assert report.window.started_at == report.generated_at


# ---------------------------------------------------------------------------
# Reason codes tests
# ---------------------------------------------------------------------------

class TestReasonCodes:
    def test_all_present(self) -> None:
        assert MISSING_INPUT in REASON_CODES
        assert INVALID_INPUT in REASON_CODES
        assert UNSUPPORTED_INPUT_VERSION in REASON_CODES
        assert DRY_RUN_DISABLED in REASON_CODES
        assert LIVE_TRADING_ENABLED in REASON_CODES
        assert REAL_ORDERS_ENABLED in REASON_CODES
        assert LEVERAGE_ENABLED in REASON_CODES
        assert SHORTING_ENABLED in REASON_CODES
        assert EMPTY_OBSERVATION_WINDOW in REASON_CODES
        assert UNSAFE_METADATA in REASON_CODES
        assert REPORT_GENERATION_BLOCKED in REASON_CODES
        assert OBSERVATION_ERROR in REASON_CODES
        assert DEFAULT_BLOCKED in REASON_CODES

    def test_is_tuple(self) -> None:
        assert isinstance(REASON_CODES, tuple)


# ---------------------------------------------------------------------------
# Forbidden metadata keys tests
# ---------------------------------------------------------------------------

class TestForbiddenMetadataKeys:
    def test_contains_trade_columns(self) -> None:
        assert "enter_long" in FORBIDDEN_METADATA_KEYS
        assert "enter_short" in FORBIDDEN_METADATA_KEYS
        assert "exit_long" in FORBIDDEN_METADATA_KEYS
        assert "exit_short" in FORBIDDEN_METADATA_KEYS

    def test_contains_secrets(self) -> None:
        assert "api_key" in FORBIDDEN_METADATA_KEYS
        assert "secret" in FORBIDDEN_METADATA_KEYS
        assert "exchange_credentials" in FORBIDDEN_METADATA_KEYS
        assert "executable_instructions" in FORBIDDEN_METADATA_KEYS
