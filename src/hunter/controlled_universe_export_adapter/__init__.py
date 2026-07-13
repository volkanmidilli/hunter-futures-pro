"""Controlled Universe Export Adapter public API (MVP-53).

The adapter consumes a `ControlledUniverseReport` and produces deterministic,
research-only export artifacts: whitelist representation, blacklist
representation, and a human-readable per-pair inclusion/exclusion summary.

All outputs are explicitly marked as research-only and require human approval
before any downstream use. The adapter is fail-closed and never integrates with
Freqtrade runtime, exchanges, databases, schedulers, or live trading systems.
"""

from __future__ import annotations

from hunter.controlled_universe_export_adapter.engine import (
    build_controlled_universe_export,
    build_controlled_universe_export_from_run_result,
)
from hunter.controlled_universe_export_adapter.models import (
    BLOCKED_EXPORT,
    CONTROLLED_UNIVERSE_EXPORT_REASON_CODES,
    CONTROLLED_UNIVERSE_EXPORT_VERSION,
    EXPORT_HUMAN_APPROVAL_REQUIRED,
    EXPORT_RESEARCH_ONLY,
    MISSING_REPORT_INPUT,
    NO_AUTOMATIC_CONFIG_MUTATION,
    NO_FREQTRADE_RUNTIME_CONNECTION,
    NO_INCLUDED_PAIRS,
    ControlledUniverseExportConfig,
    ControlledUniverseExportError,
    ControlledUniverseExportResult,
    ControlledUniversePairExportSummary,
)
from hunter.controlled_universe_export_adapter.writer import (
    ControlledUniverseExportWriterError,
    atomic_write_json_controlled_universe_export,
    atomic_write_markdown_controlled_universe_export,
    controlled_universe_export_to_dict,
    controlled_universe_export_to_json_text,
    controlled_universe_export_to_markdown_text,
    write_controlled_universe_export,
)

__all__ = [
    # Version
    "CONTROLLED_UNIVERSE_EXPORT_VERSION",
    # Reason codes
    "MISSING_REPORT_INPUT",
    "BLOCKED_EXPORT",
    "NO_INCLUDED_PAIRS",
    "EXPORT_RESEARCH_ONLY",
    "EXPORT_HUMAN_APPROVAL_REQUIRED",
    "NO_FREQTRADE_RUNTIME_CONNECTION",
    "NO_AUTOMATIC_CONFIG_MUTATION",
    "CONTROLLED_UNIVERSE_EXPORT_REASON_CODES",
    # Models
    "ControlledUniverseExportConfig",
    "ControlledUniverseExportResult",
    "ControlledUniversePairExportSummary",
    "ControlledUniverseExportError",
    # Engine
    "build_controlled_universe_export",
    "build_controlled_universe_export_from_run_result",
    # Writer
    "ControlledUniverseExportWriterError",
    "controlled_universe_export_to_dict",
    "controlled_universe_export_to_json_text",
    "controlled_universe_export_to_markdown_text",
    "write_controlled_universe_export",
    "atomic_write_json_controlled_universe_export",
    "atomic_write_markdown_controlled_universe_export",
]
