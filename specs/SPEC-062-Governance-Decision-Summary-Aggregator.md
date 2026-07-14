# SPEC-062 — Governance Decision Summary Aggregator

**Status:** Approved  
**MVP:** MVP-61  
**Version target:** `v0.61.0-dev`  
**Upstream dependencies:** MVP-59 `ResearchDecisionGateReport`, MVP-60 `HumanReviewRecord`

## Background

MVP-59 provides a deterministic, research-only `ResearchDecisionGateReport` with `GO`, `NO_GO`, and `NEEDS_REVIEW`. MVP-60 records human review outcomes as immutable, append-only `HumanReviewRecord` entries. MVP-61 combines the gate result, the review chain, and chain verification state into one deterministic governance summary.

```text
ResearchDecisionGateReport
        +
HumanReviewRecord Chain
        +
Chain Verification Result
        ↓
Governance Decision Summary Aggregator
        ↓
GovernanceDecisionSummary
```

The result is research-only and never authorizes execution, production use, or trading.

## Requirements

### Must Have

- required `ResearchDecisionGateReport`
- required review-record sequence; an empty sequence is valid input but yields `REVIEW_REQUIRED`
- revalidate review-chain integrity
- only accepted human review records affect governance approval
- deterministically select latest accepted review
- output exactly one of:
  - `READY_FOR_RESEARCH_HANDOFF`
  - `REVIEW_REQUIRED`
  - `BLOCKED`
- `NO_GO` always yields `BLOCKED`
- broken, tampered, duplicate, contradictory, or unsafe review state yields `BLOCKED`
- open `REQUEST_CHANGES` yields at least `REVIEW_REQUIRED`
- no accepted review yields `REVIEW_REQUIRED`
- `READY_FOR_RESEARCH_HANDOFF` requires:
  - gate `GO`
  - valid chain
  - accepted review present
  - latest accepted review `APPROVE_FOR_RESEARCH`
  - no open change request
  - no blocking or review-required reason
- immutable summary
- deterministic blocking/review reason lists
- preserve gate and review fingerprints
- deterministic summary, fingerprint, JSON, and Markdown
- `research_only=True`
- `human_review_required=True`
- `execution_approval_granted=False`
- no Freqtrade runtime/config mutation
- no order, signal, position, leverage, entry, exit, or live behavior

### Decision Priority

```text
blocking reason exists
→ BLOCKED

no blocking reason, review-required reason exists
→ REVIEW_REQUIRED

no reasons
→ READY_FOR_RESEARCH_HANDOFF
```

### Blocking Reason Codes

```text
MISSING_GATE_REPORT
INVALID_GATE_REPORT
GATE_DECISION_NO_GO
MISSING_REVIEW_CHAIN
BROKEN_REVIEW_CHAIN
TAMPERED_REVIEW_RECORD
DUPLICATE_REVIEW_RECORD
CONTRADICTORY_GOVERNANCE_STATE
MISSING_REQUIRED_FINGERPRINT
UNSAFE_GOVERNANCE_FLAG
INVALID_TIMESTAMP
```

### Review-Required Reason Codes

```text
NO_ACCEPTED_REVIEW
GATE_REVIEW_REQUIRED
OPEN_CHANGE_REQUEST
LATEST_REVIEW_REJECTED
LATEST_REVIEW_REQUESTS_CHANGES
INCOMPLETE_PROVENANCE
UNKNOWN_NON_BLOCKING_FIELD
```

### Ready Marker

```text
READY_FOR_RESEARCH_HANDOFF
```

## Method

### Package Layout

```text
src/hunter/governance_summary/
├── __init__.py
├── models.py
├── validator.py
├── policy.py
├── engine.py
└── writer.py

tests/test_governance_summary/
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
class GovernanceSummaryConfig:
    require_review_chain: bool
    output_dir: Path
    report_output_dir: Path
    json_filename: str
    markdown_filename: str
```

```python
@dataclass(frozen=True)
class GovernanceReviewSummary:
    total_records: int
    accepted_records: int
    rejected_attempts: int
    chain_valid: bool
    latest_accepted_record_fingerprint: str | None
    latest_reviewer_identity: str | None
    latest_reviewer_decision: str | None
    latest_review_created_at: datetime | None
    open_change_request_count: int
    source_decision_fingerprints: tuple[str, ...]
    reason_codes: tuple[str, ...]
```

```python
@dataclass(frozen=True)
class GovernanceDecisionSummary:
    version: str
    governance_status: Literal[
        "READY_FOR_RESEARCH_HANDOFF",
        "REVIEW_REQUIRED",
        "BLOCKED",
    ]
    governance_fingerprint: str
    evaluated_at: datetime
    gate_decision: Literal["GO", "NO_GO", "NEEDS_REVIEW"]
    gate_decision_fingerprint: str
    review_summary: GovernanceReviewSummary
    blocking_reason_codes: tuple[str, ...]
    review_reason_codes: tuple[str, ...]
    research_only: bool
    human_review_required: bool
    execution_approval_granted: bool
    metadata: Mapping[str, object]
```

### Public Engine

```python
build_governance_decision_summary(
    gate_report: ResearchDecisionGateReport | None,
    review_records: Sequence[HumanReviewRecord],
    config: GovernanceSummaryConfig,
    *,
    evaluated_at: datetime,
) -> GovernanceDecisionSummary
```

No file access, hidden clock, caller mutation, or real Freqtrade import.

### Latest Accepted Review

Sort accepted reviews by:

```python
(
    record.created_at,
    record.record_fingerprint,
)
```

The greatest value is the latest accepted review.

### Open Change Request Rule

- latest accepted `REQUEST_CHANGES` means open change request
- older requests are considered closed by a newer accepted `APPROVE_FOR_RESEARCH` or `REJECT`
- rejected audit attempts cannot close a request

### Safety Invariants

```python
{
    "research_only": True,
    "human_review_required": True,
    "execution_approval_granted": False,
}
```

Any contradictory source state yields `UNSAFE_GOVERNANCE_FLAG` and `BLOCKED`.

### Governance Fingerprint

Use canonical JSON with sorted keys and lowercase SHA-256 hexdigest. Include gate decision/fingerprint, ordered review fingerprints, latest accepted review fingerprint, status, reason lists, safety flags, config, and injected `evaluated_at`.

### Audit Artifacts

```text
data/governance_summary/latest_governance_summary.json
reports/governance_summary/latest_governance_summary.md
```

Artifacts must explicitly state:

```text
READY_FOR_RESEARCH_HANDOFF is not execution approval.
```

## Implementation Notes

- All dataclasses are frozen.
- Config validates paths and filenames at construction time.
- Validator is pure: no file/network access, no clock reads.
- Policy functions are pure and deterministic.
- Engine builds summaries from upstream objects without mutation.
- Writer uses atomic file writes with temp-file cleanup.
- `evaluated_at` must be timezone-aware.
- Canonical safety flags are constant; upstream safety flags only influence decisions, they do not replace the canonical flags in the summary.

## Gathering Results

Acceptance requires correct governance status matrix, no human-review override of `NO_GO`, deterministic latest-review selection, chain/tamper/duplicate detection, deterministic fingerprint and artifacts, `execution_approval_granted=False`, no runtime trading behavior, focused/full suites passing, and project version `0.61.0-dev`.
