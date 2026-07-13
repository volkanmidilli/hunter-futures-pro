# SPEC-056 — Freqtrade Universe Consumption Adapter

## Background

`PROJECT.md` envisions Hunter Futures Pro as an agent-first crypto futures research and execution-control platform. Hunter Futures Pro is the decision layer; Freqtrade is only the execution layer. The decision layer must determine which coins are suitable for research, and any bridge to Freqtrade must be deterministic, research-only, and fail-closed.

MVP-53 (`SPEC-054`) implemented the `controlled_universe_export_adapter`, which consumes a `ControlledUniverseReport` and produces a `ControlledUniverseExportResult`. The result contains a deterministic whitelist, blacklist, and per-pair inclusion/exclusion summary, all marked `research_only` and `human_approval_required`.

MVP-54 (`SPEC-055`) implemented the `coin_discovery_pipeline` runner, which wires discovery, portfolio construction, controlled universe, and export into a single public call. The pipeline produces a `CoinDiscoveryPipelineResult` that contains a `ControlledUniverseExportResult`.

Currently, there is no deterministic, fail-closed adapter that consumes the research-only `ControlledUniverseExportResult` and emits a Freqtrade-compatible representation that can be reviewed before any execution layer consumes it. MVP-55 designs and implements a **Freqtrade Universe Consumption Adapter** that performs this translation while preserving the research-only, human-approval-required safety posture.

## Purpose

The Freqtrade Universe Consumption Adapter consumes a `ControlledUniverseExportResult` and produces deterministic, research-only, human-approval-required artifacts that can later be reviewed for Freqtrade consumption.

The adapter is a pure, local, caller-triggered transformation. It does not start services, schedule jobs, read arbitrary files, connect to networks, exchanges, databases, or external services, and never emits trading or execution commands.

The adapter is **not** a trading signal, not a strategy selector, not a position-sizing tool, and not an execution approval system. It is a research-only adapter that records the controlled universe decision in a structured, machine-readable form compatible with Freqtrade configuration conventions, pending explicit human review.

## Requirements

### Must Have

- Add a new package `hunter.freqtrade_universe_adapter` with the following public interface:
  - `FREQTRADE_UNIVERSE_ADAPTER_VERSION`
  - `FreqtradeUniverseAdapterConfig`
  - `FreqtradeUniverseAdapterResult`
  - `FreqtradeUniverseAdapterError`
  - `build_freqtrade_universe_adapter_result(export_result, config)`
  - `freqtrade_universe_adapter_result_to_dict(result)`
  - `freqtrade_universe_adapter_result_to_json_text(result)`
  - `freqtrade_universe_adapter_result_to_markdown_text(result)`
  - `write_freqtrade_universe_adapter_result(result, output_dir, config)` — if `output_dir` is provided, it overrides `config.output_dir`; otherwise `config.output_dir` and `config.markdown_output_dir` are used.
- The adapter consumes a `ControlledUniverseExportResult` from `hunter.controlled_universe_export_adapter` and produces a `FreqtradeUniverseAdapterResult`.
- The result contains a deterministic static whitelist representation:
  - JSON-safe list of pair strings sorted lexicographically.
  - Empty list when the export result is blocked, failed, partial, unsafe, stale, invalid, or missing.
- The result contains a deterministic static blacklist representation:
  - JSON-safe list of pair strings blocked or excluded by the controlled universe export.
  - Sorted lexicographically.
- The result contains a deterministic pairlist/config fragment representation:
  - A JSON-safe object compatible with Freqtrade's `StaticPairList` pairlist conventions, e.g. `{"method": "StaticPairList", "pairs": ["BTC/USDT", "ETH/USDT"]}`.
  - The pairlist fragment is derived from the whitelist and is research-only.
- The result contains a strategy-contract-compatible input representation where existing public contracts support it:
  - A JSON-safe object containing `whitelist`, `blacklist`, `mode`, `safety_flags`, and `metadata`.
  - The existing `StrategyContractMode` and `FreqtradeBridgeMode` enums may be reused for mode classification.
  - Existing `StrategyContractSafetyFlags` and `StrategyContractInputRefs` patterns may be reused for structure and naming; they may not be silently redefined.
