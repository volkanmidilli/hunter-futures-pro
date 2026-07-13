"""Freqtrade Universe Consumption Adapter public API (MVP-55).

The adapter consumes a `ControlledUniverseExportResult` and produces
deterministic, research-only, human-approval-required artifacts that can be
reviewed before any Freqtrade consumption. Engine and writer behavior are
stubbed in Step 1 and implemented in Steps 2 and 3.
"""

from __future__ import annotations

from hunter.freqtrade_universe_adapter.engine import (
    build_freqtrade_universe_adapter_result,
)
from hunter.freqtrade_universe_adapter.models import (
    BLOCKED_EXPORT_INPUT,
    CONTRADICTORY_PAIR,
    DUPLICATE_PAIR,
    EMPTY_WHITELIST,
    EXPORT_HUMAN_APPROVAL_REQUIRED,
    EXPORT_RESEARCH_ONLY,
    FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES,
    FREQTRADE_UNIVERSE_ADAPTER_VERSION,
    INVALID_PAIR_FORMAT,
    MISSING_EXPORT_INPUT,
    NO_AUTOMATIC_CONFIG_MUTATION,
    NO_FREQTRADE_RUNTIME_CONNECTION,
    STALE_EXPORT_INPUT,
    FreqtradeUniverseAdapterConfig,
    FreqtradeUniverseAdapterError,
    FreqtradeUniverseAdapterResult,
)
from hunter.freqtrade_universe_adapter.writer import (
    atomic_write_json_freqtrade_universe_adapter_result,
    atomic_write_markdown_freqtrade_universe_adapter_result,
    freqtrade_universe_adapter_result_to_dict,
    freqtrade_universe_adapter_result_to_json_text,
    freqtrade_universe_adapter_result_to_markdown_text,
    write_freqtrade_universe_adapter_result,
)

__all__ = [
    # Version
    "FREQTRADE_UNIVERSE_ADAPTER_VERSION",
    # Reason codes
    "MISSING_EXPORT_INPUT",
    "BLOCKED_EXPORT_INPUT",
    "EMPTY_WHITELIST",
    "INVALID_PAIR_FORMAT",
    "DUPLICATE_PAIR",
    "CONTRADICTORY_PAIR",
    "EXPORT_RESEARCH_ONLY",
    "EXPORT_HUMAN_APPROVAL_REQUIRED",
    "NO_FREQTRADE_RUNTIME_CONNECTION",
    "NO_AUTOMATIC_CONFIG_MUTATION",
    "STALE_EXPORT_INPUT",
    "FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES",
    # Models
    "FreqtradeUniverseAdapterConfig",
    "FreqtradeUniverseAdapterResult",
    "FreqtradeUniverseAdapterError",
    # Engine
    "build_freqtrade_universe_adapter_result",
    # Writer
    "freqtrade_universe_adapter_result_to_dict",
    "freqtrade_universe_adapter_result_to_json_text",
    "freqtrade_universe_adapter_result_to_markdown_text",
    "atomic_write_json_freqtrade_universe_adapter_result",
    "atomic_write_markdown_freqtrade_universe_adapter_result",
    "write_freqtrade_universe_adapter_result",
]
