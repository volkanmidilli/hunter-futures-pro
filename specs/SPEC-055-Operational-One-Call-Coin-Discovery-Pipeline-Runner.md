# SPEC-055-Operational-One-Call-Coin-Discovery-Pipeline-Runner

## Background

`PROJECT.md` envisions Hunter Futures Pro as an agent-first crypto futures research and execution-control platform. Hunter decides whether execution should be allowed; Freqtrade is only the execution layer. The core coin-discovery flow is:

`discovery → portfolio_construction → controlled_universe → export`

MVP-51 (`SPEC-052`) implemented the `controlled_universe` package. MVP-52 (`SPEC-053`) wired the controlled-universe step into the `run_orchestrator` and provided `build_coin_discovery_run_plan` and `build_research_run_result`. MVP-53 (`SPEC-054`) implemented the `controlled_universe_export_adapter` that converts a `ControlledUniverseReport` into deterministic research-only whitelist/blacklist artifacts.

However, no single public entry point exists that:

- accepts validated coin-discovery pipeline inputs,
- builds the research run plan,
- executes the run through the orchestrator,
- invokes the controlled-universe export adapter,
- writes a deterministic pipeline packet, and
- returns a structured result with artifacts, safety flags, and status.

A human operator must currently wire `build_coin_discovery_run_plan`, `build_research_run_result`, and `build_controlled_universe_export_from_run_result` together manually. This is error-prone and makes the product flow non-operational.

MVP-54 designs and implements an **Operational One-Call Coin-Discovery Pipeline Runner** that exposes a single public function and a small set of deterministic models, making the entire research-only coin-discovery flow callable in one operation while preserving all existing safety boundaries.

## Purpose

Provide one public research-only entry point that runs the entire coin-discovery pipeline end-to-end and produces a deterministic pipeline packet containing the orchestrated run result, the controlled-universe export, and explicit safety flags.

The runner is a pure, local, caller-triggered coordinator over existing engines. It does not start services, schedule jobs, read arbitrary files, connect to networks, exchanges, databases, or external services, and never emits trading or execution commands.

The runner is **not** a trading signal, not a strategy selector, not a position-sizing tool, not an execution approval system, and not a Freqtrade runtime integration. It is research-only infrastructure that records the pipeline execution and its outputs for human review and optional downstream configuration.

## Requirements

### Must Have

- Add a new package `hunter.coin_discovery_pipeline` with the following public interface:
  - `CoinDiscoveryPipelineConfig`
  - `CoinDiscoveryPipelineResult`
  - `CoinDiscoveryPipelineError`
  - `run_coin_discovery_pipeline(config)`
  - `coin_discovery_pipeline_result_to_dict(result)`
  - `coin_discovery_pipeline_result_to_json_text(result)`
  - `coin_discovery_pipeline_result_to_markdown_text(result)`
  - `write_coin_discovery_pipeline_result(result, config)`
  - `atomic_write_json_coin_discovery_pipeline_result(result, path)`
  - `atomic_write_markdown_coin_discovery_pipeline_result(result, path)`
- The runner accepts a `CoinDiscoveryPipelineConfig` that contains:
  - `run_id: str` — deterministic identity for the pipeline run.
  - `output_dir: str` — local opaque path for the pipeline packet.
  - `write_artifacts: bool = True` — whether to write local artifacts.
  - `fail_fast: bool = True` — passed to the orchestrator.
  - `export_enabled: bool = True` — whether to run the controlled-universe export adapter.
  - `export_config: ControlledUniverseExportConfig | None` — optional configuration for the export adapter. If omitted, the runner will resolve default export paths under the pipeline `output_dir` in Step 2.
  - `run_config: ResearchRunConfig | None` — optional orchestrator config.
  - `discovery_inputs: Sequence[DiscoveryInput]` — inputs for the discovery step.
  - `portfolio_construction_inputs: Sequence[PortfolioConstructionInput] | None` — optional inline inputs for the portfolio construction step.
  - `discovery_config: DiscoveryConfig | None` — optional config for the discovery step.
  - `portfolio_construction_config: PortfolioConstructionConfig | None` — optional config for the portfolio construction step.
  - `controlled_universe_config: ControlledUniverseConfig | None` — optional config for the controlled universe step.
  - `execution_context: ExecutionContext | None` — macro execution context for the controlled-universe step.
  - `metadata: Mapping[str, str]` — optional caller-provided metadata.
