# SPEC-060 — Research Decision Gate Engine

## Background

MVP-58 produced an immutable, fail-closed `ValidatedPortfolioRiskContext`. MVP-59 combines portfolio risk, controlled-universe state, and optional strategy-contract context into one deterministic, research-only decision report.

Inputs:
- `ValidatedPortfolioRiskContext`
- `ControlledUniverseReport`
- optional strategy contract input

Output:
- `ResearchDecisionGateReport`

Allowed decisions:
- `GO`
- `NO_GO`
- `NEEDS_REVIEW`

`GO` means only that research artifacts are internally consistent and safe enough for human review. It never means execution approval, production readiness, or authorization to trade.

```text
ValidatedPortfolioRiskContext
ControlledUniverseReport
Optional Strategy Contract Input
        ↓
Research Decision Gate Engine
        ↓
ResearchDecisionGateReport
        ↓
Human Research Review
```

## Requirements

### Must Have

- risk context and universe report are required
- strategy contract is optional and policy-controlled
- decision is exactly `GO`, `NO_GO`, or `NEEDS_REVIEW`
- missing, rejected, blocked, unsafe, stale, or contradictory required inputs produce `NO_GO`
- non-blocking ambiguity may produce `NEEDS_REVIEW`
- `GO` only when all required checks pass
- deterministic blocking and review reason codes
- canonical safety flags
- `research_only=True`
- `human_approval_required=True`
- immutable report
- deterministic report, fingerprint, JSON, and Markdown
- deterministic JSON and Markdown audit artifacts
- no Freqtrade runtime/config mutation
- no order, signal, position, leverage, entry, exit, or live behavior
- `GO` never described as execution approval

### Should Have

- preserve upstream fingerprints
- generate a decision fingerprint
- retain source summaries
- configurable freshness thresholds
- strategy-contract policies:
  - `ALLOW_WITH_REVIEW`
  - `REQUIRE`
  - `IGNORE`
- classify blocking vs review reasons
- deterministic handling of unknown non-blocking fields
- no caller mutation
- fixed priority:
  - blocking → `NO_GO`
  - review only → `NEEDS_REVIEW`
  - none → `GO`

### Won’t Have

- order/signal generation
- Freqtrade strategy/config output
- position sizing, exchange precision, backtest, optimizer
- historical price, volatility, correlation, covariance
- API, network, database, scheduler, live trading
- human-approval bypass

### Defaults

- `strategy_contract_policy = ALLOW_WITH_REVIEW`
- freshness thresholds align with upstream
- missing optional contract under default policy → `NEEDS_REVIEW`

## Method

### Package Layout

```text
src/hunter/research_decision_gate/
├── __init__.py
├── models.py
├── validator.py
├── policy.py
├── engine.py
└── writer.py

tests/test_research_decision_gate/
├── __init__.py
├── test_models.py
├── test_validator.py
├── test_policy.py
├── test_engine.py
├── test_writer.py
└── test_integration.py
```

### Core Models

```python
@dataclass(frozen=True)
class ResearchDecisionGateConfig:
    strategy_contract_policy: Literal[
        "ALLOW_WITH_REVIEW",
        "REQUIRE",
        "IGNORE",
    ]
    max_universe_age_seconds: int
    max_risk_context_age_seconds: int
    allowed_future_skew_seconds: int
    output_dir: Path
    report_output_dir: Path
    json_filename: str
    markdown_filename: str
```

```python
@dataclass(frozen=True)
class DecisionSourceSummary:
    source_name: str
    present: bool
    accepted: bool
    fresh: bool
    fingerprint: str | None
    reason_codes: tuple[str, ...]
```

```python
@dataclass(frozen=True)
class ResearchDecisionGateReport:
    version: str
    decision: Literal["GO", "NO_GO", "NEEDS_REVIEW"]
    decision_fingerprint: str
    evaluated_at: datetime
    risk_context_summary: DecisionSourceSummary
    universe_summary: DecisionSourceSummary
    strategy_contract_summary: DecisionSourceSummary
    blocking_reason_codes: tuple[str, ...]
    review_reason_codes: tuple[str, ...]
    safety_flags: Mapping[str, bool]
    research_only: bool
    human_approval_required: bool
    metadata: Mapping[str, object]
```

