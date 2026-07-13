# Changelog

All important project changes will be recorded in this file.

## Unreleased

No unreleased changes.

## MVP-52 — End-to-End Research Run Orchestrator v2 (Complete)

- SPEC-053 — End-to-End Research Run Orchestrator v2 approved.
  - `specs/SPEC-053-End-to-End-Research-Run-Orchestrator-v2.md` — approved for MVP-52 implementation.
  - Extends the research run orchestrator to support a `controlled_universe` step kind with deterministic dispatch, input resolution, and writer serialization.
  - Research-only output; not a trading signal, execution approval, strategy selector, or position-sizing tool.
- Steps 1–4 — End-to-End Research Run Orchestrator v2 models, dependency validator, engine dispatch, plan builder, writer serialization, integration tests, and finalization.
  - `src/hunter/run_orchestrator/models.py` — added `ResearchRunStepKind.CONTROLLED_UNIVERSE`, new reason codes (`MISSING_PORTFOLIO_CONTEXT`, `MISSING_EXECUTION_CONTEXT`, `STALE_INPUT`, `UPSTREAM_STEP_FAILED`, `UPSTREAM_STEP_BLOCKED`, `INVALID_PORTFOLIO_SUMMARY`, `EXECUTION_BLOCKED`, `MACRO_MODE_NONE`, `CONTRADICTORY_INPUT`, `INVALID_CONTROLLED_UNIVERSE_INPUT`), `ControlledUniverseRunInput`, `RunInputResolution` helper, extended `ResearchRunDataQuality` with controlled-universe counters, and aligned `RUN_ORCHESTRATOR_VERSION` to `0.52.0-dev`.
  - `src/hunter/run_orchestrator/engine.py` — added `validate_run_plan_dependencies`, `CONTROLLED_UNIVERSE` step dispatch in `_dispatch_step`, stale-input detection, deterministic blocking reason codes, and `build_coin_discovery_run_plan` convenience builder.
  - `src/hunter/run_orchestrator/writer.py` — serialized controlled-universe data quality counters (`controlled_universe_steps`, `controlled_universe_blocked`, `controlled_universe_universe_count`, `controlled_universe_watchlist_count`, `controlled_universe_blocked_count`) in JSON and Markdown output.
  - `tests/test_run_orchestrator/` — new model, engine, writer, plan-builder, and integration tests covering controlled-universe dispatch, input resolution, serialization, and end-to-end flows.
  - 142 run_orchestrator tests in `tests/test_run_orchestrator/`; full suite: 7868 tests passing, 1 skipped.
  - Version bumped to `0.52.0-dev` in `VERSION`, `pyproject.toml`, and `src/hunter/__init__.py`.
  - Tagged `v0.52.0-dev` at `0c65e20` (local-only; no push; MVP-53 not started).

## MVP-51 — Controlled Universe Bridge Engine (Complete, Tagged)

- SPEC-052 — Controlled Universe Bridge Engine approved.
  - `specs/SPEC-052-Controlled-Universe-Bridge-Engine.md` — approved for MVP-51 implementation.
  - Bridges macro execution context (MVP-4) and per-coin portfolio construction report (MVP-27) into a deterministic, fail-closed controlled universe.
  - Research-only output; not a trading signal, execution approval, strategy selector, or position-sizing tool.
- Steps 1–4 — Controlled Universe Bridge Engine models, engine, writer, integration tests, and finalization.
  - `src/hunter/controlled_universe/` package created with `models.py`, `engine.py`, `writer.py`, and `__init__.py`.
  - Frozen dataclasses: `ControlledUniverseConfig`, `ControlledUniverseItem`, `ControlledUniverseReport`, `ControlledUniverseSafetyFlags`, `ControlledUniverseDataQuality`.
  - Pure deterministic engine: `build_controlled_universe_report` with fail-closed gating for missing execution/portfolio context, execution state, allowed mode, data quality, portfolio summary, and duplicate pairs.
  - Deterministic writers: JSON/CSV/Markdown text serializers plus atomic file writers (`atomic_write_*`, `write_controlled_universe_report`).
  - Integration tests: end-to-end engine → writer flows, fail-closed serialization, and safety notices.
  - 81 controlled_universe tests in `tests/test_controlled_universe/`; full suite: 7812 tests passing, 1 skipped.
  - Version bumped to `0.51.0-dev` in `pyproject.toml`, `src/hunter/__init__.py`, and `CONTROLLED_UNIVERSE_VERSION`.
  - Tagged `v0.51.0-dev` at `a75de79`.

## MVP-50 — Research Audit Remediation Handoff Packet (Complete, Tagged)

**Version:** 0.49.0-dev → 0.50.0-dev.

**SPEC-051:** `specs/SPEC-051-Research-Audit-Remediation-Handoff-Packet.md` — implemented across models, engine, writer, and integration tests.

**Tag:** `v0.50.0-dev` at `64004c3`.

- `src/hunter/research_audit_remediation_handoff/__init__.py` — public API exports for models (`HandoffPacket`, `HandoffPacketConfig`, `HandoffPacketDataQuality`, `HandoffPacketError`, `HandoffPacketGroup`, `HandoffPacketSafetyFlags`), engine (`build_research_audit_remediation_handoff_packet`), writer (`handoff_packet_to_dict`, `handoff_packet_to_json`, `handoff_packet_to_markdown`, `atomic_write_json_handoff_packet`, `atomic_write_markdown_handoff_packet`).
- `src/hunter/research_audit_remediation_handoff/models.py` — frozen dataclass models for the handoff packet, packet groups, data quality, config, safety flags, and errors.
- `src/hunter/research_audit_remediation_handoff/engine.py` — deterministic engine that consumes a caller-provided MVP-49 `RemediationBridgeReport` or a tuple of `RemediationBacklogItem` summaries, groups items by `(reason_code, family)`, derives packet state, counts, and safety flags.
- `src/hunter/research_audit_remediation_handoff/writer.py` — deterministic JSON and Markdown serialization plus optional atomic file writers that never read from `data/` or `reports/`.
- `tests/test_research_audit_remediation_handoff/` — model, engine, writer, and integration tests (61 tests total). Integration tests build in-memory `HealthReport` → `RemediationBridgeReport` → `HandoffPacket` → JSON/Markdown flows.
- Boundaries preserved: no data/ or reports/ inspection; no runtime/trading/API/Freqtrade/server/database/scheduler behavior; no production/trading readiness, approval, certification, recommendation, or suitability claims.

## MVP-49 — Research Audit Health Remediation Bridge (Complete, Tagged)

**Version:** 0.48.0-dev → 0.49.0-dev.

**SPEC-050:** `specs/SPEC-050-Research-Audit-Health-Remediation-Bridge.md` — implemented across models, mapping, engine, writer, and integration tests.

**Tag:** `v0.49.0-dev` at `eff7c93`.

- `src/hunter/research_audit_health_remediation/__init__.py` — public API exports for models (`RemediationBridgeConfig`, `RemediationBridgeDataQuality`, `RemediationBridgeReport`), engine (`build_health_remediation_bridge_report`), writer (`bridge_report_to_dict`, `bridge_report_to_json`, `bridge_report_to_csv`, `bridge_report_to_markdown`, `BridgeWriterError`), default mapping tables, and default paths.
- `src/hunter/research_audit_health_remediation/models.py` — frozen dataclasses, reason codes, data-quality counters, and validation.
- `src/hunter/research_audit_health_remediation/mapping.py` — default severity, priority, item-type, and reason-code mapping tables.
- `src/hunter/research_audit_health_remediation/engine.py` — pure local deterministic bridge engine with finding-to-item mapping, stable item IDs, deduplication, forbidden-term scanning, and data-quality counters.
- `src/hunter/research_audit_health_remediation/writer.py` — deterministic dict/JSON/CSV/Markdown serialization with optional atomic file writes.
- `tests/test_research_audit_health_remediation/test_models.py` — model tests.
- `tests/test_research_audit_health_remediation/test_engine.py` — engine tests.
- `tests/test_research_audit_health_remediation/test_writer.py` — writer tests.
- `tests/test_research_audit_health_remediation/test_integration.py` — integration tests.
- 60 research_audit_health_remediation tests total.
- Full suite: 7680 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Safety: local, call-triggered, audit-only bridge engine over caller-provided in-memory `HealthReport` findings; not a production release approval system, not a certification of trading readiness, not a trading signal, not a recommendation, not a strategy selector, and not an execution/portfolio/universe approval gate; artifact refs and paths are opaque strings and are never opened, traversed, validated, fetched, or executed; no `data/` or `reports/` inspection; no Freqtrade input, no Binance/exchange/API/live data, no order/execution/action commands, no leverage/shorting, no feedback into execution/strategy/portfolio paths; no scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.

**Key commits:**
- SPEC: `6806aa9` Add MVP-49 research audit health remediation bridge spec
- Implementation (Steps 1-3): `1a4c7b2` Implement MVP-49 health remediation bridge
- Step 4 (memory/version docs): `eff7c93` Finalize MVP-49 project memory state

## MVP-48 — Research Audit Aggregate Health Report (Complete, Tagged)

**Version:** 0.47.0-dev → 0.48.0-dev.

**SPEC-049:** `specs/SPEC-049-Research-Audit-Aggregate-Health-Report.md` — implemented across models, engine, writer, and integration tests.

**Tag:** `v0.48.0-dev` at `779692f`.

- `src/hunter/research_audit_health/__init__.py` — public API exports for models (`HealthArtifactSummary`, `HealthConfig`, `HealthInput`, `HealthFamilyRollup`, `HealthFinding`, `HealthDataQuality`, `HealthSafetyFlags`, `HealthReport`, `HealthScore`, `HealthSeverity`, `HealthReasonCode`, `HealthState`), engine (`evaluate_research_audit_health`), writer (`health_report_to_dict`, `health_report_to_json`, `health_report_to_markdown`, `HealthWriterError`, `WriterForbiddenPhraseLeakageError`), default allowed families, required family groups, and default severity weight map.
- `src/hunter/research_audit_health/models.py` — frozen dataclasses, enums (`HealthState`, `HealthSeverity`, `HealthReasonCode`), reason codes, safety flags, data-quality counters, and forbidden-term guard.
- `src/hunter/research_audit_health/engine.py` — pure local aggregate health engine with input validation, family rollup scoring, aggregate severity-weighted score, reason-code assignment, findings, and safety flags.
- `src/hunter/research_audit_health/writer.py` — deterministic dict/JSON/Markdown serialization with forbidden-phrase output guard.
- `tests/test_research_audit_health/test_models.py` — model tests.
- `tests/test_research_audit_health/test_engine.py` — engine tests.
- `tests/test_research_audit_health/test_writer.py` — writer tests.
- `tests/test_research_audit_health/test_integration.py` — integration tests.
- 79 research_audit_health tests total.
- Full suite: 7620 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Safety: local, call-triggered, audit-only aggregate health engine over caller-provided in-memory artifact summaries, metadata, and opaque refs; not a production release approval system, not a certification of trading readiness, not a trading signal, not a recommendation, not a strategy selector, and not an execution/portfolio/universe approval gate; refs and paths are opaque strings and are never opened, traversed, validated, fetched, or executed; no `data/` or `reports/` inspection; no Freqtrade input, no Binance/exchange/API/live data, no order/execution/action commands, no leverage/shorting, no feedback into execution/strategy/portfolio paths; no scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.

**Key commits:**
- SPEC: `ec463ff` Add MVP-48 research audit health report spec
- Step 1-4 (models, engine, writer, integration tests): `779692f` Implement MVP-48 research audit health report
- Tag `v0.48.0-dev` applied at `779692f`.

**Version:** 0.46.0-dev → 0.47.0-dev.

**SPEC-048:** `specs/SPEC-048-Cross-Artifact-Consistency-Engine.md` — implemented across models, engine, writer, and integration tests.

**Tag:** `v0.47.0-dev` at `6103b95`.

- `src/hunter/cross_artifact_consistency/__init__.py` — public API exports for models, engine, writer, reason codes, safety constants, and default artifact paths.
- `src/hunter/cross_artifact_consistency/models.py` — frozen dataclasses (`CrossArtifactConsistencyInput`, `ConsistencyCheck`, `ConsistencyCheckResult`, `ArtifactRef`, `ConsistencyRule`, `ConsistencyReport`, `ConsistencyReportConfig`, `CrossArtifactConsistency`), enums (`ConsistencyCheckState`, `ConsistencySeverity`, `ConsistencyReasonCode`), reason codes, check kinds, and forbidden-content guard.
- `src/hunter/cross_artifact_consistency/engine.py` — pure local cross-artifact consistency engine with input validation, rule normalization, per-rule checks, severity aggregation, reason-code assignment, and report building.
- `src/hunter/cross_artifact_consistency/writer.py` — deterministic JSON/Markdown serialization and atomic writes for `CrossArtifactConsistencyReport`.
- `tests/test_cross_artifact_consistency/test_models.py` — model tests.
- `tests/test_cross_artifact_consistency/test_engine.py` — engine tests.
- `tests/test_cross_artifact_consistency/test_writer.py` — writer tests.
- `tests/test_cross_artifact_consistency/test_integration.py` — integration tests.
- 86 cross_artifact_consistency tests total.
- Full suite: 7620 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Safety: local, call-triggered, audit-only consistency engine over caller-provided in-memory artifact refs, rule definitions, and check results; not a production release approval system, not a certification of trading readiness, not a trading signal, not a recommendation, not a strategy selector, and not an execution/portfolio/universe approval gate; artifact refs are opaque strings and are not opened, traversed, validated, fetched, or executed; no Freqtrade input, no Binance/exchange/API/live data, no order/execution/action commands, no leverage/shorting, no feedback into execution/strategy/portfolio paths; no scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.

**Key commits:**
- SPEC: `4961d55` Add MVP-47 cross-artifact consistency spec
- Step 1: `8eb368b` Implement MVP-47 cross-artifact consistency engine
- Step 2: `139738e` Implement MVP-47 cross-artifact consistency writer
- Step 3: `c88e229` Add MVP-47 cross-artifact consistency integration tests
- Step 4 (memory/status): `6103b95` Finalize MVP-47 project memory state

## MVP-46 — Project Memory Realignment (Complete)

**Version:** 0.45.0-dev → 0.46.0-dev.

**SPEC-047:** `specs/SPEC-047-Project-Memory-Realignment.md` — documentation-only step to realign stale project memory files with the actual repository state.

**Tag:** `v0.46.0-dev`.

- **MVP-46 Step 1 — SPEC (Complete)**
  - `specs/SPEC-047-Project-Memory-Realignment.md` — defines the documentation-only memory realignment effort, including background, MoSCoW requirements, method, implementation steps, milestones, and gathering results.
- **MVP-46 Step 2 — Roadmap and MVP Index (Complete)**
  - `ROADMAP.md` — human-readable roadmap preserving original master plan as historical context, documenting expanded MVP chain through MVP-45, and listing anomalies.
  - `docs/MVP_INDEX.md` — deterministic evidence-based MVP index from MVP-0 through MVP-46 with source packages, test packages, tag anomalies, and excluded artifact areas.
- **MVP-46 Step 3 — Current-State, Task, Changelog, Version Alignment (Complete)**
  - `docs/handoff/CURRENT_STATE.md` updated to reflect MVP-45 / v0.45.0-dev as current functional milestone and MVP-46 as active work.
  - `tasks/active.md` updated to reflect MVP-46 as current active task.
  - `CHANGELOG.md` updated with MVP-41 through MVP-45 entries.
  - `VERSION` aligned to `0.46.0-dev`.
  - `pyproject.toml` version aligned to `0.46.0-dev`.
- **MVP-46 Step 4 — Architecture and Operations Docs Refresh (Complete)**
  - `docs/architecture/SYSTEM_OVERVIEW.md` and `docs/operations/*.md` refreshed to reflect MVP-45 / v0.45.0-dev current state.
- **MVP-46 Step 5 — Review and Finalization (Complete)**
  - Tag `v0.46.0-dev` applied at commit `b3ea2a4`.

**Safety and Boundaries**
- Documentation and version metadata only.
- No runtime code changes.
- No data, reports, or untracked cross_artifact_consistency access.
- No production-readiness, trading-readiness, approval, certification, recommendation, or suitability claims.
- Original master plan preserved as historical context.

## MVP-45 — Human Review Audit Bundle Export Verification / Replay (Complete)

**Version:** 0.44.0-dev → 0.45.0-dev.

**SPEC-046:** `specs/SPEC-046-Human-Review-Audit-Bundle-Export-Verification-Replay.md` — implemented across models, engine, writer, and integration tests.

**Tag:** `v0.45.0-dev` (HEAD).

- `src/hunter/human_review_audit_bundle_export_verification/` — models, engine, writer for deterministic local verification of audit bundle export outputs.
- `tests/test_human_review_audit_bundle_export_verification/` — model tests, engine tests, writer tests, integration tests.
- Verification is local, call-triggered, deterministic, and audit-only.
- No trading, exchange, API, network, or Freqtrade runtime semantics.
- All outputs are human-audit / research-only artifacts.

## MVP-44 — Human Review Audit Bundle Export Artifact (Complete)

**Version:** 0.43.0-dev → 0.44.0-dev.

**SPEC-045:** `specs/SPEC-045-Human-Review-Audit-Bundle-Export-Artifact.md` — implemented across models, engine, writer, and integration tests.

**Tag:** `v0.44.0-dev`.

- `src/hunter/human_review_audit_bundle_export/` — models, engine, writer for deterministic local audit bundle export with artifact references.
- `tests/test_human_review_audit_bundle_export/` — model tests, engine tests, writer tests, integration tests.
- Export is local, call-triggered, deterministic, and audit-only.
- No trading, exchange, API, network, or Freqtrade runtime semantics.

## MVP-43 — Human Review Audit Bundle Export (Complete)

**Version:** 0.42.0-dev → 0.43.0-dev.

**SPEC-044:** `specs/SPEC-044-Human-Review-Audit-Bundle-Export.md` — implemented across models, engine, writer, and integration tests.

**Tag:** `v0.43.0-dev`.

- `src/hunter/human_review_audit_bundle/` — models, engine, writer for deterministic local audit bundle export.
- `tests/test_human_review_audit_bundle/` — model tests, engine tests, writer tests, integration tests.
- Audit bundle export is local, call-triggered, deterministic, and audit-only.
- No trading, exchange, API, network, or Freqtrade runtime semantics.

## MVP-42 — Human Review Decision Log Cross-Artifact Consistency (Complete)

**Version:** 0.41.0-dev → 0.42.0-dev.

**SPEC-043:** `specs/SPEC-043-Human-Review-Decision-Log-Cross-Artifact-Consistency.md` — implemented across models, engine, writer, and integration tests.

**Tag:** `v0.42.0-dev`.

- `src/hunter/human_review_decision_log_consistency/` — models, engine, writer for deterministic local cross-artifact consistency checks of decision log entries.
- `tests/test_human_review_decision_log_consistency/` — model tests, engine tests, writer tests, integration tests.
- Consistency checks are local, call-triggered, deterministic, and audit-only.
- All artifact, report, and metadata references remain opaque local strings.

## MVP-41 — Local Research Human Review Decision Log (Complete)

**Version:** 0.40.0-dev → 0.41.0-dev.

**SPEC-042:** `specs/SPEC-042-Local-Research-Human-Review-Decision-Log.md` — implemented across models, engine, writer, and integration tests.

**Tag:** `v0.41.0-dev`.

- `src/hunter/human_review_decision_log/` — models, engine, writer for deterministic local human review decision log with queue entry refs, decision records, and decision links.
- `tests/test_human_review_decision_log/` — model tests, engine tests, writer tests, integration tests.
- Decision log is local, call-triggered, deterministic, and audit-only.
- No automated remediation execution; no shell commands, patches, file edits, deployment actions, or infrastructure changes.
- No scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.
- No Binance, exchange, API, live data, network, real trading, order, leverage, shorting, or Freqtrade strategy/runtime semantics.
- All outputs are human-audit / research-only artifacts.

## MVP-40 — Local Research Human Review Queue (Complete)

**Version:** 0.39.0-dev → 0.40.0-dev.

**SPEC-041:** `specs/SPEC-041-Local-Research-Human-Review-Queue.md` — implemented across models, engine, writer, and integration tests.

**Commit:** `TBD` — chore: finalize MVP-40 human review queue.

- **MVP-40 Step 1 — Models and Engine (Complete)**
  - `src/hunter/human_review_queue/__init__.py` — public API exports for models, engine, writer, reason codes, safety constants, and default artifact paths.
  - `src/hunter/human_review_queue/models.py` — frozen dataclasses: `HumanReviewSourceRecord`, `HumanReviewQueueEntry`, `HumanReviewQueueIssue`, `HumanReviewQueueConfig`, `HumanReviewQueueDataQuality`, `HumanReviewQueueInput`, `HumanReviewQueueReport`; enums `HumanReviewQueueState`, `HumanReviewQueueReasonCode`, `HumanReviewQueueSeverity`, `HumanReviewQueueEntryState`, `HumanReviewQueuePriority`, `HumanReviewQueueSourceKind`, `HumanReviewQueueDecisionHint`, `HumanReviewQueueIssueType`; reason-code constants and forbidden-term guard.
  - `src/hunter/human_review_queue/engine.py` — pure local human review queue engine: caller-provided in-memory source records, deterministic `report_id`, `queue_entry_id`, and `issue_id` generation, duplicate source ID detection (fail-closed), duplicate queue entry detection, orphan related-record detection against both `source_id` and `record_id` sets, stale source record detection using `staleness_threshold_seconds`, source kind mapping, queue entry state mapping, priority first-match-wins, non-executable decision hints, unsafe-content and forbidden-term fail-closed handling, and report aggregation with strict/non-strict modes.
  - `tests/test_human_review_queue/test_models.py` — model validation, safety flags, reason codes, enums, frozen data quality assertions.
  - `tests/test_human_review_queue/test_engine.py` — duplicate/unsafe blocking, orphan detection, staleness, source kind mapping, entry state mapping, priority first-match-wins, decision hints, forbidden-term false positives, aggregation, determinism, no input mutation.

- **MVP-40 Step 2 — Writer (Complete)**
  - `src/hunter/human_review_queue/writer.py` — deterministic JSON/CSV/Markdown serialization and atomic writes for `HumanReviewQueueReport`.
  - Includes `human_review_queue_report_to_dict`, `human_review_queue_report_to_json_text`, `human_review_queue_report_to_csv_text`, `human_review_queue_report_to_markdown_text`, `write_human_review_queue_report`, and atomic write helpers.
  - Default local artifact paths: `data/human_review_queue/human_review_queue.json`, `data/human_review_queue/human_review_queue.csv`, `reports/human_review_queue/human_review_queue.md`.
  - Markdown includes H1 title, immediate research-only/audit-only safety notice, explicit statement that queued-for-review is not an approval/certification/production readiness/trading readiness/recommendation/suitability assessment/signal/task assignment/executable remediation plan, and sections for summary, queue entries, source records, issues, data quality, safety flags, opaque reference notice, no automated remediation notice, reason codes, and notes.
  - `tests/test_human_review_queue/test_writer.py` — dict/JSON/CSV/Markdown serialization, atomic writes, determinism, blocked/degraded/ok/not_applicable reports, queue entry state mapping, no mutation, public exports, nested dataclass/mapping serialization, opaque file references, default/explicit/None path handling.

- **MVP-40 Step 3 — Integration Tests (Complete)**
  - `tests/test_human_review_queue/test_integration.py` — end-to-end human review queue flows with caller-provided source records; built-in checks (duplicate source IDs, duplicate queue entries, orphan related records by source_id and record_id, stale records); advisory-only and strict aggregation; unsafe-content and forbidden-term fail-closed behavior; false-positive-safe examples; writer end-to-end tests; determinism; no input mutation; public exports; safety boundary assertions; opaque reference assertions.

- **Safety and Boundaries**
  - The human review queue is local, call-triggered, deterministic, and audit-only.
  - `queued-for-review` means human-audit tracking only; it is not an approval, certification, production readiness assessment, trading readiness assessment, recommendation, suitability assessment, signal, or task assignment, and is not an executable remediation plan.
  - No automated remediation execution; no shell commands, patches, file edits, deployment actions, infrastructure changes, or executable steps as output.
  - No scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.
  - No Binance, exchange, API, live data, network, real trading, order, leverage, shorting, or Freqtrade strategy/runtime semantics introduced.
  - All outputs are human-audit / research-only artifacts; no action commands or feedback into execution paths.
  - Artifact, report, path, and metadata references remain opaque local strings; they are never opened, traversed, validated, fetched, or executed by the engine or writer.

- **Test Results**
  - `pytest tests/test_human_review_queue -q --import-mode=importlib`: 132 passed.
  - `pytest -q --import-mode=importlib`: 6782 passed, 1 skipped.

## MVP-39 — Local Research Remediation Closure Register (Complete)

**Version:** 0.38.0-dev → 0.39.0-dev.

**SPEC-040:** `specs/SPEC-040-Local-Research-Remediation-Closure-Register.md` — implemented across models, engine, writer, and integration tests.

**Commit:** `TBD` — feat: complete MVP-39 local research remediation closure register.

- **MVP-39 Step 1 — Models and Engine (Complete)**
  - `src/hunter/remediation_closure/__init__.py` — public API exports for models, engine, writer, reason codes, safety constants, and default artifact paths.
  - `src/hunter/remediation_closure/models.py` — frozen dataclasses: `RemediationClosureBacklogItemRef`, `RemediationClosureEvidenceSummary`, `RemediationClosureDeclaration`, `RemediationClosureReviewRecord`, `RemediationClosureLink`, `RemediationClosureIssue`, `RemediationClosureResult`, `RemediationClosureConfig`, `RemediationClosureDataQuality`, `RemediationClosureSafetyFlags`, `RemediationClosureInput`, `RemediationClosureReport`; enums `RemediationClosureState`, `RemediationClosureReasonCode`, `RemediationClosureSeverity`, `RemediationClosureRecordState`, `RemediationClosureEligibilityState`, `RemediationClosureReviewOutcome`, `RemediationClosureIssueType`; reason-code constants and forbidden-term guard.
  - `src/hunter/remediation_closure/engine.py` — pure local remediation closure engine: caller-provided in-memory declarations, deterministic `report_id`, `issue_id`, and `closure_result_id` generation, duplicate ID detection across backlog items/evidence summaries/closure declarations/review records/links (fail-closed), semantic duplicate closure detection by content hash, orphan evidence/closure/review/link detection, conflicting closure declaration and conflicting review outcome detection, stale evidence/closure/review detection using `staleness_threshold_seconds`, missing evidence detection controlled by `require_evidence_for_closure`, missing closure metadata detection (owner/reviewer/closed_at/rationale/evidence link), rejected/pending/disputed review handling, backlog-item state mismatch handling for `BLOCKED`/`OPEN`/`CONFLICTING`/`ACKNOWLEDGED`/`DEFERRED`/`NOT_APPLICABLE`, closure-record classification with first-match-wins precedence (`NOT_APPLICABLE`, `ORPHANED`, `BLOCKED`, `DISPUTED`, `DUPLICATE`, `REJECTED`, `STALE`, `PENDING_REVIEW`, `PARTIAL`, `CLOSED_RECORDED`), eligibility derivation (`ELIGIBLE`, `PARTIAL`, `INELIGIBLE`, `PENDING_REVIEW`, `DISPUTED`, `STALE`, `NOT_APPLICABLE`), unsafe-content and forbidden-term fail-closed handling, and report aggregation with strict/non-strict modes.
  - `tests/test_remediation_closure/test_models.py` — model validation, safety flags, reason codes, enums, frozen data quality assertions.
  - `tests/test_remediation_closure/test_engine.py` — duplicate/unsafe blocking, orphan detection, conflicting closures/reviews, staleness, missing evidence/review/metadata, review outcomes, backlog item state mismatches, closure precedence, aggregation, determinism, no input mutation.

- **MVP-39 Step 2 — Writer (Complete)**
  - `src/hunter/remediation_closure/writer.py` — deterministic JSON/CSV closure record/Markdown serialization and atomic writes for `RemediationClosureReport`.
  - Includes `remediation_closure_report_to_dict`, `remediation_closure_report_to_json_text`, `remediation_closure_report_to_csv_text`, `remediation_closure_report_to_markdown_text`, `write_remediation_closure_report`, and atomic write helpers.
  - Default local artifact paths: `data/remediation_closure/remediation_closure.json`, `data/remediation_closure/remediation_closure_records.csv`, `reports/remediation_closure/remediation_closure.md`.
  - Markdown includes H1 title, immediate research-only/audit-only safety notice, explicit statement that closure recorded is not an approval/certification/production readiness/deployment readiness/trading readiness/recommendation/suitability assessment/signal/executable remediation plan, and sections for summary, closure results, evidence summaries, closure declarations, review records, links, issues, data quality, safety flags, manual review notes, reason codes, and notes.
  - `tests/test_remediation_closure/test_writer.py` — dict/JSON/CSV/Markdown serialization, atomic writes, determinism, blocked/degraded/not_applicable reports, closed-recorded/partial/blocked/pending/rejected/disputed/stale/duplicate/orphaned results, no mutation, public exports, nested dataclass/mapping serialization, opaque file references, default/explicit/None path handling.

- **MVP-39 Step 3 — Integration Tests (Complete)**
  - `tests/test_remediation_closure/test_integration.py` — end-to-end remediation closure flows with caller-provided backlog item refs, evidence summaries, closure declarations, review records, and links; built-in checks (duplicate IDs, semantic duplicates, orphan evidence/closure/review/link, conflicting closures, conflicting reviews, stale records, missing evidence, missing metadata, pending/rejected/disputed reviews, backlog-item state mismatches); closure state precedence; strict/non-strict aggregation; unsafe-content and forbidden-term fail-closed behavior; false-positive-safe examples; writer end-to-end tests; determinism; no input mutation; public exports; safety boundary assertions; opaque reference assertions.

- **MVP-39 Step 4 — SPEC Alignment Patch (Complete)**
  - Aligned `MISSING_EVIDENCE`, `OPEN_BACKLOG_ITEM`, `BLOCKED_BACKLOG_ITEM`, and `CONFLICTING_BACKLOG_ITEM` issue severity to `BLOCKING` when closure safety is in question.
  - Moved corresponding reason codes into the engine's `_BLOCKING_REASON_CODES` set so non-strict aggregation produces `BLOCKED`.
  - Updated focused engine tests and integration tests to assert `BLOCKING` severity and `BLOCKED` aggregate state.
  - Updated `tests/test_remediation_closure/test_writer.py::test_degraded_report_serialization` to use an orphan-evidence scenario, because `OPEN`/`BLOCKED`/`CONFLICTING` backlog items with closure declarations now produce `BLOCKED` reports.

- **Safety and Boundaries**
  - The remediation closure register is local, call-triggered, deterministic, and audit-only.
  - `closure-recorded` means human-audit tracking only; it is not an approval, certification, production readiness assessment, deployment readiness assessment, trading readiness assessment, recommendation, suitability assessment, or signal, and is not an executable remediation plan.
  - No automated remediation execution; no shell commands, patches, file edits, deployment actions, infrastructure changes, or executable steps as output.
  - No scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.
  - No Binance, exchange, API, live data, network, real trading, order, leverage, shorting, or Freqtrade strategy/runtime semantics introduced.
  - All outputs are human-audit / research-only artifacts; no action commands or feedback into execution paths.
  - Artifact, report, path, evidence, backlog, closure, review, and metadata references remain opaque local strings; they are never opened, traversed, validated, fetched, or executed by the engine or writer.

- **Test Results**
  - `pytest tests/test_remediation_closure -q --import-mode=importlib`: 177 passed.
  - `pytest -q --import-mode=importlib`: 6650 passed, 1 skipped.

## MVP-38 — Local Research Remediation Evidence Tracker (Complete)

**Version:** 0.37.0-dev → 0.38.0-dev.

**SPEC-039:** `specs/SPEC-039-Local-Research-Remediation-Evidence-Tracker.md` — implemented across models, engine, writer, and integration tests.

**Commit:** `TBD` — feat: complete MVP-38 local research remediation evidence tracker.

- **MVP-38 Step 1 — Models and Engine (Complete)**
  - `src/hunter/remediation_evidence/__init__.py` — public API exports for models, engine, writer, reason codes, safety constants, and default artifact paths.
  - `src/hunter/remediation_evidence/models.py` — frozen dataclasses: `RemediationBacklogItemRef`, `RemediationEvidenceRecord`, `RemediationReviewRecord`, `RemediationEvidenceLink`, `RemediationEvidenceIssue`, `RemediationEvidenceCoverageResult`, `RemediationEvidenceConfig`, `RemediationEvidenceDataQuality`, `RemediationEvidenceSafetyFlags`, `RemediationEvidenceInput`, `RemediationEvidenceReport`; enums `RemediationEvidenceState`, `RemediationEvidenceSeverity`, `RemediationEvidenceReasonCode`, `RemediationEvidenceRecordState`, `RemediationEvidenceCoverageState`, `RemediationEvidenceReviewOutcome`, `RemediationEvidenceLinkType`, `RemediationEvidenceIssueType`; reason-code constants and forbidden-term guard.
  - `src/hunter/remediation_evidence/engine.py` — pure local remediation evidence engine: caller-provided in-memory declarations, deterministic `report_id`, `issue_id`, and `coverage_id` generation, duplicate ID detection across backlog items/evidence/reviews/links (fail-closed), duplicate evidence deduplication by content hash, orphan evidence/review/link detection, conflicting review outcome detection, stale evidence/review detection using `staleness_threshold_seconds`, missing evidence/review detection, rejected and pending-review evidence detection, backlog-item state mismatch detection (BLOCKED/OPEN/ACKNOWLEDGED/DEFERRED/NOT_APPLICABLE), coverage classification with first-match-wins precedence (NOT_APPLICABLE, MISSING, CONFLICTING, REJECTED, STALE, PENDING_REVIEW, COVERED, PARTIAL), unsafe-content and forbidden-term fail-closed handling, and report aggregation with strict/non-strict modes.
  - `tests/test_remediation_evidence/test_models.py` — model validation, safety flags, reason codes, enums, frozen data quality assertions.
  - `tests/test_remediation_evidence/test_engine.py` — duplicate/unsafe blocking, duplicate evidence, orphan detection, conflicting reviews, staleness, missing evidence/review, coverage precedence, backlog item state mismatches, aggregation, determinism, no input mutation.

- **MVP-38 Step 2 — Writer (Complete)**
  - `src/hunter/remediation_evidence/writer.py` — deterministic JSON/CSV evidence record/Markdown serialization and atomic writes for `RemediationEvidenceReport`.
  - Includes `remediation_evidence_report_to_dict`, `remediation_evidence_report_to_json_text`, `remediation_evidence_report_to_csv_text`, `remediation_evidence_report_to_markdown_text`, `write_remediation_evidence_report`, and atomic write helpers.
  - Default local artifact paths: `data/remediation_evidence/remediation_evidence.json`, `data/remediation_evidence/remediation_evidence_records.csv`, `reports/remediation_evidence/remediation_evidence.md`.
  - Markdown includes H1 title, immediate research-only/audit-only safety notice, explicit statement that evidence coverage is not an approval/certification/production readiness/trading readiness/recommendation/suitability assessment/signal/executable remediation plan, and sections for summary, coverage results, evidence records, review records, links, issues, data quality, safety flags, manual review notes, reason codes, and notes.
  - `tests/test_remediation_evidence/test_writer.py` — dict/JSON/CSV/Markdown serialization, atomic writes, determinism, blocked/degraded/not_applicable reports, accepted/rejected/pending/stale/conflicting coverage, no mutation, public exports, nested dataclass/mapping serialization, opaque file references, default/explicit/None path handling.

- **MVP-38 Step 3 — Integration Tests (Complete)**
  - `tests/test_remediation_evidence/test_integration.py` — end-to-end remediation evidence flows with caller-provided backlog item refs, evidence records, review records, and evidence links; built-in checks (duplicate IDs, duplicate evidence, orphan evidence/reviews/links, conflicting reviews, stale records, missing evidence/review, rejected/pending evidence, backlog-item state mismatches); coverage state precedence; strict/non-strict aggregation; unsafe-content and forbidden-term fail-closed behavior; false-positive-safe examples; writer end-to-end tests; determinism; no input mutation; public exports; safety boundary assertions; opaque reference assertions.

- **Safety and Boundaries**
  - The remediation evidence tracker is local, call-triggered, deterministic, and audit-only.
  - Evidence coverage is a human-audit tracking label only; it is not an approval, certification, production readiness assessment, trading readiness assessment, recommendation, suitability assessment, or signal, and is not an executable remediation plan.
  - No scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.
  - No Binance, exchange, API, live data, network, real trading, order, leverage, shorting, or Freqtrade strategy/runtime semantics introduced.
  - All outputs are human-audit / research-only artifacts; no action commands, shell commands, code patches, deployment steps, infrastructure changes, or feedback into execution paths.
  - Artifact, report, path, evidence, backlog, and metadata references remain opaque local strings; they are never opened, traversed, validated, fetched, or executed by the engine or writer.

