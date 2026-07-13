"""Writer for the Freqtrade Universe Consumption Adapter (MVP-55).

Step 1 placeholder: the adapter models and public API are defined; writer
functions will be implemented in Step 3.
"""

from __future__ import annotations

from typing import Any

from hunter.freqtrade_universe_adapter.models import (
    FreqtradeUniverseAdapterConfig,
    FreqtradeUniverseAdapterResult,
)


def freqtrade_universe_adapter_result_to_dict(
    result: FreqtradeUniverseAdapterResult,
) -> dict[str, Any]:
    """Serialize a result to a JSON-safe dict."""
    raise NotImplementedError("freqtrade_universe_adapter_result_to_dict is implemented in Step 3")


def freqtrade_universe_adapter_result_to_json_text(
    result: FreqtradeUniverseAdapterResult,
) -> str:
    """Serialize a result to JSON text."""
    raise NotImplementedError("freqtrade_universe_adapter_result_to_json_text is implemented in Step 3")


def freqtrade_universe_adapter_result_to_markdown_text(
    result: FreqtradeUniverseAdapterResult,
) -> str:
    """Serialize a result to Markdown text."""
    raise NotImplementedError("freqtrade_universe_adapter_result_to_markdown_text is implemented in Step 3")


def atomic_write_json_freqtrade_universe_adapter_result(
    result: FreqtradeUniverseAdapterResult,
    path: str,
) -> None:
    """Atomically write a result as JSON to the given path."""
    raise NotImplementedError("atomic_write_json_freqtrade_universe_adapter_result is implemented in Step 3")


def atomic_write_markdown_freqtrade_universe_adapter_result(
    result: FreqtradeUniverseAdapterResult,
    path: str,
) -> None:
    """Atomically write a result as Markdown to the given path."""
    raise NotImplementedError("atomic_write_markdown_freqtrade_universe_adapter_result is implemented in Step 3")


def write_freqtrade_universe_adapter_result(
    result: FreqtradeUniverseAdapterResult,
    output_dir: str | None,
    config: FreqtradeUniverseAdapterConfig,
) -> dict[str, str]:
    """Write all enabled artifacts for the adapter result.

    If `output_dir` is provided, it overrides `config.output_dir`;
    otherwise `config.output_dir` and `config.markdown_output_dir` are used.
    """
    raise NotImplementedError("write_freqtrade_universe_adapter_result is implemented in Step 3")
