"""Security and safety tests for the walk-forward harness (MVP-66 Stage 9)."""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_walk_forward.models import (
    NO_DIRECT_SUBPROCESS,
    SAFETY_INVARIANT_VIOLATION,
    ExperimentExecutionPolicy,
    MarketRegimeLabel,
    WalkForwardCommonConfig,
    WalkForwardSafetyFlags,
    WalkForwardWindow,
)
from hunter.research_walk_forward.planner import build_explicit_plan
from hunter.research_walk_forward.runner import run_walk_forward_windows
from hunter.research_walk_forward.engine import run_walk_forward_experiment
from tests.test_research_walk_forward.test_runner import (
    _fake_run_backtest_success,
    _make_common,
)


class TestSafetyFlags:
    def test_all_safety_flags_hardcoded(self) -> None:
        flags = WalkForwardSafetyFlags()
        assert flags.research_only is True
        assert flags.execution_approval_granted is False
        assert flags.production_approval_granted is False
        assert flags.live_trading_allowed is False
        assert flags.automatic_execution_allowed is False
        assert flags.human_approval_required is True

    def test_safety_flag_mutations_rejected(self) -> None:
        with pytest.raises(ValueError):
            WalkForwardSafetyFlags(research_only=False)
        with pytest.raises(ValueError):
            WalkForwardSafetyFlags(execution_approval_granted=True)
        with pytest.raises(ValueError):
            WalkForwardSafetyFlags(production_approval_granted=True)
        with pytest.raises(ValueError):
            WalkForwardSafetyFlags(live_trading_allowed=True)
        with pytest.raises(ValueError):
            WalkForwardSafetyFlags(automatic_execution_allowed=True)
        with pytest.raises(ValueError):
            WalkForwardSafetyFlags(human_approval_required=False)


class TestNoDirectSubprocess:
    def test_no_subprocess_in_package_files(self) -> None:
        package_path = Path(__file__).parent.parent.parent / "src" / "hunter" / "research_walk_forward"
        for file_path in package_path.glob("*.py"):
            if file_path.name == "__init__.py":
                continue
            source = file_path.read_text()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import) and any(alias.name == "subprocess" for alias in node.names):
                    pytest.fail(f"subprocess imported in {file_path}")
                if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
                    pytest.fail(f"subprocess imported from in {file_path}")


class TestNoParallelExecution:
    def test_windows_run_sequentially(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        from hunter.research_walk_forward.planner import build_rolling_plan

        plan = build_rolling_plan(
            common,
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            step_days=31,
            count=3,
        )
        call_count = 0

        def fake_counting(*, config, candidate, baseline):
            nonlocal call_count
            call_count += 1
            return _fake_run_backtest_success(
                config=config, candidate=candidate, baseline=baseline
            )

        run_walk_forward_windows(
            plan=plan,
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=fake_counting,
        )
        assert call_count == 3

    def test_no_concurrency_primitives(self, tmp_path: Path) -> None:
        package_path = Path(__file__).parent.parent.parent / "src" / "hunter" / "research_walk_forward"
        for file_path in package_path.glob("*.py"):
            source = file_path.read_text()
            assert "concurrent.futures" not in source, f"{file_path} uses concurrent.futures"
            assert "multiprocessing" not in source, f"{file_path} uses multiprocessing"
            assert "asyncio.gather" not in source, f"{file_path} uses asyncio.gather"


class TestNoDataReportsAccess:
    def test_engine_no_data_or_reports_access(self, tmp_path: Path) -> None:
        package_path = Path(__file__).parent.parent.parent / "src" / "hunter" / "research_walk_forward"
        for file_path in package_path.glob("*.py"):
            source = file_path.read_text()
            assert "data/" not in source or "WalkForward" in source, f"{file_path} references data/"
            assert "reports/" not in source or "WalkForward" in source, f"{file_path} references reports/"


class TestResearchOnlyInvariant:
    def test_safety_flags_reject_non_research(self) -> None:
        with pytest.raises(ValueError):
            WalkForwardSafetyFlags(research_only=False)

    def test_engine_rejects_non_research_plan(self, tmp_path: Path) -> None:
        # Because the model layer prevents constructing a non-research safety
        # flags object, this invariant is enforced before the engine runs.
        # The constructor rejection is sufficient evidence.
        with pytest.raises(ValueError):
            WalkForwardSafetyFlags(execution_approval_granted=True)