- **Test Results**
  - `pytest tests/test_remediation_evidence -q --import-mode=importlib`: 167 passed.
  - `pytest -q --import-mode=importlib`: 6473 passed, 1 skipped.

## MVP-37 — Local Research Remediation Backlog Planner (Complete)

**Version:** 0.36.0-dev → 0.37.0-dev.

**SPEC-038:** `specs/SPEC-038-Local-Research-Remediation-Backlog-Planner.md` — implemented across models, engine, writer, and integration tests.

**Commit:** `TBD` — feat: complete MVP-37 local research remediation backlog planner.

- **MVP-37 Step 1 — Models and Engine (Complete)**
  - `src/hunter/remediation_backlog/__init__.py` — public API exports for models, engine, writer, reason codes, safety constants, and default artifact paths.
  - `src/hunter/remediation_backlog/models.py` — frozen dataclasses: `RemediationSourceRef`, `RemediationFindingRef`, `RemediationBacklogItem`, `RemediationDependency`, `RemediationAcknowledgement`, `RemediationBacklogConfig`, `RemediationBacklogDataQuality`, `RemediationBacklogSafetyFlags`, `RemediationBacklogReport`; enums `RemediationBacklogState`, `RemediationBacklogReasonCode`, `RemediationBacklogSeverity`, `RemediationBacklogPriority`, `RemediationBacklogItemState`, `RemediationBacklogItemType`, `RemediationDependencyType`; reason-code constants and forbidden-term guard.
  - `src/hunter/remediation_backlog/engine.py` — pure local remediation backlog engine: caller-provided in-memory declarations, deterministic ID normalization, deterministic `report_id` and generated `item_id`, duplicate ID detection (fail-closed), duplicate backlog-item deduplication by content hash, missing required source detection, orphan finding/dependency detection, dependency-cycle detection, conflicting item-state detection, stale source/finding ref detection, missing owner/reviewer/manual-review detection, acknowledgement handling, priority assignment (first-match-wins), unsafe-content and forbidden-term fail-closed handling, and report aggregation with strict/non-strict modes.
  - `tests/test_remediation_backlog/test_models.py` — model validation, safety flags, reason codes, enums, frozen data quality assertions.
  - `tests/test_remediation_backlog/test_engine.py` — duplicate/unsafe blocking, missing required sources, orphan findings/dependencies, dependency cycles, conflicting states, stale refs, manual review, acknowledgements, deduplication, aggregation, determinism, no input mutation.

- **MVP-37 Step 2 — Writer (Complete)**
  - `src/hunter/remediation_backlog/writer.py` — deterministic JSON/CSV backlog item/Markdown serialization and atomic writes for `RemediationBacklogReport`.
  - Includes `remediation_backlog_report_to_dict`, `remediation_backlog_report_to_json_text`, `remediation_backlog_report_to_csv_text`, `remediation_backlog_report_to_markdown_text`, `write_remediation_backlog_report`, and atomic write helpers.
  - Default local artifact paths: `data/remediation_backlog/remediation_backlog.json`, `data/remediation_backlog/remediation_backlog_items.csv`, `reports/remediation_backlog/remediation_backlog.md`.
  - Markdown includes H1 title, immediate research-only/audit-only safety notice, explicit statement that the backlog is not an approval/certification/production readiness/trading readiness/recommendation/suitability assessment/signal/executable remediation plan, and sections for summary, backlog items, dependencies, acknowledgements, source refs, finding refs, data quality, safety flags, manual review, and reason codes.
  - `tests/test_remediation_backlog/test_writer.py` — dict/JSON/CSV/Markdown serialization, atomic writes, determinism, blocked/degraded/not_applicable reports, acknowledged/deferred/duplicate/conflicting items, no mutation, public exports, nested dataclass/mapping serialization, opaque file references, default/explicit/None path handling.

- **MVP-37 Step 3 — Integration Tests (Complete)**
  - `tests/test_remediation_backlog/test_integration.py` — end-to-end remediation backlog flows with caller-provided source refs, finding refs, backlog items, dependencies, and acknowledgements; built-in checks (missing required sources, orphan findings/dependencies, dependency cycles, conflicting states, stale refs, missing owner/reviewer/manual review); acknowledgement and duplicate behavior; priority/severity/aggregation; unsafe-content and forbidden-term fail-closed behavior; false-positive-safe examples; writer end-to-end tests; determinism; no input mutation; public exports; safety boundary assertions; opaque reference assertions.

- **Safety and Boundaries**
  - The remediation backlog planner is local, call-triggered, deterministic, and audit-only.
  - It is not a production certification, not a certification of trading readiness, not a trading signal, not a recommendation, not a suitability assessment, and not an execution/portfolio/universe approval gate.
  - No scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.
  - No Binance, exchange, API, live data, network, real trading, order, leverage, shorting, or Freqtrade strategy/runtime semantics introduced.
  - All outputs are human-audit / research-only artifacts; no action commands, shell commands, code patches, deployment steps, infrastructure changes, or feedback into execution paths.
  - Priority is human-review ordering only and is not an implementation instruction, execution schedule, or automated remediation directive.
  - Artifact, report, path, finding, source, and metadata references remain opaque local strings; they are never opened, traversed, validated, fetched, or executed by the engine or writer.

- **Test Results**
  - `pytest tests/test_remediation_backlog -q --import-mode=importlib`: 141 passed.
  - `pytest -q --import-mode=importlib`: 6306 passed, 1 skipped.

## MVP-36 — Local Research Cross-Pack Consistency Validator (Complete)

**Version:** 0.35.0-dev → 0.36.0-dev.

**SPEC-037:** `specs/SPEC-037-Local-Research-Cross-Pack-Consistency-Validator.md` — implemented across models, engine, writer, and integration tests.

**Commit:** `TBD` — feat: complete MVP-36 local research cross-pack consistency validator.

- **MVP-36 Step 1 — Models and Engine (Complete)**
  - `src/hunter/cross_pack_consistency/__init__.py` — public API exports for models, engine, writer, reason codes, safety constants, and default artifact paths.
  - `src/hunter/cross_pack_consistency/models.py` — frozen dataclasses: `CrossPackConsistencyInput`, `CrossPackDeclaration`, `CrossPackArtifactRef`, `CrossPackSectionRef`, `CrossPackRequirementRef`, `CrossPackStateClaim`, `CrossPackConsistencyRule`, `CrossPackConsistencyIssue`, `CrossPackConsistencyConfig`, `CrossPackConsistencyDataQuality`, `CrossPackConsistencySafetyFlags`, `CrossPackConsistencyReport`; enums `CrossPackConsistencyState`, `CrossPackConsistencyReasonCode`, `CrossPackConsistencySeverity`, `CrossPackConsistencyIssueType`, `CrossPackConsistencyRuleType`; reason-code constants and forbidden-term guard.
  - `src/hunter/cross_pack_consistency/engine.py` — pure local cross-pack consistency engine: caller-provided in-memory declarations, deterministic ID normalization, duplicate detection, required-pack detection, expected-ref/orphan-ref detection, incompatible-version detection, stale-declaration detection, incompatible-state-combination detection, conflicting-state detection, missing-manual-review detection, unknown-upstream-state detection, unsafe-content and forbidden-term fail-closed handling, and report aggregation with strict/non-strict modes.
  - `tests/test_cross_pack_consistency/test_models.py` — model validation, safety flags, reason codes, enums.
  - `tests/test_cross_pack_consistency/test_engine.py` — duplicate/unsafe blocking, missing required packs, expected/orphan refs, staleness, conflicting states, unknown states, manual review, version/state rules, aggregation, determinism, no input mutation.

- **MVP-36 Step 2 — Writer (Complete)**
  - `src/hunter/cross_pack_consistency/writer.py` — deterministic JSON/CSV issues/Markdown serialization and atomic writes for `CrossPackConsistencyReport`.
  - Includes `cross_pack_consistency_report_to_dict`, `cross_pack_consistency_report_to_json_text`, `cross_pack_consistency_report_to_csv_text`, `cross_pack_consistency_report_to_markdown_text`, `write_cross_pack_consistency_report`, and atomic write helpers.
  - Default local artifact paths: `data/cross_pack_consistency/cross_pack_consistency.json`, `data/cross_pack_consistency/cross_pack_consistency_issues.csv`, `reports/cross_pack_consistency/cross_pack_consistency.md`.
  - Markdown includes H1 title, immediate research-only/audit-only safety notice, and sections for summary, consistency issues, pack declarations, references, state claims, rules, data quality, safety flags, manual review, and reason codes.
  - `tests/test_cross_pack_consistency/test_writer.py` — dict/JSON/CSV/Markdown serialization, atomic writes, determinism, blocked/degraded reports, no mutation, public exports, nested dataclass/mapping serialization, opaque file references.

- **MVP-36 Step 3 — Integration Tests (Complete)**
  - `tests/test_cross_pack_consistency/test_integration.py` — end-to-end cross-pack consistency flows with caller-provided declarations, artifact refs, section refs, requirement refs, state claims, and rules; built-in vs rule-driven checks; missing required packs/expected refs/orphan refs/stale declarations/conflicting states/unknown states/manual review; incompatible version/state combinations; unsafe-content fail-closed behavior; aggregation in strict and non-strict modes; writer end-to-end tests; determinism; no input mutation; public exports; safety boundary assertions; opaque artifact reference assertions.

- **Safety and Boundaries**
  - The cross-pack consistency validator is local, call-triggered, deterministic, and audit-only.
  - It is not a production certification, not a certification of trading readiness, not a trading signal, not a recommendation, not a strategy selector, and not an execution/portfolio/universe approval gate.
  - No scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.
  - No Binance, exchange, API, live data, network, real trading, order, leverage, shorting, or Freqtrade strategy/runtime semantics introduced.
  - All outputs are human-audit / research-only artifacts; no action commands or feedback into execution paths.
  - Artifact, section, requirement, report, and metadata references remain opaque local strings; they are never opened, traversed, validated, fetched, or executed by the engine or writer.

- **Test Results**
  - `pytest tests/test_cross_pack_consistency -q --import-mode=importlib`: 110 passed.
  - `pytest -q --import-mode=importlib`: 6165 passed, 1 skipped.

## MVP-35 — Local Research Audit Readiness Scorecard (Complete)

**Version:** 0.34.0-dev → 0.35.0-dev.

**SPEC-036:** `specs/SPEC-036-Local-Research-Audit-Readiness-Scorecard.md` — implemented across models, engine, writer, and integration tests.

**Commit:** `TBD` — feat: complete MVP-35 local research audit readiness scorecard.

- **MVP-35 Step 1 — Models and Engine (Complete)**
  - `src/hunter/audit_scorecard/__init__.py` — public API exports for models, engine, writer, reason codes, safety constants, and default artifact paths.
  - `src/hunter/audit_scorecard/models.py` — frozen dataclasses: `AuditScorecardInput`, `AuditScorecardDimension`, `AuditScorecardDimensionResult`, `AuditScorecardEvidenceRef`, `AuditScorecardFinding`, `AuditScorecardLink`, `AuditScorecardConfig`, `AuditScorecardDataQuality`, `AuditScorecardSafetyFlags`, `AuditScorecardReport`; enums `AuditScorecardState`, `AuditScorecardReasonCode`, `AuditScorecardSeverity`, `AuditScorecardDimensionState`, `AuditScorecardLinkType`; reason-code constants and forbidden-term guard.
  - `src/hunter/audit_scorecard/engine.py` — pure local audit readiness scorecard engine: input validation, caller-provided in-memory declarations, deterministic dimension classification (`complete`/`partial`/`missing`/`blocked`/`degraded`/`not_applicable`), upstream state propagation, duplicate detection, stale-evidence detection, missing-manual-review detection, conflicting-finding/link detection, orphan evidence/link detection, unsafe-content and forbidden-term fail-closed handling, and report aggregation with strict/non-strict modes.
  - `tests/test_audit_scorecard/test_models.py` — model validation, safety flags, reason codes, dimension/link enums.
  - `tests/test_audit_scorecard/test_engine.py` — dimension classification, upstream states, orphans, conflicts, staleness, manual review, duplicate/unsafe blocking, aggregation, determinism, no input mutation.

- **MVP-35 Step 2 — Writer (Complete)**
  - `src/hunter/audit_scorecard/writer.py` — deterministic JSON/CSV/Markdown serialization and atomic writes for `AuditScorecardReport`.
  - Includes `audit_scorecard_report_to_dict`, `audit_scorecard_report_to_json_text`, `audit_scorecard_report_to_csv_text`, `audit_scorecard_report_to_markdown_text`, `write_audit_scorecard_report`, and atomic write helpers.
  - Default local artifact paths: `data/audit_scorecard/audit_scorecard.json`, `data/audit_scorecard/audit_scorecard_dimensions.csv`, `reports/audit_scorecard/audit_scorecard.md`.
  - Markdown includes H1 title, immediate research-only/audit-only safety notice, and sections for summary, dimension results, findings, evidence references, links, data quality, safety flags, manual review, reason codes, and notes.
  - `tests/test_audit_scorecard/test_writer.py` — dict/JSON/CSV/Markdown serialization, atomic writes, determinism, blocked/degraded reports, no mutation, public exports, nested dataclass/mapping serialization, opaque file references.

- **MVP-35 Step 3 — Integration Tests (Complete)**
  - `tests/test_audit_scorecard/test_integration.py` — end-to-end audit scorecard flows with caller-provided dimensions, evidence refs, findings, links, and upstream states; dimension classification (complete/partial/missing/blocked/degraded/not-applicable); upstream precedence; duplicate/unsafe fail-closed behavior; conflicting findings/links; orphan evidence/links; stale evidence; missing manual review; aggregation in strict and non-strict modes; writer end-to-end tests; determinism; no input mutation; public exports; safety boundary assertions; opaque artifact reference assertions.

- **Safety and Boundaries**
  - The audit readiness scorecard is local, call-triggered, deterministic, and audit-only.
  - "Readiness" means only a human audit review completeness snapshot for local research artifacts; it is not a production certification, not a certification of trading readiness, not a trading signal, not a recommendation, not a suitability assessment, and not an execution/portfolio/universe approval gate.
  - No scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.
  - No Binance, exchange, API, live data, network, real trading, order, leverage, shorting, or Freqtrade strategy/runtime semantics introduced.
  - All outputs are human-audit / research-only artifacts; no action commands or feedback into execution paths.
  - Completeness percentages are descriptive metrics only (0–100 integer) and are not approval scores, certification grades, or pass/fail thresholds.
  - Artifact, report, and metadata references remain opaque local strings; they are never opened, traversed, validated, fetched, or executed by the engine or writer.

- **Test Results**
  - `pytest tests/test_audit_scorecard -q --import-mode=importlib`: 115 passed.
  - `pytest -q --import-mode=importlib`: 6055 passed, 1 skipped.

## MVP-34 — Local Research Evidence Traceability Matrix (Complete)

**Version:** 0.33.0-dev → 0.34.0-dev.

**SPEC-035:** `specs/SPEC-035-Local-Research-Evidence-Traceability-Matrix.md` — implemented across models, engine, writer, and integration tests.

**Commit:** `TBD` — feat: complete MVP-34 local research evidence traceability matrix.

- **MVP-34 Step 1 — Models and Engine (Complete)**
  - `src/hunter/evidence_traceability/__init__.py` — public API exports for models, engine, writer, reason codes, safety constants, and default artifact paths.
  - `src/hunter/evidence_traceability/models.py` — frozen dataclasses: `EvidenceRequirement`, `EvidenceCheck`, `EvidenceArtifactRef`, `EvidenceSectionRef`, `EvidenceLink`, `EvidenceTraceabilityInput`, `EvidenceTraceabilityConfig`, `EvidenceTraceabilityResult`, `EvidenceTraceabilityDataQuality`, `EvidenceTraceabilitySafetyFlags`, `EvidenceTraceabilityReport`; enums `EvidenceTraceabilityState`, `EvidenceTraceabilityReasonCode`, `EvidenceTraceabilitySeverity`, `EvidenceTraceabilityLinkType`, `EvidenceTraceabilityCoverageState`; reason-code constants and forbidden-term guard.
  - `src/hunter/evidence_traceability/engine.py` — pure local evidence traceability engine: input validation, caller-provided in-memory declarations, deterministic coverage classification (missing/partial/covered), orphan detection for checks/artifacts/sections, conflicting-link detection, stale-evidence detection, missing-manual-review detection, unsafe-content and forbidden-term fail-closed handling, and report aggregation with strict/non-strict modes.
  - `tests/test_evidence_traceability/test_models.py` — model validation, safety flags, reason codes, link/coverage enums.
  - `tests/test_evidence_traceability/test_engine.py` — coverage classification, orphans, conflicts, staleness, manual review, duplicate/unsafe blocking, aggregation, determinism, no input mutation.

- **MVP-34 Step 2 — Writer (Complete)**
  - `src/hunter/evidence_traceability/writer.py` — deterministic JSON/CSV edge/Markdown serialization and atomic writes for `EvidenceTraceabilityReport`.
  - Includes `evidence_traceability_report_to_dict`, `evidence_traceability_report_to_json_text`, `evidence_traceability_report_to_csv_text`, `evidence_traceability_report_to_markdown_text`, `write_evidence_traceability_report`, and atomic write helpers.
  - Default local artifact paths: `data/evidence_traceability/evidence_traceability.json`, `data/evidence_traceability/evidence_traceability_edges.csv`, `reports/evidence_traceability/evidence_traceability.md`.
  - Markdown includes H1 title, immediate research-only/audit-only safety notice, and sections for summary, traceability results, links, data quality, safety flags, reason codes, and notes.
  - `tests/test_evidence_traceability/test_writer.py` — dict/JSON/CSV/Markdown serialization, atomic writes, determinism, blocked/degraded reports, no mutation, public exports, opaque file references.

- **MVP-34 Step 3 — Integration Tests (Complete)**
  - `tests/test_evidence_traceability/test_integration.py` — end-to-end evidence traceability flows with caller-provided requirements, checks, artifact refs, section refs, and links; coverage classification (missing/partial/covered); orphan check/artifact/section detection; conflicting links; stale evidence; missing manual review; duplicate/unsafe/fail-closed behavior; writer end-to-end tests; determinism; no input mutation; safety boundary assertions; opaque artifact reference assertions.

- **Safety and Boundaries**
  - The evidence traceability matrix is local, call-triggered, deterministic, and audit-only.
  - It is not a production certification, not a certification of trading readiness, not a trading signal, not a recommendation, not a strategy selector, and not an execution/portfolio/universe approval gate.
  - No scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.
  - No Binance, exchange, API, live data, network, real trading, order, leverage, shorting, or Freqtrade strategy/runtime semantics introduced.
  - All outputs are human-audit / research-only artifacts; no action commands or feedback into execution paths.
  - Artifact and section references remain opaque local strings; they are never opened, traversed, validated, fetched, or executed by the engine or writer.

- **Test Results**
  - `pytest tests/test_evidence_traceability -q --import-mode=importlib`: 20 passed.
  - `pytest -q --import-mode=importlib`: 5940 passed, 1 skipped.

## MVP-33 — Local Research Release Hardening / Consistency Audit (Complete)

**Version:** 0.32.0-dev → 0.33.0-dev.

**SPEC-034:** `specs/SPEC-034-Local-Research-Release-Hardening-Consistency-Audit.md` — implemented across models, engine, writer, and integration tests.

**Commit:** `TBD` — feat: complete MVP-33 local research release hardening / consistency audit.

- **MVP-33 Step 1 — Models and Engine (Complete)**
  - `src/hunter/release_hardening/__init__.py` — public API exports for models, engine, writer, reason codes, safety constants, and default artifact paths.
  - `src/hunter/release_hardening/models.py` — frozen dataclasses: `PackageDeclaration`, `CompletedAuditPackage`, `ReleaseHardeningCheck`, `ReleaseHardeningCheckResult`, `ReleaseHardeningConfig`, `ReleaseHardeningDataQuality`, `ReleaseHardeningSafetyFlags`, `ReleaseHardeningInput`, `ReleaseHardeningReport`; enums `ReleaseHardeningState`, `ReleaseHardeningReasonCode`, `ReleaseHardeningSeverity`, `ReleaseHardeningCheckCategory`; reason-code constants and forbidden-term guard.
  - `src/hunter/release_hardening/engine.py` — pure local release hardening engine: input validation, deterministic default checks across ten categories (public exports, package presence, writer defaults, safety notices, markdown disclaimer, forbidden terms, version consistency, default path locality, test artifact isolation, artifact path policy), fail-closed duplicate/unsafe handling, and report aggregation with strict/non-strict modes.
  - `tests/test_release_hardening/test_models.py` — model validation, safety flags, reason codes.
  - `tests/test_release_hardening/test_engine.py` — check behavior, aggregation, strict mode, determinism, no input mutation, unsafe content blocking.

- **MVP-33 Step 2 — Writer (Complete)**
  - `src/hunter/release_hardening/writer.py` — deterministic JSON/CSV/Markdown serialization and atomic writes for `ReleaseHardeningReport`.
  - Includes `release_hardening_report_to_dict`, `release_hardening_report_to_json_text`, `release_hardening_report_to_csv_text`, `release_hardening_report_to_markdown_text`, `write_release_hardening_report`, and atomic write helpers.
  - Default local artifact paths: `data/release_hardening/release_hardening.json`, `data/release_hardening/release_hardening_checks.csv`, `reports/release_hardening/release_hardening.md`.
  - Markdown includes H1 title, immediate research-only/audit-only safety notice, and sections for summary, data quality, checks by category, safety flags, reason codes, and notes.
  - `tests/test_release_hardening/test_writer.py` — dict/JSON/CSV/Markdown serialization, atomic writes, determinism, blocked/degraded reports, no mutation, public exports, nested dataclass/mapping serialization, opaque file references.

- **MVP-33 Step 3 — Integration Tests (Complete)**
  - `tests/test_release_hardening/test_integration.py` — end-to-end release hardening flows with caller-provided `PackageDeclaration` and `CompletedAuditPackage` inputs; public export, package presence, and test artifact isolation checks; empty-actual behavior; aggregation in strict and non-strict modes; version consistency; duplicate/unsafe fail-closed behavior; writer end-to-end tests; determinism; no input mutation; public exports; safety boundary assertions.

- **Safety and Boundaries**
  - The release hardening audit is local, call-triggered, deterministic, and audit-only.
  - It is not a production release approval system, not a certification of trading readiness, not a trading signal, not a recommendation, not a strategy selector, and not an execution/portfolio/universe approval gate.
  - No scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.
  - No Binance, exchange, API, live data, network, real trading, order, leverage, shorting, or Freqtrade strategy/runtime semantics introduced.
  - All outputs are human-audit / research-only artifacts; no action commands or feedback into execution paths.
  - Metadata and file-reference strings remain opaque local strings; they are never opened, traversed, validated, fetched, or executed by the engine or writer.

- **Test Results**
  - `pytest tests/test_release_hardening -q --import-mode=importlib`: 94 passed.
  - `pytest -q --import-mode=importlib`: 5844 passed, 1 skipped.

## MVP-32 — Local Research Final Audit Pack Export (Complete)

**Version:** 0.31.0-dev → 0.32.0-dev.

**SPEC-033:** `specs/SPEC-033-Local-Research-Final-Audit-Pack-Export.md` — implemented across models, engine, writer, and integration tests.

**Commit:** `TBD` — feat: complete MVP-32 local research final audit pack export.

- **MVP-32 Step 1 — Models and Engine (Complete)**
  - `src/hunter/final_audit_pack/__init__.py` — public API exports for models, engine, writer, reason codes, safety constants, and default artifact paths.
  - `src/hunter/final_audit_pack/models.py` — frozen dataclasses: `FinalAuditPackInput`, `FinalAuditPackSection`, `FinalAuditPackArtifact`, `FinalAuditPackConfig`, `FinalAuditPackCompleteness`, `FinalAuditPackDataQuality`, `FinalAuditPackSafetyFlags`, `FinalAuditPackReport`; enums `FinalAuditPackState`, `FinalAuditPackReasonCode`; reason-code constants, section-kind constants, and forbidden-term guard.
  - `src/hunter/final_audit_pack/engine.py` — pure local final audit pack engine: input validation, deterministic normalization of caller-provided in-memory reports (`BacktestReport`, `ResearchRunResult`, `ExperimentLedgerReport`, `PortfolioConstructionReport`, `DiscoveryReport`, `CLICommandResult`) into `FinalAuditPackSection` objects, duplicate `section_id` detection, unsafe-content scanning, completeness/readiness summary, data quality, safety flags, and deterministic report identifiers.
  - `tests/test_final_audit_pack/test_models.py` — model validation, safety flags, reason codes.
  - `tests/test_final_audit_pack/test_engine.py` — normalization, completeness, fail-closed behavior, determinism, no input mutation.

- **MVP-32 Step 2 — Writer (Complete)**
  - `src/hunter/final_audit_pack/writer.py` — deterministic JSON/CSV/Markdown serialization and atomic writes for `FinalAuditPackReport`.
  - Includes `final_audit_pack_report_to_dict`, `final_audit_pack_report_to_json_text`, `final_audit_pack_report_to_csv_text`, `final_audit_pack_report_to_markdown_text`, `write_final_audit_pack_report`, and atomic write helpers.
  - Default local artifact paths: `data/final_audit_pack/final_audit_pack.json`, `data/final_audit_pack/final_audit_pack_sections.csv`, `reports/final_audit_pack/final_audit_pack.md`.
  - Markdown includes H1 title, immediate research-only/audit-only safety notice, and sections for summary, completeness, sections, artifacts, data quality, safety flags, reason codes, metadata, and notes.
  - `tests/test_final_audit_pack/test_writer.py` — dict/JSON/CSV/Markdown serialization, atomic writes, determinism, blocked reports, no mutation, public exports, nested dataclass/mapping serialization, opaque file references.

- **MVP-32 Step 3 — Integration Tests (Complete)**
  - `tests/test_final_audit_pack/test_integration.py` — end-to-end final audit pack flows with `BacktestReport`, `ResearchRunResult`, `ExperimentLedgerReport`, and `CLICommandResult` inputs; normalization; completeness and degraded-state tests; duplicate/unsafe fail-closed behavior; writer end-to-end tests; determinism; no input mutation; public exports; safety boundary assertions.

- **Safety and Boundaries**
  - The final audit pack is local, call-triggered, deterministic, and audit-only.
  - It is not a production release approval system, not a certification of trading readiness, not a strategy selector, not a signal generator, and not a performance attribution tool.
  - No scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.
  - No Binance, exchange, API, live data, network, real trading, order, leverage, shorting, or Freqtrade strategy/runtime semantics introduced.
  - All outputs are human-audit / research-only artifacts; no action commands or feedback into execution paths.
  - Metadata and file-reference strings remain opaque local strings; they are never opened, traversed, validated, fetched, or executed by the engine or writer.

- **Test Results**
  - `pytest tests/test_final_audit_pack -q --import-mode=importlib`: 121 passed.
  - `pytest -q --import-mode=importlib`: 5750 passed, 1 skipped.

## MVP-31 — Local Research Experiment Ledger (Complete)

**Version:** 0.30.0-dev → 0.31.0-dev.

**SPEC-032:** `specs/SPEC-032-Local-Research-Experiment-Ledger.md` — implemented across models, engine, writer, and integration tests.

**Commit:** `TBD` — feat: complete MVP-31 local research experiment ledger.

- **MVP-31 Step 1 — Models and Engine (Complete)**
  - `src/hunter/experiment_ledger/__init__.py` — public API exports for models, engine, writer, reason codes, safety constants, and default artifact paths.
  - `src/hunter/experiment_ledger/models.py` — frozen dataclasses: `ExperimentLedgerInput`, `ExperimentRecord`, `ExperimentMetricSnapshot`, `ExperimentComparisonConfig`, `ExperimentComparisonResult`, `ExperimentLedgerReport`, `ExperimentLedgerDataQuality`, `ExperimentLedgerSafetyFlags`; enums `ExperimentState`, `ExperimentReasonCode`; reason-code constants and forbidden-term guard.
  - `src/hunter/experiment_ledger/engine.py` — pure local experiment ledger engine: input validation, deterministic normalization of `BacktestReport`, `ResearchRunResult`, and `ExperimentMetricSnapshot` into `ExperimentRecord` objects, duplicate `experiment_id` detection, optional baseline lookup, metric deltas, summary metrics, and audit-review-only ranking.
  - `tests/test_experiment_ledger/test_models.py` — model validation, safety flags, reason codes.
  - `tests/test_experiment_ledger/test_engine.py` — normalization, comparison, baseline/delta behavior, ranking, fail-closed behavior, determinism, no input mutation.

- **MVP-31 Step 2 — Writer (Complete)**
  - `src/hunter/experiment_ledger/writer.py` — deterministic JSON/CSV/Markdown serialization and atomic writes for `ExperimentLedgerReport`.
  - Includes `experiment_ledger_report_to_dict`, `experiment_ledger_report_to_json_text`, `experiment_ledger_report_to_csv_text`, `experiment_ledger_report_to_markdown_text`, `write_experiment_ledger_report`, and atomic write helpers.
  - Default local artifact paths: `data/experiment_ledger/experiment_ledger.json`, `data/experiment_ledger/experiment_records.csv`, `reports/experiment_ledger/experiment_ledger.md`.
  - Markdown includes H1 title, immediate research-only/audit-only safety notice, and sections for report identity, comparison summary, ranked experiment records, baseline and deltas, data quality, safety flags, reason codes, metadata, and notes.
  - `tests/test_experiment_ledger/test_writer.py` — dict/JSON/CSV/Markdown serialization, atomic writes, determinism, blocked reports, no mutation, opaque metadata.

- **MVP-31 Step 3 — Integration Tests (Complete)**
  - `tests/test_experiment_ledger/test_integration.py` — end-to-end ledger flows with `BacktestReport`, `ResearchRunResult`, and `ExperimentMetricSnapshot` inputs; normalization; baseline and degraded-state tests; ranking behavior; visibility/count tests; unsafe/invalid/duplicate content tests; writer end-to-end tests; determinism; no mutation; public exports; safety boundary assertions.

- **Safety and Boundaries**
  - The experiment ledger is local, call-triggered, deterministic, and audit-only.
  - No scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.
  - No Binance, exchange, API, live data, network, real trading, order, leverage, shorting, or Freqtrade strategy/runtime semantics introduced.
  - Rankings are for human audit-review ordering only; they are not recommendations, signals, or trading decisions.
  - All outputs are human-audit / research-only artifacts; no action commands or feedback into execution paths.
  - Metadata and file-reference strings remain opaque local strings; they are never opened, traversed, validated, fetched, or executed by the ledger engine or writer.

- **Test Results**
  - `pytest tests/test_experiment_ledger -q --import-mode=importlib`: 138 passed.
  - `pytest -q --import-mode=importlib`: 5629 passed, 1 skipped.

## MVP-30 — Local Research Run Orchestrator (Complete)

**Version:** 0.29.0-dev → 0.30.0-dev.

**SPEC-031:** `specs/SPEC-031-Local-Research-Run-Orchestrator.md` — implemented across models, engine, writer, and integration tests.

**Commit:** `TBD` — feat: complete MVP-30 local research run orchestrator.

- **MVP-30 Step 1 — Models and Engine (Complete)**
  - `src/hunter/run_orchestrator/__init__.py` — public API exports for models, engine, writer, reason codes, and safety constants.
  - `src/hunter/run_orchestrator/models.py` — frozen dataclasses: `ResearchRunPlan`, `ResearchRunStep`, `ResearchRunConfig`, `ResearchRunStepResult`, `ResearchRunResult`, `ResearchRunArtifact`, `ResearchRunDataQuality`, `ResearchRunSafetyFlags`; enums `ResearchRunStepKind`, `ResearchRunStepState`, `ResearchRunState`; reason-code constants and forbidden-term guard.
  - `src/hunter/run_orchestrator/engine.py` — pure call-triggered orchestration engine: plan validation, fail-closed dispatch to existing local research engines (backtest, portfolio construction, discovery, reporting CLI sample, audit summaries), deterministic aggregation, safety flags, and reason codes.
  - `tests/test_run_orchestrator/test_models.py` — model validation, safety flags, reason codes.
  - `tests/test_run_orchestrator/test_engine.py` — plan validation, step dispatch, fail-fast / continue modes, fail-closed behavior, unsafe-content blocking, determinism, no input mutation.

- **MVP-30 Step 2 — Writer (Complete)**
  - `src/hunter/run_orchestrator/writer.py` — deterministic JSON/CSV/Markdown serialization and atomic writes for `ResearchRunResult`.
  - Includes `research_run_result_to_dict`, `research_run_result_to_json_text`, `research_run_result_to_csv_text`, `research_run_result_to_markdown_text`, `write_research_run_result`, and atomic write helpers.
  - Default local artifact paths: `data/run_orchestrator/run_summary.json`, `data/run_orchestrator/run_steps.csv`, `reports/run_orchestrator/run_summary.md`.
  - Markdown includes H1 title, immediate research-only/audit-only safety notice, and sections for run summary, data quality, step results, artifacts, safety flags, reason codes, metadata, and notes.
  - `tests/test_run_orchestrator/test_writer.py` — dict/JSON/CSV/Markdown serialization, atomic writes, determinism, blocked/failed runs, no mutation, no file-reference traversal, nested dataclass serialization.

- **MVP-30 Step 3 — Integration Tests (Complete)**
  - `tests/test_run_orchestrator/test_integration.py` — end-to-end runs, backtest step integration, reporting CLI sample step integration, failure/fail-fast/continue behavior, unsafe content blocking, writer end-to-end, determinism, no mutation, public exports, and safety boundaries.

- **MVP-30 Writer Serialization Fix (Complete)**
  - Fixed `writer._serialize_value` to recursively serialize dataclasses, resolving `TypeError: Object of type BacktestRunConfig is not JSON serializable` when writing `ResearchRunResult` from a `BACKTEST` step.
  - Preserved existing enum, datetime, tuple, list, mapping, frozenset, and `MappingProxyType` handling.

- **Safety and Boundaries**
  - The orchestrator is local, call-triggered, deterministic, and audit-only.
  - No scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.
  - No Binance, exchange, API, live data, network, real trading, order, leverage, shorting, or Freqtrade strategy/runtime semantics introduced.
  - All outputs are human-audit / research-only artifacts; no action commands or feedback into execution paths.
  - Metadata and file-reference strings remain opaque local strings; they are never opened, traversed, validated, fetched, or executed by the orchestrator.

- **Test Results**
  - `pytest tests/test_run_orchestrator -q --import-mode=importlib`: 86 passed.
  - `pytest -q --import-mode=importlib`: 5491 passed, 1 skipped.

## MVP-29 — Local Research Reporting CLI (Complete)

**Version:** 0.28.0-dev → 0.29.0-dev.

**SPEC-030:** `specs/SPEC-030-Local-Research-Reporting-CLI.md` — implemented across models, commands, CLI entry, and integration tests.

**Commit:** `TBD` — feat: complete MVP-29 local research reporting CLI.

- **MVP-29 Step 1 — Reporting CLI Models and Commands (Complete)**
  - `src/hunter/reporting_cli/__init__.py` — public API exports including `main`, command runners, constants, and models.
  - `src/hunter/reporting_cli/models.py` — frozen dataclasses, enums, `REPORTING_CLI_REASON_CODES`, `CLIExitCode`, `CLIOutputFormat`, `CLICommandKind`, `CLISafetyFlags`, `CLIArtifactSummary`, `CLIInvocation`, `CLICommandResult`.
  - `src/hunter/reporting_cli/commands.py` — pure deterministic command functions: `run_version_command`, `run_safety_summary_command`, `run_list_artifacts_command`, `run_validate_artifact_paths_command`, `run_render_sample_command`, `dispatch_command`.
  - `src/hunter/reporting_cli/cli.py` — thin callable entry wrapper `main(argv)` with argument parsing, help text, and exit-code dispatch.

- **MVP-29 Step 2 — Callable CLI Entry Wrapper (Complete)**
  - `main(argv)` parses commands and options, builds a `CLIInvocation`, dispatches via `dispatch_command`, and returns a deterministic `int` exit code.
  - Supported commands: `version`, `safety-summary`, `list-artifacts`, `validate-artifact-paths`, `render-sample`.
  - Output formats: `TEXT`, `JSON`, `MARKDOWN` (for `safety-summary`).