- The result contains a human-readable per-pair inclusion/exclusion summary:
  - For each pair in the export result, record `pair`, `state`, `classification`, `reason_codes`, and `human_note` from the controlled universe export.
- The result contains explicit safety flags:
  - `research_only: bool = True`
  - `human_approval_required: bool = True`
- The result contains deterministic reason codes:
  - `MISSING_EXPORT_INPUT`
  - `BLOCKED_EXPORT_INPUT`
  - `EMPTY_WHITELIST`
  - `INVALID_PAIR_FORMAT`
  - `DUPLICATE_PAIR`
  - `CONTRADICTORY_PAIR`
  - `EXPORT_RESEARCH_ONLY`
  - `EXPORT_HUMAN_APPROVAL_REQUIRED`
  - `NO_FREQTRADE_RUNTIME_CONNECTION`
  - `NO_AUTOMATIC_CONFIG_MUTATION`
  - `STALE_EXPORT_INPUT`
- The adapter is fail-closed:
  - If `export_result` is `None`, the result has an empty whitelist, a `MISSING_EXPORT_INPUT` reason code, and safety flags set to research-only / human approval required.
  - If `export_result.research_only` is not `True` or `export_result.human_approval_required` is not `True`, the result has an empty whitelist and a `BLOCKED_EXPORT_INPUT` reason code.
  - If the export result's reason codes indicate a blocked, failed, or unsafe export state, the result has an empty whitelist and a `BLOCKED_EXPORT_INPUT` reason code.
  - If the export result's whitelist is empty, the result has an empty whitelist and an `EMPTY_WHITELIST` reason code.
  - If the export result is older than the configured `stale_export_threshold_seconds`, the result has an empty whitelist and a `STALE_EXPORT_INPUT` reason code.
  - The adapter still emits the blacklist and per-pair summary when the whitelist is empty, so the fail-closed decision is auditable.
- The adapter preserves the pair format of the upstream export (`base/quote` or `base_quote`) and never silently changes formats. If the format is not supported, it fails closed with `INVALID_PAIR_FORMAT`.
- The adapter performs deterministic duplicate and contradiction handling:
  - Duplicate pairs within the whitelist or blacklist are deduplicated lexicographically while preserving the first occurrence order.
  - Any pair present in both whitelist and blacklist is treated as a contradiction: it is removed from the whitelist, added to the blacklist, and a `CONTRADICTORY_PAIR` reason code is emitted. The blacklist takes precedence.
  - If any contradiction is detected, the adapter still produces the corrected whitelist and blacklist, but the result includes the contradiction reason code.
- The adapter output is deterministic for identical inputs:
  - Pair lists are sorted lexicographically.
  - Per-pair summaries are sorted by pair identifier.
  - Reason codes are sorted lexicographically.
  - Safety flags and metadata are deterministic.
- The writer performs atomic file writes with safe defaults:
  - JSON packet: `data/freqtrade_universe_adapter/latest_universe.json`
  - Markdown summary: `reports/freqtrade_universe_adapter/latest_universe.md`
  - Pairlist fragment: `data/freqtrade_universe_adapter/pairlist.json`
  - Strategy-contract input: `data/freqtrade_universe_adapter/strategy_contract_input.json`
- All paths are opaque strings; the adapter never reads, traverses, validates, or follows file references except through deterministic writer functions.
- The adapter does not modify the `ControlledUniverseExportResult` or any existing package.

### Should Have

- Markdown output includes a clear safety notice that the artifacts are research-only and require human approval before Freqtrade consumption.
- The config allows overriding `json_filename`, `markdown_filename`, `pairlist_filename`, and `strategy_contract_input_filename`.

### Could Have

- Future MVPs may integrate the adapter into a scheduled or triggered workflow; this MVP does not.
- Future MVPs may add a diff between the current adapter output and the previous output; this MVP does not.

### Will Not Have (Explicit)

- No Freqtrade runtime import or invocation.
- No Freqtrade strategy changes.
- No automatic Freqtrade config mutation.
- No copying artifacts into live Freqtrade directories.
- No exchange, API, network, database, scheduler, or live trading behavior.
- No actionable trading signals or order recommendations.
- No production-readiness, trading-readiness, approval, suitability, or certification claims.
- No reading from `data/` or `reports/` except through deterministic writer functions.
- No MVP-55 implementation; this SPEC is for planning only.

