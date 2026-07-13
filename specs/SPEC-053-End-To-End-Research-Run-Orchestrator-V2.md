# SPEC-053-End-To-End-Research-Run-Orchestrator-V2

## Background

`PROJECT.md` envisions Hunter Futures Pro as an agent-first crypto futures research and execution-control platform. The decision layer is split into two pipelines:

- **Macro pipeline:** `market_state` → `decision` → `execution` → `freqtrade_bridge`.
- **Coin-selection pipeline:** `relative_strength` + `open_interest` → `discovery` → `portfolio_construction`.

MVP-51 (`SPEC-052`) closed the bridge between these pipelines with the `controlled_universe` package, which consumes `ExecutionContext` (macro) and `PortfolioConstructionReport` (per-coin) to produce a deterministic `ControlledUniverseReport`.

However, the existing `run_orchestrator` (MVP-30) does not include a step kind for `controlled_universe`. A caller can run `discovery`, `portfolio_construction`, and `backtest` steps, but must manually wire `PortfolioConstructionReport` and `ExecutionContext` into `build_controlled_universe_report` outside the orchestrator. This leaves the end-to-end coin discovery pipeline un-orchestrated.

MVP-52 designs and implements **End-to-End Research Run Orchestrator v2** to close that gap by extending the existing orchestrator with a deterministic `CONTROLLED_UNIVERSE` step and explicit dependency rules, without replacing established contracts.

## Purpose

The End-to-End Research Run Orchestrator v2 coordinates a deterministic, caller-provided research run plan that can execute the full coin-discovery pipeline:

`discovery` → `portfolio_construction` → `controlled_universe`

using the macro `execution_context` as a safety gate.

The orchestrator remains a pure, local, caller-triggered coordinator. It does not start services, schedule jobs, read arbitrary files, connect to networks, exchanges, databases, or external services, and never emits trading or execution commands.

The orchestrator is **not** a trading signal, not a strategy selector, not a position-sizing tool, and not an execution approval system. It is a research-only audit artifact that records which steps ran, in what order, with what results, and why.

## Requirements

### Must Have

- Extend the existing `run_orchestrator` package without replacing established contracts.
- Add a new `ResearchRunStepKind.CONTROLLED_UNIVERSE` value.
- Add a new `ResearchRunStepResult` state path for controlled universe steps.
- Add a `ControlledUniverseRunInput` helper model used by `build_coin_discovery_run_plan` to bundle:
  - `execution_context: ExecutionContext | None`
  - `portfolio_report: PortfolioConstructionReport | None`
  - `config: ControlledUniverseConfig | None`
  - optional upstream references.
- Allow the controlled universe step to receive inputs via `step.inputs` keys:
  - `"portfolio_report"`: in-line `PortfolioConstructionReport`.
  - `"execution_context"`: in-line `ExecutionContext`.
  - `"config"`: in-line `ControlledUniverseConfig` (optional; default used if absent).
  - `"portfolio_construction_step_id"`: reference to a prior `PORTFOLIO_CONSTRUCTION` step by `step_id`.
  - `"portfolio_construction_step_index"`: reference to a prior `PORTFOLIO_CONSTRUCTION` step by index.
  - `"execution_context_step_id"`: reference to a prior step that emitted an `ExecutionContext`.
- The orchestrator resolves `PortfolioConstructionReport` in this priority order:
  1. In-line `"portfolio_report"`.
  2. `"portfolio_construction_step_id"`.
  3. `"portfolio_construction_step_index"`.
  4. Most recent preceding successful `PORTFOLIO_CONSTRUCTION` step.
- The orchestrator resolves `ExecutionContext` in this priority order:
  1. In-line `"execution_context"`.
  2. `"execution_context_step_id"`.
  3. If neither is present, the controlled universe engine receives `None` and fails closed internally.
