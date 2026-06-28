# Active Task

## Current Task

MVP-13 Step 1 — Review Search Models and Engine, not started.

## Status

MVP-13 planning complete. SPEC-014 approved with minor notes (SearchConfig added, no critical issues). Ready for Step 1 implementation. Version 0.12.0-dev. Full test suite: 2450 tests passing, 1 skipped using `pytest --import-mode=importlib`.

MVP-12 Step 1 Review Index Models and Engine is complete.
- `src/hunter/review_index/__init__.py` — public API exports.
- `src/hunter/review_index/models.py` — review index models.
- `src/hunter/review_index/engine.py` — review index engine.
- `tests/test_review_index/__init__.py` — test package init.
- `tests/test_review_index/test_models.py` — 70 model tests.
- `tests/test_review_index/test_engine.py` — 97 engine tests.
- 166 review_index tests passing. 1 skipped INDEX_ERROR edge test.
- Full suite: 2377 tests passing, 1 skipped using `pytest --import-mode=importlib`.

MVP-12 Step 2 — Review Index Writer (Complete).
- `src/hunter/review_index/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/review_index/__init__.py` — updated with writer exports.
- `tests/test_review_index/test_writer.py` — 52 writer tests.
- Default JSON path: `data/review_index/latest_review_index.json`.
- Default Markdown path: `reports/review_index/latest_review_index.md`.
- 218 review_index tests total (166 model/engine + 52 writer). 1 skipped.
- Full suite: 2429 tests passing, 1 skipped using `pytest --import-mode=importlib`.

MVP-12 Step 3 — Review Index Integration Tests (Complete).
- `tests/test_review_index/test_integration.py` — 21 integration tests.
- `TestBuildReviewIndexToDict` — 9 tests.
- `TestBuildReviewIndexToMarkdown` — 5 tests.
- `TestBuildReviewIndexWrite` — 7 tests.
- 239 review_index tests total (166 model/engine + 52 writer + 21 integration). 1 skipped.
- Full suite: 2450 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- No source changes. No Web UI. No dashboard. No database persistence.

MVP-12 Step 4 — Final validation and version bump (Complete).
- Version bumped from 0.11.0-dev to 0.12.0-dev.
- `pyproject.toml` updated.
- `src/hunter/__init__.py` updated.
- Full suite: 2450 tests passing, 1 skipped. No regressions.

MVP-13 Step 1 — Review Search Models and Engine (Not Started).
- `src/hunter/review_search/__init__.py` — public API exports.
- `src/hunter/review_search/models.py` — frozen search dataclasses, enums, reason codes, forbidden search content detection.
- `src/hunter/review_search/engine.py` — in-memory search engine functions.
- `tests/test_review_search/__init__.py` — test package init.
- `tests/test_review_search/test_models.py` — model tests.
- `tests/test_review_search/test_engine.py` — engine tests.
- Target: ~120 tests.

MVP-13 Step 2 — Review Search Writer (Not Started).
- `src/hunter/review_search/writer.py` — JSON/Markdown serialization, atomic file writing.
- `tests/test_review_search/test_writer.py` — writer tests.
- Default JSON path: `data/review_search/latest_search_result.json`.
- Default Markdown path: `reports/review_search/latest_search_result.md`.
- Target: ~50 tests.

MVP-13 Step 3 — Review Search Integration Tests (Not Started).
- `tests/test_review_search/test_integration.py` — integration tests.
- Target: ~70 tests.

MVP-13 Step 4 — Final Review and Version Bump (Not Started).
- Verdict: PASS / PASS WITH NOTES / FAIL.
- If PASS: version bump to 0.13.0-dev.

## Scope

MVP-13 Step 1 — Review Search Models and Engine, not started.
- SPEC-014: Local Review Search / Query Layer.
- Approved with minor notes. Ready for implementation.

### Allowed
- `src/hunter/review_search/` package creation.
- `tests/test_review_search/` test package creation.
- `specs/SPEC-014-Local-Review-Search-Query-Layer.md` reference only.
- `src/hunter/review_index/models.py` import for `IndexEntry`, `ReviewIndex`, `IndexState`, `IndexEntryKind`, `IndexSafetyFlags`.
- No source code changes outside `src/hunter/review_search/`.
- No changes to `src/hunter/review_index/`.

### Not Allowed
- No changes to existing source code outside `src/hunter/review_search/`.
- No changes to existing tests outside `tests/test_review_search/`.
- No changes to `src/hunter/review_index/`.
- No config YAML, no JSON schema, no Freqtrade strategy class, no freqtrade import, no Freqtrade runtime connection, no Binance, no real exchange, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic, no production data reads/writes, no report feedback into execution paths, no operator feedback into execution paths, no index feedback into execution paths, no search feedback into execution paths, no Web UI, no dashboard, no database persistence.
- File references remain local strings only and must not be traversed/opened/followed/validated/executed.

## Previous Task

MVP-12 Step 4 — Final validation and version bump (Complete).
- Version bumped to 0.12.0-dev.
- Full suite: 2450 tests passing, 1 skipped.
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
- [ ] MVP-13 Step 1: review search models and engine, not started.
- [ ] MVP-13 Step 2: review search writer, not started.
- [ ] MVP-13 Step 3: review search integration tests, not started.
- [ ] MVP-13 Step 4: final review and version bump, not started.

## Next Step

MVP-13 Step 1 — Review Search Models and Engine. Ready for implementation.

Future review search integration tests or operator workflow UI may be considered only in a future SPEC, but is not implemented yet.