## Model Definitions

### `FreqtradeUniverseAdapterConfig` (frozen dataclass)

| Field | Type | Default | Description |
|---|---|---|---|
| `output_dir` | `str` | `"data/freqtrade_universe_adapter"` | Base directory for JSON and pairlist artifacts. |
| `markdown_output_dir` | `str` | `"reports/freqtrade_universe_adapter"` | Base directory for Markdown artifacts. |
| `pair_format` | `str` | `"base/quote"` | Output pair format: `"base/quote"` or `"base_quote"`. |
| `stale_export_threshold_seconds` | `int` | `300` | Maximum age of `export_result.generated_at` before `STALE_EXPORT_INPUT` is emitted. |
| `include_blacklist` | `bool` | `True` | Include the blacklist in the output artifacts. |
| `include_per_pair_summary` | `bool` | `True` | Include the per-pair summary in the output artifacts. |
| `json_filename` | `str` | `"latest_universe.json"` | Filename for the JSON packet. |
| `markdown_filename` | `str` | `"latest_universe.md"` | Filename for the Markdown summary. |
| `pairlist_filename` | `str` | `"pairlist.json"` | Filename for the pairlist fragment. |
| `strategy_contract_input_filename` | `str` | `"strategy_contract_input.json"` | Filename for the strategy-contract input. |
| `metadata` | `Mapping[str, str]` | `{}` | Optional caller-supplied metadata. |

Validation rules:

- `output_dir` and `markdown_output_dir` must be non-empty strings.
- `pair_format` must be either `"base/quote"` or `"base_quote"`.
- `stale_export_threshold_seconds` must be a non-negative integer.

### `FreqtradeUniverseAdapterResult` (frozen dataclass)

| Field | Type | Description |
|---|---|---|
| `report_id` | `str` | Identifier from the upstream export result. |
| `generated_at` | `datetime` | Timestamp of the upstream export result (timezone-aware). |
| `version` | `str` | Adapter version, defaults to `FREQTRADE_UNIVERSE_ADAPTER_VERSION`. |
| `whitelist` | `tuple[str, ...]` | Sorted, normalized pairs approved for research. |
| `blacklist` | `tuple[str, ...]` | Sorted, normalized pairs blocked or excluded. |
| `pairlist` | `dict[str, Any]` | Freqtrade-compatible static pairlist fragment. |
| `strategy_contract_input` | `dict[str, Any]` | Strategy-contract-compatible input representation. |
| `per_pair_summary` | `tuple[ControlledUniversePairExportSummary, ...]` | Sorted per-pair inclusion/exclusion summary. |
| `research_only` | `bool` | Always `True`. |
| `human_approval_required` | `bool` | Always `True`. |
| `reason_codes` | `tuple[str, ...]` | Sorted adapter-specific reason codes. |
| `safety_flags` | `dict[str, bool]` | Deterministic safety flags. |
| `metadata` | `Mapping[str, str]` | Caller-supplied and upstream metadata. |

Validation rules:

- `report_id` must be a non-empty string.
- `generated_at` must be a timezone-aware datetime.
- `research_only` and `human_approval_required` must be `True`.
- All pair strings must be non-empty.
- `reason_codes` must be a subset of `FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES`.

### `FreqtradeUniverseAdapterError`

Exception raised for invalid adapter configuration, invalid results, or writer failures. Must not be raised for normal fail-closed states (those are encoded in the result reason codes).

## Relationship to `ControlledUniverseExportResult`

The adapter's sole required input is `ControlledUniverseExportResult` from `hunter.controlled_universe_export_adapter`. The mapping is:

| Source field | Target field | Notes |
|---|---|---|
| `report_id` | `report_id` | Preserved for audit. |
| `generated_at` | `generated_at` | Used for staleness checks. |
| `whitelist` | `whitelist`, `pairlist` | Filtered, normalized, deduplicated, and sorted. |
| `blacklist` | `blacklist` | Filtered, normalized, deduplicated, and sorted. |
| `per_pair_summary` | `per_pair_summary` | Preserved and sorted by pair. |
| `research_only` | Safety gate | Must be `True`; otherwise fail-closed. |
| `human_approval_required` | Safety gate | Must be `True`; otherwise fail-closed. |
| `reason_codes` | Included in result reason codes | Adapter-specific codes added. |
| `safety_flags` | `safety_flags` | Preserved and augmented. |
| `metadata` | `metadata` | Preserved. |

