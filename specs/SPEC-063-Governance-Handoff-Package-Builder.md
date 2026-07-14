# SPEC-063 — Governance Handoff Package Builder

**Status:** Approved  
**MVP:** MVP-62  
**Version target:** `v0.62.0-dev`  
**Upstream dependencies:** MVP-59 `ResearchDecisionGateReport`, MVP-60 `HumanReviewRecord`, MVP-61 `GovernanceDecisionSummary`

## Background

MVP-61 provides `GovernanceDecisionSummary`, but downstream research teams still need one portable, immutable, and verifiable handoff package.

```text
GovernanceDecisionSummary
ResearchDecisionGateReport
Latest Accepted HumanReviewRecord
        ↓
Governance Handoff Package Builder
        ↓
ResearchGovernanceHandoffPackage
```

The package carries governance status, gate decision/fingerprint, latest accepted review, reason codes, provenance, source versions, safety declarations, a manifest, and deterministic JSON/Markdown artifacts.

The package never authorizes execution, production deployment, or trading.

## Requirements

### Must Have

- required `GovernanceDecisionSummary`
- required `ResearchDecisionGateReport`
- latest accepted `HumanReviewRecord` required by default
- governance, gate, and review fingerprints mutually consistent
- governance status limited to `READY_FOR_RESEARCH_HANDOFF`, `REVIEW_REQUIRED`, or `BLOCKED`
- package may still be produced for non-ready states
- `BLOCKED` → `handoff_allowed=False`
- `REVIEW_REQUIRED` → `handoff_allowed=False`
- `READY_FOR_RESEARCH_HANDOFF` allows research handoff only
- immutable package
- deterministic package fingerprint
- preserve source fingerprints, versions, and reason codes
- visible latest accepted review
- mandatory research-only declaration
- identical inputs/config/time produce identical model, fingerprint, JSON, and Markdown
- invalid or contradictory provenance fails closed
- no runtime trading behavior

### Should Have

- manifest includes version, package fingerprint, timestamp, source fingerprints, source versions, filenames, and safety flags
- no caller mutation
- injected `built_at`
- canonical JSON SHA-256
- semantic parity between JSON and Markdown
- atomic writer
- no silent overwrite with different content
- explicit handoff notice

### Won’t Have

- digital signatures or archive format
- database, API, UI, notifications, scheduler, external upload
- Freqtrade strategy/config output
- orders, signals, automatic execution, live trading, or production approval

### Handoff Rule

```text
READY_FOR_RESEARCH_HANDOFF
+ valid provenance
+ no blocking reasons
+ no review-required reasons
→ handoff_allowed = true

otherwise
→ handoff_allowed = false
```

## Method

### Package Layout

```text
src/hunter/governance_handoff/
├── __init__.py
├── models.py
├── validator.py
├── policy.py
├── engine.py
└── writer.py

tests/test_governance_handoff/
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
class GovernanceHandoffConfig:
    require_latest_accepted_review: bool
    output_dir: Path
    report_output_dir: Path
    json_filename: str
    markdown_filename: str
```

Default: `require_latest_accepted_review=True`.

```python
@dataclass(frozen=True)
class HandoffSourceReference:
    source_name: str
    source_version: str
    fingerprint: str
    accepted: bool
    reason_codes: tuple[str, ...]
```

```python
@dataclass(frozen=True)
class ResearchGovernanceHandoffManifest:
    package_version: str
    package_fingerprint: str
    built_at: datetime
    governance_fingerprint: str
    gate_fingerprint: str
    review_record_fingerprint: str | None
    source_versions: Mapping[str, str]
    artifact_filenames: Mapping[str, str]
    safety_flags: Mapping[str, bool]
```

```python
@dataclass(frozen=True)
class ResearchGovernanceHandoffPackage:
    version: str
    package_fingerprint: str
    built_at: datetime
    governance_status: Literal[
        "READY_FOR_RESEARCH_HANDOFF",
        "REVIEW_REQUIRED",
        "BLOCKED",
    ]
    handoff_allowed: bool
    governance_source: HandoffSourceReference
    gate_source: HandoffSourceReference
    review_source: HandoffSourceReference | None
    blocking_reason_codes: tuple[str, ...]
    review_reason_codes: tuple[str, ...]
    manifest: ResearchGovernanceHandoffManifest
    research_only: bool
    execution_approval_granted: bool
    production_approval_granted: bool
    metadata: Mapping[str, object]
```