- **MVP-29 Step 3 — Integration Tests (Complete)**
  - `tests/test_reporting_cli/test_integration.py` — end-to-end command invocation, version output, safety summary formats, deterministic artifact listing, path validation (safe, traversal, network reference), render-sample dry-run and write behavior, callable `main` entry, and public export coverage.

- **Safety Constraints**
  - Output is a human-audit / research-only artifact only; not a trading signal, not trade approval, not strategy approval, not execution approval, not portfolio approval, not universe approval, and not Freqtrade input.
  - No Freqtrade input, no Binance/API/exchange/live-data connection, no order/execution instructions, no leverage/shorting semantics, no action commands.
  - No feedback into execution, strategy, or portfolio paths.
  - Commands do not read input files, do not follow metadata/file references, and do not validate/traverse opaque strings except as string-only path safety checks.
  - No `__main__.py` or console scripts added; current supported entry is the callable `main(argv)` API.

- **Test Results**
  - Full test suite: 5405 tests passing, 1 skipped using `pytest --import-mode=importlib`.

## MVP-28 — Local Research Backtesting Engine (Complete)

**Version:** 0.27.0-dev → 0.28.0-dev.

**SPEC-029:** `specs/SPEC-029-Local-Research-Backtesting-Engine.md` — implemented across models, engine, writer, and integration tests.

**Commit:** `TBD` — feat: complete MVP-28 local research backtesting engine.

- **MVP-28 Step 1 — Backtest Models and Engine (Complete)**
  - `src/hunter/backtest/__init__.py` — public API exports including engine and writer functions and constants.
  - `src/hunter/backtest/models.py` — frozen dataclasses, enums, reason-code partitions, `FORBIDDEN_BACKTEST_TERMS`, `BacktestState`, `BacktestAllocationMode`, `BacktestInputKind`, `BacktestPriceBar`, `BacktestCandidateDecision`, `BacktestInput`, `BacktestRunConfig`, `BacktestPortfolioSnapshot`, `BacktestCandidateResult`, `BacktestPortfolioResult`, `BacktestDataQuality`, `BacktestSafetyFlags`, `BacktestReport`, plus the fail-closed `BacktestReport.blocked(...)` factory.
  - `src/hunter/backtest/engine.py` — pure local backtest engine: safety-flag construction, forbidden-content detection, config validation, candidate classification, period-return calculation, candidate-level metrics (total return, max drawdown, volatility, win rate, observation count, missing data), simulated allocation weights for `EQUAL_WEIGHT`, `RESEARCH_WEIGHT`, and `CUSTOM_WEIGHT` modes, portfolio equity curve built from the union of included/capped candidate timestamps with no carry-forward, missing bars contributing zero weight/return, portfolio-level metrics derived from the equity curve, data quality, and fail-closed report construction.
  - States: `INCLUDED`, `CAPPED`, `WATCHLIST`, `EXCLUDED`, `INSUFFICIENT_DATA`, `BLOCKED`.
  - Deterministic local research-only backtesting over caller-provided in-memory `BacktestInput` objects and `BacktestPriceBar` price history.
  - `include_excluded_candidates=True` keeps EXCLUDED pairs visible in `BacktestReport.candidate_results`; `include_excluded_candidates=False` omits only EXCLUDED pairs from the candidate results tuple while `portfolio_result` and `data_quality` counts still reflect all inputs.
  - BLOCKED and INSUFFICIENT_DATA candidates always remain visible regardless of the inclusion flag.
  - `block_on_missing_context=False` keeps missing-decision pairs as `INSUFFICIENT_DATA`; `block_on_missing_context=True` marks them as `BLOCKED`.
  - `allow_missing_decision=True` allows candidates with price bars but no decision to be simulated as equal-weight when the allocation mode permits.
  - Rounding policy: raw prices 8 decimals, period returns 8 decimals, sub-metrics 4 decimals, final percentage metrics 2 decimals.
  - Deterministic output ordering by state priority, total return descending, max drawdown ascending, pair ascending.

- **MVP-28 Step 2 — Backtest Writer (Complete)**
  - `src/hunter/backtest/writer.py` — deterministic serialization and atomic writers.
  - `backtest_report_to_dict` / `backtest_report_to_json_text` — deterministic JSON with sorted keys, enums as strings, ISO-8601 datetimes, tuples as lists, mappings as plain dicts.
  - `backtest_report_to_csv_text` — stable column order, one row per candidate, pipe-delimited reason codes and tags, empty cells for `None` values.
  - `backtest_report_to_markdown` — H1 title, explicit research-only safety notice immediately after H1, report identity, portfolio summary, data quality, candidate results, equity curve summary, configuration, reason codes, safety flags, and metadata.
  - `atomic_write_json_backtest_report`, `atomic_write_csv_backtest_report`, `atomic_write_markdown_backtest_report` — temp-file + fsync + `os.replace` atomic writes, parent directory creation.
  - `write_backtest_report` — combined writer producing JSON, CSV, and Markdown.
  - Default output paths:
    - `data/backtest/latest_backtest_report.json`
    - `data/backtest/latest_backtest_results.csv`
    - `reports/backtest/latest_backtest_report.md`

- **MVP-28 Step 3 — Backtest Integration Tests (Complete)**
  - `tests/test_backtest/test_integration.py` — end-to-end report builds, deterministic output, candidate-level metrics, portfolio-level metrics from equity curve, timestamp union alignment, no carry-forward, missing-bar handling, missing/insufficient price history, invalid close rejection, unsafe-content fail-closed behavior, metadata opacity, `volatility_scale_factor` config, `start_timestamp`/`end_timestamp` filtering, JSON/CSV/Markdown writer artifacts, determinism, no-mutation, and public export coverage.

- **Safety Constraints**
  - Output is a human-audit / research-only artifact only; not a trading signal, not trade approval, not strategy approval, not execution approval, not portfolio approval, and not Freqtrade input.
  - No Freqtrade input, no Binance/API/exchange/live-data connection, no order/execution instructions, no leverage/shorting semantics, no action commands.
  - No feedback into execution, strategy, or portfolio paths.
  - Engine and writer do not read input files, do not follow metadata/file references, and do not validate/traverse opaque strings.

- **Test Results**
  - Full test suite: 5299 tests passing, 1 skipped using `pytest --import-mode=importlib`.

## MVP-27 — Portfolio Construction Engine (Complete)

**Version:** 0.26.0-dev → 0.27.0-dev.

**SPEC-028:** `specs/SPEC-028-Portfolio-Construction-Engine.md` — implemented across models, engine, writer, and integration tests.

**Commit:** `TBD` — feat: complete MVP-27 portfolio construction engine.

- **MVP-27 Step 1 — Portfolio Construction Models and Engine (Complete)**
  - `src/hunter/portfolio_construction/__init__.py` — public API exports including engine and writer functions and constants.
  - `src/hunter/portfolio_construction/models.py` — frozen dataclasses, enums, reason-code partitions, `FORBIDDEN_PORTFOLIO_CONSTRUCTION_TERMS`, `PortfolioConstructionConfig`, `PortfolioConstructionSafetyFlags`, `PortfolioConstructionState`, `PortfolioConstructionClassification`, `PortfolioConstructionInputKind`, `PortfolioDiscoverySummary`, `PortfolioConstructionInput`, `PortfolioConstructionScore`, `PortfolioConstructionDataQuality`, `PortfolioConstructionUniverseSummary`, `PortfolioConstructionReport`, plus the fail-closed `PortfolioConstructionReport.blocked(...)` factory.
  - `src/hunter/portfolio_construction/engine.py` — pure local portfolio construction engine: safety-flag construction, forbidden-content detection, discovery sub-scoring, data quality, diversification, cap readiness, filter bonus, allocation score, initial research-weight calculation, max-single-weight cap with deterministic redistribution, candidate classification, universe summary, and fail-closed report construction.
  - States: `INCLUDED`, `CAPPED`, `WATCHLIST`, `EXCLUDED`, `INSUFFICIENT_DATA`, `BLOCKED`.
  - Classifications: `CORE_RESEARCH_ALLOCATION`, `SATELLITE_RESEARCH_ALLOCATION`, `WATCHLIST_ALLOCATION`, `EXCLUDED_BY_CONSTRAINTS`, `INSUFFICIENT_DATA`, `BLOCKED`.
  - Deterministic local research-only portfolio construction over caller-provided in-memory `PortfolioConstructionInput` objects and `PortfolioDiscoverySummary` context.
  - `include_excluded_candidates=True` keeps EXCLUDED pairs visible in `PortfolioConstructionReport.scores`; `include_excluded_candidates=False` omits only EXCLUDED pairs from the scores tuple while `universe_summary` and `data_quality` counts still reflect all inputs.
  - BLOCKED and INSUFFICIENT_DATA candidates always remain visible regardless of the inclusion flag.
  - `block_on_missing_context=False` keeps missing-discovery pairs as `INSUFFICIENT_DATA`; `block_on_missing_context=True` marks them as `BLOCKED`.
  - `block_on_blocked_context=True` keeps blocked discovery pairs as `BLOCKED`; `block_on_blocked_context=False` keeps them visible but blocked reasons are recorded.
  - Rounding policy: allocation score 2 decimals, sub-scores 4 decimals, weights 4 decimals.
  - Deterministic output ordering by state priority, final weight descending, allocation score descending, pair ascending.

- **MVP-27 Step 2 — Portfolio Construction Writer (Complete)**
  - `src/hunter/portfolio_construction/writer.py` — deterministic serialization and atomic writers.
  - `portfolio_construction_report_to_dict` / `portfolio_construction_report_to_json_text` — deterministic JSON with sorted keys, enums as strings, ISO-8601 datetimes, tuples as lists, mappings as plain dicts.
  - `portfolio_construction_report_to_csv_text` — stable column order, one row per allocation score, pipe-delimited reason codes and tags, empty cells for `None` values.
  - `portfolio_construction_report_to_markdown` — H1 title, explicit research-only safety notice immediately after H1, report identity, universe summary, data quality, allocation table, cap diagnostics, reason codes, filter diagnostics, safety flags, and metadata.
  - `atomic_write_json_portfolio_construction_report`, `atomic_write_csv_portfolio_construction_report`, `atomic_write_markdown_portfolio_construction_report` — temp-file + fsync + `os.replace` atomic writes, parent directory creation.
  - `write_portfolio_construction_report` — combined writer producing JSON, CSV, and Markdown.
  - Default output paths:
    - `data/portfolio_construction/latest_portfolio_construction_report.json`
    - `data/portfolio_construction/latest_portfolio_construction_allocations.csv`
    - `reports/portfolio_construction/latest_portfolio_construction_report.md`

- **MVP-27 Step 3 — Portfolio Construction Integration Tests (Complete)**
  - `tests/test_portfolio_construction/test_integration.py` — end-to-end report builds, deterministic output, INCLUDED/CAPPED assertions, WATCHLIST zero-weight assertions, missing-context paths, blocked-context paths, include/excluded behavior, JSON/CSV/Markdown writer artifacts, determinism, and public export coverage.

- **Safety Constraints**
  - Output is a human-audit / research-only artifact only; not a trading signal, not trade approval, not strategy approval, not execution approval, not portfolio/universe approval, and not position sizing.
  - No Freqtrade input, no Binance/API/exchange/live-data connection, no order/execution instructions, no leverage/shorting semantics, no action commands.
  - No feedback into execution, strategy, or portfolio paths.
  - Engine and writer do not read input files, do not follow metadata/file references, and do not validate/traverse opaque strings.

- **Test Results**
  - Full test suite: 5178 tests passing, 1 skipped using `pytest --import-mode=importlib`.

## MVP-26 — Discovery Engine (Complete)

**Version:** 0.25.0-dev → 0.26.0-dev.

**SPEC-027:** `specs/SPEC-027-Discovery-Engine.md` — implemented across models, engine, writer, and integration tests.

**Commit:** `TBD` — feat: complete MVP-26 discovery engine.

- **MVP-26 Step 1 — Discovery Engine Models and Engine (Complete)**
  - `src/hunter/discovery/__init__.py` — public API exports including engine and writer functions.
  - `src/hunter/discovery/models.py` — frozen dataclasses, enums, reason-code partitions, `FORBIDDEN_DISCOVERY_TERMS`, `DiscoveryConfig`, `DiscoverySafetyFlags`, `DiscoveryState`, `DiscoveryClassification`, `DiscoveryInputKind`, `DiscoveryRelativeStrengthSummary`, `DiscoveryOpenInterestSummary`, `DiscoveryInput`, `DiscoveryScore`, `DiscoveryUniverseSummary`, `DiscoveryDataQuality`, `DiscoveryCandidate`, `DiscoveryReport`, plus the fail-closed `DiscoveryReport.blocked(...)` factory.
  - `src/hunter/discovery/engine.py` — pure local combination engine: aggregates already-loaded Relative Strength and Open Interest summaries, computes alignment, data quality, filter bonus, and weighted 0–100 discovery score, classifies candidates, builds universe summary, and constructs safety flags.
  - Candidate states: `CANDIDATE`, `WATCHLIST`, `EXCLUDED`, `INSUFFICIENT_DATA`, `BLOCKED`.
  - Classifications: `STRONG_RESEARCH_CANDIDATE`, `MODERATE_RESEARCH_CANDIDATE`, `WATCHLIST_ONLY`, `EXCLUDED_BY_FILTERS`, `INSUFFICIENT_DATA`, `BLOCKED`.
  - Deterministic local research-only discovery scoring over caller-provided in-memory context summaries.
  - `include_excluded_candidates=True` keeps EXCLUDED pairs visible in `DiscoveryReport.candidates`; `include_excluded_candidates=False` omits only EXCLUDED pairs from the candidates tuple while universe summary counts still reflect all inputs.
  - BLOCKED and INSUFFICIENT_DATA candidates always remain visible regardless of the inclusion flag.
  - Rounding policy: sub-scores 4 decimals, total score 2 decimals.
  - Deterministic output ordering by state priority, total score descending, pair ascending.

- **MVP-26 Step 2 — Discovery Engine Writer (Complete)**
  - `src/hunter/discovery/writer.py` — deterministic serialization and atomic writers.
  - `discovery_report_to_dict` / `discovery_report_to_json_text` — deterministic JSON with sorted keys, enums as strings, ISO-8601 datetimes, tuples as lists, mappings as plain dicts.
  - `discovery_report_to_csv_text` — stable column order, one row per candidate, pipe-delimited reason codes and tags, empty cells for `None` values.
  - `discovery_report_to_markdown` — H1 title, explicit research-only safety notice immediately after H1, report identity, universe summary, data quality, candidate table, reason codes, filter diagnostics, safety flags.
  - `atomic_write_json_discovery_report`, `atomic_write_csv_discovery_report`, `atomic_write_markdown_discovery_report` — temp-file + fsync + `os.replace` atomic writes, parent directory creation.
  - `write_discovery_report` — combined writer producing JSON, CSV, and Markdown.
  - Default output paths:
    - `data/discovery/latest_discovery_report.json`
    - `data/discovery/latest_discovery_candidates.csv`
    - `reports/discovery/latest_discovery_report.md`

- **MVP-26 Step 3 — Discovery Engine Integration Tests (Complete)**
  - `tests/test_discovery/test_integration.py` — end-to-end report, writer artifacts, all classification paths, include/excluded behavior, missing-context paths, blocked-context paths, alignment paths, threshold behavior, unsafe-content paths, determinism, no-mutation, atomic tmp_path writes, human-research safety assertions, and public export coverage.

- **Safety Constraints**
  - Output is a human-audit / research-only artifact only; not a trading signal, not trade approval, not strategy approval, not execution approval, not portfolio/universe approval.
  - No Freqtrade input, no Binance/API/exchange/live-data connection, no order/execution instructions, no leverage/shorting semantics, no action commands.
  - No feedback into execution, strategy, or portfolio paths.
  - Engine and writer do not read input files, do not follow metadata/file references, and do not validate/traverse opaque strings.

- **Test Results**
  - Full test suite: 5020 tests passing, 1 skipped using `pytest --import-mode=importlib`.

## MVP-25 — Open Interest Engine (Complete)

**Version:** 0.24.0-dev → 0.25.0-dev.

**SPEC-026:** `specs/SPEC-026-Open-Interest-Engine.md` — implemented across models, engine, writer, and integration tests.

**Commit:** `TBD` — feat: complete MVP-25 open interest engine.

- **MVP-25 Step 1 — Open Interest Engine Models and Engine (Complete)**
  - `src/hunter/open_interest/__init__.py` — public API exports.
  - `src/hunter/open_interest/models.py` — frozen dataclasses, enums, reason-code partitions, `FORBIDDEN_OPEN_INTEREST_TERMS`, `OpenInterestConfig`, `OpenInterestSafetyFlags`, `OpenInterestState`, `OpenInterestPositioning`, `OpenInterestTrend`, `OpenInterestFundingContext`, `OpenInterestObservation`, `OpenInterestInput`, `OpenInterestPeriodChange`, `OpenInterestScore`, `OpenInterestDataQuality`, `OpenInterestUniverseSummary`, `OpenInterestReport`, plus the fail-closed `OpenInterestReport.blocked(...)` factory.
  - `src/hunter/open_interest/engine.py` — pure local computation engine: OI and price period changes, OI/price positioning classification, OI trend classification, optional caller-provided funding context, weighted 0–100 research score, deterministic universe summary, and safety-flag construction.
  - Deterministic local research-only open interest scoring over caller-provided in-memory OI/price rows.
  - Open-interest period changes across 1d, 3d, 7d, and 14d (configurable) lookback windows, with proportional weight redistribution when a specific window is missing.
  - OI/price positioning categories: `price_up_oi_up`, `price_up_oi_down`, `price_down_oi_up`, `price_down_oi_down`, `mixed`, `insufficient_data`, `blocked`.
  - OI trend categories: `expanding`, `contracting`, `flat`, `unstable`, `insufficient_data`, `blocked`.
  - Optional funding context classification: `positive`, `negative`, `neutral`, `missing`, `insufficient_data`, `blocked`.
  - Rounding policy: raw metrics 8 decimals, sub-scores 4 decimals, total score 2 decimals.
  - Input rows sorted by timestamp ascending before calculations without mutating caller input.
  - Deterministic output ordering by state priority, total score descending, pair ascending.
  - `block_on_missing_data=False` keeps pair as `INSUFFICIENT_DATA`; `block_on_missing_data=True` keeps pair as `BLOCKED`. Pairs are never silently dropped.

- **MVP-25 Step 2 — Open Interest Engine Writer (Complete)**
  - `src/hunter/open_interest/writer.py` — deterministic serialization and atomic writers.
  - `open_interest_report_to_dict` / `open_interest_report_to_json_text` — deterministic JSON with sorted keys, enums as strings, ISO-8601 datetimes, tuples as lists, mappings as plain dicts.
  - `open_interest_report_to_csv_text` — stable column order, one row per score, pipe-delimited reason codes, empty cells for `None` values.
  - `open_interest_report_to_markdown` — H1 title, explicit research-only safety notice immediately after H1, report identity, universe summary, data quality, score table, period changes / positioning summary, funding context summary, reason codes, safety flags.
  - `atomic_write_json_open_interest_report`, `atomic_write_csv_open_interest_report`, `atomic_write_markdown_open_interest_report` — temp-file + fsync + `os.replace` atomic writes, parent directory creation.
  - `write_open_interest_report` — combined writer producing JSON, CSV, and Markdown.
  - Default output paths:
    - `data/open_interest/latest_open_interest_report.json`
    - `data/open_interest/latest_open_interest_scores.csv`
    - `reports/open_interest/latest_open_interest_report.md`

- **MVP-25 Step 3 — Open Interest Engine Integration Tests (Complete)**
  - `tests/test_open_interest/test_integration.py` — end-to-end report, writer artifacts, positioning/trend paths, funding-context paths, insufficient-data paths, unsafe-content paths, determinism, no-mutation, atomic tmp_path writes, human-research safety assertions, and public export coverage.

- **Safety Constraints**
  - Output is a human-audit / research-only artifact only; not a trading signal, not trade approval, not strategy approval, not execution approval, not portfolio/universe approval.
  - No Freqtrade input, no Binance/API/exchange/live-data connection, no order/execution instructions, no leverage/shorting semantics, no action commands.
  - No feedback into execution, strategy, or portfolio paths.
  - Engine and writer do not read input files, do not follow metadata/file references, and do not validate/traverse opaque strings.

- **Test Results**
  - Full test suite: 4835 tests passing, 1 skipped using `pytest --import-mode=importlib`.

## MVP-24 — Relative Strength Engine (Complete)

**Version:** 0.23.0-dev → 0.24.0-dev.

**SPEC-025:** `specs/SPEC-025-Relative-Strength-Engine.md` — implemented across models, engine, writer, and integration tests.

**Commit:** `TBD` — feat: complete MVP-24 relative strength engine.

- **MVP-24 Step 1 — Relative Strength Engine Models and Engine (Complete)**
  - `src/hunter/relative_strength/models.py` — frozen dataclasses, enums, reason codes, forbidden-content detection, `RelativeStrengthConfig`, `RelativeStrengthSafetyFlags`, `RelativeStrengthState`, `RelativeStrengthDecision`, `RelativeStrengthBenchmarkKind`, `RelativeStrengthInput`, `OhlcvRow`, `RelativeStrengthPeriodReturn`, `RelativeStrengthRatioTrend`, `RelativeStrengthScore`, `RelativeStrengthDataQuality`, `RelativeStrengthUniverseSummary`, `RelativeStrengthReport`.
  - `src/hunter/relative_strength/engine.py` — pure local computation engine: period returns, relative returns vs BTC/ETH, Coin/BTC ratio series and ratio trend, rank percentiles with deterministic tie-breaking, weighted total score, universe summary, and safety-flag construction.
  - Deterministic local research-only relative strength scoring over caller-provided in-memory OHLCV rows.
  - Coin/BTC and Coin/ETH relative returns across configured lookback windows.
  - Coin/BTC ratio trend (last ratio, moving-average ratio, slope, trend score).
  - 30-day rank percentile over the supplied universe with tie-breaking.

- **MVP-24 Step 2 — Relative Strength Engine Writer (Complete)**
  - `src/hunter/relative_strength/writer.py` — deterministic serialization and atomic writers.
  - `relative_strength_report_to_dict` / `relative_strength_report_to_json_text` — deterministic JSON with sorted keys, enums as strings, ISO-8601 datetimes, tuples as lists, decimals as floats.
  - `relative_strength_report_to_csv_text` — stable column order, one row per score, pipe-delimited reason codes, empty cells for `None` values.
  - `relative_strength_report_to_markdown` — H1 title, explicit research-only safety notice, report identity, universe summary, data quality, score table, ratio trend summary, safety flags, reason codes.
  - `atomic_write_json_relative_strength_report`, `atomic_write_csv_relative_strength_report`, `atomic_write_markdown_relative_strength_report` — temp-file + fsync + `os.replace` atomic writes, parent directory creation.
  - `write_relative_strength_report` — combined writer producing JSON, CSV, and Markdown.
  - Default output paths:
    - `data/relative_strength/latest_relative_strength_scores.json`
    - `data/relative_strength/latest_relative_strength_scores.csv`
    - `reports/relative_strength/latest_relative_strength_report.md`

- **MVP-24 Step 3 — Relative Strength Engine Integration Tests (Complete)**
  - `tests/test_relative_strength/test_integration.py` — end-to-end report, writer artifacts, missing ETH paths, insufficient-data paths, unsafe-content paths, determinism, no-mutation, atomic tmp_path writes, human-research safety assertions, and public export coverage.

- **Safety Constraints**
  - Output is a human-audit / research-only artifact only; not a trading signal, not trade approval, not strategy approval, not execution approval, not portfolio/universe approval.
  - No Freqtrade input, no Binance/API/exchange/live-data connection, no order/execution instructions, no leverage/shorting semantics, no action commands.
  - No feedback into execution, strategy, or portfolio paths.
  - Writer does not read input files or follow metadata/file references.

- **Test Results**
  - Full test suite: 4628 tests passing, 1 skipped using `pytest --import-mode=importlib`.

## MVP-23 — Local Research Audit Snapshot (Complete)

**Version:** 0.22.0-dev → 0.23.0-dev.

**SPEC-024:** `specs/SPEC-024-Local-Research-Audit-Snapshot.md` — approved with minor notes. No critical issues found.

**Commit:** `TBD` — feat: complete MVP-23 local research audit snapshot.

- **MVP-23 Step 1 — Research Audit Snapshot Models and Engine (Complete)**
  - `src/hunter/research_audit_snapshot/__init__.py` — public API exports.
  - `src/hunter/research_audit_snapshot/models.py` — frozen snapshot dataclasses, enums, reason codes, forbidden snapshot content detection, `AuditSnapshotConfig`, `AuditSnapshotSafetyFlags`, `AuditSnapshotSectionKind`, `AuditSnapshotItemSeverity`, `AuditSnapshotItem`, `AuditSnapshotSection`, `AuditSnapshotSummary`, `AuditSnapshotDataQuality`, `ResearchAuditSnapshot`.
  - `src/hunter/research_audit_snapshot/engine.py` — in-memory snapshot engine functions: `has_unsafe_audit_snapshot_content`, `build_audit_snapshot_safety_flags`, `build_audit_snapshot_item`, `build_audit_snapshot_section`, `build_audit_snapshot_summary`, `build_audit_snapshot_data_quality`, `build_research_audit_snapshot`.
  - `tests/test_research_audit_snapshot/test_models.py` — 60 model tests.
  - `tests/test_research_audit_snapshot/test_engine.py` — 41 engine tests.

- **MVP-23 Step 2 — Research Audit Snapshot Writer (Complete)**
  - `src/hunter/research_audit_snapshot/writer.py` — JSON/Markdown serialization, atomic file writing.
  - `src/hunter/research_audit_snapshot/__init__.py` — updated with writer exports.
  - `tests/test_research_audit_snapshot/test_writer.py` — 52 writer tests.
  - Default JSON path: `data/research_audit_snapshot/latest_research_audit_snapshot.json`.
  - Default Markdown path: `reports/research_audit_snapshot/latest_research_audit_snapshot.md`.
  - `research_audit_snapshot_to_dict()` — deterministic JSON-safe serialization.
  - `research_audit_snapshot_to_markdown()` — human-readable Markdown with explicit safety notice placed immediately after the fixed H1 title and before identity, sections, items, references, metadata, or details.
  - `atomic_write_json_research_audit_snapshot()` / `atomic_write_markdown_research_audit_snapshot()` — atomic writes with temp file + flush + fsync + os.replace.
  - `write_research_audit_snapshot()` — writes both JSON and Markdown, returns paths.

- **MVP-23 Step 3 — Research Audit Snapshot Integration Tests (Complete)**
  - `tests/test_research_audit_snapshot/test_integration.py` — 85 integration tests.
  - End-to-end flows: build → serialize → write → validate, CURRENT snapshot, BLOCK snapshot for missing/unsafe/invalid artifacts, STALE snapshot and `block_on_stale=True` escalation, INCOMPLETE snapshot and `block_on_incomplete=True` escalation, UNKNOWN blocked factory behavior, deterministic section ordering (OVERVIEW → VERSION_STATE → ARTIFACT_STATE → QUALITY_STATE → OPEN_ITEMS → SAFETY_BOUNDARIES → HUMAN_AUDIT_GUIDE → APPENDIX_REFERENCES), deterministic item ordering (severity → MVP number → insertion order), JSON round-trip, Markdown safety notice first, Markdown section/item/reference/reason-code rendering, file references as plain strings, no production path writes, no action commands emitted, no network calls, no trading logic, no execution feedback, no Freqtrade/Binance/exchange/live/leverage/shorting references.
  - **Whole MVP-23 Review:** APPROVED WITH MINOR NOTES. No critical issues found.

- **MVP-23 Step 4 — Final Validation and Version Bump (Complete)**
  - Verdict: PASS. No blocking defects.
  - Version bumped to 0.23.0-dev.
  - All safety invariants verified.

- **Tests:**
  - 60 model + 41 engine + 52 writer + 85 integration = **238 research_audit_snapshot tests** total.
  - **Full suite: 4499 tests passing, 1 skipped** using `pytest --import-mode=importlib`.

- **Safety:**
  - Research audit snapshot is a human-audit / contractor-handoff artifact only.
  - Not a release approval. Not a deployment approval.
  - Not a trading signal. Not a trade approval.
  - Not execution readiness. Not strategy readiness.
  - Not transaction permission.
  - Must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.
  - No audit-snapshot feedback into execution paths.
  - No report/operator/index/search/bundle/chronicle/digest/quality-gate/handoff/archive-manifest/release-notes/audit-catalog/audit-closure/audit-snapshot feedback into execution paths.
  - No Binance, exchange, API keys, live trading, real orders, leverage, shorting.
  - File references and metadata strings are not traversed, opened, followed, validated, or executed.
  - Referenced artifact files are not read.
  - Human audit guide is advisory-only and not gating.
  - No action commands are emitted.
  - No release/deployment checklist semantics.
  - No Web UI, dashboard, database persistence, server/API/auth.
  - Not a runtime registry, indexer, crawler, scheduler, routing layer, dashboard, database, API, event store, or task runner.

- **Known Non-Blocking Note:**
  - `data_quality.sections_present` currently reports `0` and `sections_missing` reports `8` for successful snapshots because `build_audit_snapshot_data_quality` does not receive the section list in its SPEC-024 signature. The behavior is fail-closed (safe) and SPEC-compliant; a future cleanup may refine the metric so successful snapshots report `sections_present=8` and `sections_missing=0`.

- **Next:**
  - MVP-24 planning / SPEC-025 Relative Strength Engine, not started.

---

## MVP-22 — Local Research Audit Closure Report (Complete)

**Version:** 0.21.0-dev → 0.22.0-dev.

**SPEC-023:** `specs/SPEC-023-Local-Research-Audit-Closure-Report.md` — approved with minor notes. No critical issues found.

**Commit:** `TBD` — feat: complete MVP-22 local research audit closure report.

- **MVP-22 Step 1 — Research Audit Closure Models and Engine (Complete)**
  - `src/hunter/research_audit_closure/__init__.py` — public API exports.
  - `src/hunter/research_audit_closure/models.py` — frozen closure dataclasses, enums, reason codes, forbidden closure content detection, `AuditClosureConfig`, `AuditClosureSafetyFlags`, `AuditClosureSectionKind`, `AuditClosureFindingSeverity`, `AuditClosureState`, `AuditClosureKind`, `AuditClosureFinding`, `AuditClosureSection`, `AuditClosureSummary`, `AuditClosureDataQuality`, `ResearchAuditClosureReport`.
  - `src/hunter/research_audit_closure/engine.py` — in-memory closure engine functions: `has_unsafe_audit_closure_content`, `build_audit_closure_safety_flags`, `build_audit_closure_finding`, `build_audit_closure_section`, `build_audit_closure_summary`, `build_audit_closure_data_quality`, `build_research_audit_closure_report`.
  - `tests/test_research_audit_closure/test_models.py` — model tests.
  - `tests/test_research_audit_closure/test_engine.py` — engine tests.

- **MVP-22 Step 2 — Research Audit Closure Writer (Complete)**
  - `src/hunter/research_audit_closure/writer.py` — JSON/Markdown serialization, atomic file writing.
  - `src/hunter/research_audit_closure/__init__.py` — updated with writer exports.
  - `tests/test_research_audit_closure/test_writer.py` — writer tests.
  - Default JSON path: `data/research_audit_closure/latest_research_audit_closure_report.json`.
  - Default Markdown path: `reports/research_audit_closure/latest_research_audit_closure_report.md`.
  - `research_audit_closure_report_to_dict()` — deterministic JSON-safe serialization.
  - `research_audit_closure_report_to_markdown()` — human-readable Markdown with explicit safety notice.
  - `atomic_write_json_research_audit_closure_report()` / `atomic_write_markdown_research_audit_closure_report()` — atomic writes with temp file + fsync + os.replace.
  - `write_research_audit_closure_report()` — writes both JSON and Markdown, returns paths.

- **MVP-22 Step 3 — Research Audit Closure Integration Tests (Complete)**
  - `tests/test_research_audit_closure/test_integration.py` — 42 integration tests (after Step 3.1 cleanup).
  - End-to-end flows: build → serialize → write → validate, READY closure report, BLOCK closure report for missing/unsafe/invalid artifacts, INCOMPLETE closure report with `block_on_incomplete=True`, UNKNOWN blocked factory behavior, deterministic section ordering, deterministic finding ordering (severity → MVP number → insertion order), deterministic `closure_id` and `generated_at`, JSON round-trip, Markdown safety notice first, Markdown section/finding/reference/reason-code rendering, file references as plain strings, no production path writes, no action commands emitted, no network calls, no trading logic, no execution feedback, no Freqtrade/Binance/exchange/live/leverage/shorting references.
  - **Z.ai Step 3 Review:** APPROVED with minor notes. No critical issues found.

- **MVP-22 Step 3.1 — Integration Test Cleanup (Complete)**
  - Fixed logically inverted release/deployment checklist assertion to check for positive checklist semantics (`"is a release checklist" not in md.lower()`).
  - Added `test_blocked_for_unsafe_backlog_notes` — engine-level unsafe backlog note rejection.
  - Added `test_blocked_for_unsafe_references` — engine-level unsafe reference string rejection.
  - Added `test_incomplete_state_with_block_on_incomplete` — `AuditClosureState.INCOMPLETE` path coverage.
  - Expanded `test_default_safety_flags_are_fail_closed` with additional execution/strategy/exchange/file-ref/event-store/task-runner safety flags.

- **MVP-22 Step 4 — Final Validation and Version Bump (Complete)**
  - Verdict: PASS. No defects found.
  - Version bumped to 0.22.0-dev.
  - All safety invariants verified.

- **Tests:**
  - 183 research_audit_closure tests total.
  - **Full suite: 4261 tests passing, 1 skipped** using `pytest --import-mode=importlib`.

- **Safety:**
  - Research audit closure report is a human-audit / contractor-handoff artifact only.
  - Not a release approval. Not a deployment approval.
  - Not a trading signal. Not a trade approval.
  - Not execution approval. Not strategy approval.
  - Not transaction permission.
  - Must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.
  - No audit-closure feedback into execution paths.
  - No report/operator/index/search/bundle/chronicle/digest/quality-gate/handoff/archive-manifest/release-notes/audit-catalog/audit-closure feedback into execution paths.
  - No Binance, exchange, API keys, live trading, real orders, leverage, shorting.
  - File references and metadata strings are not traversed, opened, followed, validated, or executed.
  - Referenced artifact files are not read.
  - Human archival guide is advisory-only and not gating.
  - No action commands are emitted.
  - No release/deployment checklist semantics.
  - No Web UI, dashboard, database persistence, server/API/auth.
  - Not a runtime registry, indexer, crawler, scheduler, routing layer, dashboard, database, API, event store, or task runner.

- **Next:**
  - MVP-23 planning, not started.

---

## MVP-21 — Local Research Audit Catalog (Complete)

**Version:** 0.20.0-dev → 0.21.0-dev.

**SPEC-022:** `specs/SPEC-022-Local-Research-Audit-Catalog.md` — approved with no critical issues.

**Commit:** `TBD` — feat: complete MVP-21 local research audit catalog.

- **MVP-21 Step 1 — Research Audit Catalog Models and Engine (Complete)**
  - `src/hunter/research_audit_catalog/__init__.py` — public API exports.
  - `src/hunter/research_audit_catalog/models.py` — frozen catalog dataclasses, enums, reason codes, forbidden catalog content detection, `CatalogArtifactKind`, `CatalogState`, `CatalogConfig`, `CatalogSafetyFlags`, `CatalogEntry`, `CatalogSummary`, `CatalogDataQuality`, `ResearchCatalog`.
  - `src/hunter/research_audit_catalog/engine.py` — in-memory catalog engine functions: `has_unsafe_audit_catalog_content`, `build_audit_catalog_safety_flags`, `build_audit_catalog_entry`, `build_audit_catalog_summary`, `build_audit_catalog_data_quality`, `build_research_audit_catalog`.
  - `tests/test_research_audit_catalog/test_models.py` — model tests.
  - `tests/test_research_audit_catalog/test_engine.py` — engine tests.

- **MVP-21 Step 2 — Research Audit Catalog Writer (Complete)**
  - `src/hunter/research_audit_catalog/writer.py` — JSON/Markdown serialization, atomic file writing.
  - `src/hunter/research_audit_catalog/__init__.py` — updated with writer exports.
  - `tests/test_research_audit_catalog/test_writer.py` — writer tests.
  - Default JSON path: `data/research_audit_catalog/latest_research_audit_catalog.json`.
  - Default Markdown path: `reports/research_audit_catalog/latest_research_audit_catalog.md`.
  - `research_audit_catalog_to_dict()` — deterministic JSON-safe serialization.
  - `research_audit_catalog_to_markdown()` — human-readable Markdown with explicit safety notice.
  - `atomic_write_json_research_audit_catalog()` / `atomic_write_markdown_research_audit_catalog()` — atomic writes with temp file + fsync + os.replace.
  - `write_research_audit_catalog()` — writes both JSON and Markdown, returns paths.

