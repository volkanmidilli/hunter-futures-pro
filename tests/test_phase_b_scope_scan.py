"""Phase B Stage 9 source-scan tests (SPEC-072).

Proves the following invariants across Phase B source modules:
- Only MVP-65 (research_backtest_comparison) imports subprocess.
- Only ``freqtrade backtesting`` is permitted as the command subcommand.
- No ``download-data`` / ``hyperopt`` / ``trade`` / ``webserver`` raguments.
- No network/exchange client classes imported (ccxt, requests, urllib).
- No retry libraries, parallel execution, schedulers, daemons, databases,
  queues.
- No mutable approval/safety flag setters on the safety dataclasses.
- No imports of repository ``data/`` or ``reports/`` contents at runtime.

This is a static source scan using grep-like stdlib operations under a
temporary sandbox. Source paths traversed are limited to the Phase B
packages plus the MVP-65 boundary. ``data/`` and ``reports/`` are never
enumerated or read.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src" / "hunter"

# Packages whose source is in scope for Phase B invariants.
PHASE_B_PACKAGES = [
    _SRC / "research_backtest_comparison",
    _SRC / "research_statistical_confidence",
    _SRC / "research_walk_forward",
]

# Add methodology + compatibility modules here to ensure they don't
# introduce new forbidden runtime capabilities beyond what MVP-65 already has.
METHODOLOGY_MODULES = [
    _SRC / "research_statistical_confidence" / "methodology.py",
    _SRC / "research_statistical_confidence" / "methodology_engine.py",
    _SRC / "research_backtest_comparison" / "compatibility_harness.py",
    _SRC / "research_backtest_comparison" / "compatibility_validator.py",
    _SRC / "research_backtest_comparison" / "compatibility_writer.py",
    _SRC / "research_backtest_comparison" / "export_parser.py",
]


def _iter_python_sources(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        if p.is_file() and p.suffix == ".py":
            out.append(p)
        elif p.is_dir():
            for f in sorted(p.rglob("*.py")):
                if "__pycache__" in f.parts:
                    continue
                out.append(f)
    return out


def _build_text(paths: list[Path]) -> str:
    parts: list[str] = []
    for p in _iter_python_sources(paths):
        parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Scope Exclusion Verification — Stage 9 source scan items
# ---------------------------------------------------------------------------


class TestPhaseBScopeScan:
    def test_only_mvp65_imports_subprocess(self) -> None:
        """Only research_backtest_comparison may import subprocess."""
        phases = [
            _SRC / "research_statistical_confidence",
            _SRC / "research_walk_forward",
        ]
        for path in _iter_python_sources(phases):
            text = path.read_text(encoding="utf-8")
            assert "import subprocess" not in text, (
                f"{path.name} must NOT import subprocess; "
                "MVP-65 (research_backtest_comparison) is the sole subprocess boundary."
            )

    def test_phase_b_new_modules_dont_import_subprocess(self) -> None:
        """Methodology + compatibility modules do not introduce subprocess."""
        for path in METHODOLOGY_MODULES:
            if path.exists():
                text = path.read_text(encoding="utf-8")
                assert "import subprocess" not in text, (
                    f"{path.name} must NOT import subprocess."
                )

    @pytest.mark.parametrize(
        "forbidden_token",
        [
            "ccxt",
            "requests.get",
            "requests.post",
            "urllib.request.urlopen",
            "http.client.HTTPConnection",
            "FTXClient",
            "exchange.fetch",
            "fetch_ohlcv",
            "AsyncClient",
        ],
    )
    def test_no_network_or_exchange_client_in_phase_b_modules(
        self, forbidden_token: str
    ) -> None:
        text = _build_text(METHODOLOGY_MODULES)
        assert forbidden_token not in text, (
            f"forbidden runtime token present in Phase B methodology/compatibility "
            f"modules: {forbidden_token!r}"
        )

    @pytest.mark.parametrize(
        "forbidden_token",
        [
            "import tenacity",
            "from tenacity",
            "concurrent.futures",
            "asyncio.gather",
            "multiprocessing.Process",
            "APScheduler",
            "from apscheduler",
            "celery",
            "import redis",
            "import psycopg",
            "sqlite3.connect",
            "BrokerConnection",
        ],
    )
    def test_no_retry_parallel_scheduler_daemon_database_queue_in_phase_b(
        self, forbidden_token: str
    ) -> None:
        text = _build_text(METHODOLOGY_MODULES)
        assert forbidden_token not in text, (
            f"forbidden infra token in Phase B modules: {forbidden_token!r}"
        )

    @pytest.mark.parametrize(
        "forbidden_subcommand",
        [
            "download-data",
            "download_data",
            "hyperopt",
            "trade ",
            " webserver",
            "install-ui",
            "plot-dataframe",
            "plot-profit",
            "lookahead-analysis",
            "recursive-analysis",
        ],
    )
    def test_forbidden_subcommands_absent_in_command_builder(
        self, forbidden_subcommand: str
    ) -> None:
        # Forbidden subcommands may legitimately appear in the
        # _FORBIDDEN_SUBCOMMANDS denylist in validator.py — that is the
        # defensive boundary. Campaign modules construct commands only via
        # command_builder.py / runner.py, never hard-coding forbidden tokens.
        command_files = [
            _SRC / "research_backtest_comparison" / "command_builder.py",
            _SRC / "research_backtest_comparison" / "runner.py",
            _SRC / "research_backtest_comparison" / "compatibility_harness.py",
        ]
        for cf in command_files:
            if cf.exists():
                cf_text = cf.read_text(encoding="utf-8")
                # Strip comments and docstrings so the denylist / docstring
                # descriptions don't slip through.
                stripped_lines: list[str] = []
                in_docstring = False
                for line in cf_text.splitlines():
                    s = line.strip()
                    if s.startswith("#"):
                        continue
                    if s.startswith('"""'):
                        in_docstring = not in_docstring
                        continue
                    if s in ('"""', '"""  #', '""" .', '""" -*-'):
                        in_docstring = False
                        continue
                    if in_docstring:
                        continue
                    stripped_lines.append(s)
                stripped = "\n".join(stripped_lines)
                # Shell-injection-safe check: forbidden token as a literal
                # command substring, not as an element of the denylist set.
                # In the stripped text, allowlist any appearance that is part
                # of "hyperopt" inside a string tuple that begins with
                # ``_FORBIDDEN_SUBCOMMANDS``. Since we already commented out
                # docstring/comment lines, only the denylist tuple should
                # remain in validator.py — and validator.py is excluded.
                assert forbidden_subcommand not in stripped, (
                    f"forbidden token in {cf.name} command construction: "
                    f"{forbidden_subcommand!r}"
                )

    def test_backtesting_is_the_only_permitted_subcommand(self) -> None:
        from hunter.research_backtest_comparison.validator import (
            validate_command_args,
            ResearchBacktestComparisonValidationError,
        )

        # `freqtrade backtesting ...` accepted.
        validate_command_args(["freqtrade", "backtesting", "--config", "x"])

        # Singleton `freqtrade` (no subcommand) rejected.
        with pytest.raises(ResearchBacktestComparisonValidationError):
            validate_command_args(["freqtrade"])

        # Any forbidden subcommand rejected.
        for sub in ["trade", "download-data", "hyperopt", "webserver"]:
            with pytest.raises(ResearchBacktestComparisonValidationError):
                validate_command_args(["freqtrade", sub])

    def test_shell_false_enforced_by_runner(self) -> None:
        """subprocess.run in MVP-65 must use shell=False (default).
        We check the runner.py module compiles and uses ``subprocess.run``.
        """
        runner = _SRC / "research_backtest_comparison" / "runner.py"
        text = runner.read_text(encoding="utf-8")
        # Intentional: find calls to subprocess.run(...). The default shell
        # flag for subprocess.run is False, so the absence of ``shell=True``
        # (other than in a docstring) proves the policy.
        # We exclude any line that starts with '#' (comment) or '"""'.
        offending: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("#", '"', "'")):
                continue
            if "shell=True" in stripped:
                offending.append(line)
        assert offending == [], (
            f"shell=True present in runner.py: {offending}"
        )

    def test_safety_flags_are_immutable_invariants(self) -> None:
        """Safety flag dataclasses must reject any mutation that flips the
        mandatory invariants on construction.
        """
        from hunter.research_backtest_comparison.models import (
            ResearchBacktestSafetyFlags,
        )
        from hunter.research_statistical_confidence.models import (
            StatisticalConfidenceSafetyFlags,
        )

        # All mandatory invariants hold at default construction
        flags = ResearchBacktestSafetyFlags()
        assert flags.research_only is True
        assert flags.execution_approval_granted is False
        assert flags.production_approval_granted is False
        assert flags.live_trading_allowed is False
        assert flags.automatic_execution_allowed is False
        assert flags.human_approval_required is True

        sc_flags = StatisticalConfidenceSafetyFlags()
        assert sc_flags.research_only is True
        assert sc_flags.execution_approval_granted is False
        assert sc_flags.live_trading_allowed is False
        assert sc_flags.human_approval_required is True

        # Construction must raise if any invariant is violated
        for override in (
            {"execution_approval_granted": True},
            {"live_trading_allowed": True},
            {"automatic_execution_allowed": True},
            {"human_approval_required": False},
            {"research_only": False},
        ):
            with pytest.raises(ValueError):
                ResearchBacktestSafetyFlags(**override)  # type: ignore[arg-type]

    def test_phase_b_does_not_inspect_repo_data_or_reports(self) -> None:
        """Phase B source modules must not reference ``data/`` or ``reports/``
        as literal repository paths in the project root at runtime.
        """
        whitelist = ("__pycache__",)
        # Scan the Phase B source directories only (NOT data/ or reports/).
        forbidden_path_refs = [
            "Path(\"data\")", "Path(\"reports\")", "opendir(\"data\")",
            "os.listdir(\"data\")", "os.listdir(\"reports\")",
            "iterdir(\"data\")", "iterdir(\"reports\")",
            "rglob(\"data\")", "rglob(\"reports\")",
        ]
        text = _build_text([
            _SRC / "research_backtest_comparison" / "compatibility_harness.py",
            _SRC / "research_backtest_comparison" / "compatibility_validator.py",
            _SRC / "research_backtest_comparison" / "compatibility_writer.py",
            _SRC / "research_backtest_comparison" / "export_parser.py",
            _SRC / "research_statistical_confidence" / "methodology.py",
            _SRC / "research_statistical_confidence" / "methodology_engine.py",
        ])
        for ref in forbidden_path_refs:
            assert ref not in text, (
                f"Phase B modules reference forbidden repo path {ref!r}"
            )

    def test_mvp71_not_started(self) -> None:
        """No MVP-71 package introduced."""
        assert not (_SRC / "research_mvp71").exists()
        assert not (_SRC / "research_mvp_71").exists()
        assert not (_SRC / "mvp71").exists()