- The runner builds a `ResearchRunPlan` using the existing `build_coin_discovery_run_plan` helper from `run_orchestrator`.
- The runner executes the plan using the existing `build_research_run_result` from `run_orchestrator`.
- The runner extracts the `ControlledUniverseReport` from the `CONTROLLED_UNIVERSE` step result when available.
- The runner invokes the existing `build_controlled_universe_export_from_run_result` from `controlled_universe_export_adapter` when `export_enabled` is `True`.
- The runner writes the controlled-universe export artifacts using the existing `write_controlled_universe_export` when `export_enabled` and `write_artifacts` are `True`.
- The runner produces a `CoinDiscoveryPipelineResult` containing:
  - `run_id: str`
  - `state: PipelineState` (`COMPLETED`, `FAILED`, `BLOCKED`, `PARTIAL`)
  - `run_result: ResearchRunResult | None`
  - `export_result: ControlledUniverseExportResult | None`
  - `export_paths: tuple[str, ...]` — paths to the written export artifacts (JSON, Markdown).
  - `pipeline_paths: tuple[str, ...]` — paths to the written pipeline packet artifacts (JSON, Markdown).
  - `safety_flags: CoinDiscoveryPipelineSafetyFlags` with:
    - `research_only: bool = True`
    - `human_approval_required: bool = True`
    - `no_freqtrade_runtime_connection: bool = True`
    - `no_automatic_config_mutation: bool = True`
    - `no_network_connection: bool = True`
    - `no_exchange_connection: bool = True`
    - `no_database: bool = True`
    - `no_scheduler: bool = True`
    - `no_action_commands_emitted: bool = True`
  - `reason_codes: tuple[str, ...]` — sorted, deduplicated reason codes from the run, export, and pipeline.
  - `metadata: Mapping[str, str]` — deterministic metadata including project version.
- The runner is fail-closed:
  - If the config is invalid, return `BLOCKED` with `INVALID_PIPELINE_CONFIG`.
  - If the run plan is invalid, return `BLOCKED` and propagate the orchestrator validation reason codes.
  - If the run is `FAILED`, the pipeline is `FAILED` and export is `None`.
  - If the run is `BLOCKED`, the pipeline is `BLOCKED`. The export adapter may still run with a fail-closed result if `export_enabled` is `True`.
  - If the run is `PARTIAL`, the pipeline is `PARTIAL`. Export is run only if the `CONTROLLED_UNIVERSE` step succeeded and produced a report.
  - If `export_enabled` is `False`, export fields are `None` and export reason codes are omitted.
- The runner preserves the deterministic behavior of upstream components:
  - Identical inputs produce identical `run_result` and `export_result` (excluding timestamps, which are deterministic within the run).
  - Pair lists, summaries, and reason codes remain sorted.
- The runner uses atomic file writes via the existing writers.
- The runner does not modify the `run_orchestrator`, `controlled_universe_export_adapter`, `controlled_universe`, `portfolio_construction`, `discovery`, `execution`, `decision`, or `market_state` packages.
- The runner does not import or call Freqtrade runtime, strategy, or configuration code.
- The runner does not import or call exchange, API, network, database, scheduler, or live trading code.
- All file paths are opaque strings; the runner never reads, traverses, validates, or follows file references except through the existing writer modules.

### Should Have

- A convenience classmethod `CoinDiscoveryPipelineConfig.default()` for the default configuration.
- Default pipeline packet output paths:
  - JSON: `data/coin_discovery_pipeline/{run_id}/pipeline.json`
  - Markdown: `reports/coin_discovery_pipeline/{run_id}/pipeline.md`
- Default export artifact paths derived from the export config but placed under the pipeline output directory when the caller does not specify explicit paths.
- A deterministic `generated_at` timestamp carried from the run config to the pipeline result.
- Markdown pipeline packet includes a prominent safety notice and a summary of run state, export reason codes, and artifact paths.

### Could Have

- A convenience `run_coin_discovery_pipeline_from_config_dict(config_dict)` that constructs a `CoinDiscoveryPipelineConfig` from a plain dict for CLI/JSON integration.
- Optional CSV pipeline packet output.
- A CLI dry-run mode that prints the pipeline packet without writing files.
- Optional pipeline-run validation before execution (e.g., check required discovery inputs).

### Won't Have