- **MVP-21 Step 3 — Research Audit Catalog Integration Tests (Complete)**
  - `tests/test_research_audit_catalog/test_integration.py` — 28 integration tests.
  - End-to-end flows: build → serialize → write → validate, READY catalog, advisory cross-kind artifact_id overlap, BLOCK catalog for duplicate entry_id / missing layers / invalid artifacts, fail-closed unsafe content rejection, fail-closed unsafe safety flags, empty catalog customization, all 11 artifact layers coverage, summary and data quality public fields, deterministic entry ordering, deterministic catalog_id, JSON round-trip, Markdown safety notice first, Markdown artifact/reference/state/reason-code rendering, file references as plain strings, no production path writes, no action commands emitted, no network calls, no trading logic, no execution feedback, no Freqtrade/Binance/exchange/live/leverage/shorting references.
  - **Z.ai Step 3 Review:** APPROVED with minor notes. No critical issues found.

- **MVP-21 Step 3.1 — Integration Test Cleanup (Complete)**
  - Fixed incorrect inline `spec_reference` formula in `test_build_from_fake_artifacts` to use canonical `CATALOG_ARTIFACT_SPEC_REFERENCE` mapping.
  - Removed unused `timedelta` and `MappingProxyType` imports.
  - Added `TestFullLayerCoverage.test_all_eleven_kinds_produce_full_coverage` — one entry per `CatalogArtifactKind`, asserting full layer coverage and kind counts.

- **MVP-21 Step 4 — Final Validation and Version Bump (Complete)**
  - Verdict: PASS. No defects found.
  - Version bumped to 0.21.0-dev.
  - All safety invariants verified.

- **Tests:**
  - 157 research_audit_catalog tests total.
  - **Full suite: 4078 tests passing, 1 skipped** using `pytest --import-mode=importlib`.

- **Safety:**
  - Research audit catalog is a human-audit / contractor-handoff artifact only.
  - Not a release approval. Not a deployment approval.
  - Not a trading signal. Not a trade approval.
  - Not execution approval. Not strategy approval.
  - Not transaction permission.
  - Must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.
  - No audit-catalog feedback into execution paths.
  - No report/operator/index/search/bundle/chronicle/digest/quality-gate/handoff/archive-manifest/release-notes/audit-catalog feedback into execution paths.
  - No Binance, exchange, API keys, live trading, real orders, leverage, shorting.
  - File references and metadata strings are not traversed, opened, followed, validated, or executed.
  - Referenced artifact files are not read.
  - Human audit guide is advisory-only and not gating.
  - No action commands are emitted.
  - No release/deployment checklist semantics.
  - No Web UI, dashboard, database persistence, server/API/auth.
  - Not a runtime registry, indexer, crawler, scheduler, routing layer, dashboard, database, API, event store, or task runner.

- **Future Cleanup (Backlog, not a Step 4 blocker):**
  - Review `EMPTY_CATALOG` reason code reachability. Current engine emits `MISSING_ARTIFACTS` for empty input when `block_on_empty=True` and produces a READY empty catalog when `block_on_empty=False`; `EMPTY_CATALOG` is defined but not emitted. This is a non-blocking spec/engine alignment item for future cleanup/spec refinement.

## MVP-20 — Local Research Release Notes / Audit Change Summary (Complete)

**Version:** 0.19.0-dev → 0.20.0-dev.

**SPEC-021:** `specs/SPEC-021-Local-Research-Release-Notes-Audit-Change-Summary.md` — approved with no critical issues.

**Commit:** `TBD` — feat: complete MVP-20 local research release notes / audit change summary.

- **MVP-20 Step 1 — Research Release Notes Models and Engine (Complete)**
  - `src/hunter/research_release_notes/__init__.py` — public API exports.
  - `src/hunter/research_release_notes/models.py` — frozen release notes dataclasses, enums, reason codes, forbidden release notes content detection, `ReleaseNotesConfig`, `ReleaseNotesSafetyFlags`, `ReleaseNotesSectionKind`, `ReleaseNotesChangeSeverity`, `ReleaseNotesState`, `ReleaseNotesChangeItem`, `ReleaseNotesSection`, `ReleaseNotesSummary`, `ReleaseNotesDataQuality`, `ResearchReleaseNotes`.
  - `src/hunter/research_release_notes/engine.py` — in-memory release notes engine functions: `has_unsafe_release_notes_content`, `build_release_notes_safety_flags`, `build_release_notes_change_item`, `build_release_notes_section`, `build_release_notes_summary`, `build_release_notes_data_quality`, `build_research_release_notes`.
  - `tests/test_research_release_notes/test_models.py` — model tests.
  - `tests/test_research_release_notes/test_engine.py` — engine tests.

- **MVP-20 Step 2 — Research Release Notes Writer (Complete)**
  - `src/hunter/research_release_notes/writer.py` — JSON/Markdown serialization, atomic file writing.
  - `src/hunter/research_release_notes/__init__.py` — updated with writer exports.
  - `tests/test_research_release_notes/test_writer.py` — writer tests.
  - Default JSON path: `data/research_release_notes/latest_research_release_notes.json`.
  - Default Markdown path: `reports/research_release_notes/latest_research_release_notes.md`.
  - `research_release_notes_to_dict()` — deterministic JSON-safe serialization.
  - `research_release_notes_to_markdown()` — human-readable Markdown with explicit safety notice.
  - `atomic_write_json_research_release_notes()` / `atomic_write_markdown_research_release_notes()` — atomic writes with temp file + fsync + os.replace.
  - `write_research_release_notes()` — writes both JSON and Markdown, returns paths.

- **MVP-20 Step 3 — Research Release Notes Integration Tests (Complete)**
  - `tests/test_research_release_notes/test_integration.py` — 46 integration tests.
  - End-to-end flows: build → serialize → write → validate, READY release notes, WARN release notes for empty required sections, BLOCK release notes for missing/unsafe/unresolved-blocker artifacts, fail-closed UNKNOWN handling, required_sections customization, human review guide advisory semantics, summary counts, data quality public fields, all output safety flags, document notes disclaimers, deterministic section ordering, deterministic change item ordering (severity then MVP), insertion-order tiebreak, deterministic release_notes_id, JSON round-trip, Markdown safety notice first, Markdown section/change-item/reference rendering, file references as plain strings, no production path writes, no action commands emitted, no network calls, no trading logic, no execution feedback, no Freqtrade/Binance/exchange/live/leverage/shorting references.
  - **Z.ai Step 3 Review:** APPROVED. No critical issues found.

- **MVP-20 Step 4 — Final Validation and Version Bump (Complete)**
  - Verdict: PASS. No defects found.
  - Version bumped to 0.20.0-dev.
  - All safety invariants verified.

- **Tests:**
  - 157 research_release_notes tests total.
  - **Full suite: 3921 tests passing, 1 skipped** using `pytest --import-mode=importlib`.

- **Safety:**
  - Research release notes / audit change summary is a human-audit / contractor-handoff artifact only.
  - Not a release approval. Not a deployment approval. Not a publish approval.
  - Not a trading signal. Not a trade approval.
  - Not execution readiness. Not strategy readiness.
  - Not transaction permission.
  - Must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.
  - No release-notes feedback into execution paths.
  - No report/operator/index/search/bundle/chronicle/digest/quality-gate/handoff/archive-manifest/release-notes feedback into execution paths.
  - No Binance, exchange, API keys, live trading, real orders, leverage, shorting.
  - File references and metadata strings are not traversed, opened, followed, validated, or executed.
  - Referenced artifact files are not read.
  - Human review guide is advisory-only and not gating.
  - No action commands are emitted.
  - No release/deployment checklist semantics.
  - No Web UI, dashboard, database persistence, server/API/auth.
  - No database, event store, scheduler, routing layer, indexer, crawler, runtime registry, task runner, or feedback layer.

- **Next:**
  - MVP-21 planning, not started.

---

## MVP-19 — Local Research Archive Manifest (Complete)

**Version:** 0.18.0-dev → 0.19.0-dev.

**SPEC-020:** `specs/SPEC-020-Local-Research-Archive-Manifest.md` — approved with no critical issues.

**Commit:** `TBD` — feat: complete MVP-19 local research archive manifest.

- **MVP-19 Step 1 — Research Archive Manifest Models and Engine (Complete)**
  - `src/hunter/research_archive_manifest/__init__.py` — public API exports.
  - `src/hunter/research_archive_manifest/models.py` — frozen archive manifest dataclasses, enums, 34 reason codes, forbidden archive manifest content detection, `ArchiveManifestConfig`, `ArchiveManifestSafetyFlags`, `ArchiveArtifactFamily`, `ArchiveManifestState`, `ArchiveArtifactEntry`, `ArchiveManifestSummary`, `ArchiveManifestDataQuality`, `ResearchArchiveManifest`.
  - `src/hunter/research_archive_manifest/engine.py` — in-memory archive manifest engine functions: `has_unsafe_archive_manifest_content`, `build_archive_manifest_safety_flags`, `build_archive_artifact_entry`, `build_archive_manifest_summary`, `build_archive_manifest_data_quality`, `build_research_archive_manifest`.
  - `tests/test_research_archive_manifest/test_models.py` — model tests.
  - `tests/test_research_archive_manifest/test_engine.py` — engine tests.

- **MVP-19 Step 2 — Research Archive Manifest Writer (Complete)**
  - `src/hunter/research_archive_manifest/writer.py` — JSON/Markdown serialization, atomic file writing.
  - `src/hunter/research_archive_manifest/__init__.py` — updated with writer exports.
  - `tests/test_research_archive_manifest/test_writer.py` — writer tests.
  - Default JSON path: `data/research_archive_manifest/latest_research_archive_manifest.json`.
  - Default Markdown path: `reports/research_archive_manifest/latest_research_archive_manifest.md`.
  - `research_archive_manifest_to_dict()` — deterministic JSON-safe serialization.
  - `research_archive_manifest_to_markdown()` — human-readable Markdown with explicit safety notice.
  - `atomic_write_json_research_archive_manifest()` / `atomic_write_markdown_research_archive_manifest()` — atomic writes with temp file + fsync + os.replace.
  - `write_research_archive_manifest()` — writes both JSON and Markdown, returns paths.

- **MVP-19 Step 3 — Research Archive Manifest Integration Tests (Complete)**
  - `tests/test_research_archive_manifest/test_integration.py` — 42 integration tests.
  - End-to-end flows: build → serialize → write → validate, READY manifest, WARN manifest for stale artifacts, BLOCK manifest for missing/unsafe/unresolved-blocker artifacts, UNKNOWN handling, block_on_unknown True/False, required_families customization, optional family None handling, summary counts, data quality public fields, safety flags, manifest notes disclaimers, deterministic family ordering, deterministic manifest_id, JSON round-trip, Markdown safety notice, Markdown family/reference/state/reason-code rendering, file references as plain strings, no production path writes, no network calls, no trading logic, no execution feedback, no Freqtrade/Binance/exchange/live/leverage/shorting references.
  - **Z.ai Step 3 Review:** APPROVED. No critical issues found.

- **MVP-19 Step 4 — Final Validation and Version Bump (Complete)**
  - Verdict: PASS. No defects found.
  - Version bumped to 0.19.0-dev.
  - All safety invariants verified.

- **Tests:**
  - 164 research_archive_manifest tests total.
  - **Full suite: 3764 tests passing, 1 skipped** using `pytest --import-mode=importlib`.

- **Safety:**
  - Research archive manifest is a human-audit inventory artifact only.
  - Not a trading signal. Not a trade approval.
  - Not execution readiness. Not strategy readiness.
  - Not release/deployment approval. Not transaction permission.
  - Must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.
  - No archive manifest feedback into execution paths.
  - No report/operator/index/search/bundle/chronicle/digest/quality-gate/handoff/archive-manifest feedback into execution paths.
  - No Binance, exchange, API keys, live trading, real orders, leverage, shorting.
  - File references and metadata strings are not traversed, opened, followed, validated, or executed.
  - Referenced artifact files are not read.
  - No Web UI, dashboard, database persistence, server/API/auth.
  - No database, event store, scheduler, routing layer, or feedback layer.

- **Next:**
  - MVP-20 planning, not started.

---

## MVP-18 — Local Research Handoff Packet (Complete)

**Version:** 0.17.0-dev → 0.18.0-dev.

**SPEC-019:** `specs/SPEC-019-Local-Research-Handoff-Packet.md` — approved with no critical issues.

**Commit:** `TBD` — feat: complete MVP-18 local research handoff packet.

- **MVP-18 Step 1 — Research Handoff Models and Engine (Complete)**
  - `src/hunter/research_handoff/__init__.py` — public API exports.
  - `src/hunter/research_handoff/models.py` — frozen handoff dataclasses, enums, 32 reason codes, forbidden handoff content detection, `HandoffConfig`, `HandoffSafetyFlags`, `HandoffPacketKind`, `HandoffState`, `HandoffSection`, `HandoffSummary`, `HandoffDataQuality`, `ResearchHandoffPacket`.
  - `src/hunter/research_handoff/engine.py` — in-memory handoff engine functions: `has_unsafe_handoff_content`, `build_handoff_safety_flags`, `build_handoff_section`, `build_handoff_summary`, `build_handoff_data_quality`, `build_research_handoff_packet`.
  - `tests/test_research_handoff/test_models.py` — model tests.
  - `tests/test_research_handoff/test_engine.py` — engine tests.

- **MVP-18 Step 2 — Research Handoff Writer (Complete)**
  - `src/hunter/research_handoff/writer.py` — JSON/Markdown serialization, atomic file writing.
  - `src/hunter/research_handoff/__init__.py` — updated with writer exports.
  - `tests/test_research_handoff/test_writer.py` — writer tests.
  - Default JSON path: `data/research_handoff/latest_research_handoff_packet.json`.
  - Default Markdown path: `reports/research_handoff/latest_research_handoff_packet.md`.
  - `research_handoff_packet_to_dict()` — deterministic JSON-safe serialization.
  - `research_handoff_packet_to_markdown()` — human-readable Markdown with explicit safety notice.
  - `atomic_write_json_research_handoff_packet()` / `atomic_write_markdown_research_handoff_packet()` — atomic writes with temp file + fsync + os.replace.
  - `write_research_handoff_packet()` — writes both JSON and Markdown, returns paths.

- **MVP-18 Step 3 — Research Handoff Integration Tests (Complete)**
  - `tests/test_research_handoff/test_integration.py` — 25 integration tests.
  - End-to-end flows: build → serialize → write → validate, READY packet, WARN packet for stale artifacts, BLOCK packet for blocked/missing/unresolved-blocker sections, UNKNOWN handling, quality gate verdict extraction, deterministic section ordering, deterministic `packet_id` and `generated_at`, JSON round-trip, Markdown safety notice, Markdown sections as plain text, file references as plain strings, no production path writes, no network calls, no trading logic, no execution feedback, no Freqtrade/Binance/exchange/live/leverage/shorting references.
  - **Z.ai Step 3 Review:** APPROVED. No critical issues found.

- **MVP-18 Step 4 — Final Validation and Version Bump (Complete)**
  - Verdict: PASS. No defects found.
  - Version bumped to 0.18.0-dev.
  - All safety invariants verified.

- **Tests:**
  - 146 research_handoff tests total.
  - **Full suite: 3600 tests passing, 1 skipped** using `pytest --import-mode=importlib`.

- **Safety:**
  - Research handoff packet is a human-audit / contractor-handoff artifact only.
  - Not a trading signal. Not a trade approval.
  - Not execution readiness. Not strategy readiness.
  - Not release/deployment approval. Not transaction permission.
  - Must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.
  - No handoff feedback into execution paths.
  - No report/operator/index/search/bundle/chronicle/digest/quality-gate/handoff feedback into execution paths.
  - No Binance, exchange, API keys, live trading, real orders, leverage, shorting.
  - File references and metadata strings are not traversed, opened, followed, validated, or executed.
  - No Web UI, dashboard, database persistence, server/API/auth.
  - No database, event store, scheduler, routing layer, or feedback layer.

- **Next:**
  - MVP-19 planning, not started.

---

## MVP-17 — Local Research Quality Gate / Audit Readiness (Complete)

**Version:** 0.16.0-dev → 0.17.0-dev.

**SPEC-018:** `specs/SPEC-018-Local-Research-Quality-Gate-Audit-Readiness.md` — approved with one minor source defect found and fixed before Step 4.

**Commit:** `TBD` — feat: complete MVP-17 local research quality gate / audit readiness.

- **MVP-17 Step 1 — Research Quality Gate Models and Engine (Complete)**
  - `src/hunter/research_quality_gate/__init__.py` — public API exports.
  - `src/hunter/research_quality_gate/models.py` — frozen quality gate dataclasses, enums, 29 reason codes, forbidden quality gate content detection, `QualityGateConfig`, `QualityGateSafetyFlags`, `QualityGateCheck`, `QualityGateCheckKind`, `QualityGateSummary`, `QualityGateDataQuality`, `ResearchQualityGate`.
  - `src/hunter/research_quality_gate/engine.py` — in-memory quality gate engine functions: `has_unsafe_quality_gate_content`, `build_quality_gate_safety_flags`, `build_quality_gate_check`, `build_quality_gate_summary`, `build_quality_gate_data_quality`, `build_research_quality_gate`.
  - `tests/test_research_quality_gate/test_models.py` — model tests.
  - `tests/test_research_quality_gate/test_engine.py` — engine tests.

- **MVP-17 Step 2 — Research Quality Gate Writer (Complete)**
  - `src/hunter/research_quality_gate/writer.py` — JSON/Markdown serialization, atomic file writing.
  - `src/hunter/research_quality_gate/__init__.py` — updated with writer exports.
  - `tests/test_research_quality_gate/test_writer.py` — writer tests.
  - Default JSON path: `data/research_quality_gate/latest_research_quality_gate.json`.
  - Default Markdown path: `reports/research_quality_gate/latest_research_quality_gate.md`.
  - `research_quality_gate_to_dict()` — deterministic JSON-safe serialization.
  - `research_quality_gate_to_markdown()` — human-readable Markdown with explicit safety notice.
  - `atomic_write_json_research_quality_gate()` / `atomic_write_markdown_research_quality_gate()` — atomic writes with temp file + fsync + os.replace.
  - `write_research_quality_gate()` — writes both JSON and Markdown, returns paths.

- **MVP-17 Step 3 — Research Quality Gate Integration Tests (Complete)**
  - `tests/test_research_quality_gate/test_integration.py` — 31 integration tests.
  - End-to-end flows: build → serialize → write → validate, PASS gate, WARN gate for non-blocking issues, BLOCK gate for blocked/missing/unsafe checks, UNKNOWN gate, deterministic check ordering, deterministic `gate_id` and `generated_at`, JSON round-trip, Markdown safety notice, Markdown checks as plain text, file references as plain strings, no production path writes, no network calls, no trading logic, no execution feedback, no Freqtrade/Binance/exchange/live/leverage/shorting references.
  - **Z.ai Step 3 Review:** APPROVED. One minor pre-existing source defect identified and fixed before Step 4.

- **Pre-Step 4 Source Fix (Complete)**
  - `engine._is_blocking_reason` aligned with canonical `QUALITY_GATE_BLOCKING_REASON_CODES` from `models.py`.
  - `UNRESOLVED_BLOCKERS` is now included in gate-level `ResearchQualityGate.reason_codes` when present.
  - `STALE_ARTIFACT` remains non-blocking per SPEC-018 §3.3 intent.
  - `EMPTY_GATE` remains fail-closed.
  - Added focused engine tests covering the fix.

- **MVP-17 Step 4 — Final Validation and Version Bump (Complete)**
  - Verdict: PASS. No defects found after source fix.
  - Version bumped to 0.17.0-dev.
  - All safety invariants verified.

- **Tests:**
  - 152 research_quality_gate tests total.
  - **Full suite: 3454 tests passing, 1 skipped** using `pytest --import-mode=importlib`.

- **Safety:**
  - Research quality gate is a human-audit artifact only.
  - Not a trading signal. Not a trade approval.
  - Not execution readiness. Not strategy readiness.
  - Not release/deployment approval. Not transaction permission.
  - Must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.
  - No quality gate feedback into execution paths.
  - No report/operator/index/search/bundle/chronicle/digest/quality-gate feedback into execution paths.
  - No Binance, exchange, API keys, live trading, real orders, leverage, shorting.
  - File references and metadata strings are not traversed, opened, followed, validated, or executed.
  - No Web UI, dashboard, database persistence, server/API/auth.
  - No database, event store, scheduler, routing layer, or feedback layer.

- **Next:**
  - MVP-18 planning, not started.

---

## MVP-16 — Local Research Digest / Executive Summary (Complete)

**Version:** 0.15.0-dev → 0.16.0-dev.

**SPEC-017:** `specs/SPEC-017-Local-Research-Digest-Executive-Summary.md` — approved with no critical issues.

**Commit:** `TBD` — feat: complete MVP-16 local research digest / executive summary.

- **MVP-16 Step 1 — Research Digest Models and Engine (Complete)**
  - `src/hunter/research_digest/__init__.py` — public API exports.
  - `src/hunter/research_digest/models.py` — frozen digest dataclasses, enums, 17 reason codes, forbidden digest content detection, `DigestConfig`, `DigestSafetyFlags`, `DigestSection`, `DigestSectionKind`, `DigestSummary`, `DigestDataQuality`, `ResearchDigest`.
  - `src/hunter/research_digest/engine.py` — in-memory digest engine functions: `has_unsafe_digest_content`, `build_digest_safety_flags`, `build_digest_section`, `build_digest_summary`, `build_digest_data_quality`, `build_research_digest`.
  - `tests/test_research_digest/test_models.py` — model tests.
  - `tests/test_research_digest/test_engine.py` — engine tests.

- **MVP-16 Step 2 — Research Digest Writer (Complete)**
  - `src/hunter/research_digest/writer.py` — JSON/Markdown serialization, atomic file writing.
  - `src/hunter/research_digest/__init__.py` — updated with writer exports.
  - `tests/test_research_digest/test_writer.py` — writer tests.
  - Default JSON path: `data/research_digest/latest_research_digest.json`.
  - Default Markdown path: `reports/research_digest/latest_research_digest.md`.
  - `research_digest_to_dict()` — deterministic JSON-safe serialization.
  - `research_digest_to_markdown()` — human-readable Markdown with explicit safety notice.
  - `atomic_write_json_research_digest()` / `atomic_write_markdown_research_digest()` — atomic writes with temp file + fsync + os.replace.
  - `write_research_digest()` — writes both JSON and Markdown, returns paths.

- **MVP-16 Step 3 — Research Digest Integration Tests (Complete)**
  - `tests/test_research_digest/test_integration.py` — 26 integration tests.
  - End-to-end flows: build → serialize → write → validate, READY digest, BLOCKED digest for missing/invalid/unsafe inputs, deterministic section ordering, deterministic `digest_id` and `generated_at`, JSON round-trip, Markdown safety notice, Markdown sections as plain text, file references as plain strings, no file reads from production paths, no network calls, no trading logic, no execution feedback, no Freqtrade/Binance/exchange/live/leverage/shorting references.
  - **Z.ai Step 3 Review:** APPROVED. No critical issues found.

- **MVP-16 Step 4 — Final Validation and Version Bump (Complete)**
  - Verdict: PASS. No defects found.
  - Version bumped to 0.16.0-dev.
  - All safety invariants verified.

- **Tests:**
  - 141 research_digest tests total. 1 skipped.
  - **Full suite: 3302 tests passing, 1 skipped** using `pytest --import-mode=importlib`.

- **Safety:**
  - Research digest is a human-audit artifact only.
  - Not a trading signal. Not a trade approval.
  - Not a recommendation engine. Not an action-command generator.
  - Must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.
  - No digest feedback into execution paths.
  - No report/operator/index/search/bundle/chronicle/digest feedback into execution paths.
  - No Binance, exchange, API keys, live trading, real orders, leverage, shorting.
  - File references and metadata strings are not traversed, opened, followed, validated, or executed.
  - No Web UI, dashboard, database persistence, server/API/auth.
  - No database, event store, scheduler, routing layer, or feedback layer.

- **Next:**
  - MVP-17 planning, not started.

---

## MVP-15 — Local Research Chronicle / Audit Timeline (Complete)

**Version:** 0.14.0-dev → 0.15.0-dev.

**SPEC-016:** `specs/SPEC-016-Local-Research-Chronicle-Audit-Timeline.md` — approved with notes and polished.

**Commit:** `TBD` — feat: complete MVP-15 local research chronicle / audit timeline.

- **MVP-15 Step 1 — Chronicle Models and Engine (Complete)**
  - `src/hunter/chronicle/__init__.py` — public API exports.
  - `src/hunter/chronicle/models.py` — frozen chronicle dataclasses, enums, 12 reason codes, forbidden chronicle content detection, `ArtifactType`, `ChronicleEntry`, `ChronicleSummary`, `ChronicleDataQuality`, `ChronicleSafetyFlags`, `ResearchChronicle`.
  - `src/hunter/chronicle/engine.py` — in-memory chronicle engine functions: `has_unsafe_chronicle_content`, `build_chronicle_safety_flags`, `build_chronicle_entry_*` builders, `build_chronicle_summary`, `build_chronicle_data_quality`, `build_research_chronicle`.
  - `tests/test_chronicle/test_models.py` — model tests.
  - `tests/test_chronicle/test_engine.py` — engine tests.

- **MVP-15 Step 2 — Chronicle Writer (Complete)**
  - `src/hunter/chronicle/writer.py` — JSON/Markdown serialization, atomic file writing.
  - `src/hunter/chronicle/__init__.py` — updated with writer exports.
  - `tests/test_chronicle/test_writer.py` — writer tests.
  - Default JSON path: `data/chronicle/latest_research_chronicle.json`.
  - Default Markdown path: `reports/chronicle/latest_research_chronicle.md`.
  - `research_chronicle_to_dict()` — deterministic JSON-safe serialization.
  - `research_chronicle_to_markdown()` — human-readable Markdown with explicit safety notice.
  - `atomic_write_json_research_chronicle()` / `atomic_write_markdown_research_chronicle()` — atomic writes with temp file + fsync + os.replace.
  - `write_research_chronicle()` — writes both JSON and Markdown, returns paths.

- **MVP-15 Step 3 — Chronicle Integration Tests (Complete)**
  - `tests/test_chronicle/test_integration.py` — integration tests.
  - End-to-end flows: build → serialize → write → validate, empty chronicle, unsafe content, trace linkage advisory only, deterministic summary, deterministic data quality, deterministic chronicle ID, JSON round-trip, markdown safety notice, artifact references as plain strings, no file reads from references, no secrets in output, no executable instructions, no network calls, no trading logic, no execution feedback, no Freqtrade/Binance/exchange/live/leverage/shorting references.
  - **Z.ai Step 3 Review:** APPROVED. No critical issues found.

- **MVP-15 Step 4 — Final Validation and Version Bump (Complete)**
  - Verdict: PASS. No defects found.
  - Version bumped to 0.15.0-dev.
  - All safety invariants verified.

- **Tests:**
  - 239 chronicle tests total. 1 skipped.
  - **Full suite: 3161 tests passing, 1 skipped** using `pytest --import-mode=importlib`.

- **Safety:**
  - Research chronicle is a human-audit artifact only.
  - Not a trading signal. Not a trade approval.
  - Must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.
  - Trace linkage is advisory only.
  - No database, event store, scheduler, routing layer, or feedback layer.
  - No Binance, exchange, API keys, live trading, real orders, leverage, shorting.
  - No report/operator/index/search/bundle/chronicle feedback into execution paths.
  - File references and metadata strings are not traversed, opened, followed, validated, or executed.
  - No Web UI, dashboard, database persistence, server/API/auth.

- **Next:**
  - MVP-16 planning, not started.

---

## MVP-12 — Local Review Index (Complete)

**Version:** 0.11.0-dev → 0.12.0-dev.

**SPEC-013:** `specs/SPEC-013-Local-Review-Index.md` — approved with notes and polished.

**Commit:** `TBD` — feat: complete MVP-12 local review index.

- **MVP-12 Step 1 — Review Index Models and Engine (Complete)**
  - `src/hunter/review_index/models.py` — frozen index dataclasses, enums, reason codes, forbidden index content detection.
  - `src/hunter/review_index/engine.py` — in-memory review index engine functions.
  - `tests/test_review_index/test_models.py` — 70 model tests.
  - `tests/test_review_index/test_engine.py` — 97 engine tests.

- **MVP-12 Step 2 — Review Index Writer (Complete)**
  - `src/hunter/review_index/writer.py` — JSON/Markdown serialization, atomic file writing.
  - `tests/test_review_index/test_writer.py` — 52 writer tests.
  - Default JSON path: `data/review_index/latest_review_index.json`.
  - Default Markdown path: `reports/review_index/latest_review_index.md`.

- **MVP-12 Step 3 — Review Index Integration Tests (Complete)**
  - `tests/test_review_index/test_integration.py` — 21 integration tests.
  - Coverage: `build_review_index` → `review_index_to_dict`, `review_index_to_markdown`, `write_review_index`.

- **Tests:**
  - 239 review_index tests total (166 model/engine + 52 writer + 21 integration). 1 skipped.
  - **Full suite: 2450 tests passing, 1 skipped** using `pytest --import-mode=importlib`.

- **Safety:**
  - No config YAML.
  - No JSON schema.
  - No Freqtrade strategy class.
  - No freqtrade import.
  - No Freqtrade runtime connection.
  - No Binance.
  - No real exchange.
  - No API keys.
  - No live trading.
  - No real orders.
  - No leverage.
  - No shorting.
  - No real entry/exit execution logic.
  - No report feedback into execution paths.
  - No operator feedback into execution paths.
  - No index feedback into execution paths.
  - No Web UI.
  - No dashboard.
  - No database persistence.
  - File references are local strings only and are not traversed, opened, followed, validated, or executed.

- **Next:**
  - MVP-13 planning, not started.

---

## MVP-14 — Local Research Bundle / Evidence Pack (Complete)

**Version:** 0.13.0-dev → 0.14.0-dev.

**SPEC-015:** `specs/SPEC-015-Local-Research-Bundle-Evidence-Pack.md` — approved with no critical issues.

**Commit:** `TBD` — feat: add MVP-14 research bundle models and engine.
**Commit:** `TBD` — feat: add MVP-14 research bundle writer.
**Commit:** `TBD` — feat: add MVP-14 research bundle integration tests.

- **MVP-14 Step 1 — Research Bundle Models and Engine (Complete)**
  - `src/hunter/research_bundle/__init__.py` — public API exports.
  - `src/hunter/research_bundle/models.py` — frozen bundle dataclasses, enums, 12 reason codes, 22 forbidden terms, 8 bundle output safety flags, 13 unsafe safety flags, `BundleConfig`, `BundleSafetyFlags`, `BundleItem`, `BundleSummary`, `BundleDataQuality`, `ResearchBundle`.
  - `src/hunter/research_bundle/engine.py` — 7 in-memory bundle engine functions: `build_bundle_safety_flags`, `has_unsafe_bundle_content`, `validate_bundle_item`, `build_bundle_item`, `build_bundle_summary`, `build_bundle_data_quality`, `build_research_bundle`.
  - `tests/test_research_bundle/test_models.py` — 54 model tests.
  - `tests/test_research_bundle/test_engine.py` — 58 engine tests.

- **MVP-14 Step 2 — Research Bundle Writer (Complete)**
  - `src/hunter/research_bundle/writer.py` — JSON/Markdown serialization, atomic file writing.
  - `src/hunter/research_bundle/__init__.py` — updated with writer exports.
  - `tests/test_research_bundle/test_writer.py` — 49 writer tests.
  - Default JSON path: `data/research_bundle/latest_research_bundle.json`.
  - Default Markdown path: `reports/research_bundle/latest_research_bundle.md`.
  - `research_bundle_to_dict()` — deterministic JSON-safe serialization.
  - `research_bundle_to_markdown()` — human-readable Markdown with explicit safety notice.
  - `atomic_write_json_research_bundle()` / `atomic_write_markdown_research_bundle()` — atomic writes with temp file + fsync + os.replace.
  - `write_research_bundle()` — writes both JSON and Markdown, returns paths.

- **MVP-14 Step 3 — Research Bundle Integration Tests (Complete)**
  - `tests/test_research_bundle/test_integration.py` — 33 integration tests.
  - End-to-end flows: build → serialize → write → validate, empty bundle, unsafe content, max items exceeded, blocked items, deterministic summary, deterministic data quality, deterministic bundle ID, JSON round-trip, markdown safety notice, item references as plain strings, no file reads from references, no secrets in output, no executable instructions, no network calls, no trading logic, no execution feedback, no Freqtrade/Binance/exchange/live/leverage/shorting references.
  - **Z.ai Step 3 Review:** APPROVED. Engine `human_note_count` fix validated — counts items with non-empty notes (not just HUMAN_NOTE kind), aligning with SPEC-015 semantic definition.
  - 194 research_bundle tests total (54 model + 58 engine + 49 writer + 33 integration). 1 skipped.
  - **Full suite: 2922 tests passing, 1 skipped** using `pytest --import-mode=importlib`.

- **MVP-14 Step 4 — Final Review and Version Bump (Complete)**
  - Verdict: PASS. No defects found.
  - Version bumped to 0.14.0-dev.
  - All safety invariants verified.

- **Safety:**
  - Research bundles are human-audit artifacts only.
  - Not trading signals. Not trade approvals.
  - Must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.
  - No Web UI. No dashboard. No database persistence.
  - No config YAML. No JSON schema. No Freqtrade strategy class. No freqtrade import. No Freqtrade runtime.
  - No Binance. No real exchange. No API keys. No live trading. No real orders. No leverage. No shorting.
  - No report/operator/index/search/bundle feedback into execution paths.
  - File references remain strings only and are not traversed, opened, followed, validated, or executed.

---

## MVP-13 — Local Review Search / Query Layer (Complete)

**Version:** 0.12.0-dev → 0.13.0-dev.

**SPEC-014:** `specs/SPEC-014-Local-Review-Search-Query-Layer.md` — approved with minor notes (SearchConfig added, no critical issues).

**Commit:** `aa4dc25` — feat: add MVP-13 review search models and engine.
**Commit:** `b1465f0` — feat: add MVP-13 review search writer.
**Commit:** `c70d341` — feat: add MVP-13 review search integration tests.

- **MVP-13 Step 1 — Review Search Models and Engine (Complete)**
  - `src/hunter/review_search/__init__.py` — public API exports.
  - `src/hunter/review_search/models.py` — frozen search dataclasses, enums, 12 reason codes, forbidden search content detection, 8 search output safety flags (human-audit-only, not-trading-signal, not-trade-approval, not-for-execution, not-for-strategy, not-for-freqtrade, not-for-order, not-for-exchange).
  - `src/hunter/review_search/engine.py` — 6 in-memory search engine functions: `build_search_safety_flags`, `validate_search_query`, `entry_matches_query`, `score_search_entry`, `sort_search_results`, `build_search_result`.
  - `tests/test_review_search/test_models.py` — 92 model tests.
  - `tests/test_review_search/test_engine.py` — 82 engine tests.

- **MVP-13 Step 2 — Review Search Writer (Complete)**
  - `src/hunter/review_search/writer.py` — JSON/Markdown serialization, atomic file writing.
  - `src/hunter/review_search/__init__.py` — updated with writer exports.
  - `tests/test_review_search/test_writer.py` — 51 writer tests.
  - Default JSON path: `data/review_search/latest_search_result.json`.
  - Default Markdown path: `reports/review_search/latest_search_result.md`.
  - `search_result_to_dict()` — deterministic JSON-safe serialization.
  - `search_result_to_markdown()` — human-readable Markdown with explicit safety notice.
  - `atomic_write_json_search_result()` / `atomic_write_markdown_search_result()` — atomic writes with temp file + fsync + os.replace.
  - `write_search_result()` — writes both JSON and Markdown, returns paths.

- **MVP-13 Step 3 — Review Search Integration Tests (Complete)**
  - `tests/test_review_search/test_integration.py` — 45 integration tests.
  - End-to-end flows: search → serialize → write → validate, score-based ranking, pagination, filter combinations, timestamp ranges, sort modes, blocked index, empty index, blocked query, empty query, unsafe query, safety flag violations, fail-closed summary, empty output, write-only mode, human-audit-only notice, markdown generation, markdown safety notice, no secrets in output, no executable instructions, no file reads from production paths, no network calls, no trading logic, no execution feedback, no Freqtrade/Binance/exchange/live/leverage/shorting references.
  - 278 review_search tests total (92 model + 82 engine + 51 writer + 45 integration + 8 safety flag tests). 1 skipped.
  - **Full suite: 2728 tests passing, 1 skipped** using `pytest --import-mode=importlib`.