All public models are immutable. Mapping fields use defensive copies.

### Public Engine

```python
build_research_governance_handoff_package(
    governance_summary: GovernanceDecisionSummary | None,
    gate_report: ResearchDecisionGateReport | None,
    latest_accepted_review: HumanReviewRecord | None,
    config: GovernanceHandoffConfig,
    *,
    built_at: datetime,
) -> ResearchGovernanceHandoffPackage
```

No file access, hidden clock, caller mutation, or real Freqtrade import.

### Provenance Validation

Validate:

```text
governance_summary.gate_decision_fingerprint
    == gate_report.decision_fingerprint
```

```text
governance_summary.review_summary.latest_accepted_record_fingerprint
    == latest_accepted_review.record_fingerprint
```

Also require:

- valid governance/gate/review fingerprints
- review `accepted=True`
- review `human_approval_recorded=True`
- review `execution_approval_granted=False`
- review source decision fingerprint matches gate fingerprint
- non-empty source versions
- timezone-aware timestamps
- no contradictory safety flags

### Safety Invariants

```python
{
    "research_only": True,
    "execution_approval_granted": False,
    "production_approval_granted": False,
    "live_trading_allowed": False,
    "automatic_execution_allowed": False,
}
```

Any contradiction yields `UNSAFE_HANDOFF_FLAG` and `handoff_allowed=False`.

### Reason Codes

Blocking:

```text
MISSING_GOVERNANCE_SUMMARY
MISSING_GATE_REPORT
MISSING_LATEST_ACCEPTED_REVIEW
INVALID_GOVERNANCE_SUMMARY
INVALID_GATE_REPORT
INVALID_REVIEW_RECORD
GOVERNANCE_FINGERPRINT_MISMATCH
GATE_FINGERPRINT_MISMATCH
REVIEW_FINGERPRINT_MISMATCH
SOURCE_VERSION_MISMATCH
CONTRADICTORY_HANDOFF_STATE
UNSAFE_HANDOFF_FLAG
INVALID_TIMESTAMP
```

Review-required:

```text
GOVERNANCE_REVIEW_REQUIRED
INCOMPLETE_PROVENANCE
UNKNOWN_NON_BLOCKING_FIELD
MISSING_OPTIONAL_METADATA
```

Ready marker:

```text
HANDOFF_PACKAGE_READY
```

### Package Fingerprint

Use canonical JSON with sorted keys, compact separators, UTF-8, and lowercase SHA-256 `hexdigest()`.

Include governance status, handoff flag, source fingerprints, reason lists, versions, filenames, safety flags, injected `built_at`, and canonical config.

### Artifacts

```text
data/governance_handoff/latest_handoff_package.json
reports/governance_handoff/latest_handoff_package.md
```

Artifacts must include:

```text
Handoff allowed does not authorize execution or production deployment.
```

### Writer API

```python
governance_handoff_package_to_dict(...)
governance_handoff_package_to_json_text(...)
governance_handoff_package_to_markdown_text(...)
write_governance_handoff_package(...)
```

Rules:

- deterministic JSON/Markdown
- atomic temp-file + `os.replace`
- temp cleanup
- configurable paths
- same content may be rewritten
- different content must not silently overwrite existing artifact
- no source artifact reads

### Determinism

Identical governance summary, gate report, latest review, config, and `built_at` must produce identical source references, reasons, handoff flag, manifest, fingerprint, JSON, and Markdown.

## Implementation Notes

- All dataclasses are frozen.
- Config validates booleans, paths, and filenames at construction time.
- Validator is pure: no file/network access, no clock reads.
- Policy functions are pure and deterministic.
- Engine builds source references from upstream objects without mutation.
- Writer uses atomic file writes with temp-file cleanup.
- `built_at` must be timezone-aware.
- Canonical safety flags are constant; upstream safety flags only influence decisions, they do not replace the canonical flags in the package.

## Gathering Results

Acceptance requires correct provenance validation, fail-closed behavior, deterministic fingerprint and artifacts, collision handling, safety invariants, focused/full tests passing, project version `0.62.0-dev`, local annotated tag `v0.62.0-dev`, and no push.
