# SPEC-054-Controlled-Universe-Export-Adapter

## Background

`PROJECT.md` envisions Hunter Futures Pro as an agent-first crypto futures research and execution-control platform. Hunter decides whether execution should be allowed; Freqtrade is only the execution layer.

MVP-51 (`SPEC-052`) implemented the `controlled_universe` package, which consumes `ExecutionContext` (macro) and `PortfolioConstructionReport` (per-coin) to produce a deterministic `ControlledUniverseReport`. MVP-52 (`SPEC-053`) wired the controlled-universe step into the `run_orchestrator` so the full coin-discovery pipeline can run end-to-end:

`discovery → portfolio_construction → controlled_universe`

However, the `ControlledUniverseReport` is a research-only audit artifact. It is not a trading signal, not execution approval, and not a Freqtrade input. There is currently no deterministic, fail-closed adapter that consumes this report and produces a stable, human-reviewable representation of which pairs may be considered for the execution layer and which are explicitly blocked.

MVP-53 designs and implements a **Controlled Universe Export Adapter** that converts a `ControlledUniverseReport` into deterministic research-only representations, keeping Hunter as the decision layer and Freqtrade as a downstream execution consumer that still requires explicit human approval.

## Purpose

The Controlled Universe Export Adapter consumes a `ControlledUniverseReport` and produces deterministic research-only artifacts that represent the allowed and blocked pair sets in a format compatible with the execution layer's configuration conventions.

The adapter is a pure, local, caller-triggered transformation. It does not start services, schedule jobs, read arbitrary files, connect to networks, exchanges, databases, or external services, and never emits trading or execution commands.

The adapter is **not** a trading signal, not a strategy selector, not a position-sizing tool, and not an execution approval system. It is a research-only adapter that records the controlled universe decision in a structured, machine-readable form for human review and optional downstream configuration.

## Requirements

### Must Have

- Add a new package `hunter.controlled_universe_export_adapter` with the following public interface:
  - `ControlledUniverseExportConfig`
  - `ControlledUniverseExportResult`
  - `build_controlled_universe_export(report, config)`
  - `build_controlled_universe_export_from_run_result(result, config)`
  - `controlled_universe_export_to_dict(result)`
  - `controlled_universe_export_to_json_text(result)`
  - `controlled_universe_export_to_markdown_text(result)`
  - `write_controlled_universe_export(result, output_dir, config)`
- The adapter consumes a `ControlledUniverseReport` from `hunter.controlled_universe.models` and produces a `ControlledUniverseExportResult`.
- The export result contains a deterministic whitelist representation:
  - A JSON-safe list of pair strings (e.g., `["BTC/USDT", "ETH/USDT"]`).
  - Empty list when the report is blocked, unsafe, stale, invalid, or missing required inputs.
- The export result contains a deterministic blacklist representation:
  - A JSON-safe list of pair strings blocked or excluded by the controlled universe engine.
  - Includes all pairs from the report with state `BLOCKED`, `EXCLUDED`, or `INSUFFICIENT_DATA`.
- The export result contains a human-readable per-pair inclusion/exclusion summary:
  - For each pair in the original report, record:
    - `pair`: pair identifier string.
    - `state`: `INCLUDED`, `WATCHLIST`, `EXCLUDED`, `BLOCKED`, or `INSUFFICIENT_DATA`.
    - `classification`: `LONG_RESEARCH`, `SHORT_RESEARCH`, `NEUTRAL_RESEARCH`, `BLOCKED_BY_MACRO`, `BLOCKED_BY_PORTFOLIO`, `WATCHLIST_RESEARCH`.
    - `reason_codes`: tuple of reason codes explaining the decision.
    - `human_note`: a short deterministic explanation such as "passed controlled universe filter" or "blocked by macro execution context".
- The export result contains explicit safety flags:
  - `research_only: bool = True`
  - `human_approval_required: bool = True`
- The adapter is fail-closed:
  - If the input `ControlledUniverseReport` is `None`, the adapter returns an empty whitelist, a `MISSING_REPORT_INPUT` reason code, and safety flags set to research-only / human approval required.
  - If the report's safety flags indicate `is_safe is False` or `has_blocked_execution is True`, the adapter returns an empty whitelist and a `BLOCKED_EXPORT` reason code.
  - If the report contains any unsafe or blocked state, the adapter still emits the blacklist and per-pair summary, but the whitelist is empty.
  - If the report is valid but contains no `INCLUDED` items, the adapter returns an empty whitelist and a `NO_INCLUDED_PAIRS` advisory reason code.
- The adapter preserves the reason codes from the `ControlledUniverseReport` and adds adapter-specific reason codes:
  - `MISSING_REPORT_INPUT`
  - `BLOCKED_EXPORT`
  - `NO_INCLUDED_PAIRS`
  - `EXPORT_RESEARCH_ONLY`
  - `EXPORT_HUMAN_APPROVAL_REQUIRED`
  - `NO_FREQTRADE_RUNTIME_CONNECTION`
  - `NO_AUTOMATIC_CONFIG_MUTATION`
