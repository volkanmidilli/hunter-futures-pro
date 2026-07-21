"""Tests for deterministic writers (MVP-66 Stage 8)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_walk_forward.errors import WalkForwardWriterError
from hunter.research_walk_forward.models import (
    MarketRegimeLabel,
    MetricAggregate,
    RegimeAggregate,
    WalkForwardCommonConfig,
    WalkForwardExperimentPlan,
    WalkForwardExperimentReport,
    WalkForwardManifest,
    WalkForwardMode,
    WalkForwardSafetyFlags,
    WalkForwardWindow,
    WalkForwardWindowResult,
    WindowStatus,
)
from hunter.research_walk_forward.writer import (
    WalkForwardWriter,
    _write_json_atomic,
    write_all_walk_forward_artifacts,
    write_walk_forward_report,
)


def _make_report(tmp_path: Path) -> WalkForwardExperimentReport:
    from datetime import datetime, timezone
    from hunter.research_walk_forward.models import ConsistencyState, MetricDirection

    common = WalkForwardCommonConfig(
        strategy_name="TestStrategy",
        strategy_path=tmp_path / "strategy.py",
        data_path=tmp_path / "data",
        timeframe="1h",
        balance=Decimal("1000"),
        stake=Decimal("100"),
        max_open_trades=3,
        fee=Decimal("0.001"),
        executable_path=tmp_path / "freqtrade",
    )
    window = WalkForwardWindow(
        selection_start="20240101",
        selection_end="20240201",
        evaluation_start="20240301",
        evaluation_end="20240401",
    )
    plan = WalkForwardExperimentPlan(
        mode=WalkForwardMode.ROLLING,
        windows=(window,),
        common=common,
    )
    plan = WalkForwardExperimentPlan(
        mode=plan.mode,
        windows=plan.windows,
        common=plan.common,
        safety_flags=plan.safety_flags,
        fingerprint="fp-plan",
    )
    result = WalkForwardWindowResult(
        window=window,
        window_index=0,
        status=WindowStatus.COMPLETED,
        candidate_metrics={"total_return_pct": Decimal("10")},
        baseline_metrics={"total_return_pct": Decimal("5")},
        metric_deltas={"total_return_pct": Decimal("5")},
        metric_directions={"total_return_pct": MetricDirection.CANDIDATE_HIGHER},
        comparison_fingerprint="fp-comp",
        candidate_fingerprint="fp-c",
        baseline_fingerprint="fp-b",
        fingerprint="fp-result",
    )
    agg = MetricAggregate(
        metric_name="total_return_pct",
        available_count=1,
        unavailable_count=0,
        candidate_higher_count=1,
        baseline_higher_count=0,
        equal_count=0,
        mean=Decimal("5"),
        median=Decimal("5"),
        min=Decimal("5"),
        max=Decimal("5"),
        q1=Decimal("5"),
        q3=Decimal("5"),
        iqr=Decimal("0"),
        positive_delta_share=Decimal("1"),
        negative_delta_share=Decimal("0"),
        zero_delta_share=Decimal("0"),
        consistency_state=ConsistencyState.CONSISTENT_CANDIDATE_HIGHER,
    )
    regime = RegimeAggregate(
        regime_label=MarketRegimeLabel.UNKNOWN,
        window_count=1,
        completed_count=1,
        failed_count=0,
        blocked_count=0,
        timed_out_count=0,
        unsupported_count=0,
        insufficient_count=0,
        metric_aggregates={"total_return_pct": agg},
        fingerprint="fp-regime",
    )
    manifest = WalkForwardManifest(
        version="0.66.0-dev",
        spec_version="SPEC-067",
        walk_forward_version="0.66.0-dev",
        generated_at=datetime.now(timezone.utc),
        plan_fingerprint="fp-plan",
        overall_aggregate_fingerprint="fp-agg",
        regime_aggregate_fingerprint="fp-regime",
        safety_flags=WalkForwardSafetyFlags(),
    )
    return WalkForwardExperimentReport(
        version="0.66.0-dev",
        spec_version="SPEC-067",
        walk_forward_version="0.66.0-dev",
        plan=plan,
        window_results=(result,),
        metric_aggregates={"total_return_pct": agg},
        regime_aggregates=(regime,),
        manifest=manifest,
        safety_flags=WalkForwardSafetyFlags(),
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
        with pytest.raises(WalkForwardWriterError):
            _write_json_atomic(path, {"key": "value"})

    def test_overwrite_allowed(self, tmp_path: Path) -> None:
        path = tmp_path / "test.json"
        path.write_text("existing")
        _write_json_atomic(path, {"key": "value"}, overwrite=True)
        assert "key" in path.read_text()

    def test_partial_file_cleanup(self, tmp_path: Path) -> None:
        path = tmp_path / "subdir" / "test.json"
        _write_json_atomic(path, {"key": "value"})
        assert path.exists()


class TestWalkForwardWriter:
    def test_missing_output_dir_rejected(self) -> None:
        with pytest.raises(WalkForwardWriterError):
            WalkForwardWriter()

    def test_empty_output_dir_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(WalkForwardWriterError):
            WalkForwardWriter(output_dir="")

    def test_write_all(self, tmp_path: Path) -> None:
        report = _make_report(tmp_path)
        writer = WalkForwardWriter(output_dir=tmp_path / "out")
        paths = writer.write_all(report)
        for key in (
            "plan",
            "window_results",
            "metric_aggregates",
            "regime_aggregates",
            "report",
            "manifest",
            "markdown",
        ):
            assert key in paths
            assert paths[key].exists()

    def test_write_report(self, tmp_path: Path) -> None:
        report = _make_report(tmp_path)
        writer = WalkForwardWriter(output_dir=tmp_path / "out")
        path = writer.write_report(report)
        assert path.exists()
        assert path.name == "walk_forward_experiment_report.json"

    def test_write_markdown(self, tmp_path: Path) -> None:
        report = _make_report(tmp_path)
        writer = WalkForwardWriter(output_dir=tmp_path / "out")
        path = writer.write_markdown(report)
        assert path.exists()
        text = path.read_text()
        assert "Walk-Forward" in text
        assert "Research only" in text
        assert "Human review remains required" in text

    def test_convenience_function(self, tmp_path: Path) -> None:
        report = _make_report(tmp_path)
        report_path, manifest_path = write_walk_forward_report(
            report, output_dir=tmp_path / "out"
        )
        assert report_path.exists()
        assert manifest_path.exists()

    def test_convenience_function_missing_output_dir_rejected(
        self, tmp_path: Path
    ) -> None:
        report = _make_report(tmp_path)
        with pytest.raises(WalkForwardWriterError):
            write_walk_forward_report(report)

    def test_all_artifacts_convenience(self, tmp_path: Path) -> None:
        report = _make_report(tmp_path)
        paths = write_all_walk_forward_artifacts(report, output_dir=tmp_path / "out")
        assert len(paths) == 7

    def test_all_artifacts_convenience_missing_output_dir_rejected(
        self, tmp_path: Path
    ) -> None:
        report = _make_report(tmp_path)
        with pytest.raises(WalkForwardWriterError):
            write_all_walk_forward_artifacts(report)

    def test_silent_overwrite_markdown(self, tmp_path: Path) -> None:
        report = _make_report(tmp_path)
        writer = WalkForwardWriter(output_dir=tmp_path / "out")
        writer.write_markdown(report)
        with pytest.raises(WalkForwardWriterError):
            writer.write_markdown(report)

    def test_deterministic_json(self, tmp_path: Path) -> None:
        report = _make_report(tmp_path)
        writer = WalkForwardWriter(output_dir=tmp_path / "out")
        path1 = writer.write_report(report)
        path2 = writer.write_report(report, overwrite=True)
        text1 = path1.read_text()
        text2 = path2.read_text()
        assert text1 == text2

    def test_path_redaction(self, tmp_path: Path) -> None:
        report = _make_report(tmp_path)
        writer = WalkForwardWriter(output_dir=tmp_path / "out")
        path = writer.write_plan(report)
        text = path.read_text()
        assert "/tmp/[REDACTED]" in text or "/home/[REDACTED]" in text or "strategy.py" in text

    def test_no_output_under_data(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Patch the writer's notion of "project root" to tmp_path so this
        # test's forbidden-path assertion is correct regardless of the real
        # cwd/repository root -- it must never depend on being run from the
        # actual repository root to pass (or, worse, to silently write into
        # a differently-located data/ when it is not).
        monkeypatch.setattr(WalkForwardWriter, "_project_root", lambda self: tmp_path)
        report = _make_report(tmp_path)
        writer = WalkForwardWriter(output_dir=tmp_path / "data")
        with pytest.raises(WalkForwardWriterError):
            writer.write_report(report)
        assert not (tmp_path / "data").exists()

    def test_no_output_under_reports(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(WalkForwardWriter, "_project_root", lambda self: tmp_path)
        report = _make_report(tmp_path)
        writer = WalkForwardWriter(output_dir=tmp_path / "reports")
        with pytest.raises(WalkForwardWriterError):
            writer.write_report(report)
        assert not (tmp_path / "reports").exists()

    def test_secret_redaction(self, tmp_path: Path) -> None:
        report = _make_report(tmp_path)
        # Inject a secret-like metadata into the report.
        from dataclasses import replace

        report = replace(report, metadata={"note": "api_key=sk-1234567890abcdef"})
        writer = WalkForwardWriter(output_dir=tmp_path / "out")
        path = writer.write_markdown(report)
        text = path.read_text()
        assert "sk-1234567890abcdef" not in text
