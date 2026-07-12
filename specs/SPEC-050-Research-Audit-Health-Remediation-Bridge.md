# SPEC-050-Research-Audit-Health-Remediation-Bridge

## Background

MVP-48 (`SPEC-049`) introduced the `Research Audit Aggregate Health Report`
engine at `src/hunter/research_audit_health/`. It consumes caller-provided,
in-memory artifact summaries and produces a deterministic, severity-weighted
aggregate `HealthReport` with per-family rollups and findings. The report is
human-audit-only and does not perform remediation, emit actions, or claim any
approval.

MVP-38 (`SPEC-038`) introduced the `Local Research Remediation Backlog Planner`
at `src/hunter/remediation_backlog/`. It converts audit findings, check
failures, and issue summaries into a human-review backlog with deterministic
priorities, item states, and dependencies.

MVP-49 needs a deterministic bridge between the two: a component that takes an
MVP-48 `HealthReport` and converts its `HealthFinding` objects into structured
`RemediationBacklogItem` entries suitable for the MVP-38 backlog planner. The
bridge is purely local and audit-only; it does not perform remediation, does
not create executable actions, and does not claim that any backlog item is
approved, deployable, production-ready, or trading-ready. Its purpose is to help
a human auditor move from "the report says X is unhealthy" to "here is a
tracked backlog item for a human to review".

## Requirements

### Must Have (M)

- **M1:** A new package `src/hunter/research_audit_health_remediation/`
  implementing the bridge.
- **M2:** Caller-provided in-memory input only: a `HealthReport` (from
  `research_audit_health`) plus a bridge configuration. No filesystem scans,
  no path traversal, no opening of artifact/report references, and no
  validation of referenced paths.
- **M3:** Deterministic mapping from each `HealthFinding` in the input report
  to zero or more `RemediationBacklogItem` objects.
- **M4:** Deterministic mapping from `HealthSeverity` to
  `RemediationBacklogSeverity` and `RemediationBacklogPriority`.
- **M5:** Deterministic mapping from `HealthReasonCode` to
  `RemediationBacklogItemType` and `RemediationBacklogReasonCode` where a
  direct semantic equivalent exists; otherwise map to
  `RemediationBacklogItemType.MANUAL_REVIEW` with reason code
  `RemediationBacklogReasonCode.CONSISTENCY_DEGRADED`.
- **M6:** Generate stable, deterministic `item_id` values for produced backlog
  items by combining the source `finding_id`, family, and artifact_id into a
  normalized identifier (e.g. `sha256` of sorted deterministic fields).
- **M7:** Detect duplicate items produced from the same `HealthFinding` and
  collapse them deterministically.
- **M8:** Detect forbidden-term leakage in generated item titles, descriptions,
  and metadata; fail-closed and produce a single safety-flagged backlog item
  if leakage is detected.
- **M9:** Produce a `RemediationBridgeReport` containing the mapped items, a
  data-quality summary, and safety flags.
- **M10:** Provide JSON/CSV/Markdown writer outputs with explicit
  research-only/audit-only safety notice in Markdown.
- **M11:** Output paths remain under `data/research_audit_health_remediation/`
  and `reports/research_audit_health_remediation/`; the writer never reads
  from `data/` or `reports/`.

### Should Have (S)

- **S1:** Configurable severity-to-priority override map in the bridge config.
- **S2:** Configurable reason-code-to-item-type override map in the bridge
  config.
- **S3:** Optional deduplication by `subject_id` derived from
  `(family, artifact_id, reason_code, severity)`.
- **S4:** Data-quality counters for input findings, produced items, dropped
  findings, duplicates, and safety-flagged items.
- **S5:** Integration tests using caller-built in-memory `HealthReport` sample
  only; no test may read actual artifact files from `data/` or `reports/`.

### Could Have (C)

- **C1:** Support for generating dependencies between backlog items that share
  a family or reason code (e.g. `RELATED_TO`).
- **C2:** Optional `owner` and `reviewer` fields propagated from caller-provided
  config.
- **C3:** Optional filtering to exclude `INFO` findings from backlog output.

### Will Not Have (W)

- **W1:** Live trading, order generation, or execution semantics.
- **W2:** Exchange/Binance/API/network access.
- **W3:** Freqtrade strategy/import/runtime integration.
- **W4:** Leverage/shorting execution.
- **W5:** Web UI, dashboard, server, database, scheduler, or daemon.
- **W6:** Actionable buy/sell/hold signals or recommendations.
- **W7:** Approval, certification, production-readiness, or trading-readiness
  claims.
- **W8:** Automated remediation actions, shell commands, code patches, or
  infrastructure changes.
- **W9:** Executable remediation plans in any output.
- **W10:** Reading, validating, or traversing artifact refs or paths.

## Method

### Architecture Overview

The bridge is a two-stage local pipeline:

1. **Input**: Caller provides a `HealthReport` from
   `research_audit_health.evaluate_research_audit_health(...)` and a
   `RemediationBridgeConfig`.
2. **Engine**: `build_health_remediation_bridge_report(input)` validates the
   report, maps each `HealthFinding` to a `RemediationBacklogItem`, deduplicates,
   checks for forbidden terms, and produces a `RemediationBridgeReport`.
