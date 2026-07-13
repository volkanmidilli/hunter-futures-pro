"""Public API for the one-call coin-discovery pipeline runner (MVP-54).

The runner is a pure, local, caller-triggered coordinator over the existing
discovery, portfolio-construction, controlled-universe, run-orchestrator, and
controlled-universe-export-adapter engines. It does not start services, schedule
jobs, read arbitrary files, connect to networks, exchanges, databases, or external
services, and never emits trading or execution commands.

All outputs are research-only and require human approval before any downstream use.
"""

from __future__ import annotations

from typing import Any

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


# ---------------------------------------------------------------------------
# Engine stubs (implemented in Step 2)
# ---------------------------------------------------------------------------


def run_coin_discovery_pipeline(
    config: CoinDiscoveryPipelineConfig,
) -> CoinDiscoveryPipelineResult:
    """Execute a deterministic one-call coin-discovery pipeline run.

    This is a validation stub for Step 1. The full implementation is deferred to
    Step 2 of MVP-54.
    """
    if not isinstance(config, CoinDiscoveryPipelineConfig):
        raise CoinDiscoveryPipelineError(
            f"config must be a CoinDiscoveryPipelineConfig, got {config!r}"
        )
    raise NotImplementedError(
        "run_coin_discovery_pipeline is implemented in MVP-54 Step 2"
    )


# ---------------------------------------------------------------------------
# Writer stubs (implemented in Step 3)
# ---------------------------------------------------------------------------


def coin_discovery_pipeline_result_to_dict(
    result: CoinDiscoveryPipelineResult,
) -> dict[str, Any]:
    """Convert a pipeline result to a JSON-safe dictionary.

    This is a validation stub for Step 1. The full implementation is deferred to
    Step 3 of MVP-54.
    """
    if not isinstance(result, CoinDiscoveryPipelineResult):
        raise CoinDiscoveryPipelineError(
            f"result must be a CoinDiscoveryPipelineResult, got {result!r}"
        )
    raise NotImplementedError(
        "coin_discovery_pipeline_result_to_dict is implemented in MVP-54 Step 3"
    )


def coin_discovery_pipeline_result_to_json_text(
    result: CoinDiscoveryPipelineResult,
) -> str:
    """Convert a pipeline result to a deterministic JSON string.

    This is a validation stub for Step 1. The full implementation is deferred to
    Step 3 of MVP-54.
    """
    if not isinstance(result, CoinDiscoveryPipelineResult):
        raise CoinDiscoveryPipelineError(
            f"result must be a CoinDiscoveryPipelineResult, got {result!r}"
        )
    raise NotImplementedError(
        "coin_discovery_pipeline_result_to_json_text is implemented in MVP-54 Step 3"
    )


def coin_discovery_pipeline_result_to_markdown_text(
    result: CoinDiscoveryPipelineResult,
) -> str:
    """Convert a pipeline result to a deterministic Markdown string.

    This is a validation stub for Step 1. The full implementation is deferred to
    Step 3 of MVP-54.
    """
    if not isinstance(result, CoinDiscoveryPipelineResult):
        raise CoinDiscoveryPipelineError(
            f"result must be a CoinDiscoveryPipelineResult, got {result!r}"
        )
    raise NotImplementedError(
        "coin_discovery_pipeline_result_to_markdown_text is implemented in MVP-54 Step 3"
    )


def write_coin_discovery_pipeline_result(
    result: CoinDiscoveryPipelineResult,
    config: CoinDiscoveryPipelineConfig,
) -> tuple[str, ...]:
    """Write pipeline result artifacts to local paths.

    This is a validation stub for Step 1. The full implementation is deferred to
    Step 3 of MVP-54.
    """
    if not isinstance(result, CoinDiscoveryPipelineResult):
        raise CoinDiscoveryPipelineError(
            f"result must be a CoinDiscoveryPipelineResult, got {result!r}"
        )
    if not isinstance(config, CoinDiscoveryPipelineConfig):
        raise CoinDiscoveryPipelineError(
            f"config must be a CoinDiscoveryPipelineConfig, got {config!r}"
        )
    raise NotImplementedError(
        "write_coin_discovery_pipeline_result is implemented in MVP-54 Step 3"
    )


def atomic_write_json_coin_discovery_pipeline_result(
    result: CoinDiscoveryPipelineResult,
    path: str,
) -> str:
    """Atomically write a pipeline result JSON packet.

    This is a validation stub for Step 1. The full implementation is deferred to
    Step 3 of MVP-54.
    """
    if not isinstance(result, CoinDiscoveryPipelineResult):
        raise CoinDiscoveryPipelineError(
            f"result must be a CoinDiscoveryPipelineResult, got {result!r}"
        )
    if not isinstance(path, str) or not path.strip():
        raise CoinDiscoveryPipelineError(
            f"path must be a non-empty string, got {path!r}"
        )
    raise NotImplementedError(
        "atomic_write_json_coin_discovery_pipeline_result is implemented in MVP-54 Step 3"
    )


def atomic_write_markdown_coin_discovery_pipeline_result(
    result: CoinDiscoveryPipelineResult,
    path: str,
) -> str:
    """Atomically write a pipeline result Markdown packet.

    This is a validation stub for Step 1. The full implementation is deferred to
    Step 3 of MVP-54.
    """
    if not isinstance(result, CoinDiscoveryPipelineResult):
        raise CoinDiscoveryPipelineError(
            f"result must be a CoinDiscoveryPipelineResult, got {result!r}"
        )
    if not isinstance(path, str) or not path.strip():
        raise CoinDiscoveryPipelineError(
            f"path must be a non-empty string, got {path!r}"
        )
    raise NotImplementedError(
        "atomic_write_markdown_coin_discovery_pipeline_result is implemented in MVP-54 Step 3"
    )