- Live trading, order placement, or position sizing.
- Exchange API connection or real-time market data ingestion.
- Freqtrade runtime integration, strategy implementation, or automatic config mutation.
- Scheduler, daemon, web UI, dashboard, or REST API.
- Database persistence.
- Modification of existing package internals.
- Feedback from the pipeline result back into upstream engines.
- Production-readiness, trading-readiness, or suitability claims.
- Historical backtest validation of the selected universe (deferred to a future MVP).
- Deterministic downstream Freqtrade consumption adapter (deferred to a future MVP).

## Interface / Public API

```python
from hunter.coin_discovery_pipeline import (
    COIN_DISCOVERY_PIPELINE_VERSION,
    COIN_DISCOVERY_PIPELINE_REASON_CODES,
    INVALID_PIPELINE_CONFIG,
    PIPELINE_RESEARCH_ONLY,
    PIPELINE_HUMAN_APPROVAL_REQUIRED,
    NO_FREQTRADE_RUNTIME_CONNECTION,
    NO_AUTOMATIC_CONFIG_MUTATION,
    EXPORT_SKIPPED,
    PIPELINE_RUN_FAILED,
    PIPELINE_RUN_BLOCKED,
    PIPELINE_RUN_PARTIAL,
    CoinDiscoveryPipelineConfig,
    CoinDiscoveryPipelineResult,
    CoinDiscoveryPipelineError,
    PipelineState,
    CoinDiscoveryPipelineSafetyFlags,
    run_coin_discovery_pipeline,
    coin_discovery_pipeline_result_to_dict,
    coin_discovery_pipeline_result_to_json_text,
    coin_discovery_pipeline_result_to_markdown_text,
    write_coin_discovery_pipeline_result,
    atomic_write_json_coin_discovery_pipeline_result,
    atomic_write_markdown_coin_discovery_pipeline_result,
)
```

### Primary Pipeline Function

```python
def run_coin_discovery_pipeline(
    config: CoinDiscoveryPipelineConfig,
) -> CoinDiscoveryPipelineResult:
    """Execute a deterministic one-call coin-discovery pipeline run.

    The runner builds the research run plan, executes it through the existing
    orchestrator, optionally invokes the controlled-universe export adapter,
    writes deterministic pipeline artifacts, and returns a structured result.

    Args:
        config: Validated pipeline configuration.

    Returns:
        A `CoinDiscoveryPipelineResult` with the run result, export result,
        artifact paths, safety flags, and reason codes.

    Raises:
        CoinDiscoveryPipelineError: If an unexpected internal error occurs that
        cannot be represented as a deterministic pipeline result. Normal failures
        (blocked, failed, partial) are returned, not raised.
    """
```

### Configuration Model

```python
@dataclass(frozen=True)
class CoinDiscoveryPipelineConfig:
    run_id: str = ""
    output_dir: str = "data/coin_discovery_pipeline"
    write_artifacts: bool = True
    fail_fast: bool = True
    export_enabled: bool = True
    export_config: ControlledUniverseExportConfig | None = None
    run_config: ResearchRunConfig | None = None
    discovery_inputs: Sequence[DiscoveryInput] = field(default_factory=tuple)
    portfolio_construction_inputs: Sequence[PortfolioConstructionInput] | None = None
    discovery_config: DiscoveryConfig | None = None
    portfolio_construction_config: PortfolioConstructionConfig | None = None
    controlled_universe_config: ControlledUniverseConfig | None = None
    execution_context: ExecutionContext | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "CoinDiscoveryPipelineConfig": ...
```

### Result Model

```python
COIN_DISCOVERY_PIPELINE_VERSION: str = "0.54.0-dev"


class PipelineState(Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    PARTIAL = "PARTIAL"


@dataclass(frozen=True)
class CoinDiscoveryPipelineSafetyFlags:
    research_only: bool = True
    human_approval_required: bool = True
    no_freqtrade_runtime_connection: bool = True
    no_automatic_config_mutation: bool = True
    no_network_connection: bool = True
    no_exchange_connection: bool = True
    no_database: bool = True
    no_scheduler: bool = True
    no_action_commands_emitted: bool = True


@dataclass(frozen=True)
class CoinDiscoveryPipelineResult:
    run_id: str
    state: PipelineState
    run_result: ResearchRunResult | None
    export_result: ControlledUniverseExportResult | None
    export_paths: tuple[str, ...]
    pipeline_paths: tuple[str, ...]
    safety_flags: CoinDiscoveryPipelineSafetyFlags
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, str]
    version: str = COIN_DISCOVERY_PIPELINE_VERSION
```

