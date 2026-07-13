"""Frozen models for the one-call coin-discovery pipeline runner (MVP-54).

The runner is a pure, local, caller-triggered coordinator over the existing
discovery, portfolio-construction, controlled-universe, run-orchestrator, and
controlled-universe-export-adapter engines. It does not start services, schedule
jobs, read arbitrary files, connect to networks, exchanges, databases, or external
services, and never emits trading or execution commands.

All outputs are research-only and require human approval before any downstream use.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hunter.controlled_universe.models import ControlledUniverseConfig
    from hunter.controlled_universe_export_adapter.models import (
        ControlledUniverseExportConfig,
        ControlledUniverseExportResult,
    )
    from hunter.discovery.models import DiscoveryConfig, DiscoveryInput
    from hunter.execution.models import ExecutionContext
    from hunter.portfolio_construction.models import (
        PortfolioConstructionConfig,
        PortfolioConstructionInput,
    )
    from hunter.run_orchestrator.models import ResearchRunResult

COIN_DISCOVERY_PIPELINE_VERSION: str = "0.54.0-dev"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PipelineState(Enum):
    """Terminal state of a coin-discovery pipeline run."""

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    PARTIAL = "PARTIAL"


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------


INVALID_PIPELINE_CONFIG = "INVALID_PIPELINE_CONFIG"
PIPELINE_RESEARCH_ONLY = "PIPELINE_RESEARCH_ONLY"
PIPELINE_HUMAN_APPROVAL_REQUIRED = "PIPELINE_HUMAN_APPROVAL_REQUIRED"
NO_FREQTRADE_RUNTIME_CONNECTION = "NO_FREQTRADE_RUNTIME_CONNECTION"
NO_AUTOMATIC_CONFIG_MUTATION = "NO_AUTOMATIC_CONFIG_MUTATION"
EXPORT_SKIPPED = "EXPORT_SKIPPED"
PIPELINE_RUN_FAILED = "PIPELINE_RUN_FAILED"
PIPELINE_RUN_BLOCKED = "PIPELINE_RUN_BLOCKED"
PIPELINE_RUN_PARTIAL = "PIPELINE_RUN_PARTIAL"

COIN_DISCOVERY_PIPELINE_REASON_CODES: frozenset[str] = frozenset({
    INVALID_PIPELINE_CONFIG,
    PIPELINE_RESEARCH_ONLY,
    PIPELINE_HUMAN_APPROVAL_REQUIRED,
    NO_FREQTRADE_RUNTIME_CONNECTION,
    NO_AUTOMATIC_CONFIG_MUTATION,
    EXPORT_SKIPPED,
    PIPELINE_RUN_FAILED,
    PIPELINE_RUN_BLOCKED,
    PIPELINE_RUN_PARTIAL,
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coerce_tuple_strs(values: Sequence[str] | None) -> tuple[str, ...]:
    """Return a deduplicated tuple of strings."""
    if values is None:
        return ()
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        s = str(item)
        if s not in seen:
            seen.add(s)
            result.append(s)
    return tuple(result)


def _coerce_mapping_strs(
    mapping: Mapping[str, str] | None,
) -> Mapping[str, str]:
    """Return an immutable copy of a string mapping."""
    if mapping is None:
        return MappingProxyType({})
    return MappingProxyType({str(k): str(v) for k, v in mapping.items()})


def _utc_now() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoinDiscoveryPipelineSafetyFlags:
    """Safety invariants for the coin-discovery pipeline runner."""

    research_only: bool = True
    human_approval_required: bool = True
    no_freqtrade_runtime_connection: bool = True
    no_automatic_config_mutation: bool = True
    no_network_connection: bool = True
    no_exchange_connection: bool = True
    no_database: bool = True
    no_scheduler: bool = True
    no_action_commands_emitted: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("research_only", self.research_only),
            ("human_approval_required", self.human_approval_required),
            ("no_freqtrade_runtime_connection", self.no_freqtrade_runtime_connection),
            ("no_automatic_config_mutation", self.no_automatic_config_mutation),
            ("no_network_connection", self.no_network_connection),
            ("no_exchange_connection", self.no_exchange_connection),
            ("no_database", self.no_database),
            ("no_scheduler", self.no_scheduler),
            ("no_action_commands_emitted", self.no_action_commands_emitted),
        ):
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a bool, got {value!r}")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoinDiscoveryPipelineConfig:
    """Configuration for a one-call coin-discovery pipeline run.

    The runner treats all paths as opaque local strings. It does not open,
    traverse, or validate the contents of directories beyond writing artifacts
    through deterministic writer functions.
    """

    run_id: str = ""
    output_dir: str = "data/coin_discovery_pipeline"
    write_artifacts: bool = True
    fail_fast: bool = True
    export_enabled: bool = True
    export_config: "ControlledUniverseExportConfig | None" = None
    run_config: "ResearchRunConfig | None" = None
    discovery_inputs: Sequence["DiscoveryInput"] = field(default_factory=tuple)
    portfolio_construction_inputs: Sequence["PortfolioConstructionInput"] | None = None
    discovery_config: "DiscoveryConfig | None" = None
    portfolio_construction_config: "PortfolioConstructionConfig | None" = None
    controlled_universe_config: "ControlledUniverseConfig | None" = None
    execution_context: "ExecutionContext | None" = None
    metadata: Mapping[str, str] = field(default_factory=dict)
    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str):
            raise ValueError(f"run_id must be a string, got {self.run_id!r}")
        if not isinstance(self.output_dir, str) or not self.output_dir.strip():
            raise ValueError(f"output_dir must be a non-empty string, got {self.output_dir!r}")
        if not isinstance(self.write_artifacts, bool):
            raise ValueError(f"write_artifacts must be a bool, got {self.write_artifacts!r}")
        if not isinstance(self.fail_fast, bool):
            raise ValueError(f"fail_fast must be a bool, got {self.fail_fast!r}")
        if not isinstance(self.export_enabled, bool):
            raise ValueError(f"export_enabled must be a bool, got {self.export_enabled!r}")
        if self.export_config is not None:
            from hunter.controlled_universe_export_adapter.models import (
                ControlledUniverseExportConfig,
            )

            if not isinstance(self.export_config, ControlledUniverseExportConfig):
                raise ValueError(
                    "export_config must be a ControlledUniverseExportConfig or None, "
                    f"got {self.export_config!r}"
                )
        if not isinstance(self.discovery_inputs, Sequence):
            raise ValueError(f"discovery_inputs must be a sequence, got {self.discovery_inputs!r}")
        if len(self.discovery_inputs) == 0:
            raise ValueError("discovery_inputs must contain at least one DiscoveryInput")
        for idx, item in enumerate(self.discovery_inputs):
            # DiscoveryInput is imported at the bottom of the module to avoid
            # circular import problems while still allowing runtime validation.
            from hunter.discovery.models import DiscoveryInput

            if not isinstance(item, DiscoveryInput):
                raise ValueError(
                    f"discovery_inputs[{idx}] must be a DiscoveryInput, got {item!r}"
                )
        if self.portfolio_construction_inputs is not None:
            if not isinstance(self.portfolio_construction_inputs, Sequence):
                raise ValueError(
                    f"portfolio_construction_inputs must be a sequence or None, "
                    f"got {self.portfolio_construction_inputs!r}"
                )
            from hunter.portfolio_construction.models import PortfolioConstructionInput

            for idx, item in enumerate(self.portfolio_construction_inputs):
                if not isinstance(item, PortfolioConstructionInput):
                    raise ValueError(
                        f"portfolio_construction_inputs[{idx}] must be a "
                        f"PortfolioConstructionInput, got {item!r}"
                    )
        if self.run_config is not None:
            from hunter.run_orchestrator.models import ResearchRunConfig

            if not isinstance(self.run_config, ResearchRunConfig):
                raise ValueError(
                    f"run_config must be a ResearchRunConfig or None, got {self.run_config!r}"
                )
        if self.discovery_config is not None:
            from hunter.discovery.models import DiscoveryConfig

            if not isinstance(self.discovery_config, DiscoveryConfig):
                raise ValueError(
                    f"discovery_config must be a DiscoveryConfig or None, got {self.discovery_config!r}"
                )
        if self.portfolio_construction_config is not None:
            from hunter.portfolio_construction.models import PortfolioConstructionConfig

            if not isinstance(self.portfolio_construction_config, PortfolioConstructionConfig):
                raise ValueError(
                    "portfolio_construction_config must be a PortfolioConstructionConfig or None, "
                    f"got {self.portfolio_construction_config!r}"
                )
        if self.controlled_universe_config is not None:
            from hunter.controlled_universe.models import ControlledUniverseConfig

            if not isinstance(self.controlled_universe_config, ControlledUniverseConfig):
                raise ValueError(
                    "controlled_universe_config must be a ControlledUniverseConfig or None, "
                    f"got {self.controlled_universe_config!r}"
                )
        if self.execution_context is not None:
            from hunter.execution.models import ExecutionContext

            if not isinstance(self.execution_context, ExecutionContext):
                raise ValueError(
                    f"execution_context must be an ExecutionContext or None, got {self.execution_context!r}"
                )
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if self.generated_at is not None and not isinstance(self.generated_at, datetime):
            raise ValueError(f"generated_at must be a datetime or None, got {self.generated_at!r}")
        if self.generated_at is not None and self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware when provided")

    @classmethod
    def default(
        cls,
        *,
        discovery_inputs: Sequence["DiscoveryInput"],
        execution_context: "ExecutionContext",
        run_id: str | None = None,
        output_dir: str | None = None,
    ) -> "CoinDiscoveryPipelineConfig":
        """Return a default config for the required inputs.

        If run_id is omitted, a deterministic id is generated from the current
        UTC timestamp and the pipeline version. True reproducibility requires the
        caller to supply both run_id and generated_at.
        """
        final_run_id = run_id or f"run-{_utc_now().isoformat()}-{COIN_DISCOVERY_PIPELINE_VERSION}"
        final_output_dir = output_dir or "data/coin_discovery_pipeline"
        return cls(
            run_id=final_run_id,
            output_dir=final_output_dir,
            discovery_inputs=discovery_inputs,
            execution_context=execution_context,
        )


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoinDiscoveryPipelineResult:
    """Deterministic result of a one-call coin-discovery pipeline run.

    Contains the orchestrated run result, the optional controlled-universe export
    result, artifact paths, explicit safety flags, and aggregated reason codes.
    """

    run_id: str
    state: PipelineState
    run_result: "ResearchRunResult | None"
    export_result: "ControlledUniverseExportResult | None"
    export_paths: tuple[str, ...]
    pipeline_paths: tuple[str, ...]
    safety_flags: CoinDiscoveryPipelineSafetyFlags
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, str]
    version: str = COIN_DISCOVERY_PIPELINE_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError(f"run_id must be a non-empty string, got {self.run_id!r}")
        if not isinstance(self.state, PipelineState):
            raise ValueError(f"state must be a PipelineState, got {self.state!r}")
        if self.run_result is not None:
            from hunter.run_orchestrator.models import ResearchRunResult

            if not isinstance(self.run_result, ResearchRunResult):
                raise ValueError(
                    f"run_result must be a ResearchRunResult or None, got {self.run_result!r}"
                )
        if self.export_result is not None:
            from hunter.controlled_universe_export_adapter.models import (
                ControlledUniverseExportResult,
            )

            if not isinstance(self.export_result, ControlledUniverseExportResult):
                raise ValueError(
                    f"export_result must be a ControlledUniverseExportResult or None, "
                    f"got {self.export_result!r}"
                )
        object.__setattr__(self, "export_paths", _coerce_tuple_strs(self.export_paths))
        object.__setattr__(self, "pipeline_paths", _coerce_tuple_strs(self.pipeline_paths))
        if not isinstance(self.safety_flags, CoinDiscoveryPipelineSafetyFlags):
            raise ValueError(
                f"safety_flags must be a CoinDiscoveryPipelineSafetyFlags, got {self.safety_flags!r}"
            )
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        for code in self.reason_codes:
            if not isinstance(code, str) or not code.strip():
                raise ValueError(f"reason_codes must contain non-empty strings, got {code!r}")
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.version, str):
            raise ValueError(f"version must be a string, got {self.version!r}")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CoinDiscoveryPipelineError(Exception):
    """Base exception for the coin-discovery pipeline runner.

    Raised only for unexpected internal failures that cannot be represented as
    a deterministic CoinDiscoveryPipelineResult. Normal operational failures
    (blocked, failed, partial) are returned, not raised.
    """
