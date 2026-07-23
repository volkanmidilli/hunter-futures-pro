# SPEC-076-STATCONF-FINDINGS — Statistical Confidence Evidence Source

**Status:** Evidence source for SPEC-076 planning draft  
**Purpose:** Direct code evidence for every capability or limitation claim in the Statistical Confidence section of SPEC-076.  
**Source:** Direct inspection of `src/hunter/research_statistical_confidence/` and `tests/test_research_statistical_confidence/`. No claims are inferred from package or symbol names.

---

## 1. Package location

- **Implementation:** `src/hunter/research_statistical_confidence/`
- **Tests:** `tests/test_research_statistical_confidence/`
- **Spec:** `specs/SPEC-068-Walk-Forward-Statistical-Confidence.md`

## 2. Public API and input/output contracts

| File | Symbols | Evidence |
|---|---|---|
| `src/hunter/research_statistical_confidence/__init__.py:5-50` | `run_statistical_confidence`, `ExperimentConfidenceReport`, `StatisticalConfidenceConfig`, `BootstrapConfig`, `RobustnessCriteria`, `MetricConfidenceResult`, `RegimeConfidenceResult`, `ConfidenceState`, `StatisticalConfidenceSafetyFlags` | Exported public API |
| `src/hunter/research_statistical_confidence/engine.py:80-291` | `run_statistical_confidence(report, config)` | Consumes `WalkForwardExperimentReport` + `StatisticalConfidenceConfig`; returns `ExperimentConfidenceReport` |
| `src/hunter/research_statistical_confidence/models.py:203-266` | `BootstrapConfig`, `RobustnessCriteria`, `StatisticalConfidenceConfig` | Frozen input configuration models |
| `src/hunter/research_statistical_confidence/models.py:274-466` | `BootstrapInterval`, `LeaveOneOutResult`, `MetricConfidenceResult`, `RegimeConfidenceResult`, `StatisticalConfidenceManifest`, `ExperimentConfidenceReport` | Frozen output result models |

**Input contract:** `WalkForwardExperimentReport` (from `src/hunter/research_walk_forward/models.py`) with:
- `window_results: tuple[WalkForwardWindowResult, ...]`
- Each window result: `metric_deltas: dict[str, Decimal | None]`, `candidate_metrics`, `baseline_metrics`, `metric_directions`, `window` (with `regime_label`), `status`, `fingerprint`
- Inherited safety flags (`WalkForwardSafetyFlags`)

**Output contract:** `ExperimentConfidenceReport` with:
- `metric_results: dict[str, MetricConfidenceResult]` — per-metric descriptive stats, bootstrap CIs, LOO, confidence state
- `regime_results: dict[str, RegimeConfidenceResult]` — regime-stratified results
- `manifest`, `safety_flags`, `fingerprint`

## 3. Dependency-aware methods actually implemented

| File | Symbol | Capability | Evidence |
|---|---|---|---|
| `src/hunter/research_statistical_confidence/methodology.py:301-400` | `WindowDependencePolicy` | Detects selection/evaluation window overlaps via closed-interval comparison of YYYYMMDD boundaries. Returns `DependenceStatus` (NON_OVERLAPPING / OVERLAPPING / UNKNOWN), overlapping pair count, max overlap seconds. | Direct code and tests |
| `src/hunter/research_statistical_confidence/methodology.py:403-441` | `ResearchMethodologyPolicy` | Aggregates `WindowDependencePolicy` with other policies. | Direct code and tests |
| `src/hunter/research_statistical_confidence/methodology_engine.py` | `MethodologyValidationReport`, `build_methodology_validation_report` | Emits methodology validation artifacts. | Direct code and tests |

**Limitation:** `run_statistical_confidence` (engine.py:80-291) **does not** consume or adjust its statistical methods based on `DependenceStatus`. The core bootstrap and LOO treat all windows as independent samples. `WindowDependencePolicy` is a standalone validation function that flags overlaps but does not alter inference.

## 4. Repeated observations from overlapping cohorts

**Not supported.** No code in `src/hunter/research_statistical_confidence/` or `tests/test_research_statistical_confidence/` references 1d/3d/7d cohorts, horizons, or multi-horizon grouping. Each window contributes exactly one observation per metric. The iid bootstrap (`bootstrap.py:76-82`) samples each observation independently with replacement. LOO (`sensitivity.py:17-127`) removes one window at a time. Neither accounts for correlated/overlapping observations.

