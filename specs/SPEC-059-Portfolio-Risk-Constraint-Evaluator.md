# SPEC-059-Portfolio-Risk-Constraint-Evaluator

## Background

MVP-57 produced a deterministic, constrained `PortfolioResearchContext`. MVP-58 validates its static portfolio structure and exposure risks before downstream research use.

Flow:

```text
PortfolioResearchContext
        ↓
Portfolio Risk Constraint Evaluator
        ↓
ValidatedPortfolioRiskContext
        ↓
Downstream Research Components
```

MVP-58 validates total exposure, asset weights, cluster exposure, concentration, minimum asset count, and diversification. It is fail-closed and research-only. It does not use historical prices, volatility, correlation, covariance, drawdown, or trading runtime behavior.

## Requirements

### Must Have

- accept only valid `PortfolioResearchContext`
- missing, rejected, `BLOCK_ALL`, or empty allocations must fail closed
- recalculate and validate total exposure
- validate min/max asset weights
- recalculate and validate cluster exposure
- validate allocation sum vs recorded `total_exposure`
- reject duplicate pairs and invalid Decimal weights
- enforce minimum asset count
- enforce maximum single-asset weight
- calculate concentration metrics
- produce immutable deterministic `ValidatedPortfolioRiskContext`
- every blocking result:
  - `accepted = false`
  - `risk_gate_open = false`
  - `mode = BLOCK_ALL`
  - `validated_allocations = ()`
- write deterministic JSON and Markdown audit artifacts
- no Freqtrade runtime/config mutation
- no trading or market-risk runtime behavior

### Should Have

- HHI
- effective asset count
- largest asset weight
- largest cluster exposure
- configurable diversification thresholds
- deterministic reason codes
- preserve source portfolio fingerprint
- generate risk evaluation fingerprint
- never mutate input/config
- byte-identical outputs for identical input/config/evaluation time

### Could Have

- sector-level concentration alerts
- allocation vs target tracking
- research-note metadata

### Won’t Have

- price history
- volatility/correlation/covariance
- drawdown
- VaR/CVaR
- stress testing
- backtest/order sizing/exchange precision/leverage
- Freqtrade strategy/config
- network/database/scheduler/live trading

### Defaults

- `min_asset_count = 2`
- `max_single_asset_weight = 0.35`
- `max_total_exposure = 1.00`
- `max_cluster_exposure = 0.50`
- `max_hhi = 0.30`
- normalized-weight HHI
- `effective_asset_count = 1 / HHI`

## Method

### Package Layout

```text
src/hunter/portfolio_risk_evaluator/
├── __init__.py
├── models.py
├── validator.py
├── metrics.py
├── engine.py
└── writer.py

```

```text
tests/test_portfolio_risk_evaluator/
├── __init__.py
├── test_models.py
├── test_validator.py
├── test_metrics.py
├── test_engine.py
├── test_writer.py
└── test_integration.py
```

### Core Models

```python
@dataclass(frozen=True)
class PortfolioRiskConfig:
    min_asset_count: int
    min_asset_weight: Decimal
    max_single_asset_weight: Decimal
    max_total_exposure: Decimal
    max_cluster_exposure: Decimal
    max_hhi: Decimal
    exposure_tolerance: Decimal
    output_dir: Path
    report_output_dir: Path
    json_filename: str
    markdown_filename: str
```

```python
@dataclass(frozen=True)
class PortfolioRiskMetrics:
    asset_count: int
    total_exposure: Decimal
    largest_asset_weight: Decimal
    largest_cluster_exposure: Decimal
    hhi: Decimal
    effective_asset_count: Decimal
    cluster_exposure: Mapping[str, Decimal]
```

```python
@dataclass(frozen=True)
class ValidatedPortfolioRiskContext:
    version: str
    source_portfolio_fingerprint: str
    risk_evaluation_fingerprint: str
    evaluated_at: datetime
    accepted: bool
    risk_gate_open: bool
    mode: Literal["LONG", "SHORT", "BLOCK_ALL"]
    validated_allocations: tuple[PortfolioAllocation, ...]
    metrics: PortfolioRiskMetrics
    reason_codes: tuple[str, ...]
    research_only: bool
    human_approval_required: bool
    metadata: Mapping[str, object]
```

### Public Engine

```python
build_validated_portfolio_risk_context(
    portfolio_context: PortfolioResearchContext | None,
    config: PortfolioRiskConfig,
    *,
    evaluated_at: datetime,
) -> ValidatedPortfolioRiskContext
```

### Structural Validation

Validate:
- context presence/acceptance/mode
- non-empty allocations
- canonical `BASE/QUOTE`
- no duplicate pairs
- positive finite Decimal weights
- blacklist conflict
- allocation sum vs recorded total within tolerance
- recalculated vs recorded cluster exposure
- config consistency

No file reads/writes, hidden clocks, or mutation.

