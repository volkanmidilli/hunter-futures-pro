# SPEC-052-Controlled-Universe-Bridge-Engine

## Background

The original 12-module plan in `PROJECT.md` describes an integrated decision platform:

- Market regime and breadth determine the **macro** trading mode.
- Relative strength and open interest identify **individual** coin candidates.
- Discovery and portfolio construction group and rank those candidates.
- A decision gate blocks or allows execution in that regime.
- Freqtrade acts only as the execution layer.

The repository has completed both halves of this chain independently:

- **Pipeline A (Macro Decision):** `market_state` → `decision` → `execution` → `freqtrade_bridge` → `strategy_contract` → `dry_run_strategy`.
- **Pipeline B (Coin Selection):** `relative_strength` + `open_interest` → `discovery` → `portfolio_construction`.

However, no engine bridges the two pipelines. `portfolio_construction` produces a ranked list of candidates (`INCLUDED`, `CAPPED`, `WATCHLIST`, `EXCLUDED`, `INSUFFICIENT_DATA`, `BLOCKED`), but that list never reaches the decision gate or Freqtrade. The execution chain currently makes a single ALLOW/BLOCK decision for **all** pairs and has no notion of a per-pair controlled universe.

MVP-51 designs and implements the **Controlled Universe Bridge Engine** to close that gap.

## Purpose

The Controlled Universe Bridge Engine consumes the macro execution context (from the Decision/Execution layers) and the per-coin portfolio construction report, and produces a deterministic, fail-closed **controlled universe** list suitable for downstream consumption by a Freqtrade whitelist or strategy guard.

The engine is **not** a trading signal, not a strategy selector, not a position-sizing tool, and not an approval gate. It is a deterministic research-only bridge that records, for each pair, whether it is included in the controlled universe and why.

## Requirements

### Must Have

- Consume a `PortfolioConstructionReport` (from MVP-27) as the source of per-coin state.
- Consume an `ExecutionContext` (from MVP-4 / SPEC-005) as the macro safety gate.
- Produce a `ControlledUniverseReport` with:
  - A `universe` list of allowed pair strings.
  - A `blocked` list of pairs removed with reason codes.
  - A `watchlist` list of pairs not in the universe but tracked.
  - A `data_quality` object.
  - A `safety_flags` object.
  - A deterministic `reason_codes` list.
- Fail-closed defaults:
  - If `ExecutionContext` is missing, invalid, or not `DRY_RUN_ONLY`/`ENABLED`, universe is empty.
  - If `PortfolioConstructionReport` is missing, universe is empty.
  - If `PortfolioConstructionState` is `EXCLUDED`, `BLOCKED`, `INSUFFICIENT_DATA`, or `WATCHLIST`, the pair is **not** in the universe.
- Allow only `INCLUDED` and `CAPPED` states into the universe (with a deterministic tie-breaker if needed).
- Detect duplicate normalized pair identifiers in `PortfolioConstructionReport` and fail closed with an empty universe and a deterministic `DUPLICATE_PAIR_DETECTED` reason code.
- Consume freshness and data-quality state already present in `ExecutionContext` and `PortfolioConstructionReport`; do not invent an independent market-data freshness policy.
- Fail closed when freshness/data-quality state is missing, unknown, stale, or invalid.
- Apply gate precedence in the exact order defined in the **Gate Precedence** section.
- Apply configurable limits:
  - `max_universe_pairs`: cap the number of pairs in the universe (priority by score, then symbol).
  - `min_portfolio_score`: minimum score threshold for inclusion.
- Respect the `AllowedMode` from the execution context: if mode is `LONG_ONLY`, block short-only research candidates; if `SHORT_ONLY`, block long-only; if `NONE`, block all.
- Deterministic output for identical inputs.
- No file I/O, no network, no database, no exchange API, no Freqtrade runtime, no action commands, no live trading in the engine itself.
- Pure functions operating on in-memory inputs.
- Frozen dataclasses with `__post_init__` validation.
- Reason codes for every inclusion/exclusion decision.
- Writer helpers for JSON, Markdown, and CSV serialization (same pattern as other MVP packages).
- Atomic file-write helpers returning paths as opaque strings (no path validation in engine).
- Integration tests covering the bridge from portfolio construction to controlled universe.
- Safety notice repeated in outputs: research-only, not trading advice, not execution approval.

