"""Tests for hunter.portfolio_construction.writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from hunter.portfolio_construction.engine import build_portfolio_construction_report
from hunter.portfolio_construction.models import (
    PortfolioConstructionClassification,
    PortfolioConstructionConfig,
    PortfolioConstructionInput,
    PortfolioConstructionReport,
    PortfolioConstructionScore,
    PortfolioConstructionState,
    PortfolioDiscoverySummary,
)
from hunter.portfolio_construction.writer import (
    DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    atomic_write_csv_portfolio_construction_report,
    atomic_write_json_portfolio_construction_report,
    atomic_write_markdown_portfolio_construction_report,
    portfolio_construction_report_to_csv_text,
    portfolio_construction_report_to_dict,
    portfolio_construction_report_to_json_text,
    portfolio_construction_report_to_markdown,
    write_portfolio_construction_report,
)


def _discovery(
    pair: str = "SOL/USDT:USDT",
    *,
    state: str = "CANDIDATE",
    classification: str = "STRONG_RESEARCH_CANDIDATE",
    discovery_score: float | None = 80.0,
) -> PortfolioDiscoverySummary:
    return PortfolioDiscoverySummary(
        pair=pair,
        state=state,
        classification=classification,
        discovery_score=discovery_score,
    )


def _input(
    pair: str = "SOL/USDT:USDT",
    *,
    discovery: PortfolioDiscoverySummary | None = None,
    tags: tuple[str, ...] = (),
) -> PortfolioConstructionInput:
    if discovery is None:
        discovery = _discovery(pair=pair)
    return PortfolioConstructionInput(
        pair=pair,
        discovery=discovery,
        tags=tags,
    )


def _simple_report() -> PortfolioConstructionReport:
    inputs = [
        _input(pair="A", discovery=_discovery(pair="A", discovery_score=95.0)),
        _input(pair="B", discovery=_discovery(pair="B", discovery_score=80.0)),
        _input(pair="C", discovery=_discovery(pair="C", state="WATCHLIST", classification="WATCHLIST_ONLY", discovery_score=40.0)),
    ]
    return build_portfolio_construction_report(inputs=inputs)


class TestDictSerialization:
    def test_enums_serialize_as_strings(self) -> None:
        report = _simple_report()
        data = portfolio_construction_report_to_dict(report)
        score = data["scores"][0]
        assert isinstance(score["state"], str)
        assert isinstance(score["classification"], str)
        assert score["state"] in {s.value for s in PortfolioConstructionState}

    def test_datetime_iso8601(self) -> None:
        report = _simple_report()
        data = portfolio_construction_report_to_dict(report)
        assert data["generated_at"].endswith("+00:00")
        datetime.fromisoformat(data["generated_at"])

    def test_tuples_as_lists(self) -> None:
        report = _simple_report()
        data = portfolio_construction_report_to_dict(report)
        assert isinstance(data["scores"][0]["reason_codes"], list)
        assert isinstance(data["scores"][0]["tags"], list)

    def test_mappings_as_sorted_dicts(self) -> None:
        report = _simple_report()
        data = portfolio_construction_report_to_dict(report)
        assert isinstance(data["metadata"], dict)
        keys = list(data["metadata"].keys())
        assert keys == sorted(keys)


class TestJsonText:
    def test_deterministic(self) -> None:
        report = _simple_report()
        text1 = portfolio_construction_report_to_json_text(report)
        text2 = portfolio_construction_report_to_json_text(report)
        assert text1 == text2
        assert text1.endswith("\n")
        data = json.loads(text1)
        assert data["version"] == report.version

    def test_trailing_newline(self) -> None:
        report = _simple_report()
        text = portfolio_construction_report_to_json_text(report)
        assert text[-1] == "\n"


class TestCsvText:
    def test_header_and_rows(self) -> None:
        report = _simple_report()
        text = portfolio_construction_report_to_csv_text(report)
        lines = text.strip().split("\n")
        assert len(lines) == len(report.scores) + 1
        header = lines[0].split(",")
        assert "pair" in header
        assert "state" in header
        assert "classification" in header
        assert "allocation_score" in header
        assert "final_weight_pct" in header

    def test_none_rank_empty(self) -> None:
        report = _simple_report()
        text = portfolio_construction_report_to_csv_text(report)
        lines = text.strip().split("\n")
        for row in lines[1:]:
            assert "None" not in row

    def test_tags_pipe_delimited(self) -> None:
        report = _simple_report()
        text = portfolio_construction_report_to_csv_text(report)
        lines = text.strip().split("\n")
        assert any("|" in line for line in lines[1:])

    def test_weight_fields_present(self) -> None:
        report = _simple_report()
        text = portfolio_construction_report_to_csv_text(report)
        header = text.strip().split("\n")[0]
        assert "initial_research_weight_pct" in header
        assert "capped_weight_pct" in header
        assert "final_weight_pct" in header


class TestMarkdown:
    def test_starts_with_h1_then_safety_notice(self) -> None:
        report = _simple_report()
        text = portfolio_construction_report_to_markdown(report)
        lines = [line for line in text.split("\n") if line.strip()]
        assert lines[0] == "# Portfolio Construction Report"
        assert lines[1].startswith("> This local portfolio construction report")

    def test_no_actionable_instructions(self) -> None:
        report = _simple_report()
        text = portfolio_construction_report_to_markdown(report)
        # Skip the required safety notice; it legitimately mentions order/trade/execute as disclaimers.
        lines = [line for line in text.split("\n") if not line.startswith("> ")]
        body = "\n".join(lines).lower()
        for bad in ("buy", "sell", "place order", "execute trade", "rebalance now", "position size"):
            assert bad not in body, f"found actionable term: {bad}"

    def test_contains_allocation_table(self) -> None:
        report = _simple_report()
        text = portfolio_construction_report_to_markdown(report)
        assert "## Allocation Table" in text

    def test_contains_cap_diagnostics(self) -> None:
        report = _simple_report()
        text = portfolio_construction_report_to_markdown(report)
        assert "## Cap Diagnostics" in text


class TestAtomicWrites:
    def test_atomic_json_creates_parent_dir(self, tmp_path) -> None:
        report = _simple_report()
        path = tmp_path / "nested" / "report.json"
        atomic_write_json_portfolio_construction_report(report, path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["report_id"] == report.report_id

    def test_atomic_csv_creates_parent_dir(self, tmp_path) -> None:
        report = _simple_report()
        path = tmp_path / "nested" / "alloc.csv"
        atomic_write_csv_portfolio_construction_report(report, path)
        assert path.exists()
        assert "," in path.read_text()

    def test_atomic_markdown_creates_parent_dir(self, tmp_path) -> None:
        report = _simple_report()
        path = tmp_path / "nested" / "report.md"
        atomic_write_markdown_portfolio_construction_report(report, path)
        assert path.exists()
        assert path.read_text().startswith("# Portfolio Construction Report")


class TestWriteReport:
    def test_writes_all_artifacts(self, tmp_path) -> None:
        report = _simple_report()
        json_path = tmp_path / "report.json"
        csv_path = tmp_path / "alloc.csv"
        md_path = tmp_path / "report.md"
        write_portfolio_construction_report(
            report, json_path=json_path, csv_path=csv_path, md_path=md_path
        )
        assert json_path.exists()
        assert csv_path.exists()
        assert md_path.exists()

    def test_can_skip_format(self, tmp_path) -> None:
        report = _simple_report()
        json_path = tmp_path / "report.json"
        write_portfolio_construction_report(
            report, json_path=json_path, csv_path=None, md_path=None
        )
        assert json_path.exists()
        assert not (tmp_path / "alloc.csv").exists()
        assert not (tmp_path / "report.md").exists()

    def test_does_not_mutate_report(self, tmp_path) -> None:
        report = _simple_report()
        before = portfolio_construction_report_to_json_text(report)
        write_portfolio_construction_report(report, json_path=tmp_path / "r.json")
        after = portfolio_construction_report_to_json_text(report)
        assert before == after


class TestEdgeReports:
    def test_blocked_report(self) -> None:
        report = PortfolioConstructionReport.blocked(reason_code="UNSAFE_PORTFOLIO_CONSTRUCTION_CONTENT")
        text = portfolio_construction_report_to_json_text(report)
        data = json.loads(text)
        assert data["safety_flags"]["has_unsafe_content"] is True
        assert data["scores"] == []

    def test_insufficient_data_report(self) -> None:
        inputs = [_input(discovery=_discovery(state="INSUFFICIENT_DATA", classification="INSUFFICIENT_DATA", discovery_score=None))]
        report = build_portfolio_construction_report(inputs=inputs)
        text = portfolio_construction_report_to_csv_text(report)
        assert "INSUFFICIENT_DATA" in text

    def test_watchlist_zero_weight(self) -> None:
        inputs = [_input(discovery=_discovery(state="WATCHLIST", classification="WATCHLIST_ONLY", discovery_score=40.0))]
        report = build_portfolio_construction_report(inputs=inputs)
        score = report.scores[0]
        assert score.final_weight_pct == 0.0

    def test_excluded_omitted_when_flag_false(self) -> None:
        inputs = [
            _input(pair="A", discovery=_discovery(pair="A", state="EXCLUDED", classification="EXCLUDED_BY_FILTERS", discovery_score=30.0)),
            _input(pair="B", discovery=_discovery(pair="B", state="CANDIDATE", discovery_score=80.0)),
        ]
        report = build_portfolio_construction_report(inputs=inputs, config=PortfolioConstructionConfig(include_excluded_candidates=False))
        csv_text = portfolio_construction_report_to_csv_text(report)
        assert "EXCLUDED" not in csv_text
        assert "B" in csv_text


class TestDefaultPaths:
    def test_default_paths_exported(self) -> None:
        assert str(DEFAULT_JSON_PATH) == "data/portfolio_construction/latest_portfolio_construction_report.json"
        assert str(DEFAULT_CSV_PATH) == "data/portfolio_construction/latest_portfolio_construction_allocations.csv"
        assert str(DEFAULT_MD_PATH) == "reports/portfolio_construction/latest_portfolio_construction_report.md"