- **MVP-13 Step 4 — Final Review and Version Bump (Complete)**
  - Verdict: PASS. No defects found.
  - Version bumped to 0.13.0-dev.
  - All safety invariants verified.

- **Safety:**
  - Search results are human-audit artifacts only.
  - Not trading signals. Not trade approvals.
  - Must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.
  - No Web UI. No dashboard. No database persistence.
  - No config YAML. No JSON schema. No Freqtrade strategy class. No freqtrade import. No Freqtrade runtime.
  - No Binance. No real exchange. No API keys. No live trading. No real orders. No leverage. No shorting.
  - No report/operator/index/search feedback into execution paths.
  - File references remain strings only and are not traversed, opened, followed, validated, or executed.

## MVP-12 Step 3 — Review Index Integration Tests (Complete)

**Version:** 0.11.0-dev (MVP-12 Step 2 complete) → MVP-12 Step 3 complete.

**SPEC-013:** `specs/SPEC-013-Local-Review-Index.md` — approved with notes and polished.

**Commit:** `TBD` — test: add MVP-12 review index integration tests.

- **Files created:**
  - `tests/test_review_index/test_integration.py` — 21 integration tests.
- **Coverage:**
  - `build_review_index` → `review_index_to_dict` — linked entries, observation-only, fail-closed missing inputs, invalid/unsafe inputs, mixed ready + blocked entries, deterministic timestamps, file references as strings, no production paths.
  - `build_review_index` → `review_index_to_markdown` — linked entries, fail-closed, mixed entries, file references not opened, no production paths.
  - `build_review_index` → `write_review_index` with custom `tmp_path` — JSON + Markdown write, fail-closed write, mixed entries, deterministic JSON output, no temp files left behind, file references not traversed, `tmp_path` used exclusively.
- **Tests:**
  - 21 new integration tests.
  - 239 review_index tests total (166 model/engine + 52 writer + 21 integration). 1 skipped.
  - **Full suite: 2450 tests passing, 1 skipped** using `pytest --import-mode=importlib`.
- **Safety:**
  - No source changes.
  - No config YAML.
  - No JSON schema.
  - No Freqtrade strategy class.
  - No freqtrade import.
  - No Freqtrade runtime connection.
  - No Binance.
  - No real exchange.
  - No API keys.
  - No live trading.
  - No real orders.
  - No leverage.
  - No shorting.
  - No real entry/exit execution logic.
  - No report feedback into execution paths.
  - No operator feedback into execution paths.
  - No index feedback into execution paths.
  - No Web UI.
  - No dashboard.
  - No database persistence.
  - File references are local strings only and are not traversed, opened, followed, validated, or executed.
- **Next:**
  - MVP-12 Step 4 — Final MVP-12 validation and version bump, not started.

---

## MVP-12 Step 2 — Review Index Writer (Complete)

**Version:** 0.12.0-dev (MVP-12 Step 1 complete) → MVP-12 Step 2 complete.

**SPEC-013:** `specs/SPEC-013-Local-Review-Index.md` — approved with notes and polished.

**Commit:** `64bc10b` — feat: add MVP-12 review index writer.

- **Files created/modified:**
  - `src/hunter/review_index/writer.py` — JSON/Markdown serialization, atomic file writing.
  - `src/hunter/review_index/__init__.py` — updated with writer exports.
  - `tests/test_review_index/test_writer.py` — writer unit tests.
- **Implemented:**
  - `DEFAULT_REVIEW_INDEX_JSON_PATH = Path("data/review_index/latest_review_index.json")`
  - `DEFAULT_REVIEW_INDEX_MARKDOWN_PATH = Path("reports/review_index/latest_review_index.md")`
  - `_iso()` — ISO-8601 timestamp helper.
  - `_serialize_value()` — deterministic JSON-safe value serialization.
  - `index_entry_to_dict()` — serializes `IndexEntry` to JSON-compatible dict.
  - `index_summary_to_dict()` — serializes `IndexSummary` to JSON-compatible dict.
  - `index_data_quality_to_dict()` — serializes `IndexDataQuality` to JSON-compatible dict.
  - `index_safety_flags_to_dict()` — serializes `IndexSafetyFlags` to JSON-compatible dict.
  - `review_index_to_dict()` — full `ReviewIndex` serialization with nested entries/summary/data_quality/safety_flags.
  - `review_index_to_markdown()` — human-readable Markdown with explicit safety notice.
  - `_atomic_write()` — atomic temp-file write with parent dirs, fsync, os.replace, cleanup.
  - `atomic_write_json_review_index()` — atomic JSON writer.
  - `atomic_write_markdown_review_index()` — atomic Markdown writer.
  - `write_review_index()` — writes both JSON and Markdown, returns paths.
- **Outputs:**
  - Local JSON index artifact: `data/review_index/latest_review_index.json`
  - Local Markdown index artifact: `reports/review_index/latest_review_index.md`
- **Tests:**
  - 52 new writer tests.
  - 218 review_index tests total (166 model/engine + 52 writer).
  - **Full suite: 2429 tests passing, 1 skipped** using `pytest --import-mode=importlib`.
- **Safety:**
  - No integration tests created.
  - No config YAML.
  - No JSON schema.
  - No Freqtrade strategy class.
  - No freqtrade import.
  - No Freqtrade runtime connection.
  - No Binance.
  - No real exchange.
  - No API keys.
  - No live trading.
  - No real orders.
  - No leverage.
  - No shorting.
  - No real entry/exit execution logic.
  - No report feedback into execution paths.
  - No operator feedback into execution paths.
  - No index feedback into execution paths.
  - No Web UI.
  - No dashboard.
  - No database persistence.
  - File references are local strings only and are not traversed, opened, followed, validated, or executed.
- **Next:**
  - MVP-12 Step 3 — Review Index Integration Tests, not started.

---

## MVP-12 Step 1 — Review Index Models and Engine (Complete)

**Version:** 0.11.0-dev (MVP-11 complete) → MVP-12 Step 1 complete.

**SPEC-013:** `specs/SPEC-013-Local-Review-Index.md` — approved with notes and polished.

- **Implemented package:** `src/hunter/review_index/`
- **Files created:**
  - `src/hunter/review_index/__init__.py` — public API exports.
  - `src/hunter/review_index/models.py` — frozen index dataclasses, enums, reason codes, forbidden index content detection.
  - `src/hunter/review_index/engine.py` — in-memory review index engine functions.
  - `tests/test_review_index/__init__.py` — test package init.
  - `tests/test_review_index/test_models.py` — model unit tests.
  - `tests/test_review_index/test_engine.py` — engine unit tests.
- **Implemented:**
  - `IndexState` enum (DISABLED, READY, BLOCKED, UNKNOWN).
  - `IndexEntryKind` enum (OBSERVATION_ONLY, REVIEW_ONLY, LINKED_REPORT_REVIEW, EMPTY, UNKNOWN).
  - `IndexOutputFormat` enum (JSON, MARKDOWN).
  - `IndexConfig` frozen dataclass with 13 fields and validation.
  - `IndexSafetyFlags` frozen dataclass with 10 fields and validation.
  - `IndexEntry` frozen dataclass with 11 fields, `blocked()` factory, validation.
  - `IndexSummary` frozen dataclass with 8 fields and validation.
  - `IndexDataQuality` frozen dataclass with 7 fields and validation.
  - `ReviewIndex` frozen dataclass with 8 fields, `blocked()` factory, validation.
  - Deterministic `REASON_CODES` tuple with 12 constants.
  - `FORBIDDEN_INDEX_TERMS` frozenset with 13 forbidden keys/terms.
  - `has_unsafe_index_content()` — case-insensitive forbidden content detection.
  - `build_index_safety_flags()` — safe defaults from config.
  - `build_index_entry()` — 12-priority fail-closed entry builder.
  - `build_index_summary()` — deterministic summary counts.
  - `build_index_data_quality()` — deterministic quality metrics.
  - `build_review_index()` — full index builder with empty-records blocking.
- **Fail-closed priority order:**
  1. EMPTY_INDEX
  2. INVALID_REPORT
  3. UNSUPPORTED_REPORT_VERSION
  4. UNSAFE_REPORT_STATE
  5. INVALID_REVIEW
  6. UNSUPPORTED_REVIEW_VERSION
  7. UNSAFE_REVIEW_STATE
  8. UNSAFE_SAFETY_FLAGS
  9. UNSAFE_INDEX_CONTENT
  10. MISSING_REPORTS
  11. MISSING_REVIEWS
  12. INDEX_ERROR
- **Tests:**
  - 70 model tests + 97 engine tests = 166 review_index tests passing.
  - 1 skipped (INDEX_ERROR orphan review edge case — requires source modification to trigger).
  - **Full suite: 2377 tests passing** using `pytest --import-mode=importlib`.
- **Safety:**
  - No writer created.
  - No integration tests created.
  - No file I/O in engine.
  - No config YAML.
  - No JSON schema.
  - No Freqtrade strategy class.
  - No freqtrade import.
  - No Freqtrade runtime connection.
  - No Binance.
  - No real exchange.
  - No API keys.
  - No live trading.
  - No real orders.
  - No leverage.
  - No shorting.
  - No real entry/exit execution logic.
  - No report feedback into execution paths.
  - No operator feedback into execution paths.
  - No index feedback into execution paths.
  - No Web UI.
  - No dashboard.
  - No database persistence.
  - File references are local strings only and are not traversed, opened, followed, validated, or executed.

---

## SPEC-013 — Local Review Index (Planning)

**Version:** 0.11.0-dev (MVP-11 complete) → SPEC-013 drafted, MVP-12 not started.

**SPEC-013:** `specs/SPEC-013-Local-Review-Index.md` — draft, awaiting human review.

- **File created:**
  - `specs/SPEC-013-Local-Review-Index.md` — MVP-12 planning document only.
- **Purpose:**
  - Local Review Index layer that catalogs MVP-10 observation reports and MVP-11 review audit records as human-audit catalog artifacts.
- **Planned outputs:**
  - Local JSON index artifact: `data/review_index/latest_review_index.json`
  - Local Markdown index artifact: `reports/review_index/latest_review_index.md`
- **Key design elements:**
  - `IndexEntry` — single report + review catalog entry.
  - `IndexSummary` — aggregated counts across all entries.
  - `IndexDataQuality` — completeness and staleness metrics.
  - `IndexSafetyFlags` — safety invariants with human-audit-only flags.
  - `ReviewIndex` — full index container with fail-closed `blocked()` factory.
  - Fail-closed local index engine with 12 priority-ordered reason codes.
  - Deterministic local index writer with atomic JSON/Markdown output.
  - PlantUML component and sequence diagrams.
  - Four-step MVP-12 implementation plan (Models+Engine → Writer → Integration → Final Review).
- **Safety clarifications:**
  - Local review index artifacts are human-audit catalog artifacts only.
  - Index entries, summaries, JSON output, and Markdown output are not trading signals.
  - Index entries, summaries, JSON output, and Markdown output are not trade approvals.
  - Index artifacts must never be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.
  - Index artifacts and summaries must not feed back into MVP-4, MVP-5, MVP-6, MVP-7, MVP-8, MVP-9, MVP-10, MVP-11, Freqtrade, strategy, order, exchange, or execution paths.
  - File references are local string references only; index logic must not traverse, validate, open, follow, or execute file references.
  - Missing/invalid/unsafe report or review inputs are summarized as BLOCKED/UNKNOWN/INVALID in data quality, not repaired, inferred, upgraded, or normalized into safe-looking records.
  - Fail-closed index records are audit/catalog only and never trigger action.
  - Index output must not contain API keys, secrets, exchange credentials, executable trading instructions, or operational instructions.
- **Not started:**
  - No source code.
  - No tests.
  - No config YAML.
  - No JSON schema.
  - No Freqtrade strategy class.
  - No freqtrade import.
  - No Binance.
  - No real exchange.
  - No API keys.
  - No live trading.
  - No real orders.
  - No leverage.
  - No shorting.
  - No real entry/exit execution logic.
  - No Web UI.
  - No dashboard.
  - No database persistence.

## MVP-11 — Operator Review Workflow (Complete)

**Version:** 0.11.0-dev (MVP-11 Steps 1-3 complete) → MVP-11 complete.

**SPEC-012:** `specs/SPEC-012-Operator-Review-Workflow.md` — complete.

- **Implemented package:** `src/hunter/review/`
- **Files created/modified:**
  - `src/hunter/review/__init__.py` — public API exports.
  - `src/hunter/review/models.py` — frozen review dataclasses, enums, reason codes, forbidden review content detection.
  - `src/hunter/review/engine.py` — in-memory review engine functions.
  - `src/hunter/review/writer.py` — JSON/Markdown serialization, atomic file writing.
  - `tests/test_review/__init__.py` — test package init.
  - `tests/test_review/test_models.py` — model unit tests.
  - `tests/test_review/test_engine.py` — engine unit tests.
  - `tests/test_review/test_writer.py` — writer unit tests.
  - `tests/test_review/test_integration.py` — integration tests.
- **Capabilities:**
  - Review models (`ReviewStatus`, `ReviewState`, `ReviewOutputFormat`, `ReviewConfig`, `ReviewSafetyFlags`, `ReviewRecord`, `ReviewAuditSummary`, `ReviewDataQuality`, `ReviewAuditRecord`).
  - Fail-closed review engine with 13 priority-ordered blocking rules and deterministic first blocking reason.
  - Human-audit-only JSON/Markdown review writer with explicit safety notice.
  - Atomic review audit output writing (temp file, fsync, os.replace, cleanup).
  - In-process review integration tests (observation report → review record → audit record → JSON/Markdown).
  - No report feedback into execution paths.
  - No operator feedback into execution paths.
- **Default review output paths:**
  - `data/review/latest_review_audit_record.json`
  - `reports/review/latest_review_audit_record.md`
- **Tests:**
  - 138 model/engine tests (Step 1)
  - 54 writer tests (Step 2)
  - 83 integration tests (Step 3)
  - 243 review tests total
  - **Full suite: 2211 tests passing** using `pytest --import-mode=importlib`
- **Final review verdict: PASS.** No defects found.
- **Safety:**
  - No config YAML.
  - No JSON schema.
  - No Freqtrade strategy class.
  - No freqtrade import.
  - No Freqtrade runtime connection.
  - No Binance.
  - No real exchange.
  - No API keys.
  - No live trading.
  - No real orders.
  - No leverage.
  - No shorting.
  - No real entry/exit execution logic.
  - No report feedback into execution paths.
  - No operator feedback into execution paths.
  - No production data reads/writes.

## MVP-11 Step 3 — Review Integration Tests (Complete)

**Version:** 0.10.0-dev (MVP-11 Step 2 complete) → MVP-11 Step 3 complete.

**SPEC-012:** `specs/SPEC-012-Operator-Review-Workflow.md` — approved with notes and polished.

- **Files created:**
  - `tests/test_review/test_integration.py` — review integration tests.
- **Integration flow covered:**
  - observation report payload → `build_review_record` → `build_review_audit_record` → `write_review_audit_records`
- **Covered paths:**
  - accepted review happy path
  - rejected review happy path
  - needs investigation happy path
  - not reviewed path
  - missing report → `MISSING_REPORT`
  - invalid report missing version → `INVALID_REPORT`
  - invalid report missing report_state → `INVALID_REPORT`
  - unsupported report version → `UNSUPPORTED_REPORT_VERSION`
  - unsafe report_state `BLOCKED`/`UNKNOWN`/`DISABLED` → `UNSAFE_REPORT_STATE`
  - dry_run false → `DRY_RUN_DISABLED`
  - live_trading_enabled true → `LIVE_TRADING_ENABLED`
  - real_orders_enabled true → `REAL_ORDERS_ENABLED`
  - leverage_enabled true → `LEVERAGE_ENABLED`
  - shorting_enabled true → `SHORTING_ENABLED`
  - missing reviewer → `MISSING_REVIEWER`
  - unsafe notes/tags/metadata → `UNSAFE_REVIEW_CONTENT`
  - deterministic first blocking reason
  - mixed audit summary
  - empty audit fail-closed
  - JSON/Markdown writer integration with `tmp_path`
  - safety assertions
- **Tests:**
  - 83 new integration tests
  - 243 review tests total
  - full suite 2211 passing with `pytest --import-mode=importlib`
- **Safety:**
  - no source changes
  - tests only
  - tests write only to `tmp_path`
  - no production data reads/writes
  - no config YAML
  - no JSON schema
  - no Freqtrade strategy class
  - no freqtrade import
  - no Freqtrade runtime connection
  - no Binance
  - no real exchange
  - no API keys
  - no live trading
  - no real orders
  - no leverage
  - no shorting
  - no real entry/exit execution logic
  - no report feedback into execution paths
  - no operator feedback into execution paths

## MVP-11 Step 2 — Review Writer (Complete)

**Version:** 0.10.0-dev (MVP-11 Step 1 complete) → MVP-11 Step 2 complete.

**SPEC-012:** `specs/SPEC-012-Operator-Review-Workflow.md` — approved with notes and polished.

- **Files created/modified:**
  - `src/hunter/review/writer.py` — JSON/Markdown serialization, atomic file writing.
  - `src/hunter/review/__init__.py` — updated with writer exports.
  - `tests/test_review/test_writer.py` — writer unit tests.
- **Implemented:**
  - `DEFAULT_REVIEW_JSON_RECORD_PATH = Path("data/review/latest_review_audit_record.json")`
  - `DEFAULT_REVIEW_MARKDOWN_RECORD_PATH = Path("reports/review/latest_review_audit_record.md")`
  - `review_record_to_dict()` — deterministic JSON-safe serialization (ISO-8601 Z suffix, enum values, tuple→list, metadata).
  - `review_safety_flags_to_dict()` — safety flags serialization.
  - `review_audit_summary_to_dict()` — summary with reason_counts as plain dict.
  - `review_data_quality_to_dict()` — data quality serialization.
  - `review_audit_record_to_dict()` — full audit record with nested records/summary/data_quality/safety_flags.
  - `review_audit_record_to_markdown()` — human-readable Markdown with explicit safety notice:
    - "This review audit record is a human-audit artifact only."
    - "It is not a trading signal, not trade approval, and must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path."
  - `atomic_write_json_review_audit_record()` — atomic temp-file write with parent dirs, UTF-8, indent=2, sort_keys, trailing newline, fsync, os.replace, cleanup.
  - `atomic_write_markdown_review_audit_record()` — atomic temp-file write with parent dirs, UTF-8, trailing newline, fsync, os.replace, cleanup.
  - `write_review_audit_records()` — writes both JSON and Markdown, returns paths.
- **Tests:** 54 new writer tests. Full suite: **2160 tests passing** using `pytest --import-mode=importlib`.
- **Safety:**
  - No model changes.
  - No engine changes.
  - No integration tests created.
  - Tests write only to `tmp_path`.
  - No config YAML.
  - No JSON schema.
  - No Freqtrade strategy class.
  - No freqtrade import.
  - No Freqtrade runtime connection.
  - No Binance.
  - No real exchange connection.
  - No API keys.
  - No live trading.
  - No real orders.
  - No leverage.
  - No shorting.
  - No real entry/exit execution logic.
  - No report feedback into execution paths.
  - No operator feedback into execution paths.

## MVP-11 Step 1 — Review Models and Engine (Complete)

**Version:** 0.10.0-dev (MVP-10 complete) → MVP-11 Step 1 complete.

**SPEC-012:** `specs/SPEC-012-Operator-Review-Workflow.md` — approved with notes and polished.

- **Files created:**
  - `src/hunter/review/__init__.py` — public API exports.
  - `src/hunter/review/models.py` — frozen review dataclasses, enums, reason codes, forbidden review content detection.
  - `src/hunter/review/engine.py` — in-memory review engine functions.
  - `tests/test_review/__init__.py` — test package init.
  - `tests/test_review/test_models.py` — model unit tests.
  - `tests/test_review/test_engine.py` — engine unit tests.
- **Implemented:**
  - `ReviewStatus` enum (NOT_REVIEWED, REVIEWED, ACCEPTED, REJECTED, NEEDS_INVESTIGATION).
  - `ReviewState` enum (DISABLED, READY, BLOCKED, UNKNOWN).
  - `ReviewOutputFormat` enum (JSON, MARKDOWN).
  - `ReviewConfig` frozen dataclass with 13 fields and validation.
  - `ReviewSafetyFlags` frozen dataclass with 10 fields and validation.
  - `ReviewRecord` frozen dataclass with 11 fields, `blocked()` factory, validation.
  - `ReviewAuditSummary` frozen dataclass with 8 fields and validation.
  - `ReviewDataQuality` frozen dataclass with 7 fields and validation.
  - `ReviewAuditRecord` frozen dataclass with 8 fields, `blocked()` factory, validation.
  - Deterministic `REASON_CODES` tuple with 14 constants.
  - `FORBIDDEN_REVIEW_TERMS` frozenset with 13 forbidden keys/terms.
  - `has_unsafe_review_content()` — case-insensitive forbidden content detection.
  - `build_review_safety_flags()` — safe defaults from config.
  - `build_review_record()` — 13-priority fail-closed record builder.
  - `build_review_audit_summary()` — deterministic summary counts.
  - `build_review_data_quality()` — deterministic quality metrics.
  - `build_review_audit_record()` — audit record builder with empty-records blocking.
- **Fail-closed priority order:**
  1. MISSING_REPORT
  2. INVALID_REPORT
  3. UNSUPPORTED_REPORT_VERSION
  4. UNSAFE_REPORT_STATE
  5. DRY_RUN_DISABLED
  6. LIVE_TRADING_ENABLED
  7. REAL_ORDERS_ENABLED
  8. LEVERAGE_ENABLED
  9. SHORTING_ENABLED
  10. MISSING_REVIEWER
  11. INVALID_REVIEW_STATUS
  12. UNSAFE_REVIEW_CONTENT
  13. REVIEW_ERROR
- **Tests:** 138 new review tests. Full suite: **2106 tests passing** using `pytest --import-mode=importlib`.
- **Safety:**
  - No writer created.
  - No integration tests created.
  - No file I/O in engine.
  - No config YAML.
  - No JSON schema.
  - No Freqtrade strategy class.
  - No freqtrade import.
  - No Freqtrade runtime connection.
  - No Binance.
  - No real exchange connection.
  - No API keys.
  - No live trading.
  - No real orders.
  - No leverage.
  - No shorting.
  - No real entry/exit execution logic.
  - No report feedback into execution paths.
  - No operator feedback into execution paths.

## MVP-11 — Operator Review Workflow (Planning)

**Version:** 0.10.0-dev (MVP-10 complete) → MVP-11 planning phase.

**SPEC-012:** `specs/SPEC-012-Operator-Review-Workflow.md` — drafted.

- **Purpose:** Design an operator review workflow layer that consumes MVP-10 observation reports as human-review artifacts and produces local JSON/Markdown review audit records.
- **File created:** `specs/SPEC-012-Operator-Review-Workflow.md` (838 lines).
- **Key design elements:**
  - `ReviewStatus`, `ReviewRecord`, `ReviewAuditSummary`, `ReviewSafetyFlags`, `ReviewDataQuality`, `ReviewAuditRecord` models.
  - 9 fail-closed validation rules with priority-ordered blocking.
  - 15 deterministic reason code constants.
  - Proposed package: `src/hunter/review/`.
  - Proposed output paths: `data/review/latest_review_record.json`, `reports/review/latest_review_record.md`.
  - PlantUML component and sequence diagrams.
  - 4-step implementation plan (Models+Engine → Writer → Integration → Review).
  - ~115 test plan (45 models + 40 engine + 30 integration).
- **Key safety clarifications:**
  - **Operator acceptance is not trade approval.** The `ACCEPTED` status means the operator acknowledges the observation report as a valid audit artifact, not that they approve any trade.
  - Review records are **human-audit artifacts only** — not trading signals, not trade approvals, not execution instructions.
  - JSON/Markdown review records **must never be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path**.
  - Review decisions **must not feed back into MVP-4, MVP-5, MVP-6, MVP-7, MVP-8, MVP-9, MVP-10, Freqtrade, strategy, order, exchange, or execution paths**.
  - Fail-closed review records may be generated for audit only and **never trigger any action**.
  - Missing/invalid/unsafe observation reports are **summarized as BLOCKED/UNKNOWN**, not repaired or inferred.
  - Review files **must not contain API keys, secrets, exchange credentials, or executable trading instructions**.
- **No MVP-11 implementation started.** No source code, no tests, no config YAML, no JSON schema.
- **Safety constraints preserved:**
  - No Freqtrade strategy class.
  - No `freqtrade` import.
  - No Freqtrade runtime connection.
  - No Binance integration.
  - No real exchange connection.
  - No API keys.
  - No live trading.
  - No real orders.
  - No leverage.
  - No shorting.
  - No real entry/exit execution logic (`enter_long`, `enter_short`, `exit_long`, `exit_short`).
  - No report feedback into execution paths.
  - No operator feedback into execution paths.

---

## MVP-10 — Dry-Run Research Observation & Reports (Complete)

**Version:** 0.10.0-dev (MVP-10 complete).

**SPEC-011:** `specs/SPEC-011-Dry-Run-Research-Observation-Reports.md` — approved with notes and polished.

- **Purpose:** Design a dry-run research observation/reporting layer that consumes MVP-9 research-only shell metadata and produces local JSON/Markdown reports for human review.
- **File created:** `specs/SPEC-011-Dry-Run-Research-Observation-Reports.md` (729 lines).
- **Key design elements:**
  - `ObservationState`, `SignalObservation`, `ObservationWindow`, `ObservationReport`, `ObservationSafetyFlags`, `ObservationDataQuality` models.
  - `JsonReport` and `MarkdownReport` output models.
  - 8 fail-closed validation rules with priority-ordered blocking.
  - 13 deterministic reason code constants.
  - Proposed package: `src/hunter/observation/`.
  - Proposed output paths: `data/observation/current_observation_report.json`, `data/observation/current_observation_report.md`.
  - PlantUML component and sequence diagrams.
  - 4-step implementation plan (Models+Engine → Writer → Integration → Review).
  - ~100 test plan (40 models + 35 engine + 25 integration).
- **Key safety clarifications:**
  - Reports are **human-review artifacts only** — not trading signals.
  - JSON/Markdown reports **must never be consumed by execution, strategy, Freqtrade shell, order, or any MVP execution path**.
  - Observation layer **must not feed outputs back into MVP-4, MVP-5, MVP-6, MVP-7, MVP-8, MVP-9, Freqtrade, or any execution path**.
  - Fail-closed observations produce **safe audit/report output only** and never trigger action.
  - Missing/invalid/unsafe inputs are **summarized as BLOCKED/UNKNOWN**, not repaired or inferred.
  - Reports **must not contain API keys, secrets, exchange credentials, or executable trading instructions**.
- **MVP-10 implementation complete.** All 4 steps finished. Final review verdict: PASS.
- **Safety constraints preserved:**
  - No Freqtrade strategy class.
  - No `freqtrade` import.
  - No Freqtrade runtime connection.
  - No Binance integration.
  - No real exchange connection.
  - No API keys.
  - No live trading.
  - No real orders.
  - No leverage.
  - No shorting.
  - No real entry/exit execution logic (`enter_long`, `enter_short`, `exit_long`, `exit_short`).
  - No report feedback into execution paths.

---

## MVP-10 — Dry-Run Research Observation & Reports (Complete)

- **Version:** 0.10.0-dev (MVP-10 complete).
- **SPEC-011:** `specs/SPEC-011-Dry-Run-Research-Observation-Reports.md` — approved with notes and polished.
- **Implemented package:** `src/hunter/observation/`
- **Files created/modified:**
  - `src/hunter/observation/__init__.py` — public API exports.
  - `src/hunter/observation/models.py` — 9 models + 13 reason codes + `FORBIDDEN_METADATA_KEYS`.
  - `src/hunter/observation/engine.py` — 5 engine functions.
  - `src/hunter/observation/writer.py` — 5 writer functions + 2 default path constants.
  - `tests/test_observation/__init__.py` — test package init.
  - `tests/test_observation/test_models.py` — 77 model tests.
  - `tests/test_observation/test_engine.py` — 59 engine tests.
  - `tests/test_observation/test_writer.py` — 58 writer tests.
  - `tests/test_observation/test_integration.py` — 58 integration tests.
- **Capabilities:**
  - Observation models (ObservationState, ObservationSignal, ReportFormat, ObservationConfig, ObservationSafetyFlags, SignalObservation, ObservationWindow, ObservationDataQuality, ObservationReport).
  - Fail-closed observation engine with 10 priority-ordered validation rules.
  - Human-review-only JSON/Markdown report writer.
  - Atomic report output writing (temp file, fsync, os.replace, cleanup).
  - In-process observation integration tests (MVP-9 metadata → SignalObservation → ObservationWindow → ObservationReport → JSON/Markdown).
  - No report feedback into execution paths.
- **Default report paths:**
  - `data/observation/latest_observation_report.json`
  - `reports/observation/latest_observation_report.md`
- **Tests:**
  - 77 model tests + 59 engine tests + 58 writer tests + 58 integration tests = **252 MVP-10 tests**.
  - **Full test suite: 1968 tests passing** using `pytest --import-mode=importlib`.
- **Final review verdict: PASS.** No defects found.
- **Safety constraints preserved:**
  - No config YAML.
  - No JSON schema.
  - No Freqtrade strategy class.
  - No `freqtrade` import.
  - No Freqtrade runtime connection.
  - No Binance integration.
  - No real exchange connection.
  - No API keys.
  - No live trading.
  - No real orders.
  - No leverage.
  - No shorting.
  - No real entry/exit execution logic (`enter_long`, `enter_short`, `exit_long`, `exit_short`).
  - No report feedback into execution paths.
  - No production data reads/writes.

---

## MVP-10 Step 4 — Final Review (Complete)

- **Final review verdict: PASS.** No defects found.
- All SPEC-011 requirements verified against implementation.
- All models, engine, writer, and integration tests reviewed.
- Full test suite: 1968 tests passing using `pytest --import-mode=importlib`.
- Safety constraints verified.
- No new features, config, schema, or strategy class created.
- No production data reads/writes.

---

## MVP-10 Step 3 — Observation Integration Tests (Complete)

- **File created:**
  - `tests/test_observation/test_integration.py` — 58 integration tests.
- **Integration flow verified:**
  - MVP-9 shell metadata dict → `build_signal_observation(...)` → `SignalObservation` → `build_observation_window(...)` → `ObservationWindow` → `build_observation_report(...)` → `ObservationReport` → `observation_report_to_dict(...)` → `observation_report_to_markdown(...)` → `write_observation_reports(..., tmp_path JSON and Markdown paths)` → verify local report outputs.
- **Paths covered:**
  - Long research happy path: READY observation + LONG_RESEARCH, READY report, JSON/Markdown contain long research, human-review safety notice.
  - Short research happy path: READY observation + SHORT_RESEARCH, READY report, JSON/Markdown contain short research.
  - Missing metadata: MISSING_INPUT → BLOCKED observation + NONE, BLOCKED report, audit artifact generated, no action triggered.
  - Invalid metadata: INVALID_INPUT → BLOCKED observation + NONE, BLOCKED report.
  - Unsupported version: UNSUPPORTED_INPUT_VERSION → BLOCKED observation + NONE, BLOCKED report.
  - dry_run false: DRY_RUN_DISABLED → BLOCKED observation + NONE, BLOCKED report.
  - live_trading_enabled true: LIVE_TRADING_ENABLED → BLOCKED observation + NONE, BLOCKED report.
  - real_orders_enabled true: REAL_ORDERS_ENABLED → BLOCKED observation + NONE, BLOCKED report.
  - leverage_enabled true: LEVERAGE_ENABLED → BLOCKED observation + NONE, BLOCKED report.
  - shorting_enabled true: SHORTING_ENABLED → BLOCKED observation + NONE, BLOCKED report.
  - Unsafe metadata: all 8 forbidden keys (`enter_long`, `enter_short`, `exit_long`, `exit_short`, `api_key`, `secret`, `exchange_credentials`, `executable_instructions`) → UNSAFE_METADATA → BLOCKED observation + NONE, no unsafe keys in report output.
  - Empty observation window: EMPTY_OBSERVATION_WINDOW → BLOCKED report.
  - Mixed observation window: long + short + blocked → summary counts correct (total=3, long=1, short=1, none≥1, blocked≥1), reason_counts aggregated, report state BLOCKED.
  - Writer integration: both JSON and Markdown written to tmp_path, parent directories created, JSON valid and deterministic, Markdown safety notice present, no API keys/secrets/executable instructions in output.
  - Safety assertions: no freqtrade import, no production data reads/writes, no report feedback into execution, no network/database/realtime, no live trading/real orders/leverage/shorting, no real entry/exit execution logic.
- **58 new integration tests** (all passed).
- **Full test suite: 1968 tests passing** using `pytest --import-mode=importlib`.
- **No models, engine, writer, or `__init__.py` changes.**
- **Tests write only to `tmp_path`.**
- **No production data reads/writes.**
- **Safety constraints preserved:**
  - No config YAML.
  - No JSON schema.
  - No Freqtrade strategy class.
  - No `freqtrade` import.
  - No runtime connection.
  - No Binance integration.
  - No real exchange connection.
  - No API keys.
  - No live trading.
  - No real orders.
  - No leverage.
  - No shorting.
  - No real entry/exit execution logic (`enter_long`, `enter_short`, `exit_long`, `exit_short`).
  - No report feedback into execution paths.

---

## MVP-10 Step 2 — Observation Report Writer (Complete)

- **Files created/modified:**
  - `src/hunter/observation/writer.py` — observation report writer.
  - `src/hunter/observation/__init__.py` — updated with writer exports.
  - `tests/test_observation/test_writer.py` — 58 writer tests.
- **Constants:**
  - `DEFAULT_OBSERVATION_JSON_REPORT_PATH = Path("data/observation/latest_observation_report.json")`
  - `DEFAULT_OBSERVATION_MARKDOWN_REPORT_PATH = Path("reports/observation/latest_observation_report.md")`
- **Writer functions:**
  - `observation_report_to_dict(...)` — serializes `ObservationReport` to JSON-compatible dict with ISO-8601 timestamps, enum `.value` strings, tuple→list conversion, nested dicts for window/observations/data_quality/safety_flags.
  - `observation_report_to_markdown(...)` — human-review-only Markdown with title, generated_at, report_state, window info, summary counts, reason codes, data quality, safety flags, explicit safety notice.
  - `atomic_write_json_report(...)` — atomic temp-file write with parent dirs, UTF-8, indent=2, sort_keys, trailing newline, fsync, os.replace, cleanup on failure.
  - `atomic_write_markdown_report(...)` — atomic temp-file write with parent dirs, UTF-8, trailing newline, fsync, os.replace, cleanup on failure.
  - `write_observation_reports(...)` — writes both JSON and Markdown reports, uses default paths when None.
- **58 new writer tests** covering:
  - Dict serialization: all fields, ISO-8601, enum values, nested objects, no secrets, blocked report, no mutation.
  - Markdown: title, generated_at, report_state, window, counts, reason codes, data quality, safety flags, human-review safety notice, no executable instructions, no secrets, blocked report.
  - Atomic JSON write: parent dirs, valid JSON, indent/sort_keys, UTF-8, overwrite, no temp files, cleanup on failure.
  - Atomic Markdown write: parent dirs, UTF-8, trailing newline, overwrite, no temp files, cleanup on failure.
  - `write_observation_reports`: default paths, custom paths, blocked report, no mutation.
  - Safety assertions: no production data reads, no execution feedback, no network, no database, no realtime, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit, no report feedback, default paths, no freqtrade import.
- **Full test suite: 1910 tests passing** using `pytest --import-mode=importlib`.
- **Safety constraints preserved:**
  - No model changes.
  - No engine changes.
  - No integration tests created.
  - No config YAML.
  - No JSON schema.
  - No Freqtrade strategy class.
  - No `freqtrade` import.
  - No runtime connection.
  - No Binance integration.
  - No real exchange connection.
  - No API keys.
  - No live trading.
  - No real orders.
  - No leverage.
  - No shorting.
  - No real entry/exit execution logic (`enter_long`, `enter_short`, `exit_long`, `exit_short`).
  - No report feedback into execution paths.
  - Tests write only to `tmp_path`.

---

## MVP-10 Step 1 — Observation Models and Engine (Complete)

