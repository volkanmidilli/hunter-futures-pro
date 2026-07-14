# SPEC-061 — Human Review Decision Registry

**Status:** Approved  
**MVP:** MVP-60  
**Version target:** `v0.60.0-dev`  
**Upstream dependency:** MVP-59 `ResearchDecisionGateReport`

## Background

MVP-59 introduced a deterministic, research-only `ResearchDecisionGateReport` with `GO`, `NO_GO`, and `NEEDS_REVIEW`. MVP-60 records human review outcomes as immutable, append-only governance records.

```text
ResearchDecisionGateReport
        ↓
Human Review Decision Registry
        ↓
HumanReviewRecord
        ↓
Audit / Governance / Reporting
```

The registry records reviewer identity, decision, notes, timestamps, provenance, chain linkage, and record fingerprints. Human approval remains research-only and never authorizes execution.

## Requirements

### Must Have

- required `ResearchDecisionGateReport`
- required reviewer identity
- reviewer decision limited to `APPROVE_FOR_RESEARCH`, `REJECT`, or `REQUEST_CHANGES`
- immutable, append-only records
- previous records are never modified or deleted
- record includes source decision fingerprint, source decision, reviewer identity, reviewer decision, review note, created timestamp, previous record fingerprint, and record fingerprint
- all non-first accepted records link to the previous accepted record fingerprint
- deterministic chain verification
- invalid, contradictory, tampered, duplicate, or broken-chain inputs fail closed
- `GO` never grants automatic execution
- `APPROVE_FOR_RESEARCH` is research-only
- `NO_GO + APPROVE_FOR_RESEARCH` is rejected
- `NEEDS_REVIEW + APPROVE_FOR_RESEARCH` requires an adequate note
- deterministic JSON and Markdown artifacts
- no Freqtrade runtime/config mutation
- no order, signal, position, leverage, entry, exit, or live behavior

### Defaults

- `min_review_note_length = 12`
- first record uses `previous_record_fingerprint=None`
- duplicate key uses source fingerprint, canonical reviewer identity, reviewer decision, and normalized note
- `GO + APPROVE_FOR_RESEARCH` valid
- `NO_GO + APPROVE_FOR_RESEARCH` always rejected
- `NEEDS_REVIEW + APPROVE_FOR_RESEARCH` valid only with adequate explanation

## Method

### Package Layout

```text
src/hunter/human_review_registry/
├── __init__.py
├── models.py
├── validator.py
├── policy.py
├── engine.py
├── chain.py
└── writer.py

tests/test_human_review_registry/
├── __init__.py
├── test_models.py
├── test_validator.py
├── test_policy.py
├── test_chain.py
├── test_engine.py
├── test_writer.py
└── test_integration.py
```

### Core Models

```python
@dataclass(frozen=True)
class HumanReviewRegistryConfig:
    min_review_note_length: int
    output_dir: Path
    report_output_dir: Path
    json_filename: str
    markdown_filename: str
```

```python
@dataclass(frozen=True)
class HumanReviewInput:
    reviewer_identity: str
    reviewer_decision: Literal[
        "APPROVE_FOR_RESEARCH",
        "REJECT",
        "REQUEST_CHANGES",
    ]
    review_note: str
```

```python
@dataclass(frozen=True)
class HumanReviewRecord:
    version: str
    source_decision_fingerprint: str
    source_decision: Literal["GO", "NO_GO", "NEEDS_REVIEW"]
    reviewer_identity: str
    reviewer_decision: Literal[
        "APPROVE_FOR_RESEARCH",
        "REJECT",
        "REQUEST_CHANGES",
    ]
    review_note: str
    created_at: datetime
    previous_record_fingerprint: str | None
    record_fingerprint: str
    accepted: bool
    human_approval_recorded: bool
    execution_approval_granted: bool
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, object]
```

`execution_approval_granted` is always `False`.

### Public Engine

```python
build_human_review_record(
    decision_report: ResearchDecisionGateReport | None,
    review_input: HumanReviewInput | None,
    config: HumanReviewRegistryConfig,
    *,
    previous_record: HumanReviewRecord | None = None,
    existing_records: Sequence[HumanReviewRecord] = (),
    created_at: datetime,
) -> HumanReviewRecord
```

No file access, hidden clock, caller mutation, or real Freqtrade import.

### Review Policy

```text
GO + APPROVE_FOR_RESEARCH → accepted
GO + REJECT → accepted
GO + REQUEST_CHANGES → accepted
NO_GO + APPROVE_FOR_RESEARCH → rejected
NO_GO + REJECT → accepted
NO_GO + REQUEST_CHANGES → accepted
NEEDS_REVIEW + APPROVE_FOR_RESEARCH → accepted only with adequate note
NEEDS_REVIEW + REJECT → accepted
NEEDS_REVIEW + REQUEST_CHANGES → accepted only with adequate note
```

Every outcome preserves:

```text
execution_approval_granted = false
```

### Chain Rules

First accepted record:

```text
previous_record_fingerprint = null
```

Subsequent accepted record:

```text
previous_record_fingerprint = previous_record.record_fingerprint
```

Verification checks:

- first record previous fingerprint is `None`
- each next record points to the prior record
- each fingerprint recomputes identically
- no duplicate fingerprint
- deterministic order
- duplicate review key rejected

### Reason Codes

Blocking:

```text
MISSING_DECISION_REPORT
MISSING_REVIEW_INPUT
INVALID_REVIEWER_IDENTITY
INVALID_REVIEW_DECISION
REVIEW_NOTE_TOO_SHORT
MISSING_REQUIRED_REVIEW_NOTE
SOURCE_FINGERPRINT_MISSING
NO_GO_APPROVAL_FORBIDDEN
BROKEN_REVIEW_CHAIN
PREVIOUS_RECORD_MISMATCH
DUPLICATE_REVIEW
INVALID_TIMESTAMP
CONTRADICTORY_REVIEW
```

Accepted:

```text
REVIEW_APPROVED_FOR_RESEARCH
REVIEW_REJECTED
REVIEW_CHANGES_REQUESTED
```

### Audit Artifacts

Immutable:

```text
data/human_review_registry/<record_fingerprint>.json
reports/human_review_registry/<record_fingerprint>.md
```

Optional convenience copies:

```text
data/human_review_registry/latest_review.json
reports/human_review_registry/latest_review.md
```

Artifacts must state that human review does not authorize execution.

## Gathering Results

Acceptance requires correct policy behavior, chain integrity, duplicate/tamper detection, deterministic fingerprints and artifacts, `execution_approval_granted=False` in every record, no runtime trading behavior, no caller mutation, focused/full suites passing, and project version `0.60.0-dev`.
