# SPEC-051-Research-Audit-Remediation-Handoff-Packet

## Background

MVP-49 (`SPEC-050`) introduced the `Research Audit Health Remediation Bridge`
at `src/hunter/research_audit_health_remediation/`. It consumes a caller-provided
MVP-48 `HealthReport` and produces deterministic `RemediationBacklogItem`
entries together with a `RemediationBridgeReport` summarizing the mapping.

MVP-50 needs a deterministic handoff-packet generator that consumes the MVP-49
bridge output (or a caller-provided sequence of `RemediationBacklogItem`
summaries) and produces a human-review handoff packet. The packet is a
research-only, audit-only artifact: it groups backlog items, adds summary
metadata and counts, and emits JSON and Markdown renderings suitable for a human
reviewer. It does not perform remediation, emit actions, or claim any approval.

## Requirements

### Must Have (M)

- **M1:** A new package `src/hunter/research_audit_remediation_handoff/`
  implementing the handoff packet generator.
- **M2:** Caller-provided in-memory input only: a `RemediationBridgeReport` from
  `research_audit_health_remediation` or a sequence of `RemediationBacklogItem`
  summaries, plus a handoff configuration. No filesystem scans, no path
  traversal, no opening of artifact/report references, and no validation of
  referenced paths.
- **M3:** A deterministic `HandoffPacket` model containing grouped items,
  summary counts, metadata, and a packet-level state (`OK` / `DEGRADED` /
  `BLOCKED` derived from item severities).
- **M4:** Deterministic grouping of items by `(severity, priority, item_type,
  reason_code, family)` where `family` is read from item metadata (opaque string).
- **M5:** Summary counts per grouping: total items, blocking count, advisory
  count, info count, and a per-group item list ordered deterministically by
  `(priority, severity, item_id)`.
- **M6:** Packet-level metadata: `packet_id`, `source_report_id`, `generated_at`,
  `project_version`, `total_items`, `total_blocking`, `total_advisory`,
  `total_info`, `group_count`, `owner`, `reviewer`, and `notes`.
- **M7:** Stable, deterministic `packet_id` derived from the source report ID
  and sorted deterministic item fields (e.g. `sha256` of a normalized tuple).
- **M8:** Deterministic JSON dict/string serialization via
  `handoff_packet_to_dict(...)` and `handoff_packet_to_json(...)`.
- **M9:** Deterministic Markdown summary via
  `handoff_packet_to_markdown(...)` including a research-only/audit-only safety
  notice and an explicit statement that the packet is not an approval, trading
  signal, recommendation, or production-readiness claim.
- **M10:** Optional atomic file writers `atomic_write_json_handoff_packet` and
  `atomic_write_markdown_handoff_packet` writing to
  `data/research_audit_remediation_handoff/` and
  `reports/research_audit_remediation_handoff/`; writers never read from `data/`
  or `reports/`.
- **M11:** Forbidden-term scanning on all output strings; fail-closed and set a
  safety flag if leakage is detected, mirroring the behavior of the MVP-49
  bridge.

### Should Have (S)

- **S1:** Configurable grouping keys in `HandoffPacketConfig` (e.g. allow
  grouping by `severity` only, by `priority` only, or by a custom tuple).
- **S2:** Configurable exclusion of `INFO` items from the handoff packet.
- **S3:** Summary tables in Markdown: per-group counts, per-priority counts,
  and per-reason-code counts.
- **S4:** Data-quality counters for input items, grouped items, dropped info
  items, and safety-flagged items.
- **S5:** Integration tests using caller-built in-memory `RemediationBridgeReport`
  samples only; no test may read actual artifact files from `data/` or `reports/`.

### Could Have (C)

- **C1:** Optional `status_by_group` table in Markdown for human triage.
- **C2:** Optional propagation of `owner` and `reviewer` from the source report
  metadata or caller config.
- **C3:** Optional filtering by severity or priority ranges.

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
- **W11:** Consuming actual artifact files referenced inside item metadata.

## Method

### Architecture Overview

The handoff packet generator is a single-stage local function:

