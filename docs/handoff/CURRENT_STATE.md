# Current State

## Project

Hunter Futures Pro

## Version

0.20.0-dev

## Current Phase

MVP-20 is complete and committed. SPEC-021 for MVP-20 Local Research Release Notes / Audit Change Summary is complete and approved. Version 0.20.0-dev. Full test suite: 3921 tests passing, 1 skipped using `pytest --import-mode=importlib`. Next step: MVP-21 planning, not started. Research release notes / audit change summary is a human-audit / contractor-handoff artifact only, not a release approval, not a deployment approval, not a publish approval, not a trading signal, not a trade approval, not execution readiness, not strategy readiness, not transaction permission, and must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path. No release-notes feedback into execution paths. No report/operator/index/search/bundle/chronicle/digest/quality-gate/handoff/archive-manifest/release-notes feedback into execution paths. Referenced artifact files are not read. File references and metadata strings are not traversed, opened, followed, validated, or executed. Human review guide is advisory-only and not gating. No action commands are emitted. No release/deployment checklist semantics. No Web UI, no dashboard, no database persistence, no config YAML, no JSON schema, no Freqtrade strategy class, no freqtrade import, no Binance, no real exchange, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic, no production data reads/writes.

## Current Status

MVP-0 foundation is complete and committed.

MVP-1 Data Foundation is complete and committed. All 91 tests pass.

MVP-2 Market State is complete and committed. All 278 tests pass.
- Market State Models, Indicator Utilities, Regime Engine, Breadth Engine, JSON Output Writers all implemented.
- No Binance integration. No Freqtrade integration. No live trading.

MVP-3 Decision Layer is complete and committed. All 394 tests pass.
- Decision Models, Decision Engine, Decision Writer, Integration Tests all implemented.
- No Binance integration. No Freqtrade integration. No live trading. No JSON input reading.

MVP-4 Execution Bridge is complete and committed. All 538 tests pass.
- Execution Bridge Models, Engine, Writer, Integration Tests, Final Review all implemented.
- No Binance integration. No Freqtrade runtime integration. No live trading. No trading logic. No API keys.

MVP-5 Freqtrade Integration is complete and committed. All 722 tests pass.
- Freqtrade Bridge Models, Engine, Writer, Integration Tests, Final Review all implemented.
- No Binance integration. No real Freqtrade runtime integration. No live trading. No trading logic. No API keys.

MVP-6 Freqtrade Strategy Contract is complete and committed. All 959 tests pass.
- Strategy Contract Models, Engine, Writer, Integration Tests, Final Review all implemented.
- No Binance integration. No real Freqtrade runtime integration. No live trading. No trading logic. No API keys.

MVP-7 Freqtrade Dry-Run Strategy Adapter is complete and committed. All 1214 tests pass.
- Strategy Adapter Models, Engine, Writer, Integration Tests, Final Review all implemented.
- `src/hunter/strategy_adapter/models.py` — 8 model types + 15 reason codes.
- `src/hunter/strategy_adapter/engine.py` — 6 engine functions.
- `src/hunter/strategy_adapter/writer.py` — 3 writer functions + default path constant.
- `tests/test_strategy_adapter/test_models.py` — 94 model tests.
- `tests/test_strategy_adapter/test_engine.py` — 75 engine tests.
- `tests/test_strategy_adapter/test_writer.py` — 41 writer tests.
- `tests/test_strategy_adapter/test_integration.py` — 45 integration tests.
- `DEFAULT_ADAPTER_DECISION_PATH = data/strategy_adapter/current_adapter_decision.json`.
- Adapter produces dry-run-only fail-closed `AdapterDecisionContext` for future Freqtrade-facing consumers.
- No config YAML exists. No JSON schema exists. No deployable Freqtrade strategy class exists.
- No Binance integration. No real Freqtrade runtime integration. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