3. **Writer**: Single-argument writer functions serialize the report to
   deterministic JSON, CSV, and Markdown artifacts.

No stage opens, follows, traverses, validates, fetches, or executes any path or
reference string. References remain opaque.

### Proposed Package

- `src/hunter/research_audit_health_remediation/` — implementation package.
- `tests/test_research_audit_health_remediation/` — test package.

### Data Model

All new models are frozen dataclasses with `__slots__`. Strings are normalized
to lowercase and stripped. Reference/path strings are opaque.

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from hunter.remediation_backlog.models import (
    RemediationBacklogItem,
    RemediationBacklogItemState,
    RemediationBacklogItemType,
    RemediationBacklogPriority,
    RemediationBacklogReasonCode,
    RemediationBacklogSeverity,
    RemediationBacklogSafetyFlags,
)
from hunter.research_audit_health.models import HealthFinding, HealthReport


@dataclass(frozen=True, slots=True)
class RemediationBridgeConfig:
    strict: bool = False
    owner: Optional[str] = None
    reviewer: Optional[str] = None
    exclude_info: bool = False
    severity_to_priority: Mapping[str, str] = field(default_factory=dict)
    reason_to_item_type: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self):
        # Defaults are applied if caller provides an empty mapping.
        pass


@dataclass(frozen=True, slots=True)
class RemediationBridgeDataQuality:
    input_findings: int = 0
    produced_items: int = 0
    dropped_info: int = 0
    duplicates_collapsed: int = 0
    safety_flagged_items: int = 0


@dataclass(frozen=True, slots=True)
class RemediationBridgeReport:
    report_id: str
    source_report_id: str
    generated_at: str  # ISO-8601
    items: Tuple[RemediationBacklogItem, ...]
    data_quality: RemediationBridgeDataQuality
    safety_flags: RemediationBacklogSafetyFlags


class RemediationBridgeError(Exception):
    pass