- Define exact step dependency rules:
  - A `CONTROLLED_UNIVERSE` step requires a `PortfolioConstructionReport`.
  - The `PortfolioConstructionReport` must come from either an in-line input or a successfully completed `PORTFOLIO_CONSTRUCTION` step earlier in the plan.
  - The `ExecutionContext` must come from either an in-line input or a successfully completed step that emitted an `ExecutionContext` (e.g., a future macro-pipeline step, or provided in-line by the caller).
- Define exact step order for the canonical coin-discovery pipeline:
  1. `DISCOVERY` (produces `DiscoveryReport`, optional if portfolio report is supplied directly)
  2. `PORTFOLIO_CONSTRUCTION` (produces `PortfolioConstructionReport`)
  3. `CONTROLLED_UNIVERSE` (produces `ControlledUniverseReport`)
- The orchestrator may run only a subset of these steps if the caller provides the required in-line inputs; it must not require the full pipeline.
- Fail closed when required inputs are missing:
  - Missing `PortfolioConstructionReport` → step state `BLOCKED`, reason `MISSING_PORTFOLIO_CONTEXT`.
  - Missing `ExecutionContext` → step state `BLOCKED`, reason `MISSING_EXECUTION_CONTEXT`.
- Fail closed when upstream inputs are stale:
  - If the resolved `PortfolioConstructionReport` or `ExecutionContext` carries a stale flag, the controlled universe step is `BLOCKED` with reason `STALE_INPUT`.
  - If freshness metadata is missing, treat as stale and block.
- Fail closed on contradictory inputs:
  - `ExecutionContext` execution state `BLOCKED`/`UNKNOWN` while portfolio items are `INCLUDED` → controlled universe step is `BLOCKED` with reason `EXECUTION_BLOCKED`.
  - `AllowedMode.NONE` with non-empty portfolio → controlled universe step is `BLOCKED` with reason `MACRO_MODE_NONE`.
  - Portfolio summary inconsistent with item counts → `BLOCKED` with reason `INVALID_PORTFOLIO_SUMMARY`.
- Define partial-run behavior:
  - If `fail_fast=True` (config default), any step with state `BLOCKED` or `FAILED` causes the run to terminate immediately with `ResearchRunState.PARTIAL` or `ResearchRunState.BLOCKED`.
  - If `fail_fast=False`, subsequent steps may still attempt to run using in-line inputs or resolved upstream data, but steps that depend on a failed/blocked upstream step are themselves `BLOCKED` or `SKIPPED`.
- Define downstream-step failure behavior:
  - A controlled universe step that depends on a failed/blocked `PORTFOLIO_CONSTRUCTION` step is `BLOCKED` with reason `UPSTREAM_STEP_FAILED` or `UPSTREAM_STEP_BLOCKED`.
- Deterministic run identity:
  - `run_id` is caller-provided and must be non-empty.
  - Run identity is the tuple `(run_id, generated_at, tuple(step.step_id for step in plan.steps))`.
  - Identical plans and configs produce identical `ResearchRunResult` ordering for identical engine inputs.
- Deterministic result ordering:
  - Step results are returned in the exact order of `plan.steps`.
  - Artifacts are returned in step-index order.
  - Reason codes in the run-level result are sorted lexicographically.
- Update `ResearchRunDataQuality` to include controlled-universe-specific counts:
  - `controlled_universe_steps: int`
  - `controlled_universe_blocked: int`
  - `controlled_universe_failed: int`
- Update `ResearchRunSafetyFlags` to inherit and surface safety flags from the controlled universe step result.
- Update `ResearchRunArtifact` kind vocabulary to include `"controlled_universe_json"`, `"controlled_universe_csv"`, `"controlled_universe_markdown"`.
- Update the writer to serialize the new step kind and run-level fields deterministically.
- No file reads inside the orchestrator engine; writers only serialize in-memory results.
- No network, exchange, database, server, scheduler, daemon, or Freqtrade runtime interaction.
- No actionable trading signals, order suggestions, or readiness claims.
- Safety notice repeated in all orchestrator outputs: research-only, not trading advice, not execution approval.