SPEC-009 Freqtrade Deployable Dry-Run Strategy design is finalized and polished.
- `DryRunStrategyState`, `DryRunStrategyMode`, `DryRunSignalAction`, `DryRunStrategyRuntimeContext` defined.
- Fail-closed deployable dry-run strategy rules, deterministic reason codes, future config/schema/output defined.
- PlantUML component and runtime flow diagrams included.
- 5-step implementation plan defined.
- MVP-8 Step 1 Dry-Run Strategy Runtime Models complete.
- `dry_run_strategy` package now exists with models, engine, writer, and integration tests.
- `tests/test_dry_run_strategy/test_models.py` exists with 94 tests.
- MVP-8 Step 2 Dry-Run Strategy Runtime Engine complete.
- `src/hunter/dry_run_strategy/engine.py` exists with 6 engine functions.
- `tests/test_dry_run_strategy/test_engine.py` exists with 93 tests.
- MVP-8 Step 3 Dry-Run Strategy Runtime JSON Writer complete.
- `src/hunter/dry_run_strategy/writer.py` exists with 3 writer functions + default path constant.
- `tests/test_dry_run_strategy/test_writer.py` exists with 42 tests.
- MVP-8 Step 4 Dry-Run Strategy Runtime Integration Tests complete.
- `tests/test_dry_run_strategy/test_integration.py` exists with 48 tests.
- MVP-8 Step 5 Final Review complete. Verdict: PASS. No defects found.
- `DEFAULT_DRY_RUN_STRATEGY_RUNTIME_PATH = data/freqtrade_strategy/current_dry_run_strategy_runtime.json`.
- Full test suite: 1491 tests passing.

SPEC-010 Freqtrade Dry-Run Strategy Shell design is approved.
- `specs/SPEC-010-Freqtrade-Dry-Run-Strategy-Shell.md` approved.
- Designs a Freqtrade-compatible dry-run strategy shell consuming MVP-8 runtime JSON.
- Key safety clarifications: research-only signal exposure (metadata/columns only, no real trade signals), `populate_entry_trend` never sets `enter_long`/`enter_short`, `populate_exit_trend` never sets `exit_long`/`exit_short`, Freqtrade compatibility is interface boundary only, shell must not bypass MVP-5/MVP-6/MVP-7/MVP-8 safety contexts.
- MVP-9 Step 1 Shell Models and Validator complete.
- MVP-9 Step 2 Shell Adapter Boundary complete.
- MVP-9 Step 3 Shell Integration Tests complete.
- MVP-9 Step 4 Final Review complete. Verdict: PASS. No defects found.
- No Freqtrade strategy class. No freqtrade import.

SPEC-011 Freqtrade Dry-Run Research Observation Reports design is approved with notes and polished.
- `specs/SPEC-011-Dry-Run-Research-Observation-Reports.md` approved (729 lines).
- Designs a dry-run research observation/reporting layer consuming MVP-9 shell metadata.
- Produces local JSON/Markdown reports for human review only.
- Key safety clarifications: reports are human-review artifacts only (not trading signals), must never be consumed by execution/strategy/shell/order layers, must not feed back into any MVP layer, fail-closed observations produce safe audit output only, missing/invalid inputs summarized as BLOCKED/UNKNOWN, reports must not contain API keys/secrets/credentials/executable trading instructions.
- MVP-10 Step 1 Observation Models and Engine complete.
- `src/hunter/observation/__init__.py` — public API exports.
- `src/hunter/observation/models.py` — 9 models: ObservationState, ObservationSignal, ReportFormat, ObservationConfig, ObservationSafetyFlags, SignalObservation, ObservationWindow, ObservationDataQuality, ObservationReport.
- `src/hunter/observation/engine.py` — 5 engine functions: build_signal_observation, build_observation_window, build_observation_report, build_observation_safety_flags, has_unsafe_metadata.
- `tests/test_observation/test_models.py` — 77 model tests.
- `tests/test_observation/test_engine.py` — 59 engine tests.
- 13 deterministic reason codes + FORBIDDEN_METADATA_KEYS.
- MVP-10 Step 2 Observation Report Writer complete.
- `src/hunter/observation/writer.py` — 5 writer functions: observation_report_to_dict, observation_report_to_markdown, atomic_write_json_report, atomic_write_markdown_report, write_observation_reports.
- `src/hunter/observation/__init__.py` — updated with writer exports.
- `tests/test_observation/test_writer.py` — 58 writer tests.
- Default JSON path: `data/observation/latest_observation_report.json`.
- Default Markdown path: `reports/observation/latest_observation_report.md`.
- MVP-10 Step 3 Observation Integration Tests complete.
- `tests/test_observation/test_integration.py` — 58 integration tests.
- Full test suite: 1968 tests passing using `pytest --import-mode=importlib`.
- No models, engine, writer, or `__init__.py` changes.
- No integration tests yet. → now complete with integration tests.
- No Freqtrade strategy class. No freqtrade import. No Freqtrade runtime connection. No Binance. No real exchange. No API keys. No live trading. No real orders. No leverage. No shorting. No real entry/exit execution logic. No report feedback into execution paths. No production data reads/writes.

