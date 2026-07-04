# Active Task

## Current Task

MVP-32 — Local Research Final Audit Pack Export is complete. Next phase: not started; requires human direction.

## Status

MVP-32 — Local Research Final Audit Pack Export is complete. SPEC-033 implemented across models, engine, writer, and integration tests. Version 0.32.0-dev. Full test suite: 5750 tests passing, 1 skipped using `pytest --import-mode=importlib`. All four steps (Step 1 models/engine, Step 2 writer, Step 3 integration tests, Step 4 finalization) completed. Source changes in finalization limited to version bump and documentation only. Safety boundaries preserved: local, call-triggered, audit-only final export/manifest layer over caller-provided in-memory research reports and opaque artifact references; not a production release approval system, not a certification of trading readiness, not a strategy selector, not a signal generator, and not a performance attribution tool; not a trading signal, not trade/strategy/execution/portfolio/universe approval, and not Freqtrade input; no Freqtrade input, no Binance/exchange/API/live data, no order/execution/action commands, no leverage/shorting, no feedback into execution/strategy/portfolio paths; no scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced. Current supported entry is the callable `build_final_audit_pack_report(input, config)` public API; no standalone runner or console script entry has been added. Next phase: not started; requires human direction.

MVP-31 — Local Research Experiment Ledger is complete. Next recommended step: not started; requires human direction. [SUPERSEDED]

MVP-24 — Relative Strength Engine is complete and committed. SPEC-025 implemented across models, engine, writer, and integration tests. Version 0.24.0-dev. Full test suite: 4628 tests passing, 1 skipped using `pytest --import-mode=importlib`. All four steps (Step 1 models/engine, Step 2 writer, Step 3 integration tests, Step 4 finalization) completed. No source changes made in finalization. Safety boundaries preserved. [SUPERSEDED]

MVP-24 planning / SPEC-025 Relative Strength Engine — not started. No SPEC drafted yet. Requires human approval before any implementation. [SUPERSEDED]

MVP-23 is complete and committed. SPEC-024 approved with minor notes. All MVP-23 steps completed successfully. Version 0.23.0-dev. Full test suite: 4499 tests passing, 1 skipped using `pytest --import-mode=importlib`. Current active task: MVP-24 planning / SPEC-025 Relative Strength Engine, not started. No SPEC drafted yet. Requires human approval before any implementation. [SUPERSEDED]

MVP-21 is complete and committed. SPEC-022 approved with no critical issues. All MVP-21 steps completed successfully. Version 0.21.0-dev. Full test suite: 4078 tests passing, 1 skipped using `pytest --import-mode=importlib`.

MVP-20 is complete and committed. SPEC-021 approved with no critical issues. All MVP-20 steps completed successfully. Version 0.20.0-dev. Full test suite: 3921 tests passing, 1 skipped using `pytest --import-mode=importlib`.

MVP-19 is complete and committed. SPEC-020 approved with no critical issues. All MVP-19 steps completed successfully. Version 0.19.0-dev. Full test suite: 3764 tests passing, 1 skipped using `pytest --import-mode=importlib`.

MVP-18 is complete and committed. SPEC-019 approved with no critical issues. All MVP-18 steps completed successfully. Version 0.18.0-dev. Full test suite: 3600 tests passing, 1 skipped using `pytest --import-mode=importlib`.

MVP-17 is complete and committed. SPEC-018 approved with one minor source defect found and fixed before Step 4. All MVP-17 steps completed successfully. Version 0.17.0-dev. Full test suite: 3454 tests passing, 1 skipped using `pytest --import-mode=importlib`.

MVP-16 is complete and committed. SPEC-017 approved with no critical issues. All MVP-16 steps completed successfully. Version 0.16.0-dev. Full test suite: 3302 tests passing, 1 skipped using `pytest --import-mode=importlib`.

MVP-15 is complete and committed. SPEC-016 approved with notes and polished. All MVP-15 steps completed successfully. Version 0.15.0-dev. Full test suite: 3161 tests passing, 1 skipped using `pytest --import-mode=importlib`.

MVP-14 is complete and committed. SPEC-015 approved with no critical issues. All MVP-14 steps completed successfully. Version 0.14.0-dev. Full test suite: 2922 tests passing, 1 skipped using `pytest --import-mode=importlib`.