```

### Default Severity-to-Priority Mapping

| `HealthSeverity` | `RemediationBacklogSeverity` | `RemediationBacklogPriority` |
|------------------|------------------------------|------------------------------|
| `BLOCKING`       | `BLOCKING`                   | `P0`                         |
| `WARNING`        | `ADVISORY`                   | `P1`                         |
| `INFO`           | `INFO`                       | `P3` (or dropped if configured) |

The caller may override these defaults through
`RemediationBridgeConfig.severity_to_priority`.

### Default Reason-Code-to-Item-Type Mapping

| `HealthReasonCode`                  | `RemediationBacklogItemType`        | `RemediationBacklogReasonCode`     |
|-------------------------------------|---------------------------------------|--------------------------------------|
| `FAMILY_HAS_BLOCKING_FINDINGS`      | `MANUAL_REVIEW`                       | `CONSISTENCY_DEGRADED`               |
| `FAMILY_HAS_WARNING_FINDINGS`       | `MANUAL_REVIEW`                       | `CONSISTENCY_DEGRADED`               |
| `FAMILY_MISSING`                      | `MISSING_REF`                         | `MISSING_REQUIRED_SOURCE`            |
| `FAMILY_STATE_BLOCKED`              | `MANUAL_REVIEW`                       | `SAFETY_BLOCKED`                     |
| `FAMILY_STATE_DEGRADED`             | `MANUAL_REVIEW`                       | `CONSISTENCY_DEGRADED`               |
| `AGGREGATE_SCORE_DEGRADED`          | `MANUAL_REVIEW`                       | `CONSISTENCY_DEGRADED`               |
| `AGGREGATE_SCORE_BLOCKED`           | `MANUAL_REVIEW`                       | `SAFETY_BLOCKED`                     |
| `MISSING_DATA_QUALITY`              | `MISSING_REF`                         | `MISSING_REQUIRED_SOURCE`            |
| `REASON_CODE_MISMATCH`              | `MANUAL_REVIEW`                       | `CONSISTENCY_DEGRADED`               |
| `FORBIDDEN_PHRASE_LEAKAGE`          | `UNSAFE_CONTENT`                    | `FORBIDDEN_TERM_PRESENT`             |
| `UNSAFE_INPUT`                      | `UNSAFE_CONTENT`                    | `UNSAFE_CONTENT`                     |
| `INSUFFICIENT_DATA`                 | `MANUAL_REVIEW`                       | `CONSISTENCY_DEGRADED`               |
| `OK`                                | (no item produced)                    | (no item produced)                   |
| any other code                      | `MANUAL_REVIEW`                       | `CONSISTENCY_DEGRADED`               |

The caller may override these defaults through
`RemediationBridgeConfig.reason_to_item_type`.

### Item Derivation

For each `HealthFinding` in `HealthReport.findings`:

1. Skip if `reason_code == "OK"`.
2. Skip if `severity == INFO` and `config.exclude_info` is `True`.
3. Derive `item_type` and `reason_code` from the default mapping or caller
   overrides.
4. Derive `severity` and `priority` from the default mapping or caller
   overrides.
5. Set `item_state = RemediationBacklogItemState.OPEN`.
6. Set `source_id = finding.family` (or `finding.artifact_id` if non-empty).
7. Set `finding_id = finding.finding_id`.
8. Set `title` from a deterministic template:
   `"[{reason_code}] {family}/{artifact_id}: {short_message}"` where
   `short_message` is the first 60 characters of `finding.message`.
9. Set `description = finding.message`.
10. Set `generated_at` from the source report timestamp or current UTC time if
    none is provided.
11. Set `metadata` from `finding.evidence` plus `family` and `artifact_id`.
12. Compute a deterministic `item_id` as a stable hash of the sorted tuple:
    `(report_id, finding_id, family, artifact_id, reason_code, severity)`.

### Deduplication

After derivation, collapse items that share the same `item_id`. The
`duplicates_collapsed` counter is incremented for each collapsed duplicate. In
case of conflict, the `BLOCKING` severity wins; if severities are equal, the
first item in sorted order wins.

### Forbidden-Term Scanning

All generated titles, descriptions, and metadata values are scanned against
the same `FORBIDDEN_REMEDIATION_BACKLOG_TERMS` set used by
`remediation_backlog`. If any forbidden phrase is found, the bridge:

1. Sets `has_forbidden_terms = True` on the report safety flags.
2. Produces a single safety-flagged backlog item of type
   `RemediationBacklogItemType.UNSAFE_CONTENT` with reason code
   `RemediationBacklogReasonCode.FORBIDDEN_TERM_PRESENT`.
3. Increments `data_quality.safety_flagged_items` by one.

### Safety Flags

The report carries a `RemediationBacklogSafetyFlags` instance with all
positive invariants (`no_executable_actions`, `no_trading_instructions`,
`no_approval_claims`, `no_automated_remediation`, `references_opaque`) set to
`True` and all negative flags set to `False` by default. If forbidden-term
leakage is detected, `has_forbidden_terms` becomes `True`.

## Implementation Milestones

### Step 1: Models and Engine

- Create `src/hunter/research_audit_health_remediation/__init__.py` with public
  exports.
- Create `src/hunter/research_audit_health_remediation/models.py` with
  `RemediationBridgeConfig`, `RemediationBridgeDataQuality`,
  `RemediationBridgeReport`, and `RemediationBridgeError`.
- Create `src/hunter/research_audit_health_remediation/engine.py` with
  `build_health_remediation_bridge_report(...)` and deterministic mapping
  functions.
- Create `src/hunter/research_audit_health_remediation/mapping.py` with default
  severity-to-priority and reason-code-to-item-type tables.
- Add model tests in `tests/test_research_audit_health_remediation/test_models.py`.
- Add engine tests in `tests/test_research_audit_health_remediation/test_engine.py`.

### Step 2: Writer

- Create `src/hunter/research_audit_health_remediation/writer.py` with
  deterministic JSON, CSV, and Markdown serialization, atomic writes, and
  forbidden-phrase output guard.
- Add writer tests in
  `tests/test_research_audit_health_remediation/test_writer.py`.

### Step 3: Integration Tests

- Create `tests/test_research_audit_health_remediation/test_integration.py` with
  end-to-end flows using caller-built in-memory `HealthReport` instances only.
- Verify safety boundaries, opaque refs, forbidden-term handling, deduplication,
  and deterministic output.

### Step 4: Metadata and Documentation Finalization

- Update `VERSION` to `0.49.0-dev`.
- Update `pyproject.toml` version.
- Add MVP-49 entry to `CHANGELOG.md`.
- Update `docs/handoff/CURRENT_STATE.md`, `tasks/active.md`, and
  `docs/MVP_INDEX.md`.
- No source code changes beyond the bridge package.
- Stop before tag (tag is applied by human or later task).

## Acceptance Criteria

- The bridge package is importable and exposes `build_health_remediation_bridge_report`.
- A `HealthReport` with one `BLOCKING` finding produces at least one
  `RemediationBacklogItem` with `BLOCKING` severity and `P0` priority.
- A `HealthReport` with duplicate findings produces no duplicate backlog items.
- All tests pass; the full suite remains at 7620+ tests passing, 1 skipped
  using `pytest --import-mode=importlib`.
- No test reads from `data/` or `reports/`.
- No runtime/trading/API/Freqtrade/server/database/scheduler behavior is
  introduced.
- No production/trading readiness, approval, certification, recommendation,
  or suitability claims appear in output or documentation.

## Safety Boundaries

This SPEC is explicitly scoped to local, human-audit-only remediation backlog
generation. It does not:

- Create or execute trading signals.
- Create or execute orders, positions, or portfolio actions.
- Connect to exchanges, Freqtrade, Binance, APIs, networks, or live data.
- Start servers, daemons, schedulers, databases, Web UIs, or dashboards.
- Read, validate, traverse, or execute artifact refs, paths, or files.
- Claim that any item, report, or project state is production-ready,
  trading-ready, approved, certified, recommended, or suitable.
- Emit automated remediation actions, shell commands, code patches, or
  infrastructure changes.

All refs and paths remain opaque strings. `data/` and `reports/` are not
inspected during engine operation or tests.
