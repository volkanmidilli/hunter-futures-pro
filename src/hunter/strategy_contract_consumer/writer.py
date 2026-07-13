"""Writer for the Strategy Contract Consumption Adapter (MVP-57)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hunter.strategy_contract_consumer.models import (
    StrategyContractConsumerConfig,
    ValidatedStrategyContext,
)


def strategy_context_result_to_dict(
    result: ValidatedStrategyContext,
) -> dict[str, Any]:
    """Serialize a validation result to an ordered, deterministic dictionary."""
    raise NotImplementedError("strategy_context_result_to_dict is implemented in Step 6")


def strategy_context_result_to_json_text(
    result: ValidatedStrategyContext,
    *,
    indent: int | None = 2,
) -> str:
    """Serialize a validation result to JSON text."""
    raise NotImplementedError(
        "strategy_context_result_to_json_text is implemented in Step 6"
    )


def strategy_context_result_to_markdown_text(
    result: ValidatedStrategyContext,
) -> str:
    """Serialize a validation result to Markdown text."""
    raise NotImplementedError(
        "strategy_context_result_to_markdown_text is implemented in Step 6"
    )


def write_strategy_context_validation_result(
    result: ValidatedStrategyContext,
    output_dir: Path | str,
    config: StrategyContractConsumerConfig,
) -> tuple[Path, Path]:
    """Write JSON and Markdown artifacts atomically.

    Returns the paths to the written JSON and Markdown files.
    """
    raise NotImplementedError(
        "write_strategy_context_validation_result is implemented in Step 6"
    )