MVP-13 is complete and committed.
- `src/hunter/review_search/models.py` — frozen search dataclasses, 12 reason codes, 8 search output safety flags, forbidden search content detection.
- `src/hunter/review_search/engine.py` — 6 engine functions.
- `src/hunter/review_search/writer.py` — JSON/Markdown serialization, atomic file writing.
- `tests/test_review_search/test_models.py` — 92 model tests.
- `tests/test_review_search/test_engine.py` — 82 engine tests.
- `tests/test_review_search/test_writer.py` — 51 writer tests.
- `tests/test_review_search/test_integration.py` — 45 integration tests.
- 278 review_search tests total. 1 skipped.
- Full suite: 2728 tests passing, 1 skipped using `pytest --import-mode=importlib`.

MVP-14 Step 1 — Research Bundle Models and Engine (Complete).
- `src/hunter/research_bundle/__init__.py` — public API exports.
- `src/hunter/research_bundle/models.py` — frozen bundle dataclasses, enums, 12 reason codes, 22 forbidden terms, 8 bundle output safety flags, 13 unsafe safety flags.
- `src/hunter/research_bundle/engine.py` — 7 engine functions.
- `tests/test_research_bundle/test_models.py` — 54 model tests.
- `tests/test_research_bundle/test_engine.py` — 58 engine tests.
- 112 research_bundle model/engine tests pass.

MVP-14 Step 2 — Research Bundle Writer (Complete).
- `src/hunter/research_bundle/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/research_bundle/__init__.py` — updated with writer exports.
- `tests/test_research_bundle/test_writer.py` — 49 writer tests.
- Default JSON path: `data/research_bundle/latest_research_bundle.json`.
- Default Markdown path: `reports/research_bundle/latest_research_bundle.md`.

MVP-14 Step 3 — Research Bundle Integration Tests (Complete).
- `tests/test_research_bundle/test_integration.py` — 33 integration tests.
- 194 research_bundle tests total (54 model + 58 engine + 49 writer + 33 integration). 1 skipped.
- Full suite: 2922 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Z.ai Step 3 review: APPROVED. Engine `human_note_count` fix validated.

MVP-14 Step 4 — Final Review and Version Bump (Complete).
- Verdict: PASS. No defects found.
- Version bumped to 0.14.0-dev.
- All safety invariants verified.

## Scope

Next MVP: not started.
- No SPEC drafted yet. Requires human approval before any implementation.
- No source code changes until next MVP planning approved.

### Allowed
- Planning documents, discussion, SPEC drafting (outside repo or in docs/ if needed).
- No source code changes until MVP-24 planning approved.

### Not Allowed
- No changes to existing source code.
- No changes to existing tests.
- No config YAML, no JSON schema, no Freqtrade strategy class, no freqtrade import, no Freqtrade runtime connection, no Binance, no real exchange, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic, no production data reads/writes, no report feedback into execution paths, no operator feedback into execution paths, no index feedback into execution paths, no search feedback into execution paths, no bundle feedback into execution paths, no chronicle feedback into execution paths, no digest feedback into execution paths, no quality gate feedback into execution paths, no handoff feedback into execution paths, no archive manifest feedback into execution paths, no release-notes feedback into execution paths, no audit-catalog feedback into execution paths, no audit-closure feedback into execution paths, no audit-snapshot feedback into execution paths, no Web UI, no dashboard, no database persistence.
- File references and metadata strings remain local strings only and must not be traversed/opened/followed/validated/executed.

## Previous Task

MVP-23 Step 4 — Final validation and version bump (Complete).
- Version bumped from 0.22.0-dev to 0.23.0-dev.
- `pyproject.toml` updated.
- `src/hunter/__init__.py` updated.
- `CHANGELOG.md` updated with MVP-23 completion summary.
- `docs/handoff/CURRENT_STATE.md` updated.
- `tasks/active.md` updated.
- `tasks/agent-log.md` updated.
- Step 3 Whole MVP-23 review: APPROVED WITH MINOR NOTES. No critical issues found.
- research_audit_snapshot tests: 238 passed.
- Full suite: 4499 tests passing, 1 skipped.
- All safety invariants verified.
- MVP-23 complete.

## Definition of Done

