"""Tests for hunter.discovery.writer."""

from __future__ import annotations

import csv
import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.discovery import (
    DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    DiscoveryConfig,
    DiscoveryInput,
    DiscoveryOpenInterestSummary,
    DiscoveryRelativeStrengthSummary,
    DiscoveryReport,
    build_discovery_report,
)
from hunter.discovery.writer import (
    atomic_write_csv_discovery_report,
    atomic_write_json_discovery_report,
    atomic_write_markdown_discovery_report,
    discovery_report_to_csv_text,
    discovery_report_to_dict,
    discovery_report_to_json_text,
    discovery_report_to_markdown,
    write_discovery_report,
)

REPORT_ID = "test-discovery-report"


def _rs(
    pair: str = "BTCUSDT",
    *,
    state: str = "READY",
    total_score: float | None = 80.0,
    decision: str = "OUTPERFORMER",
    rank_percentile_30d: float | None = 70.0,
) -> DiscoveryRelativeStrengthSummary:
    return DiscoveryRelativeStrengthSummary(
        pair=pair,
        state=state,
        decision=decision,
        total_score=total_score,
        rank_percentile_30d=rank_percentile_30d,
    )


def _oi(
    pair: str = "BTCUSDT",
    *,
    state: str = "READY",
    total_score: float | None = 70.0,
    positioning: str = "PRICE_UP_OI_UP",
    trend: str = "EXPANDING",
    funding_context: str = "POSITIVE",
) -> DiscoveryOpenInterestSummary:
    return DiscoveryOpenInterestSummary(
        pair=pair,
        state=state,
        positioning=positioning,
        trend=trend,
        funding_context=funding_context,
        total_score=total_score,
    )


def _make_inputs() -> tuple[DiscoveryInput, ...]:
    return (
        DiscoveryInput(
            pair="BTCUSDT",
            relative_strength=_rs(pair="BTCUSDT"),
            open_interest=_oi(pair="BTCUSDT"),
            tags=("large-cap", "bitcoin"),
            metadata={"source": "test"},
        ),
        DiscoveryInput(
            pair="ETHUSDT",
            relative_strength=_rs(pair="ETHUSDT", total_score=55.0, decision="NEUTRAL"),
            open_interest=_oi(pair="ETHUSDT", total_score=48.0, positioning="MIXED", trend="FLAT"),
            tags=("altcoin",),
            metadata={"source": "test"},
        ),
    )


def _make_report(**kwargs: object) -> DiscoveryReport:
    config = DiscoveryConfig()
    inputs = _make_inputs()
    return build_discovery_report(
        inputs=inputs,
        config=config,
        report_id=REPORT_ID,
        generated_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        metadata={"generator": "test"},
        **kwargs,
    )


class TestDictSerialization:
    def test_round_trip_types(self) -> None:
        report = _make_report()
        data = discovery_report_to_dict(report)
        assert data["report_id"] == REPORT_ID
        assert data["version"] == "0.26.0-dev"
        assert data["generated_at"] == "2026-01-15T12:00:00+00:00"
        assert isinstance(data["config"], dict)
        assert isinstance(data["inputs"], list)
        assert isinstance(data["candidates"], list)
        assert isinstance(data["universe_summary"], dict)
        assert isinstance(data["data_quality"], dict)
        assert isinstance(data["safety_flags"], dict)
        assert isinstance(data["reason_codes"], list)
        assert isinstance(data["metadata"], dict)

    def test_enum_values_are_strings(self) -> None:
        report = _make_report()
        data = discovery_report_to_dict(report)
        candidate_data = data["candidates"][0]
        assert isinstance(candidate_data["state"], str)
        assert isinstance(candidate_data["classification"], str)
        assert candidate_data["state"] in {"CANDIDATE", "WATCHLIST", "EXCLUDED", "INSUFFICIENT_DATA", "BLOCKED"}
        assert candidate_data["classification"] in {
            "STRONG_RESEARCH_CANDIDATE",
            "MODERATE_RESEARCH_CANDIDATE",
            "WATCHLIST_ONLY",
            "EXCLUDED_BY_FILTERS",
            "INSUFFICIENT_DATA",
            "BLOCKED",
        }
        input_data = data["inputs"][0]
        assert isinstance(input_data["input_kind"], str)
        assert input_data["input_kind"] in {"SUMMARY", "RELATIVE_STRENGTH", "OPEN_INTEREST"}

    def test_datetimes_are_iso(self) -> None:
        report = _make_report()
        data = discovery_report_to_dict(report)
        assert data["generated_at"] == "2026-01-15T12:00:00+00:00"

    def test_tuples_are_lists(self) -> None:
        report = _make_report()
        data = discovery_report_to_dict(report)
        candidate_data = data["candidates"][0]
        assert isinstance(candidate_data["reason_codes"], list)
        assert isinstance(candidate_data["tags"], list)
        input_data = data["inputs"][0]
        assert isinstance(input_data["tags"], list)

    def test_mappings_are_plain_dicts_sorted(self) -> None:
        report = _make_report()
        data = discovery_report_to_dict(report)
        assert isinstance(data["metadata"], dict)
        assert list(data["metadata"].keys()) == ["generator"]
        config = data["config"]
        assert isinstance(config["score_weights"], dict)
        assert list(config["score_weights"].keys()) == sorted(config["score_weights"].keys())