- The adapter does not modify the `ControlledUniverseReport` or any existing package.
- The adapter does not import or call Freqtrade runtime, strategy, or configuration code.
- The adapter does not import or call exchange, API, network, database, scheduler, or live trading code.
- The adapter output is deterministic for identical inputs:
  - Pair lists are sorted lexicographically.
  - Per-pair summaries are sorted by pair identifier.
  - Reason codes are sorted lexicographically.
  - Safety flags and human notes are deterministic.
- The writer performs atomic file writes with safe defaults:
  - JSON: `data/controlled_universe_export/latest_export.json`
  - Markdown: `reports/controlled_universe_export/latest_export.md`
- All paths are opaque strings; the adapter never reads, traverses, validates, or follows file references.

### Should Have

- A convenience classmethod `ControlledUniverseExportConfig.default()` for the default configuration.
- Configurable pair formatter (e.g., "BTC/USDT" vs "BTC_USDT") with a default that matches the execution layer's documented convention.
- Configurable output directory via `ControlledUniverseExportConfig`.
- Markdown output includes a prominent safety notice and a summary table.

### Could Have

- Optional CSV output.
- Optional static `pairlists` config object representation that mirrors the execution layer's JSON structure but is explicitly labeled as a research-only template.
- A CLI dry-run mode that prints the export without writing files.

### Won't Have

- Live trading, order placement, or position sizing.
- Exchange API connection or real-time market data ingestion.
- Freqtrade runtime integration, strategy implementation, or automatic config mutation.
- Scheduler, daemon, web UI, dashboard, or REST API.
- Database persistence.
- Modification of `controlled_universe`, `run_orchestrator`, `portfolio_construction`, `discovery`, `execution`, `decision`, or `market_state` package internals.
- Feedback from the export back into upstream engines.
- Production-readiness, trading-readiness, or suitability claims.

## Interface / Public API

```python
from hunter.controlled_universe_export_adapter import (
    ControlledUniverseExportConfig,
    ControlledUniverseExportResult,
    build_controlled_universe_export,
    build_controlled_universe_export_from_run_result,
    controlled_universe_export_to_dict,
    controlled_universe_export_to_json_text,
    controlled_universe_export_to_markdown_text,
    write_controlled_universe_export,
)
```

### Primary Adapter Function

```python
def build_controlled_universe_export(
    report: ControlledUniverseReport | None,
    config: ControlledUniverseExportConfig | None = None,
) -> ControlledUniverseExportResult:
    """Transform a ControlledUniverseReport into a deterministic research-only export."""
    ...
```

### Convenience Function

```python
def build_controlled_universe_export_from_run_result(
    result: ResearchRunResult,
    config: ControlledUniverseExportConfig | None = None,
) -> ControlledUniverseExportResult:
    """Extract the controlled-universe report from a ResearchRunResult and export it."""
    ...
```

### Writer Functions

```python
def controlled_universe_export_to_dict(
    result: ControlledUniverseExportResult,
) -> dict[str, Any]:
    ...

def controlled_universe_export_to_json_text(
    result: ControlledUniverseExportResult,
) -> str:
    ...

def controlled_universe_export_to_markdown_text(
    result: ControlledUniverseExportResult,
) -> str:
    ...

def write_controlled_universe_export(
    result: ControlledUniverseExportResult,
    output_dir: str | Path | None = None,
    config: ControlledUniverseExportConfig | None = None,
) -> tuple[Path, Path]:
    """Atomically write JSON and Markdown export artifacts.

    Returns the written JSON path and Markdown path.
    """
    ...
```

## Data Model

### `ControlledUniverseExportConfig`

```python
@dataclass(frozen=True)
class ControlledUniverseExportConfig:
    pair_format: str = "base/quote"  # alternative: "base_quote"
    output_dir: str = "data/controlled_universe_export"
    markdown_output_dir: str = "reports/controlled_universe_export"
    json_filename: str = "latest_export.json"
    markdown_filename: str = "latest_export.md"
    include_watchlist_in_whitelist: bool = False
    include_reason_codes_in_summary: bool = True
```

### `ControlledUniverseExportResult`

```python
@dataclass(frozen=True)
class ControlledUniverseExportResult:
    report_id: str
    generated_at: datetime
    whitelist: tuple[str, ...]
    blacklist: tuple[str, ...]
    per_pair_summary: tuple[ControlledUniversePairExportSummary, ...]
    research_only: bool = True
    human_approval_required: bool = True
    reason_codes: tuple[str, ...]
    safety_flags: dict[str, bool]
    metadata: dict[str, Any]
```

### `ControlledUniversePairExportSummary`

```python
@dataclass(frozen=True)
class ControlledUniversePairExportSummary:
    pair: str
    state: str
    classification: str
    reason_codes: tuple[str, ...]
    human_note: str
```

## Safety

