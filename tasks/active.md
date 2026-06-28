# Active Task

## Current Task

MVP-15 planning, not started.

## Status

MVP-14 is complete and committed. SPEC-015 approved with no critical issues. All MVP-14 steps completed successfully. Version 0.14.0-dev. Full test suite: 2922 tests passing, 1 skipped using `pytest --import-mode=importlib`. Current active task: MVP-15 planning, not started. No SPEC drafted yet. Requires human approval before any implementation.

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

MVP-15 planning, not started.
- No SPEC drafted yet. Requires human approval before any implementation.
- No source code changes until SPEC approved and planning complete.

### Allowed
- Planning documents, discussion, SPEC drafting (outside repo or in docs/ if needed).
- No source code changes until MVP-15 planning approved.

### Not Allowed
- No changes to existing source code.
- No changes to existing tests.
- No config YAML, no JSON schema, no Freqtrade strategy class, no freqtrade import, no Freqtrade runtime connection, no Binance, no real exchange, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic, no production data reads/writes, no report feedback into execution paths, no operator feedback into execution paths, no index feedback into execution paths, no search feedback into execution paths, no bundle feedback into execution paths, no Web UI, no dashboard, no database persistence.
- File references remain local strings only and must not be traversed/opened/followed/validated/executed.

## Previous Task

MVP-13 Step 4 — Final validation and version bump (Complete).
- Version bumped to 0.13.0-dev.
- Full suite: 2728 tests passing, 1 skipped.
- No source changes.

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
- [ ] MVP-15 planning: not started. No SPEC drafted yet. Requires human approval before any implementation.

## Next Step

MVP-15 planning, not started. No SPEC drafted yet. Requires human approval before any implementation.

Future research bundle search engine, operator workflow UI, or cross-reference validation may be considered only in a future SPEC, but is not implemented yet.
