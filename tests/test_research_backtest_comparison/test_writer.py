"""Tests for deterministic writers (MVP-65 Stage 5)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonWriterError,
)
from hunter.research_backtest_comparison.models import (
    BacktestArmLabel,
    BacktestComparisonReport,
    BacktestComparisonResult,
    BacktestFairnessManifest,
    BacktestMetrics,
    BacktestRunResult,
    MetricInterpretation,
    ResearchBacktestSafetyFlags,
)
from hunter.research_backtest_comparison.writer import (
    BacktestComparisonWriter,
    _write_json_atomic,
    write_backtest_comparison_report,
)


def _make_report() -> BacktestComparisonReport:
    from datetime import datetime, timezone
    from hunter.research_backtest_comparison.models import (
        BacktestComparisonConfig,
        BacktestComparisonManifest,
    )

    config = BacktestComparisonConfig(
        strategy_name="TestStrategy",
        strategy_path="/tmp/strategy.py",
        data_path="/tmp/data",
        timeframe="1h",
        timerange="20240101-20240201",
        balance=Decimal("1000"),
        stake=Decimal("100"),
        max_open_trades=3,
        fee=Decimal("0.001"),
        executable_path="/tmp/freqtrade",
    )
    candidate = BacktestRunResult(
        label=BacktestArmLabel.CANDIDATE,
        success=True,
        metrics=BacktestMetrics(total_return_pct=Decimal("10"), trade_count=5),
        stdout="",
        stderr="",
        exit_code=0,
        workspace="/tmp/ws-c",
        result_file="/tmp/ws-c/result.json",
        command=("freqtrade", "backtesting"),
        command_fingerprint="fp-c",
        strategy_sha_before="abc",
        strategy_sha_after="abc",
        fingerprint="fp-rc",
    )
    baseline = BacktestRunResult(
        label=BacktestArmLabel.BASELINE,
        success=True,
        metrics=BacktestMetrics(total_return_pct=Decimal("5"), trade_count=5),
        stdout="",
        stderr="",
        exit_code=0,
        workspace="/tmp/ws-b",
        result_file="/tmp/ws-b/result.json",
        command=("freqtrade", "backtesting"),
        command_fingerprint="fp-b",
        strategy_sha_before="abc",
        strategy_sha_after="abc",
        fingerprint="fp-rb",
    )
    comparison = BacktestComparisonResult(
        candidate=candidate,
        baseline=baseline,
        metric_deltas={"total_return_pct": Decimal("5")},
        interpretations={"total_return_pct": MetricInterpretation.CANDIDATE_HIGHER},
        comparison_fingerprint="fp-comp",
        trade_sufficiency=True,
    )
    fairness = BacktestFairnessManifest(
        strategy_name="TestStrategy",
        strategy_fingerprint="fp-s",
        data_fingerprint="fp-d",
        timeframe="1h",
        timerange="20240101-20240201",
        balance=Decimal("1000"),
        stake=Decimal("100"),
        max_open_trades=3,
        fee=Decimal("0.001"),
        protections=(),
        assumptions_equal=True,
        pairlist_only_difference=("overlap=1", ("ETH/USDT",), ()),
        fairness_fingerprint="fp-f",
    )
    manifest = BacktestComparisonManifest(
        version="0.65.0-dev",
        spec_version="SPEC-066",
        research_backtest_comparison_version="0.65.0-dev",
        generated_at=datetime.now(timezone.utc),
        config_fingerprint="fp-cfg",
        strategy_fingerprint="fp-s",
        candidate_pairlist_fingerprint="fp-cp",
        baseline_pairlist_fingerprint="fp-bp",
        candidate_result_fingerprint="fp-rc",
        baseline_result_fingerprint="fp-rb",
        comparison_fingerprint="fp-comp",
        safety_flags=ResearchBacktestSafetyFlags(),
        reason_codes=(),
    )
    return BacktestComparisonReport(
        version="0.65.0-dev",
        spec_version="SPEC-066",
        research_backtest_comparison_version="0.65.0-dev",
        config=config,
        manifest=manifest,
        candidate=candidate,
        baseline=baseline,
        comparison=comparison,
        fairness=fairness,
        safety_flags=ResearchBacktestSafetyFlags(),
        fingerprint="fp-report",
    )


class TestWriteJsonAtomic:
    def test_write_and_read(self, tmp_path: Path) -> None:
        path = tmp_path / "test.json"
        _write_json_atomic(path, {"key": "value"})
        assert path.exists()
        assert "key" in path.read_text()

    def test_silent_overwrite_blocked(self, tmp_path: Path) -> None:
        path = tmp_path / "test.json"
        path.write_text("existing")
        with pytest.raises(ResearchBacktestComparisonWriterError):
            _write_json_atomic(path, {"key": "value"})

    def test_overwrite_allowed(self, tmp_path: Path) -> None:
        path = tmp_path / "test.json"
        path.write_text("existing")
        _write_json_atomic(path, {"key": "value"}, overwrite=True)
        assert "key" in path.read_text()


class TestBacktestComparisonWriter:
    def test_write_report(self, tmp_path: Path) -> None:
        report = _make_report()
        writer = BacktestComparisonWriter(
            output_dir=tmp_path / "reports",
            data_dir=tmp_path / "data",
        )
        path = writer.write_report(report)
        assert path.exists()
        assert path.parent.name == "reports"

    def test_write_manifest(self, tmp_path: Path) -> None:
        report = _make_report()
        writer = BacktestComparisonWriter(
            output_dir=tmp_path / "reports",
            data_dir=tmp_path / "data",
        )
        path = writer.write_manifest(report)
        assert path.exists()
        assert path.parent.name == "data"

    def test_write_all(self, tmp_path: Path) -> None:
        report = _make_report()
        writer = BacktestComparisonWriter(
            output_dir=tmp_path / "reports",
            data_dir=tmp_path / "data",
        )
        paths = writer.write_all(report)
        assert "report" in paths
        assert "manifest" in paths
        assert "markdown" in paths
        for p in paths.values():
            assert p.exists()

    def test_write_markdown(self, tmp_path: Path) -> None:
        report = _make_report()
        writer = BacktestComparisonWriter(
            output_dir=tmp_path / "reports",
            data_dir=tmp_path / "data",
        )
        path = writer.write_markdown(report)
        assert path.exists()
        text = path.read_text()
        assert "Research Backtest Comparison Report" in text
        assert "Research only" in text

    def test_convenience_function(self, tmp_path: Path) -> None:
        report = _make_report()
        report_path, manifest_path = write_backtest_comparison_report(
            report,
            output_dir=tmp_path / "reports",
            data_dir=tmp_path / "data",
        )
        assert report_path.exists()
        assert manifest_path.exists()