MVP-12 — Review Index is complete and committed.
- `src/hunter/review_index/models.py` — frozen index dataclasses, enums, reason codes, forbidden index content detection.
- `src/hunter/review_index/engine.py` — in-memory review index engine functions.
- `src/hunter/review_index/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/review_index/__init__.py` — updated with writer exports.
- `tests/test_review_index/test_models.py` — 70 model tests.
- `tests/test_review_index/test_engine.py` — 97 engine tests.
- `tests/test_review_index/test_writer.py` — 52 writer tests.
- `tests/test_review_index/test_integration.py` — 21 integration tests.
- 239 review_index tests total. 1 skipped.
- Full suite: 2450 tests passing, 1 skipped.

MVP-13 — Review Search / Query Layer is complete and committed.
- `src/hunter/review_search/models.py` — frozen search dataclasses, 12 reason codes, 8 search output safety flags, forbidden search content detection.
- `src/hunter/review_search/engine.py` — 6 engine functions: build_search_safety_flags, validate_search_query, entry_matches_query, score_search_entry, sort_search_results, build_search_result.
- `src/hunter/review_search/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/review_search/__init__.py` — updated with engine and writer exports.
- `tests/test_review_search/test_models.py` — 92 model tests.
- `tests/test_review_search/test_engine.py` — 82 engine tests.
- `tests/test_review_search/test_writer.py` — 51 writer tests.
- `tests/test_review_search/test_integration.py` — 45 integration tests.
- 278 review_search tests total. 1 skipped.
- Full suite: 2728 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Search results are human-audit artifacts only. Not trading signals. Not trade approvals.
- No file reads, no network, no Freqtrade, no Binance, no exchange, no API keys, no live trading, no real orders, no leverage, no shorting, no entry/exit execution logic.
- No report/operator/index/search feedback into execution paths.
- File references remain strings only, never traversed, opened, followed, validated, or executed.

MVP-14 — Local Research Bundle / Evidence Pack is complete and committed.
- SPEC-015: `specs/SPEC-015-Local-Research-Bundle-Evidence-Pack.md` — approved with no critical issues.
- `src/hunter/research_bundle/models.py` — frozen bundle dataclasses, enums, 12 reason codes, 22 forbidden terms, 8 bundle output safety flags, 13 unsafe safety flags.
- `src/hunter/research_bundle/engine.py` — 7 engine functions: build_bundle_safety_flags, has_unsafe_bundle_content, validate_bundle_item, build_bundle_item, build_bundle_summary, build_bundle_data_quality, build_research_bundle.
- `src/hunter/research_bundle/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/research_bundle/__init__.py` — updated with engine and writer exports.
- `tests/test_research_bundle/test_models.py` — 54 model tests.
- `tests/test_research_bundle/test_engine.py` — 58 engine tests.
- `tests/test_research_bundle/test_writer.py` — 49 writer tests.
- `tests/test_research_bundle/test_integration.py` — 33 integration tests.
- 194 research_bundle tests total. 1 skipped.
- Full suite: 2922 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Z.ai Step 3 review: APPROVED. Engine `human_note_count` fix validated — counts items with non-empty notes (not just HUMAN_NOTE kind), aligning with SPEC-015 semantic definition.
- Safety: human-audit only, no execution feedback, no trading signals, no file reference traversal.