### Should Have

- Capped-pair annotation: include the cap reason in the report metadata, not in pair string.
- Explicit `transition` handling: if `ExecutionContext` is in a transition state, fail-closed to empty universe.
- Optional `exclude_reason` enum partitions for UI/CLI filtering.
- Stable pair IDs derived from deterministic input hashing (for downstream audit traceability).
- Configurable `max_watchlist_pairs` for reporting.
- Markdown summary with human-readable table of included, watchlist, and blocked pairs.

### Could Have

- Support for future per-pair risk scores from a later MVP.
- Direct downstream strategy contract integration (out of scope for MVP-51; this is the bridge only).
- Optional CSV writer for CLI consumption.

### Won't Have

- Live trading.
- Order placement.
- Position sizing.
- Freqtrade strategy implementation.
- Exchange API connection.
- Web UI, dashboard, or scheduler.
- Feedback from this report into the decision gate or portfolio engine (this engine is read-only).
- No database persistence.
- No file reads inside the engine.

## Inputs

1. `PortfolioConstructionReport` (from `hunter.portfolio_construction.models`).
2. `ExecutionContext` (from `hunter.execution.models`).
3. `ControlledUniverseConfig` (new in this package).

## Outputs

1. `ControlledUniverseReport` (new in this package).
2. `ControlledUniverseSafetyFlags` (new in this package).
3. `ControlledUniverseDataQuality` (new in this package).
4. Writer outputs: JSON string, Markdown string, CSV string, atomic file writes.

## Interface / Public API

```python
from hunter.controlled_universe import (
    build_controlled_universe_report,
    build_controlled_universe_safety_flags,
    build_controlled_universe_data_quality,
    classify_controlled_universe_item,
    ControlledUniverseConfig,
    ControlledUniverseReport,
    ControlledUniverseSafetyFlags,
    ControlledUniverseDataQuality,
    ControlledUniverseState,
    ControlledUniverseClassification,
    controlled_universe_report_to_dict,
    controlled_universe_report_to_json_text,
    controlled_universe_report_to_csv_text,
    controlled_universe_report_to_markdown,
    atomic_write_json_controlled_universe_report,
    atomic_write_csv_controlled_universe_report,
    atomic_write_markdown_controlled_universe_report,
)
```

Primary engine function:

```python
def build_controlled_universe_report(
    portfolio_report: PortfolioConstructionReport | None,
    execution_context: ExecutionContext | None,
    config: ControlledUniverseConfig | None = None,
) -> ControlledUniverseReport:
    ...
```

## Data Model

### Enums

```python
class ControlledUniverseState(Enum):
    INCLUDED = "INCLUDED"
    WATCHLIST = "WATCHLIST"
    EXCLUDED = "EXCLUDED"
    BLOCKED = "BLOCKED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

class ControlledUniverseClassification(Enum):
    LONG_RESEARCH = "LONG_RESEARCH"
    SHORT_RESEARCH = "SHORT_RESEARCH"
    NEUTRAL_RESEARCH = "NEUTRAL_RESEARCH"
    BLOCKED_BY_MACRO = "BLOCKED_BY_MACRO"
    BLOCKED_BY_PORTFOLIO = "BLOCKED_BY_PORTFOLIO"
    WATCHLIST_RESEARCH = "WATCHLIST_RESEARCH"
```

### Reason Codes

