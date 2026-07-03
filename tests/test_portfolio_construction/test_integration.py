"""Integration tests for hunter.portfolio_construction.

MVP-27 Step 3 — End-to-end portfolio construction report flow.

These tests exercise the public API (engine + writer) with in-memory inputs
and tmp_path-only file I/O. They do not read external files, access the
network, or interact with exchanges.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.portfolio_construction import (
    PortfolioConstructionConfig,
    PortfolioConstructionInput,
    PortfolioConstructionReport,
    PortfolioConstructionState,
    PortfolioDiscoverySummary,
    apply_research_weight_caps,
    atomic_write_csv_portfolio_construction_report,
    atomic_write_json_portfolio_construction_report,
    atomic_write_markdown_portfolio_construction_report,
    build_portfolio_construction_report,
    build_portfolio_construction_score,
    build_portfolio_construction_universe_summary,
    calculate_initial_research_weights,
    portfolio_construction_report_to_csv_text,
    portfolio_construction_report_to_dict,
    portfolio_construction_report_to_json_text,
    portfolio_construction_report_to_markdown,
    write_portfolio_construction_report,
)


def _discovery(
    pair: str,
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


_NO_DISCOVERY = object()


def _input(
    pair: str,
    *,
    discovery: PortfolioDiscoverySummary | None | object = _NO_DISCOVERY,
    tags: tuple[str, ...] = (),
) -> PortfolioConstructionInput:
    if discovery is _NO_DISCOVERY:
        discovery = _discovery(pair=pair)
    return PortfolioConstructionInput(
        pair=pair,
        discovery=discovery,  # type: ignore[arg-type]
        tags=tags,
    )


def _build_inputs() -> list[PortfolioConstructionInput]:
    """Return a deterministic mix of candidate/excluded/blocked inputs."""
    return [
        _input("CORE1", discovery=_discovery("CORE1", discovery_score=95.0)),
        _input("CORE2", discovery=_discovery("CORE2", discovery_score=88.0)),
        _input("SAT1", discovery=_discovery("SAT1", discovery_score=70.0)),
        _input("WATCH1", discovery=_discovery("WATCH1", state="WATCHLIST", classification="WATCHLIST_ONLY", discovery_score=50.0)),
        _input("EXCL1", discovery=_discovery("EXCL1", state="EXCLUDED", classification="EXCLUDED_BY_FILTERS", discovery_score=30.0)),
    ]


_FIXED_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)


class TestBuildReport:
    def test_builds_deterministic_report_from_inputs(self) -> None:
        inputs = _build_inputs()
        report = build_portfolio_construction_report(
            inputs=inputs,
            report_id="integration-test",
            generated_at=_FIXED_AT,
        )
        assert isinstance(report, PortfolioConstructionReport)
        assert report.report_id == "integration-test"
        assert report.generated_at == _FIXED_AT
        assert len(report.inputs) == len(inputs)
        assert report.universe_summary.total_candidates == len(inputs)
        assert report.version == "0.27.0-dev"
        assert report.data_quality.safety_flags_ok is True

    def test_strong_candidates_produce_included_or_capped(self) -> None:
        inputs = [
            _input("STRONG1", discovery=_discovery("STRONG1", discovery_score=95.0)),
            _input("STRONG2", discovery=_discovery("STRONG2", discovery_score=92.0)),
        ]
        report = build_portfolio_construction_report(inputs=inputs)
        states = {s.state for s in report.scores}
        assert PortfolioConstructionState.INCLUDED in states or PortfolioConstructionState.CAPPED in states

    def test_watchlist_allocation_has_zero_weight(self) -> None:
        inputs = [
            _input("WATCH1", discovery=_discovery("WATCH1", state="WATCHLIST", classification="WATCHLIST_ONLY", discovery_score=45.0)),
        ]
        report = build_portfolio_construction_report(inputs=inputs)
        score = report.scores[0]
        assert score.state == PortfolioConstructionState.WATCHLIST
        assert score.initial_research_weight_pct == 0.0
        assert score.capped_weight_pct == 0.0
        assert score.final_weight_pct == 0.0

    def test_missing_context_with_block_false_is_insufficient_data(self) -> None:
        inputs = [_input("MISS1", discovery=None)]
        config = PortfolioConstructionConfig(
            require_discovery_context=True,
            block_on_missing_context=False,
        )
        report = build_portfolio_construction_report(inputs=inputs, config=config)
        score = report.scores[0]
        assert score.state == PortfolioConstructionState.INSUFFICIENT_DATA
        assert report.data_quality.missing_context_count == 1
        assert report.data_quality.insufficient_data_count == 1

    def test_blocked_context_with_block_true_is_blocked(self) -> None:
        inputs = [
            _input(
                "BLOCK1",
                discovery=_discovery("BLOCK1", state="BLOCKED", classification="BLOCKED", discovery_score=90.0),
            )
        ]
        config = PortfolioConstructionConfig(block_on_blocked_context=True)
        report = build_portfolio_construction_report(inputs=inputs, config=config)
        score = report.scores[0]
        assert score.state == PortfolioConstructionState.BLOCKED
        assert report.data_quality.blocked_context_count == 1
        assert report.data_quality.blocked_count == 1

    def test_include_excluded_false_omits_excluded_but_summary_counts_all(self) -> None:
        inputs = [
            _input("INC1", discovery=_discovery("INC1", discovery_score=95.0)),
            _input("EXCL1", discovery=_discovery("EXCL1", state="EXCLUDED", classification="EXCLUDED_BY_FILTERS", discovery_score=30.0)),
        ]
        config = PortfolioConstructionConfig(include_excluded_candidates=False)
        report = build_portfolio_construction_report(inputs=inputs, config=config)
        visible_states = {s.state for s in report.scores}
        assert PortfolioConstructionState.EXCLUDED not in visible_states
        assert PortfolioConstructionState.INCLUDED in visible_states or PortfolioConstructionState.CAPPED in visible_states
        assert report.universe_summary.excluded_count == 1
        assert report.universe_summary.total_candidates == 2
        assert report.data_quality.total_inputs == 2


class TestWriterFlow:
    def test_writer_writes_json_csv_markdown_under_tmp_path(self, tmp_path: Path) -> None:
        inputs = _build_inputs()
        report = build_portfolio_construction_report(inputs=inputs, generated_at=_FIXED_AT)
        json_path = tmp_path / "report.json"
        csv_path = tmp_path / "alloc.csv"
        md_path = tmp_path / "report.md"
        write_portfolio_construction_report(
            report,
            json_path=json_path,
            csv_path=csv_path,
            md_path=md_path,
        )
        assert json_path.exists()
        assert csv_path.exists()
        assert md_path.exists()
        # Confirm all files are under tmp_path.
        for path in (json_path, csv_path, md_path):
            assert str(path).startswith(str(tmp_path))

    def test_json_parses_csv_has_rows_markdown_has_h1_and_safety_notice(self, tmp_path: Path) -> None:
        inputs = _build_inputs()
        report = build_portfolio_construction_report(inputs=inputs, generated_at=_FIXED_AT)
        json_path = tmp_path / "report.json"
        csv_path = tmp_path / "alloc.csv"
        md_path = tmp_path / "report.md"
        write_portfolio_construction_report(
            report,
            json_path=json_path,
            csv_path=csv_path,
            md_path=md_path,
        )

        # JSON parses and matches report structure.
        data = json.loads(json_path.read_text())
        assert data["report_id"] == report.report_id
        assert data["version"] == report.version
        assert "generated_at" in data
        assert "scores" in data
        assert "universe_summary" in data

        # CSV has header plus rows for every visible score.
        csv_text = csv_path.read_text()
        rows = list(csv.reader(csv_text.splitlines()))
        assert len(rows) >= 2
        header = rows[0]
        assert "pair" in header
        assert "state" in header
        assert "final_weight_pct" in header

        # Markdown starts with H1 and then safety notice.
        md_text = md_path.read_text()
        lines = [line for line in md_text.splitlines() if line.strip()]
        assert lines[0] == "# Portfolio Construction Report"
        assert lines[1].startswith("> This local portfolio construction report")

    def test_same_input_fixed_generated_at_produces_identical_json(self, tmp_path: Path) -> None:
        inputs = _build_inputs()
        report1 = build_portfolio_construction_report(
            inputs=inputs,
            report_id="deterministic",
            generated_at=_FIXED_AT,
        )
        report2 = build_portfolio_construction_report(
            inputs=inputs,
            report_id="deterministic",
            generated_at=_FIXED_AT,
        )
        text1 = portfolio_construction_report_to_json_text(report1)
        text2 = portfolio_construction_report_to_json_text(report2)
        assert text1 == text2
        # Also assert that the file can be written and read back identically.
        json_path = tmp_path / "report.json"
        atomic_write_json_portfolio_construction_report(report1, json_path)
        assert json_path.read_text() == text1


class TestPublicApiExports:
    def test_public_exports_include_report_builder_and_writers(self) -> None:
        from hunter.portfolio_construction import (
            build_portfolio_construction_report,
            portfolio_construction_report_to_csv_text,
            portfolio_construction_report_to_dict,
            portfolio_construction_report_to_json_text,
            portfolio_construction_report_to_markdown,
            write_portfolio_construction_report,
        )

        assert callable(build_portfolio_construction_report)
        assert callable(write_portfolio_construction_report)
        assert callable(portfolio_construction_report_to_dict)
        assert callable(portfolio_construction_report_to_json_text)
        assert callable(portfolio_construction_report_to_csv_text)
        assert callable(portfolio_construction_report_to_markdown)