### Metrics

Use only `Decimal`.

```python
RISK_QUANTUM = Decimal("0.00000001")
```

Rounding: `ROUND_DOWN`.

Calculate:
- total exposure
- cluster exposure
- largest asset weight
- largest cluster exposure
- normalized-weight HHI
- effective asset count

Zero exposure:
- `hhi = 0`
- `effective_asset_count = 0`

### Risk Gate

Blocking:
- asset count below minimum
- asset below minimum weight
- asset above maximum weight
- total exposure exceeded
- cluster exposure exceeded
- HHI exceeded
- rejected/contradictory source
- exposure mismatch

Blocking output:

```text
accepted = false
risk_gate_open = false
mode = BLOCK_ALL
validated_allocations = ()
```

Metrics and reason codes remain available for audit.

### Reason Codes

```text
MISSING_CONTEXT
REJECTED_PORTFOLIO_CONTEXT
BLOCK_ALL_CONTEXT
EMPTY_ALLOCATIONS
INVALID_CONFIG
INVALID_ALLOCATION
INVALID_WEIGHT
DUPLICATE_PAIR
BLACKLIST_CONFLICT
TOTAL_EXPOSURE_MISMATCH
TOTAL_EXPOSURE_EXCEEDED
ASSET_COUNT_BELOW_MINIMUM
ASSET_WEIGHT_BELOW_MINIMUM
ASSET_WEIGHT_EXCEEDED
CLUSTER_EXPOSURE_MISMATCH
CLUSTER_EXPOSURE_EXCEEDED
HHI_EXCEEDED
CONTRADICTORY_CONTEXT
RISK_ACCEPTED
```

### Fingerprint

Use canonical JSON with sorted keys and SHA-256 bare lowercase `hexdigest()`. Include source portfolio fingerprint, evaluated time, metrics, reason codes, and canonical config.

### Audit Artifacts

```text
data/portfolio_risk/latest_risk_validation.json
reports/portfolio_risk/latest_risk_validation.md
```

Include:
- source/risk fingerprints
- evaluated time
- accepted/risk-gate status
- mode
- allocation count
- total exposure
- largest asset/cluster exposure
- HHI/effective asset count
- cluster exposure
- configured limits
- reason codes
- research-only notice
- human approval requirement
- artifact paths

### Determinism

Identical portfolio context, config, and injected `evaluated_at` must produce identical metrics, reason ordering, result, fingerprint, JSON, and Markdown.

## Implementation

### Step 1 — SPEC-059 and Foundation

Create:
- `specs/SPEC-059-Portfolio-Risk-Constraint-Evaluator.md`
- package/test skeleton
- version constant `0.58.0-dev`
- reason-code constants
- frozen dataclasses
- config validation
- immutable metadata/mapping behavior
- public API scaffold
- model tests

### Step 2 — Structural Validator

Implement pure structural validation and tests. No file reads, writes, or hidden clocks.

### Step 3 — Risk Metrics

Implement deterministic Decimal metrics and tests:

```python
recalculate_total_exposure(...)
recalculate_cluster_exposure(...)
calculate_hhi(...)
calculate_effective_asset_count(...)
calculate_largest_asset_weight(...)
calculate_largest_cluster_exposure(...)
build_portfolio_risk_metrics(...)
```

### Step 4 — Risk Evaluation Engine

Implement engine pipeline, limit checks, fingerprint, immutable result, and fail-closed tests.

### Step 5 — Audit Writer

Implement dict serializer, deterministic JSON/Markdown, atomic writes, temp cleanup, configurable artifact paths, and writer tests.

### Step 6 — Integration

Create integration tests covering accepted portfolio, missing/rejected/blocked/empty context, duplicate/invalid/blacklisted allocations, total/cluster mismatch and limits, asset count and weight limits, HHI exceeded, deterministic metrics/fingerprint/writes, Decimal precision, public API, no Freqtrade imports, no mutation, no file reads in validator/metrics/engine.

### Step 7 — Finalization

- project version → `0.58.0-dev`
- `PORTFOLIO_RISK_EVALUATOR_VERSION` → `0.58.0-dev`
- docs/memory updates
- focused/full tests
- local annotated tag `v0.58.0-dev`
- post-tag context-sync commit
- no push

## Milestones

1. SPEC and foundation
2. Structural validation
3. Risk metrics
4. Risk evaluation engine
5. Audit artifacts
6. Integration
7. Finalization and local tag

## Success Criteria

- accepted context produces risk-accepted context
- blocked/rejected/missing/empty input produces empty validated allocations
- all asset, total and cluster limits remain respected
- blacklisted pairs never receive allocation
- invalid/duplicate pairs fail closed
- identical input/config/time produce identical fingerprints and artifacts
- no Freqtrade/runtime behavior
- no config/caller mutation
- focused/full tests pass
- no blocking input produces accepted risk context