- `INVALID_PAIR`
- `DUPLICATE_PAIR_DETECTED`
- `MISSING_EXECUTION_CONTEXT`
- `EXECUTION_BLOCKED`
- `EXECUTION_UNKNOWN`
- `MACRO_MODE_NONE`
- `MACRO_MODE_MISMATCH`
- `TRANSITION_STATE`
- `MISSING_PORTFOLIO_CONTEXT`
- `INVALID_PORTFOLIO_SUMMARY`
- `PORTFOLIO_STATE_EXCLUDED`
- `PORTFOLIO_STATE_BLOCKED`
- `PORTFOLIO_STATE_INSUFFICIENT_DATA`
- `PORTFOLIO_STATE_WATCHLIST`
- `LOW_PORTFOLIO_SCORE`
- `MAX_UNIVERSE_PAIRS_EXCEEDED`
- `PASSED_UNIVERSE_FILTER`
- `HUMAN_RESEARCH_ONLY`
- `NO_ACTION_COMMANDS_EMITTED`
- `NO_FILE_READ_IN_ENGINE`
- `NO_NETWORK_CONNECTION`

### Config

```python
@dataclass(frozen=True, slots=True)
class ControlledUniverseConfig:
    max_universe_pairs: int | None = None
    min_portfolio_score: float | None = None
    max_watchlist_pairs: int | None = None
    include_capped: bool = True
    default_mode: AllowedMode = AllowedMode.LONG_ONLY
    require_dry_run: bool = True  # Must remain True for MVP-51; setting False is invalid.
```

**Config validation:**
- `require_dry_run` must be `True`. A `ValueError` (or equivalent) is raised at construction time if `False` is supplied. MVP-51 does not approve any `ENABLED`/live execution path.

### Report

```python
@dataclass(frozen=True, slots=True)
class ControlledUniverseReport:
    version: str
    generated_at: datetime
    config: ControlledUniverseConfig
    execution_state: str | None
    allowed_mode: str | None
    universe: tuple[str, ...]
    watchlist: tuple[str, ...]
    blocked: tuple[str, ...]
    items: tuple[ControlledUniverseItem, ...]
    data_quality: ControlledUniverseDataQuality
    safety_flags: ControlledUniverseSafetyFlags
    reason_codes: tuple[str, ...]
```

```python
@dataclass(frozen=True, slots=True)
class ControlledUniverseItem:
    pair: str
    state: ControlledUniverseState
    classification: ControlledUniverseClassification
    reason_codes: tuple[str, ...]
    portfolio_score: float | None
    portfolio_state: str | None
    capped: bool
```

## Safety

- Fail-closed: missing or invalid macro context yields an empty universe.
- Fail-closed: missing or invalid portfolio report yields an empty universe.
- All functions pure and deterministic.
- No file reads, no network, no shell, no database, no Freqtrade import, no exchange import.
- No action commands, no order instructions, no position sizes.
- Research-only output; not a trading signal, not execution approval, not a strategy selector.
- All file writes are optional and atomic; engine functions are path-agnostic.
- Paths are opaque strings; never traversed, validated, or opened.

## Out of Scope

- Implementing a Freqtrade strategy.
- Modifying the decision or execution engines.
- Modifying the portfolio construction or discovery engines.
- Adding a scheduler or daemon.
- Adding Web UI or dashboard.
- Adding database persistence.
- Adding real-time market data ingestion.
- Adding order placement, position sizing, or leverage logic.
- Adding live trading or shorting approval.
- Changing the safety policy of existing engines.

## Default Writer Paths

Writers must use atomic replacement and must remain free of file I/O in the engine functions. The default paths below are opaque strings; the engine never validates, traverses, or opens them.

- JSON: `data/controlled_universe/latest_controlled_universe.json`
- Markdown: `reports/controlled_universe/latest_controlled_universe.md`
- CSV: `data/controlled_universe/latest_controlled_universe.csv`

The writer helpers must:
- Write to a temporary file in the same directory.
- Replace the target atomically (e.g., `os.replace`).
- Return the target path as an opaque string.
- Not create intermediate directories unless a config flag explicitly enables it (out of scope for MVP-51; tests may use temporary directories).

## Gate Precedence

The engine must apply the following gates in strict order. The first failing gate determines the outcome and reason codes.

