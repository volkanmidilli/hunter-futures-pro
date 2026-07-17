"""Tests for integration wrappers — MVP-66/67/68 (MVP-70 / SPEC-070).

No subprocess, threading, network, eval, exec, or dynamic code.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from hunter.research_campaign.errors import ResearchCampaignRunnerError
from hunter.research_campaign.integration import (
    ingest_experiment_evidence,
    run_confidence_for_experiment,
    run_walk_forward_for_experiment,
)
from hunter.research_evidence_ledger.models import (
    EvidenceLedgerEntry,
    ExperimentRegistration,
    ExperimentStatus,
    IndependenceClass,
    LedgerSnapshot,
)
from hunter.research_statistical_confidence.models import (
    BootstrapConfig,
    ExperimentConfidenceReport,
    RobustnessCriteria,
    StatisticalConfidenceConfig,
)
from hunter.research_walk_forward.models import (
    ExperimentExecutionPolicy,
    MarketRegimeLabel,
    MetricAggregate,
    MetricDirection,
    RegimeAggregate,
    WalkForwardExperimentPlan,
    WalkForwardExperimentReport,
    WalkForwardManifest,
    WalkForwardSafetyFlags,
    WalkForwardWindow,
    WalkForwardWindowResult,
    WindowStatus,
    ConsistencyState,
)


# ===========================================================================
# Helpers
# ===========================================================================


def _make_completed_window(
    window: WalkForwardWindow, index: int
) -> WalkForwardWindowResult:
    """Create a COMPLETED window result."""
    return WalkForwardWindowResult(
        window=window,
        window_index=index,
        status=WindowStatus.COMPLETED,
        candidate_metrics={"sharpe_ratio": Decimal("1.5")},
        baseline_metrics={"sharpe_ratio": Decimal("1.0")},
        metric_deltas={"sharpe_ratio": Decimal("0.5")},
        metric_directions={"sharpe_ratio": MetricDirection.CANDIDATE_HIGHER},
        comparison_fingerprint="cmp_fp",
        candidate_fingerprint="cand_fp",
        baseline_fingerprint="base_fp",
        fingerprint="win_fp",
    )


def _make_failed_window(
    window: WalkForwardWindow, index: int
) -> WalkForwardWindowResult:
    """Create a FAILED window result."""
    return WalkForwardWindowResult(
        window=window,
        window_index=index,
        status=WindowStatus.FAILED,
        candidate_metrics={},
        baseline_metrics={},
        metric_deltas={},
        metric_directions={},
        comparison_fingerprint="cmp_fp",
        candidate_fingerprint="cand_fp",
        baseline_fingerprint="base_fp",
        fingerprint="win_fp",
    )


def _make_wf_report(
    plan: WalkForwardExperimentPlan,
    window_results: tuple[WalkForwardWindowResult, ...],
) -> WalkForwardExperimentReport:
    """Create a minimal WalkForwardExperimentReport."""
    now = datetime.now(timezone.utc)
    aggregate = MetricAggregate(
        metric_name="sharpe_ratio",
        available_count=1,
        unavailable_count=0,
        candidate_higher_count=1,
        baseline_higher_count=0,
        equal_count=0,
        mean=Decimal("0.5"),
        median=Decimal("0.5"),
        min=Decimal("0.5"),
        max=Decimal("0.5"),
        q1=Decimal("0.5"),
        q3=Decimal("0.5"),
        iqr=Decimal("0"),
        positive_delta_share=Decimal("1.0"),
        negative_delta_share=Decimal("0"),
        zero_delta_share=Decimal("0"),
        consistency_state=ConsistencyState.CONSISTENT_CANDIDATE_HIGHER,
    )
    regime_agg = RegimeAggregate(
        regime_label=MarketRegimeLabel.UNKNOWN,
        window_count=1,
        completed_count=1,
        failed_count=0,
        blocked_count=0,
        timed_out_count=0,
        unsupported_count=0,
        insufficient_count=0,
        metric_aggregates={"sharpe_ratio": aggregate},
        fingerprint="reg_agg_fp",
    )
    manifest = WalkForwardManifest(
        version="0.66.0-dev",
        spec_version="SPEC-066",
        walk_forward_version="0.66.0-dev",
        generated_at=now,
        plan_fingerprint=plan.fingerprint,
        overall_aggregate_fingerprint="overall_fp",
        regime_aggregate_fingerprint="reg_fp",
        safety_flags=WalkForwardSafetyFlags(),
    )
    return WalkForwardExperimentReport(
        version="0.66.0-dev",
        spec_version="SPEC-066",
        walk_forward_version="0.66.0-dev",
        plan=plan,
        window_results=window_results,
        metric_aggregates={"sharpe_ratio": aggregate},
        regime_aggregates=(regime_agg,),
        manifest=manifest,
        safety_flags=WalkForwardSafetyFlags(),
        fingerprint="wf_report_fp",
    )


# ===========================================================================
# run_walk_forward_for_experiment
# ===========================================================================


class TestRunWalkForwardForExperiment:
    def test_calls_run_with_correct_arguments(
        self, sample_compiled_experiment
    ) -> None:
        """Verify the wrapper calls run_walk_forward_experiment with correct args."""
        mock_report = MagicMock(spec=WalkForwardExperimentReport)

        with patch(
            "hunter.research_campaign.integration.run_walk_forward_experiment",
            return_value=mock_report,
        ) as mock_call:
            result = run_walk_forward_for_experiment(
                sample_compiled_experiment,
                execution_policy=ExperimentExecutionPolicy.COLLECT_ALL,
            )

            assert result is mock_report
            mock_call.assert_called_once()

            # Verify call arguments
            call_kwargs = mock_call.call_args.kwargs
            assert "plan" in call_kwargs
            assert call_kwargs["plan"] is sample_compiled_experiment.walk_forward_plan
            assert call_kwargs["candidate_pairlist"] == (
                sample_compiled_experiment.universe_plan.candidate_pairlist
            )
            assert call_kwargs["baseline_pairlist"] == (
                sample_compiled_experiment.universe_plan.baseline_pairlist
            )
            assert call_kwargs[
                "candidate_universe_fingerprint"
            ] == sample_compiled_experiment.universe_plan.candidate_universe_fingerprint
            assert call_kwargs[
                "baseline_universe_fingerprint"
            ] == sample_compiled_experiment.universe_plan.baseline_universe_fingerprint
            assert call_kwargs["execution_policy"] == ExperimentExecutionPolicy.COLLECT_ALL


# ===========================================================================
# run_confidence_for_experiment
# ===========================================================================


class TestRunConfidenceForExperiment:
    def test_runs_when_all_windows_completed(
        self, sample_wf_plan, sample_wf_window
    ) -> None:
        """Confidence runs when all windows are COMPLETED."""
        window_results = (_make_completed_window(sample_wf_window, 0),)
        wf_report = _make_wf_report(sample_wf_plan, window_results)

        mock_confidence_report = MagicMock(spec=ExperimentConfidenceReport)
        with patch(
            "hunter.research_campaign.integration.run_statistical_confidence",
            return_value=mock_confidence_report,
        ) as mock_call:
            result = run_confidence_for_experiment(
                wf_report, MagicMock()
            )
            assert result is mock_confidence_report
            mock_call.assert_called_once()

    def test_raises_error_when_any_window_not_completed(
        self, sample_wf_plan, sample_wf_window
    ) -> None:
        """Raises ResearchCampaignRunnerError when a window is not COMPLETED."""
        window_results = (_make_failed_window(sample_wf_window, 0),)
        wf_report = _make_wf_report(sample_wf_plan, window_results)

        with pytest.raises(ResearchCampaignRunnerError) as excinfo:
            run_confidence_for_experiment(wf_report, MagicMock())
        assert "incomplete windows" in str(excinfo.value).lower()

    def test_raises_error_when_mixed_window_status(
        self, sample_wf_plan, sample_wf_window
    ) -> None:
        """Raises ResearchCampaignRunnerError with mixed window statuses."""
        # Create a second window
        window2 = WalkForwardWindow(
            selection_start="2024-07-01",
            selection_end="2024-09-01",
            evaluation_start="2024-09-01",
            evaluation_end="2025-01-01",
            regime_label=MarketRegimeLabel.UNKNOWN,
        )
        window_results = (
            _make_completed_window(sample_wf_window, 0),
            _make_failed_window(window2, 1),
        )
        wf_report = _make_wf_report(sample_wf_plan, window_results)

        with pytest.raises(ResearchCampaignRunnerError) as excinfo:
            run_confidence_for_experiment(wf_report, MagicMock())
        assert "incomplete windows" in str(excinfo.value).lower()


# ===========================================================================
# ingest_experiment_evidence
# ===========================================================================


class TestIngestExperimentEvidence:
    def test_calls_engine_methods_correctly(
        self, sample_compiled_experiment
    ) -> None:
        """Verify ingest_experiment_evidence calls engine.register_experiment
        and engine.ingest_evidence with the correct arguments."""
        mock_engine = MagicMock()
        mock_engine.register_experiment = MagicMock()
        mock_engine.ingest_evidence = MagicMock()
        mock_engine.build_entry = MagicMock()
        mock_engine.take_snapshot = MagicMock()

        # Create a minimal registration
        reg = ExperimentRegistration(
            experiment_id=sample_compiled_experiment.experiment_id,
            hypothesis="test:hyp",
            strategy_name="test_strat",
            universe_plan="uni_a",
            timeframe="1h",
            walk_forward_plan_fingerprint="wfp",
            metric_family=("sharpe_ratio",),
            independence=IndependenceClass.INDEPENDENT,
        )

        mock_wf_report = MagicMock(spec=WalkForwardExperimentReport)
        mock_conf_report = MagicMock(spec=ExperimentConfidenceReport)

        mock_entry = MagicMock(spec=EvidenceLedgerEntry)
        mock_snapshot = MagicMock(spec=LedgerSnapshot)

        mock_engine.build_entry.return_value = mock_entry
        mock_engine.take_snapshot.return_value = mock_snapshot

        entry, snapshot = ingest_experiment_evidence(
            engine=mock_engine,
            compiled_experiment=sample_compiled_experiment,
            registration=reg,
            walk_forward_report=mock_wf_report,
            confidence_report=mock_conf_report,
        )

        # Verify calls
        mock_engine.register_experiment.assert_called_once_with(reg)
        mock_engine.ingest_evidence.assert_called_once_with(
            experiment_id=sample_compiled_experiment.experiment_id,
            walk_forward_report=mock_wf_report,
            confidence_report=mock_conf_report,
        )
        mock_engine.build_entry.assert_called_once_with(
            experiment_id=sample_compiled_experiment.experiment_id,
        )
        mock_engine.take_snapshot.assert_called_once()

        assert entry is mock_entry
        assert snapshot is mock_snapshot