### Reason Codes

```python
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
```

The set may also include reason codes propagated from `ResearchRunResult` and `ControlledUniverseExportResult`.

## Orchestration Sequence

```text
1. Validate CoinDiscoveryPipelineConfig.
   └─ Invalid? → return BLOCKED result with INVALID_PIPELINE_CONFIG.
2. Build ResearchRunPlan via build_coin_discovery_run_plan.
   ├─ discovery_inputs (+ discovery_config) → DISCOVERY step
   ├─ portfolio_construction_inputs (+ portfolio_construction_config) or inference from discovery → PORTFOLIO_CONSTRUCTION step
   └─ execution_context (+ controlled_universe_config) → CONTROLLED_UNIVERSE step
3. Execute plan via build_research_run_result.
   └─ Invalid plan? → return BLOCKED with orchestrator reason codes.
4. Determine pipeline state from ResearchRunState.
5. If export_enabled is True and a ControlledUniverseReport is available:
   ├─ Build ControlledUniverseExportResult via build_controlled_universe_export_from_run_result.
   └─ Write export artifacts via write_controlled_universe_export.
6. If export_enabled is True but no report is available:
   ├─ Build a fail-closed export result with MISSING_REPORT_INPUT or BLOCKED_EXPORT.
   └─ Write the fail-closed export artifacts.
7. If export_enabled is False:
   └─ export_result is None; export_paths is empty; add EXPORT_SKIPPED.
8. Build pipeline packet (run + export + paths + safety flags + reason codes).
9. If write_artifacts is True:
   ├─ Write pipeline JSON packet.
   └─ Write pipeline Markdown packet.
10. Return CoinDiscoveryPipelineResult.
```

## Deterministic Run Identity and Output Layout

- `run_id` is caller-provided. If empty, the runner generates a deterministic id from `run_{iso_timestamp}_{version}`. True reproducibility requires the caller to provide both `run_id` and `generated_at`.
- Output layout (when `write_artifacts` is True and the export config defaults are applied):
  ```
  data/coin_discovery_pipeline/{run_id}/
    pipeline.json
  reports/coin_discovery_pipeline/{run_id}/
    pipeline.md
  data/coin_discovery_pipeline/{run_id}/controlled_universe_export/
    latest_export.json
  reports/coin_discovery_pipeline/{run_id}/controlled_universe_export/
    latest_export.md
  ```
- The runner applies default export `output_dir` and `markdown_output_dir` to subdirectories under the pipeline `output_dir` only when the caller has not explicitly set them. The caller may override these paths to any local string; the runner treats them as opaque.
- The export artifact paths are recorded in `export_paths`.
- The pipeline packet paths are recorded in `pipeline_paths`.
- All paths are returned as strings; the runner does not inspect their contents after writing.

## Fail-Closed Behavior

| Input/Run Condition | Pipeline State | Export Result | Reason Codes |
|---|---|---|---|
| Invalid config | `BLOCKED` | `None` | `INVALID_PIPELINE_CONFIG`, safety codes |
| Invalid plan | `BLOCKED` | `None` | Orchestrator validation codes + safety codes |
| Run `FAILED` | `FAILED` | `None` | `PIPELINE_RUN_FAILED`, step reason codes |
| Run `BLOCKED` | `BLOCKED` | Fail-closed if `export_enabled` | `PIPELINE_RUN_BLOCKED`, `BLOCKED_EXPORT` |
| Run `PARTIAL` with no CU report | `PARTIAL` | `None` | `PIPELINE_RUN_PARTIAL`, `EXPORT_SKIPPED` |
| Run `PARTIAL` with CU report | `PARTIAL` | Export built from report | `PIPELINE_RUN_PARTIAL` |
| Run `COMPLETED` with no CU report | `BLOCKED` | Fail-closed | `MISSING_REPORT_INPUT` |
| Run `COMPLETED` with CU report | `COMPLETED` | Export built from report | Normal export codes |
| Export disabled | Follows run state | `None` | `EXPORT_SKIPPED` |

## Blocked / Partial / Failed Run Handling

- **Blocked:** The runner does not retry. The pipeline result state is `BLOCKED`. If export is enabled, the adapter still runs and produces a fail-closed export (empty whitelist, explicit reason codes) so the human reviewer sees a complete artifact set.
- **Failed:** The runner does not retry. The pipeline state is `FAILED`. Export is `None` because the orchestrator did not produce a consistent report.
- **Partial:** The pipeline state is `PARTIAL`. Export is run only if the `CONTROLLED_UNIVERSE` step succeeded; otherwise export is `None` with `EXPORT_SKIPPED`.