### Should Have

- A convenience plan builder `build_coin_discovery_run_plan` that returns a valid `ResearchRunPlan` for the canonical pipeline (discovery → portfolio construction → controlled universe) with deterministic step IDs.
- A validation helper `validate_run_plan_dependencies` that checks whether every controlled universe step can resolve its required inputs before the run starts.
- Reason-code partitions for controlled universe failures in the run-level data quality summary.
- Optional `execution_context_step_id` field in controlled universe step inputs to reference a macro-pipeline step by ID.

### Could Have

- Pre-run static dependency graph visualization (text only, no UI).
- Optional dry-run mode that reports which steps would run without invoking engines.
- Support for multiple controlled universe steps in a single run (e.g., different configs).

### Won't Have

- Live trading, order placement, or position sizing.
- Exchange API connection or real-time market data ingestion.
- Freqtrade runtime integration or strategy implementation.
- Scheduler, daemon, web UI, dashboard, or REST API.
- Database persistence.
- Modification of `controlled_universe`, `portfolio_construction`, `discovery`, `execution`, or `decision` package internals.
- Feedback from orchestrator output back into upstream engines.

## Inputs

1. `ResearchRunPlan` (existing in `hunter.run_orchestrator.models`).
2. `ResearchRunConfig` (existing in `hunter.run_orchestrator.models`).
3. `ControlledUniverseRunInput` (new in this spec):
   - `execution_context: ExecutionContext | None`
   - `portfolio_report: PortfolioConstructionReport | None`
   - `config: ControlledUniverseConfig | None`
4. Optional upstream step references:
   - `portfolio_construction_step_id: str | None`
   - `portfolio_construction_step_index: int | None`
   - `execution_context_step_id: str | None`

## Outputs

1. `ResearchRunResult` (extended with controlled universe support).
2. `ResearchRunStepResult` for `CONTROLLED_UNIVERSE` steps.
3. `ResearchRunArtifact` for controlled universe JSON/CSV/Markdown files.
4. Updated `ResearchRunDataQuality` and `ResearchRunSafetyFlags`.
5. Writer outputs: JSON string, CSV string, Markdown string, atomic file writes.

## Interface / Public API

```python
from hunter.run_orchestrator import (
    ResearchRunStepKind,
    ResearchRunStep,
    ResearchRunPlan,
    ResearchRunConfig,
    ResearchRunResult,
    ResearchRunStepResult,
    ResearchRunArtifact,
    build_research_run_result,
    build_coin_discovery_run_plan,
    validate_run_plan_dependencies,
    research_run_result_to_dict,
    research_run_result_to_json_text,
    research_run_result_to_csv_text,
    research_run_result_to_markdown_text,
    write_research_run_result,
    atomic_write_json_research_run_result,
    atomic_write_csv_research_run_result,
    atomic_write_markdown_research_run_result,
)
```

Primary orchestrator function (existing, unchanged signature):

```python
def build_research_run_result(
    plan: ResearchRunPlan,
    config: ResearchRunConfig | None = None,
) -> ResearchRunResult:
    ...
```

New convenience and validation functions:

```python
def build_coin_discovery_run_plan(
    run_id: str,
    discovery_inputs: Sequence[DiscoveryInput] | None = None,
    portfolio_construction_inputs: Sequence[PortfolioConstructionInput] | None = None,
    execution_context: ExecutionContext | None = None,
    controlled_universe_config: ControlledUniverseConfig | None = None,
    metadata: Mapping[str, str] | None = None,
) -> ResearchRunPlan:
    ...

def validate_run_plan_dependencies(
    plan: ResearchRunPlan,
) -> tuple[bool, Sequence[str]]:
    """Return (is_valid, reason_codes)."""
    ...
```

All new functions are exported from `hunter.run_orchestrator.__init__.py`.

## Data Model

### Enum Addition