If evaluation windows overlap, `WindowDependencePolicy` will flag them, but the statistical engine still treats them as independent. No cluster-aware or horizon-aware resampling exists.

## 5. Supported statistical techniques

| Technique | Implemented? | Evidence | Notes |
|---|---|---|---|
| Descriptive statistics | ✅ | `descriptive.py:69-142` | Mean, median, std dev, MAD, min/max, q1/q3/IQR, sign shares |
| Percentile bootstrap CI | ✅ | `bootstrap.py:49-94` | Mean and median CIs; nearest-rank method; deterministic seed |
| BCa / bias-corrected accelerated bootstrap | ❌ | — | Not implemented |
| Studentized bootstrap | ❌ | — | Not implemented |
| Block bootstrap | ❌ | — | Not implemented |
| Cluster bootstrap | ❌ | — | Not implemented |
| Leave-one-out sensitivity | ✅ | `sensitivity.py:17-127` | Mean/median ranges, max influence ratio, sign stability |
| HAC / Newey-West | ❌ | — | Not implemented |
| Autocorrelation-consistent standard errors | ❌ | — | Not implemented |
| Significance testing (t-test, z-test) | ❌ | — | Not implemented |
| Quartile alignment (MVP-66/67) | ✅ | `methodology.py:160-199` | `QuartilePolicy` verifies median-of-halves alignment |
| Zero-dispersion detection | ✅ | `engine.py:130-141`, `classification.py:122-126` | Blocks `ROBUST_*` when std_dev == 0 or insufficient distinct values |

## 6. Minimum-sample behavior and failure modes

| File | Behavior | Evidence |
|---|---|---|
| `validator.py:39-43` | `minimum_available_window_count >= 2` | Hard validation error |
| `validator.py:61-65` | `bootstrap.iterations >= 100` | Hard validation error |
| `bootstrap.py:66-69` | Bootstrap requires `max(3, minimum_available_window_count)` available values | Returns `(None, None)` below threshold |
| `sensitivity.py:43-46` | LOO requires at least 2 available values | Returns `None` below threshold |
| `classification.py:69-72` | `available_count < minimum_available_window_count` → `INSUFFICIENT_EVIDENCE` | Fail-closed |
| `classification.py:99-106` | `loo is None` or `sign_stable=False` → `UNSTABLE` | Fail-closed |
| `classification.py:78-86` | Direction conflict or weak sign share → `MIXED` | Fail-closed |
| `engine.py:130-141` | Zero observed dispersion or insufficient distinct values blocks `ROBUST_*` | SPEC-072 fail-closed rule |

## 7. Safe evaluation of SPEC-076 metrics

| Metric | Safe? | Explanation | Evidence |
|---|---|---|---|
| **Top-N returns** | ✅ Descriptive only | Can be processed as generic `metric_deltas` if pre-computed. The engine evaluates any `Decimal` delta per window. Overlapping cohorts violate iid assumptions, so only descriptive point estimates are valid. | `engine.py:107-183` processes any `metric_deltas` key |
| **Spearman(rank, return)** | ⚠️ Requires adapter | Not computed natively. If pre-computed per window and provided as a metric delta, it can be processed like any other delta. For overlapping cohorts, descriptive only. | No Spearman code exists in package or tests |
| **Spearman(score, return)** | ⚠️ Requires adapter | Same as above. Pre-computation required. | No Spearman code exists in package or tests |
| **Benchmark-relative returns** | ✅ Descriptive only | Can be provided as `metric_deltas` (e.g., `return_pct - benchmark_return_pct`). Processed as generic deltas. Overlapping cohorts → descriptive only. | `engine.py:107-183` processes any `metric_deltas` key |

## 8. Reuse requirements

| Metric | Reuse path |
|---|---|
| Top-N returns | **Adapter only** — pre-compute `metric_deltas` in `WalkForwardExperimentReport` |
| Benchmark-relative returns | **Adapter only** — pre-compute deltas |
| Spearman correlations | **Adapter only** — pre-compute per-window Spearman and inject as `metric_deltas`. The engine treats it as a scalar metric. No engine modification needed if the adapter provides the delta. |
| Overlapping cohorts | **Not supported** for inferential output. Existing engine lacks cluster/bootstrap-aware methods. Use descriptive point estimates only. No new statistical engine in Phase A. |

## 9. Traceability note

Every capability claim in the Statistical Confidence section of SPEC-076 must trace back to this findings document. Where a capability is not listed here, it is not confirmed by code and tests and must not be claimed.
