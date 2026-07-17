# SPEC-070 — Research Campaign Compiler and Batch Orchestrator

**Status:** Closed  
**MVP:** MVP-69 (Compiler) / MVP-70 (Batch Orchestrator)  
**Version target:** `v0.70.0-dev`  
**Source package:** `src/hunter/research_campaign/`  
**Test package:** `tests/test_research_campaign/`  

## Scope

A research-only, deterministic campaign compilation and controlled batch experiment orchestration system that consumes caller-provided strategy references, historical data references, universe plans, walk-forward templates, and statistical-confidence configurations; compiles an explicit Cartesian product of experiments; validates, filters, and deduplicates the campaign; and executes experiments sequentially with deterministic fingerprints, resume/reuse policies, checkpoints, and a final dossier writer.

## Input boundary

The package consumes only:

- `WalkForwardCommonConfig` from MVP-66 (immutable)
- `WalkForwardExperimentPlan` / `WalkForwardExperimentReport` from MVP-66 (immutable)
- `StatisticalConfidenceConfig` / `ExperimentConfidenceReport` from MVP-67 (immutable)
- `EvidenceLedgerEntry` / `LedgerSnapshot` / `ExperimentRegistration` from MVP-68 (immutable)

No new market data, backtest execution, Freqtrade invocation, or live subprocess is used by the orchestrator itself. Downstream integration adapters may invoke pre-existing MVP-65 backtest code only through explicit, caller-provided adapters.

## Public models

- `ResearchCampaignSafetyFlags` — hard-coded research-only safety invariants
- `CampaignExecutionPolicy` — `COLLECT_ALL`, `FAIL_FAST`, `STOP_AFTER_N_FAILURES`
- `ResumePolicy` — `REUSE`, `RERUN`, `BLOCK`
- `CampaignStatus` — `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `STOPPED`
- `ExperimentOutcome` — `COMPLETED`, `FAILED`, `BLOCKED`, `TIMED_OUT`, `UNSUPPORTED`, `INSUFFICIENT_EVIDENCE`, `WITHDRAWN`, `SKIPPED_BY_POLICY`, `STALE_RESUME_EVIDENCE`
- `StrategyReference`, `HistoricalDataReference`, `UniversePlanReference`, `WalkForwardTemplateReference`, `StatisticalConfidenceConfigReference`
- `CampaignFilterRule` — declarative include/exclude rules with `EQUALS`, `NOT_EQUALS`, `IN`, `NOT_IN`, `PREFIX`, `MATCH_ALL`
- `CampaignParameterSet` — explicit, immutable parameter matrix
- `ResearchCampaignDefinition` — explicit campaign definition with max experiment count and execution policy
- `CompiledExperiment` — single compiled experiment in the campaign matrix
- `CompiledCampaign` — immutable compiled campaign matrix with deterministic fingerprint
- `CampaignRegistrationSet` — pre-registration records with coherence checks
- `CampaignExecutionManifest` — deterministic manifest for execution
- `ExperimentEvidence` / `ExperimentExecutionRecord` / `CampaignCheckpoint`
- `PriorExperimentEvidence` / `CampaignResumeManifest` — deterministic resume
- `CampaignStatusSummary` / `CampaignEvidenceSummary` / `CampaignDossier` / `CampaignArtifactManifest`

All models are frozen and carry hard-coded research-only safety flags.

## Compilation

- Explicit Cartesian-product expansion of all parameter tuples.
- Include/exclude filter rules are applied deterministically.
- Duplicate logical experiments are detected and removed.
- `max_experiment_count` is enforced; zero-experiment campaigns are rejected.
- Deterministic SHA-256 fingerprints exclude paths, timestamps, durations, PID, hostname, and insertion order.

## Execution

- Sequential runner with no parallel execution.
- `COLLECT_ALL`, `FAIL_FAST`, and `STOP_AFTER_N_FAILURES` policies.
- `REUSE`, `RERUN`, and `BLOCK` resume policies for stale or missing prior evidence.
- Resume matching requires all 11 reference fingerprints plus inherited safety invariants and the ledger snapshot fingerprint.
- Atomic checkpoints written after each experiment attempt.
- Final deterministic dossier and artifact manifest.

## Writer

- Explicit-output-directory deterministic JSON/Markdown writers.
- Silent-overwrite protection, failed-write cleanup, and atomic replace.
- Rejects output under `data/` or `reports/`.
- Redaction and safety notice embedded in every artifact.

## Safety invariants

- No direct subprocess, no parallel execution, no live/dry-run trading.
- No exchange/API/network/data access, no data download.
- No tracked config/strategy/universe mutation.
- No `data/` or `reports/` access, no push, no remote changes.
- No execution/production/live approval.
- Human approval required for any downstream action.

## Closure

- MVP-70 closed with version `0.70.0-dev`.
- Local annotated tag `v0.70.0-dev` created; historical tag `v0.69.0-dev` preserved at `e826936`.
- `tests/test_research_campaign/test_py_compile.py` added for deterministic source/test byte-compile verification.