class TestJsonText:
    def test_deterministic_output(self) -> None:
        report = _make_report()
        first = discovery_report_to_json_text(report)
        second = discovery_report_to_json_text(report)
        assert first == second
        assert first.endswith("\n")

    def test_is_valid_json(self) -> None:
        report = _make_report()
        text = discovery_report_to_json_text(report)
        data = json.loads(text)
        assert data["report_id"] == REPORT_ID


class TestCsvText:
    def test_header_and_rows(self) -> None:
        report = _make_report()
        text = discovery_report_to_csv_text(report)
        lines = text.strip().split("\n")
        expected_header = (
            "report_id,generated_at,pair,state,classification,total_score,"
            "relative_strength_score,open_interest_score,alignment_score,"
            "data_quality_score,filter_bonus_score,reason_codes,human_note,"
            "tags,input_kind"
        )
        assert lines[0] == expected_header
        assert len(lines) == len(report.candidates) + 1

    def test_none_values_empty(self) -> None:
        report = _make_report()
        text = discovery_report_to_csv_text(report)
        reader = csv.reader(text.splitlines())
        rows = list(reader)
        # human_note is always empty because DiscoveryCandidate has no human_note field.
        assert rows[0][12] == "human_note"
        for row in rows[1:]:
            assert row[12] == ""

    def test_tags_as_pipe_delimited(self) -> None:
        report = _make_report()
        text = discovery_report_to_csv_text(report)
        reader = csv.reader(text.splitlines())
        rows = list(reader)
        btc_row = next(row for row in rows[1:] if row[2] == "BTCUSDT")
        assert btc_row[13] == "large-cap|bitcoin"

    def test_reason_codes_as_pipe_delimited(self) -> None:
        report = _make_report()
        text = discovery_report_to_csv_text(report)
        reader = csv.reader(text.splitlines())
        rows = list(reader)
        for row in rows[1:]:
            assert "|" in row[11] or row[11] == ""

    def test_input_kind_column(self) -> None:
        report = _make_report()
        text = discovery_report_to_csv_text(report)
        reader = csv.reader(text.splitlines())
        rows = list(reader)
        for row in rows[1:]:
            assert row[14] == "SUMMARY"


