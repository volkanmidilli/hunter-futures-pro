"""Engine for the one-call coin-discovery pipeline runner (MVP-54 Step 2)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hunter.coin_discovery_pipeline.models import (
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
from hunter.controlled_universe_export_adapter import (
    BLOCKED_EXPORT,
    build_controlled_universe_export_from_run_result,
)
from hunter.controlled_universe_export_adapter.models import (
    ControlledUniverseExportConfig,
    ControlledUniverseExportResult,
)
from hunter.run_orchestrator import (
    build_coin_discovery_run_plan,
    build_research_run_result,
)
from hunter.run_orchestrator.models import (
    ResearchRunResult,
    ResearchRunState,
    ResearchRunConfig,
)


def _utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


def _validate_pipeline_config(
    config: Any,
) -> tuple[CoinDiscoveryPipelineConfig | None, str]:
    """Validate the incoming config object.

    Returns (valid_config, error_message). If the input is not a valid
    CoinDiscoveryPipelineConfig, error_message is non-empty and valid_config is
    None.
    """
    if not isinstance(config, CoinDiscoveryPipelineConfig):
        return None, f"config must be a CoinDiscoveryPipelineConfig, got {type(config).__name__}"
    return config, ""


def _build_run_config(
    config: CoinDiscoveryPipelineConfig,
) -> ResearchRunConfig:
    """Return the ResearchRunConfig to use for the orchestrator.

    If the caller supplied a run_config, it is used. Otherwise, a default is
    created under ``<pipeline.output_dir>/<run_id>`` so orchestrator artifacts
    are grouped by run ID per SPEC-055.
    """
    if config.run_config is not None:
        return config.run_config
    return ResearchRunConfig(
        output_dir=str(Path(config.output_dir) / config.run_id),
        fail_fast=config.fail_fast,
        write_artifacts=config.write_artifacts,
    )


def _build_export_config(
    config: CoinDiscoveryPipelineConfig,
) -> ControlledUniverseExportConfig:
    """Return the ControlledUniverseExportConfig to use for export.

    If the caller supplied an export_config, it is used. Otherwise, default
    output_dir and markdown_output_dir are derived from the pipeline output_dir
    and run_id per SPEC-055.
    """
    if config.export_config is not None:
        return config.export_config
    base = Path(config.output_dir)
    run_base = base / config.run_id
    pkg_name = base.name or "coin_discovery_pipeline"
    return ControlledUniverseExportConfig(
        output_dir=str(run_base / "controlled_universe_export"),
        markdown_output_dir=str(Path("reports") / pkg_name / config.run_id / "controlled_universe_export"),
    )


def _map_run_state_to_pipeline_state(
    run_state: ResearchRunState,
) -> PipelineState:
    """Map a ResearchRunState to a PipelineState deterministically."""
    mapping = {
        ResearchRunState.COMPLETED: PipelineState.COMPLETED,
        ResearchRunState.FAILED: PipelineState.FAILED,
        ResearchRunState.BLOCKED: PipelineState.BLOCKED,
        ResearchRunState.PARTIAL: PipelineState.PARTIAL,
    }
    try:
        return mapping[run_state]
    except KeyError as exc:
        raise CoinDiscoveryPipelineError(
            f"Unknown ResearchRunState: {run_state!r}"
        ) from exc


def _build_pipeline_safety_flags() -> CoinDiscoveryPipelineSafetyFlags:
    """Return the fixed safety flags for every pipeline run."""
    return CoinDiscoveryPipelineSafetyFlags()


def _build_reason_codes(
    run_result: ResearchRunResult | None,
    export_result: ControlledUniverseExportResult | None,
    extra_codes: tuple[str, ...],
) -> tuple[str, ...]:
    """Aggregate and deduplicate reason codes from pipeline, run, and export."""
    code_set: dict[str, None] = {}
    for code in (
        PIPELINE_RESEARCH_ONLY,
        PIPELINE_HUMAN_APPROVAL_REQUIRED,
        NO_FREQTRADE_RUNTIME_CONNECTION,
        NO_AUTOMATIC_CONFIG_MUTATION,
    ):
        code_set[code] = None
    for code in extra_codes:
        code_set[code] = None
    if run_result is not None:
        for code in run_result.reason_codes:
            code_set[code] = None
    if export_result is not None:
        for code in export_result.reason_codes:
            code_set[code] = None
    return tuple(sorted(code_set.keys()))


def _export_is_blocked(
    export_result: ControlledUniverseExportResult,
) -> bool:
    """Return True if the export result represents a fail-closed blocked export.

    A blocked export has no included pairs and/or includes the BLOCKED_EXPORT
    reason code propagated by the export adapter.
    """
    if BLOCKED_EXPORT in export_result.reason_codes:
        return True
    if len(export_result.whitelist) == 0 and len(export_result.per_pair_summary) > 0:
        return True
    return False


def run_coin_discovery_pipeline(
    config: CoinDiscoveryPipelineConfig,
) -> CoinDiscoveryPipelineResult:
    """Execute a deterministic one-call coin-discovery pipeline run.

    The runner validates the config, builds the research run plan, executes it
    through the existing orchestrator, optionally invokes the controlled-universe
    export adapter, and returns a structured result with explicit safety flags.

    Normal failures (blocked, failed, partial) are returned as deterministic
    CoinDiscoveryPipelineResult objects. Unexpected internal errors are wrapped in
    CoinDiscoveryPipelineError and raised so callers can distinguish them from
    deterministic safety outcomes.
    """
    valid_config, error_message = _validate_pipeline_config(config)
    if valid_config is None:
        return CoinDiscoveryPipelineResult(
            run_id="blocked",
            state=PipelineState.BLOCKED,
            run_result=None,
            export_result=None,
            export_paths=(),
            pipeline_paths=(),
            safety_flags=_build_pipeline_safety_flags(),
            reason_codes=(
                INVALID_PIPELINE_CONFIG,
                PIPELINE_RESEARCH_ONLY,
                PIPELINE_HUMAN_APPROVAL_REQUIRED,
                NO_FREQTRADE_RUNTIME_CONNECTION,
                NO_AUTOMATIC_CONFIG_MUTATION,
            ),
            metadata={},
        )

    config = valid_config

    try:
        run_config = _build_run_config(config)
        export_config = _build_export_config(config)

        plan = build_coin_discovery_run_plan(
            run_id=config.run_id,
            discovery_inputs=config.discovery_inputs,
            portfolio_construction_inputs=config.portfolio_construction_inputs,
            execution_context=config.execution_context,
            controlled_universe_config=config.controlled_universe_config,
            discovery_config=config.discovery_config,
            portfolio_construction_config=config.portfolio_construction_config,
            metadata=config.metadata,
        )

        run_result = build_research_run_result(plan, run_config)
        pipeline_state = _map_run_state_to_pipeline_state(run_result.state)

        export_result: ControlledUniverseExportResult | None = None
        export_paths: tuple[str, ...] = ()
        extra_reason_codes: tuple[str, ...] = ()

        if config.export_enabled:
            export_result = build_controlled_universe_export_from_run_result(
                run_result, export_config
            )
            # Treat an unsafe export result (e.g., empty whitelist, blocked export)
            # as a fail-closed signal: retain the result but surface the blocked
            # reason code. The export adapter already builds fail-closed exports.
            if _export_is_blocked(export_result):
                extra_reason_codes = (PIPELINE_RUN_BLOCKED,)
        else:
            extra_reason_codes = (EXPORT_SKIPPED,)

        # Add run-state-specific pipeline reason codes.
        state_reasons = {
            PipelineState.FAILED: (PIPELINE_RUN_FAILED,),
            PipelineState.BLOCKED: (PIPELINE_RUN_BLOCKED,),
            PipelineState.PARTIAL: (PIPELINE_RUN_PARTIAL,),
        }.get(pipeline_state, ())
        extra_reason_codes = tuple(
            dict.fromkeys([*extra_reason_codes, *state_reasons]).keys()
        )

        reason_codes = _build_reason_codes(
            run_result, export_result, extra_reason_codes
        )
        safety_flags = _build_pipeline_safety_flags()

        return CoinDiscoveryPipelineResult(
            run_id=config.run_id,
            state=pipeline_state,
            run_result=run_result,
            export_result=export_result,
            export_paths=export_paths,
            pipeline_paths=(),
            safety_flags=safety_flags,
            reason_codes=reason_codes,
            metadata=dict(config.metadata),
        )

    except Exception as exc:
        # Unexpected errors (e.g., ValueError from the plan builder) are wrapped
        # and re-raised as CoinDiscoveryPipelineError so callers can handle them
        # distinctly from deterministic safety outcomes.
        raise CoinDiscoveryPipelineError(
            f"Unexpected pipeline failure for run {config.run_id}: {exc}"
        ) from exc
