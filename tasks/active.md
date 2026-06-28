# Active Task

## Current Task

MVP-14 Step 1 — Research Bundle Models and Engine, not started.

## Status

MVP-14 planning complete. SPEC-015 approved with no critical issues. Ready for Step 1 implementation. Version 0.13.0-dev. Full test suite: 2728 tests passing, 1 skipped using `pytest --import-mode=importlib`.

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

MVP-14 Step 1 — Research Bundle Models and Engine (Not Started).
- `src/hunter/research_bundle/__init__.py` — public API exports.
- `src/hunter/research_bundle/models.py` — frozen bundle dataclasses, enums, reason codes, forbidden bundle content detection.
- `src/hunter/research_bundle/engine.py` — in-memory bundle engine functions.
- `tests/test_research_bundle/__init__.py` — test package init.
- `tests/test_research_bundle/test_models.py` — model tests.
- `tests/test_research_bundle/test_engine.py` — engine tests.
- Target: ~140 tests.

MVP-14 Step 2 — Research Bundle Writer (Not Started).
- `src/hunter/research_bundle/writer.py` — JSON/Markdown serialization, atomic file writing.
- `tests/test_research_bundle/test_writer.py` — writer tests.
- Default JSON path: `data/research_bundle/latest_research_bundle.json`.
- Default Markdown path: `reports/research_bundle/latest_research_bundle.md`.
- Target: ~50 tests.

MVP-14 Step 3 — Research Bundle Integration Tests (Not Started).
- `tests/test_research_bundle/test_integration.py` — integration tests.
- Target: ~45 tests.

MVP-14 Step 4 — Final Review and Version Bump (Not Started).
- Verdict: PASS / PASS WITH NOTES / FAIL.
- If PASS: version bump to 0.14.0-dev.

## Scope

MVP-14 Step 1 — Research Bundle Models and Engine, not started.
- SPEC-015: Local Research Bundle / Evidence Pack.
- Approved with no critical issues. Ready for implementation.

### Allowed
- `src/hunter/research_bundle/` package creation.
- `tests/test_research_bundle/` test package creation.
- `specs/SPEC-015-Local-Research-Bundle-Evidence-Pack.md` reference only.
- No source code changes outside `src/hunter/research_bundle/`.

### Not Allowed
- No changes to existing source code outside `src/hunter/research_bundle/`.
- No changes to existing tests outside `tests/test_research_bundle/`.
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
- [ ] MVP-14 Step 1: research bundle models and engine, not started.
- [ ] MVP-14 Step 2: research bundle writer, not started.
- [ ] MVP-14 Step 3: research bundle integration tests, not started.
- [ ] MVP-14 Step 4: final review and version bump, not started.

## Next Step

MVP-14 Step 1 — Research Bundle Models and Engine. SPEC-015 approved. Ready for implementation.

Future research bundle search engine, operator workflow UI, or cross-reference validation may be considered only in a future SPEC, but is not implemented yet.