- **SPEC-011 approved with notes and polished.**
- **Files created:**
  - `src/hunter/observation/__init__.py` — public API exports.
  - `src/hunter/observation/models.py` — observation models and reason codes.
  - `src/hunter/observation/engine.py` — observation engine functions.
  - `tests/test_observation/__init__.py` — test package init.
  - `tests/test_observation/test_models.py` — 77 model tests.
  - `tests/test_observation/test_engine.py` — 59 engine tests.
- **Models:**
  - `ObservationState` enum: DISABLED, READY, BLOCKED, UNKNOWN.
  - `ObservationSignal` enum: LONG_RESEARCH, SHORT_RESEARCH, NONE.
  - `ReportFormat` enum: JSON, MARKDOWN.
  - `ObservationConfig` — 13 fields, frozen, fail-closed validation (all unsafe flags must be False).
  - `ObservationSafetyFlags` — 10 fields, frozen, validation (all unsafe flags must be False).
  - `SignalObservation` — 9 fields, `blocked()` fail-closed factory, validation.
  - `ObservationWindow` — 4 fields, frozen, validation.
  - `ObservationDataQuality` — 7 fields, frozen, validation.
  - `ObservationReport` — 9 fields, `blocked()` fail-closed factory, validation.
- **Engine functions:**
  - `build_signal_observation(...)` — builds a single `SignalObservation` from MVP-9 shell metadata with 10 priority-ordered fail-closed validation rules, returns first blocking reason only, catches exceptions → `OBSERVATION_ERROR`.
  - `build_observation_window(...)` — creates `ObservationWindow` from a list of `SignalObservation` instances.
  - `build_observation_report(...)` — creates `ObservationReport` from `ObservationWindow`, empty window → blocked, unsafe metadata → blocked, summary counts aggregated.
  - `build_observation_safety_flags(...)` — safe defaults from `ObservationConfig`.
  - `has_unsafe_metadata(...)` — checks metadata dict for `FORBIDDEN_METADATA_KEYS`.
- **13 deterministic reason codes:** MISSING_INPUT, INVALID_INPUT, UNSUPPORTED_INPUT_VERSION, DRY_RUN_DISABLED, LIVE_TRADING_ENABLED, REAL_ORDERS_ENABLED, LEVERAGE_ENABLED, SHORTING_ENABLED, UNSAFE_METADATA, LONG_RESEARCH_EXPOSED, SHORT_RESEARCH_EXPOSED, DEFAULT_BLOCKED, OBSERVATION_ERROR.
- **FORBIDDEN_METADATA_KEYS** frozenset for unsafe metadata detection.
- **136 new MVP-10 Step 1 tests** (77 models + 59 engine).
- **Full test suite: 1852 tests passing** using `pytest --import-mode=importlib`.
- **No writer yet.** No integration tests yet.
- **Safety constraints preserved:**
  - No Freqtrade strategy class.
  - No `freqtrade` import.
  - No Freqtrade runtime connection.
  - No Binance integration.
  - No real exchange connection.
  - No API keys.
  - No live trading.
  - No real orders.
  - No leverage.
  - No shorting.
  - No real entry/exit execution logic (`enter_long`, `enter_short`, `exit_long`, `exit_short`).
  - No report feedback into execution paths.
  - No file reads/writes.
  - No production data access.

---

## MVP-9 — Freqtrade Dry-Run Strategy Shell (Planning)

### Added

- SPEC-010 Freqtrade Dry-Run Strategy Shell design approved.
  - `ShellState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
  - `ShellSignalExposure` enum: EXPOSE_LONG_RESEARCH_METADATA, EXPOSE_SHORT_RESEARCH_METADATA, NO_RESEARCH_SIGNAL, BLOCKED.
  - `ShellRuntimeConfig` with 15 fields and fail-closed validation (all unsafe flags must be False).
  - `ShellValidationResult` with 20 fields, `blocked()` fail-closed factory, and validation.
  - 18 deterministic reason codes: RUNTIME_JSON_MISSING, RUNTIME_JSON_INVALID, RUNTIME_JSON_VERSION_MISMATCH, RUNTIME_JSON_INVALID_TIMESTAMP, STALE_RUNTIME_CONTEXT, INVALID_STRATEGY_STATE, INVALID_SIGNAL_ACTION, SIGNAL_BLOCKED, NOT_DRY_RUN_READY, DRY_RUN_DISABLED, LIVE_TRADING_ENABLED, REAL_ORDERS_ENABLED, LEVERAGE_ENABLED, SHORTING_ENABLED, LONG_RESEARCH_METADATA_EXPOSED, SHORT_RESEARCH_METADATA_EXPOSED, DEFAULT_BLOCKED, VALIDATION_ERROR.
  - 14 priority-ordered validation rules for runtime JSON payload validation.
  - Pull-model interface: reads MVP-8 runtime JSON, validates in-memory, exposes research-only metadata.
  - Safety clarifications: research-only means metadata/columns only (no real trade signals), `populate_entry_trend` never sets `enter_long`/`enter_short`, `populate_exit_trend` never sets `exit_long`/`exit_short`, fail-closed produces no active research signal and no real entry/exit signal, Freqtrade compatibility is interface boundary only.
  - 4-step implementation plan: Models+Validator, Adapter, Integration, Final Review.
- MVP-9 Step 1 — Shell Models and Validator complete.
  - `src/hunter/freqtrade_shell/__init__.py` — public API exports.
  - `src/hunter/freqtrade_shell/models.py` — Shell Models (Step 1).
    - `ShellState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
    - `ShellSignalExposure` enum: EXPOSE_LONG_RESEARCH_METADATA, EXPOSE_SHORT_RESEARCH_METADATA, NO_RESEARCH_SIGNAL, BLOCKED.
    - `ShellRuntimeConfig` with 15 fields and fail-closed validation.
    - `ShellValidationResult` with 20 fields, `blocked()` fail-closed factory.
    - 18 deterministic reason codes.
    - All models frozen/immutable with `__post_init__` validation.
    - 94 shell model tests, all passing.
  - `src/hunter/freqtrade_shell/validator.py` — Shell Validator (Step 1).
    - `validate_runtime_payload()` — 14 priority-ordered blocking checks, returns first blocking reason only, catches exceptions → VALIDATION_ERROR.
    - `is_runtime_payload_stale()` — timestamp age check against config.
    - `parse_runtime_timestamp()` — ISO-8601 parser with Z suffix and offset support.
    - `map_signal_action_to_exposure()` — MVP-8 signal action → shell signal exposure mapping.
    - 28 validator tests, all passing.
  - `tests/test_freqtrade_shell/__init__.py` — test package (added to avoid pytest import mismatch).
  - `tests/test_freqtrade_shell/test_models.py` — 94 model tests, all passing.
  - `tests/test_freqtrade_shell/test_validator.py` — 28 validator tests, all passing.
  - Full test suite: 1613 tests passing (1491 existing + 122 new).
  - No adapter.py, no Freqtrade strategy class, no freqtrade import, no config YAML, no JSON schema, no Freqtrade runtime connection, no Binance, no real exchange connection, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.
- MVP-9 Step 3 — Shell Integration Tests complete.
  - `tests/test_freqtrade_shell/test_integration.py` — Shell Integration Tests (Step 3).
    - 62 integration tests covering the complete in-process MVP-9 shell flow: MVP-8 runtime payload dict → `validate_runtime_payload()` → `ShellValidationResult` → `shell_validation_result_to_metadata()` → `determine_research_signal()` → `apply_research_metadata_to_dataframe()` → research-only dataframe metadata verification.
    - Happy paths: long research (`EXPOSE_LONG_RESEARCH_SIGNAL` → `LONG_RESEARCH`), short research (`EXPOSE_SHORT_RESEARCH_SIGNAL` → `SHORT_RESEARCH`).
    - Fail-closed blocking paths: missing payload, invalid payload, version mismatch, dry_run false, live_trading_enabled true, real_orders_enabled true, leverage_enabled true, shorting_enabled true, invalid timestamp, stale runtime context, invalid strategy state, invalid signal action, `BLOCK_SIGNAL`, `NO_SIGNAL`, `BLOCKED`/`UNKNOWN`/`DISABLED` states.
    - Forbidden trade columns: `enter_long`, `enter_short`, `exit_long`, `exit_short` all rejected with `ValueError`.
    - Metadata verification: enum serialization to `.value` strings, `reason_codes` tuple → list, runtime version/state/mode/action present, all unsafe flags remain False.
    - Safety assertions: no freqtrade import, no Freqtrade strategy class, no config YAML, no JSON schema, no network calls, no Binance, no live trading, no real orders, no leverage, no shorting, no real entry/exit columns set, no production data access.
  - Full test suite: 1716 tests passing (1654 existing + 62 new) using `pytest --import-mode=importlib`.
  - No model changes, no validator changes, no adapter changes, no `__init__.py` changes, no file reads/writes, no production data access, no Freqtrade import, no Freqtrade strategy class, no config YAML, no JSON schema, no Freqtrade runtime connection, no Binance, no real exchange connection, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.
  - `src/hunter/freqtrade_shell/adapter.py` — Shell Adapter (Step 2).
    - `RESEARCH_SIGNAL_COLUMN`, `RESEARCH_REASON_COLUMN`, `RESEARCH_STATE_COLUMN`, `RESEARCH_EXPOSURE_COLUMN` — research-only metadata column names.
    - `shell_validation_result_to_metadata()` — serializes `ShellValidationResult` to deterministic JSON-compatible dict (16 fields, enum `.value` strings, tuple→list).
    - `determine_research_signal()` — returns `"LONG_RESEARCH"`, `"SHORT_RESEARCH"`, or `"NONE"` based on state + exposure.
    - `apply_research_metadata_to_dataframe()` — returns copy of dataframe with 4 research-only columns added, never mutates input, rejects dataframes containing forbidden trade columns (`enter_long`, `enter_short`, `exit_long`, `exit_short`).
    - `assert_no_trade_columns()` — raises `ValueError` if dataframe contains any forbidden trade columns.
    - `build_blocked_research_metadata()` — fail-closed metadata factory with blocked defaults.
    - Research-only behavior: adds only `hunter_*` research metadata columns, never sets `enter_long`/`enter_short`/`exit_long`/`exit_short`, blocked/unknown/disabled results produce `NONE`.
  - `src/hunter/freqtrade_shell/__init__.py` — updated with adapter constants and function exports.
  - `tests/test_freqtrade_shell/test_adapter.py` — 41 adapter tests, all passing.
  - Full test suite: 1654 tests passing (1613 existing + 41 new) using `pytest --import-mode=importlib`.
  - No model changes, no validator changes, no Freqtrade import, no Freqtrade strategy class, no config YAML, no JSON schema, no Freqtrade runtime connection, no Binance, no real exchange connection, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.

## MVP-9 — Freqtrade Dry-Run Strategy Shell (Complete)

### Added

- SPEC-010 Freqtrade Dry-Run Strategy Shell design approved.
  - `ShellState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
  - `ShellSignalExposure` enum: EXPOSE_LONG_RESEARCH_METADATA, EXPOSE_SHORT_RESEARCH_METADATA, NO_RESEARCH_SIGNAL, BLOCKED.
  - `ShellRuntimeConfig` with 15 fields and fail-closed validation (all unsafe flags must be False).
  - `ShellValidationResult` with 20 fields, `blocked()` fail-closed factory, and validation.
  - 18 deterministic reason codes: RUNTIME_JSON_MISSING, RUNTIME_JSON_INVALID, RUNTIME_JSON_VERSION_MISMATCH, RUNTIME_JSON_INVALID_TIMESTAMP, STALE_RUNTIME_CONTEXT, INVALID_STRATEGY_STATE, INVALID_SIGNAL_ACTION, SIGNAL_BLOCKED, NOT_DRY_RUN_READY, DRY_RUN_DISABLED, LIVE_TRADING_ENABLED, REAL_ORDERS_ENABLED, LEVERAGE_ENABLED, SHORTING_ENABLED, LONG_RESEARCH_METADATA_EXPOSED, SHORT_RESEARCH_METADATA_EXPOSED, DEFAULT_BLOCKED, VALIDATION_ERROR.
  - 14 priority-ordered validation rules for runtime JSON payload validation.
  - Pull-model interface: reads MVP-8 runtime JSON, validates in-memory, exposes research-only metadata.
  - Safety clarifications: research-only means metadata/columns only (no real trade signals), `populate_entry_trend` never sets `enter_long`/`enter_short`, `populate_exit_trend` never sets `exit_long`/`exit_short`, fail-closed produces no active research signal and no real entry/exit signal, Freqtrade compatibility is interface boundary only.
  - 4-step implementation plan: Models+Validator, Adapter, Integration, Final Review.
- MVP-9 Step 1 — Shell Models and Validator complete.
  - `src/hunter/freqtrade_shell/__init__.py` — public API exports.
  - `src/hunter/freqtrade_shell/models.py` — Shell Models (Step 1).
    - `ShellState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
    - `ShellSignalExposure` enum: EXPOSE_LONG_RESEARCH_METADATA, EXPOSE_SHORT_RESEARCH_METADATA, NO_RESEARCH_SIGNAL, BLOCKED.
    - `ShellRuntimeConfig` with 15 fields and fail-closed validation.
    - `ShellValidationResult` with 20 fields, `blocked()` fail-closed factory.
    - 18 deterministic reason codes.
    - All models frozen/immutable with `__post_init__` validation.
    - 94 shell model tests, all passing.
  - `src/hunter/freqtrade_shell/validator.py` — Shell Validator (Step 1).
    - `validate_runtime_payload()` — 14 priority-ordered blocking checks, returns first blocking reason only, catches exceptions → VALIDATION_ERROR.
    - `is_runtime_payload_stale()` — timestamp age check against config.
    - `parse_runtime_timestamp()` — ISO-8601 parser with Z suffix and offset support.
    - `map_signal_action_to_exposure()` — MVP-8 signal action → shell signal exposure mapping.
    - 28 validator tests, all passing.
  - `tests/test_freqtrade_shell/__init__.py` — test package (added to avoid pytest import mismatch).
  - `tests/test_freqtrade_shell/test_models.py` — 94 model tests, all passing.
  - `tests/test_freqtrade_shell/test_validator.py` — 28 validator tests, all passing.
  - Full test suite: 1613 tests passing (1491 existing + 122 new).
  - No adapter.py, no Freqtrade strategy class, no freqtrade import, no config YAML, no JSON schema, no Freqtrade runtime connection, no Binance, no real exchange connection, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.
- MVP-9 Step 2 — Shell Adapter Boundary complete.
  - `src/hunter/freqtrade_shell/adapter.py` — Shell Adapter (Step 2).
    - `RESEARCH_SIGNAL_COLUMN`, `RESEARCH_REASON_COLUMN`, `RESEARCH_STATE_COLUMN`, `RESEARCH_EXPOSURE_COLUMN` — research-only metadata column names.
    - `shell_validation_result_to_metadata()` — serializes `ShellValidationResult` to deterministic JSON-compatible dict (16 fields, enum `.value` strings, tuple→list).
    - `determine_research_signal()` — returns `"LONG_RESEARCH"`, `"SHORT_RESEARCH"`, or `"NONE"` based on state + exposure.
    - `apply_research_metadata_to_dataframe()` — returns copy of dataframe with 4 research-only columns added, never mutates input, rejects dataframes containing forbidden trade columns (`enter_long`, `enter_short`, `exit_long`, `exit_short`).
    - `assert_no_trade_columns()` — raises `ValueError` if dataframe contains any forbidden trade columns.
    - `build_blocked_research_metadata()` — fail-closed metadata factory with blocked defaults.
    - Research-only behavior: adds only `hunter_*` research metadata columns, never sets `enter_long`/`enter_short`/`exit_long`/`exit_short`, blocked/unknown/disabled results produce `NONE`.
  - `src/hunter/freqtrade_shell/__init__.py` — updated with adapter constants and function exports.
  - `tests/test_freqtrade_shell/test_adapter.py` — 41 adapter tests, all passing.
  - Full test suite: 1654 tests passing (1613 existing + 41 new) using `pytest --import-mode=importlib`.
  - No model changes, no validator changes, no Freqtrade import, no Freqtrade strategy class, no config YAML, no JSON schema, no Freqtrade runtime connection, no Binance, no real exchange connection, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.
- MVP-9 Step 3 — Shell Integration Tests complete.
  - `tests/test_freqtrade_shell/test_integration.py` — Shell Integration Tests (Step 3).
    - 62 integration tests covering the complete in-process MVP-9 shell flow: MVP-8 runtime payload dict → `validate_runtime_payload()` → `ShellValidationResult` → `shell_validation_result_to_metadata()` → `determine_research_signal()` → `apply_research_metadata_to_dataframe()` → research-only dataframe metadata verification.
    - Happy paths: long research (`EXPOSE_LONG_RESEARCH_SIGNAL` → `LONG_RESEARCH`), short research (`EXPOSE_SHORT_RESEARCH_SIGNAL` → `SHORT_RESEARCH`).
    - Fail-closed blocking paths: missing payload, invalid payload, version mismatch, dry_run false, live_trading_enabled true, real_orders_enabled true, leverage_enabled true, shorting_enabled true, invalid timestamp, stale runtime context, invalid strategy state, invalid signal action, `BLOCK_SIGNAL`, `NO_SIGNAL`, `BLOCKED`/`UNKNOWN`/`DISABLED` states.
    - Forbidden trade columns: `enter_long`, `enter_short`, `exit_long`, `exit_short` all rejected with `ValueError`.
    - Metadata verification: enum serialization to `.value` strings, `reason_codes` tuple → list, runtime version/state/mode/action present, all unsafe flags remain False.
    - Safety assertions: no freqtrade import, no Freqtrade strategy class, no config YAML, no JSON schema, no network calls, no Binance, no live trading, no real orders, no leverage, no shorting, no real entry/exit columns set, no production data access.
  - Full test suite: 1716 tests passing (1654 existing + 62 new) using `pytest --import-mode=importlib`.
  - No model changes, no validator changes, no adapter changes, no `__init__.py` changes, no file reads/writes, no production data access, no Freqtrade import, no Freqtrade strategy class, no config YAML, no JSON schema, no Freqtrade runtime connection, no Binance, no real exchange connection, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.
- Final review verdict: **PASS**. No defects found.
- Version 0.9.0-dev.

## MVP-8 — Freqtrade Deployable Dry-Run Strategy (Planning)

### Added

- SPEC-009 Freqtrade Deployable Dry-Run Strategy design finalized.
  - `DryRunStrategyState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
  - `DryRunStrategyMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
  - `DryRunSignalAction` enum: EXPOSE_LONG_RESEARCH_SIGNAL, EXPOSE_SHORT_RESEARCH_SIGNAL, BLOCK_SIGNAL, NO_SIGNAL.
  - `DryRunStrategyRuntimeContext` with 22 fields including adapter_state, adapter_mode, adapter_signal_intent, dry_run, live_trading_enabled, real_orders_enabled, leverage_enabled, shorting_enabled, freqtrade_runtime_allowed, strategy_class_allowed, populate_indicators_allowed, populate_entry_trend_allowed, populate_exit_trend_allowed, order_execution_allowed.
  - Fail-closed deployable dry-run strategy rules: 12 blocking + 2 allowed + 1 fallback in deterministic priority order.
  - Deterministic reason codes: MISSING_ADAPTER_DECISION_CONTEXT, INVALID_ADAPTER_DECISION_CONTEXT, ADAPTER_NOT_DRY_RUN_READY, ADAPTER_MODE_BLOCK_ALL, ADAPTER_SIGNAL_BLOCKED, DRY_RUN_DISABLED, LIVE_TRADING_ENABLED, REAL_ORDERS_ENABLED, LEVERAGE_ENABLED, SHORTING_ENABLED, STALE_ADAPTER_DECISION_CONTEXT, UNSUPPORTED_ADAPTER_MODE, UNSUPPORTED_ADAPTER_SIGNAL_INTENT, LONG_RESEARCH_SIGNAL_EXPOSED, SHORT_RESEARCH_SIGNAL_EXPOSED, DEFAULT_BLOCK_SIGNAL, CALCULATION_ERROR.
  - Future config design: `configs/dry_run_strategy.yaml` (design-only, not created).
  - Future output: `data/freqtrade_strategy/current_dry_run_strategy_runtime.json` (design-only, not created).
  - Future schema: `schemas/dry_run_strategy_runtime.schema.json` (design-only, not created).
  - PlantUML component and runtime flow diagrams included.
  - 5-step implementation plan defined: Models, Engine, Writer, Integration Tests, Final Review.
- MVP-8 Step 1 — Dry-Run Strategy Runtime Models complete.
  - `src/hunter/dry_run_strategy/__init__.py` — public API exports.
  - `src/hunter/dry_run_strategy/models.py` — Dry-Run Strategy Models (Step 1).
    - `DryRunStrategyState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
    - `DryRunStrategyMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
    - `DryRunSignalAction` enum: EXPOSE_LONG_RESEARCH_SIGNAL, EXPOSE_SHORT_RESEARCH_SIGNAL, BLOCK_SIGNAL, NO_SIGNAL.
    - `DryRunStrategyConfig` with 17 fields and MVP-8 safety validation.
    - `DryRunStrategyInputRefs` with path validation.
    - `DryRunStrategySafetyFlags` with 12 safety fields and `to_dict()` for JSON serialization.
    - `DryRunStrategyDataQuality` with 4 quality fields and `to_dict()` for JSON serialization.
    - `DryRunStrategyRuntimeContext` with 24 fields, version default "1.0", `blocked()` fail-closed factory, `is_blocking()` method.
    - 17 deterministic reason codes: MISSING_ADAPTER_DECISION_CONTEXT, INVALID_ADAPTER_DECISION_CONTEXT, ADAPTER_NOT_DRY_RUN_READY, ADAPTER_MODE_BLOCK_ALL, ADAPTER_SIGNAL_BLOCKED, DRY_RUN_DISABLED, LIVE_TRADING_ENABLED, REAL_ORDERS_ENABLED, LEVERAGE_ENABLED, SHORTING_ENABLED, STALE_ADAPTER_DECISION_CONTEXT, UNSUPPORTED_ADAPTER_MODE, UNSUPPORTED_ADAPTER_SIGNAL_INTENT, LONG_RESEARCH_SIGNAL_EXPOSED, SHORT_RESEARCH_SIGNAL_EXPOSED, DEFAULT_BLOCK_SIGNAL, CALCULATION_ERROR.
    - All models frozen/immutable with `__post_init__` validation.
    - 94 dry-run strategy model tests, all passing.
  - `tests/test_dry_run_strategy/__init__.py` — test package.
  - `tests/test_dry_run_strategy/test_models.py` — 94 model tests, all passing.
  - Full test suite: 1308 tests passing (1214 existing + 94 new).
  - No engine, no writer, no integration tests, no config YAML, no JSON schema, no deployable Freqtrade strategy class, no Freqtrade runtime connection, no Binance, no real exchange connection, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.
- MVP-8 Step 2 — Dry-Run Strategy Runtime Engine complete.
  - `src/hunter/dry_run_strategy/engine.py` — Dry-Run Strategy Engine (Step 2).
    - `build_dry_run_strategy_runtime_context()` — fail-closed runtime context builder with deterministic validation.
    - `validate_dry_run_strategy_inputs()` — 13 priority-ordered blocking checks, returns first blocking reason only.
    - `is_stale_adapter_decision_context()` — timestamp validity + age check.
    - `map_adapter_to_strategy_mode()` — adapter mode → strategy mode mapping.
    - `map_adapter_to_signal_action()` — adapter signal intent → strategy signal action mapping.
    - `build_safety_flags()` — safe defaults from config.
    - Allowed mappings:
      - `LONG_RESEARCH_ONLY` + `ALLOW_LONG_RESEARCH_SIGNAL` → `EXPOSE_LONG_RESEARCH_SIGNAL`
      - `SHORT_RESEARCH_ONLY` + `ALLOW_SHORT_RESEARCH_SIGNAL` → `EXPOSE_SHORT_RESEARCH_SIGNAL`
    - Unsafe/invalid/stale/unsupported → `BLOCK_SIGNAL`.
  - `src/hunter/dry_run_strategy/__init__.py` — updated with 6 engine function exports.
  - `tests/test_dry_run_strategy/test_engine.py` — 93 engine tests, all passing.
  - Full test suite: 1401 tests passing (1308 existing + 93 new).
  - No writer, no integration tests, no config YAML, no JSON schema, no deployable Freqtrade strategy class, no Freqtrade runtime connection, no Binance, no real exchange connection, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.
- MVP-8 Step 3 — Dry-Run Strategy Runtime JSON Writer complete.
  - `src/hunter/dry_run_strategy/writer.py` — Dry-Run Strategy Writer (Step 3).
    - `DEFAULT_DRY_RUN_STRATEGY_RUNTIME_PATH = data/freqtrade_strategy/current_dry_run_strategy_runtime.json`.
    - `dry_run_strategy_runtime_context_to_dict()` — deterministic JSON-safe serialization:
      - ISO-8601 timestamps with Z suffix.
      - Enum values as `.value` strings.
      - Tuple `reason_codes` as list.
      - Nested `input_refs`, `safety_flags`, `data_quality` as dicts.
    - `atomic_write_json()` — atomic write:
      - Parent directories created if missing.
      - Temp file in same directory.
      - `fsync` for durability.
      - `os.replace` for atomic rename.
      - Temp cleanup on failure.
      - Sorted, indented UTF-8 JSON with trailing newline.
    - `write_dry_run_strategy_runtime_context()` — default path or custom path, converts + writes atomically.
  - `src/hunter/dry_run_strategy/__init__.py` — updated with 4 writer exports.
  - `tests/test_dry_run_strategy/test_writer.py` — 42 writer tests, all passing.
  - Full test suite: 1443 tests passing (1401 existing + 42 new).
  - No engine changes, no model changes, no integration tests, no config YAML, no JSON schema, no deployable Freqtrade strategy class, no Freqtrade runtime connection, no Binance, no real exchange connection, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.
- MVP-8 Step 4 — Dry-Run Strategy Runtime Integration Tests complete.
  - `tests/test_dry_run_strategy/test_integration.py` — 48 integration tests, all passing.
    - Long research happy path: DRY_RUN_READY + LONG_RESEARCH_ONLY + ALLOW_LONG_RESEARCH_SIGNAL → EXPOSE_LONG_RESEARCH_SIGNAL, JSON round-trip verified.
    - Short research happy path: DRY_RUN_READY + SHORT_RESEARCH_ONLY + ALLOW_SHORT_RESEARCH_SIGNAL → EXPOSE_SHORT_RESEARCH_SIGNAL, JSON round-trip verified.
    - Missing adapter decision context: None input → MISSING_ADAPTER_DECISION_CONTEXT, BLOCK_SIGNAL.
    - Invalid adapter decision context: missing attrs → INVALID_ADAPTER_DECISION_CONTEXT, BLOCK_SIGNAL.
    - Adapter BLOCKED state → ADAPTER_NOT_DRY_RUN_READY, BLOCK_SIGNAL.
    - Adapter UNKNOWN state → ADAPTER_NOT_DRY_RUN_READY, BLOCK_SIGNAL.
    - Adapter DISABLED state → ADAPTER_NOT_DRY_RUN_READY, BLOCK_SIGNAL.
    - Adapter BLOCK_ALL mode → ADAPTER_MODE_BLOCK_ALL, BLOCK_SIGNAL.
    - Adapter BLOCK_SIGNAL intent → ADAPTER_SIGNAL_BLOCKED, BLOCK_SIGNAL.
    - dry_run false → DRY_RUN_DISABLED, BLOCK_SIGNAL.
    - live_trading_enabled true → LIVE_TRADING_ENABLED, BLOCK_SIGNAL.
    - real_orders_enabled true → REAL_ORDERS_ENABLED, BLOCK_SIGNAL.
    - leverage_enabled true → LEVERAGE_ENABLED, BLOCK_SIGNAL.
    - shorting_enabled true → SHORTING_ENABLED, BLOCK_SIGNAL.
    - Stale adapter decision context → STALE_ADAPTER_DECISION_CONTEXT, BLOCK_SIGNAL.
    - Unsupported adapter mode → UNSUPPORTED_ADAPTER_MODE, BLOCK_SIGNAL.
    - Unsupported signal intent → UNSUPPORTED_ADAPTER_SIGNAL_INTENT, BLOCK_SIGNAL.
    - Writer integration: parent directory creation, valid JSON with deterministic top-level keys, safety flags verification, blocked context JSON output.
    - Safety integration assertions: no production data path writes, no network calls, no Freqtrade runtime, no Binance, no real exchange, no API keys, no live trading, no leverage, no shorting, no real entry/exit execution logic.
  - Full test suite: 1491 tests passing (1443 existing + 48 new).
  - No model changes, no engine changes, no writer changes, no __init__.py changes.
  - No config YAML, no JSON schema, no deployable Freqtrade strategy class, no Freqtrade runtime connection, no Binance, no real exchange connection, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.
- MVP-8 remains design-first; implementation has not started.
- Full test suite: 1214 tests passing.

## SPEC-010 — Freqtrade Dry-Run Strategy Shell (Planning)

### Added

- SPEC-010 drafted for MVP-9 planning.
  - `specs/SPEC-010-Freqtrade-Dry-Run-Strategy-Shell.md` — Freqtrade Dry-Run Strategy Shell design document.
  - Designs a Freqtrade-compatible dry-run strategy shell that consumes MVP-8's `DryRunStrategyRuntimeContext` JSON from `data/freqtrade_strategy/current_dry_run_strategy_runtime.json`.
  - Key safety clarifications:
    - Research-only signal exposure means metadata/columns only, not real Freqtrade trade signals.
    - `populate_entry_trend` must never set `enter_long` or `enter_short` execution columns.
    - `populate_exit_trend` must never set `exit_long` or `exit_short` execution columns.
    - Freqtrade compatibility is an interface boundary only, not a real runtime/exchange connection.
    - The shell must not bypass MVP-5, MVP-6, MVP-7, or MVP-8 safety contexts.
  - No MVP-9 implementation started.
  - No source code, no tests, no config YAML, no JSON schema, no Freqtrade strategy class implementation.
  - No Binance, no real exchange, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.

## MVP-8 — Freqtrade Deployable Dry-Run Strategy (Complete)

### Added

- MVP-8 complete — SPEC-009 Freqtrade Deployable Dry-Run Strategy implemented.
  - Version 0.8.0-dev.
  - `src/hunter/dry_run_strategy/` package with models, engine, writer, and tests.
  - `src/hunter/dry_run_strategy/__init__.py` — public API exports (8 models + 6 engine functions + 4 writer functions + 17 reason codes).
  - `src/hunter/dry_run_strategy/models.py` — Dry-Run Strategy Runtime Models.
    - `DryRunStrategyState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
    - `DryRunStrategyMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
    - `DryRunSignalAction` enum: EXPOSE_LONG_RESEARCH_SIGNAL, EXPOSE_SHORT_RESEARCH_SIGNAL, BLOCK_SIGNAL, NO_SIGNAL.
    - `DryRunStrategyConfig` with 17 fields and MVP-8 safety validation (dry_run=True, all unsafe flags=False).
    - `DryRunStrategyInputRefs` with path validation.
    - `DryRunStrategySafetyFlags` with 12 safety fields and `to_dict()` for JSON serialization.
    - `DryRunStrategyDataQuality` with 4 quality fields and `to_dict()` for JSON serialization.
    - `DryRunStrategyRuntimeContext` with 24 fields, version default "1.0", `blocked()` fail-closed factory, `is_blocking()` method.
    - 17 deterministic reason codes: MISSING_ADAPTER_DECISION_CONTEXT, INVALID_ADAPTER_DECISION_CONTEXT, ADAPTER_NOT_DRY_RUN_READY, ADAPTER_MODE_BLOCK_ALL, ADAPTER_SIGNAL_BLOCKED, DRY_RUN_DISABLED, LIVE_TRADING_ENABLED, REAL_ORDERS_ENABLED, LEVERAGE_ENABLED, SHORTING_ENABLED, STALE_ADAPTER_DECISION_CONTEXT, UNSUPPORTED_ADAPTER_MODE, UNSUPPORTED_ADAPTER_SIGNAL_INTENT, LONG_RESEARCH_SIGNAL_EXPOSED, SHORT_RESEARCH_SIGNAL_EXPOSED, DEFAULT_BLOCK_SIGNAL, CALCULATION_ERROR.
    - All models frozen/immutable with `__post_init__` validation.
  - `src/hunter/dry_run_strategy/engine.py` — Dry-Run Strategy Runtime Engine.
    - `build_dry_run_strategy_runtime_context()` — fail-closed runtime context builder with deterministic validation.
    - `validate_dry_run_strategy_inputs()` — 13 priority-ordered blocking checks, returns first blocking reason only.
    - `is_stale_adapter_decision_context()` — timestamp validity + age check.
    - `map_adapter_to_strategy_mode()` — adapter mode → strategy mode mapping.
    - `map_adapter_to_signal_action()` — adapter signal intent → strategy signal action mapping.
    - `build_safety_flags()` — safe defaults from config.
    - Allowed mappings: LONG_RESEARCH_ONLY + ALLOW_LONG_RESEARCH_SIGNAL → EXPOSE_LONG_RESEARCH_SIGNAL; SHORT_RESEARCH_ONLY + ALLOW_SHORT_RESEARCH_SIGNAL → EXPOSE_SHORT_RESEARCH_SIGNAL.
    - Unsafe/invalid/stale/unsupported → BLOCK_SIGNAL.
  - `src/hunter/dry_run_strategy/writer.py` — Dry-Run Strategy Runtime JSON Writer.
    - `DEFAULT_DRY_RUN_STRATEGY_RUNTIME_PATH = data/freqtrade_strategy/current_dry_run_strategy_runtime.json`.
    - `dry_run_strategy_runtime_context_to_dict()` — deterministic JSON-safe serialization with ISO-8601 timestamps, enum values, tuple→list, nested dicts.
    - `atomic_write_json()` — atomic temp-file write with parent directory creation, fsync, os.replace, cleanup on failure.
    - `write_dry_run_strategy_runtime_context()` — default path or custom path, converts + writes atomically.
  - `tests/test_dry_run_strategy/__init__.py` — test package.
  - `tests/test_dry_run_strategy/test_models.py` — 94 model tests, all passing.
  - `tests/test_dry_run_strategy/test_engine.py` — 93 engine tests, all passing.
  - `tests/test_dry_run_strategy/test_writer.py` — 42 writer tests, all passing.
  - `tests/test_dry_run_strategy/test_integration.py` — 48 integration tests, all passing.
  - 277 MVP-8 tests total. Full test suite: 1491 tests passing.
  - Final review verdict: PASS. No defects found.
  - No config YAML. No JSON schema. No deployable Freqtrade strategy class. No Freqtrade runtime connection. No Binance. No real exchange. No API keys. No live trading. No real orders. No leverage. No shorting. No real entry/exit execution logic.

### Safety

- No Binance integration.
- No real exchange connection.
- No real Freqtrade runtime connection.
- No API keys.
- No live trading.
- No real orders.
- No leverage.
- No shorting.
- No real entry/exit execution logic.
- No deployable Freqtrade strategy class created.
- No config YAML created.
- No JSON schema created.

### Next

- MVP-8 Step 1 — Dry-Run Strategy Runtime Models.

## MVP-7 — Freqtrade Dry-Run Strategy Adapter (Complete)

### Added

- `src/hunter/strategy_adapter/__init__.py` — public API exports (Step 1).
- `src/hunter/strategy_adapter/models.py` — Strategy Adapter Models (Step 1).
  - `AdapterState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
  - `AdapterMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
  - `AdapterSignalIntent` enum: ALLOW_LONG_RESEARCH_SIGNAL, ALLOW_SHORT_RESEARCH_SIGNAL, BLOCK_SIGNAL, NO_SIGNAL.
  - `AdapterConfig` with MVP-7 safety validation (dry_run_required=True, all unsafe flags False, all runtime/execution flags False).
  - `AdapterInputRefs` for audit trail references to strategy context and adapter decision.
  - `AdapterSafetyFlags` with 12 fields including adapter_runtime_allowed, freqtrade_runtime_allowed, strategy_class_allowed, entry_signal_allowed, exit_signal_allowed, order_execution_allowed (all default False).
  - `AdapterDataQuality` with strategy_context_present, strategy_context_valid, strategy_context_stale, reason.
  - `AdapterDecisionContext` with 22 fields including signal_intent, strategy_contract_state, strategy_contract_mode, adapter_runtime_allowed, freqtrade_runtime_allowed, strategy_class_allowed, entry_signal_allowed, exit_signal_allowed, order_execution_allowed.
  - `AdapterDecisionContext.blocked()` fail-closed factory producing BLOCKED + BLOCK_ALL + BLOCK_SIGNAL + version "1.0".
  - 15 deterministic reason codes: MISSING_STRATEGY_CONTEXT, INVALID_STRATEGY_CONTEXT, STRATEGY_CONTRACT_NOT_DRY_RUN_READY, STRATEGY_CONTRACT_MODE_BLOCK_ALL, DRY_RUN_DISABLED, LIVE_TRADING_ENABLED, REAL_ORDERS_ENABLED, LEVERAGE_ENABLED, SHORTING_ENABLED, STALE_STRATEGY_CONTEXT, UNSUPPORTED_STRATEGY_MODE, LONG_RESEARCH_SIGNAL_ALLOWED, SHORT_RESEARCH_SIGNAL_ALLOWED, DEFAULT_BLOCK_SIGNAL, CALCULATION_ERROR.
  - All models frozen/immutable with `__post_init__` validation.
  - 94 strategy adapter model tests, all passing.