MVP-15 — Local Research Chronicle / Audit Timeline is complete and committed.
- SPEC-016: `specs/SPEC-016-Local-Research-Chronicle-Audit-Timeline.md` — approved with notes and polished.
- `src/hunter/chronicle/__init__.py` — public API exports.
- `src/hunter/chronicle/models.py` — frozen chronicle dataclasses, enums, 12 reason codes, forbidden chronicle content detection, ArtifactType, ChronicleEntry, ChronicleSummary, ChronicleDataQuality, ChronicleSafetyFlags, ResearchChronicle.
- `src/hunter/chronicle/engine.py` — in-memory chronicle engine functions: has_unsafe_chronicle_content, build_chronicle_safety_flags, build_chronicle_entry_* builders, build_chronicle_summary, build_chronicle_data_quality, build_research_chronicle.
- `src/hunter/chronicle/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/chronicle/__init__.py` — updated with writer exports.
- `tests/test_chronicle/test_models.py` — model tests.
- `tests/test_chronicle/test_engine.py` — engine tests.
- `tests/test_chronicle/test_writer.py` — writer tests.
- `tests/test_chronicle/test_integration.py` — integration tests.
- 239 chronicle tests total. 1 skipped.
- Full suite: 3161 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Z.ai Step 3 review: APPROVED. No critical issues found.
- Safety: human-audit only, no execution feedback, no trading signals, trace linkage advisory only, no file reference traversal, no chronicle feedback into execution paths.

MVP-17 — Local Research Quality Gate / Audit Readiness is complete and committed.
- SPEC-018: `specs/SPEC-018-Local-Research-Quality-Gate-Audit-Readiness.md` — approved with one minor source defect found and fixed before Step 4.
- `src/hunter/research_quality_gate/__init__.py` — public API exports.
- `src/hunter/research_quality_gate/models.py` — frozen quality gate dataclasses, enums, 29 reason codes, forbidden quality gate content detection, QualityGateConfig, QualityGateSafetyFlags, QualityGateCheck, QualityGateCheckKind, QualityGateSummary, QualityGateDataQuality, ResearchQualityGate.
- `src/hunter/research_quality_gate/engine.py` — in-memory quality gate engine functions: has_unsafe_quality_gate_content, build_quality_gate_safety_flags, build_quality_gate_check, build_quality_gate_summary, build_quality_gate_data_quality, build_research_quality_gate.
- `src/hunter/research_quality_gate/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/research_quality_gate/__init__.py` — updated with writer exports.
- `tests/test_research_quality_gate/test_models.py` — model tests.
- `tests/test_research_quality_gate/test_engine.py` — engine tests.
- `tests/test_research_quality_gate/test_writer.py` — writer tests.
- `tests/test_research_quality_gate/test_integration.py` — 31 integration tests.
- 152 research_quality_gate tests total.
- Full suite: 3454 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Z.ai Step 3 review: APPROVED. Source defect `_is_blocking_reason` not treating `UNRESOLVED_BLOCKERS` as blocking was identified and fixed before Step 4. `engine._is_blocking_reason` now aligns with canonical `QUALITY_GATE_BLOCKING_REASON_CODES`; `UNRESOLVED_BLOCKERS` is included in gate-level `ResearchQualityGate.reason_codes`; `STALE_ARTIFACT` remains non-blocking per SPEC-018 §3.3.
- Safety: human-audit only, no execution feedback, no trading signals, not execution readiness, not strategy readiness, not release/deployment approval, not transaction permission, no file reference traversal, no quality gate feedback into execution paths.