## Reuse Boundaries for Existing Contracts

The adapter must review and reuse existing public contracts where appropriate:

- `freqtrade_bridge` (MVP-5):
  - Reuse `FreqtradeBridgeMode` and `FreqtradeBridgeState` only for enum classification in metadata or strategy-contract input.
  - Do not depend on `FreqtradeBridgeContext`, `FreqtradeBridgeConfig`, or `FreqtradeBridgeInputRefs` as inputs; they describe bridge state, not universe consumption.
  - Do not import any non-public internals.
- `strategy_contract` (MVP-6):
  - Reuse `StrategyContractMode` and `StrategyContractState` only for enum classification in the strategy-contract input representation.
  - Reuse the safety-flag field names (`dry_run`, `live_trading_enabled`, etc.) for consistency when building `strategy_contract_input`.
  - Do not depend on `StrategyContext` as an input; it describes strategy execution state, not universe consumption.
  - Do not import any non-public internals.
- `freqtrade_shell` (MVP-9):
  - The adapter is independent of the dry-run strategy shell. It does not emit signal metadata or dataframe annotations.
  - No reuse is required; the shell is a downstream consumer, not a dependency.

No existing contract may be silently redefined. If a new concept is needed (e.g., a whitelist/blacklist pairlist for universe consumption), it must be defined in the adapter's own models and clearly distinguished from the bridge/contract contexts.

## Whitelist / Blacklist Mapping Rules

1. **Input validation:** If `export_result` is `None`, return empty whitelist and blacklist with `MISSING_EXPORT_INPUT`.
2. **Safety gate:** If `export_result.research_only` is `False` or `export_result.human_approval_required` is `False`, return empty whitelist with `BLOCKED_EXPORT_INPUT`.
3. **Blocked export reason codes:** If any of `export_result.reason_codes` contains `BLOCKED_EXPORT`, `MISSING_REPORT_INPUT`, or `INVALID_UNIVERSE_REPORT`, return empty whitelist with `BLOCKED_EXPORT_INPUT`.
4. **Staleness:** If `now - export_result.generated_at > stale_export_threshold_seconds`, return empty whitelist with `STALE_EXPORT_INPUT`.
5. **Pair normalization:** Convert each pair string from the upstream format to the configured `pair_format`.
   - The adapter infers the upstream format from the first valid pair string, or from `metadata["pair_format"]` if the upstream export recorded it.
   - `"base/quote"` format is `"BASE/QUOTE"` (uppercase base and quote, separated by a slash).
   - `"base_quote"` format is `"BASE_QUOTE"` (uppercase base and quote, separated by an underscore).
   - If conversion fails because the input is not a valid pair string, add `INVALID_PAIR_FORMAT` and exclude the pair from the whitelist and blacklist.
6. **Deduplication:** Remove duplicate pairs within the whitelist and blacklist, preserving first-occurrence order before sorting. If any duplicates are removed, add a `DUPLICATE_PAIR` reason code.
7. **Contradiction handling:** Any pair in both whitelist and blacklist is removed from the whitelist and added to the blacklist with a `CONTRADICTORY_PAIR` reason code.
8. **Sorting:** Final whitelist and blacklist are sorted lexicographically.
9. **Pairlist:** The pairlist fragment is derived from the final whitelist.
10. **Strategy-contract input:** Contains `whitelist`, `blacklist`, `mode`, `safety_flags`, and `metadata`. Mode is derived using the rules in the next section.

## Pair Format and Mode Mapping

### Pair Format

The adapter does not guess the format of the upstream `ControlledUniverseExportResult`. It reads the upstream `pair_format` metadata if present, or defaults to the format already in the pair strings. It then converts each pair to the configured `FreqtradeUniverseAdapterConfig.pair_format`. If a pair cannot be parsed, the adapter emits `INVALID_PAIR_FORMAT` and excludes that pair from both whitelist and blacklist.

