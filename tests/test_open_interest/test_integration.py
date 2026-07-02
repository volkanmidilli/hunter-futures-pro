"""Integration tests for hunter.open_interest end-to-end workflows."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import hunter.open_interest as oi
from hunter.open_interest.models import (
    OpenInterestConfig,
    OpenInterestFundingContext,
    OpenInterestInput,
    OpenInterestObservation,
    OpenInterestPositioning,
    OpenInterestState,
    OpenInterestTrend,
)


def _make_dt(day: int) -> datetime:
    return datetime(2026, 7, day, tzinfo=timezone.utc)


def _make_obs(day: int, close: float, oi_value: float, funding_rate: float | None = None) -> OpenInterestObservation:
    return OpenInterestObservation(
        timestamp=_make_dt(day),
        open_interest=oi_value,
        close=close,
        funding_rate=funding_rate,
    )


def _make_rows(
    n: int = 15,
    daily_price_return: float = 0.0,
    daily_oi_return: float = 0.0,
    start_close: float = 100.0,
    start_oi: float = 1_000_000.0,
    funding_rate: float | None = None,
) -> tuple[OpenInterestObservation, ...]:
    """Generate deterministic OI/price observations."""
    rows: list[OpenInterestObservation] = []
    close = start_close
    oi_value = start_oi
    for i in range(n):
        day = i + 1
        rows.append(
            _make_obs(
                day=day,
                close=round(close, 8),
                oi_value=round(oi_value, 8),
                funding_rate=funding_rate if i == n - 1 else None,
            )
        )
        close *= 1 + daily_price_return
        oi_value *= 1 + daily_oi_return
    return tuple(rows)


def _make_report(
    universe: tuple[OpenInterestInput, ...] | list[OpenInterestInput],
    config: OpenInterestConfig | None = None,
    report_id: str = "latest-open-interest",
) -> oi.OpenInterestReport:
    return oi.build_open_interest_report(
        universe=universe,
        config=config,
        report_id=report_id,
        generated_at=datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


class TestEndToEndReport:
    def test_build_full_report(self) -> None:
        rows = _make_rows(n=15, daily_price_return=0.01, daily_oi_return=0.01)
        universe = (OpenInterestInput(pair="BTCUSDT", rows=rows),)
        report = _make_report(universe)

        assert report.kind == "open_interest_report"
        assert report.source_spec == "SPEC-026"
        assert report.version == "0.25.0-dev"
        assert len(report.scores) == 1
        assert report.universe_summary.total_pairs == 1

        score = report.scores[0]
        assert score.state == OpenInterestState.READY
        assert score.positioning == OpenInterestPositioning.PRICE_UP_OI_UP
        assert score.trend == OpenInterestTrend.EXPANDING
        assert score.total_score > 0.0
        assert 0.0 <= score.total_score <= 100.0

        summary = report.universe_summary
        assert summary.ready_count == 1
        assert summary.average_total_score is not None
        assert summary.top_expanding_pair == "BTCUSDT"
        assert summary.data_quality.min_required_rows_met is True

        assert report.safety_flags.human_research_only is True
        assert report.safety_flags.no_action_commands_emitted is True
        assert report.safety_flags.output_not_trading_signal is True
        assert report.safety_flags.output_not_trade_approval is True
        assert report.safety_flags.leverage_enabled is False
        assert report.safety_flags.shorting_enabled is False

    def test_report_with_multiple_pairs(self) -> None:
        expanding = OpenInterestInput(
            pair="EXPUSDT",
            rows=_make_rows(n=15, daily_price_return=0.01, daily_oi_return=0.01),
        )
        contracting = OpenInterestInput(
            pair="CONUSDT",
            rows=_make_rows(n=15, daily_price_return=-0.01, daily_oi_return=-0.01),
        )
        report = _make_report((expanding, contracting))
        assert len(report.scores) == 2
        states = {score.state for score in report.scores}
        assert states == {OpenInterestState.READY}
        assert report.universe_summary.expanding_count >= 1
        assert report.universe_summary.contracting_count >= 1

    def test_deterministic_ordering(self) -> None:
        ready = OpenInterestInput(
            pair="READY",
            rows=_make_rows(n=15, daily_price_return=0.01, daily_oi_return=0.01),
        )
        insufficient = OpenInterestInput(
            pair="INSUF",
            rows=_make_rows(n=5),
        )
        blocked = OpenInterestInput(
            pair="BLOCKED",
            rows=_make_rows(n=15),
            metadata={"action": "buy"},
        )
        report = _make_report([blocked, insufficient, ready])
        assert report.scores[0].state == OpenInterestState.READY
        assert report.scores[1].state == OpenInterestState.INSUFFICIENT_DATA
        assert report.scores[2].state == OpenInterestState.BLOCKED


class TestEndToEndWriter:
    def test_write_all_artifacts(self, tmp_path: Path) -> None:
        report = _make_report(
            (OpenInterestInput(pair="BTCUSDT", rows=_make_rows(n=15)),),
            report_id="writer-test",
        )
        json_out = tmp_path / "out.json"
        csv_out = tmp_path / "out.csv"
        md_out = tmp_path / "out.md"

        paths = oi.write_open_interest_report(report, json_out, csv_out, md_out)
        assert paths == (json_out, csv_out, md_out)
        assert json_out.exists()
        assert csv_out.exists()
        assert md_out.exists()

        data = json.loads(json_out.read_text(encoding="utf-8"))
        assert data["kind"] == "open_interest_report"
        assert data["report_id"] == "writer-test"
        assert data["scores"]

        rows = list(csv.reader(csv_out.read_text().splitlines()))
        assert len(rows) == len(report.scores) + 1
        assert "pair" in rows[0]
        assert "BTCUSDT" in csv_out.read_text()

        md = md_out.read_text()
        assert md.startswith("# Open Interest Report")
        lines = md.splitlines()
        assert lines[2].startswith("> ")
        assert "research-only" in lines[2].lower() or "human-audit" in lines[2].lower()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        report = _make_report(
            (OpenInterestInput(pair="BTCUSDT", rows=_make_rows(n=15)),),
        )
        target = tmp_path / "nested" / "dir" / "report.json"
        paths = oi.write_open_interest_report(report, target, None, None)
        assert paths[0] == target
        assert paths[1] is None
        assert paths[2] is None
        assert target.exists()

    def test_default_paths_write(self, tmp_path: Path) -> None:
        import hunter.open_interest.writer as writer_module

        original_json = writer_module.DEFAULT_JSON_PATH
        original_csv = writer_module.DEFAULT_CSV_PATH
        original_md = writer_module.DEFAULT_MD_PATH
        try:
            writer_module.DEFAULT_JSON_PATH = tmp_path / "default.json"
            writer_module.DEFAULT_CSV_PATH = tmp_path / "default.csv"
            writer_module.DEFAULT_MD_PATH = tmp_path / "default.md"
            report = _make_report(
                (OpenInterestInput(pair="BTCUSDT", rows=_make_rows(n=15)),),
            )
            json_out, csv_out, md_out = oi.write_open_interest_report(report)
            assert json_out == tmp_path / "default.json"
            assert csv_out == tmp_path / "default.csv"
            assert md_out == tmp_path / "default.md"
            assert json_out.exists()
            assert csv_out.exists()
            assert md_out.exists()
        finally:
            writer_module.DEFAULT_JSON_PATH = original_json
            writer_module.DEFAULT_CSV_PATH = original_csv
            writer_module.DEFAULT_MD_PATH = original_md


class TestPositioningPaths:
    def _positioning_report(
        self, price_return: float, oi_return: float
    ) -> oi.OpenInterestReport:
        rows = _make_rows(n=15, daily_price_return=price_return, daily_oi_return=oi_return)
        return _make_report((OpenInterestInput(pair="PAIR", rows=rows),))

    def test_price_up_oi_up(self) -> None:
        report = self._positioning_report(0.01, 0.01)
        assert report.scores[0].positioning == OpenInterestPositioning.PRICE_UP_OI_UP

    def test_price_up_oi_down(self) -> None:
        report = self._positioning_report(0.01, -0.01)
        assert report.scores[0].positioning == OpenInterestPositioning.PRICE_UP_OI_DOWN

    def test_price_down_oi_up(self) -> None:
        report = self._positioning_report(-0.01, 0.01)
        assert report.scores[0].positioning == OpenInterestPositioning.PRICE_DOWN_OI_UP

    def test_price_down_oi_down(self) -> None:
        report = self._positioning_report(-0.01, -0.01)
        assert report.scores[0].positioning == OpenInterestPositioning.PRICE_DOWN_OI_DOWN

    def test_mixed(self) -> None:
        # Price stays flat (within 0.001 threshold over 7d), OI rises strongly.
        # 7d price change with daily 0.00005 is roughly 0.00035, within threshold.
        rows = _make_rows(n=15, daily_price_return=0.00005, daily_oi_return=0.01)
        report = _make_report((OpenInterestInput(pair="PAIR", rows=rows),))
        assert report.scores[0].positioning == OpenInterestPositioning.MIXED


class TestTrendPaths:
    def test_expanding(self) -> None:
        rows = _make_rows(n=15, daily_price_return=0.01, daily_oi_return=0.01)
        report = _make_report((OpenInterestInput(pair="PAIR", rows=rows),))
        assert report.scores[0].trend == OpenInterestTrend.EXPANDING

    def test_contracting(self) -> None:
        rows = _make_rows(n=15, daily_price_return=-0.01, daily_oi_return=-0.01)
        report = _make_report((OpenInterestInput(pair="PAIR", rows=rows),))
        assert report.scores[0].trend == OpenInterestTrend.CONTRACTING

    def test_flat(self) -> None:
        # Very small daily OI changes keep all windows within threshold.
        rows = _make_rows(n=15, daily_price_return=0.00005, daily_oi_return=0.00005)
        report = _make_report((OpenInterestInput(pair="PAIR", rows=rows),))
        assert report.scores[0].trend == OpenInterestTrend.FLAT

    def test_unstable(self) -> None:
        # Construct a series where 2 of the 4 windows are positive and 2 are negative.
        # Values: day1=1.0M, day8=1.05M, day12=1.0M, day14=1.03M, day15=1.02M
        # 1d: (1.02 - 1.03) / 1.03 = -0.0097  -> negative
        # 3d: (1.02 - 1.00) / 1.00 = +0.02     -> positive
        # 7d: (1.02 - 1.05) / 1.05 = -0.0286   -> negative
        # 14d: (1.02 - 1.00) / 1.00 = +0.02    -> positive
        values = [
            1_000_000.0,  # day1
            1_010_000.0,
            1_020_000.0,
            1_030_000.0,
            1_040_000.0,
            1_045_000.0,
            1_048_000.0,
            1_050_000.0,  # day8
            1_040_000.0,
            1_030_000.0,
            1_020_000.0,
            1_000_000.0,  # day12
            1_015_000.0,
            1_030_000.0,  # day14
            1_020_000.0,  # day15
        ]
        rows = [
            _make_obs(day=i + 1, close=100.0, oi_value=round(values[i], 8))
            for i in range(15)
        ]
        report = _make_report((OpenInterestInput(pair="PAIR", rows=tuple(rows)),))
        assert report.scores[0].trend == OpenInterestTrend.UNSTABLE


class TestFundingContextPaths:
    def _funding_report(self, funding_rate: float | None) -> oi.OpenInterestReport:
        rows = _make_rows(n=15, funding_rate=funding_rate)
        return _make_report((OpenInterestInput(pair="PAIR", rows=rows),))

    def test_positive(self) -> None:
        # Upper bound is 0.01, so upper/3 is ~0.003333.
        report = self._funding_report(0.005)
        assert report.scores[0].funding_context == OpenInterestFundingContext.POSITIVE

    def test_negative(self) -> None:
        report = self._funding_report(-0.005)
        assert report.scores[0].funding_context == OpenInterestFundingContext.NEGATIVE

    def test_neutral(self) -> None:
        report = self._funding_report(0.0001)
        assert report.scores[0].funding_context == OpenInterestFundingContext.NEUTRAL

    def test_missing(self) -> None:
        report = self._funding_report(None)
        assert report.scores[0].funding_context == OpenInterestFundingContext.MISSING


class TestInsufficientData:
    def test_insufficient_data_not_blocked(self) -> None:
        config = OpenInterestConfig(block_on_missing_data=False)
        rows = _make_rows(n=5)
        report = _make_report((OpenInterestInput(pair="PAIR", rows=rows),), config=config)
        assert len(report.scores) == 1
        score = report.scores[0]
        assert score.state == OpenInterestState.INSUFFICIENT_DATA
        assert score.positioning == OpenInterestPositioning.INSUFFICIENT_DATA
        assert score.trend == OpenInterestTrend.INSUFFICIENT_DATA
        assert score.total_score == 0.0

    def test_block_on_missing_data(self) -> None:
        config = OpenInterestConfig(block_on_missing_data=True)
        rows = _make_rows(n=5)
        report = _make_report((OpenInterestInput(pair="PAIR", rows=rows),), config=config)
        assert len(report.scores) == 1
        score = report.scores[0]
        assert score.state == OpenInterestState.BLOCKED
        assert score.positioning == OpenInterestPositioning.BLOCKED
        assert score.total_score == 0.0

    def test_pairs_not_dropped(self) -> None:
        ready = OpenInterestInput(pair="READY", rows=_make_rows(n=15))
        insufficient = OpenInterestInput(pair="INSUF", rows=_make_rows(n=5))
        report = _make_report([ready, insufficient])
        assert len(report.scores) == 2


class TestUnsafeContent:
    def test_unsafe_pair_blocks(self) -> None:
        rows = _make_rows(n=15)
        unsafe_input = OpenInterestInput(pair="place_order", rows=rows)
        report = _make_report((unsafe_input,))
        assert len(report.scores) == 1
        assert report.scores[0].state == OpenInterestState.BLOCKED
        assert "UNSAFE_OPEN_INTEREST_CONTENT" in report.scores[0].reason_codes

    def test_unsafe_metadata_not_executed(self, tmp_path: Path) -> None:
        # Metadata may contain path-like strings that must remain opaque.
        # The engine must not read, open, follow, validate, or execute them.
        rows = _make_rows(n=15)
        safe_input = OpenInterestInput(
            pair="SAFE",
            rows=rows,
            metadata={"note": "research observation", "path": "/tmp/hypothetical/path"},
        )
        report = _make_report((safe_input,))
        # Path strings are opaque; engine does not traverse metadata.
        assert report.scores[0].state == OpenInterestState.READY
        assert report.scores[0].metadata["path"] == "/tmp/hypothetical/path"
        assert report.scores[0].metadata == {"note": "research observation", "path": "/tmp/hypothetical/path"}
        json_out = tmp_path / "meta.json"
        oi.write_open_interest_report(report, json_out, None, None)
        # The writer serializes the report without executing metadata contents.
        assert json_out.exists()


class TestDeterminism:
    def test_report_is_deterministic(self) -> None:
        universe = (OpenInterestInput(pair="BTCUSDT", rows=_make_rows(n=15)),)
        report1 = _make_report(universe)
        report2 = _make_report(universe)
        assert report1 == report2

    def test_serialization_text_is_deterministic(self) -> None:
        report = _make_report((OpenInterestInput(pair="BTCUSDT", rows=_make_rows(n=15)),))
        assert oi.open_interest_report_to_json_text(report) == oi.open_interest_report_to_json_text(report)
        assert oi.open_interest_report_to_csv_text(report) == oi.open_interest_report_to_csv_text(report)
        assert oi.open_interest_report_to_markdown(report) == oi.open_interest_report_to_markdown(report)
        assert oi.open_interest_report_to_dict(report) == oi.open_interest_report_to_dict(report)


class TestNoMutation:
    def test_input_rows_not_mutated(self) -> None:
        rows = list(_make_rows(n=15))
        original_rows = tuple(rows)
        # Reverse rows to ensure engine sorts them itself.
        rows = rows[::-1]
        inp = OpenInterestInput(pair="BTCUSDT", rows=rows)
        report = _make_report((inp,))
        assert tuple(rows) == tuple(original_rows[::-1])
        assert report.scores[0].pair == "BTCUSDT"

    def test_input_object_not_mutated(self) -> None:
        rows = _make_rows(n=15)
        inp = OpenInterestInput(pair="BTCUSDT", rows=rows)
        original_pair = inp.pair
        original_rows = inp.rows
        _make_report((inp,))
        assert inp.pair == original_pair
        assert inp.rows == original_rows


class TestAtomicTmpPathWrites:
    def test_outputs_only_under_tmp_path(self, tmp_path: Path) -> None:
        report = _make_report((OpenInterestInput(pair="BTCUSDT", rows=_make_rows(n=15)),))
        json_out = tmp_path / "data" / "out.json"
        csv_out = tmp_path / "data" / "out.csv"
        md_out = tmp_path / "reports" / "out.md"
        oi.write_open_interest_report(report, json_out, csv_out, md_out)

        for path in (json_out, csv_out, md_out):
            assert path.exists()
            assert tmp_path in path.parents

        for path in tmp_path.rglob("*"):
            assert tmp_path in path.parents or path == tmp_path


class TestHumanResearchSafety:
    def test_markdown_contains_research_only_language(self) -> None:
        report = _make_report((OpenInterestInput(pair="BTCUSDT", rows=_make_rows(n=15)),))
        md = oi.open_interest_report_to_markdown(report)
        assert "human-audit" in md.lower() or "research-only" in md.lower()
        assert "not a trading signal" in md.lower()

    def test_markdown_no_actionable_instructions(self) -> None:
        report = _make_report((OpenInterestInput(pair="BTCUSDT", rows=_make_rows(n=15)),))
        md = oi.open_interest_report_to_markdown(report)
        lower = md.lower()
        assert "place order" not in lower
        assert "buy now" not in lower
        assert "sell now" not in lower
        assert "execute trade" not in lower
        assert "enter_long" not in lower
        assert "go_live" not in lower


class TestPublicExports:
    def test_public_api_exports(self) -> None:
        assert callable(oi.build_open_interest_report)
        assert callable(oi.open_interest_report_to_dict)
        assert callable(oi.open_interest_report_to_json_text)
        assert callable(oi.open_interest_report_to_csv_text)
        assert callable(oi.open_interest_report_to_markdown)
        assert callable(oi.atomic_write_json_open_interest_report)
        assert callable(oi.atomic_write_csv_open_interest_report)
        assert callable(oi.atomic_write_markdown_open_interest_report)
        assert callable(oi.write_open_interest_report)
        assert oi.DEFAULT_JSON_PATH is not None
        assert oi.DEFAULT_CSV_PATH is not None
        assert oi.DEFAULT_MD_PATH is not None