1. **Input validation** — validate types and required fields. Missing or invalid `ExecutionContext` or `PortfolioConstructionReport` fails closed.
2. **Duplicate detection** — detect duplicate normalized pair identifiers in the portfolio report. Duplicates fail closed with `DUPLICATE_PAIR_DETECTED`.
3. **Freshness / data-quality validation** — propagate and enforce `DataQuality` and freshness state already present in the inputs. Missing, unknown, stale, or invalid freshness/quality state fails closed.
4. **Execution-state gate** — if `ExecutionContext.execution_state` is not `DRY_RUN_ONLY` or `ENABLED`, or if `ExecutionContext.execution_mode` is `BLOCK_ALL`, fail closed.
5. **Allowed-mode / direction filter** — if `AllowedMode` is `NONE`, fail closed; otherwise, drop per-pair items whose research direction conflicts with the allowed mode.
6. **Portfolio classification mapping** — map `PortfolioConstructionState` to `ControlledUniverseState` and reason codes.
7. **Deterministic ordering** — sort universe, watchlist, and blocked lists by stable keys.
8. **Artifact generation** — produce the report, safety flags, data quality, and optional writer outputs.

## Determinism

All outputs must be deterministic for identical inputs. The following rules guarantee this:

- **Pair normalization:** pair strings are normalized as opaque strings trimmed of leading/trailing whitespace and converted to uppercase before comparison. The original casing is preserved in the report. Empty or whitespace-only strings are invalid (`INVALID_PAIR`).
- **Stable sorting keys:**
  - Primary: descending portfolio score (or `0.0` if missing).
  - Secondary: normalized pair string ascending.
- **Reason-code ordering:** reason codes are emitted in the order they are encountered during gate traversal, then sorted lexicographically for the final report-level tuple.
- **Duplicate reason handling:** when a pair fails multiple gates, only the first-failing gate's reason code is recorded at the item level; report-level reason codes include all distinct reasons encountered.
- **Serialization field order:** `dict` and JSON outputs preserve the field order defined in the report dataclass.

## Contradictory Inputs

The engine must resolve contradictions deterministically and fail-closed:

- **Execution allowed + all portfolio items excluded** → empty `universe`, all pairs in `blocked` with `PORTFOLIO_STATE_EXCLUDED`. No error.
- **Execution blocked + included portfolio items** → empty `universe`; included pairs are moved to `blocked` with `EXECUTION_BLOCKED`. No universe is produced.
- **Direction mismatch** → if `AllowedMode` is `LONG_ONLY`, any per-pair classification implying short research is excluded; if `SHORT_ONLY`, any long research classification is excluded. Affected pairs are recorded with `MACRO_MODE_MISMATCH`.
- **Portfolio summary inconsistent with item counts** → treat as invalid input. Fail closed with empty universe and report-level reason code `INVALID_PORTFOLIO_SUMMARY` (or equivalent) after input validation. This case is separate from the data-quality gates; it is a structural inconsistency in the input report.

## Acceptance Criteria

