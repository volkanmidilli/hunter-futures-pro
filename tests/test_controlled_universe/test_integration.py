"""Integration tests for the controlled_universe package.

End-to-end flows: build a real ControlledUniverseReport via the engine and
serialize it with the writer. No file reads; all data is fabricated in-memory.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from hunter.controlled_universe import (
    AllowedMode,
    ControlledUniverseClassification,
    ControlledUniverseConfig,
    ControlledUniverseItem,
    ControlledUniverseReport,
    ControlledUniverseState,
    atomic_write_csv_controlled_universe_report,
    atomic_write_json_controlled_universe_report,
    atomic_write_markdown_controlled_universe_report,
    build_controlled_universe_report,
    classify_controlled_universe_item,
    controlled_universe_report_to_csv_text,
    controlled_universe_report_to_json_text,
    controlled_universe_report_to_markdown,
    write_controlled_universe_report,
)
from hunter.decision.models import DecisionAction, DecisionState
from hunter.execution.models import (
    DataQuality,
    ExecutionContext,
    ExecutionMode,
    ExecutionSafetyFlags,
    ExecutionState,
    OutputStatus,
)
from hunter.market_state.models import AllowedMode as MarketAllowedMode
from hunter.portfolio_construction.models import (
    PortfolioConstructionClassification,
    PortfolioConstructionConfig,
    PortfolioConstructionDataQuality,
    PortfolioConstructionReport,
    PortfolioConstructionSafetyFlags,
    PortfolioConstructionScore,
    PortfolioConstructionState,
    PortfolioConstructionUniverseSummary,
)


def _dt() -> datetime:
    return datetime.now(timezone.utc)


def _minimal_safety_flags() -> PortfolioConstructionSafetyFlags:
    return PortfolioConstructionSafetyFlags()


def _minimal_data_quality(
    total_inputs: int = 0,
    included_count: int = 0,
    capped_count: int = 0,
    watchlist_count: int = 0,
    excluded_count: int = 0,
    insufficient_data_count: int = 0,
    blocked_count: int = 0,
) -> PortfolioConstructionDataQuality:
    return PortfolioConstructionDataQuality(
        total_inputs=total_inputs,
        included_count=included_count,
        capped_count=capped_count,
        watchlist_count=watchlist_count,
        excluded_count=excluded_count,
        insufficient_data_count=insufficient_data_count,
        blocked_count=blocked_count,
        ready_context_count=0,
        missing_context_count=0,
        blocked_context_count=0,
        total_final_weight_pct=0.0,
        total_research_weight_pct=100.0,
        data_quality_score=0.0,
        sections_present=0,
        all_sections_present=True,
        all_counts_consistent=True,
        total_weight_within_tolerance=True,
        has_unsafe_content=False,
        safety_flags_ok=True,
    )


def _score(
    pair: str,
    state: PortfolioConstructionState = PortfolioConstructionState.INCLUDED,
    classification: PortfolioConstructionClassification = PortfolioConstructionClassification.CORE_RESEARCH_ALLOCATION,
    allocation_score: float = 80.0,
) -> PortfolioConstructionScore:
    return PortfolioConstructionScore(
        pair=pair,
        state=state,
        classification=classification,
        allocation_score=allocation_score,
        discovery_score_component=0.0,
        data_quality_score=0.0,
        diversification_component=0.0,
        cap_readiness_score=0.0,
        filter_bonus_score=0.0,
        initial_research_weight_pct=0.0,
        capped_weight_pct=0.0,
        final_weight_pct=0.0,
        reason_codes=(),
        tags=(),
        metadata={},
        notes=(),
        rank=None,
    )


def _universe_summary(
    total_candidates: int,
    included_count: int = 0,
    capped_count: int = 0,
    watchlist_count: int = 0,
    excluded_count: int = 0,
    insufficient_data_count: int = 0,
    blocked_count: int = 0,
) -> PortfolioConstructionUniverseSummary:
    return PortfolioConstructionUniverseSummary(
        total_candidates=total_candidates,
        included_count=included_count,
        capped_count=capped_count,
        watchlist_count=watchlist_count,
        excluded_count=excluded_count,
        insufficient_data_count=insufficient_data_count,
        blocked_count=blocked_count,
        core_allocation_count=0,
        satellite_allocation_count=0,
        watchlist_allocation_count=0,
        total_final_weight_pct=0.0,
        top_pair=None,
        notes=(),
    )


def _portfolio_report(*scores: PortfolioConstructionScore) -> PortfolioConstructionReport:
    counts = {
        PortfolioConstructionState.INCLUDED: 0,
        PortfolioConstructionState.CAPPED: 0,
        PortfolioConstructionState.WATCHLIST: 0,
        PortfolioConstructionState.EXCLUDED: 0,
        PortfolioConstructionState.INSUFFICIENT_DATA: 0,
        PortfolioConstructionState.BLOCKED: 0,
    }
    for score in scores:
        counts[score.state] += 1
    total = len(scores)
    return PortfolioConstructionReport(
        version="0.27.0-dev",
        report_id="portfolio-report-1",
        generated_at=_dt(),
        inputs=(),
        config=PortfolioConstructionConfig(),
        safety_flags=_minimal_safety_flags(),
        scores=scores,
        universe_summary=_universe_summary(
            total_candidates=total,
            included_count=counts[PortfolioConstructionState.INCLUDED],
            capped_count=counts[PortfolioConstructionState.CAPPED],
            watchlist_count=counts[PortfolioConstructionState.WATCHLIST],
            excluded_count=counts[PortfolioConstructionState.EXCLUDED],
            insufficient_data_count=counts[PortfolioConstructionState.INSUFFICIENT_DATA],
            blocked_count=counts[PortfolioConstructionState.BLOCKED],
        ),
        data_quality=_minimal_data_quality(
            total_inputs=total,
            included_count=counts[PortfolioConstructionState.INCLUDED],
            capped_count=counts[PortfolioConstructionState.CAPPED],
            watchlist_count=counts[PortfolioConstructionState.WATCHLIST],
            excluded_count=counts[PortfolioConstructionState.EXCLUDED],
            insufficient_data_count=counts[PortfolioConstructionState.INSUFFICIENT_DATA],
            blocked_count=counts[PortfolioConstructionState.BLOCKED],
        ),
        reason_codes=(),
        metadata={},
        notes=(),
    )


def _execution_context(
    execution_state: ExecutionState = ExecutionState.DRY_RUN_ONLY,
    execution_mode: ExecutionMode = ExecutionMode.DRY_RUN_ONLY,
    allowed_mode: MarketAllowedMode = MarketAllowedMode.LONG_ONLY,
    status: OutputStatus = OutputStatus.VALID,
    data_quality: DataQuality | None = None,
) -> ExecutionContext:
    return ExecutionContext(
        timestamp=_dt(),
        status=status,
        execution_state=execution_state,
        execution_mode=execution_mode,
        decision_state=DecisionState.ALLOW,
        decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
        allowed_mode=allowed_mode,
        dry_run=True,
        live_trading_enabled=False,
        exchange_connection_enabled=False,
        freqtrade_enabled=False,
        reason_codes=[],
        data_quality=data_quality or DataQuality(),
        safety_flags=ExecutionSafetyFlags(),
        version="1.0",
    )


def _config() -> ControlledUniverseConfig:
    return ControlledUniverseConfig(
        max_universe_pairs=5,
        min_portfolio_score=60.0,
        max_watchlist_pairs=3,
        include_capped=True,
        default_mode=AllowedMode.LONG_ONLY,
        require_dry_run=True,
    )


class TestEngineWriterIntegration:
    def test_engine_report_to_json_text(self) -> None:
        portfolio = _portfolio_report(
            _score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
            _score("ETH/USDT", PortfolioConstructionState.WATCHLIST, allocation_score=70.0),
            _score("DOGE/USDT", PortfolioConstructionState.BLOCKED, allocation_score=10.0),
        )
        execution = _execution_context()
        report = build_controlled_universe_report(portfolio, execution, _config())
        text = controlled_universe_report_to_json_text(report)
        data = json.loads(text)
        assert data["kind"] == "controlled_universe_report"
        assert data["execution_state"] == "DRY_RUN_ONLY"
        assert data["allowed_mode"] == "LONG_ONLY"
        assert len(data["items"]) == 3
        assert data["data_quality"]["universe_count"] == 1
        assert data["data_quality"]["watchlist_count"] == 1
        assert data["data_quality"]["blocked_count"] == 1

    def test_engine_report_to_csv_text(self) -> None:
        portfolio = _portfolio_report(
            _score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
            _score("ETH/USDT", PortfolioConstructionState.WATCHLIST, allocation_score=70.0),
        )
        execution = _execution_context()
        report = build_controlled_universe_report(portfolio, execution, _config())
        text = controlled_universe_report_to_csv_text(report)
        rows = list(csv.reader(text.splitlines()))
        assert rows[0] == [
            "pair",
            "state",
            "classification",
            "portfolio_score",
            "portfolio_state",
            "capped",
            "reason_codes",
        ]
        assert len(rows) == 3

    def test_engine_report_to_markdown(self) -> None:
        portfolio = _portfolio_report(
            _score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        execution = _execution_context()
        report = build_controlled_universe_report(portfolio, execution, _config())
        text = controlled_universe_report_to_markdown(report)
        assert text.startswith("# Controlled Universe Report")
        assert "## Universe" in text
        assert "BTC/USDT" in text

    def test_atomic_writes_of_engine_report(self, tmp_path: Path) -> None:
        portfolio = _portfolio_report(
            _score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
            _score("ETH/USDT", PortfolioConstructionState.WATCHLIST, allocation_score=70.0),
        )
        execution = _execution_context()
        report = build_controlled_universe_report(portfolio, execution, _config())
        json_path = tmp_path / "report.json"
        csv_path = tmp_path / "report.csv"
        md_path = tmp_path / "report.md"
        out_json, out_csv, out_md = write_controlled_universe_report(
            report, json_path, csv_path, md_path
        )
        assert out_json == json_path
        assert out_csv == csv_path
        assert out_md == md_path
        assert json_path.exists()
        assert csv_path.exists()
        assert md_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["kind"] == "controlled_universe_report"

    def test_json_roundtrip_from_engine_report(self) -> None:
        portfolio = _portfolio_report(
            _score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        execution = _execution_context()
        report = build_controlled_universe_report(portfolio, execution, _config())
        text = controlled_universe_report_to_json_text(report)
        data = json.loads(text)
        assert data["version"] == report.version
        assert data["generated_at"] == report.generated_at.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S+00:00"
        )
        assert data["safety_flags"]["is_safe"] == report.safety_flags.is_safe

    def test_classify_then_serialize(self) -> None:
        portfolio = _portfolio_report(
            _score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        execution = _execution_context()
        config = _config()
        state, classification, reason_codes, capped = classify_controlled_universe_item(
            score=portfolio.scores[0],
            allowed_mode=AllowedMode.LONG_ONLY,
            config=config,
        )
        item = ControlledUniverseItem(
            pair="BTC/USDT",
            state=state,
            classification=classification,
            reason_codes=reason_codes,
            portfolio_score=portfolio.scores[0].allocation_score,
            portfolio_state=portfolio.scores[0].state.value,
            capped=capped,
        )
        assert item.state == ControlledUniverseState.INCLUDED
        assert item.classification == ControlledUniverseClassification.LONG_RESEARCH

    def test_fail_closed_report_still_serializable(self) -> None:
        portfolio = _portfolio_report(
            _score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        report = build_controlled_universe_report(portfolio, None, _config())
        assert isinstance(report, ControlledUniverseReport)
        assert report.items == ()
        text = controlled_universe_report_to_markdown(report)
        assert "## Items" in text
        assert "_none_" in text
        json_text = controlled_universe_report_to_json_text(report)
        data = json.loads(json_text)
        assert data["items"] == []
        assert data["safety_flags"]["has_missing_execution_context"] is True

    def test_invalid_portfolio_summary_report_serializable(self) -> None:
        portfolio = _portfolio_report(
            _score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        # Break the summary consistency by setting total_candidates to 0 while
        # there is still one score, so the engine flags an invalid portfolio summary.
        portfolio = PortfolioConstructionReport(
            version=portfolio.version,
            report_id=portfolio.report_id,
            generated_at=portfolio.generated_at,
            inputs=portfolio.inputs,
            config=portfolio.config,
            safety_flags=portfolio.safety_flags,
            scores=portfolio.scores,
            universe_summary=_universe_summary(
                total_candidates=0,
                included_count=0,
                capped_count=0,
                watchlist_count=0,
                excluded_count=0,
                insufficient_data_count=0,
                blocked_count=0,
            ),
            data_quality=portfolio.data_quality,
            reason_codes=portfolio.reason_codes,
            metadata=portfolio.metadata,
            notes=portfolio.notes,
        )
        execution = _execution_context()
        report = build_controlled_universe_report(portfolio, execution, _config())
        assert report.safety_flags.has_invalid_portfolio_summary is True
        text = controlled_universe_report_to_csv_text(report)
        assert "pair" in text  # header present
        # With invalid portfolio summary, items are empty.
        rows = list(csv.reader(text.splitlines()))
        assert len(rows) == 1

    def test_markdown_safety_notice_for_engine_report(self) -> None:
        portfolio = _portfolio_report(
            _score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        execution = _execution_context()
        report = build_controlled_universe_report(portfolio, execution, _config())
        text = controlled_universe_report_to_markdown(report)
        assert "research-only" in text
        assert "not a trading signal" in text
        assert "not Freqtrade input" in text


class TestIntegrationDefaults:
    def test_default_paths(self) -> None:
        from hunter.controlled_universe import DEFAULT_CSV_PATH, DEFAULT_JSON_PATH, DEFAULT_MD_PATH

        assert str(DEFAULT_JSON_PATH) == "data/controlled_universe/latest_controlled_universe.json"
        assert str(DEFAULT_CSV_PATH) == "data/controlled_universe/latest_controlled_universe.csv"
        assert str(DEFAULT_MD_PATH) == "reports/controlled_universe/latest_controlled_universe.md"