## Export Adapter Invocation Rules

- The runner invokes `build_controlled_universe_export_from_run_result(run_result, config.export_config)` only when `export_enabled` is `True`.
- The runner does not call `build_controlled_universe_export` directly; it always flows through the run-result path to preserve the upstream run context.
- The runner does not modify the export result after creation.
- The runner passes the export result to the existing writer; it does not reimplement serialization.

## Artifact and Writer Boundaries

- The runner writes two categories of artifacts:
  1. **Controlled-universe export artifacts** — produced by `controlled_universe_export_adapter` writer.
  2. **Pipeline packet artifacts** — produced by the new pipeline writer, containing the run result summary, export summary, paths, safety flags, and reason codes.
- The runner only writes files; it never reads files except through the existing writer modules that perform their own writes.
- The runner uses atomic writes (`tempfile` + `os.replace`) to avoid partial writes.
- All file paths are opaque strings. The runner never validates path existence, follows symlinks, or executes referenced files.

## Idempotency and Collision Behavior

- Identical `run_id` and identical inputs produce the same logical result (modulo wall-clock timestamps, which are configurable via `run_config.generated_at`).
- If a file already exists at the target path, the atomic writer overwrites it with the new deterministic content. This is intentional for reproducible local runs.
- The runner does not maintain a run database or lock files. Concurrent runs with the same `run_id` are the caller's responsibility; the runner itself is stateless and single-call.
- To avoid collisions, callers should supply unique `run_id` values (e.g., timestamps or content-derived hashes). The default `run_id` includes a timestamp if none is provided.

## Test Strategy

### Focused Tests (unit / model / engine)

- `CoinDiscoveryPipelineConfig` validation:
  - valid default config
  - invalid `run_id` (empty, non-string)
  - invalid `output_dir` (empty, non-string)
  - invalid `write_artifacts` / `fail_fast` / `export_enabled` (non-bool)
  - default classmethod returns expected defaults
- `CoinDiscoveryPipelineResult` validation:
  - valid completed result
  - valid blocked/failed/partial results
  - lists and reason codes coerced to tuples
  - safety flags defaults
- `PipelineState` enum coverage.
- Orchestration sequence tests using in-memory discovery inputs and controlled-universe inputs:
  - completed run produces a completed pipeline result
  - blocked run produces a blocked result with fail-closed export
  - failed run produces a failed result with no export
  - partial run with CU report runs export; partial without CU report skips export
  - export disabled → `export_result` is `None` and `EXPORT_SKIPPED` is present
- Determinism tests:
  - same inputs → same run result and export result
  - same run_id → same output paths
- Fail-closed tests:
  - invalid config returns blocked result, not an exception
  - missing CU report in completed run returns fail-closed export
- Reason-code aggregation tests:
  - run reason codes + export reason codes + pipeline reason codes are deduplicated and sorted.

### Writer Tests

- `coin_discovery_pipeline_result_to_dict` returns JSON-safe deterministic dict.
- `coin_discovery_pipeline_result_to_json_text` returns valid JSON with sorted keys.
- `coin_discovery_pipeline_result_to_markdown_text` contains the safety notice, run state, export reason codes, and artifact paths.
- `write_coin_discovery_pipeline_result` writes JSON and Markdown files when `write_artifacts` is `True`.
- `write_coin_discovery_pipeline_result` writes nothing when `write_artifacts` is `False`.
- Atomic writers use temp-file + rename and do not leave partial files.
- Empty/None export result is handled gracefully in dict/Markdown output.

### End-to-End Integration Tests

- From raw `DiscoveryInput` and `ExecutionContext` to written pipeline packet and export artifacts.
- The JSON pipeline packet can be parsed and contains the expected keys.
- The Markdown pipeline packet contains a safety notice and the artifact paths.
- The exported whitelist/blacklist in the pipeline packet matches the controlled-universe export output.
- No file reads occur outside the writer modules (verified by no `open()` or `Path.read_text()` in the pipeline package).

## Implementation Steps and Milestones

### Step 1 — Models and Config

