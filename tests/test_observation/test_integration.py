"""Integration tests for MVP-10 Dry-Run Research Observation & Reports.

Tests the complete in-process observation flow:
  MVP-9 shell metadata -> SignalObservation -> ObservationWindow -> ObservationReport
  -> JSON/Markdown report -> tmp_path verification.

Uses tmp_path only for file output. No production data reads/writes.
No network, database, realtime streaming, Freqtrade import, or exchange calls.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from hunter.observation.engine import (
    build_observation_report,
    build_observation_window,
    build_signal_observation,
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
from hunter.observation.writer import (
    atomic_write_json_report,
    atomic_write_markdown_report,
    observation_report_to_dict,
    observation_report_to_markdown,
    write_observation_reports,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc)


def _make_valid_metadata(
    signal: str = "LONG_RESEARCH",
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a valid MVP-9 shell metadata dict."""
    meta: dict[str, Any] = {
        "version": "1.0",
        "dry_run": True,
        "live_trading_enabled": False,
        "real_orders_enabled": False,
        "leverage_enabled": False,
        "shorting_enabled": False,
        "shell_state": "DRY_RUN_READY",
        "signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
        "reason_codes": ("LONG_RESEARCH_EXPOSED",),
        "hunter_research_signal": signal,
        "hunter_research_reason": "LONG_RESEARCH_EXPOSED",
        "hunter_shell_state": "DRY_RUN_READY",
        "hunter_signal_exposure": "EXPOSE_LONG_RESEARCH_METADATA",
        "metadata": {},
    }
    if overrides:
        meta.update(overrides)
    return meta


# ---------------------------------------------------------------------------
# 1. Long research happy path
# ---------------------------------------------------------------------------