```python
class ResearchRunStepKind(Enum):
    REPORTING_CLI_SAMPLE = "reporting_cli_sample"
    BACKTEST = "backtest"
    PORTFOLIO_CONSTRUCTION = "portfolio_construction"
    DISCOVERY = "discovery"
    AUDIT_SNAPSHOT_SUMMARY = "audit_snapshot_summary"
    AUDIT_CATALOG_SUMMARY = "audit_catalog_summary"
    AUDIT_CLOSURE_SUMMARY = "audit_closure_summary"
    CONTROLLED_UNIVERSE = "controlled_universe"  # NEW
```

### New Reason Codes

- `MISSING_PORTFOLIO_CONTEXT`
- `MISSING_EXECUTION_CONTEXT`
- `STALE_INPUT`
- `UPSTREAM_STEP_FAILED`
- `UPSTREAM_STEP_BLOCKED`
- `INVALID_PORTFOLIO_SUMMARY`
- `EXECUTION_BLOCKED`
- `MACRO_MODE_NONE`
- `CONTRADICTORY_INPUT`
- `INVALID_CONTROLLED_UNIVERSE_INPUT`

These are added to `RUN_ORCHESTRATOR_BLOCKING_REASON_CODES` and `RUN_ORCHESTRATOR_REASON_CODES`.

### New Input Model

```python
@dataclass(frozen=True, slots=True)
class ControlledUniverseRunInput:
    execution_context: ExecutionContext | None = None
    portfolio_report: PortfolioConstructionReport | None = None
    config: ControlledUniverseConfig | None = None
    portfolio_construction_step_id: str | None = None
    portfolio_construction_step_index: int | None = None
    execution_context_step_id: str | None = None

    def __post_init__(self) -> None:
        # Validation is performed at orchestrator dispatch time, not here.
        ...
```

### Extended Result Models

`ResearchRunDataQuality` receives:

```python
controlled_universe_steps: int = 0
controlled_universe_blocked: int = 0
controlled_universe_failed: int = 0
```

`ResearchRunSafetyFlags` is updated by the controlled universe step to reflect:

```python
no_universe_approval: bool = True
```

(already covered by `no_universe_approval` in existing model; verify and extend if needed)

### Artifact Kind

`ResearchRunArtifact.kind` may be `"controlled_universe_json"`, `"controlled_universe_csv"`, or `"controlled_universe_markdown"`.

## Safety

- Fail-closed: missing required inputs block the controlled universe step.
- Fail-closed: stale, contradictory, or invalid upstream data blocks the controlled universe step.
- All orchestrator functions remain pure and deterministic.
- No file reads, no network, no shell, no database, no Freqtrade import, no exchange import.
- No action commands, no order instructions, no position sizes, no leverage, no shorting approval.
- Research-only output; not a trading signal, not execution approval, not a strategy selector.
- All file writes are optional and atomic; engine functions are path-agnostic.
- Paths are opaque strings; never traversed, validated, or opened by the orchestrator.
- The orchestrator never modifies upstream engine packages or their outputs.

## Out of Scope

- Implementing a Freqtrade strategy.
- Modifying the `controlled_universe`, `portfolio_construction`, `discovery`, `execution`, `decision`, or `market_state` packages.
- Adding a scheduler or daemon.
- Adding Web UI or dashboard.
- Adding database persistence.
- Adding real-time market data ingestion.
- Adding order placement, position sizing, or leverage logic.
- Adding live trading or shorting approval.
- Changing the safety policy of existing engines.
- Replacing the existing `run_orchestrator` models or engine; only additive extensions.

## Default Writer Paths

Writers must use atomic replacement and must remain free of file I/O in the engine functions. Default paths are opaque strings:

- JSON: `data/run_orchestrator/latest_run.json`
- CSV: `data/run_orchestrator/latest_run_steps.csv`
- Markdown: `reports/run_orchestrator/latest_run.md`