class TestMarkdown:
    def test_starts_with_h1_then_safety_notice(self) -> None:
        report = _make_report()
        text = discovery_report_to_markdown(report)
        lines = text.splitlines()
        assert lines[0] == "# Discovery Report"
        assert lines[1] == ""
        assert lines[2].startswith("> ")
        assert "human-audit" in lines[2].lower() or "research-only" in lines[2].lower()
        assert "not a trading signal" in lines[2]

    def test_contains_report_identity(self) -> None:
        report = _make_report()
        text = discovery_report_to_markdown(report)
        assert "## Report Identity" in text
        assert f"**report_id**: {REPORT_ID}" in text

    def test_contains_universe_summary(self) -> None:
        report = _make_report()
        text = discovery_report_to_markdown(report)
        assert "## Universe Summary" in text

    def test_contains_data_quality(self) -> None:
        report = _make_report()
        text = discovery_report_to_markdown(report)
        assert "## Data Quality" in text

    def test_contains_candidate_table(self) -> None:
        report = _make_report()
        text = discovery_report_to_markdown(report)
        assert "## Candidate Table" in text

    def test_contains_reason_codes_section(self) -> None:
        report = _make_report()
        text = discovery_report_to_markdown(report)
        assert "## Reason Codes" in text

    def test_contains_filter_diagnostics(self) -> None:
        report = _make_report()
        text = discovery_report_to_markdown(report)
        assert "## Filter Diagnostics" in text

    def test_contains_safety_flags(self) -> None:
        report = _make_report()
        text = discovery_report_to_markdown(report)
        assert "## Safety Flags" in text

    def test_no_actionable_trading_language_outside_notice(self) -> None:
        report = _make_report()
        text = discovery_report_to_markdown(report)
        lines = text.splitlines()
        # The safety notice is the first blockquote; everything after it must not
        # contain actionable trading/order/execution language.
        notice_end = 0
        for i, line in enumerate(lines):
            if line.startswith("> "):
                notice_end = i
        remaining = "\n".join(lines[notice_end + 1 :])
        actionable_terms = [
            "buy",
            "sell",
            "long",
            "short",
            "enter",
            "entry",
            "exit",
            "stop loss",
            "take profit",
            "leverage",
            "action command",
            "execution approval",
            "trade approval",
            "order suggestion",
        ]
        lower_remaining = remaining.lower()
        for term in actionable_terms:
            assert term not in lower_remaining, f"found actionable term {term!r}"


class TestAtomicWrites:
    def test_atomic_json_write_creates_parent_directory(self, tmp_path: Path) -> None:
        report = _make_report()
        target = tmp_path / "nested" / "report.json"
        path = atomic_write_json_discovery_report(report, target)
        assert path == target
        assert path.exists()
        assert path.parent.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["report_id"] == REPORT_ID

    def test_atomic_csv_write_creates_parent_directory(self, tmp_path: Path) -> None:
        report = _make_report()
        target = tmp_path / "nested" / "candidates.csv"
        path = atomic_write_csv_discovery_report(report, target)
        assert path == target
        assert path.exists()
        assert path.parent.exists()
        text = path.read_text(encoding="utf-8")
        assert "pair,state,classification" in text

    def test_atomic_markdown_write_creates_parent_directory(self, tmp_path: Path) -> None:
        report = _make_report()
        target = tmp_path / "nested" / "report.md"
        path = atomic_write_markdown_discovery_report(report, target)
        assert path == target
        assert path.exists()
        assert path.parent.exists()
        text = path.read_text(encoding="utf-8")
        assert text.startswith("# Discovery Report")


class TestWriteDiscoveryReport:
    def test_writes_all_artifacts(self, tmp_path: Path) -> None:
        report = _make_report()
        json_path = tmp_path / "out.json"
        csv_path = tmp_path / "out.csv"
        md_path = tmp_path / "out.md"
        json_out, csv_out, md_out = write_discovery_report(
            report,
            json_path=json_path,
            csv_path=csv_path,
            md_path=md_path,
        )
        assert json_out == json_path
        assert csv_out == csv_path
        assert md_out == md_path
        assert json_path.exists()
        assert csv_path.exists()
        assert md_path.exists()

    def test_skip_none_paths(self, tmp_path: Path) -> None:
        report = _make_report()
        json_path = tmp_path / "out.json"
        json_out, csv_out, md_out = write_discovery_report(
            report,
            json_path=json_path,
            csv_path=None,
            md_path=None,
        )
        assert json_out == json_path
        assert csv_out is None
        assert md_out is None


class TestReportMutation:
    def test_writer_does_not_mutate_report(self) -> None:
        report = _make_report()
        original = dataclasses.replace(report)
        discovery_report_to_dict(report)
        discovery_report_to_json_text(report)
        discovery_report_to_csv_text(report)
        discovery_report_to_markdown(report)
        assert report == original


