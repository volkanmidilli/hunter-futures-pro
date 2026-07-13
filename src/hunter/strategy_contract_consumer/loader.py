"""Loader for the Strategy Contract Consumption Adapter (MVP-57)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from hunter.strategy_contract_consumer.models import (
    StrategyContractConsumerConfig,
    StrategyContractConsumerError,
)


def load_strategy_contract_input(
    source: Path | str | Mapping[str, Any] | None,
    *,
    config: StrategyContractConsumerConfig | None = None,
) -> dict[str, Any] | None:
    """Load a strategy-contract input from a file path or in-memory mapping.

    Returns ``None`` for ``None`` input so the engine can emit ``MISSING_INPUT``.
    Raises ``StrategyContractConsumerError`` for read failures, invalid JSON, or
    a non-object top-level JSON value.
    """
    raise NotImplementedError("load_strategy_contract_input is implemented in Step 3")