### Mode Mapping

The `strategy_contract_input.mode` is derived from the per-pair classifications of the **included** pairs:

- If all included pairs have classification `LONG_RESEARCH`, mode is `"LONG_RESEARCH_ONLY"`.
- If all included pairs have classification `SHORT_RESEARCH`, mode is `"SHORT_RESEARCH_ONLY"`.
- If included pairs contain both `LONG_RESEARCH` and `SHORT_RESEARCH`, mode is `"BLOCK_ALL"` (fail-closed on mixed directions).
- If no pairs are included, mode is `"BLOCK_ALL"`.
- For `NEUTRAL_RESEARCH` or `WATCHLIST_RESEARCH`, treat as neither long nor short and default to `"BLOCK_ALL"` unless the set is purely long or short after excluding these.

Mode values are strings matching the enum names of `StrategyContractMode` and `FreqtradeBridgeMode` (`LONG_RESEARCH_ONLY`, `SHORT_RESEARCH_ONLY`, `BLOCK_ALL`). No mode is a trading signal; it is a research classification only.

## Duplicate and Contradiction Handling

- Duplicates are deterministic: the first occurrence is kept, subsequent occurrences are removed, and a `DUPLICATE_PAIR` reason code is added if any duplicates are removed.
- Contradictions are fail-closed on the specific pair: blacklist always wins. A `CONTRADICTORY_PAIR` reason code is added, and the pair is removed from the whitelist and added to the blacklist.
- If a contradiction exists, the adapter still produces a valid result with corrected lists. The result is not blocked as a whole unless the corrected whitelist becomes empty.

## Deterministic Artifact Schemas

### JSON Packet (`latest_universe.json`)

```json
{
  "report_id": "<export-report-id>",
  "generated_at": "<iso-timestamp>",
  "version": "0.55.0-dev",
  "research_only": true,
  "human_approval_required": true,
  "whitelist": ["BTC/USDT", "ETH/USDT"],
  "blacklist": ["DOGE/USDT"],
  "pairlist": {"method": "StaticPairList", "pairs": ["BTC/USDT", "ETH/USDT"]},
  "strategy_contract_input": {
    "whitelist": ["BTC/USDT", "ETH/USDT"],
    "blacklist": ["DOGE/USDT"],
    "mode": "LONG_RESEARCH_ONLY",
    "safety_flags": {"dry_run": true, "live_trading_enabled": false},
    "metadata": {"source": "ControlledUniverseExportResult"}
  },
  "reason_codes": ["EXPORT_RESEARCH_ONLY", "EXPORT_HUMAN_APPROVAL_REQUIRED"],
  "safety_flags": {"research_only": true, "human_approval_required": true},
  "metadata": {"source": "ControlledUniverseExportResult"}
}
```

### Pairlist Fragment (`pairlist.json`)

```json
{
  "method": "StaticPairList",
  "pairs": ["BTC/USDT", "ETH/USDT"]
}
```

### Strategy-Contract Input (`strategy_contract_input.json`)

```json
{
  "whitelist": ["BTC/USDT", "ETH/USDT"],
  "blacklist": ["DOGE/USDT"],
  "mode": "LONG_RESEARCH_ONLY",
  "safety_flags": {"dry_run": true, "live_trading_enabled": false},
  "metadata": {"source": "ControlledUniverseExportResult"}
}
```

### Markdown Summary (`latest_universe.md`)

- Header with version and timestamp.
- Safety notice: research-only, human approval required, no Freqtrade runtime connection, no automatic config mutation.
- Whitelist section.
- Blacklist section.
- Per-pair summary table.
- Reason codes and safety flags.
- Artifact paths.

## Fail-Closed and Stale-Input Behavior

- Any missing, invalid, blocked, or unsafe export input produces an empty whitelist, empty pairlist, and a fail-closed reason code.
- Stale input is determined by comparing `export_result.generated_at` (timezone-aware) against current UTC time using `stale_export_threshold_seconds` (default 300 seconds).
- The adapter never falls back to a non-empty whitelist when safety checks fail.
- The blacklist is always emitted, even when the whitelist is empty, to preserve auditability.