1. **Input**: Caller provides a `RemediationBridgeReport` (or a tuple of
   `RemediationBacklogItem` summaries) and a `HandoffPacketConfig`.
2. **Engine**: `build_research_audit_remediation_handoff_packet(...)` validates
   the input, groups items, computes summary counts, derives a packet state, and
   produces a `HandoffPacket`.
3. **Writer**: Single-argument writer functions serialize the packet to
   deterministic JSON, Markdown strings, and optional atomic files.

No stage opens, follows, traverses, validates, fetches, or executes any path or
reference string. References remain opaque.

### Proposed Package

- `src/hunter/research_audit_remediation_handoff/` — implementation package.
- `tests/test_research_audit_remediation_handoff/` — test package.

### Data Model

All new models are frozen dataclasses with `__slots__`. Strings are normalized
and stripped. Reference/path strings are opaque.

```python
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Optional, Tuple

from hunter.remediation_backlog.models import RemediationBacklogItem
from hunter.research_audit_health_remediation.models import RemediationBridgeReport


@dataclass(frozen=True, slots=True)
class HandoffPacketConfig:
    owner: Optional[str] = None
    reviewer: Optional[str] = None
    notes: str = ""
    exclude_info: bool = False
    grouping_keys: Tuple[str, ...] = ("severity", "priority", "item_type", "reason_code")
    include_markdown_safety_notice: bool = True

    def __post_init__(self):
        # Defaults are applied if caller provides an empty mapping.
        pass


@dataclass(frozen=True, slots=True)
class HandoffPacketGroup:
    group_id: str
    severity: str
    priority: str
    item_type: str
    reason_code: str
    family: str
    item_count: int
    blocking_count: int
    advisory_count: int
    info_count: int
    items: Tuple[RemediationBacklogItem, ...]


@dataclass(frozen=True, slots=True)
class HandoffPacketDataQuality:
    input_items: int = 0
    produced_items: int = 0
    dropped_info: int = 0
    grouped_items: int = 0
    safety_flagged_items: int = 0
    group_count: int = 0


@dataclass(frozen=True, slots=True)
class HandoffPacketSafetyFlags:
    has_forbidden_terms: bool = False
    references_opaque: bool = True
    no_executable_actions: bool = True
    no_trading_instructions: bool = True
    no_approval_claims: bool = True


@dataclass(frozen=True, slots=True)
class HandoffPacket:
    packet_id: str
    source_report_id: str
    generated_at: str  # ISO-8601
    project_version: str
    owner: Optional[str]
    reviewer: Optional[str]
    notes: str
    total_items: int
    total_blocking: int
    total_advisory: int
    total_info: int
    group_count: int
    state: str  # "ok" | "degraded" | "blocked"
    groups: Tuple[HandoffPacketGroup, ...]
    data_quality: HandoffPacketDataQuality
    safety_flags: HandoffPacketSafetyFlags


class HandoffPacketError(Exception):
    pass
```

### Packet State Derivation

- `state = "blocked"` if any item has severity `BLOCKING`.
- `state = "degraded"` if no `BLOCKING` items but at least one `ADVISORY` item.
- `state = "ok"` if only `INFO` items or no items remain.

### Grouping

Default grouping is by `(severity, priority, item_type, reason_code)` plus the
`family` value extracted from each item's `metadata["family"]` (or
`metadata.get("family", "unknown")`). The group identifier `group_id` is a
stable hash of the sorted grouping tuple.

Items within each group are sorted by `(priority, severity, item_id)` using
the enum ordering: `P0 < P1 < P2 < P3 < NONE`, and `BLOCKING > ADVISORY > INFO`.

### Summary Counts

The packet-level counts are computed from the grouped items after filtering:

- `total_items`: sum of items across all groups.
- `total_blocking`: count of items with `severity == BLOCKING`.
- `total_advisory`: count of items with `severity == ADVISORY`.
- `total_info`: count of items with `severity == INFO`.
- `group_count`: number of distinct groups.

### Deterministic Output Ordering