- Fail-closed: missing or unsafe input produces an empty whitelist.
- Fail-closed: blocked or stale report produces an empty whitelist and explicit reason codes.
- All adapter functions remain pure and deterministic.
- No file reads, no network, no shell, no database, no Freqtrade import, no exchange import.
- No data/ or reports/ inspection; the adapter only writes its own output artifacts.
- No action commands, no order instructions, no position sizes, no leverage, no shorting approval.
- Research-only output; not a trading signal, not execution approval, not a strategy selector.
- All file writes are optional and atomic; engine functions are path-agnostic.
- Paths are opaque strings; never traversed, validated, or opened by the adapter.
- The adapter never modifies upstream engine packages or their outputs.

## Out of Scope

- Implementing or modifying a Freqtrade strategy.
- Modifying the `controlled_universe`, `run_orchestrator`, `portfolio_construction`, `discovery`, `execution`, `decision`, or `market_state` packages.
- Adding a scheduler or daemon.
- Adding a Web UI or dashboard.
- Adding database persistence.
- Adding real-time market data ingestion.
- Adding order placement, position sizing, or leverage logic.
- Adding live trading or shorting approval.
- Changing the safety policy of existing engines.
- Replacing the existing `controlled_universe` models or writer; only additive extensions.

## Determinism

All outputs must be deterministic for identical inputs:

- Pair lists are sorted lexicographically.
- Per-pair summaries are sorted by pair identifier.
- Reason codes are sorted lexicographically within each list.
- `generated_at` is either caller-provided or derived from `ControlledUniverseReport.timestamp`.
- No external state: the adapter does not read the filesystem, environment variables (except `PYTHONPATH` for imports), or network state.

## Failure Behavior

### Missing Input

- Input `ControlledUniverseReport` is `None` → empty whitelist, empty blacklist, reason code `MISSING_REPORT_INPUT`, research-only and human-approval flags set.

### Unsafe or Blocked Report

- `ControlledUniverseReport.safety_flags.is_safe` is `False` → empty whitelist, blacklist and summary still emitted, reason code `BLOCKED_EXPORT`.
- Any report state indicates blocked execution → empty whitelist.

### No Included Pairs

- Report is valid and safe but contains no `INCLUDED` items → empty whitelist, reason code `NO_INCLUDED_PAIRS`, blacklist and summary still emitted.

## Acceptance Criteria

1. `build_controlled_universe_export` returns a `ControlledUniverseExportResult` for a valid `ControlledUniverseReport`.
2. The whitelist contains exactly the `INCLUDED` pairs from the report, formatted as configured.
3. The blacklist contains all `BLOCKED`, `EXCLUDED`, and `INSUFFICIENT_DATA` pairs from the report.
4. `WATCHLIST` pairs are not in the whitelist by default but appear in the per-pair summary.
5. The per-pair summary contains one entry for every pair in the report, sorted by pair identifier.
6. The export result has `research_only=True` and `human_approval_required=True` for all inputs.
7. A `None` report input produces an empty whitelist and reason code `MISSING_REPORT_INPUT`.
8. An unsafe report input produces an empty whitelist and reason code `BLOCKED_EXPORT`.
9. A valid but empty included set produces an empty whitelist and reason code `NO_INCLUDED_PAIRS`.
10. Reason codes are sorted lexicographically.
11. Pair lists are sorted lexicographically.
12. Markdown output contains a safety notice and the research-only / human-approval flags.
13. `build_controlled_universe_export_from_run_result` extracts the controlled-universe report from a `ResearchRunResult` and produces the same export as `build_controlled_universe_export`.
14. No existing package internals are modified.
15. No Freqtrade, exchange, network, database, scheduler, or live trading code is imported or called.

## Test Strategy

- Unit tests in `tests/test_controlled_universe_export_adapter/`:
  - Valid report → whitelist/blacklist/summary structure.
  - `None` report → fail-closed behavior.
  - Unsafe report → empty whitelist.
  - Empty included set → empty whitelist.
  - Pair format variations (`base/quote` vs `base_quote`).
  - Determinism: identical inputs produce identical outputs.
  - Writer round-trip: dict → JSON → parse → compare.
  - Markdown contains safety notice and flags.
  - `build_controlled_universe_export_from_run_result` extracts from a real `ResearchRunResult`.
- Integration tests use `build_coin_discovery_run_plan` and `build_research_run_result` from MVP-52 to produce a report, then export it.
- Full test suite must continue to pass.

## Files

- `specs/SPEC-054-Controlled-Universe-Export-Adapter.md` (this specification)
- `src/hunter/controlled_universe_export_adapter/__init__.py`
- `src/hunter/controlled_universe_export_adapter/models.py`
- `src/hunter/controlled_universe_export_adapter/engine.py`
- `src/hunter/controlled_universe_export_adapter/writer.py`
- `tests/test_controlled_universe_export_adapter/__init__.py`
- `tests/test_controlled_universe_export_adapter/test_models.py`
- `tests/test_controlled_universe_export_adapter/test_engine.py`
- `tests/test_controlled_universe_export_adapter/test_writer.py`
- `tests/test_controlled_universe_export_adapter/test_integration.py`

## Version Target

MVP-53 will be tagged `v0.53.0-dev` after implementation, documentation, and finalization. Version bump is deferred to Step 4 of the MVP-53 SDD flow.
