# SPEC-065 — Dual Universe Builder

**Status:** Approved
**MVP:** MVP-64
**Version target:** `v0.64.0-dev`
**Upstream dependencies:** MVP-63 `Research Market Data CSV Loader and Adapter`, MVP-51 `Controlled Universe Bridge Engine`, MVP-57 `Portfolio Construction Research Adapter`, MVP-55 `Freqtrade Universe Consumption Adapter`

## Background

The research pipeline now produces a deterministic `ResearchMarketDataBundle` (MVP-63), a `ControlledUniverseReport` (MVP-51), and a `PortfolioConstructionReport` (MVP-57). MVP-64 introduces a Dual Universe Builder that consumes these artifacts to produce two parallel, research-only universes:

- **Candidate Universe**: derived from the controlled universe and portfolio construction outputs, using the existing Hunter research engines (relative strength, discovery, portfolio construction, controlled universe, export adapter, and Freqtrade adapter).
- **Baseline Universe**: derived directly from the market data bundle using only quote-volume ranking, with no portfolio construction or controlled universe logic.

The two universes are compared deterministically to produce overlap, candidate-only, baseline-only, and Jaccard similarity metrics. All outputs are research-only artifacts with explicit safety flags and human-approval requirements.

```text
ResearchMarketDataBundle ──────► BaselineUniverseResult
                                       │
ControlledUniverseReport ──────┐       │
                               ▼       ▼
PortfolioConstructionReport ─► CandidateUniverseResult
                                       │
                                       ▼
                           ResearchUniverseComparison
                                       │
                                       ▼
                           ResearchUniverseReport
                                       │
                                       ▼
                           JSON / Markdown artifacts + manifest
```

## Requirements

### Must Have

- frozen dataclasses for `CandidateUniverseResult`, `BaselineUniverseResult`, `UniversePairDecision`, `UniverseSelectionWindow`, `ResearchUniverseComparison`, `ResearchUniverseConfig`, `ResearchUniverseReport`, and `ResearchUniverseSafetyFlags`
- deterministic SHA-256 fingerprints for the candidate universe, baseline universe, and comparison
- candidate universe built from `ControlledUniverseReport` and `PortfolioConstructionReport` only
- baseline universe built from `ResearchMarketDataBundle` using only quote-volume ranking
- shared eligibility policy applied to both universes (minimum coverage, required quote currency, blocked symbols, top-N limits)
- deterministic pair ordering: candidate by portfolio weight, baseline by descending quote volume
- fail-closed behavior when inputs are invalid or all pairs are excluded
- explicit reason codes on every decision and on the final report
- comparison output: overlap, candidate-only, baseline-only, union count, Jaccard similarity, coverage and data-quality metrics
- safety flags hard-coded to research-only: `live_trading_allowed=False`, `automatic_execution_allowed=False`, `human_approval_required=True`, `research_only=True`
- deterministic JSON and Markdown artifacts with a safety notice and no absolute paths
- atomic file writes with silent-overwrite protection and failed-write cleanup
- manifest pointing to the report with a deterministic fingerprint

### Should Have

- configurable `max_candidate_pairs` and `max_baseline_pairs`
- configurable `minimum_coverage` and `required_quote_currency`
- configurable `blocked_symbols` and exclusion reason codes
- stable sort for deterministic ordering regardless of input order
- exclusion log in both candidate and baseline results
- support for `allowed_pair` and `blocked_pair` validation
- integration tests proving invariance to window-postfix candles and price changes
- all public writer outputs preserve `research_only`, `human_approval_required`, and safety flags

### Won’t Have

- Freqtrade runtime integration or strategy changes
- automatic Freqtrade configuration mutation
- exchange, API, server, database, or scheduler behavior
- live trading, orders, or execution instructions
- production or execution approval
- Open Interest synthesis or fabrication in the baseline
- reliance on price action in the candidate (uses portfolio construction scores)

## Method

### Package Layout

```text
src/hunter/research_universe/
├── __init__.py
├── models.py
├── eligibility.py
├── candidate.py
├── baseline.py
├── comparison.py
├── engine.py
├── validator.py
├── writer.py
```

### Candidate Universe

1. Validate `ControlledUniverseReport` and `PortfolioConstructionReport` with the existing `ResearchUniverseValidator`.
2. Select `PortfolioConstructionScore` entries whose symbol is present in the controlled universe whitelist.
3. Sort by descending `final_weight_pct` and apply `max_candidate_pairs`.
4. Build a `UniversePairDecision` for each included pair with state `CANDIDATE` and classification `RESEARCH_CANDIDATE`.
5. Compute a deterministic fingerprint from the sorted pair list and policy window.
6. Apply eligibility policy (coverage, quote currency, blocked symbols) to produce exclusion decisions with reason codes.

### Baseline Universe

1. Validate `ResearchMarketDataBundle` and `UniverseSelectionWindow`.
2. For each series in the bundle, compute average quote volume over the selection window using `close * volume`.
3. Sort pairs by descending average quote volume and apply `max_baseline_pairs`.
4. Build a `UniversePairDecision` for each included pair with state `BASELINE` and classification `RESEARCH_BASELINE`.
5. Compute a deterministic fingerprint from the sorted pair list and policy window.
6. Apply eligibility policy (minimum coverage, quote currency, blocked symbols) to produce exclusion decisions with reason codes.

### Comparison

1. Compute overlap, candidate-only, baseline-only, union count, and Jaccard similarity.
2. Derive overall safety flags from the logical AND of candidate and baseline safety flags plus `live_trading_allowed=False`.
3. Record reason codes for any mismatch.
4. Compute a deterministic fingerprint from the union of pair identifiers and overlap.

### Writer

1. `write_candidate_json` / `write_candidate_markdown`
2. `write_baseline_json` / `write_baseline_markdown`
3. `write_comparison_json` / `write_comparison_markdown`
4. `write_report` — top-level `ResearchUniverseReport`
5. `write_manifest` — small manifest with relative report path, fingerprint, version, and safety notice

All JSON outputs use `sort_keys=True`, explicit indentation, and a safety notice. File writes are atomic via `tempfile.NamedTemporaryFile` + `os.replace`. If the target exists and `overwrite=False`, a `ResearchUniverseWriterError` is raised and no temporary file is left behind.

## Acceptance Criteria

1. `CandidateUniverseResult` and `BaselineUniverseResult` are frozen and JSON-serializable through the writer.
2. Candidate fingerprints change when the controlled universe or portfolio weights change; they do not change when only market price changes after the window.
3. Baseline fingerprints change when volume changes within the window; they do not change when high-volume candles are appended after the window.
4. Comparison overlap and Jaccard metrics are deterministic and exact.
5. All writer outputs contain `research_only=True`, `human_approval_required=True`, and safety flags with `live_trading_allowed=False`.
6. No silent overwrites: writing twice without `overwrite=True` raises `ResearchUniverseWriterError`.
7. Failed atomic writes leave no `.tmp` files behind.
8. Manifest contains only relative paths and includes a safety notice.
9. Source CSV candle files and `data/` / `reports/` directories are not modified by tests or engine.
10. Full test suite passes with the new module and all upstream regression tests.

## Safety Notes

- This MVP is research-only. It does not touch Freqtrade, exchanges, wallets, databases, or live trading.
- Human approval is required before any runtime use of the generated artifacts.
- The baseline universe is intentionally price-action-free and uses only quote volume to provide a stable reference.
- The candidate universe is intentionally independent of post-window price changes to isolate model-driven selection from market drift.

## Version

Target release: `v0.64.0-dev`