- `src/hunter/strategy_adapter/engine.py` — Strategy Adapter Engine (Step 2).
  - `build_adapter_decision_context()` — main entry point implementing all 11 fail-closed adapter rules + 2 allowed + 1 fallback from SPEC-008 in priority order.
  - `validate_adapter_inputs()` — deterministic priority-ordered validation, returns first blocking reason only.
  - `is_stale_strategy_context()` — checks timestamp validity (missing/naive/None → stale) and age against threshold.
  - `map_strategy_to_adapter_mode()` — maps `StrategyContractMode` → `AdapterMode`.
  - `map_strategy_to_signal_intent()` — maps `StrategyContractMode` → `AdapterSignalIntent`.
  - `build_safety_flags()` — constructs `AdapterSafetyFlags` from config with safe defaults.
  - Allowed mappings: LONG_RESEARCH_ONLY → ALLOW_LONG_RESEARCH_SIGNAL, SHORT_RESEARCH_ONLY → ALLOW_SHORT_RESEARCH_SIGNAL.
  - Blocking mappings: all unsafe/invalid/stale/unsupported → BLOCK_SIGNAL.
  - 75 strategy adapter engine tests, all passing.

- `src/hunter/strategy_adapter/writer.py` — Adapter Decision JSON Writer (Step 3).
  - `adapter_decision_context_to_dict()` — serializes all 22 `AdapterDecisionContext` fields to JSON-compatible dict.
  - `atomic_write_json()` — atomic temp-file write with `os.replace()`, parent directory creation, cleanup on failure.
  - `write_adapter_decision_context()` — writes to `data/strategy_adapter/current_adapter_decision.json` by default.
  - `DEFAULT_ADAPTER_DECISION_PATH = data/strategy_adapter/current_adapter_decision.json`.
  - ISO-8601 UTC timestamps ending with Z, enum string values, signal_intent as string, reason_codes as list, nested dicts, version "1.0".
  - 41 writer tests, all passing.

- `tests/test_strategy_adapter/test_integration.py` — Integration Tests (Step 4).
  - 45 end-to-end integration tests.
  - Full pipeline: StrategyContext → build_adapter_decision_context() → write_adapter_decision_context() → JSON verification.
  - Allowed LONG_RESEARCH_ONLY signal flow (DRY_RUN_READY → ALLOW_LONG_RESEARCH_SIGNAL).
  - Allowed SHORT_RESEARCH_ONLY signal flow (DRY_RUN_READY → ALLOW_SHORT_RESEARCH_SIGNAL).
  - Blocked signal flows: missing, BLOCKED, UNKNOWN, DISABLED strategy contract states; BLOCK_ALL strategy contract mode; stale StrategyContext; unsafe flags (dry_run false, live_trading_enabled true, real_orders_enabled true, leverage_enabled true, shorting_enabled true).
  - JSON output verification: all 22 fields, enum strings, signal_intent, reason_codes, safety_flags, data_quality, version "1.0", ISO-8601 timestamps.
  - Atomic write tests with tmp_path, nested directory creation, no production path usage.
  - Safety tests: no network, no trading logic, no JSON input reading, no Freqtrade runtime, no Binance, all flags safe.

- SPEC-008 Freqtrade Dry-Run Strategy Adapter design finalized and polished.
  - AdapterState, AdapterMode, AdapterSignalIntent, AdapterDecisionContext defined.
  - Fail-closed adapter rules, deterministic reason codes, future config/schema/output defined.
  - PlantUML component and flow diagrams included.
  - 5-step implementation plan defined.

- MVP-7 Step 5 — Final Review and Polish complete.
  - 63 final review checklist items passed.
  - No issues found. No fixes applied.
  - Full test suite: 1214 tests passing.
  - Adapter remains dry-run-only and fail-closed.
  - No Binance integration. No real Freqtrade runtime integration. No deployable strategy class.
  - No config YAML. No JSON schema. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

### Changed

- `src/hunter/__init__.py` — version bumped to `0.7.0-dev`.


### Added

- `src/hunter/execution/models.py` — Execution Bridge Models (Step 1).
  - `ExecutionState` enum: ENABLED, BLOCKED, DRY_RUN_ONLY, UNKNOWN.
  - `ExecutionMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL, DRY_RUN_ONLY.
  - `ExecutionBridgeConfig` with MVP-4 safety validation (dry_run_required=True, live_trading_enabled=False, etc.).
  - `ExecutionInputRefs` for audit trail references to decision output.
  - `ExecutionSafetyFlags` with human_override_required (default false) and max_context_age_seconds (default 300).
  - `ExecutionContext` with version field default "1.0" for backward-compatible contract evolution.
  - `ExecutionContext.blocked()` fail-closed factory producing BLOCKED + BLOCK_ALL + dry_run True + version "1.0".
  - All models frozen/immutable with __post_init__ validation.
  - 49 execution model tests, all passing.

- `src/hunter/execution/engine.py` — Execution Bridge Engine (Step 2).
  - `build_execution_context()` — main entry point implementing all 15 fail-closed rules from SPEC-005 in priority order.
  - `validate_execution_inputs()` — validates DecisionOutput against all safety constraints.
  - `is_stale_decision()` — checks DecisionOutput age against stale_decision_minutes threshold.
  - `map_decision_to_execution_mode()` — maps DecisionAction to ExecutionMode.
  - `build_safety_flags()` — constructs ExecutionSafetyFlags with all defaults safe.
  - All successful paths produce DRY_RUN_ONLY (ENABLED reserved for future).
  - All blocked paths produce BLOCKED + BLOCK_ALL + dry_run=True.
  - Missing/invalid/stale/unsafe inputs all block by default.
  - input_refs populated with decision timestamp and source on successful paths.
  - 45 execution engine tests, all passing.

- `src/hunter/execution/writer.py` — Execution Context Writer (Step 3).
  - `execution_context_to_dict()` — serializes all 14 ExecutionContext fields to JSON-compatible dict.
  - `atomic_write_json()` — atomic temp-file write with os.replace(), parent directory creation, cleanup on failure.
  - `write_execution_context()` — writes to `data/execution/current_execution_context.json` by default.
  - ISO-8601 timestamp serialization, enum string serialization.
  - safety_flags, input_refs, data_quality, version all preserved in JSON output.
  - 20 execution writer tests, all passing.

- `tests/test_execution/test_integration.py` — Integration Tests (Step 4).
  - 30 end-to-end integration tests.
  - Full pipeline: DecisionOutput → build_execution_context() → write_execution_context() → JSON verification.
  - Long-only research enable scenario (ENABLE_LONG_ONLY_RESEARCH → DRY_RUN_ONLY + LONG_RESEARCH_ONLY).
  - Short-only research enable scenario (ENABLE_SHORT_ONLY_RESEARCH → DRY_RUN_ONLY + SHORT_RESEARCH_ONLY).
  - Block scenarios: BLOCK_ALL, MANUAL_REVIEW, stale, missing, invalid, blocked decision state.
  - Unsafe config rejection tests: dry_run=False, live_trading=True, exchange=True, freqtrade=True all raise ValueError.
  - JSON output verification: all 18 fields, enum strings, safety_flags, version "1.0", ISO-8601 timestamps.
  - Atomic write tests with tmp_path, nested directory creation, no production path usage.
  - Safety tests: no network, no trading logic, no JSON input reading, no Freqtrade runtime, all flags safe.

- Final Review and Polish (Step 5).
  - All 29 review checklist items verified and passing.
  - No issues found. No fixes applied.
  - Full test suite: 538 tests passing.

### Safety

- No application code modified during integration tests or review.
- No config YAML created for execution bridge.
- No JSON Schema files created.
- No DecisionOutput JSON reading used.
- No Freqtrade strategy class created.
- No trading execution logic added.
- No Binance integration.
- No live trading enabled.
- No network calls.
- All safety flags remain False or safe (dry_run=True).
- All blocked paths produce BLOCKED + BLOCK_ALL.
- ENABLED state exists in enum but is never emitted by MVP-4.

### Next

- MVP-5 Planning — Freqtrade Integration design.

## 0.4.0-dev — MVP-5 Planning — Freqtrade Integration Design (Complete)

### Added

- `specs/SPEC-006-Freqtrade-Integration.md` — Freqtrade Integration specification (design-only, no code).
  - Consumes in-memory `ExecutionContext` from MVP-4.
  - Future input reference: `data/execution/current_execution_context.json`.
  - Outputs: `data/freqtrade/current_freqtrade_context.json`.
  - Dry-run only: the only non-blocked state is `DRY_RUN_READY`.
  - Fail-closed `BLOCK_ALL` by default for all unsafe inputs.
  - `FreqtradeBridgeState` enum design: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
  - `FreqtradeBridgeMode` enum design: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
  - `FreqtradeBridgeContext` with 18 fields including version default `"1.0"`.
  - 17 fail-closed rules in deterministic priority order.
  - `configs/freqtrade_bridge.yaml` future design only (not created in MVP-5).
  - `schemas/freqtrade_bridge_context.schema.json` future design only (not created in MVP-5).
  - Mock Freqtrade strategy deferred to MVP-6 or later.
  - No code implemented yet.

### Safety

- No code implemented for Freqtrade Integration.
- No Binance integration.
- No real Freqtrade runtime integration.
- No strategy class.
- No trading logic (pairlist, order, stake, leverage, stoploss, ROI, entry, exit).
- No live trading.
- No leverage.
- No shorting.
- No API keys.
- No network calls.

### Next

- MVP-5 Step 1 — Freqtrade Bridge Models.

## 0.4.0-dev — MVP-5 Step 1 — Freqtrade Bridge Models (Complete)

### Added

- `src/hunter/freqtrade_bridge/models.py` — Freqtrade Bridge Models.
  - `FreqtradeBridgeState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
  - `FreqtradeBridgeMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
  - `FreqtradeBridgeConfig` with 12 fields and MVP-5 safety validation.
  - `FreqtradeBridgeInputRefs` for execution context audit trail references.
  - `FreqtradeBridgeSafetyFlags` with 10 safety fields and `to_dict()` for JSON serialization.
  - `FreqtradeBridgeDataQuality` with freshness, validity, validation errors, and `to_dict()`.
  - `FreqtradeBridgeContext` with 18 fields, version default `"1.0"`, fail-closed by default.
  - `FreqtradeBridgeContext.blocked()` factory producing BLOCKED + BLOCK_ALL + dry_run=True + version `"1.0"`.
  - All models frozen/immutable with `__post_init__` validation.
  - 62 Freqtrade bridge model tests, all passing.
  - Full test suite: 600 tests passing.

### Safety

- No Freqtrade Bridge Engine exists yet.
- No Freqtrade Bridge Writer exists yet.
- No config YAML created.
- No JSON Schema files created.
- No ExecutionContext JSON reading.
- No Binance integration.
- No real Freqtrade runtime integration.
- No strategy class.
- No trading logic (pairlist, order, stake, leverage, stoploss, ROI, entry, exit).
- No live trading.
- No leverage.
- No shorting.
- No API keys.
- No network calls.

### Next

- MVP-5 Step 2 — Freqtrade Bridge Engine.

## 0.4.0-dev — MVP-5 Step 2 — Freqtrade Bridge Engine (Complete)

### Added

- `src/hunter/freqtrade_bridge/engine.py` — Freqtrade Bridge Engine.
  - `build_freqtrade_bridge_context()` — main entry point consuming in-memory `ExecutionContext`.
  - `validate_freqtrade_bridge_inputs()` — 12 fail-closed rules in priority order.
  - `is_stale_execution_context()` — checks ExecutionContext age against stale threshold.
  - `map_execution_to_bridge_mode()` — maps ExecutionMode to FreqtradeBridgeState/Mode.
  - `build_safety_flags()` — constructs FreqtradeBridgeSafetyFlags from ExecutionContext.
  - All unsafe inputs produce BLOCKED + BLOCK_ALL with descriptive reason codes.
  - DRY_RUN_ONLY + LONG_RESEARCH_ONLY → DRY_RUN_READY + LONG_RESEARCH_ONLY.
  - DRY_RUN_ONLY + SHORT_RESEARCH_ONLY → DRY_RUN_READY + SHORT_RESEARCH_ONLY.
  - BLOCK_ALL → BLOCKED + BLOCK_ALL.
  - UNKNOWN → BLOCKED + BLOCK_ALL.
  - Checks both ExecutionContext direct fields and nested safety_flags for safety.
  - 57 Freqtrade bridge engine tests, all passing.
  - Full test suite: 657 tests passing.

### Safety

- No Freqtrade Bridge Writer exists yet.
- No config YAML created.
- No JSON Schema files created.
- No ExecutionContext JSON reading.
- No Binance integration.
- No real Freqtrade runtime integration.
- No strategy class.
- No trading logic (pairlist, order, stake, leverage, stoploss, ROI, entry, exit).
- No live trading.
- No leverage.
- No shorting.
- No API keys.
- No network calls.
- No JSON reading or writing.

### Next

- MVP-5 Step 3 — Freqtrade Bridge Writer.

## 0.4.0-dev — MVP-5 Step 3 — Freqtrade Bridge Writer (Complete)

### Added

- `src/hunter/freqtrade_bridge/writer.py` — Freqtrade Bridge Writer.
  - `freqtrade_bridge_context_to_dict()` — serializes all 18 FreqtradeBridgeContext fields to JSON-compatible dict.
  - `atomic_write_json()` — atomic temp-file write with `os.replace()`, parent directory creation, cleanup on failure.
  - `write_freqtrade_bridge_context()` — writes to `data/freqtrade/current_freqtrade_context.json` by default.
  - ISO-8601 timestamp serialization with `Z` suffix.
  - Enum string serialization via `.value`.
  - `safety_flags` serialization via `to_dict()` with all 10 fields.
  - `data_quality` serialization via `to_dict()` with freshness, validity, validation errors.
  - `input_refs` nested dict with `execution_context_timestamp` and `execution_context_version`.
  - `version` always `"1.0"`.
  - `reason_codes` list of strings.
  - 25 Freqtrade bridge writer tests, all passing.
  - Full test suite: 682 tests passing.

### MVP-5 Step 4 — Freqtrade Bridge Integration Tests

- `tests/test_freqtrade_bridge/test_integration.py` — 40 integration tests.
  - End-to-end flow: ExecutionContext → `build_freqtrade_bridge_context()` → `write_freqtrade_bridge_context()`.
  - Long research dry-run-ready scenario: DRY_RUN_ONLY + LONG_RESEARCH_ONLY → DRY_RUN_READY + LONG_RESEARCH_ONLY.
  - Short research dry-run-ready scenario: DRY_RUN_ONLY + SHORT_RESEARCH_ONLY → DRY_RUN_READY + SHORT_RESEARCH_ONLY.
  - Fail-closed blocked scenarios: BLOCK_ALL, stale, missing, blocked state, dry_run false, live trading true, exchange true, freqtrade enabled true, dry_run_only mode.
  - JSON output verification: all 18 fields present, enum values as strings, version "1.0", ISO-8601 timestamps, safety_flags with all 10 fields, input_refs, data_quality, reason_codes.
  - Atomic write and path tests: no temp files left, nested directory creation, no production path used, overwrite existing file.
  - Safety checks: no network, no trading logic, no Freqtrade runtime, no strategy, no leverage, no shorting, no live trading, no real orders, no exchange, no freqtrade runtime, dry_run always true, no JSON input reading.
  - 40 integration tests, all passing.
  - Full test suite: 722 tests passing.
  - No config YAML created.
  - No JSON Schema created.
  - No ExecutionContext JSON reading used.
  - No Freqtrade strategy class created.
  - No Binance integration.
  - No real Freqtrade runtime integration.
  - No trading execution logic.
  - No live trading enabled.
  - No leverage enabled.
  - No shorting enabled.
  - No API keys.
  - No network calls.
  - Next step: MVP-5 Step 5 — Final Review and Polish.

### MVP-5 Complete — Freqtrade Integration Boundary

- SPEC-007 Freqtrade Strategy Contract design finalized and polished.
  - Strategy contract states, modes, StrategyContext, fail-closed rules, reason codes defined.
  - Future config design: `configs/strategy_contract.yaml`.
  - Future schema design: `schemas/strategy_context.schema.json`.
  - PlantUML component and flow diagrams included.
  - Implementation split into 5 steps: Models, Engine, Writer, Integration Tests, Final Review.
  - No MVP-6 code implemented yet.
  - Full test suite: 722 tests passing.
- MVP-6 Step 1 — Strategy Contract Models complete.
  - `src/hunter/strategy_contract/__init__.py` — public API exports.
  - `src/hunter/strategy_contract/models.py` — 7 model types.
    - `StrategyContractState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
    - `StrategyContractMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
    - `StrategyContractConfig` with 14 fields and MVP-6 safety validation.
    - `StrategyContractInputRefs` with path validation.
    - `StrategyContractSafetyFlags` with 9 safety fields and `to_dict()` for JSON serialization.
    - `StrategyContractDataQuality` with 4 quality fields and `to_dict()` for JSON serialization.
    - `StrategyContext` with 18 fields, version default "1.0", `blocked()` fail-closed factory, `is_blocking()` method.
  - 15 deterministic reason codes: MISSING_BRIDGE_CONTEXT, INVALID_BRIDGE_CONTEXT, BRIDGE_NOT_DRY_RUN_READY, BRIDGE_MODE_BLOCK_ALL, DRY_RUN_DISABLED, LIVE_TRADING_ENABLED, REAL_ORDERS_ENABLED, LEVERAGE_ENABLED, SHORTING_ENABLED, STALE_BRIDGE_CONTEXT, UNSUPPORTED_BRIDGE_MODE, LONG_RESEARCH_ALLOWED, SHORT_RESEARCH_ALLOWED, DEFAULT_BLOCK_ALL, CALCULATION_ERROR.
  - `tests/test_strategy_contract/__init__.py` — test package.
  - `tests/test_strategy_contract/test_models.py` — 84 model tests, all passing.
  - Full test suite: 806 tests passing (722 existing + 84 new).
  - No engine, no writer, no integration tests, no config YAML, no JSON schema, no strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting.
- MVP-6 Step 2 — Strategy Contract Engine complete.
  - `src/hunter/strategy_contract/engine.py` — 5 engine functions.
    - `build_strategy_context(...)` — main entry point, implements 14 fail-closed rules.
    - `validate_strategy_contract_inputs(...)` — deterministic priority-ordered validation, returns first blocking reason only.
    - `is_stale_bridge_context(...)` — checks timestamp validity and age against threshold.
    - `map_bridge_to_strategy_mode(...)` — maps bridge mode to strategy contract mode.
    - `build_safety_flags(...)` — constructs safety flags from config with safe defaults.
  - `src/hunter/strategy_contract/__init__.py` — updated exports.
  - `tests/test_strategy_contract/test_engine.py` — 72 engine tests, all passing.
  - Allowed mappings: LONG_RESEARCH_ONLY → LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY → SHORT_RESEARCH_ONLY.
  - Blocking mappings: unsafe/invalid/stale/unsupported → BLOCK_ALL.
  - Full test suite: 878 tests passing (806 existing + 72 new).
  - No writer, no integration tests, no config YAML, no JSON schema, no strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting.
- MVP-6 Step 3 — Strategy Context Writer complete.
  - `src/hunter/strategy_contract/writer.py` — 3 writer functions + default path constant.
    - `DEFAULT_STRATEGY_CONTEXT_PATH = data/strategy/current_strategy_context.json`.
    - `strategy_context_to_dict(...)` — serializes StrategyContext to JSON-compatible dict.
    - `atomic_write_json(...)` — temp-file + os.replace atomic write, auto cleanup on failure.
    - `write_strategy_context(...)` — entry point, writes to default or custom path.
  - `src/hunter/strategy_contract/__init__.py` — updated exports.
  - `tests/test_strategy_contract/test_writer.py` — 36 writer tests, all passing.
  - JSON serialization: ISO-8601 UTC timestamps ending with Z, enum string values, reason_codes as list, nested input_refs/safety_flags/data_quality as dicts, version "1.0".
  - Full test suite: 914 tests passing (878 existing + 36 new).
  - No integration tests, no config YAML, no JSON schema, no strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting.
- MVP-6 Step 4 — Strategy Contract Integration Tests complete.
  - `tests/test_strategy_contract/test_integration.py` — 45 integration tests, all passing.
  - Integration coverage:
    - Allowed flows: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY (full pipeline engine + writer + JSON verification).
    - Blocked flows: missing bridge context, BLOCKED bridge state, UNKNOWN bridge state, DISABLED bridge state, BLOCK_ALL bridge mode, stale bridge context.
    - Unsafe flags blocked: dry_run false, live_trading_enabled true, real_orders_enabled true, leverage_enabled true, shorting_enabled true.
    - JSON output verification: ISO-8601 timestamps, enum strings, reason_codes list, input_refs/safety_flags/data_quality dicts, version "1.0", blocked vs allowed reason codes.
    - Atomic/path verification: custom tmp_path, nested directory creation, overwrite existing file, no temp files left, default path constant.
    - Safety absence checks: no config YAML, no JSON schema, no strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting, no entry/exit logic, no trading fields.
  - Full test suite: 959 tests passing (914 existing + 45 new).
  - No application code changed.
  - No config YAML, no JSON schema, no strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting.
- MVP-6 Step 4 — Strategy Contract Integration Tests complete.
  - `tests/test_strategy_contract/test_integration.py` — 45 integration tests, all passing.
  - Integration coverage:
    - Allowed flows: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY (full pipeline engine + writer + JSON verification).
    - Blocked flows: missing bridge context, BLOCKED bridge state, UNKNOWN bridge state, DISABLED bridge state, BLOCK_ALL bridge mode, stale bridge context.
    - Unsafe flags blocked: dry_run false, live_trading_enabled true, real_orders_enabled true, leverage_enabled true, shorting_enabled true.
    - JSON output verification: ISO-8601 timestamps, enum strings, reason_codes list, input_refs/safety_flags/data_quality dicts, version "1.0", blocked vs allowed reason codes.
    - Atomic/path verification: custom tmp_path, nested directory creation, overwrite existing file, no temp files left, default path constant.
    - Safety absence checks: no config YAML, no JSON schema, no strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting, no entry/exit logic, no trading fields.
  - Full test suite: 959 tests passing (914 existing + 45 new).
  - No application code changed.
  - No config YAML, no JSON schema, no strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting.
- MVP-6 Step 5 — Final Review and Polish complete.
  - All 60 final review checklist items passed.
  - No issues found. No fixes applied.
  - Version bumped to 0.6.0-dev.
- SPEC-008 Freqtrade Dry-Run Strategy Adapter design finalized and polished.
  - AdapterState enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
  - AdapterMode enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
  - AdapterSignalIntent enum: ALLOW_LONG_RESEARCH_SIGNAL, ALLOW_SHORT_RESEARCH_SIGNAL, BLOCK_SIGNAL, NO_SIGNAL.
  - AdapterDecisionContext with 22 fields including adapter_runtime_allowed, freqtrade_runtime_allowed, strategy_class_allowed, entry_signal_allowed, exit_signal_allowed, order_execution_allowed.
  - 15 deterministic reason codes: MISSING_STRATEGY_CONTEXT, INVALID_STRATEGY_CONTEXT, STRATEGY_CONTRACT_NOT_DRY_RUN_READY, STRATEGY_CONTRACT_MODE_BLOCK_ALL, DRY_RUN_DISABLED, LIVE_TRADING_ENABLED, REAL_ORDERS_ENABLED, LEVERAGE_ENABLED, SHORTING_ENABLED, STALE_STRATEGY_CONTEXT, UNSUPPORTED_STRATEGY_MODE, LONG_RESEARCH_SIGNAL_ALLOWED, SHORT_RESEARCH_SIGNAL_ALLOWED, DEFAULT_BLOCK_SIGNAL, CALCULATION_ERROR.
  - Fail-closed adapter rules: 11 blocking + 2 allowed + 1 fallback.
  - Future config design: `configs/strategy_adapter.yaml`.
  - Future output: `data/strategy_adapter/current_adapter_decision.json`.
  - Future schema: `schemas/strategy_adapter_decision.schema.json`.
  - PlantUML component and adapter flow diagrams included.
  - Implementation split into 5 steps: Models, Engine, Writer, Integration Tests, Final Review.
  - No MVP-7 code implemented yet.
  - Full test suite: 959 tests passing.
- MVP-7 Step 1 — Strategy Adapter Models complete.
  - `src/hunter/strategy_adapter/__init__.py` — public API exports.
  - `src/hunter/strategy_adapter/models.py` — 8 model types.
    - `AdapterState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
    - `AdapterMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
    - `AdapterSignalIntent` enum: ALLOW_LONG_RESEARCH_SIGNAL, ALLOW_SHORT_RESEARCH_SIGNAL, BLOCK_SIGNAL, NO_SIGNAL.
    - `AdapterConfig` with 17 fields and MVP-7 safety validation.
    - `AdapterInputRefs` with path validation.
    - `AdapterSafetyFlags` with 12 safety fields and `to_dict()` for JSON serialization.
    - `AdapterDataQuality` with 4 quality fields and `to_dict()` for JSON serialization.
    - `AdapterDecisionContext` with 22 fields, version default "1.0", `blocked()` fail-closed factory, `is_blocking()` method.
  - 15 deterministic reason codes: MISSING_STRATEGY_CONTEXT, INVALID_STRATEGY_CONTEXT, STRATEGY_CONTRACT_NOT_DRY_RUN_READY, STRATEGY_CONTRACT_MODE_BLOCK_ALL, DRY_RUN_DISABLED, LIVE_TRADING_ENABLED, REAL_ORDERS_ENABLED, LEVERAGE_ENABLED, SHORTING_ENABLED, STALE_STRATEGY_CONTEXT, UNSUPPORTED_STRATEGY_MODE, LONG_RESEARCH_SIGNAL_ALLOWED, SHORT_RESEARCH_SIGNAL_ALLOWED, DEFAULT_BLOCK_SIGNAL, CALCULATION_ERROR.
  - `tests/test_strategy_adapter/__init__.py` — test package.
  - `tests/test_strategy_adapter/test_models.py` — 94 model tests, all passing.
  - Full test suite: 1053 tests passing (959 existing + 94 new).
  - No engine, no writer, no integration tests, no config YAML, no JSON schema, no deployable strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting, no entry/exit execution logic.
- MVP-7 Step 2 — Strategy Adapter Engine complete.
  - `src/hunter/strategy_adapter/engine.py` — 6 engine functions.
    - `build_adapter_decision_context(...)` — main entry point implementing all 11 fail-closed adapter rules + 2 allowed + 1 fallback.
    - `validate_adapter_inputs(...)` — deterministic priority-ordered validation, returns first blocking reason only.
    - `is_stale_strategy_context(...)` — checks timestamp validity (missing/naive/None → stale) and age against threshold.
    - `map_strategy_to_adapter_mode(...)` — maps `StrategyContractMode` → `AdapterMode`.
    - `map_strategy_to_signal_intent(...)` — maps `StrategyContractMode` → `AdapterSignalIntent`.
    - `build_safety_flags(...)` — constructs `AdapterSafetyFlags` from config with safe defaults.
  - Allowed mappings: `LONG_RESEARCH_ONLY` → `ALLOW_LONG_RESEARCH_SIGNAL`, `SHORT_RESEARCH_ONLY` → `ALLOW_SHORT_RESEARCH_SIGNAL`.
  - Blocking mappings: all unsafe/invalid/stale/unsupported → `BLOCK_SIGNAL`.
  - `src/hunter/strategy_adapter/__init__.py` — updated exports.
  - `tests/test_strategy_adapter/test_engine.py` — 75 engine tests, all passing.
  - Full test suite: 1128 tests passing (1053 existing + 75 new).
  - No writer, no integration tests, no config YAML, no JSON schema, no deployable strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting, no entry/exit execution logic.

- MVP-7 Step 4 — Strategy Adapter Integration Tests (Complete).
  - `tests/test_strategy_adapter/test_integration.py` — 45 integration tests, all passing.
  - Integration coverage: allowed LONG_RESEARCH_ONLY and SHORT_RESEARCH_ONLY signal flows; blocked missing, BLOCKED, UNKNOWN, DISABLED strategy contract states; blocked BLOCK_ALL strategy contract mode; blocked stale StrategyContext; blocked unsafe flags (dry_run false, live_trading_enabled true, real_orders_enabled true, leverage_enabled true, shorting_enabled true); JSON output verification; atomic/path verification; safety absence checks.
  - Full test suite: 1214 tests passing (1169 existing + 45 new).
  - No application code changed. No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime. No Binance. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

- MVP-7 Step 3 — Adapter Decision JSON Writer (Complete).
  - `src/hunter/strategy_adapter/writer.py` — writer functions.
  - `src/hunter/strategy_adapter/__init__.py` — updated exports.
  - `tests/test_strategy_adapter/test_writer.py` — 41 writer tests, all passing.
  - `DEFAULT_ADAPTER_DECISION_PATH = data/strategy_adapter/current_adapter_decision.json`.
  - `adapter_decision_context_to_dict()` — serializes `AdapterDecisionContext` to JSON-compatible dict.
  - `atomic_write_json()` — atomic temp-file write with `os.replace()`, parent directory creation, cleanup on failure.
  - `write_adapter_decision_context()` — writes to `data/strategy_adapter/current_adapter_decision.json` by default.
  - ISO-8601 UTC timestamp serialization ending with `Z`.
  - Enum string serialization: `adapter_state`, `adapter_mode`, `signal_intent`.
  - `reason_codes` serialized as `list[str]`.
  - Nested `input_refs`, `safety_flags`, `data_quality` serialized as dicts.
  - `version` is `"1.0"`.
  - Full test suite: 1169 tests passing (1128 existing + 41 new).
  - No integration tests yet. No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime. No Binance. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

- MVP-6 — Freqtrade Strategy Contract complete.
  - SPEC-007 finalized and polished.
  - Strategy contract produces dry-run-only fail-closed StrategyContext for future strategy-facing consumers.
  - Default output path: `data/strategy/current_strategy_context.json`.
  - Full test suite: 959 tests passing.
  - No Binance integration.
  - No real Freqtrade runtime integration.
  - No strategy class.
  - No config YAML.
  - No JSON schema.
  - No API keys.
  - No live trading.
  - No real orders.
  - No leverage.
  - No shorting.
- SPEC-006 Freqtrade Integration design complete and reviewed.
- Step 1 Freqtrade Bridge Models complete: `src/hunter/freqtrade_bridge/models.py` with 62 tests.
- Step 2 Freqtrade Bridge Engine complete: `src/hunter/freqtrade_bridge/engine.py` with 57 tests.
- Step 3 Freqtrade Bridge Writer complete: `src/hunter/freqtrade_bridge/writer.py` with 25 tests.
- Step 4 Integration Tests complete: `tests/test_freqtrade_bridge/test_integration.py` with 40 tests.
- Step 5 Final Review complete: all 35 checklist items verified, no issues found, no fixes required.
- Full test suite: 722 tests passing.
- Output path: `data/freqtrade/current_freqtrade_context.json`.
- Dry-run only: all outputs have `dry_run=True` and `live_trading_enabled=False`.
- Fail-closed: all unsafe inputs produce `BLOCKED` + `BLOCK_ALL`.
- No Binance integration.
- No real Freqtrade runtime integration.
- No strategy class.
- No trading logic (pairlist, order, stake, leverage, stoploss, ROI, entry, exit).
- No live trading.
- No leverage.
- No shorting.
- No API keys.
- No network calls.
- Next step: MVP-6 Planning — Freqtrade Strategy Contract design.

### Safety

- No config YAML created.
- No JSON Schema files created.
- No ExecutionContext JSON reading.
- No Binance integration.
- No real Freqtrade runtime integration.
- No strategy class.
- No trading logic (pairlist, order, stake, leverage, stoploss, ROI, entry, exit).
- No live trading.
- No leverage.
- No shorting.
- No API keys.
- No network calls.
- No JSON input reading.

### Next

- MVP-5 Step 4 — Integration Tests.

## 0.4.0-dev — MVP-4 Step 4 — Integration Tests (Complete)

### Added

- `tests/test_execution/test_integration.py` created with 30 end-to-end integration tests.
- Full pipeline: DecisionOutput → `build_execution_context()` → `write_execution_context()` → JSON verification.
- Long-only research enable scenario (`ENABLE_LONG_ONLY_RESEARCH` → `DRY_RUN_ONLY` + `LONG_RESEARCH_ONLY`).
- Short-only research enable scenario (`ENABLE_SHORT_ONLY_RESEARCH` → `DRY_RUN_ONLY` + `SHORT_RESEARCH_ONLY`).
- Block scenarios: `BLOCK_ALL`, `MANUAL_REVIEW`, stale, missing, invalid, blocked decision state.
- Unsafe config rejection tests: `dry_run=False`, `live_trading=True`, `exchange=True`, `freqtrade=True` all raise `ValueError`.
- JSON output verification: all 18 fields, enum strings, `safety_flags`, version `"1.0"`, ISO-8601 timestamps.
- Atomic write tests with `tmp_path`, nested directory creation, no production path usage.
- Safety tests: no network, no trading logic, no JSON input reading, no Freqtrade runtime, all flags safe.
- 30 integration tests, all passing.
- Full test suite: 538 tests passing (508 existing + 30 new).

### Safety

- No application code modified.
- No config YAML created.
- No JSON Schema files created.
- No DecisionOutput JSON reading used.
- No Freqtrade strategy class created.
- No trading execution logic added.
- No Binance integration.
- No live trading enabled.
- No network calls.
- All safety flags remain `False` or safe (`dry_run=True`).

### Next

- MVP-4 Step 5 — Final Review and Polish.

## 0.4.0-dev — MVP-4 Step 3 — Execution Context Writer (Complete)

### Added

- `src/hunter/execution/writer.py` created with JSON serialization and atomic output writer.
- `execution_context_to_dict()` — serializes all 14 ExecutionContext fields to JSON-compatible dict.
- `atomic_write_json()` — atomic temp-file write with `os.replace()`, parent directory creation, cleanup on failure.
- `write_execution_context()` — writes to `data/execution/current_execution_context.json` by default.
- ISO-8601 timestamp serialization with Z suffix.
- Enum string serialization for all enum fields.
- `input_refs` serialized as nested dict with `decision_timestamp` and `decision_source`.
- `safety_flags` serialized as nested dict with all 6 safety fields.
- `data_quality` serialized as nested dict with all 4 quality flags.
- `version` field preserved for backward-compatible contract evolution.
- 20 execution writer tests, all passing.
- Full test suite: 508 tests passing.

### Safety

- No Binance integration.
- No Freqtrade runtime integration.
- No strategy class.
- No trading logic.
- No live trading.
- No API keys.
- No network calls.
- No JSON input reading.
- Atomic writes prevent partial output on failure.

### Next

- MVP-4 Step 4 — Integration Tests.

## 0.4.0-dev — MVP-4 Step 2 — Execution Bridge Engine (Complete)

### Added

- `src/hunter/execution/engine.py` created with deterministic execution bridge engine.
- `build_execution_context()` — main entry point implementing all 15 fail-closed rules from SPEC-005 in priority order.
- `validate_execution_inputs()` — validates DecisionOutput against all safety constraints.
- `is_stale_decision()` — checks DecisionOutput age against `stale_decision_minutes` threshold.
- `map_decision_to_execution_mode()` — maps DecisionAction to ExecutionMode.
- `build_safety_flags()` — constructs ExecutionSafetyFlags with all defaults safe.
- All successful paths produce `DRY_RUN_ONLY` (ENABLED reserved for future).
- All blocked paths produce `BLOCKED` + `BLOCK_ALL` + `dry_run=True`.
- Missing/invalid/stale/unsafe inputs all block by default.
- `input_refs` populated with decision timestamp and source on successful paths.
- 45 execution engine tests, all passing.
- Full test suite: 488 tests passing.

### Safety

- No Binance integration.
- No Freqtrade runtime integration.
- No strategy class.
- No trading logic.
- No live trading.
- No API keys.
- No network calls.
- No JSON reading or writing.
- No exchange connection.
- No order execution.

### Next

- MVP-4 Step 3 — Execution Bridge Writer.

## 0.4.0-dev — MVP-4 Step 1 — Execution Bridge Models (Complete)

### Added

- `src/hunter/execution/models.py` created with immutable execution bridge models.
- `ExecutionState` enum: ENABLED, BLOCKED, DRY_RUN_ONLY, UNKNOWN.
- `ExecutionMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL, DRY_RUN_ONLY.
- `ExecutionBridgeConfig` with MVP-4 safety validation (dry_run_required=True, live_trading_enabled=False, etc.).
- `ExecutionInputRefs` for audit trail references to decision output.
- `ExecutionSafetyFlags` with `human_override_required` (default false) and `max_context_age_seconds` (default 300).
- `ExecutionContext` with `version` field default `"1.0"` for backward-compatible contract evolution.
- `ExecutionContext.blocked()` fail-closed factory producing BLOCKED + BLOCK_ALL + dry_run True + version "1.0".
- All models frozen/immutable with `__post_init__` validation.
- 49 execution model tests, all passing.
- Full test suite: 443 tests passing.