MVP-18 — Local Research Handoff Packet is complete and committed.
- SPEC-019: `specs/SPEC-019-Local-Research-Handoff-Packet.md` — approved with no critical issues.
- `src/hunter/research_handoff/__init__.py` — public API exports.
- `src/hunter/research_handoff/models.py` — frozen handoff dataclasses, enums, 32 reason codes, forbidden handoff content detection, HandoffConfig, HandoffSafetyFlags, HandoffPacketKind, HandoffState, HandoffSection, HandoffSummary, HandoffDataQuality, ResearchHandoffPacket.
- `src/hunter/research_handoff/engine.py` — in-memory handoff engine functions: has_unsafe_handoff_content, build_handoff_safety_flags, build_handoff_section, build_handoff_summary, build_handoff_data_quality, build_research_handoff_packet.
- `src/hunter/research_handoff/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/research_handoff/__init__.py` — updated with writer exports.
- `tests/test_research_handoff/test_models.py` — model tests.
- `tests/test_research_handoff/test_engine.py` — engine tests.
- `tests/test_research_handoff/test_writer.py` — writer tests.
- `tests/test_research_handoff/test_integration.py` — 25 integration tests.
- 146 research_handoff tests total.
- Full suite: 3600 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Z.ai Step 3 review: APPROVED. No critical issues found.
- Safety: human-audit / contractor-handoff artifact only, no execution feedback, no trading signals, not execution readiness, not strategy readiness, not release/deployment approval, not transaction permission, no file reference traversal, no handoff feedback into execution paths, no report/operator/index/search/bundle/chronicle/digest/quality-gate/handoff feedback into execution paths.

MVP-20 — Local Research Release Notes / Audit Change Summary is complete and committed.
- SPEC-021: `specs/SPEC-021-Local-Research-Release-Notes-Audit-Change-Summary.md` — approved with no critical issues.
- `src/hunter/research_release_notes/__init__.py` — public API exports.
- `src/hunter/research_release_notes/models.py` — frozen release notes dataclasses, enums, reason codes, forbidden release notes content detection, ReleaseNotesConfig, ReleaseNotesSafetyFlags, ReleaseNotesSectionKind, ReleaseNotesChangeSeverity, ReleaseNotesState, ReleaseNotesChangeItem, ReleaseNotesSection, ReleaseNotesSummary, ReleaseNotesDataQuality, ResearchReleaseNotes.
- `src/hunter/research_release_notes/engine.py` — in-memory release notes engine functions: has_unsafe_release_notes_content, build_release_notes_safety_flags, build_release_notes_change_item, build_release_notes_section, build_release_notes_summary, build_release_notes_data_quality, build_research_release_notes.
- `src/hunter/research_release_notes/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/research_release_notes/__init__.py` — updated with writer exports.
- `tests/test_research_release_notes/test_models.py` — model tests.
- `tests/test_research_release_notes/test_engine.py` — engine tests.
- `tests/test_research_release_notes/test_writer.py` — writer tests.
- `tests/test_research_release_notes/test_integration.py` — 46 integration tests.
- 157 research_release_notes tests total.
- Full suite: 3921 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Z.ai Step 3 review: APPROVED. No critical issues found.
- Safety: human-audit / contractor-handoff artifact only, not release approval, not deployment approval, not publish approval, no execution feedback, no trading signals, not execution readiness, not strategy readiness, not transaction permission, referenced artifact files are not read, file references and metadata strings are not traversed/opened/followed/validated/executed, human review guide advisory-only and not gating, no action commands emitted, no release/deployment checklist semantics, no release-notes feedback into execution paths, no report/operator/index/search/bundle/chronicle/digest/quality-gate/handoff/archive-manifest/release-notes feedback into execution paths.

