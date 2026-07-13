"""Engine for the Freqtrade Universe Consumption Adapter (MVP-55).

Step 1 placeholder: the adapter models and public API are defined;
`build_freqtrade_universe_adapter_result` will be implemented in Step 2.
"""

from __future__ import annotations

from typing import Any

from hunter.controlled_universe_export_adapter.models import ControlledUniverseExportResult
from hunter.freqtrade_universe_adapter.models import (
    FreqtradeUniverseAdapterConfig,
    FreqtradeUniverseAdapterResult,
)


def build_freqtrade_universe_adapter_result(
    export_result: ControlledUniverseExportResult | None,
    config: FreqtradeUniverseAdapterConfig | None = None,
) -> FreqtradeUniverseAdapterResult:
    """Build a Freqtrade-compatible universe packet from a controlled export.

    Step 1 placeholder: this function will be implemented in Step 2.
    """
    raise NotImplementedError(
        "build_freqtrade_universe_adapter_result is implemented in Step 2"
    )


# Convenience helper used by the engine; stubbed for Step 1.
def _now_utc() -> Any:
    """Return the current UTC datetime."""
    raise NotImplementedError("_now_utc is implemented in Step 2")