- [x] SPEC-012 approved with notes and polished.
- [x] MVP-11 Step 1 complete: review models and engine implemented.
- [x] MVP-11 Step 2 complete: review writer implemented.
- [x] MVP-11 Step 3 complete: integration tests implemented.
- [x] MVP-11 Step 4 complete: final review passed.
- [x] 138 review model/engine tests pass.
- [x] 54 writer tests pass.
- [x] 83 integration tests pass.
- [x] Full suite 2211 tests pass.
- [x] No defects found.
- [x] Version bumped to 0.11.0-dev.
- [x] SPEC-013 drafted for MVP-12 planning.
- [x] SPEC-013 reviewed and approved.
- [x] MVP-12 Step 1 complete: review index models and engine implemented.
- [x] 70 review index model tests pass.
- [x] 97 review index engine tests pass.
- [x] Full suite 2377 tests pass, 1 skipped.
- [x] MVP-12 Step 2 complete: review index writer implemented.
- [x] 52 review index writer tests pass.
- [x] Full suite 2429 tests pass, 1 skipped.
- [x] MVP-12 Step 3 complete: review index integration tests implemented.
- [x] 21 review index integration tests pass.
- [x] Full suite 2450 tests pass, 1 skipped.
- [x] MVP-12 Step 4 complete: final validation and version bump.
- [x] Version bumped to 0.12.0-dev.
- [x] Full suite 2450 tests pass, 1 skipped. No regressions.
- [x] SPEC-014 drafted for MVP-13 planning.
- [x] SPEC-014 reviewed and approved with minor notes.
- [x] MVP-13 Step 1 complete: review search models and engine implemented.
- [x] 92 review search model tests pass.
- [x] 82 review search engine tests pass.
- [x] Full suite 2624 tests pass, 1 skipped.
- [x] MVP-13 Step 2 complete: review search writer implemented.
- [x] 51 review search writer tests pass.
- [x] Full suite 2675 tests pass, 1 skipped.
- [x] MVP-13 Step 3 complete: review search integration tests implemented.
- [x] 45 review search integration tests pass.
- [x] Full suite 2728 tests pass, 1 skipped.
- [x] MVP-13 Step 4 complete: final review and version bump.
- [x] Version bumped to 0.13.0-dev.
- [x] Full suite 2728 tests pass, 1 skipped. No regressions.
- [x] SPEC-015 drafted for MVP-14 planning.
- [x] SPEC-015 reviewed and approved with no critical issues.
- [x] MVP-14 Step 1: research bundle models and engine, complete.
- [x] 54 research bundle model tests pass.
- [x] 58 research bundle engine tests pass.
- [x] Full suite 2840 tests pass, 1 skipped.
- [x] MVP-14 Step 2: research bundle writer, complete.
- [x] 49 research bundle writer tests pass.
- [x] Full suite 2889 tests pass, 1 skipped.
- [x] MVP-14 Step 3: research bundle integration tests, complete.
- [x] 33 research bundle integration tests pass.
- [x] Full suite 2922 tests pass, 1 skipped.
- [x] Z.ai Step 3 review: APPROVED.
- [x] MVP-14 Step 4: final review and version bump, complete.
- [x] Version bumped to 0.14.0-dev.
- [x] Full suite 2922 tests pass, 1 skipped. No regressions.
- [x] SPEC-016 drafted for MVP-15 planning.
- [x] SPEC-016 reviewed and approved with notes.
- [x] MVP-15 Step 1: chronicle models and engine, complete.
- [x] Chronicle model tests pass.
- [x] Chronicle engine tests pass.
- [x] Full suite passes after Step 1, 1 skipped.
- [x] MVP-15 Step 2: chronicle writer, complete.
- [x] Chronicle writer tests pass.
- [x] Full suite passes after Step 2, 1 skipped.
- [x] MVP-15 Step 3: chronicle integration tests, complete.
- [x] Chronicle integration tests pass.
- [x] 239 chronicle tests total pass, 1 skipped.
- [x] Full suite 3161 tests pass, 1 skipped.
- [x] Z.ai Step 3 review: APPROVED.
- [x] MVP-15 Step 4: final validation and version bump, complete.
- [x] Version bumped to 0.15.0-dev.
- [x] Full suite 3161 tests pass, 1 skipped. No regressions.
- [x] MVP-16 Step 1 complete: research digest models and engine implemented.
- [x] MVP-16 Step 2 complete: research digest writer implemented.
- [x] MVP-16 Step 3 complete: research digest integration tests implemented.
- [x] MVP-16 Step 4 complete: final validation passed, version bumped to 0.16.0-dev.
- [x] MVP-16 complete.
- [x] MVP-17 Step 1 complete: research quality gate models and engine implemented.
- [x] MVP-17 Step 2 complete: research quality gate writer implemented.
- [x] MVP-17 Step 3 complete: research quality gate integration tests implemented.
- [x] MVP-17 Step 3 Z.ai review: APPROVED.
- [x] MVP-17 pre-Step 4 source fix complete: `_is_blocking_reason` aligned with `QUALITY_GATE_BLOCKING_REASON_CODES`.
- [x] MVP-17 Step 4 complete: final validation passed, version bumped to 0.17.0-dev.
- [x] MVP-17 complete.
- [x] MVP-18 Step 1 complete: research handoff models and engine implemented.
- [x] MVP-18 Step 2 complete: research handoff writer implemented.
- [x] MVP-18 Step 3 complete: research handoff integration tests implemented.
- [x] MVP-18 Step 3 Z.ai review: APPROVED.
- [x] MVP-18 Step 4 complete: final validation passed, version bumped to 0.18.0-dev.
- [x] MVP-18 complete.
- [x] MVP-19 Step 1 complete: research archive manifest models and engine implemented.
- [x] MVP-19 Step 2 complete: research archive manifest writer implemented.
- [x] MVP-19 Step 3 complete: research archive manifest integration tests implemented.
- [x] MVP-19 Step 3 Z.ai review: APPROVED.
- [x] MVP-19 Step 4 complete: final validation passed, version bumped to 0.19.0-dev.
- [x] MVP-19 complete.
- [x] MVP-20 Step 4 complete: final validation passed, version bumped to 0.20.0-dev.
- [x] MVP-20 complete.
- [x] MVP-21 Step 4 complete: final validation passed, version bumped to 0.21.0-dev.
- [x] MVP-21 complete.
- [x] MVP-22 Step 4 complete: final validation passed, version bumped to 0.22.0-dev.
- [x] MVP-22 complete.
- [x] MVP-23 Step 1 complete: research audit snapshot models and engine implemented.
- [x] MVP-23 Step 2 complete: research audit snapshot writer implemented.
- [x] MVP-23 Step 3 complete: research audit snapshot integration tests implemented.
- [x] MVP-23 Whole MVP-23 review: APPROVED WITH MINOR NOTES. No critical issues found.
- [x] MVP-23 Step 4 complete: final validation passed, version bumped to 0.23.0-dev.
- [x] MVP-23 complete.
- [x] MVP-24 through MVP-30 complete (historical entries in tasks/agent-log.md).
- [x] MVP-31 Step 1 complete: experiment ledger models and engine implemented.
- [x] MVP-31 Step 2 complete: experiment ledger writer implemented.
- [x] MVP-31 Step 3 complete: integration tests implemented.
- [x] MVP-31 Step 4 complete: final validation passed, version bumped to 0.31.0-dev.
- [x] MVP-31 complete.
- [x] Full suite 5629 tests pass, 1 skipped.
- [ ] Next MVP: not started. No SPEC drafted yet. Requires human approval before any implementation.

## Backlog (Non-Blocking)
- Review `research_audit_snapshot` `data_quality.sections_present` / `sections_missing` reporting so successful snapshots correctly reflect the number of sections present (8) versus missing (0). Current behavior is fail-closed (0 / 8) and SPEC-compliant because `build_audit_snapshot_data_quality` does not receive the section list in its SPEC-024 signature.
- Review `EMPTY_CATALOG` reason code reachability in `research_audit_catalog/engine.py` vs SPEC-022 §3.5. Current behavior is fail-closed; `EMPTY_CATALOG` is defined but not emitted.

## Next Step

Next MVP: not started. No SPEC drafted yet. Requires human approval before any implementation.

Future research bundle search engine, operator workflow UI, cross-reference validation, or handoff packet consumers may be considered only in a future SPEC, but is not implemented yet.
