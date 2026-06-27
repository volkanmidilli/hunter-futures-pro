"""Tests for observation report writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from hunter.observation.models import (
    DEFAULT_BLOCKED,
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def now() -> datetime:
    return datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_window(now: datetime) -> ObservationWindow:
    obs = SignalObservation(
        timestamp=now,
        observation_state=ObservationState.READY,
        signal=ObservationSignal.LONG_RESEARCH,
        source_shell_state="DRY_RUN_READY",
        source_signal_exposure="EXPOSE_LONG_RESEARCH_METADATA",
        reason_codes=("LONG_RESEARCH_OBSERVED",),
        metadata={"pair": "BTC/USDT"},
        safety_flags=ObservationSafetyFlags(),
        version="1.0",
    )
    return ObservationWindow(
        started_at=now,
        ended_at=now,
        observations=(obs,),
        window_id="test-window",
    )


@pytest.fixture
def sample_report(now: datetime, sample_window: ObservationWindow) -> ObservationReport:
    return ObservationReport(
        generated_at=now,
        report_state=ObservationState.READY,
        window=sample_window,
        summary={
            "total_observations": 1,
            "long_research_count": 1,
            "short_research_count": 0,
            "none_count": 0,
            "blocked_count": 0,
            "unknown_count": 0,
            "reason_counts": {"LONG_RESEARCH_OBSERVED": 1},
        },
        data_quality=ObservationDataQuality(
            input_present=True,
            input_valid=True,
            input_version_supported=True,
            observation_count=1,
            blocked_count=0,
            unknown_count=0,
            reason="VALID",
        ),
        safety_flags=ObservationSafetyFlags(),
        report_formats=(ReportFormat.JSON, ReportFormat.MARKDOWN),
        reason_codes=("REPORT_GENERATED",),
        version="1.0",
    )


@pytest.fixture
def blocked_report(now: datetime) -> ObservationReport:
    window = ObservationWindow(
        started_at=now,
        ended_at=now,
        observations=(),
        window_id="blocked-window",
    )
    return ObservationReport.blocked(
        reason_codes=(DEFAULT_BLOCKED,),
        window=window,
        generated_at=now,
    )


# ---------------------------------------------------------------------------
# observation_report_to_dict tests
# ---------------------------------------------------------------------------


class TestObservationReportToDict:
    def test_all_top_level_fields_present(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        assert "generated_at" in d
        assert "report_state" in d
        assert "window" in d
        assert "summary" in d
        assert "data_quality" in d
        assert "safety_flags" in d
        assert "report_formats" in d
        assert "reason_codes" in d
        assert "version" in d

    def test_datetime_serialized_as_iso(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        assert d["generated_at"] == "2025-01-15T12:00:00Z"

    def test_enum_serialized_as_value(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        assert d["report_state"] == "READY"
        assert d["report_formats"] == ["JSON", "MARKDOWN"]

    def test_tuple_serialized_as_list(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        assert isinstance(d["reason_codes"], list)
        assert d["reason_codes"] == ["REPORT_GENERATED"]

    def test_window_serialized_as_dict(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        window = d["window"]
        assert isinstance(window, dict)
        assert window["window_id"] == "test-window"
        assert window["started_at"] == "2025-01-15T12:00:00Z"
        assert window["ended_at"] == "2025-01-15T12:00:00Z"
        assert isinstance(window["observations"], list)
        assert len(window["observations"]) == 1

    def test_observation_serialized_as_dict(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        obs = d["window"]["observations"][0]
        assert obs["observation_state"] == "READY"
        assert obs["signal"] == "LONG_RESEARCH"
        assert obs["source_shell_state"] == "DRY_RUN_READY"
        assert obs["source_signal_exposure"] == "EXPOSE_LONG_RESEARCH_METADATA"
        assert obs["reason_codes"] == ["LONG_RESEARCH_OBSERVED"]
        assert obs["metadata"] == {"pair": "BTC/USDT"}
        assert obs["version"] == "1.0"

    def test_data_quality_serialized_as_dict(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        dq = d["data_quality"]
        assert isinstance(dq, dict)
        assert dq["input_present"] is True
        assert dq["input_valid"] is True
        assert dq["observation_count"] == 1
        assert dq["reason"] == "VALID"

    def test_safety_flags_serialized_as_dict(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        sf = d["safety_flags"]
        assert isinstance(sf, dict)
        assert sf["dry_run"] is True
        assert sf["live_trading_enabled"] is False
        assert sf["real_orders_enabled"] is False
        assert sf["leverage_enabled"] is False
        assert sf["shorting_enabled"] is False
        assert sf["execution_feedback_allowed"] is False
        assert sf["network_calls_allowed"] is False
        assert sf["database_persistence_allowed"] is False
        assert sf["realtime_streaming_allowed"] is False
        assert sf["api_keys_allowed"] is False

    def test_does_not_mutate_report(self, sample_report: ObservationReport) -> None:
        original_reason_codes = sample_report.reason_codes
        original_summary = dict(sample_report.summary)
        observation_report_to_dict(sample_report)
        assert sample_report.reason_codes == original_reason_codes
        assert dict(sample_report.summary) == original_summary

    def test_no_secrets_in_dict(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        json_str = json.dumps(d)
        # The field "api_keys_allowed" is a safety flag, not a secret value
        assert "api_key\": \"" not in json_str.lower()
        assert "secret\": \"" not in json_str.lower()
        assert "exchange_credentials" not in json_str.lower()
        assert "executable_instructions" not in json_str.lower()

    def test_blocked_report(self, blocked_report: ObservationReport) -> None:
        d = observation_report_to_dict(blocked_report)
        assert d["report_state"] == "BLOCKED"
        assert d["reason_codes"] == ["DEFAULT_BLOCKED"]
        assert d["window"]["observations"] == []


# ---------------------------------------------------------------------------
# observation_report_to_markdown tests
# ---------------------------------------------------------------------------


class TestObservationReportToMarkdown:
    def test_contains_title(self, sample_report: ObservationReport) -> None:
        md = observation_report_to_markdown(sample_report)
        assert "# Observation Report" in md

    def test_contains_generated_at(self, sample_report: ObservationReport) -> None:
        md = observation_report_to_markdown(sample_report)
        assert "**Generated at:**" in md
        assert "2025-01-15T12:00:00Z" in md

    def test_contains_report_state(self, sample_report: ObservationReport) -> None:
        md = observation_report_to_markdown(sample_report)
        assert "**Report state:** READY" in md

    def test_contains_window_id(self, sample_report: ObservationReport) -> None:
        md = observation_report_to_markdown(sample_report)
        assert "**Window ID:** test-window" in md

    def test_contains_window_start_end(self, sample_report: ObservationReport) -> None:
        md = observation_report_to_markdown(sample_report)
        assert "**Window start:**" in md
        assert "**Window end:**" in md

    def test_contains_summary_counts(self, sample_report: ObservationReport) -> None:
        md = observation_report_to_markdown(sample_report)
        assert "**Total observations:** 1" in md
        assert "**Long research count:** 1" in md
        assert "**Short research count:** 0" in md
        assert "**None count:** 0" in md
        assert "**Blocked count:** 0" in md
        assert "**Unknown count:** 0" in md

    def test_contains_reason_codes(self, sample_report: ObservationReport) -> None:
        md = observation_report_to_markdown(sample_report)
        assert "## Reason Codes" in md
        assert "REPORT_GENERATED" in md

    def test_contains_data_quality(self, sample_report: ObservationReport) -> None:
        md = observation_report_to_markdown(sample_report)
        assert "## Data Quality" in md
        assert "**Input present:** True" in md
        assert "**Input valid:** True" in md
        assert "**Observation count:** 1" in md

    def test_contains_safety_flags(self, sample_report: ObservationReport) -> None:
        md = observation_report_to_markdown(sample_report)
        assert "## Safety Flags" in md
        assert "**Dry run:** True" in md
        assert "**Live trading enabled:** False" in md

    def test_contains_human_review_safety_notice(self, sample_report: ObservationReport) -> None:
        md = observation_report_to_markdown(sample_report)
        assert "human-review artifact only" in md
        assert "not a trading signal" in md
        assert "must not be consumed by execution" in md

    def test_no_executable_trading_instructions(self, sample_report: ObservationReport) -> None:
        md = observation_report_to_markdown(sample_report)
        assert "enter_long" not in md.lower()
        assert "enter_short" not in md.lower()
        assert "exit_long" not in md.lower()
        assert "exit_short" not in md.lower()

    def test_no_secrets_in_markdown(self, sample_report: ObservationReport) -> None:
        md = observation_report_to_markdown(sample_report)
        assert "api_key" not in md.lower()
        assert "secret" not in md.lower()
        assert "exchange_credentials" not in md.lower()

    def test_blocked_report(self, blocked_report: ObservationReport) -> None:
        md = observation_report_to_markdown(blocked_report)
        assert "**Report state:** BLOCKED" in md
        assert "DEFAULT_BLOCKED" in md


# ---------------------------------------------------------------------------
# atomic_write_json_report tests
# ---------------------------------------------------------------------------


class TestAtomicWriteJsonReport:
    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        output = tmp_path / "nested" / "report.json"
        payload = {"key": "value"}
        result = atomic_write_json_report(payload, output)
        assert result == output
        assert output.exists()

    def test_writes_valid_json(self, tmp_path: Path) -> None:
        output = tmp_path / "report.json"
        payload = {"b": 2, "a": 1}
        atomic_write_json_report(payload, output)
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data == {"a": 1, "b": 2}

    def test_indent_and_sort_keys(self, tmp_path: Path) -> None:
        output = tmp_path / "report.json"
        payload = {"b": 2, "a": 1}
        atomic_write_json_report(payload, output)
        text = output.read_text(encoding="utf-8")
        assert '"a": 1' in text
        assert '"b": 2' in text
        assert text.endswith("\n")

    def test_utf8_encoding(self, tmp_path: Path) -> None:
        output = tmp_path / "report.json"
        payload = {"symbol": "BTC/€"}
        atomic_write_json_report(payload, output)
        text = output.read_text(encoding="utf-8")
        assert "BTC/€" in text

    def test_returns_path(self, tmp_path: Path) -> None:
        output = tmp_path / "report.json"
        payload = {"key": "value"}
        result = atomic_write_json_report(payload, output)
        assert isinstance(result, Path)
        assert result == output

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        output = tmp_path / "report.json"
        output.write_text("old", encoding="utf-8")
        payload = {"new": "data"}
        atomic_write_json_report(payload, output)
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data == {"new": "data"}

    def test_no_temp_file_left(self, tmp_path: Path) -> None:
        output = tmp_path / "report.json"
        payload = {"key": "value"}
        atomic_write_json_report(payload, output)
        temps = list(tmp_path.glob("*.tmp"))
        assert len(temps) == 0

    def test_cleanup_on_failure(self, tmp_path: Path) -> None:
        output = tmp_path / "readonly" / "report.json"
        output.parent.mkdir(mode=0o555)
        payload = {"key": "value"}
        try:
            atomic_write_json_report(payload, output)
        except Exception:
            pass
        temps = list(tmp_path.glob("**/*.tmp"))
        assert len(temps) == 0


# ---------------------------------------------------------------------------
# atomic_write_markdown_report tests
# ---------------------------------------------------------------------------


class TestAtomicWriteMarkdownReport:
    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        output = tmp_path / "nested" / "report.md"
        content = "# Report"
        result = atomic_write_markdown_report(content, output)
        assert result == output
        assert output.exists()

    def test_writes_utf8_markdown(self, tmp_path: Path) -> None:
        output = tmp_path / "report.md"
        content = "# Report with €"
        atomic_write_markdown_report(content, output)
        text = output.read_text(encoding="utf-8")
        assert "# Report with €" in text

    def test_trailing_newline(self, tmp_path: Path) -> None:
        output = tmp_path / "report.md"
        content = "# Report"
        atomic_write_markdown_report(content, output)
        text = output.read_text(encoding="utf-8")
        assert text.endswith("\n")

    def test_returns_path(self, tmp_path: Path) -> None:
        output = tmp_path / "report.md"
        content = "# Report"
        result = atomic_write_markdown_report(content, output)
        assert isinstance(result, Path)
        assert result == output

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        output = tmp_path / "report.md"
        output.write_text("old", encoding="utf-8")
        content = "# New Report"
        atomic_write_markdown_report(content, output)
        text = output.read_text(encoding="utf-8")
        assert "# New Report" in text

    def test_no_temp_file_left(self, tmp_path: Path) -> None:
        output = tmp_path / "report.md"
        content = "# Report"
        atomic_write_markdown_report(content, output)
        temps = list(tmp_path.glob("*.tmp"))
        assert len(temps) == 0

    def test_cleanup_on_failure(self, tmp_path: Path) -> None:
        output = tmp_path / "readonly" / "report.md"
        output.parent.mkdir(mode=0o555)
        content = "# Report"
        try:
            atomic_write_markdown_report(content, output)
        except Exception:
            pass
        temps = list(tmp_path.glob("**/*.tmp"))
        assert len(temps) == 0


# ---------------------------------------------------------------------------
# write_observation_reports tests
# ---------------------------------------------------------------------------


class TestWriteObservationReports:
    def test_default_paths(self, tmp_path: Path, sample_report: ObservationReport) -> None:
        import hunter.observation.writer as writer_module
        original_json = writer_module.DEFAULT_OBSERVATION_JSON_REPORT_PATH
        original_md = writer_module.DEFAULT_OBSERVATION_MARKDOWN_REPORT_PATH
        try:
            writer_module.DEFAULT_OBSERVATION_JSON_REPORT_PATH = tmp_path / "obs.json"
            writer_module.DEFAULT_OBSERVATION_MARKDOWN_REPORT_PATH = tmp_path / "obs.md"
            json_path, md_path = write_observation_reports(sample_report)
            assert json_path == tmp_path / "obs.json"
            assert md_path == tmp_path / "obs.md"
            assert json_path.exists()
            assert md_path.exists()
            data = json.loads(json_path.read_text(encoding="utf-8"))
            assert data["report_state"] == "READY"
            md_text = md_path.read_text(encoding="utf-8")
            assert "# Observation Report" in md_text
        finally:
            writer_module.DEFAULT_OBSERVATION_JSON_REPORT_PATH = original_json
            writer_module.DEFAULT_OBSERVATION_MARKDOWN_REPORT_PATH = original_md

    def test_custom_paths(self, tmp_path: Path, sample_report: ObservationReport) -> None:
        json_out = tmp_path / "custom.json"
        md_out = tmp_path / "custom.md"
        json_path, md_path = write_observation_reports(
            sample_report,
            json_output_path=json_out,
            markdown_output_path=md_out,
        )
        assert json_path == json_out
        assert md_path == md_out
        assert json_out.exists()
        assert md_out.exists()

    def test_blocked_report(self, tmp_path: Path, blocked_report: ObservationReport) -> None:
        json_out = tmp_path / "blocked.json"
        md_out = tmp_path / "blocked.md"
        json_path, md_path = write_observation_reports(
            blocked_report,
            json_output_path=json_out,
            markdown_output_path=md_out,
        )
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["report_state"] == "BLOCKED"
        md_text = md_path.read_text(encoding="utf-8")
        assert "BLOCKED" in md_text

    def test_does_not_mutate_report(self, sample_report: ObservationReport, tmp_path: Path) -> None:
        original_reason_codes = sample_report.reason_codes
        original_summary = dict(sample_report.summary)
        write_observation_reports(
            sample_report,
            json_output_path=tmp_path / "test.json",
            markdown_output_path=tmp_path / "test.md",
        )
        assert sample_report.reason_codes == original_reason_codes
        assert dict(sample_report.summary) == original_summary


# ---------------------------------------------------------------------------
# Safety assertions
# ---------------------------------------------------------------------------


class TestWriterSafety:
    def test_no_production_data_reads(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        assert "data/" not in str(d)
        assert "production" not in str(d).lower()

    def test_no_execution_feedback(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        sf = d["safety_flags"]
        assert sf["execution_feedback_allowed"] is False

    def test_no_network_calls(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        sf = d["safety_flags"]
        assert sf["network_calls_allowed"] is False

    def test_no_database_persistence(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        sf = d["safety_flags"]
        assert sf["database_persistence_allowed"] is False

    def test_no_realtime_streaming(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        sf = d["safety_flags"]
        assert sf["realtime_streaming_allowed"] is False

    def test_no_api_keys(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        sf = d["safety_flags"]
        assert sf["api_keys_allowed"] is False

    def test_no_live_trading(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        sf = d["safety_flags"]
        assert sf["live_trading_enabled"] is False

    def test_no_real_orders(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        sf = d["safety_flags"]
        assert sf["real_orders_enabled"] is False

    def test_no_leverage(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        sf = d["safety_flags"]
        assert sf["leverage_enabled"] is False

    def test_no_shorting(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        sf = d["safety_flags"]
        assert sf["shorting_enabled"] is False

    def test_no_real_entry_exit(self, sample_report: ObservationReport) -> None:
        md = observation_report_to_markdown(sample_report)
        assert "enter_long" not in md.lower()
        assert "enter_short" not in md.lower()
        assert "exit_long" not in md.lower()
        assert "exit_short" not in md.lower()

    def test_no_report_feedback_into_execution(self, sample_report: ObservationReport) -> None:
        d = observation_report_to_dict(sample_report)
        sf = d["safety_flags"]
        assert sf["execution_feedback_allowed"] is False
        md = observation_report_to_markdown(sample_report)
        assert "must not be consumed by execution" in md

    def test_default_json_path(self) -> None:
        assert str(DEFAULT_OBSERVATION_JSON_REPORT_PATH) == "data/observation/latest_observation_report.json"

    def test_default_markdown_path(self) -> None:
        assert str(DEFAULT_OBSERVATION_MARKDOWN_REPORT_PATH) == "reports/observation/latest_observation_report.md"

    def test_no_freqtrade_import(self) -> None:
        import sys
        assert "freqtrade" not in sys.modules