### Input Contract

```python
build_research_decision_gate_report(
    risk_context: ValidatedPortfolioRiskContext | None,
    universe_report: ControlledUniverseReport | None,
    config: ResearchDecisionGateConfig,
    *,
    strategy_contract_input: Mapping[str, object] | None = None,
    evaluated_at: datetime,
) -> ResearchDecisionGateReport
```

The engine does not read/write files, read the clock internally, mutate caller input, or import real Freqtrade runtime modules.

### Decision Priority

```text
blocking reasons → NO_GO
no blocking + review reasons → NEEDS_REVIEW
no blocking or review reasons → GO
```

### Mandatory Blocking Conditions

- missing/rejected/blocked risk context
- closed risk gate
- missing/rejected/blocked universe report
- stale required input
- invalid/future timestamp
- `research_only=False`
- `human_approval_required=False`
- missing required fingerprint
- contradictory safety flags
- `REQUIRE` policy with missing contract
- invalid/unsafe contract
- contradictory required inputs

### Review Conditions

- `ALLOW_WITH_REVIEW` with missing contract
- non-blocking mode or scope mismatch
- incomplete provenance
- unknown non-blocking field
- upstream review-required state

### Strategy Contract Policies

- `REQUIRE`: missing/invalid/unsafe contract → `NO_GO`
- `ALLOW_WITH_REVIEW`: missing contract → `NEEDS_REVIEW`; invalid/unsafe → `NO_GO`
- `IGNORE`: contract does not affect decision

### Canonical Safety Flags

```python
{
    "research_only": True,
    "human_approval_required": True,
    "automatic_execution_allowed": False,
    "runtime_config_mutation_allowed": False,
    "live_trading_allowed": False,
}
```

### Reason Codes

Blocking:
```text
MISSING_RISK_CONTEXT
REJECTED_RISK_CONTEXT
RISK_GATE_CLOSED
BLOCK_ALL_RISK_CONTEXT
MISSING_UNIVERSE_REPORT
REJECTED_UNIVERSE_REPORT
STALE_RISK_CONTEXT
STALE_UNIVERSE_REPORT
INVALID_TIMESTAMP
UNSAFE_RESEARCH_FLAG
MISSING_HUMAN_APPROVAL_FLAG
MISSING_REQUIRED_FINGERPRINT
MISSING_STRATEGY_CONTRACT
INVALID_STRATEGY_CONTRACT
UNSAFE_STRATEGY_CONTRACT
CONTRADICTORY_SAFETY_FLAGS
CONTRADICTORY_INPUTS
```

Review:
```text
OPTIONAL_STRATEGY_CONTRACT_MISSING
STRATEGY_CONTRACT_MODE_MISMATCH
STRATEGY_CONTRACT_SCOPE_MISMATCH
INCOMPLETE_PROVENANCE
UNKNOWN_NON_BLOCKING_FIELD
UPSTREAM_REVIEW_REQUIRED
```

Decision:
```text
DECISION_GO
DECISION_NO_GO
DECISION_NEEDS_REVIEW
```

### Fingerprint

Use canonical JSON with sorted keys and bare lowercase SHA-256 `hexdigest()`. Include upstream fingerprints, decision, blocking/review reasons, canonical safety flags, evaluated time, and canonical config.

### Audit Artifacts

```text
data/research_decision_gate/latest_decision.json
reports/research_decision_gate/latest_decision.md
```

Artifacts include decision, fingerprint, evaluated time, source summaries, blocking/review reasons, safety flags, policy, freshness thresholds, research-only notice, human approval requirement, explicit statement that `GO` is not execution approval, and artifact paths.

### Determinism

Identical inputs, config, optional contract, and injected time must produce identical decision, summaries, reason ordering, safety flags, fingerprint, JSON, and Markdown.

## Implementation Notes

- All dataclasses are frozen.
- Config validates thresholds and policy at construction time.
- Validator is pure: no file/network access, no clock reads.
- Policy functions are pure and deterministic.
- Engine builds source summaries from upstream objects without mutation.
- Writer uses atomic file writes with temp-file cleanup.
- `evaluated_at` must be timezone-aware.
- Canonical safety flags are constant; upstream safety flags only influence decisions, they do not replace the canonical flags in the report.