### Safety

- No Binance integration.
- No Freqtrade runtime integration.
- No strategy class.
- No trading logic.
- No live trading.
- No API keys.
- No network calls.
- No JSON reading or writing.

### Next

- MVP-4 Step 2 — Execution Bridge Engine.

## 0.4.0-dev — MVP-4 Execution Bridge (Design Complete)

### Added

- SPEC-005 — Execution Bridge / Freqtrade Integration design document created and reviewed.
- Execution Bridge consumes in-memory `DecisionOutput` from MVP-3.
- Future input path documented: `data/decision/current_decision.json`.
- Output path defined: `data/execution/current_execution_context.json`.
- `ExecutionState` enum design: ENABLED, BLOCKED, DRY_RUN_ONLY, UNKNOWN.
- `ExecutionMode` enum design: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL, DRY_RUN_ONLY.
- `ExecutionContext` model design with `version` field default `"1.0"` for backward-compatible contract evolution.
- `max_context_age_seconds` default `300` documented as consumer-side stale rejection guard.
- `human_override_required` default `false` documented as reserved for future DRY_RUN_ONLY → ENABLED transitions.
- Fail-closed by default: all bad inputs produce BLOCKED + BLOCK_ALL.
- Dry-run only: all successful paths produce DRY_RUN_ONLY, ENABLED reserved for future.
- 15 priority-ordered fail-closed rules defined.
- Config file design: `configs/execution_bridge.yaml` (single file, no sprawl).
- JSON Schema design: `schemas/execution_context.schema.json` (future work only, not implemented yet).
- Freqtrade compatibility contract documented for future MVP-5+ implementation.
- All 27 review checklist items passed.

### Safety

- No code implemented yet.
- No Binance integration.
- No Freqtrade runtime integration.
- No strategy class.
- No trading logic.
- No live trading.
- No API keys.
- No real data fetching.

### Next

- MVP-4 Step 2 — Execution Bridge Engine.

## 0.4.0-dev — MVP-4 Step 1 — Execution Bridge Models (Complete)

### Added

- `src/hunter/execution/models.py` created with immutable execution bridge models.
- `ExecutionState` enum: ENABLED, BLOCKED, DRY_RUN_ONLY, UNKNOWN.
- `ExecutionMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL, DRY_RUN_ONLY.
- `ExecutionBridgeConfig` with MVP-4 safety validation (dry_run_required=True, live_trading_enabled=False, etc.).
- `ExecutionInputRefs` for audit trail references to decision output.
- `ExecutionSafetyFlags` with `human_override_required` (default false) and `max_context_age_seconds` (default 300).
- `ExecutionContext` with `version` field default `"1.0"` for backward-compatible contract evolution.
- `ExecutionContext.blocked()` fail-closed factory producing BLOCKED + BLOCK_ALL + dry_run True + version "1.0".
- All models frozen/immutable with `__post_init__` validation.
- 49 execution model tests, all passing.
- Full test suite: 443 tests passing.

### Safety

- No Binance integration.
- No Freqtrade runtime integration.
- No strategy class.
- No trading logic.
- No live trading.
- No API keys.
- No network calls.
- No JSON reading or writing.

### Next

- MVP-4 Step 2 — Execution Bridge Engine.

## 0.3.0-dev — MVP-3 Decision Layer (Complete)

### Added

- SPEC-004 — Decision Layer design document created, clarified, and reviewed.
- Decision Models: `DecisionState`, `DecisionAction`, `DecisionConfig`, `DecisionInputRefs`, `DecisionOutput` with `block_all()` fail-closed factory.
- Decision Engine: `make_decision()` with 14 priority-ordered fail-closed rules.
- Decision Writer: `decision_to_dict()`, `atomic_write_json()`, `write_decision_output()` with atomic temp-file writes.
- Integration tests: DecisionOutput → make_decision → write_decision_output end-to-end pipeline.
- Default output: `BLOCK` + `BLOCK_ALL` + confidence `0.0` on all bad inputs.
- Allow cases: `BULL` + `LONG_ONLY` + healthy breadth → `ENABLE_LONG_ONLY_RESEARCH`; `BEAR` + `SHORT_ONLY` + weak breadth → `ENABLE_SHORT_ONLY_RESEARCH`.
- All other states (`SIDEWAYS`, `TRANSITION`, conflict, stale) → `BLOCK_ALL`.
- `REVIEW` state reserved for future, never emitted by default.
- Config file design: `configs/decision.yaml` (single file).
- JSON Schema design: `schemas/decision.schema.json` (future work only).
- All 20 review checklist items passed.
- Full test suite: 394 tests passing.

### Safety

- No Binance integration.
- No Freqtrade integration.
- No trading logic.
- No live trading.
- No API keys.
- No network calls.
- No JSON input reading.

### Next

- MVP-4 Execution Bridge design and implementation.

## 0.2.0-dev — MVP-2 Market State (Complete)

### Added

- SPEC-003 — Market State Regime & Breadth design document created, reviewed, and finalized with all fixes applied.
- Market State Models: `RegimeState`, `RiskState`, `AllowedMode`, `OutputStatus`, `DataQuality`, `RegimeOutput`, `BreadthOutput` with `invalid()` fail-closed factories.
- Indicator Utilities: `safe_divide`, `percent_change`, `simple_moving_average`, `exponential_moving_average`, `ema_slope_pct`, `is_rising`, `is_falling`, `is_flat` — pure standard-library functions.
- Regime Engine: deterministic `btc_trend_score`, `bearish_btc_trend_score`, `eth_trend_score`, `breadth_confirmation_score`, `classify_regime()` with fail-closed `UNKNOWN` + `NONE` behavior.
- Breadth Engine: deterministic `breadth_score` with weighted formula, universe filtering, invalid symbol exclusion.
- JSON Output Writers: `regime_to_dict()`, `breadth_to_dict()`, `atomic_write_json()`, `write_regime_output()`, `write_breadth_output()` with atomic temp-file writes and ISO-8601 timestamps.
- All 17 review checklist items passed.
- Full test suite: 278 tests passing.

### Safety

- No Binance integration.
- No Freqtrade integration.
- No trading logic.
- No live trading.
- No API keys.
- No network calls.
- No storage integration.

### Next

- MVP-3 Decision Layer design and implementation.

## 0.1.0-dev — MVP-1 Data Foundation (Complete)

### Added

- Python project structure: `src/hunter/` package with `config`, `data`, `core`, `engines` modules.
- `pyproject.toml` with project metadata, `pydantic` and `pyyaml` dependencies.
- `requirements.txt` and `requirements-dev.txt` with pytest dependencies.
- `.gitignore` excluding Python cache, secrets, runtime data, and local config.
- `tests/` directory at repo root with `test_config`, `test_data`, `test_core`, `fixtures`.
- `__version__ = "0.2.0-dev"` in `src/hunter/__init__.py`.
- SQLiteStorage implementation with `DataStorage` ABC.
- Config models with Pydantic validation.
- Logging setup with structlog and JSON output.
- Test fixtures for config and data layers.
- Full test suite: 91 tests passing.

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets should be stored in the repository.

### Next

- MVP-2 Market State design and implementation.

## 0.0.0 — MVP-0 Project Foundation (Complete)

### Added

- Initial project README
- Initial PROJECT.md specification
- Main AGENTS.md instructions
- Current project state handoff file
- Task backlog file
- Active task file
- Agent log file

### Project Direction

- Hunter Futures Pro will be developed as an agent-first crypto futures research and execution-control platform.
- WrongStack will be used as the main CLI AI agent.
- Kimi K2.7 will be used as the preferred model/backend.
- Freqtrade will be used only as the execution layer.
- Hunter Futures Pro will be the decision layer.
- Old strategies are benchmarks only.

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets should be stored in the repository.

### Next

- Review MVP-0 cleanup.
- Commit initial foundation.
- Plan MVP-1 Data Foundation.

## 0.2.0-dev — MVP-1 Data Foundation (In Progress)

### Added

- Python project structure: `src/hunter/` package with `config`, `data`, `core`, `engines` modules
- `pyproject.toml` with project metadata, `pydantic` and `pyyaml` dependencies
- `requirements.txt` and `requirements-dev.txt` with pytest dependencies
- `.gitignore` excluding Python cache, secrets, runtime data, and local config
- `tests/` directory at repo root with `test_config`, `test_data`, `test_core`, `fixtures`
- `__version__ = "0.2.0-dev"` in `src/hunter/__init__.py`

### MVP-1 Step 2 — Config Models and Validation (Complete)

- Pydantic config models: `TradingConfig`, `CollectionConfig`, `StorageConfig`, `LoggingConfig`, `HunterConfig`
- Config loader with safe override hierarchy (YAML file, env var)
- `validate_config()` with fail-closed validation:
  - Raises `ConfigLoadError` if `trading.enabled` is `true`
  - Raises `ConfigLoadError` if `trading.live_enabled` is `true`
  - Raises `ConfigLoadError` if secrets (`api_key`, `api_secret`, `secret_key`, `private_key`) detected
- Safe defaults: `trading.enabled: false`, `trading.live_enabled: false`, `collection.enabled: false`
- Config files: `configs/data.yaml` (safe defaults), `configs/local.example.yaml` (warnings)
- Config directory standard: `configs/` (not `config/`)
- Config tests: 23 tests for safe defaults, validation failures, and YAML loading

### MVP-1 Step 3 — Logging Structure (Complete)

- `src/hunter/core/logging.py` with structured logging components:
  - `JSONFormatter` for JSON log output with timestamp, level, logger, message, correlation_id, context, exception info
  - `RedactingFilter` for recursive secret redaction (api_key, secret, password, token, private_key) in dicts and lists
  - `setup_logging()` with console handler (text or JSON) and rotating file handler (always JSON, 10MB/5 backups)
- `tests/test_core/test_logging.py` with 18 tests for formatting, redaction, and setup behavior
- Log secret redaction applied to file handler only

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- `.gitignore` prevents accidental commit of `configs/local.yaml`, `.env`, `*.key`, `*.pem`.
- Logging redacts secret-like fields from file output.

### MVP-1 Step 4 — Data Collector Interface (Complete)

- `src/hunter/data/collector.py` with abstract `DataCollector` interface:
  - 6 abstract methods: `get_exchange_info()`, `get_klines()`, `get_funding_rates()`, `get_open_interest()`, `get_mark_price()`, `get_24h_ticker()`
- `BinanceFuturesCollector` skeleton class that does NOT connect to Binance
  - All methods raise `NotImplementedError` with message "Binance connection not implemented in MVP-1"
- 5 frozen dataclass data models: `KlineData`, `FundingRateData`, `OpenInterestData`, `MarkPriceData`, `Ticker24hData`
- `tests/test_data/test_collector.py` with 18 tests:
  - `DataCollector` cannot be instantiated directly (abstract)
  - `BinanceFuturesCollector` raises `NotImplementedError` on all methods
  - No network calls are made (verified by monkeypatch)
  - Data models are immutable (`frozen=True`)

### MVP-1 Step 5 — SQLite Storage Layer (Complete)

- `src/hunter/data/schema.sql` with 5 tables:
  - `market_symbols` — Symbol registry with base/quote assets
  - `candles` — OHLCV data with unique constraint on (symbol, timeframe, open_time)
  - `funding_rates` — Funding rate history with unique constraint on (symbol, funding_time)
  - `open_interest` — Open interest snapshots
  - `collection_metadata` — Freshness tracking with upsert support
- Indexes on common query patterns: `idx_candles_symbol_timeframe_time`, `idx_funding_symbol_time`, `idx_oi_symbol_time`, `idx_meta_symbol_type`
- `src/hunter/data/storage.py` with `DataStorage` ABC and `SQLiteStorage` implementation
  - `DataStorage` ABC: 9 abstract methods (`initialize`, `save_klines`, `get_klines`, `get_latest_kline`, `save_funding_rates`, `get_funding_rates`, `save_collection_metadata`, `get_collection_metadata`, `is_data_fresh`)
  - `SQLiteStorage` uses Python standard library `sqlite3` only (no external dependencies)
  - `save_klines()` / `save_funding_rates()` use `INSERT OR IGNORE` for deduplication
  - `is_data_fresh()` checks metadata age against `max_age_seconds`
- `tests/test_data/test_storage.py` with 19 tests using temporary SQLite database files
  - All tests pass, no network calls, no Binance connection, no Freqtrade connection

### MVP-1 Step 6 — Final Safety Tests and MVP-1 Completion (Complete)

- Final review found config loader returning `dict` instead of `HunterConfig` when merging YAML
- Fixed `load_config()` to use `_deep_update()` + `model_validate()` for safe nested merging
- Fixed secret detection to scan merged dict before Pydantic strips extra fields
- Fixed config tests to use `raw_dict` parameter for secret injection
- Fixed missing `import sys` in logging tests
- Fixed `test_sets_log_level` to check root logger level
- Commit `dd3ea99`: config loader bugfix and test fixes
- All 91 tests now pass (0 failures)
- MVP-1 Data Foundation is complete

### Next

- MVP-2 Market State: Regime Engine and Market Breadth Engine design.

## 0.3.0-dev — MVP-2 Market State Design (Complete)

### Added

- `specs/SPEC-003-Market-State-Regime-Breadth.md` with complete MVP-2 design:
  - Regime Engine design with 5 states (BULL, BEAR, SIDEWAYS, TRANSITION, UNKNOWN)
  - Market Breadth Engine design with universe filtering and invalid symbol rules
  - Deterministic scoring formulas (no ML, no optimization, no curve fitting):
    - `btc_trend_score`, `bearish_btc_trend_score`, `eth_trend_score` (0–100)
    - `breadth_confirmation_score` (0–100)
    - `breadth_score` (0–100) with weighted component formula
    - `confidence` (0.0–1.0) = min(primary_score, confirmation_score) / 100
  - EMA slope formula: `ema_slope_pct = ((ema_current - ema_n_candles_ago) / ema_n_candles_ago) * 100`
  - Fail-closed behavior: all bad data → UNKNOWN + NONE + confidence 0
  - Pipeline order: Breadth Engine runs first, Regime Engine consumes breadth output
  - Timeframe-aware stale data: `stale_threshold_candles: 2` with `timeframe_duration` multiplier
  - `configs/market_state.yaml` as single config standard (no separate regime/breadth YAML)
  - JSON Schema design section for future `schemas/regime.schema.json` and `schemas/breadth.schema.json`
  - Test plan for regime, breadth, and safety tests
  - MVP-1 interface references: DataStorage ABC, SQLiteStorage, KlineData, HunterConfig

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No code implemented yet — design only.

### Next

- MVP-2 implementation planning: Step 1 — Market State Models.

### MVP-2 Step 1 — Market State Models (Complete)

- `src/hunter/market_state/__init__.py` created
- `src/hunter/market_state/models.py` created with frozen dataclasses:
  - Enums: `RegimeState` (BULL, BEAR, SIDEWAYS, TRANSITION, UNKNOWN)
  - Enums: `RiskState` (RISK_ON, RISK_OFF, NEUTRAL, UNKNOWN)
  - Enums: `AllowedMode` (LONG_ONLY, SHORT_ONLY, NONE)
  - Enums: `OutputStatus` (VALID, INVALID)
  - `DataQuality` — immutable flags for missing, stale, insufficient_history, insufficient_universe
  - `RegimeOutput` — frozen output model with `__post_init__` validation:
    - confidence range: 0.0–1.0
    - score ranges: 0–100
    - `RegimeOutput.unknown()` fail-closed factory: UNKNOWN + NONE + confidence 0
  - `BreadthOutput` — frozen output model with `__post_init__` validation:
    - breadth_score range: 0–100
    - percentage fields range: 0.0–1.0
    - `BreadthOutput.invalid()` fail-closed factory: INVALID + UNKNOWN health + score 0
- `tests/test_market_state/__init__.py` created
- `tests/test_market_state/test_models.py` with 37 tests:
  - Enum value verification
  - Valid creation with boundary values
  - Validation failures (out-of-range confidence, scores, percentages)
  - Fail-closed factory defaults and custom overrides
  - Immutability (frozen dataclass)
- Full test suite: 128 tests passing (91 existing + 37 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No Regime Engine logic exists yet.
- No Breadth Engine logic exists yet.
- No indicators exist yet.

### MVP-2 Step 2 — Indicator Utilities (Complete)

- `src/hunter/market_state/indicators.py` created with pure, deterministic functions:
  - `safe_divide(numerator, denominator, default)` — division with zero-safe fallback
  - `percent_change(current, previous, default)` — percentage change with zero-safe fallback
  - `simple_moving_average(values, period)` — SMA with sliding window; returns empty list if insufficient data
  - `exponential_moving_average(values, period)` — EMA with standard multiplier formula; returns empty list if insufficient data
  - `ema_slope_pct(ema_values, lookback)` — EMA slope percentage matching SPEC-003 formula exactly
  - `is_rising(slope_pct, threshold_pct)` — slope > threshold
  - `is_falling(slope_pct, threshold_pct)` — slope < -threshold
  - `is_flat(slope_pct, threshold_pct)` — abs(slope) <= threshold
- Standard library only — no pandas, no external dependencies
- All functions are stateless, no network, no storage, no trading logic
- `tests/test_market_state/test_indicators.py` with 50 tests:
  - Safe divide: normal, zero denominator, custom default, negatives, floats
  - Percent change: normal, negative, zero previous, no change, double
  - SMA: basic, period 1, insufficient data, exact period, invalid period, empty values, large values
  - EMA: basic, period 1, insufficient data, exact period, invalid period, empty values, known values
  - EMA slope: rising, falling, flat, lookback 1, lookback 5 (SPEC default), zero denominator, insufficient data, invalid lookback
  - Slope direction: rising/falling/flat at and around thresholds, combined state checks
  - Safety: no network imports, no trading terms in module source
- Full test suite: 178 tests passing (128 existing + 50 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No Regime Engine logic exists yet.
- No Breadth Engine logic exists yet.
- No JSON writers exist yet.

### MVP-2 Step 3 — Regime Engine (Complete)

- `src/hunter/market_state/regime.py` created with deterministic Regime Engine:
  - `RegimeConfig` — frozen dataclass with all SPEC-003 defaults (ema periods, thresholds, lookbacks)
  - `calculate_btc_trend_score(btc_closes, config)` — bullish conditions / total * 100, 0–100
  - `calculate_bearish_btc_trend_score(btc_closes, config)` — bearish conditions / total * 100, 0–100
  - `calculate_eth_trend_score(eth_closes, config)` — optional ETH confirmation, returns 0 + `ETH_DATA_UNAVAILABLE` if missing
  - `calculate_breadth_confirmation_score(...)` — optional breadth confirmation based on regime direction
  - `classify_regime(...)` — main classifier with fail-closed behavior:
    - Missing BTC candles → `UNKNOWN` + `NONE` + confidence 0
    - Insufficient BTC history → `UNKNOWN` + `NONE` + confidence 0
    - Invalid candle values (≤0) → `UNKNOWN` + `NONE` + confidence 0
    - Bull detected → `BULL` + `LONG_ONLY` + confidence from confirmation
    - Bear detected → `BEAR` + `SHORT_ONLY` + confidence from confirmation
    - Weak trend → `SIDEWAYS` + `NONE`
    - Low confidence (<0.6) → `TRANSITION` + `NONE`
  - Uses `ema_slope_pct` from indicators.py (matches SPEC-003 formula exactly)
  - No ML, no optimization, no curve fitting
- `tests/test_market_state/test_regime.py` with 37 tests:
  - RegimeConfig defaults and custom values
  - BTC trend score: bullish high, bearish low, flat medium, missing, insufficient, invalid, range
  - Bearish BTC trend score: bearish high, bullish low, missing
  - ETH trend score: None unavailable, bullish, missing
  - Breadth confirmation: bull confirmation, bear confirmation, None returns zero, no confirmation
  - Fail-closed: missing BTC, insufficient history, invalid values, calculation error blocks
  - Regime detection: bull, bear, sideways, transition with ETH, bull with breadth, confidence range, allowed mode NONE when invalid
  - Reason codes: bull, bear, unknown all have non-empty reason codes
  - Safety: no network imports, no trading terms, no Binance, no Freqtrade
- Full test suite: 215 tests passing (178 existing + 37 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No Breadth Engine logic exists yet.
- No JSON writers exist yet.

### MVP-2 Step 4 — Breadth Engine (Complete)

- `src/hunter/market_state/breadth.py` created with deterministic Market Breadth Engine:
  - `BreadthConfig` — frozen dataclass with all SPEC-003 defaults (min_universe_size, EMA periods, thresholds, lookbacks)
  - `filter_valid_symbols(universe_candles, config)` — validates symbols per SPEC-003 rules:
    - Exclude missing candles, insufficient history, close ≤ 0, negative volume, calculation failures
    - Returns (valid_symbols, invalid_count, reason_codes)
  - `calculate_percent_above_ema(valid_candles, ema_period)` — percentage of symbols with close > EMA
  - `calculate_percent_ema_rising(valid_candles, ema_period, lookback, threshold)` — percentage with rising EMA slope
  - `calculate_advancing_declining_pct(valid_candles)` — advancing vs declining percentages (flat excluded)
  - `calculate_outperforming_btc_pct(valid_candles, btc_closes, lookback_days)` — percentage outperforming BTC return
  - `calculate_breadth_score(...)` — weighted formula per SPEC-003, clamped 0–100:
    - above_ema20_pct * 25 + above_ema50_pct * 20 + ema20_rising_pct * 20 + ema50_rising_pct * 15 + advancing_pct * 10 + outperforming_btc_7d_pct * 10
  - `calculate_breadth(universe_candles, btc_closes, ...)` — main breadth function with fail-closed behavior:
    - Missing universe → `INVALID` + `UNKNOWN` health + score 0
    - Missing BTC → `INVALID` + `UNKNOWN` health + score 0
    - Insufficient universe (< min_universe_size) → `INVALID` + `UNKNOWN` health + score 0
    - Invalid BTC values → `INVALID` + `UNKNOWN` health + score 0
    - Valid data → `VALID` + market health (RISK_ON/RISK_OFF/NEUTRAL) + breadth_score 0–100
  - Uses `exponential_moving_average`, `ema_slope_pct`, `percent_change` from indicators.py
  - No ML, no optimization, no curve fitting
- `tests/test_market_state/test_breadth.py` with 44 tests:
  - BreadthConfig defaults, custom values, frozen immutability
  - filter_valid_symbols: all valid, missing excluded, insufficient excluded, invalid price excluded, negative excluded
  - calculate_percent_above_ema: all above, none above, half above, empty
  - calculate_percent_ema_rising: all rising, none rising, empty
  - calculate_advancing_declining_pct: all advancing, all declining, mixed, empty, flat excluded
  - calculate_outperforming_btc_pct: all outperform, none outperform, half, empty, missing BTC, insufficient BTC
  - calculate_breadth_score: max 100, min 0, mixed, clamped above 100, clamped below 0, deterministic
  - calculate_breadth: missing universe, missing BTC, insufficient universe, invalid BTC, valid calculation, score range, reason codes, risk_on, risk_off, invalid symbols counted
  - Safety: no network calls, no trading logic
- Full test suite: 259 tests passing (215 existing + 44 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No JSON writers exist yet.
- No schema files exist yet.

### MVP-2 Step 5 — JSON Output Writers (Complete)

- `src/hunter/market_state/writer.py` created with JSON serialization and atomic output writers:
  - `regime_to_dict(output)` — Serializes `RegimeOutput` to JSON-compatible dict:
    - ISO-8601 timestamps with Z suffix (e.g., `2026-06-17T12:00:00Z`)
    - Enum values serialized as strings (e.g., `BULL`, `LONG_ONLY`, `VALID`)
    - `DataQuality` and `reason_codes` preserved
  - `breadth_to_dict(output)` — Serializes `BreadthOutput` to JSON-compatible dict:
    - Same timestamp and enum serialization as regime
    - All percentage fields and counts preserved
  - `atomic_write_json(data, target_path)` — Atomic file write:
    - Writes to temp file in same directory first
    - Uses `os.replace()` for atomic rename
    - Creates parent directories if missing
    - Cleans up temp file on failure (no partial output)
    - Uses `fsync` for durability
  - `write_regime_output(output, target_path)` — Writes to `data/regime/current_regime.json` by default
  - `write_breadth_output(output, target_path)` — Writes to `data/breadth/current_breadth.json` by default
  - Output matches SPEC-003 JSON contract exactly
- `tests/test_market_state/test_writer.py` with 19 tests:
  - regime_to_dict: valid regime, unknown regime, ISO-8601 format, naive datetime, enum strings, data quality, reason codes
  - breadth_to_dict: valid breadth, invalid breadth
  - atomic_write_json: writes file, creates directories, no partial on failure, unicode encoding
  - write_regime_output: default path, parent directories
  - write_breadth_output: default path, parent directories
  - Safety: no network calls, no trading logic
- Full test suite: 278 tests passing (259 existing + 19 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No JSON schema validation exists yet.
- No storage integration exists yet.
- No report templates exist yet.

### MVP-2 Complete

MVP-2 Market State implementation is fully complete. All 6 steps finished:
- Step 1: Market State Models (37 tests)
- Step 2: Indicator Utilities (50 tests)
- Step 3: Regime Engine (37 tests)
- Step 4: Breadth Engine (44 tests)
- Step 5: JSON Output Writers (19 tests)
- Step 6: Final review and polish
- Version bumped to 0.3.0-dev
- Full test suite: 278 tests passing

### SPEC-004 — Decision Layer Design (Complete)

- SPEC-004 exists and is reviewed (19 checklist items all passed)
- Decision Layer consumes in-memory `RegimeOutput` and `BreadthOutput` from MVP-2
- Decision Layer produces `data/decision/current_decision.json`
- `DecisionState` enum designed: `ALLOW`, `BLOCK`, `REVIEW` (reserved for future), `UNKNOWN`
- `DecisionAction` enum designed: `ENABLE_LONG_ONLY_RESEARCH`, `ENABLE_SHORT_ONLY_RESEARCH`, `BLOCK_ALL`, `MANUAL_REVIEW`
- `DecisionOutput` model with 14 fields including audit trail (`input_refs`, `data_quality`)
- `DecisionConfig` with frozen defaults: `min_regime_confidence: 0.60`, `stale_input_minutes: 120`
- 14 deterministic fail-closed rules in priority order (all block by default)
- `configs/decision.yaml` design: single config file with threshold controls
- `schemas/decision.schema.json` design: future validation schema (not implemented yet)
- `REVIEW` state reserved for future manual-review workflows; default is `BLOCK_ALL`
- Staleness is output-level (engine output age), not candle-level (handled by MVP-2)
- No MVP-3 code has been implemented yet
- No Binance integration
- No Freqtrade integration
- No trading logic
- No live trading

### MVP-3 Step 1 — Decision Models (Complete)

- `src/hunter/decision/__init__.py` created
- `src/hunter/decision/models.py` created with frozen dataclasses:
  - Enums: `DecisionState` (ALLOW, BLOCK, REVIEW, UNKNOWN)
  - Enums: `DecisionAction` (ENABLE_LONG_ONLY_RESEARCH, ENABLE_SHORT_ONLY_RESEARCH, BLOCK_ALL, MANUAL_REVIEW)
  - `DecisionConfig` — frozen dataclass with `__post_init__` validation:
    - min_regime_confidence: 0.60 (range 0.0–1.0)
    - min_breadth_score_for_long: 60 (range 0–100)
    - max_breadth_score_for_short: 40 (range 0–100)
    - stale_input_minutes: 120 (positive integer)
    - transition_action: BLOCK_ALL, conflict_action: BLOCK_ALL
  - `DecisionInputRefs` — frozen dataclass for audit trail references to consumed inputs
  - `DecisionOutput` — frozen output model with `__post_init__` validation:
    - confidence range: 0.0–1.0
    - regime_confidence range: 0.0–1.0
    - breadth_score range: 0–100
    - `DecisionOutput.block_all()` fail-closed factory: BLOCK + BLOCK_ALL + confidence 0.0
- `tests/test_decision/test_models.py` with 32 tests:
  - Enum value verification
  - DecisionConfig defaults, custom values, and boundary validation
  - Valid DecisionOutput creation with all 14 fields
  - Validation failures (out-of-range confidence, regime_confidence, breadth_score)
  - Fail-closed factory defaults and custom overrides
  - Immutability (frozen dataclass)
- Full test suite: 310 tests passing (278 existing + 32 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No Decision Engine logic exists yet.
- No Decision Writer exists yet.
- No config YAML exists yet.

### MVP-3 Step 2 — Decision Engine (Complete)

- `src/hunter/decision/engine.py` created with deterministic fail-closed Decision Engine:
  - `make_decision(regime_output, breadth_output, config)` — main entry point implementing all 14 priority rules from SPEC-004
  - `validate_decision_inputs(regime, breadth, config)` — fail-closed validation in priority order:
    - Missing RegimeOutput → BLOCK_ALL (MISSING_REGIME)
    - Missing BreadthOutput → BLOCK_ALL (MISSING_BREADTH)
    - Invalid RegimeOutput status → BLOCK_ALL (INVALID_REGIME)
    - Invalid BreadthOutput status → BLOCK_ALL (INVALID_BREADTH)
    - UNKNOWN regime → BLOCK_ALL (UNKNOWN_REGIME)
    - allowed_mode NONE → BLOCK_ALL (ALLOWED_MODE_NONE)
    - Low regime confidence → BLOCK_ALL (LOW_REGIME_CONFIDENCE)
    - Stale inputs → BLOCK_ALL (STALE_INPUT)
  - `is_stale_output(regime, breadth, stale_input_minutes)` — checks oldest timestamp against threshold
  - `detect_regime_breadth_conflict(regime, breadth)` — detects 4 conflict conditions per SPEC-004:
    - BULL + RISK_OFF, BEAR + RISK_ON, BULL + score < 50, BEAR + score > 50
  - `calculate_decision_confidence(regime, breadth)` — min(regime_confidence, breadth_score / 100)
  - Decision rules (after all fail-closed checks pass):
    - BULL + LONG_ONLY + breadth_score >= min_breadth_score_for_long → ALLOW + ENABLE_LONG_ONLY_RESEARCH
    - BEAR + SHORT_ONLY + breadth_score <= max_breadth_score_for_short → ALLOW + ENABLE_SHORT_ONLY_RESEARCH
    - SIDEWAYS → BLOCK_ALL (SIDEWAYS_NO_DIRECTION)
    - TRANSITION → BLOCK_ALL (TRANSITION_UNCERTAIN) or custom transition_action
    - Conflicts → BLOCK_ALL (CONFLICTING_SIGNALS) or custom conflict_action
    - Default → BLOCK_ALL (DEFAULT_BLOCK)
  - Data quality aggregation: logical OR of RegimeOutput and BreadthOutput data_quality flags
  - Input refs populated with timestamps and source labels for audit trail
- `tests/test_decision/test_engine.py` with 50 tests:
  - validate_decision_inputs: missing regime, missing breadth, invalid status, UNKNOWN, NONE mode, low confidence, stale, valid, data quality aggregation
  - is_stale_output: fresh, old regime, old breadth, uses oldest timestamp
  - detect_conflict: bull+risk_off, bear+risk_on, bull+low_score, bear+high_score, no conflict cases
  - calculate_confidence: high/high, low/high, high/low, perfect, zero
  - make_decision fail-closed: all 8 fail-closed conditions produce BLOCK_ALL
  - make_decision allow: bull+healthy_breadth allows long, bear+weak_breadth allows short
  - make_decision special: sideways blocks, transition blocks, custom actions, conflicts, default block, input refs, confidence calculation
  - Safety: no network calls, no trading execution logic
- Full test suite: 360 tests passing (310 existing + 50 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No Decision Writer exists yet.
- No config YAML exists yet.
- No JSON reading or writing in Decision Engine.

### MVP-3 Step 3 — Decision Writer (Complete)

- `src/hunter/decision/writer.py` created with JSON serialization and atomic output writer:
  - `decision_to_dict(output)` — Serializes `DecisionOutput` to JSON-compatible dict:
    - ISO-8601 timestamps with Z suffix (e.g., `2026-06-17T12:00:00Z`)
    - Enum values serialized as strings (e.g., `ALLOW`, `BLOCK_ALL`, `LONG_ONLY`)
    - `DecisionInputRefs` with regime/breadth timestamps and source labels
    - `DataQuality` with all 4 boolean flags
    - `reason_codes` preserved as list
  - `atomic_write_json(data, target_path)` — Atomic file write:
    - Writes to temp file in same directory first
    - Uses `os.replace()` for atomic rename
    - Creates parent directories if missing
    - Cleans up temp file on failure (no partial output)
    - Uses `fsync` for durability
  - `write_decision_output(output, target_path)` — Writes to `data/decision/current_decision.json` by default
  - Output matches SPEC-004 JSON contract exactly
- `tests/test_decision/test_writer.py` with 19 tests:
  - decision_to_dict: valid decision, block decision, ISO-8601 format, naive datetime, enum strings, input refs, data quality, reason codes, JSON roundtrip
  - atomic_write_json: writes file, creates directories, no partial on failure, unicode encoding
  - write_decision_output: default path, parent directories, default path constant, invalid path fails
  - Safety: no network calls, no trading logic
- Full test suite: 379 tests passing (360 existing + 19 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No config YAML exists yet.
- No JSON schema validation exists yet.
- No JSON input reading in Decision Writer.

### MVP-3 Step 4 — Integration Tests (Complete)

- `tests/test_decision/test_integration.py` created with 15 end-to-end tests:
  - `test_bull_long_healthy_full_pipeline` — BULL + LONG_ONLY + healthy breadth → ENABLE_LONG_ONLY_RESEARCH, JSON written and verified
  - `test_bear_short_weak_full_pipeline` — BEAR + SHORT_ONLY + weak breadth → ENABLE_SHORT_ONLY_RESEARCH, JSON written and verified
  - `test_unknown_regime_blocks_pipeline` — UNKNOWN regime → BLOCK_ALL, JSON verified
  - `test_invalid_breadth_blocks_pipeline` — INVALID breadth → BLOCK_ALL, JSON verified
  - `test_sideways_blocks_pipeline` — SIDEWAYS → BLOCK_ALL, JSON verified
  - `test_transition_blocks_pipeline` — TRANSITION → BLOCK_ALL, JSON verified
  - `test_stale_regime_blocks_pipeline` — stale regime → BLOCK_ALL, JSON verified
  - `test_stale_breadth_blocks_pipeline` — stale breadth → BLOCK_ALL, JSON verified
  - `test_conflict_blocks_pipeline` — conflicting signals → BLOCK_ALL, JSON verified
  - `test_json_contains_all_expected_fields` — all 14 SPEC-004 fields present in JSON output
  - `test_enum_values_are_strings_in_json` — all enum values serialized as strings
  - `test_no_default_production_path_used` — tests use tmp_path, not production data/decision path
  - Safety: no network calls, no trading execution logic, no JSON input reading
- Full test suite: 394 tests passing (379 existing + 15 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No config YAML exists yet.
- No JSON schema validation exists yet.
- No JSON input reading in integration tests.

### MVP-3 Complete

MVP-3 Decision Layer implementation is fully complete. All 5 steps finished:
- Step 1: Decision Models (32 tests)
- Step 2: Decision Engine (50 tests)
- Step 3: Decision Writer (19 tests)
- Step 4: Integration Tests (15 tests)
- Step 5: Final review and polish
- Version: 0.3.0-dev
- Full test suite: 394 tests passing

### Next

- MVP-4 planning (Execution Bridge / Freqtrade Integration) — design only, no implementation yet.
- Commit current state.
- Review PROJECT.md for MVP-4 scope.
