"""In-memory engine for hunter.experiment_ledger package.

MVP-31 — Local Research Experiment Ledger.

The engine consumes already-loaded in-memory research artifacts and produces a
deterministic, local, human-audit comparison ledger. It never reads files,
follows paths, calls networks, accesses exchanges, starts servers, schedulers,
daemons, or databases, and never emits trading or execution commands.

All metadata and file-reference strings are opaque local strings. The engine
never opens, follows, traverses, validates, fetches, or executes them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
from types import MappingProxyType
from typing import Any

from hunter.backtest import BacktestReport
from hunter.experiment_ledger.models import (
    BACKTEST_SOURCE_KIND,
    BASELINE_MISSING,
    COMPARABLE_METRICS,
    DUPLICATE_ID,
    EXPERIMENT_LEDGER_VERSION,
    EXPERIMENT_LEDGER_BLOCKING_REASON_CODES,
    EXPERIMENT_LEDGER_REASON_CODES,
    HUMAN_RESEARCH_ONLY,
    INVALID_METRICS,
    METRIC_SNAPSHOT_SOURCE_KIND,
    MISSING_REQUIRED_FIELDS,
    NOT_TRADING_ADVICE,
    NO_ACTION_COMMANDS_EMITTED,
    NO_DATABASE,
    NO_DAEMON,
    NO_EXCHANGE_CONNECTION,
    NO_FILE_INGESTION,
    NO_FREQTRADE_INPUT,
    NO_NETWORK_CONNECTION,
    NO_SCHEDULER,
    NO_WEB_UI,
    OK,
    RESEARCH_ONLY,
    RUN_RESULT_METRICS,
    RUN_SOURCE_KIND,
    UNSAFE_CONTENT,
    ExperimentComparisonConfig,
    ExperimentComparisonResult,
    ExperimentLedgerDataQuality,
    ExperimentLedgerInput,
    ExperimentLedgerReport,
    ExperimentLedgerSafetyFlags,
    ExperimentMetricSnapshot,
    ExperimentRecord,
    ExperimentReasonCode,
    ExperimentState,
    FORBIDDEN_EXPERIMENT_LEDGER_TERMS,
)
from hunter.run_orchestrator import ResearchRunResult


# ---------------------------------------------------------------------------
# Safety helpers
# ---------------------------------------------------------------------------


def has_unsafe_experiment_ledger_content(
    text: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    tags: Sequence[str] | None = None,
    forbidden_terms: frozenset[str] | None = None,
) -> bool:
    """Return True if text, tags, or metadata contain forbidden ledger terms.

    Scans only the caller-provided string values. Metadata/file-reference
    strings are opaque local strings and are never opened, followed, traversed,
    validated, fetched, or executed.
    """
    terms = forbidden_terms or FORBIDDEN_EXPERIMENT_LEDGER_TERMS
    if text is not None and _has_forbidden_term(text, terms):
        return True
    if tags is not None:
        for tag in tags:
            if isinstance(tag, str) and _has_forbidden_term(tag, terms):
                return True
    if metadata is not None and _check_forbidden_mapping(metadata, terms):
        return True
    return False


def _has_forbidden_term(text: str, forbidden_terms: frozenset[str]) -> bool:
    """Case-insensitive substring check for forbidden terms in a single string."""
    if not isinstance(text, str):
        return False
    lower = text.lower()
    return any(term in lower for term in forbidden_terms)


def _check_forbidden_mapping(
    mapping: Mapping[str, Any], forbidden_terms: frozenset[str]
) -> bool:
    """Return True if any key or string value in mapping contains forbidden terms."""
    for key, value in mapping.items():
        if isinstance(key, str) and _has_forbidden_term(key, forbidden_terms):
            return True
        if isinstance(value, str) and _has_forbidden_term(value, forbidden_terms):
            return True
        if isinstance(value, (tuple, list)):
            for item in value:
                if isinstance(item, str) and _has_forbidden_term(item, forbidden_terms):
                    return True
        if isinstance(value, Mapping):
            if _check_forbidden_mapping(value, forbidden_terms):
                return True
    return False


def build_experiment_ledger_safety_flags(
    *,
    has_unsafe_content: bool = False,
    has_invalid_record: bool = False,
    has_blocked_record: bool = False,
    has_insufficient_data: bool = False,
    has_missing_baseline: bool = False,
) -> ExperimentLedgerSafetyFlags:
    """Build ledger safety flags with observed negative states."""
    return ExperimentLedgerSafetyFlags(
        has_unsafe_content=has_unsafe_content,
        has_invalid_record=has_invalid_record,
        has_blocked_record=has_blocked_record,
        has_insufficient_data=has_insufficient_data,
        has_missing_baseline=has_missing_baseline,
    )


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def build_experiment_ledger_report(
    input: ExperimentLedgerInput,
    config: ExperimentComparisonConfig | None = None,
) -> ExperimentLedgerReport:
    """Build a deterministic experiment ledger report from in-memory inputs.

    The engine never reads files, follows paths, calls networks, accesses
    exchanges, or emits trading/execution commands. All inputs are caller-
    provided in-memory objects.
    """
    if config is None:
        config = ExperimentComparisonConfig()

    generated_at = _resolve_generated_at(input, config)

    # Input-level unsafe content check on opaque metadata only.
    if has_unsafe_experiment_ledger_content(metadata=input.metadata):
        return ExperimentLedgerReport.blocked(
            input=input,
            reason_code=UNSAFE_CONTENT,
            generated_at=generated_at,
            notes=(
                "Ledger report blocked due to unsafe content in input metadata.",
                "Experiment ledger output is for human audit only and is not a "
                "trading signal, recommendation, or approval.",
            ),
        )

    # Normalize each input into an ExperimentRecord.
    records: list[ExperimentRecord] = []
    for report in input.backtest_reports:
        record = _normalize_backtest_report(report, input, generated_at)
        records.append(record)
    for result in input.run_results:
        record = _normalize_run_result(result, input, generated_at)
        records.append(record)
    for snapshot in input.metric_snapshots:
        record = _normalize_metric_snapshot(snapshot, input, generated_at)
        records.append(record)

    # Detect duplicate experiment_id values deterministically.
    records = list(_detect_duplicate_records(records))

    # Sort normalized records deterministically.
    records = _sort_records(records)

    # Build comparison: baseline, deltas, ranking, summary.
    comparison = _build_comparison(records, config)

    # Build data quality and safety flags.
    data_quality = _build_data_quality(records, input)
    safety_flags = _build_safety_flags(records, comparison)

    # Aggregate reason codes.
    reason_codes = _aggregate_reason_codes(records, comparison)

    notes = (
        "Experiment ledger output is for human audit only.",
        "This is not a trading signal or recommendation.",
    )

    report_id = _deterministic_report_id(input, generated_at)

    return ExperimentLedgerReport(
        report_id=report_id,
        version=EXPERIMENT_LEDGER_VERSION,
        generated_at=generated_at,
        input=input,
        comparison=comparison,
        data_quality=data_quality,
        safety_flags=safety_flags,
        reason_codes=reason_codes,
        metadata=_coerce_str_mapping(input.metadata),
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _resolve_generated_at(
    input: ExperimentLedgerInput, config: ExperimentComparisonConfig
) -> datetime:
    """Resolve the ledger timestamp deterministically."""
    if config.generated_at is not None:
        return config.generated_at
    if input.generated_at is not None:
        return input.generated_at
    return datetime.now(timezone.utc)


def _deterministic_report_id(input: ExperimentLedgerInput, generated_at: datetime) -> str:
    """Generate a deterministic report identifier from input summary."""
    data = (
        f"ledger:{generated_at.isoformat()}:"
        f"{len(input.backtest_reports)}:"
        f"{len(input.run_results)}:"
        f"{len(input.metric_snapshots)}"
    )
    return sha256(data.encode("utf-8")).hexdigest()[:16]


def _normalize_backtest_report(
    report: BacktestReport,
    input: ExperimentLedgerInput,
    default_generated_at: datetime,
) -> ExperimentRecord:
    """Normalize a BacktestReport into an ExperimentRecord."""
    source_id = report.report_id
    experiment_id = source_id
    run_id = source_id
    source_kind = BACKTEST_SOURCE_KIND
    name = _resolve_display_name(source_id, input)

    tags: tuple[str, ...] = ()
    metadata = _coerce_str_mapping(report.metadata)
    generated_at = report.generated_at or default_generated_at

    if not all((experiment_id, run_id, name)):
        return ExperimentRecord.blocked(
            experiment_id=experiment_id or "blocked",
            run_id=run_id or "blocked",
            name=name or "blocked",
            source_kind=source_kind,
            reason_codes=(MISSING_REQUIRED_FIELDS,),
            generated_at=generated_at,
            tags=tags,
            metadata=metadata,
            notes=("Blocked: missing required fields after normalization.",),
        )

    if has_unsafe_experiment_ledger_content(
        text=source_id, metadata=metadata, tags=tags
    ):
        return ExperimentRecord.blocked(
            experiment_id=experiment_id,
            run_id=run_id,
            name=name,
            source_kind=source_kind,
            reason_codes=(UNSAFE_CONTENT,),
            generated_at=generated_at,
            tags=tags,
            metadata=metadata,
            notes=("Blocked: unsafe content detected.",),
        )

    metrics = _extract_backtest_metrics(report)
    if _has_invalid_metrics(metrics):
        return ExperimentRecord.blocked(
            experiment_id=experiment_id,
            run_id=run_id,
            name=name,
            source_kind=source_kind,
            reason_codes=(INVALID_METRICS,),
            generated_at=generated_at,
            metrics=metrics,
            tags=tags,
            metadata=metadata,
            notes=("Blocked: invalid metric values detected.",),
        )

    state, reason_codes = _determine_state(metrics, COMPARABLE_METRICS)
    notes = ("Backtest report normalized for audit review.",)
    if state is ExperimentState.INSUFFICIENT_DATA:
        notes = ("Insufficient data: some comparable metrics are missing.",)

    return ExperimentRecord(
        experiment_id=experiment_id,
        source_kind=source_kind,
        run_id=run_id,
        name=name,
        state=state,
        reason_codes=reason_codes,
        metrics=metrics,
        generated_at=generated_at,
        tags=tags,
        metadata=metadata,
        notes=notes,
    )


def _normalize_run_result(
    result: ResearchRunResult,
    input: ExperimentLedgerInput,
    default_generated_at: datetime,
) -> ExperimentRecord:
    """Normalize a ResearchRunResult into an ExperimentRecord."""
    source_id = result.run_id
    experiment_id = source_id
    run_id = source_id
    source_kind = RUN_SOURCE_KIND
    name = _resolve_display_name(source_id, input)

    tags: tuple[str, ...] = ()
    metadata = _coerce_str_mapping(result.metadata)
    generated_at = result.generated_at or default_generated_at

    if not all((experiment_id, run_id, name)):
        return ExperimentRecord.blocked(
            experiment_id=experiment_id or "blocked",
            run_id=run_id or "blocked",
            name=name or "blocked",
            source_kind=source_kind,
            reason_codes=(MISSING_REQUIRED_FIELDS,),
            generated_at=generated_at,
            tags=tags,
            metadata=metadata,
            notes=("Blocked: missing required fields after normalization.",),
        )

    if has_unsafe_experiment_ledger_content(
        text=source_id, metadata=metadata, tags=tags
    ):
        return ExperimentRecord.blocked(
            experiment_id=experiment_id,
            run_id=run_id,
            name=name,
            source_kind=source_kind,
            reason_codes=(UNSAFE_CONTENT,),
            generated_at=generated_at,
            tags=tags,
            metadata=metadata,
            notes=("Blocked: unsafe content detected.",),
        )

    metrics = _extract_run_metrics(result)
    if _has_invalid_metrics(metrics):
        return ExperimentRecord.blocked(
            experiment_id=experiment_id,
            run_id=run_id,
            name=name,
            source_kind=source_kind,
            reason_codes=(INVALID_METRICS,),
            generated_at=generated_at,
            metrics=metrics,
            tags=tags,
            metadata=metadata,
            notes=("Blocked: invalid metric values detected.",),
        )

    state, reason_codes = _determine_state(metrics, RUN_RESULT_METRICS)
    notes = ("Research run result normalized for audit review.",)
    if state is ExperimentState.INSUFFICIENT_DATA:
        notes = ("Insufficient data: some run metrics are missing.",)

    return ExperimentRecord(
        experiment_id=experiment_id,
        source_kind=source_kind,
        run_id=run_id,
        name=name,
        state=state,
        reason_codes=reason_codes,
        metrics=metrics,
        generated_at=generated_at,
        tags=tags,
        metadata=metadata,
        notes=notes,
    )


def _normalize_metric_snapshot(
    snapshot: ExperimentMetricSnapshot,
    input: ExperimentLedgerInput,
    default_generated_at: datetime,
) -> ExperimentRecord:
    """Normalize an ExperimentMetricSnapshot into an ExperimentRecord."""
    experiment_id = snapshot.experiment_id
    run_id = snapshot.run_id if snapshot.run_id else experiment_id
    source_kind = METRIC_SNAPSHOT_SOURCE_KIND
    name = _resolve_display_name(experiment_id, input)
    if name == experiment_id:
        name = snapshot.name

    tags = snapshot.tags
    metadata = _coerce_str_mapping(snapshot.metadata)
    generated_at = snapshot.generated_at or default_generated_at

    if not all((experiment_id, run_id, name)):
        return ExperimentRecord.blocked(
            experiment_id=experiment_id or "blocked",
            run_id=run_id or "blocked",
            name=name or "blocked",
            source_kind=source_kind,
            reason_codes=(MISSING_REQUIRED_FIELDS,),
            generated_at=generated_at,
            tags=tags,
            metadata=metadata,
            notes=("Blocked: missing required fields after normalization.",),
        )

    if has_unsafe_experiment_ledger_content(
        text=experiment_id, metadata=metadata, tags=tags
    ) or has_unsafe_experiment_ledger_content(text=name, metadata={}, tags=tags):
        return ExperimentRecord.blocked(
            experiment_id=experiment_id,
            run_id=run_id,
            name=name,
            source_kind=source_kind,
            reason_codes=(UNSAFE_CONTENT,),
            generated_at=generated_at,
            tags=tags,
            metadata=metadata,
            notes=("Blocked: unsafe content detected.",),
        )

    metrics = _coerce_metrics(snapshot.metrics)
    if _has_invalid_metrics(metrics):
        return ExperimentRecord.blocked(
            experiment_id=experiment_id,
            run_id=run_id,
            name=name,
            source_kind=source_kind,
            reason_codes=(INVALID_METRICS,),
            generated_at=generated_at,
            metrics=metrics,
            tags=tags,
            metadata=metadata,
            notes=("Blocked: invalid metric values detected.",),
        )

    state, reason_codes = _determine_state(metrics, COMPARABLE_METRICS, require_all=False)
    notes = ("Metric snapshot normalized for audit review.",)
    if state is ExperimentState.INSUFFICIENT_DATA:
        notes = ("Insufficient data: metric snapshot contains no comparable metrics.",)

    return ExperimentRecord(
        experiment_id=experiment_id,
        source_kind=source_kind,
        run_id=run_id,
        name=name,
        state=state,
        reason_codes=reason_codes,
        metrics=metrics,
        generated_at=generated_at,
        tags=tags,
        metadata=metadata,
        notes=notes,
    )


def _resolve_display_name(source_id: str, input: ExperimentLedgerInput) -> str:
    """Return an explicit display name from metadata or the source id."""
    display_name = input.metadata.get(source_id)
    if isinstance(display_name, str) and display_name:
        return display_name
    return source_id


def _extract_backtest_metrics(report: BacktestReport) -> Mapping[str, float | int | None]:
    """Extract comparable metrics from a BacktestReport."""
    portfolio = report.portfolio_result
    data_quality = report.data_quality
    metrics: dict[str, float | int | None] = {
        "total_return_pct": portfolio.total_return_pct,
        "max_drawdown_pct": portfolio.max_drawdown_pct,
        "volatility_pct": portfolio.volatility_pct,
        "win_rate_pct": portfolio.win_rate_pct,
        "observation_count": portfolio.observation_count,
        "missing_data_count": portfolio.missing_data_count,
        "blocked_count": portfolio.blocked_count,
        "insufficient_data_count": portfolio.insufficient_data_count,
    }
    if data_quality.observation_count:
        metrics["observation_count"] = data_quality.observation_count
    if data_quality.missing_data_count:
        metrics["missing_data_count"] = data_quality.missing_data_count
    if data_quality.blocked_count:
        metrics["blocked_count"] = data_quality.blocked_count
    if data_quality.insufficient_data_count:
        metrics["insufficient_data_count"] = data_quality.insufficient_data_count
    return MappingProxyType(metrics)


def _extract_run_metrics(result: ResearchRunResult) -> Mapping[str, float | int | None]:
    """Extract run summary metrics from a ResearchRunResult."""
    dq = result.data_quality
    metrics: dict[str, float | int | None] = {
        "total_steps": dq.total_steps,
        "successful_steps": dq.successful_steps,
        "failed_steps": dq.failed_steps,
        "blocked_steps": dq.blocked_steps,
        "skipped_steps": dq.skipped_steps,
    }
    return MappingProxyType(metrics)


def _coerce_metrics(
    metrics: Mapping[str, Any]
) -> Mapping[str, float | int | None]:
    """Coerce snapshot metrics into a normalized mapping of numeric values."""
    coerced: dict[str, float | int | None] = {}
    for key, value in metrics.items():
        if isinstance(key, str) and _has_forbidden_term(key, FORBIDDEN_EXPERIMENT_LEDGER_TERMS):
            continue
        if value is None or isinstance(value, (int, float)):
            coerced[key] = value
        else:
            coerced[key] = value
    return MappingProxyType(coerced)


def _has_invalid_metrics(metrics: Mapping[str, Any]) -> bool:
    """Return True if any metric value is non-numeric, NaN, or infinite."""
    import math

    for value in metrics.values():
        if value is None:
            continue
        if isinstance(value, bool):
            return True
        if isinstance(value, (int, float)):
            if math.isnan(value) or math.isinf(value):
                return True
        else:
            return True
    return False


def _determine_state(
    metrics: Mapping[str, Any],
    required_metrics: tuple[str, ...],
    *,
    require_all: bool = True,
) -> tuple[ExperimentState, tuple[str, ...]]:
    """Determine record state and reason codes based on metric completeness.

    When require_all is True, every required metric must be present for INCLUDED.
    When False, at least one required metric must be present.
    """
    present = [m for m in required_metrics if metrics.get(m) is not None]
    if not present:
        return (ExperimentState.INSUFFICIENT_DATA, ())
    if require_all and len(present) != len(required_metrics):
        return (ExperimentState.INSUFFICIENT_DATA, ())
    return (ExperimentState.INCLUDED, (OK,))


def _detect_duplicate_records(
    records: Sequence[ExperimentRecord]
) -> tuple[ExperimentRecord, ...]:
    """Mark duplicate experiment_id records as BLOCKED with DUPLICATE_ID."""
    seen: set[str] = set()
    updated: list[ExperimentRecord] = []
    for record in records:
        if record.experiment_id in seen:
            new_reasons = tuple(dict.fromkeys((*record.reason_codes, DUPLICATE_ID)))
            updated.append(
                ExperimentRecord(
                    experiment_id=record.experiment_id,
                    source_kind=record.source_kind,
                    run_id=record.run_id,
                    name=record.name,
                    state=ExperimentState.BLOCKED,
                    reason_codes=new_reasons,
                    metrics=record.metrics,
                    generated_at=record.generated_at,
                    tags=record.tags,
                    metadata=record.metadata,
                    notes=(*record.notes, "Blocked: duplicate experiment_id."),
                )
            )
        else:
            seen.add(record.experiment_id)
            updated.append(record)
    return tuple(updated)


def _sort_records(records: Sequence[ExperimentRecord]) -> list[ExperimentRecord]:
    """Sort records deterministically."""
    return sorted(
        records,
        key=lambda r: (
            r.generated_at.isoformat(),
            r.run_id,
            r.experiment_id,
            r.name,
        ),
    )


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------


def _build_comparison(
    records: Sequence[ExperimentRecord], config: ExperimentComparisonConfig
) -> ExperimentComparisonResult:
    """Build comparison result with baseline, deltas, ranking, and summary."""
    baseline_record: ExperimentRecord | None = None
    comparison_reason_codes: list[str] = []
    notes: list[str] = []

    if config.baseline_experiment_id is not None:
        baseline_record = _find_baseline(records, config.baseline_experiment_id)
        if baseline_record is None:
            comparison_reason_codes.append(BASELINE_MISSING)
            notes.append(
                f"Baseline {config.baseline_experiment_id} was provided but not found."
            )

    deltas = _compute_deltas(records, baseline_record)
    summary_metrics = _compute_summary_metrics(records)
    ranked_records = _rank_records(records, config)

    return ExperimentComparisonResult(
        config=config,
        records=tuple(records),
        ranked_records=tuple(ranked_records),
        baseline_record=baseline_record,
        deltas=deltas,
        summary_metrics=summary_metrics,
        reason_codes=tuple(comparison_reason_codes),
        notes=tuple(notes),
    )


def _find_baseline(
    records: Sequence[ExperimentRecord], baseline_experiment_id: str
) -> ExperimentRecord | None:
    """Locate the baseline record by experiment_id."""
    for record in records:
        if record.experiment_id == baseline_experiment_id:
            return record
    return None


def _compute_deltas(
    records: Sequence[ExperimentRecord],
    baseline_record: ExperimentRecord | None,
) -> Mapping[str, Mapping[str, float | int | None]]:
    """Compute per-record deltas versus the baseline."""
    if baseline_record is None:
        return MappingProxyType({})

    deltas: dict[str, dict[str, float | int | None]] = {}
    baseline_metrics = dict(baseline_record.metrics)

    for record in records:
        record_deltas: dict[str, float | int | None] = {}
        for metric_name in COMPARABLE_METRICS:
            record_value = record.metrics.get(metric_name)
            baseline_value = baseline_metrics.get(metric_name)
            if (
                record_value is not None
                and baseline_value is not None
                and isinstance(record_value, (int, float))
                and isinstance(baseline_value, (int, float))
                and not isinstance(record_value, bool)
                and not isinstance(baseline_value, bool)
            ):
                record_deltas[metric_name] = record_value - baseline_value
            else:
                record_deltas[metric_name] = None
        deltas[record.experiment_id] = record_deltas

    return MappingProxyType({k: MappingProxyType(v) for k, v in deltas.items()})


def _compute_summary_metrics(
    records: Sequence[ExperimentRecord]
) -> Mapping[str, float | int | None]:
    """Compute aggregate summary metrics over all records where safe."""
    summary: dict[str, float | int | None] = {}
    for metric_name in COMPARABLE_METRICS:
        values = [
            record.metrics[metric_name]
            for record in records
            if record.metrics.get(metric_name) is not None
            and isinstance(record.metrics[metric_name], (int, float))
            and not isinstance(record.metrics[metric_name], bool)
        ]
        if not values:
            summary[metric_name] = None
            continue
        summary[f"{metric_name}_count"] = len(values)
        summary[f"{metric_name}_mean"] = sum(values) / len(values)
        summary[f"{metric_name}_min"] = min(values)
        summary[f"{metric_name}_max"] = max(values)
    return MappingProxyType(summary)


def _rank_records(
    records: Sequence[ExperimentRecord], config: ExperimentComparisonConfig
) -> list[ExperimentRecord]:
    """Rank records for audit-review ordering."""
    eligible: list[ExperimentRecord] = []
    for record in records:
        if record.state is ExperimentState.INCLUDED:
            eligible.append(record)
        elif record.state is ExperimentState.BLOCKED and config.include_blocked:
            eligible.append(record)
        elif record.state is ExperimentState.INSUFFICIENT_DATA and config.include_insufficient:
            eligible.append(record)
        elif record.state is ExperimentState.EXCLUDED:
            eligible.append(record)

    primary_metric = config.primary_metric

    def _has_primary(record: ExperimentRecord) -> bool:
        value = record.metrics.get(primary_metric)
        return value is not None and isinstance(value, (int, float)) and not isinstance(value, bool)

    def _state_priority(record: ExperimentRecord) -> int:
        return {
            ExperimentState.INCLUDED: 0,
            ExperimentState.INSUFFICIENT_DATA: 1,
            ExperimentState.EXCLUDED: 2,
            ExperimentState.BLOCKED: 3,
        }[record.state]

    def _sort_key(record: ExperimentRecord) -> tuple:
        has_metric = _has_primary(record)
        if has_metric:
            value = record.metrics[primary_metric]
            return (
                0,
                -float(value),
                record.generated_at.isoformat(),
                record.run_id,
                record.experiment_id,
                record.name,
            )
        return (
            1,
            _state_priority(record),
            record.generated_at.isoformat(),
            record.run_id,
            record.experiment_id,
            record.name,
        )

    return sorted(eligible, key=_sort_key)


# ---------------------------------------------------------------------------
# Data quality, safety flags, and reason code aggregation
# ---------------------------------------------------------------------------


def _build_data_quality(
    records: Sequence[ExperimentRecord], input: ExperimentLedgerInput
) -> ExperimentLedgerDataQuality:
    """Build data quality summary from records."""
    total_inputs = len(input.backtest_reports) + len(input.run_results) + len(input.metric_snapshots)
    normalized_records = len(records)
    blocked_records = sum(1 for r in records if r.state is ExperimentState.BLOCKED)
    insufficient_records = sum(1 for r in records if r.state is ExperimentState.INSUFFICIENT_DATA)
    excluded_records = sum(1 for r in records if r.state is ExperimentState.EXCLUDED)
    included_records = sum(1 for r in records if r.state is ExperimentState.INCLUDED)

    sections_expected = [BACKTEST_SOURCE_KIND, RUN_SOURCE_KIND, METRIC_SNAPSHOT_SOURCE_KIND]
    sections_present = sorted(
        {r.source_kind for r in records if r.source_kind in sections_expected}
    )

    notes = (
        "Data quality summary for experiment ledger.",
        "Sections present reflect source kinds that were normalized.",
    )

    return ExperimentLedgerDataQuality(
        total_inputs=total_inputs,
        normalized_records=normalized_records,
        blocked_records=blocked_records,
        insufficient_records=insufficient_records,
        excluded_records=excluded_records,
        included_records=included_records,
        sections_present=tuple(sections_present),
        sections_expected=tuple(sections_expected),
        notes=notes,
    )


def _build_safety_flags(
    records: Sequence[ExperimentRecord],
    comparison: ExperimentComparisonResult,
) -> ExperimentLedgerSafetyFlags:
    """Build safety flags from observed record states and comparison outcome."""
    has_unsafe_content = any(UNSAFE_CONTENT in r.reason_codes for r in records)
    has_invalid_record = any(INVALID_METRICS in r.reason_codes for r in records)
    has_blocked_record = any(r.state is ExperimentState.BLOCKED for r in records)
    has_insufficient_data = any(r.state is ExperimentState.INSUFFICIENT_DATA for r in records)
    has_missing_baseline = BASELINE_MISSING in comparison.reason_codes
    return ExperimentLedgerSafetyFlags(
        has_unsafe_content=has_unsafe_content,
        has_invalid_record=has_invalid_record,
        has_blocked_record=has_blocked_record,
        has_insufficient_data=has_insufficient_data,
        has_missing_baseline=has_missing_baseline,
    )


def _aggregate_reason_codes(
    records: Sequence[ExperimentRecord],
    comparison: ExperimentComparisonResult,
) -> tuple[str, ...]:
    """Aggregate reason codes from records and comparison."""
    codes: list[str] = []
    has_blocking = False
    for record in records:
        for code in record.reason_codes:
            if code in EXPERIMENT_LEDGER_BLOCKING_REASON_CODES:
                has_blocking = True
            if code not in codes:
                codes.append(code)
    for code in comparison.reason_codes:
        if code not in codes:
            codes.append(code)
    # Add baseline advisory if needed and not already present.
    if BASELINE_MISSING in comparison.reason_codes and BASELINE_MISSING not in codes:
        codes.append(BASELINE_MISSING)
    # Add OK only when no blocking reason codes are present and the report is safe.
    if not has_blocking and not codes:
        codes.append(OK)
    # Add canonical safety advisory codes.
    for code in (RESEARCH_ONLY, NOT_TRADING_ADVICE, HUMAN_RESEARCH_ONLY, NO_FILE_INGESTION, NO_NETWORK_CONNECTION):
        if code not in codes:
            codes.append(code)
    return tuple(codes)


def _coerce_str_mapping(
    value: Mapping[str, str] | dict[str, str] | None
) -> Mapping[str, str]:
    """Coerce a string mapping into an immutable MappingProxyType."""
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        return MappingProxyType(dict(value))
    raise ValueError("metadata must be a mapping")
