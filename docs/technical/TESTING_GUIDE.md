# Testing Guide

> **Research only.** All commands below exercise local, deterministic test code. None start Freqtrade, place
> orders, or connect to any exchange/network.

Verified against commit `08a78d9`, version `0.72.0-dev`. All results in this guide were produced by actually
running the listed commands during this validation pass — see the parent validation report for the full
per-command log (exact command, exit code, duration, pass/fail/skip counts).

## Test Runner: Verified Fallback

This repo's `.venv` does **not** have `pytest` installed by default — `.venv/bin/python -m pytest` fails with
`No module named pytest`, and there is no `.venv/bin/pytest` binary until you install the `dev` extra. A
user-level `pytest` install (outside the project venv, e.g. `pip install --user pytest`) also works and is
used throughout this guide as `pytest`. It correctly picks up this repo's `pyproject.toml`
`[tool.pytest.ini_options]` (`pythonpath = ["src"]`, `testpaths = ["tests"]`) with no extra flags, as long as
you invoke it **from the repository root**.

If your environment differs, install the `dev` extra into `.venv` instead
(`.venv/bin/pip install -e ".[dev]"`) and use `.venv/bin/pytest`.

## Test Structure

```text
tests/
├── test_<package_name>/          # one directory per src/hunter/<package_name>
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_*.py                 # unit tests
│   └── test_integration.py       # end-to-end / cross-module tests, where present
```

