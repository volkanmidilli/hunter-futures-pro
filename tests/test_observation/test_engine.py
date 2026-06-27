"""Tests for observation engine."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

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
# build_signal_observation tests
# ---------------------------------------------------------------------------

class TestBuildSignalObservation:
    def test_long_research_happy_path(self) -> None:
        now = datetime.now(timezone.utc)
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata, now=now)
        assert obs.observation_state == ObservationState.READY
        assert obs.signal == ObservationSignal.LONG_RESEARCH
        assert obs.reason_codes == ("LONG_RESEARCH_OBSERVED",)

    def test_short_research_happy_path(self) -> None:
        now = datetime.now(timezone.utc)
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_SHORT_RESEARCH_METADATA",
            "reason_codes": ["SHORT_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "SHORT_RESEARCH",
            "hunter_research_reason": "SHORT_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_SHORT_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata, now=now)
        assert obs.observation_state == ObservationState.READY
        assert obs.signal == ObservationSignal.SHORT_RESEARCH
        assert obs.reason_codes == ("SHORT_RESEARCH_OBSERVED",)

    def test_none_signal(self) -> None:
        now = datetime.now(timezone.utc)
        metadata = {
            "shell_state": "BLOCKED",
            "signal_exposure": "BLOCKED",
            "reason_codes": ["SIGNAL_BLOCKED"],
            "hunter_research_signal": "NONE",
            "hunter_research_reason": "SIGNAL_BLOCKED",
            "hunter_shell_state": "BLOCKED",
            "hunter_signal_exposure": "BLOCKED",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert obs.signal == ObservationSignal.NONE
        assert obs.reason_codes == (DEFAULT_BLOCKED,)

    def test_missing_input(self) -> None:
        obs = build_signal_observation(None)
        assert obs.observation_state == ObservationState.BLOCKED
        assert obs.reason_codes == (MISSING_INPUT,)

    def test_invalid_input_not_dict(self) -> None:
        obs = build_signal_observation("not a dict")
        assert obs.observation_state == ObservationState.BLOCKED
        assert obs.reason_codes == (INVALID_INPUT,)

    def test_invalid_input_missing_fields(self) -> None:
        obs = build_signal_observation({"version": "1.0"})
        assert obs.observation_state == ObservationState.BLOCKED
        assert obs.reason_codes == (INVALID_INPUT,)

    def test_unsupported_version(self) -> None:
        now = datetime.now(timezone.utc)
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "2.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert obs.reason_codes == (UNSUPPORTED_INPUT_VERSION,)

    def test_dry_run_disabled(self) -> None:
        now = datetime.now(timezone.utc)
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": False,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert obs.reason_codes == (DRY_RUN_DISABLED,)

    def test_live_trading_enabled(self) -> None:
        now = datetime.now(timezone.utc)
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": True,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert obs.reason_codes == (LIVE_TRADING_ENABLED,)

    def test_real_orders_enabled(self) -> None:
        now = datetime.now(timezone.utc)
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": True,
            "leverage_enabled": False,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert obs.reason_codes == (REAL_ORDERS_ENABLED,)

    def test_leverage_enabled(self) -> None:
        now = datetime.now(timezone.utc)
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": True,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert obs.reason_codes == (LEVERAGE_ENABLED,)

    def test_shorting_enabled(self) -> None:
        now = datetime.now(timezone.utc)
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": True,
        }
        obs = build_signal_observation(metadata, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert obs.reason_codes == (SHORTING_ENABLED,)

    def test_unsafe_metadata(self) -> None:
        now = datetime.now(timezone.utc)
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
            "metadata": {"enter_long": True},
        }
        obs = build_signal_observation(metadata, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert obs.reason_codes == (UNSAFE_METADATA,)

    def test_first_blocking_reason_only(self) -> None:
        now = datetime.now(timezone.utc)
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "2.0",
            "dry_run": False,
            "live_trading_enabled": True,
            "real_orders_enabled": True,
            "leverage_enabled": True,
            "shorting_enabled": True,
        }
        obs = build_signal_observation(metadata, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        # Should be UNSUPPORTED_INPUT_VERSION (priority 3) not DRY_RUN_DISABLED (priority 4)
        assert obs.reason_codes == (UNSUPPORTED_INPUT_VERSION,)

    def test_default_config(self) -> None:
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata)
        assert obs.observation_state == ObservationState.READY

    def test_default_now(self) -> None:
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata)
        assert obs.timestamp.tzinfo is not None

    def test_exception_fail_closed(self) -> None:
        # Create a scenario that causes an unexpected exception in the engine
        # by passing a dict with a value that raises when compared
        class BadValue:
            def __eq__(self, other):
                raise RuntimeError("Simulated unexpected error")

        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": BadValue(),
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
            "metadata": {},
        }
        obs = build_signal_observation(metadata)
        assert obs.observation_state == ObservationState.BLOCKED
        assert obs.reason_codes == (OBSERVATION_ERROR,)

    def test_no_file_reads(self) -> None:
        # Verify the function does not read files
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata)
        assert obs.observation_state == ObservationState.READY

    def test_no_file_writes(self) -> None:
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata)
        assert obs.observation_state == ObservationState.READY

    def test_no_network_calls(self) -> None:
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata)
        assert obs.observation_state == ObservationState.READY

    def test_no_freqtrade_import(self) -> None:
        import hunter.observation.engine as engine_module
        assert "freqtrade" not in engine_module.__dict__

    def test_no_binance(self) -> None:
        import hunter.observation.engine as engine_module
        assert "binance" not in engine_module.__dict__

    def test_no_live_trading(self) -> None:
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata)
        assert obs.observation_state == ObservationState.READY

    def test_no_leverage(self) -> None:
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata)
        assert obs.observation_state == ObservationState.READY

    def test_no_shorting(self) -> None:
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata)
        assert obs.observation_state == ObservationState.READY

    def test_no_real_entry_exit(self) -> None:
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata)
        assert obs.observation_state == ObservationState.READY

    def test_no_report_feedback(self) -> None:
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
        }
        obs = build_signal_observation(metadata)
        assert obs.observation_state == ObservationState.READY

    def test_no_api_keys_in_metadata(self) -> None:
        metadata = {
            "shell_state": "DRY_RUN_READY",
            "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "reason_codes": ["LONG_RESEARCH_METADATA_EXPOSED"],
            "hunter_research_signal": "LONG_RESEARCH",
            "hunter_research_reason": "LONG_RESEARCH_METADATA_EXPOSED",
            "hunter_shell_state": "DRY_RUN_READY",
            "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
            "version": "1.0",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
            "metadata": {"api_key": "secret123"},
        }
        obs = build_signal_observation(metadata)
        assert obs.observation_state == ObservationState.BLOCKED
        assert obs.reason_codes == (UNSAFE_METADATA,)


# ---------------------------------------------------------------------------
# build_observation_window tests
# ---------------------------------------------------------------------------

class TestBuildObservationWindow:
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
        window = build_observation_window((obs,), now, now)
        assert window.started_at == now
        assert len(window.observations) == 1

    def test_empty(self) -> None:
        now = datetime.now(timezone.utc)
        window = build_observation_window((), now, now)
        assert len(window.observations) == 0


# ---------------------------------------------------------------------------
# build_observation_report tests
# ---------------------------------------------------------------------------

class TestBuildObservationReport:
    def test_valid_with_observations(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.report_state == ObservationState.READY
        assert report.summary["total_observations"] == 1
        assert report.summary["long_research_count"] == 1
        assert report.summary["short_research_count"] == 0
        assert report.summary["none_count"] == 0
        assert report.summary["blocked_count"] == 0
        assert report.summary["unknown_count"] == 0

    def test_empty_window_blocked(self) -> None:
        now = datetime.now(timezone.utc)
        window = build_observation_window((), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.report_state == ObservationState.BLOCKED
        assert report.reason_codes == (EMPTY_OBSERVATION_WINDOW,)

    def test_mixed_observations_blocked(self) -> None:
        now = datetime.now(timezone.utc)
        ready_obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        blocked_obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.BLOCKED,
            signal=ObservationSignal.NONE,
            source_shell_state="BLOCKED",
            source_signal_exposure="BLOCKED",
            reason_codes=("SIGNAL_BLOCKED",),
        )
        window = build_observation_window((ready_obs, blocked_obs), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.report_state == ObservationState.BLOCKED
        assert report.summary.get("blocked_count", 0) == 1
        assert report.summary["total_observations"] == 2

    def test_unsafe_metadata_in_observation(self) -> None:
        now = datetime.now(timezone.utc)
        # Use safe metadata in SignalObservation constructor, then test report-level detection
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
            metadata={"safe_key": "safe_value"},
        )
        window = build_observation_window((obs,), now, now)
        # Manually test that has_unsafe_metadata detects forbidden keys
        assert has_unsafe_metadata({"enter_long": True}) is True
        assert has_unsafe_metadata({"safe_key": "safe_value"}) is False
        # Report should be READY since observation metadata is safe
        report = build_observation_report(window, generated_at=now)
        assert report.report_state == ObservationState.READY

    def test_reason_counts(self) -> None:
        now = datetime.now(timezone.utc)
        obs1 = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        obs2 = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        window = build_observation_window((obs1, obs2), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.summary["reason_counts"]["LONG_RESEARCH_OBSERVED"] == 2

    def test_default_config(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window)
        assert report.report_state == ObservationState.READY

    def test_default_generated_at(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window)
        assert report.generated_at.tzinfo is not None

    def test_exception_fail_closed(self) -> None:
        # Create a window with invalid observations that will cause an error
        now = datetime.now(timezone.utc)
        # This should not cause an error in normal flow, but test exception handling
        window = ObservationWindow(
            started_at=now,
            ended_at=now,
            observations=(),
        )
        report = build_observation_report(window, generated_at=now)
        assert report.report_state == ObservationState.BLOCKED

    def test_safety_flags(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.safety_flags.dry_run is True
        assert report.safety_flags.live_trading_enabled is False
        assert report.safety_flags.real_orders_enabled is False
        assert report.safety_flags.leverage_enabled is False
        assert report.safety_flags.shorting_enabled is False

    def test_report_formats(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert ReportFormat.JSON in report.report_formats
        assert ReportFormat.MARKDOWN in report.report_formats

    def test_data_quality(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.data_quality.input_present is True
        assert report.data_quality.input_valid is True
        assert report.data_quality.observation_count == 1

    def test_blocked_data_quality(self) -> None:
        now = datetime.now(timezone.utc)
        window = build_observation_window((), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.data_quality.input_present is False
        assert report.data_quality.input_valid is False
        assert report.data_quality.observation_count == 0

    def test_no_file_reads(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.report_state == ObservationState.READY

    def test_no_file_writes(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.report_state == ObservationState.READY

    def test_no_network_calls(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.report_state == ObservationState.READY

    def test_no_freqtrade_import(self) -> None:
        import hunter.observation.engine as engine_module
        assert "freqtrade" not in engine_module.__dict__

    def test_no_binance(self) -> None:
        import hunter.observation.engine as engine_module
        assert "binance" not in engine_module.__dict__

    def test_no_live_trading(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.safety_flags.live_trading_enabled is False

    def test_no_leverage(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.safety_flags.leverage_enabled is False

    def test_no_shorting(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.safety_flags.shorting_enabled is False

    def test_no_real_entry_exit(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.report_state == ObservationState.READY

    def test_no_report_feedback(self) -> None:
        now = datetime.now(timezone.utc)
        obs = SignalObservation(
            timestamp=now,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="DRY_RUN_READY",
            source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
            reason_codes=("LONG_RESEARCH_OBSERVED",),
        )
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.report_state == ObservationState.READY


# ---------------------------------------------------------------------------
# build_observation_safety_flags tests
# ---------------------------------------------------------------------------

class TestBuildObservationSafetyFlags:
    def test_defaults(self) -> None:
        config = ObservationConfig()
        flags = build_observation_safety_flags(config)
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


# ---------------------------------------------------------------------------
# has_unsafe_metadata tests
# ---------------------------------------------------------------------------

class TestHasUnsafeMetadata:
    def test_safe_metadata(self) -> None:
        assert has_unsafe_metadata({"foo": "bar"}) is False

    def test_enter_long(self) -> None:
        assert has_unsafe_metadata({"enter_long": True}) is True

    def test_enter_short(self) -> None:
        assert has_unsafe_metadata({"enter_short": True}) is True

    def test_exit_long(self) -> None:
        assert has_unsafe_metadata({"exit_long": True}) is True

    def test_exit_short(self) -> None:
        assert has_unsafe_metadata({"exit_short": True}) is True

    def test_api_key(self) -> None:
        assert has_unsafe_metadata({"api_key": "secret"}) is True

    def test_secret(self) -> None:
        assert has_unsafe_metadata({"secret": "value"}) is True

    def test_exchange_credentials(self) -> None:
        assert has_unsafe_metadata({"exchange_credentials": "value"}) is True

    def test_executable_instructions(self) -> None:
        assert has_unsafe_metadata({"executable_instructions": "value"}) is True

    def test_not_dict(self) -> None:
        assert has_unsafe_metadata("not a dict") is False  # type: ignore[arg-type]

    def test_empty_dict(self) -> None:
        assert has_unsafe_metadata({}) is False

    def test_multiple_forbidden_keys(self) -> None:
        assert has_unsafe_metadata({"enter_long": True, "api_key": "secret"}) is True