MVP-19 — Local Research Archive Manifest is complete and committed.
- SPEC-020: `specs/SPEC-020-Local-Research-Archive-Manifest.md` — approved with no critical issues.
- `src/hunter/research_archive_manifest/__init__.py` — public API exports.
- `src/hunter/research_archive_manifest/models.py` — frozen archive manifest dataclasses, enums, 34 reason codes, forbidden archive manifest content detection, ArchiveManifestConfig, ArchiveManifestSafetyFlags, ArchiveArtifactFamily, ArchiveManifestState, ArchiveArtifactEntry, ArchiveManifestSummary, ArchiveManifestDataQuality, ResearchArchiveManifest.
- `src/hunter/research_archive_manifest/engine.py` — in-memory archive manifest engine functions: has_unsafe_archive_manifest_content, build_archive_manifest_safety_flags, build_archive_artifact_entry, build_archive_manifest_summary, build_archive_manifest_data_quality, build_research_archive_manifest.
- `src/hunter/research_archive_manifest/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/research_archive_manifest/__init__.py` — updated with writer exports.
- `tests/test_research_archive_manifest/test_models.py` — model tests.
- `tests/test_research_archive_manifest/test_engine.py` — engine tests.
- `tests/test_research_archive_manifest/test_writer.py` — writer tests.
- `tests/test_research_archive_manifest/test_integration.py` — 42 integration tests.
- 164 research_archive_manifest tests total.
- Full suite: 3764 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Z.ai Step 3 review: APPROVED. No critical issues found.
- Safety: human-audit inventory artifact only, no execution feedback, no trading signals, not execution readiness, not strategy readiness, not release/deployment approval, not transaction permission, referenced artifact files are not read, file references and metadata strings are not traversed/opened/followed/validated/executed, no archive manifest feedback into execution paths, no report/operator/index/search/bundle/chronicle/digest/quality-gate/handoff/archive-manifest feedback into execution paths.

MVP-16 — Local Research Digest / Executive Summary is complete and committed.
- SPEC-017: `specs/SPEC-017-Local-Research-Digest-Executive-Summary.md` — approved with no critical issues.
- `src/hunter/research_digest/__init__.py` — public API exports.
- `src/hunter/research_digest/models.py` — frozen digest dataclasses, enums, 17 reason codes, forbidden digest content detection, DigestConfig, DigestSafetyFlags, DigestSection, DigestSectionKind, DigestSummary, DigestDataQuality, ResearchDigest.
- `src/hunter/research_digest/engine.py` — in-memory digest engine functions: has_unsafe_digest_content, build_digest_safety_flags, build_digest_section, build_digest_summary, build_digest_data_quality, build_research_digest.
- `src/hunter/research_digest/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/research_digest/__init__.py` — updated with writer exports.
- `tests/test_research_digest/test_models.py` — model tests.
- `tests/test_research_digest/test_engine.py` — engine tests.
- `tests/test_research_digest/test_writer.py` — writer tests.
- `tests/test_research_digest/test_integration.py` — 26 integration tests.
- 141 research_digest tests total. 1 skipped.
- Full suite: 3302 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Z.ai Step 3 review: APPROVED. No critical issues found.
- Safety: human-audit only, no execution feedback, no trading signals, no recommendation engine, no action-command generator, no file reference traversal, no digest feedback into execution paths.

## Next Step

MVP-21 planning, not started. No SPEC drafted yet. Requires human approval before any implementation.

### Not Allowed Until Future SPEC
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
- No search feedback into execution paths.
- No bundle feedback into execution paths.
- No chronicle feedback into execution paths.
- No digest feedback into execution paths.
- No quality gate feedback into execution paths.
- No handoff feedback into execution paths.
- No archive manifest feedback into execution paths.
- No release-notes feedback into execution paths.
- No Web UI.
- No dashboard.
- No database persistence.
- No production data reads/writes.

---

## Previous State (MVP-12 Complete)

MVP-12 — Review Index is complete and committed. All 239 tests pass (1 skipped).
- Review Index Models, Engine, Writer, Integration Tests all implemented.
- No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime.
- No Binance. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.
- File references are local strings only and are not traversed, opened, followed, validated, or executed.

---
