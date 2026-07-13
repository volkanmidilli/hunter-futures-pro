"""Public API for the one-call coin-discovery pipeline runner (MVP-54).

The runner is a pure, local, caller-triggered coordinator over the existing
discovery, portfolio-construction, controlled-universe, run-orchestrator, and
controlled-universe-export-adapter engines. It does not start services, schedule
jobs, read arbitrary files, connect to networks, exchanges, databases, or external
services, and never emits trading or execution commands.

All outputs are research-only and require human approval before any downstream use.
"""

from __future__ import annotations

from hunter.coin_discovery_pipeline.models import (
    COIN_DISCOVERY_PIPELINE_REASON_CODES,
    COIN_DISCOVERY_PIPELINE_VERSION,
    EXPORT_SKIPPED,
    INVALID_PIPELINE_CONFIG,
    NO_AUTOMATIC_CONFIG_MUTATION,
    NO_FREQTRADE_RUNTIME_CONNECTION,
    PIPELINE_HUMAN_APPROVAL_REQUIRED,
    PIPELINE_RESEARCH_ONLY,
    PIPELINE_RUN_BLOCKED,
    PIPELINE_RUN_FAILED,
    PIPELINE_RUN_PARTIAL,
    CoinDiscoveryPipelineConfig,
    CoinDiscoveryPipelineError,
    CoinDiscoveryPipelineResult,
    CoinDiscoveryPipelineSafetyFlags,
    PipelineState,
)

__all__ = [
    # Version
    "COIN_DISCOVERY_PIPELINE_VERSION",
    # Reason codes
    "INVALID_PIPELINE_CONFIG",
    "PIPELINE_RESEARCH_ONLY",
    "PIPELINE_HUMAN_APPROVAL_REQUIRED",
    "NO_FREQTRADE_RUNTIME_CONNECTION",
    "NO_AUTOMATIC_CONFIG_MUTATION",
    "EXPORT_SKIPPED",
    "PIPELINE_RUN_FAILED",
    "PIPELINE_RUN_BLOCKED",
    "PIPELINE_RUN_PARTIAL",
    "COIN_DISCOVERY_PIPELINE_REASON_CODES",
    # Enums
    "PipelineState",
    # Models
    "CoinDiscoveryPipelineConfig",
    "CoinDiscoveryPipelineResult",
    "CoinDiscoveryPipelineSafetyFlags",
    "CoinDiscoveryPipelineError",
    # Engine
    "run_coin_discovery_pipeline",
    # Writer
    "coin_discovery_pipeline_result_to_dict",
    "coin_discovery_pipeline_result_to_json_text",
    "coin_discovery_pipeline_result_to_markdown_text",
    "write_coin_discovery_pipeline_result",
    "atomic_write_json_coin_discovery_pipeline_result",
    "atomic_write_markdown_coin_discovery_pipeline_result",
]

from hunter.coin_discovery_pipeline.engine import (
    run_coin_discovery_pipeline,
)
from hunter.coin_discovery_pipeline.writer import (
    atomic_write_json_coin_discovery_pipeline_result,
    atomic_write_markdown_coin_discovery_pipeline_result,
    coin_discovery_pipeline_result_to_dict,
    coin_discovery_pipeline_result_to_json_text,
    coin_discovery_pipeline_result_to_markdown_text,
    write_coin_discovery_pipeline_result,
)