(Existing defaults may be preserved; new controlled-universe artifacts are written by the `controlled_universe` writer invoked by the orchestrator step, not by the orchestrator's own writer.)

## Orchestration Rules

### Step Dependency Graph

```
DISCOVERY ──┐
            ▼
PORTFOLIO_CONSTRUCTION ──┐
                           ▼
                  CONTROLLED_UNIVERSE
                           ▲
ExecutionContext (provided in-line or resolved from macro step)
```

### Input Resolution Order

For a `CONTROLLED_UNIVERSE` step, the orchestrator resolves `PortfolioConstructionReport` in this order:

1. **In-line object:** use `step.inputs["portfolio_report"]` if present and not `None`.
2. **Step reference by ID:** if `step.inputs["portfolio_construction_step_id"]` is present, find the step with that ID and use its `data["report"]` if state is `SUCCESS`.
3. **Step reference by index:** if `step.inputs["portfolio_construction_step_index"]` is present, use the step at that index under the same conditions.
4. **Default upstream:** if none of the above, look for the most recent preceding `PORTFOLIO_CONSTRUCTION` step with state `SUCCESS`.
5. If none resolve, the step is `BLOCKED` with `MISSING_PORTFOLIO_CONTEXT`.

`ExecutionContext` is resolved in this order:

1. **In-line object:** use `step.inputs["execution_context"]` if present and not `None`.
2. **Step reference by ID:** if `step.inputs["execution_context_step_id"]` is present, find the step with that ID and use its `data["execution_context"]` if state is `SUCCESS`.
3. If neither resolves, the controlled universe engine receives `None` and fails closed internally with `MISSING_EXECUTION_CONTEXT`.

### Step Ordering Constraints

- A `CONTROLLED_UNIVERSE` step must not appear before a `PORTFOLIO_CONSTRUCTION` step it depends on.
- A `PORTFOLIO_CONSTRUCTION` step must not appear before a `DISCOVERY` step it depends on, unless the caller provides in-line inputs.
- The orchestrator validates these constraints during `validate_run_plan_dependencies`.

### Failure Propagation

- If `fail_fast=True` (default):
  - First `FAILED` or `BLOCKED` step terminates the run.
  - Run state becomes `FAILED` or `BLOCKED`.
  - Remaining steps are `SKIPPED` with reason `UPSTREAM_STEP_FAILED` or `UPSTREAM_STEP_BLOCKED`.
- If `fail_fast=False`:
  - Each step is evaluated independently.
  - Steps that can resolve their inputs run normally.
  - Steps that depend on failed/blocked upstream steps are `BLOCKED` or `SKIPPED`.
  - Run state is `PARTIAL` if any step failed or blocked but some succeeded.

### Partial-Run Behavior

A run is `PARTIAL` when:
- At least one step succeeded, and
- At least one step failed or was blocked, and
- The run did not terminate early due to `fail_fast=True`.

The orchestrator still emits a `ResearchRunResult` with accurate step states and artifact references for successful steps.

## Determinism

All outputs must be deterministic for identical inputs. The following rules guarantee this:

- **Run identity:** `(run_id, generated_at, step_id_order)`.
- **Step ordering:** steps execute in the exact order of `plan.steps`.
- **Artifact ordering:** artifacts are appended in step-index order.
- **Reason-code ordering:** run-level reason codes are sorted lexicographically; step-level reason codes preserve encounter order.
- **Input resolution:** when multiple upstream steps could provide the same input (e.g., two `PORTFOLIO_CONSTRUCTION` steps), the most recent preceding step is chosen deterministically.
- **Serialization field order:** `dict` and JSON outputs preserve the field order defined in the dataclasses.
- **No external state:** the orchestrator does not read the filesystem, environment variables (except `PYTHONPATH` for imports), or network state.

## Failure Behavior

### Missing Input

- Missing `PortfolioConstructionReport` → step `BLOCKED`, reason `MISSING_PORTFOLIO_CONTEXT`.
- Missing `ExecutionContext` → step `BLOCKED`, reason `MISSING_EXECUTION_CONTEXT`.
- Missing both → step `BLOCKED`, reasons include both.

### Stale Input

- If the resolved `PortfolioConstructionReport.data_quality.stale` is `True` → step `BLOCKED`, reason `STALE_INPUT`.
- If the resolved `ExecutionContext.safety_flags` or `data_quality` indicates stale data → step `BLOCKED`, reason `STALE_INPUT`.
- If freshness metadata is absent → step `BLOCKED`, reason `STALE_INPUT`.

### Contradictory Input

- `ExecutionContext.execution_state` is `BLOCKED`/`UNKNOWN` while portfolio has `INCLUDED`/`CAPPED` items → step `BLOCKED`, reason `EXECUTION_BLOCKED`.
- `AllowedMode.NONE` with non-empty portfolio → step `BLOCKED`, reason `MACRO_MODE_NONE`.
- Portfolio summary item counts do not match actual items → step `BLOCKED`, reason `INVALID_PORTFOLIO_SUMMARY`.
- `ExecutionContext.allowed_mode` conflicts with per-pair research direction → controlled universe engine handles this internally; the orchestrator propagates the resulting reason codes.

### Downstream-Step Failure

- A `CONTROLLED_UNIVERSE` step that depends on a failed/blocked upstream step is `BLOCKED`.
- Reason code is `UPSTREAM_STEP_FAILED` if the upstream step state is `FAILED`.
- Reason code is `UPSTREAM_STEP_BLOCKED` if the upstream step state is `BLOCKED`.
- If the upstream step is `SKIPPED`, the downstream step is `SKIPPED` with reason `UPSTREAM_STEP_BLOCKED`.

## Acceptance Criteria

1. `build_research_run_result` returns a `ResearchRunResult` for a valid plan including a `CONTROLLED_UNIVERSE` step.
2. A plan with `DISCOVERY` → `PORTFOLIO_CONSTRUCTION` → `CONTROLLED_UNIVERSE` executes end-to-end and produces a `ControlledUniverseReport`.
3. A `CONTROLLED_UNIVERSE` step with in-line `PortfolioConstructionReport` and `ExecutionContext` succeeds without requiring upstream steps.
4. A `CONTROLLED_UNIVERSE` step that references an upstream `PORTFOLIO_CONSTRUCTION` step by `step_id` resolves the report correctly.
5. Missing `PortfolioConstructionReport` blocks the step with reason `MISSING_PORTFOLIO_CONTEXT`.
6. Missing `ExecutionContext` blocks the step with reason `MISSING_EXECUTION_CONTEXT`.
7. Stale upstream `PortfolioConstructionReport` blocks the step with reason `STALE_INPUT`.
8. Stale upstream `ExecutionContext` blocks the step with reason `STALE_INPUT`.
9. `ExecutionContext.execution_state` `BLOCKED`/`UNKNOWN` with included portfolio items blocks with reason `EXECUTION_BLOCKED`.
10. `AllowedMode.NONE` with non-empty portfolio blocks with reason `MACRO_MODE_NONE`.
11. Portfolio summary inconsistent with item counts blocks with reason `INVALID_PORTFOLIO_SUMMARY`.
12. A `CONTROLLED_UNIVERSE` step depending on a failed upstream `PORTFOLIO_CONSTRUCTION` step is blocked with reason `UPSTREAM_STEP_FAILED`.
13. A `CONTROLLED_UNIVERSE` step depending on a blocked upstream `PORTFOLIO_CONSTRUCTION` step is blocked with reason `UPSTREAM_STEP_BLOCKED`.
14. With `fail_fast=True`, the run terminates at the first blocked/failed step and remaining steps are `SKIPPED`.
15. With `fail_fast=False`, a run with mixed success/blocked states returns `ResearchRunState.PARTIAL`.
16. `validate_run_plan_dependencies` returns `False` for a `CONTROLLED_UNIVERSE` step placed before its required `PORTFOLIO_CONSTRUCTION` step when no in-line input is provided.
17. `build_coin_discovery_run_plan` returns a valid plan with deterministic step IDs.
18. Step results are returned in the order of `plan.steps`.
19. Artifacts are returned in step-index order.
20. Writer outputs are deterministic and JSON-serializable.
21. All tests pass; no regressions in existing suite.
22. No modifications to `controlled_universe`, `portfolio_construction`, `discovery`, `execution`, `decision`, or `market_state` packages.
23. No new non-standard-library dependencies for engine logic.
24. No file reads inside the orchestrator engine.
25. No network, exchange, database, server, scheduler, daemon, Freqtrade, or live trading behavior.

## Dependencies

- `hunter.run_orchestrator.models` (existing models)
- `hunter.run_orchestrator.engine` (existing dispatch and run logic)
- `hunter.run_orchestrator.writer` (existing writers)
- `hunter.discovery.models` (`DiscoveryInput`, `DiscoveryReport`)
- `hunter.portfolio_construction.models` (`PortfolioConstructionInput`, `PortfolioConstructionReport`)
- `hunter.controlled_universe` (`ControlledUniverseConfig`, `ControlledUniverseReport`, `build_controlled_universe_report`, `write_controlled_universe_report`)
- `hunter.execution.models` (`ExecutionContext`, `ExecutionState`, `ExecutionMode`)
- `hunter.market_state.models` (`AllowedMode`, `DataQuality`)
- Standard library only for engine logic.
- Optional writer dependencies same as other MVP packages.

## Version

MVP-52 will be tagged `v0.52.0-dev`. The orchestrator version constant `RUN_ORCHESTRATOR_VERSION` will be updated from `"0.30.0-dev"` to `"0.52.0-dev"` (or a new `END_TO_END_RUN_ORCHESTRATOR_VERSION` constant may be added if preserving the old constant is preferred). For simplicity, bump the existing constant to `0.52.0-dev`.

## Implementation Notes (Step 1–4)

### Step 1: Models and Dependency Validator

- Add `ResearchRunStepKind.CONTROLLED_UNIVERSE` to `src/hunter/run_orchestrator/models.py`.
- Add new reason codes to `RUN_ORCHESTRATOR_BLOCKING_REASON_CODES` and `RUN_ORCHESTRATOR_REASON_CODES`.
- Add `ControlledUniverseRunInput` dataclass.
- Extend `ResearchRunDataQuality` with controlled-universe counts.
- Add `validate_run_plan_dependencies` function to `src/hunter/run_orchestrator/engine.py`.
- Add tests in `tests/test_run_orchestrator/test_models.py` and `tests/test_run_orchestrator/test_engine.py`.

### Step 2: Engine Dispatch and Input Resolution

- Add `_dispatch_step` branch for `ResearchRunStepKind.CONTROLLED_UNIVERSE`.
- Implement input resolution logic:
  - In-line objects.
  - Step references by `step_id` and `step_index`.
  - Default upstream resolution.
- Implement stale/contradictory/partial-run/downstream failure handling.
- Update `_build_data_quality` and `_build_safety_flags` to aggregate controlled universe results.
- Add integration tests covering end-to-end pipeline.

### Step 3: Writer and Plan Builder

- Add `build_coin_discovery_run_plan` convenience builder.
- Update `src/hunter/run_orchestrator/writer.py` to serialize the new step kind and data quality fields.
- Add tests for writer and plan builder.

### Step 4: SPEC Alignment and Finalization

- Update `VERSION`, `pyproject.toml`, `src/hunter/__init__.py` to `0.52.0-dev`.
- Update `CHANGELOG.md`, `docs/MVP_INDEX.md`, `docs/handoff/CURRENT_STATE.md`, `AGENTS.md`, `tasks/active.md`, `tasks/agent-log.md`.
- Tag `v0.52.0-dev` at finalization commit (after human approval).

## Implementation Boundaries

- **No modifications** to `controlled_universe`, `portfolio_construction`, `discovery`, `execution`, `decision`, or `market_state` packages.
- **No new dependencies** beyond standard library for engine logic.
- **No file I/O** in engine functions; writers may use standard library only.
- **No data/report inspection** at runtime.
- **Established contracts remain intact:** existing `ResearchRunStepKind`, `ResearchRunStep`, `ResearchRunPlan`, `ResearchRunConfig`, `ResearchRunResult`, `ResearchRunStepResult`, and `ResearchRunArtifact` fields and behaviors are preserved; only additive extensions are allowed.

## Task Graph

```
spec-draft
    ├── models-extension
    │       ├── add-controlled-universe-step-kind
    │       ├── add-reason-codes
    │       ├── add-controlled-universe-run-input
    │       └── extend-data-quality
    ├── engine-extension
    │       ├── input-resolution-for-portfolio-report
    │       ├── input-resolution-for-execution-context
    │       ├── controlled-universe-dispatch-branch
    │       ├── stale-input-handling
    │       ├── contradictory-input-handling
    │       ├── partial-run-handling
    │       └── downstream-failure-propagation
    ├── plan-builder
    │       └── build-coin-discovery-run-plan
    ├── dependency-validator
    │       └── validate-run-plan-dependencies
    ├── writer-extension
    │       ├── serialize-new-step-kind
    │       └── serialize-extended-data-quality
    ├── focused-tests
    │       ├── model-tests
    │       ├── engine-unit-tests
    │       └── writer-tests
    ├── integration-tests
    │       ├── end-to-end-discovery-portfolio-universe
    │       ├── inline-input-controlled-universe
    │       ├── upstream-reference-resolution
    │       └── fail-fast-vs-partial-run
    ├── regression-tests
    │       └── full-pytest-suite
    └── finalization
            ├── version-bump
            ├── changelog-update
            ├── mvp-index-update
            ├── current-state-update
            ├── agents-update
            ├── tasks-update
            └── tag-pending
```

## Test Strategy

### Focused Tests

- **Model tests:** verify new enum value, new reason codes, `ControlledUniverseRunInput` validation, and extended `ResearchRunDataQuality` defaults.
- **Engine unit tests:** test input resolution (in-line, by ID, by index, default upstream), stale detection, contradiction detection, partial-run behavior, and downstream failure propagation.
- **Writer tests:** verify JSON/CSV/Markdown serialization includes the new step kind and data quality fields.
- **Plan builder tests:** verify deterministic step IDs and valid plans.
- **Dependency validator tests:** verify valid and invalid plans.

### Integration Tests

- **End-to-end discovery → portfolio → universe:** create `DiscoveryInput` objects, run `DISCOVERY`, pass report to `PORTFOLIO_CONSTRUCTION`, pass `PortfolioConstructionReport` and `ExecutionContext` to `CONTROLLED_UNIVERSE`, assert final `ControlledUniverseReport` is produced.
- **Inline-input controlled universe:** run a plan with only `CONTROLLED_UNIVERSE` and in-line inputs; assert it succeeds.
- **Upstream reference resolution:** run a plan with `PORTFOLIO_CONSTRUCTION` step ID referenced by `CONTROLLED_UNIVERSE`; assert resolution.
- **Fail-fast vs. partial-run:** run a plan with a failing upstream step and assert run state and downstream behavior under both modes.

### Regression Tests

- Run the full `pytest -q` suite before and after implementation.
- Target: no regressions; all existing `run_orchestrator` tests continue to pass.
- Target: full suite passes with the same 1 skipped test as before.

## Notes

- The orchestrator remains a coordinator. It does not change the semantics of `build_controlled_universe_report`; it only supplies the correct inputs and propagates the results.
- All safety claims are inherited from the underlying engines. The orchestrator's job is to ensure inputs are routed correctly and that failures are surfaced deterministically.
- No new I/O beyond existing writers is introduced.
