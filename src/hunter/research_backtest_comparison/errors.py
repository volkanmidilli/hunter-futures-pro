"""Error types for the research backtest comparison harness (MVP-65 / SPEC-066)."""

from hunter.research_backtest_comparison.models import (
    ResearchBacktestComparisonError,
    ResearchBacktestComparisonConfigError,
    ResearchBacktestComparisonValidationError,
    ResearchBacktestComparisonExecutableError,
    ResearchBacktestComparisonFairnessError,
    ResearchBacktestComparisonRunnerError,
    ResearchBacktestComparisonParserError,
    ResearchBacktestComparisonWriterError,
)

__all__ = [
    "ResearchBacktestComparisonError",
    "ResearchBacktestComparisonConfigError",
    "ResearchBacktestComparisonValidationError",
    "ResearchBacktestComparisonExecutableError",
    "ResearchBacktestComparisonFairnessError",
    "ResearchBacktestComparisonRunnerError",
    "ResearchBacktestComparisonParserError",
    "ResearchBacktestComparisonWriterError",
]