## Public API

The adapter must expose the following public symbols via `hunter.freqtrade_universe_adapter`:

- `FREQTRADE_UNIVERSE_ADAPTER_VERSION: str = "0.55.0-dev"`
- `MISSING_EXPORT_INPUT`, `BLOCKED_EXPORT_INPUT`, `EMPTY_WHITELIST`, `INVALID_PAIR_FORMAT`, `DUPLICATE_PAIR`, `CONTRADICTORY_PAIR`, `EXPORT_RESEARCH_ONLY`, `EXPORT_HUMAN_APPROVAL_REQUIRED`, `NO_FREQTRADE_RUNTIME_CONNECTION`, `NO_AUTOMATIC_CONFIG_MUTATION`, `STALE_EXPORT_INPUT`
- `FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES: frozenset[str]`
- `FreqtradeUniverseAdapterConfig` (frozen dataclass)
- `FreqtradeUniverseAdapterResult` (frozen dataclass)
- `FreqtradeUniverseAdapterError` (exception)
- `build_freqtrade_universe_adapter_result(export_result, config)`
- `freqtrade_universe_adapter_result_to_dict(result)`
- `freqtrade_universe_adapter_result_to_json_text(result)`
- `freqtrade_universe_adapter_result_to_markdown_text(result)`
- `atomic_write_json_freqtrade_universe_adapter_result(result, path)`
- `atomic_write_markdown_freqtrade_universe_adapter_result(result, path)`
- `write_freqtrade_universe_adapter_result(result, output_dir, config)` — if `output_dir` is provided, it overrides `config.output_dir`; otherwise `config.output_dir` and `config.markdown_output_dir` are used.

## Test Strategy

### Model Tests

- `FreqtradeUniverseAdapterConfig` validation: required fields, defaults, invalid values.
- `FreqtradeUniverseAdapterResult` validation: required fields, frozen behavior, safety flags, reason codes.
- `FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES` completeness.

### Engine Tests

- Missing export result returns empty whitelist with `MISSING_EXPORT_INPUT`.
- Export result with `research_only=False` or `human_approval_required=False` returns empty whitelist with `BLOCKED_EXPORT_INPUT`.
- Blocked export result returns empty whitelist with `BLOCKED_EXPORT_INPUT`.
- Empty whitelist returns `EMPTY_WHITELIST`.
- Stale export result returns empty whitelist with `STALE_EXPORT_INPUT`.
- Pair normalization for `base/quote` and `base_quote` formats.
- Duplicate pairs are deduplicated deterministically.
- Duplicate pairs emit a `DUPLICATE_PAIR` reason code.
- Contradictory pairs are removed from whitelist and added to blacklist with `CONTRADICTORY_PAIR`.
- Deterministic output for identical inputs.
- Safety flags are always research-only and human-approval-required.

### Writer Tests

- `freqtrade_universe_adapter_result_to_dict` returns a JSON-safe, deterministic dict with sorted keys.
- `freqtrade_universe_adapter_result_to_json_text` returns valid JSON.
- `freqtrade_universe_adapter_result_to_markdown_text` contains the safety notice and artifact paths.
- Atomic writers use temp-file + rename and do not leave partial files.
- `write_freqtrade_universe_adapter_result` writes all four artifacts when enabled.

### Integration Tests

- End-to-end flow: `ControlledUniverseExportResult` → `FreqtradeUniverseAdapterResult` → written artifacts.
- The JSON packet can be parsed and contains the expected keys.
- The Markdown packet contains the safety notice and artifact paths.
- The pairlist fragment matches the whitelist.
- No file reads occur outside the writer modules.
- No Freqtrade imports occur anywhere in the package.

## Implementation Steps and Milestones

### Step 1 — Models and Public API

- Create `src/hunter/freqtrade_universe_adapter/models.py`.
  - Define `FREQTRADE_UNIVERSE_ADAPTER_VERSION`.
  - Define reason codes and `FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES` frozenset.
  - Define `FreqtradeUniverseAdapterConfig` frozen dataclass with validation.
  - Define `FreqtradeUniverseAdapterResult` frozen dataclass with validation.
  - Define `FreqtradeUniverseAdapterError` exception.