1. `build_controlled_universe_report` returns a `ControlledUniverseReport` for valid inputs.
2. Missing `ExecutionContext` returns an empty universe with reason `MISSING_EXECUTION_CONTEXT`.
3. `ExecutionState.BLOCKED` or `ExecutionState.UNKNOWN` returns an empty universe with reason `EXECUTION_BLOCKED` or `EXECUTION_UNKNOWN`.
4. `AllowedMode.NONE` returns an empty universe with reason `MACRO_MODE_NONE`.
5. `INCLUDED` and `CAPPED` portfolio items are included (if `include_capped=True`).
6. `EXCLUDED`, `BLOCKED`, `INSUFFICIENT_DATA`, and `WATCHLIST` items are excluded with correct reason codes.
7. `max_universe_pairs` caps the universe deterministically (higher score first, then alphabetical pair).
8. `min_portfolio_score` excludes items below the threshold with reason `LOW_PORTFOLIO_SCORE`.
9. All outputs are JSON-serializable via writer helpers.
10. Markdown output includes a safety notice and a table of included/watchlist/blocked pairs.
11. Integration test demonstrates the full chain from portfolio construction report to controlled universe report.
12. All tests pass; no regressions in existing suite.
13. No runtime code changes in other packages.
14. Duplicate normalized pair identifiers in the portfolio report fail closed with `DUPLICATE_PAIR_DETECTED` and an empty universe.
15. Missing, unknown, stale, or invalid freshness/data-quality state in inputs fails closed with an empty universe.
16. `ControlledUniverseConfig(require_dry_run=False)` is rejected as invalid configuration.
17. Execution allowed with all portfolio items excluded yields an empty universe and all pairs in `blocked` with `PORTFOLIO_STATE_EXCLUDED`.
18. Execution blocked with included portfolio items yields an empty universe with included pairs in `blocked` carrying `EXECUTION_BLOCKED`.
19. Direction mismatch (`AllowedMode.LONG_ONLY` vs short-research classification) moves affected pairs to `blocked` with `MACRO_MODE_MISMATCH`.
20. Portfolio summary inconsistent with item counts fails closed with `INVALID_PORTFOLIO_SUMMARY`.
21. Report outputs are deterministic: identical inputs produce identical `universe`, `watchlist`, `blocked`, and `reason_codes` tuples.

## Dependencies

- `hunter.portfolio_construction.models` (`PortfolioConstructionReport`, `PortfolioConstructionState`, `PortfolioDiscoverySummary`, etc.)
- `hunter.execution.models` (`ExecutionContext`, `ExecutionState`, `ExecutionMode`)
- `hunter.decision.models` (`DecisionAction`, `DecisionState`, `AllowedMode` via `hunter.market_state.models`)
- `hunter.market_state.models` (`AllowedMode`, `OutputStatus`, `DataQuality`)
- Standard library only for engine logic.
- Optional writer dependencies same as other MVP packages.

## Version

MVP-51 will be tagged `v0.51.0-dev`. Engine version constant: `CONTROLLED_UNIVERSE_VERSION = "0.51.0-dev"`.

## Implementation Notes (Step 1–4)

### Step 1: Models and Engine

- Create `src/hunter/controlled_universe/models.py` with frozen dataclasses, enums, reason codes, and validation.
- Create `src/hunter/controlled_universe/engine.py` with `build_controlled_universe_report`, helper classification functions, and deterministic filtering.
- Add `src/hunter/controlled_universe/__init__.py` with public exports.
- Add tests in `tests/test_controlled_universe/test_models.py` and `tests/test_controlled_universe/test_engine.py`.

### Step 2: Writer

- Create `src/hunter/controlled_universe/writer.py` with dict/JSON/CSV/Markdown serialization and atomic write helpers.
- Update `__init__.py` exports.
- Add `tests/test_controlled_universe/test_writer.py`.

### Step 3: Integration Tests

- Add `tests/test_controlled_universe/test_integration.py` demonstrating portfolio construction report → controlled universe report.
- Add cross-package integration test verifying execution context from decision → controlled universe.

### Step 4: SPEC Alignment and Finalization

- Update `VERSION`, `pyproject.toml`, `src/hunter/__init__.py` to `0.51.0-dev`.
- Update `CHANGELOG.md`, `docs/MVP_INDEX.md`, `docs/handoff/CURRENT_STATE.md`, `AGENTS.md`, `tasks/active.md`, `tasks/agent-log.md`.
- Tag `v0.51.0-dev` at finalization commit (after human approval).

## Implementation Boundaries

- **No modifications** to `decision`, `execution`, `freqtrade_bridge`, `strategy_contract`, `discovery`, `portfolio_construction`, `relative_strength`, `open_interest`, or `market_state` packages.
- **No new dependencies** beyond standard library for engine logic.
- **No file I/O** in engine functions; writers may use standard library only.
- **No data/report inspection** at runtime.