class TestBlockedReport:
    def test_blocked_report_serialization(self) -> None:
        report = DiscoveryReport.blocked(
            reason_code="INVALID_PAIR",
            report_id="blocked-test",
            generated_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        )
        data = discovery_report_to_dict(report)
        assert data["report_id"] == "blocked-test"
        assert data["candidates"] == []
        assert data["inputs"] == []
        text = discovery_report_to_csv_text(report)
        lines = text.strip().split("\n")
        assert len(lines) == 1
        assert lines[0].startswith("report_id")
        md = discovery_report_to_markdown(report)
        assert "# Discovery Report" in md


class TestInsufficientDataReport:
    def test_insufficient_data_serialization(self) -> None:
        inputs = (
            DiscoveryInput(
                pair="BTCUSDT",
                relative_strength=_rs(pair="BTCUSDT", state="INSUFFICIENT_DATA"),
            ),
        )
        report = build_discovery_report(
            inputs=inputs,
            config=DiscoveryConfig(block_on_missing_context=False),
            report_id=REPORT_ID,
            generated_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        )
        data = discovery_report_to_dict(report)
        assert data["candidates"][0]["state"] == "INSUFFICIENT_DATA"
        assert data["candidates"][0]["classification"] == "INSUFFICIENT_DATA"
        text = discovery_report_to_csv_text(report)
        reader = csv.reader(text.splitlines())
        rows = list(reader)
        assert rows[1][3] == "INSUFFICIENT_DATA"
        assert rows[1][4] == "INSUFFICIENT_DATA"


class TestExcludedCandidates:
    def test_excluded_candidate_included_by_default(self) -> None:
        inputs = (
            DiscoveryInput(
                pair="BTCUSDT",
                relative_strength=_rs(pair="BTCUSDT", total_score=10.0, decision="NEUTRAL"),
                open_interest=_oi(pair="BTCUSDT", total_score=10.0, positioning="MIXED", trend="FLAT"),
            ),
        )
        report = build_discovery_report(
            inputs=inputs,
            config=DiscoveryConfig(),
            report_id=REPORT_ID,
            generated_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert report.candidates[0].state.value == "EXCLUDED"
        text = discovery_report_to_csv_text(report)
        reader = csv.reader(text.splitlines())
        rows = list(reader)
        assert len(rows) == 2
        assert rows[1][3] == "EXCLUDED"

    def test_excluded_candidate_omitted_when_configured(self) -> None:
        inputs = (
            DiscoveryInput(
                pair="BTCUSDT",
                relative_strength=_rs(pair="BTCUSDT", total_score=10.0, decision="NEUTRAL"),
                open_interest=_oi(pair="BTCUSDT", total_score=10.0, positioning="MIXED", trend="FLAT"),
            ),
        )
        report = build_discovery_report(
            inputs=inputs,
            config=DiscoveryConfig(include_excluded_candidates=False),
            report_id=REPORT_ID,
            generated_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert len(report.candidates) == 0
        assert report.universe_summary.excluded_count == 1
        text = discovery_report_to_csv_text(report)
        reader = csv.reader(text.splitlines())
        rows = list(reader)
        assert len(rows) == 1


class TestDefaultPaths:
    def test_default_paths_exported(self) -> None:
        assert DEFAULT_JSON_PATH == Path("data/discovery/latest_discovery_report.json")
        assert DEFAULT_CSV_PATH == Path("data/discovery/latest_discovery_candidates.csv")
        assert DEFAULT_MD_PATH == Path("reports/discovery/latest_discovery_report.md")


class TestNoFileReads:
    def test_writer_does_not_read_input_files(self) -> None:
        report = _make_report()
        # If the writer tried to read anything, it would need a path; inputs are already in-memory.
        # This test exercises the writer functions and confirms no FileNotFoundError is raised.
        discovery_report_to_dict(report)
        discovery_report_to_json_text(report)
        discovery_report_to_csv_text(report)
        discovery_report_to_markdown(report)
        assert True