Groups are emitted in lexicographic order of their `group_id`. Items within each
group are emitted in sorted order. This ensures `dict` and Markdown outputs are
byte-for-byte reproducible for identical inputs.

### Forbidden-Term Scanning

All generated titles, descriptions, notes, and metadata values are scanned
against the same forbidden-term set used by the remediation backlog. If leakage
is detected:

1. Set `safety_flags.has_forbidden_terms = True`.
2. Increment `data_quality.safety_flagged_items` by one.
3. Do not add a new item; instead, annotate the packet with a safety warning in
the Markdown output.

## Implementation Milestones

### Step 1: Models and Engine

- Create `src/hunter/research_audit_remediation_handoff/__init__.py` with public
  exports.
- Create `src/hunter/research_audit_remediation_handoff/models.py` with
  `HandoffPacketConfig`, `HandoffPacketGroup`, `HandoffPacketDataQuality`,
  `HandoffPacketSafetyFlags`, `HandoffPacket`, and `HandoffPacketError`.
- Create `src/hunter/research_audit_remediation_handoff/engine.py` with
  `build_research_audit_remediation_handoff_packet(...)` and grouping/counting
  helpers.
- Add model tests in `tests/test_research_audit_remediation_handoff/test_models.py`.
- Add engine tests in `tests/test_research_audit_remediation_handoff/test_engine.py`.

### Step 2: Writer

- Create `src/hunter/research_audit_remediation_handoff/writer.py` with
  deterministic `handoff_packet_to_dict`, `handoff_packet_to_json`, and
  `handoff_packet_to_markdown` functions.
- Add optional atomic file writers that never read from `data/` or `reports/`.
- Add writer tests in
  `tests/test_research_audit_remediation_handoff/test_writer.py`.

### Step 3: Integration Tests

- Create `tests/test_research_audit_remediation_handoff/test_integration.py`
  with end-to-end flows using caller-built in-memory `RemediationBridgeReport`
  samples only.
- Verify grouping, deterministic ordering, Markdown safety notice, and opaque
  references.

### Step 4: Metadata and Documentation Finalization

- Update `VERSION` to `0.50.0-dev`.
- Update `pyproject.toml` version.
- Update `src/hunter/__init__.py` version.
- Add MVP-50 entry to `CHANGELOG.md`.
- Update `docs/handoff/CURRENT_STATE.md`, `tasks/active.md`, `AGENTS.md`, and
  `docs/MVP_INDEX.md`.
- No source code changes beyond the handoff packet package.
- Stop before tag (tag is applied by human or later task).

## Acceptance Criteria

- The handoff packet package is importable and exposes
  `build_research_audit_remediation_handoff_packet`.
- A `RemediationBridgeReport` with one `BLOCKING` item produces a packet with
  `state == "blocked"`, `total_blocking == 1`, and exactly one group containing
  that item.
- A `RemediationBridgeReport` with duplicate items produces deterministic groups
  and counts.
- The Markdown output contains the explicit research-only/audit-only safety
  notice and no production-readiness or trading-readiness claims.
- All tests pass; the full suite remains at 7680+ tests passing, 1 skipped
  using the default `pytest -q` mode.
- No test reads from `data/` or `reports/`.
- No runtime/trading/API/Freqtrade/server/database/scheduler behavior is
  introduced.
- No production/trading readiness, approval, certification, recommendation,
  or suitability claims appear in output or documentation.

## Safety Boundaries

This SPEC is explicitly scoped to local, human-audit-only handoff packet
generation. It does not:

- Create or execute trading signals.
- Create or execute orders, positions, or portfolio actions.
- Connect to exchanges, Freqtrade, Binance, APIs, networks, or live data.
- Start servers, daemons, schedulers, databases, Web UIs, or dashboards.
- Read, validate, traverse, or execute artifact refs, paths, or files.
- Claim that any packet, item, or project state is production-ready,
  trading-ready, approved, certified, recommended, or suitable.
- Emit automated remediation actions, shell commands, code patches, or
  infrastructure changes.

All refs and paths remain opaque strings. `data/` and `reports/` are not
inspected during engine operation or tests.