Each `tests/test_<x>/` mirrors a `src/hunter/<x>/` package 1:1 (verified: 74 `src/hunter/` packages, matching
`tests/test_*` directories per `docs/MVP_INDEX.md`'s package-mapping table). The SPEC-074 surface's tests live
in `tests/test_pairlist_export/` (11 files: `test_audit.py`, `test_cli.py`, `test_deployment_profiles.py`,
`test_fingerprint.py`, `test_integration.py`, `test_models.py`, `test_publisher.py`,
`test_ranking_adapter.py`, `test_snapshot.py`, `test_validator.py`, `__init__.py`).

## Focused Test Commands

Run from the repository root:

```bash
pytest tests/test_pairlist_export -q
pytest tests/test_core -q
pytest tests/test_reporting_cli -q
pytest tests/test_relative_strength -q
pytest tests/test_open_interest -q
pytest tests/test_research_market_data -q
pytest tests/test_research_universe -q
pytest tests/test_research_backtest_comparison -q
pytest tests/test_research_walk_forward -q
pytest tests/test_research_statistical_confidence -q
pytest tests/test_research_evidence_ledger -q
pytest tests/test_research_campaign -q
```

All 12 passed cleanly at commit `08a78d9` (70, 19, 106, 129, 207, 91, 61, 364+1 skipped, 131, 180, 192, 268
tests respectively — see the validation report's Test Results table for exact durations/exit codes).

## Full-Suite Command

```bash
pytest tests/ -q
```

Result at commit `08a78d9`: **10,334 passed, 2 skipped, 10–11 warnings, exit code 0**, ~11.4s wall time. This
matches the count recorded in the MVP-71 commit message (`be854db`) exactly, confirming no regression across
the two trailing docs/test-`__init__.py` commits.

Two skips are explicit and always present, not environment failures:

- `tests/test_research_backtest_comparison/test_stage6_comparison.py:177` — `"placeholder row"`
- `tests/test_review_index/test_engine.py:917` — `"INDEX_ERROR for orphan reviews requires source
  modification"`

A third, conditional skip appears on most machines:

- `tests/test_pairlist_export/test_cli_feather.py:172` — `"real external Feather fixture not present on
  this machine"`. This test only runs if you point `_REAL_XRP_FIXTURE` at a real Freqtrade-produced
  `XRP_USDT_USDT-1h-futures.feather` file on your own machine; it is a local, opt-in smoke test, not part of
  the guaranteed suite.

The warnings are all either Python 3.14 `datetime.datetime.utcnow()` deprecation warnings inside test code
(not production `src/` code), one `ResourceWarning` for an unclosed file handle in a test's tmp-path fixture,
and one expected `UserWarning` from Python's `zipfile` module inside an adversarial "duplicate ZIP member"
test (`test_research_backtest_comparison/test_zip_safety.py`) — that warning is the test's intended trigger,
not a defect.

## CLI Tests

`tests/test_pairlist_export/test_cli.py` (11 tests) exercises every subcommand end-to-end via `tmp_path`
fixtures, including `test_output_dir_targeting_repo_data_tree_is_rejected`. `tests/test_reporting_cli/`
(106 tests across `test_cli.py`, `test_integration.py`, `test_models.py`) covers the legacy
`reporting_cli` surface that `hunter --help`/`version`/`safety-summary` fall through to.

## Adversarial / Security Tests

Identified by name/content grep for path-traversal, symlink, ZIP-safety, overwrite-protection,
failed-write-cleanup, secret-redaction, subprocess-boundary, no-retry, and no-parallelism assertions:

```bash
pytest -q \
  tests/test_audit_scorecard/test_integration.py \
  tests/test_cross_pack_consistency/test_writer.py \
  tests/test_human_review_audit_bundle_export/test_engine.py \
  tests/test_human_review_audit_bundle_export/test_integration.py \
  tests/test_human_review_audit_bundle_export/test_writer.py \
  tests/test_phase_b_scope_scan.py \
  tests/test_remediation_closure/test_writer.py \
  tests/test_remediation_evidence/test_writer.py \
  tests/test_reporting_cli/test_cli.py \
  tests/test_reporting_cli/test_integration.py \
  tests/test_reporting_cli/test_models.py \
  tests/test_research_audit_snapshot/test_integration.py \
  tests/test_research_audit_snapshot/test_models.py \
  tests/test_research_backtest_comparison/test_executable.py \
  tests/test_research_backtest_comparison/test_fixture_models.py \
  tests/test_research_backtest_comparison/test_fixture_validator.py \
  tests/test_research_backtest_comparison/test_result_locator.py \
  tests/test_research_backtest_comparison/test_validator.py \
  tests/test_research_backtest_comparison/test_workspace.py \
  tests/test_research_backtest_comparison/test_zip_safety.py \
  tests/test_research_campaign/test_adversarial.py \
  tests/test_research_campaign/test_models.py \
  tests/test_research_campaign/test_safety.py \
  tests/test_research_statistical_confidence/test_models.py \
  tests/test_research_statistical_confidence/test_safety.py \
  tests/test_research_statistical_confidence/test_writer.py \
  tests/test_research_universe/test_writer.py \
  tests/test_research_walk_forward/test_models.py \
  tests/test_research_walk_forward/test_writer.py
```

Result: **812 passed, 1 warning (the expected ZIP UserWarning above), exit 0**. See
`docs/architecture/THREAT_MODEL.md` for the full ZIP/subprocess/executable threat catalog these tests assert
against (13 ZIP reason codes, executable allowlisting, environment allowlisting, etc.).

## Deterministic / Snapshot Tests

`tests/test_pairlist_export/test_fingerprint.py` (7 tests) and `test_snapshot.py` (4 tests) assert
wall-clock-free fingerprinting and immutable-snapshot-conflict behavior directly. This was additionally
verified manually during this pass: running `hunter pairlist build` twice on byte-identical input produced a
byte-identical `hunter-pairs.json` and identical audit `fingerprint` field.

## Freqtrade Compatibility Tests

`tests/test_research_backtest_comparison/` (the MVP-65 suite, 364 passed + 1 skipped) exercises the
subprocess boundary against mocked/fixture executables — it does not require a real `freqtrade` install to
pass. Separately, this validation pass confirmed a real `freqtrade` executable on `PATH` (version
`2026.6-dev-3c293b78e`, verified via `freqtrade --version`, read-only). Running `freqtrade test-pairlist`
against Hunter's deployment profile was **NOT EXECUTED**: it
requires querying live exchange market data (even with a `RemotePairList` + native filters config, Freqtrade
needs real market/pair-listing data to evaluate `AgeFilter`/`DelistFilter`), which is prohibited by this
task's safety rules (no network, no exchange access). Treat `freqtrade test-pairlist` as a manual,
operator-run acceptance step outside this repo's automated test scope — see
`docs/operations/DEPLOYMENT_GUIDE.md`.

## Interpreting Skips and Warnings

- A skip with an explicit reason string (as both current skips have) is expected — do not "fix" it by
  deleting the skip unless you are also implementing the placeholder/source-modification it names.
- `DeprecationWarning: datetime.datetime.utcnow() is deprecated` warnings originate in **test** files
  (`test_governance_handoff/*.py`, `test_portfolio_risk_evaluator/*.py`, `test_controlled_universe/
  test_models.py`), not in `src/hunter/pairlist_export/` production code — informational only for the
  product surface this documentation covers.
- Any warning you don't recognize from this list is new since this validation pass — investigate before
  assuming it's benign.

## Pre-Commit Verification Checklist

1. `find src/hunter src/freqtrade_strategies -name "*.py" -not -path "*/__pycache__/*" -print0 | xargs -0
   .venv/bin/python -m py_compile` — must exit 0.
2. Focused suite(s) touching your change — must show `N passed` with no `failed`.
3. `pytest tests/ -q` — must show `passed`/`skipped` only, no `failed`, exit 0.
4. If you touched `pairlist_export/`, re-run the manual smoke sequence in
   `docs/technical/PAIRLIST_PIPELINE.md` §"Manual verification" against a scratch directory outside `data/`
   and `reports/`.
5. `git status --porcelain` — confirm no `data/`/`reports/` paths appear.

## Release Verification Checklist

See `docs/operations/RELEASE_CHECKLIST.md` for the full pre-tag checklist (version consistency, full suite,
CLI checks, documentation checks, pairlist acceptance, no forbidden files, no push).
