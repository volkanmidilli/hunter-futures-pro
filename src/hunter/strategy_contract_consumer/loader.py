"""Loader for the Strategy Contract Consumption Adapter (MVP-57)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

from hunter.strategy_contract_consumer.models import (
    INPUT_READ_FAILED,
    INVALID_JSON,
    INVALID_SCHEMA,
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

    The function never mutates the caller-supplied input. Mappings are deep-copied
    before they are returned. File paths are read as UTF-8 JSON.
    """
    del config  # Reserved for future caller-supplied configuration; not used today.

    if source is None:
        return None

    if isinstance(source, Mapping):
        data = dict(source)
        return copy.deepcopy(data)

    try:
        path = Path(source)
    except TypeError as exc:
        raise StrategyContractConsumerError(
            f"Unsupported input source type: {type(source).__name__}",
            reason_code=INVALID_SCHEMA,
        ) from exc

    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise StrategyContractConsumerError(
            f"Input file not found: {path}",
            reason_code=INPUT_READ_FAILED,
        ) from exc
    except OSError as exc:
        raise StrategyContractConsumerError(
            f"Input read failed: {path}",
            reason_code=INPUT_READ_FAILED,
        ) from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StrategyContractConsumerError(
            f"Invalid JSON in {path}: {exc}",
            reason_code=INVALID_JSON,
        ) from exc

    if not isinstance(data, dict):
        raise StrategyContractConsumerError(
            f"Expected top-level JSON object in {path}, got {type(data).__name__}",
            reason_code=INVALID_SCHEMA,
        )

    return data