- Create `src/hunter/freqtrade_universe_adapter/__init__.py` with public API exports.
- Create `tests/test_freqtrade_universe_adapter/__init__.py`.
- Create `tests/test_freqtrade_universe_adapter/test_models.py`.

### Step 2 — Engine

- Create `src/hunter/freqtrade_universe_adapter/engine.py`.
  - Implement `build_freqtrade_universe_adapter_result(export_result, config)`.
  - Implement helpers for validation, staleness, normalization, deduplication, contradiction handling, and fail-closed mapping.
- Create `tests/test_freqtrade_universe_adapter/test_engine.py`.

### Step 3 — Writer

- Create `src/hunter/freqtrade_universe_adapter/writer.py`.
  - Implement `freqtrade_universe_adapter_result_to_dict`.
  - Implement `freqtrade_universe_adapter_result_to_json_text`.
  - Implement `freqtrade_universe_adapter_result_to_markdown_text`.
  - Implement `atomic_write_json_freqtrade_universe_adapter_result`.
  - Implement `atomic_write_markdown_freqtrade_universe_adapter_result`.
  - Implement `write_freqtrade_universe_adapter_result`.
- Update `__init__.py` with writer exports.
- Create `tests/test_freqtrade_universe_adapter/test_writer.py`.

### Step 4 — Integration Tests and Public API Review

- Create `tests/test_freqtrade_universe_adapter/test_integration.py`.
- Review public API exports for completeness.
- Run focused tests and full suite.

### Step 5 — Finalization

- Bump `FREQTRADE_UNIVERSE_ADAPTER_VERSION` to `0.55.0-dev`.
- Bump `pyproject.toml` and `src/hunter/__init__.py` to `0.55.0-dev`.
- Update `CHANGELOG.md`, `docs/handoff/CURRENT_STATE.md`, `docs/MVP_INDEX.md`, `AGENTS.md`, `tasks/active.md`, and `tasks/agent-log.md`.
- Apply local tag `v0.55.0-dev` (no push).

## Task Graph

```
Step 1: Models + Public API
    |
    v
Step 2: Engine
    |
    v
Step 3: Writer
    |
    v
Step 4: Integration Tests + API Review
    |
    v
Step 5: Finalization
```

Each step depends on the previous one. No step may be skipped. Implementation is deferred until after human approval of this SPEC.

## Non-Goals

- This MVP does not validate the selected universe with historical backtests.
- This MVP does not produce a Freqtrade-ready strategy or live trading configuration.
- This MVP does not modify the behavior of existing engines; it only consumes their outputs.
- This MVP does not introduce a scheduler, daemon, server, REST API, or database.
- This MVP does not claim production readiness, trading readiness, or suitability for any execution purpose.
- This MVP does not read from `data/` or `reports/` except through the writer modules during file writes.
- This MVP does not create a second or alternate specification; implementation follows this SPEC.
- This MVP does not stage, commit, tag, push, or configure remotes.

## Safety and Boundaries

- **No Freqtrade runtime integration:** The adapter does not import or call Freqtrade runtime, strategy, or configuration code.
- **No automatic config mutation:** The adapter writes local artifacts; it does not modify Freqtrade config files, strategy files, or any existing project config.
- **No exchange or network access:** The adapter does not call networks, APIs, exchanges, or external services.
- **No API, server, database, scheduler, or live trading behavior:** The adapter is a single-call local function. No background services, servers, daemons, schedulers, or trading execution are started or invoked.
- **No actionable trading signals:** The output is a research-only adapter packet with explicit safety flags. It is not an order, signal, or execution instruction.
- **No readiness/approval/suitability claims:** All outputs are labeled as research-only and requiring human approval.
- **No data/ or reports/ inspection:** The adapter never reads, traverses, or validates the contents of `data/` or `reports/`. It only writes artifacts through deterministic writer functions.
- **No implementation yet:** This SPEC is for planning only. Implementation begins after human approval.
- **No staging, commit, tag, push, or remote configuration:** This SPEC does not trigger any source-control or deployment operations.

## Version

Target: `0.55.0-dev`

`FREQTRADE_UNIVERSE_ADAPTER_VERSION`: `0.55.0-dev`