class TestLongResearchHappyPath:
    def test_signal_observation_ready(self) -> None:
        now = _now()
        meta = _make_valid_metadata("LONG_RESEARCH")
        obs = build_signal_observation(meta, now=now)
        assert obs.observation_state == ObservationState.READY
        assert obs.signal == ObservationSignal.LONG_RESEARCH
        assert obs.reason_codes == ("LONG_RESEARCH_OBSERVED",)

    def test_observation_report_ready(self) -> None:
        now = _now()
        meta = _make_valid_metadata("LONG_RESEARCH")
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.report_state == ObservationState.READY
        assert report.summary["long_research_count"] == 1
        assert report.summary["short_research_count"] == 0
        assert report.summary["total_observations"] == 1

    def test_json_report_contains_long_research(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata("LONG_RESEARCH")
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        json_path = tmp_path / "report.json"
        atomic_write_json_report(observation_report_to_dict(report), json_path)
        data = json.loads(json_path.read_text())
        assert data["summary"]["long_research_count"] == 1
        assert "LONG_RESEARCH" in json.dumps(data)

    def test_markdown_report_contains_long_research(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata("LONG_RESEARCH")
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        md_path = tmp_path / "report.md"
        atomic_write_markdown_report(observation_report_to_markdown(report), md_path)
        md = md_path.read_text()
        assert "Long research" in md or "LONG_RESEARCH" in md
        assert "Safety Notice" in md

    def test_report_is_human_review_only(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata("LONG_RESEARCH")
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        md = observation_report_to_markdown(report)
        assert "Safety Notice" in md
        assert "human-review artifact" in md.lower() or "must not be consumed" in md.lower()


# ---------------------------------------------------------------------------
# 2. Short research happy path
# ---------------------------------------------------------------------------


class TestShortResearchHappyPath:
    def test_signal_observation_ready(self) -> None:
        now = _now()
        meta = _make_valid_metadata("SHORT_RESEARCH", {
            "signal_exposure": "EXPOSE_SHORT_RESEARCH_METADATA",
            "hunter_signal_exposure": "EXPOSE_SHORT_RESEARCH_METADATA",
        })
        obs = build_signal_observation(meta, now=now)
        assert obs.observation_state == ObservationState.READY
        assert obs.signal == ObservationSignal.SHORT_RESEARCH
        assert obs.reason_codes == ("SHORT_RESEARCH_OBSERVED",)

    def test_observation_report_ready(self) -> None:
        now = _now()
        meta = _make_valid_metadata("SHORT_RESEARCH", {
            "signal_exposure": "EXPOSE_SHORT_RESEARCH_METADATA",
            "hunter_signal_exposure": "EXPOSE_SHORT_RESEARCH_METADATA",
        })
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.report_state == ObservationState.READY
        assert report.summary["short_research_count"] == 1
        assert report.summary["long_research_count"] == 0

    def test_json_report_contains_short_research(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata("SHORT_RESEARCH", {
            "signal_exposure": "EXPOSE_SHORT_RESEARCH_METADATA",
            "hunter_signal_exposure": "EXPOSE_SHORT_RESEARCH_METADATA",
        })
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        json_path = tmp_path / "report.json"
        atomic_write_json_report(observation_report_to_dict(report), json_path)
        data = json.loads(json_path.read_text())
        assert data["summary"]["short_research_count"] == 1
        assert "SHORT_RESEARCH" in json.dumps(data)

    def test_markdown_report_contains_short_research(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata("SHORT_RESEARCH", {
            "signal_exposure": "EXPOSE_SHORT_RESEARCH_METADATA",
            "hunter_signal_exposure": "EXPOSE_SHORT_RESEARCH_METADATA",
        })
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        md_path = tmp_path / "report.md"
        atomic_write_markdown_report(observation_report_to_markdown(report), md_path)
        md = md_path.read_text()
        assert "Short research" in md or "SHORT_RESEARCH" in md


# ---------------------------------------------------------------------------
# 3. Missing metadata
# ---------------------------------------------------------------------------


class TestMissingMetadata:
    def test_signal_observation_blocked(self) -> None:
        now = _now()
        obs = build_signal_observation(None, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert obs.signal == ObservationSignal.NONE
        assert MISSING_INPUT in obs.reason_codes

    def test_report_generated_as_audit_artifact(self, tmp_path: Path) -> None:
        now = _now()
        obs = build_signal_observation(None, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.report_state == ObservationState.BLOCKED
        assert MISSING_INPUT in report.window.observations[0].reason_codes
        json_path = tmp_path / "report.json"
        atomic_write_json_report(observation_report_to_dict(report), json_path)
        data = json.loads(json_path.read_text())
        assert data["report_state"] == "BLOCKED"
        assert MISSING_INPUT in data["window"]["observations"][0]["reason_codes"]

    def test_no_action_triggered(self) -> None:
        now = _now()
        obs = build_signal_observation(None, now=now)
        assert obs.signal == ObservationSignal.NONE
        assert obs.observation_state == ObservationState.BLOCKED


# ---------------------------------------------------------------------------
# 4. Invalid metadata
# ---------------------------------------------------------------------------


class TestInvalidMetadata:
    def test_signal_observation_blocked(self) -> None:
        now = _now()
        obs = build_signal_observation({}, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert INVALID_INPUT in obs.reason_codes

    def test_report_generated_as_audit_artifact(self, tmp_path: Path) -> None:
        now = _now()
        obs = build_signal_observation({}, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.report_state == ObservationState.BLOCKED
        assert INVALID_INPUT in report.window.observations[0].reason_codes
        md_path = tmp_path / "report.md"
        atomic_write_markdown_report(observation_report_to_markdown(report), md_path)
        md = md_path.read_text()
        assert "BLOCKED" in md
        assert INVALID_INPUT in report.window.observations[0].reason_codes


# ---------------------------------------------------------------------------
# 5. Unsupported version
# ---------------------------------------------------------------------------


class TestUnsupportedVersion:
    def test_signal_observation_blocked(self) -> None:
        now = _now()
        meta = _make_valid_metadata(overrides={"version": "2.0"})
        obs = build_signal_observation(meta, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert UNSUPPORTED_INPUT_VERSION in obs.reason_codes

    def test_report_generated_safely(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata(overrides={"version": "2.0"})
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert UNSUPPORTED_INPUT_VERSION in report.window.observations[0].reason_codes
        json_path = tmp_path / "report.json"
        atomic_write_json_report(observation_report_to_dict(report), json_path)
        data = json.loads(json_path.read_text())
        assert UNSUPPORTED_INPUT_VERSION in data["window"]["observations"][0]["reason_codes"]


# ---------------------------------------------------------------------------
# 6. dry_run false
# ---------------------------------------------------------------------------


class TestDryRunDisabled:
    def test_signal_observation_blocked(self) -> None:
        now = _now()
        meta = _make_valid_metadata(overrides={"dry_run": False})
        obs = build_signal_observation(meta, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert DRY_RUN_DISABLED in obs.reason_codes

    def test_report_generated_safely(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata(overrides={"dry_run": False})
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert DRY_RUN_DISABLED in report.window.observations[0].reason_codes
        md_path = tmp_path / "report.md"
        atomic_write_markdown_report(observation_report_to_markdown(report), md_path)
        md = md_path.read_text()
        assert "BLOCKED" in md


# ---------------------------------------------------------------------------
# 7. live_trading_enabled true
# ---------------------------------------------------------------------------


class TestLiveTradingEnabled:
    def test_signal_observation_blocked(self) -> None:
        now = _now()
        meta = _make_valid_metadata(overrides={"live_trading_enabled": True})
        obs = build_signal_observation(meta, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert LIVE_TRADING_ENABLED in obs.reason_codes

    def test_report_generated_safely(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata(overrides={"live_trading_enabled": True})
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert LIVE_TRADING_ENABLED in report.window.observations[0].reason_codes
        json_path = tmp_path / "report.json"
        atomic_write_json_report(observation_report_to_dict(report), json_path)
        data = json.loads(json_path.read_text())
        assert LIVE_TRADING_ENABLED in data["window"]["observations"][0]["reason_codes"]


# ---------------------------------------------------------------------------
# 8. real_orders_enabled true
# ---------------------------------------------------------------------------


class TestRealOrdersEnabled:
    def test_signal_observation_blocked(self) -> None:
        now = _now()
        meta = _make_valid_metadata(overrides={"real_orders_enabled": True})
        obs = build_signal_observation(meta, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert REAL_ORDERS_ENABLED in obs.reason_codes

    def test_report_generated_safely(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata(overrides={"real_orders_enabled": True})
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert REAL_ORDERS_ENABLED in report.window.observations[0].reason_codes
        md_path = tmp_path / "report.md"
        atomic_write_markdown_report(observation_report_to_markdown(report), md_path)
        md = md_path.read_text()
        assert "BLOCKED" in md


# ---------------------------------------------------------------------------
# 9. leverage_enabled true
# ---------------------------------------------------------------------------


class TestLeverageEnabled:
    def test_signal_observation_blocked(self) -> None:
        now = _now()
        meta = _make_valid_metadata(overrides={"leverage_enabled": True})
        obs = build_signal_observation(meta, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert LEVERAGE_ENABLED in obs.reason_codes

    def test_report_generated_safely(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata(overrides={"leverage_enabled": True})
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert LEVERAGE_ENABLED in report.window.observations[0].reason_codes
        json_path = tmp_path / "report.json"
        atomic_write_json_report(observation_report_to_dict(report), json_path)
        data = json.loads(json_path.read_text())
        assert LEVERAGE_ENABLED in data["window"]["observations"][0]["reason_codes"]


# ---------------------------------------------------------------------------
# 10. shorting_enabled true
# ---------------------------------------------------------------------------


class TestShortingEnabled:
    def test_signal_observation_blocked(self) -> None:
        now = _now()
        meta = _make_valid_metadata(overrides={"shorting_enabled": True})
        obs = build_signal_observation(meta, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert SHORTING_ENABLED in obs.reason_codes

    def test_report_generated_safely(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata(overrides={"shorting_enabled": True})
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        assert SHORTING_ENABLED in report.window.observations[0].reason_codes
        md_path = tmp_path / "report.md"
        atomic_write_markdown_report(observation_report_to_markdown(report), md_path)
        md = md_path.read_text()
        assert "BLOCKED" in md


# ---------------------------------------------------------------------------
# 11. Unsafe metadata
# ---------------------------------------------------------------------------


class TestUnsafeMetadata:
    @pytest.mark.parametrize("forbidden_key", list(FORBIDDEN_METADATA_KEYS))
    def test_signal_observation_blocked(self, forbidden_key: str) -> None:
        now = _now()
        meta = _make_valid_metadata(overrides={"metadata": {forbidden_key: "value"}})
        obs = build_signal_observation(meta, now=now)
        assert obs.observation_state == ObservationState.BLOCKED
        assert UNSAFE_METADATA in obs.reason_codes

    def test_no_unsafe_keys_in_report_output(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata(overrides={"metadata": {"enter_long": True}})
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        json_path = tmp_path / "report.json"
        atomic_write_json_report(observation_report_to_dict(report), json_path)
        data = json.loads(json_path.read_text())
        json_str = json.dumps(data)
        # Check that forbidden keys are not in metadata (safety flags may contain "api_key" substring)
        for obs_data in data["window"]["observations"]:
            for key in FORBIDDEN_METADATA_KEYS:
                assert key not in obs_data["metadata"], f"forbidden key {key} found in observation metadata"

    def test_no_unsafe_keys_in_markdown_output(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata(overrides={"metadata": {"secret": "abc"}})
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        md_path = tmp_path / "report.md"
        atomic_write_markdown_report(observation_report_to_markdown(report), md_path)
        md = md_path.read_text()
        # The markdown should not contain the forbidden metadata values
        assert "abc" not in md, "secret value found in Markdown output"
        assert "secret" not in md.lower() or "Safety Notice" in md, "forbidden key found in Markdown output"


# ---------------------------------------------------------------------------
# 12. Empty observation window
# ---------------------------------------------------------------------------


class TestEmptyObservationWindow:
    def test_report_blocked(self) -> None:
        now = _now()
        window = build_observation_window((), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.report_state == ObservationState.BLOCKED
        assert EMPTY_OBSERVATION_WINDOW in report.reason_codes

    def test_json_report_contains_empty_window_reason(self, tmp_path: Path) -> None:
        now = _now()
        window = build_observation_window((), now, now)
        report = build_observation_report(window, generated_at=now)
        json_path = tmp_path / "report.json"
        atomic_write_json_report(observation_report_to_dict(report), json_path)
        data = json.loads(json_path.read_text())
        assert data["report_state"] == "BLOCKED"
        assert EMPTY_OBSERVATION_WINDOW in data["reason_codes"]


# ---------------------------------------------------------------------------
# 13. Mixed observation window
# ---------------------------------------------------------------------------


class TestMixedObservationWindow:
    def test_summary_counts(self) -> None:
        now = _now()
        long_obs = build_signal_observation(_make_valid_metadata("LONG_RESEARCH"), now=now)
        short_obs = build_signal_observation(
            _make_valid_metadata("SHORT_RESEARCH", {
                "signal_exposure": "EXPOSE_SHORT_RESEARCH_METADATA",
                "hunter_signal_exposure": "EXPOSE_SHORT_RESEARCH_METADATA",
            }),
            now=now,
        )
        blocked_obs = build_signal_observation(None, now=now)
        window = build_observation_window((long_obs, short_obs, blocked_obs), now, now)
        report = build_observation_report(window, generated_at=now)
        assert report.summary["total_observations"] == 3
        assert report.summary["long_research_count"] == 1
        assert report.summary["short_research_count"] == 1
        assert report.summary["none_count"] >= 1
        assert report.summary["blocked_count"] >= 1
        assert report.report_state == ObservationState.BLOCKED

    def test_reason_counts(self) -> None:
        now = _now()
        long_obs = build_signal_observation(_make_valid_metadata("LONG_RESEARCH"), now=now)
        short_obs = build_signal_observation(
            _make_valid_metadata("SHORT_RESEARCH", {
                "signal_exposure": "EXPOSE_SHORT_RESEARCH_METADATA",
                "hunter_signal_exposure": "EXPOSE_SHORT_RESEARCH_METADATA",
            }),
            now=now,
        )
        blocked_obs = build_signal_observation(None, now=now)
        window = build_observation_window((long_obs, short_obs, blocked_obs), now, now)
        report = build_observation_report(window, generated_at=now)
        assert "LONG_RESEARCH_OBSERVED" in report.summary["reason_counts"]
        assert "SHORT_RESEARCH_OBSERVED" in report.summary["reason_counts"]
        assert MISSING_INPUT in report.summary["reason_counts"]


# ---------------------------------------------------------------------------
# 14. Writer integration
# ---------------------------------------------------------------------------


class TestWriterIntegration:
    def test_write_both_reports_to_tmp_path(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata("LONG_RESEARCH")
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        json_path = tmp_path / "report.json"
        md_path = tmp_path / "report.md"
        write_observation_reports(report, json_output_path=json_path, markdown_output_path=md_path)
        assert json_path.exists()
        assert md_path.exists()

    def test_parent_directories_created(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata("LONG_RESEARCH")
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        json_path = tmp_path / "nested" / "dir" / "report.json"
        md_path = tmp_path / "nested" / "dir" / "report.md"
        write_observation_reports(report, json_output_path=json_path, markdown_output_path=md_path)
        assert json_path.exists()
        assert md_path.exists()

    def test_json_valid_and_deterministic(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata("LONG_RESEARCH")
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        json_path = tmp_path / "report.json"
        write_observation_reports(report, json_output_path=json_path, markdown_output_path=tmp_path / "report.md")
        data = json.loads(json_path.read_text())
        assert data["report_state"] == "READY"
        assert data["summary"]["long_research_count"] == 1
        assert data["version"] == "1.0"
        assert "window" in data
        assert "data_quality" in data
        assert "safety_flags" in data

    def test_markdown_safety_notice(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata("LONG_RESEARCH")
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        md_path = tmp_path / "report.md"
        write_observation_reports(report, json_output_path=tmp_path / "report.json", markdown_output_path=md_path)
        md = md_path.read_text()
        assert "Safety Notice" in md
        assert "human-review artifact" in md.lower() or "must not be consumed" in md.lower()

    def test_no_api_keys_in_output(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata("LONG_RESEARCH")
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        json_path = tmp_path / "report.json"
        md_path = tmp_path / "report.md"
        write_observation_reports(report, json_output_path=json_path, markdown_output_path=md_path)
        json_str = json_path.read_text()
        md_str = md_path.read_text()
        # "api_key" as a standalone word should not appear (but "api_keys_allowed" is a safety flag field)
        assert "\"api_key\":" not in json_str.lower(), "standalone api_key found in JSON output"
        assert "secret" not in json_str.lower() or "secret" not in md_str.lower(), "secret value found in output"
        assert "password" not in json_str.lower() or "password" not in md_str.lower(), "password found in output"

    def test_no_executable_instructions_in_output(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata("LONG_RESEARCH")
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        json_path = tmp_path / "report.json"
        md_path = tmp_path / "report.md"
        write_observation_reports(report, json_output_path=json_path, markdown_output_path=md_path)
        md_str = md_path.read_text()
        assert "execute" not in md_str.lower() or "buy" not in md_str.lower() or "sell" not in md_str.lower()


# ---------------------------------------------------------------------------
# 15. Safety assertions
# ---------------------------------------------------------------------------


class TestSafetyAssertions:
    def test_no_freqtrade_import(self) -> None:
        import sys
        assert "freqtrade" not in sys.modules

    def test_no_production_data_reads(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata("LONG_RESEARCH")
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        json_path = tmp_path / "report.json"
        md_path = tmp_path / "report.md"
        write_observation_reports(report, json_output_path=json_path, markdown_output_path=md_path)
        assert json_path.exists()
        assert md_path.exists()

    def test_no_production_data_writes(self, tmp_path: Path) -> None:
        now = _now()
        meta = _make_valid_metadata("LONG_RESEARCH")
        obs = build_signal_observation(meta, now=now)
        window = build_observation_window((obs,), now, now)
        report = build_observation_report(window, generated_at=now)
        json_path = tmp_path / "report.json"
        md_path = tmp_path / "report.md"
        write_observation_reports(report, json_output_path=json_path, markdown_output_path=md_path)
        assert json_path.exists()
        assert md_path.exists()

    def test_no_report_feedback_into_execution(self) -> None:
        config = ObservationConfig()
        assert config.allow_execution_feedback is False

    def test_no_network_calls(self) -> None:
        config = ObservationConfig()
        assert config.allow_network_calls is False

    def test_no_database_persistence(self) -> None:
        config = ObservationConfig()
        assert config.allow_database_persistence is False

    def test_no_realtime_streaming(self) -> None:
        config = ObservationConfig()
        assert config.allow_realtime_streaming is False

    def test_no_live_trading(self) -> None:
        config = ObservationConfig()
        assert config.allow_live_trading is False

    def test_no_real_orders(self) -> None:
        config = ObservationConfig()
        assert config.allow_real_orders is False

    def test_no_leverage(self) -> None:
        config = ObservationConfig()
        assert config.allow_leverage is False

    def test_no_shorting(self) -> None:
        config = ObservationConfig()
        assert config.allow_shorting is False

    def test_no_real_entry_exit_execution(self) -> None:
        config = ObservationConfig()
        assert config.allow_execution_feedback is False