- Create `src/hunter/coin_discovery_pipeline/models.py`.
  - Define `COIN_DISCOVERY_PIPELINE_VERSION`.
  - Define reason codes and `COIN_DISCOVERY_PIPELINE_REASON_CODES` frozenset.
  - Define `PipelineState` enum.
  - Define `CoinDiscoveryPipelineSafetyFlags` frozen dataclass.
  - Define `CoinDiscoveryPipelineConfig` frozen dataclass with validation.
  - Define `CoinDiscoveryPipelineResult` frozen dataclass with validation.
  - Define `CoinDiscoveryPipelineError` exception.

### Step 2 — Engine

- Create `src/hunter/coin_discovery_pipeline/engine.py`.
  - Implement `run_coin_discovery_pipeline(config)`.
  - Implement helper `_build_pipeline_plan` using `build_coin_discovery_run_plan`.
  - Implement helper `_execute_pipeline_run` using `build_research_run_result`.
  - Implement helper `_build_export_from_run_result` using `build_controlled_universe_export_from_run_result`.
  - Implement helper `_write_export_artifacts` using `write_controlled_universe_export`.
  - Implement helper `_build_pipeline_result` to aggregate run/export/paths/safety flags/reason codes.
  - Implement fail-closed mappings for blocked/failed/partial states.

### Step 3 — Writer

- Create `src/hunter/coin_discovery_pipeline/writer.py`.
  - Implement `coin_discovery_pipeline_result_to_dict`.
  - Implement `coin_discovery_pipeline_result_to_json_text`.
  - Implement `coin_discovery_pipeline_result_to_markdown_text`.
  - Implement `atomic_write_json_coin_discovery_pipeline_result`.
  - Implement `atomic_write_markdown_coin_discovery_pipeline_result`.
  - Implement `write_coin_discovery_pipeline_result`.
  - Include a safety notice in Markdown output.

### Step 4 — Public API and Tests

- Create `src/hunter/coin_discovery_pipeline/__init__.py` with public exports.
- Create `tests/test_coin_discovery_pipeline/test_models.py`.
- Create `tests/test_coin_discovery_pipeline/test_engine.py`.
- Create `tests/test_coin_discovery_pipeline/test_writer.py`.
- Create `tests/test_coin_discovery_pipeline/test_integration.py`.
- Run focused tests and full suite.

### Step 5 — Finalization

- Bump `COIN_DISCOVERY_PIPELINE_VERSION` to `0.54.0-dev`.
- Bump `pyproject.toml` and `src/hunter/__init__.py` to `0.54.0-dev`.
- Update `CHANGELOG.md`, `docs/handoff/CURRENT_STATE.md`, `docs/MVP_INDEX.md`, `AGENTS.md`, `tasks/active.md`, and `tasks/agent-log.md`.
- Apply local tag `v0.54.0-dev` (no push).

## Non-Goals (Explicit)

- This MVP does not validate the selected universe with historical backtests.
- This MVP does not produce a Freqtrade-ready config or strategy contract.
- This MVP does not modify the behavior of existing engines; it only coordinates them.
- This MVP does not introduce a scheduler, daemon, server, REST API, or database.
- This MVP does not claim production readiness, trading readiness, or suitability for any execution purpose.
- This MVP does not read from `data/` or `reports/` except through the existing writer modules during file writes.

## Safety and Boundaries

- **No Freqtrade runtime integration:** The runner does not import or call Freqtrade runtime, strategy, or configuration code.
- **No automatic config mutation:** The runner writes local artifacts; it does not modify Freqtrade config files, strategy files, or any existing project config.
- **No exchange or network access:** The runner does not call networks, APIs, exchanges, or external services.
- **No API, server, database, scheduler, or live trading behavior:** The runner is a single-call local function. No background services, servers, daemons, schedulers, or trading execution are started or invoked.
- **No actionable trading signals:** The output is a research-only pipeline packet with explicit safety flags. It is not an order, signal, or execution instruction.
- **No readiness/approval/suitability claims:** All outputs are labeled as research-only and requiring human approval.
- **No data/ or reports/ inspection:** The runner never reads, traverses, or validates the contents of `data/` or `reports/`. It only writes artifacts through deterministic writer functions.
- **No implementation yet:** This SPEC is for planning only. Implementation begins after human approval.
- **No staging, commit, tag, push, or remote configuration:** This SPEC does not trigger any source-control or deployment operations.

## Version

Target: `0.54.0-dev`

`COIN_DISCOVERY_PIPELINE_VERSION`: `0.54.0-dev`
