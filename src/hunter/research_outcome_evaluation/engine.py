"""Evaluation orchestration for SPEC-076 outcome evaluation (M4).

For every matured (snapshot_date, ranking_profile, outcome_horizon) cohort:

1. Load the immutable JSON snapshot (invalid -> every identifiable member
   resolves to ``SNAPSHOT_INVALID``; nothing is silently discarded).
2. Resolve the BTC benchmark once per cohort (shared by all members).
3. Resolve every cohort member in the mandated terminal-state order.
4. Compute per-pair metrics for ``OUTCOME_AVAILABLE`` members only.
5. Compute cohort-level descriptive metrics and turnover/retention versus
   ``D_prev`` (source-based previous valid snapshot).
6. Persist Pair Observation Records and the Snapshot Summary Record
   exactly once (append-only, atomic).

``PENDING_HORIZON`` cohorts are computed transiently and never persisted.
No network, no subprocess, no scheduler mutation, no source-data mutation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable, Mapping

from hunter.research_outcome_evaluation.errors import SnapshotValidationError
from hunter.research_outcome_evaluation.fingerprint import (
    compute_record_fingerprint,
    compute_snapshot_id,
)
from hunter.research_outcome_evaluation.metrics import (
    compute_mae_mfe,
    compute_realized_return,
    compute_realized_volatility_pct,
    mean_pct,
    spearman,
    top_n_return_and_count,
)
from hunter.research_outcome_evaluation.models import (
    BENCHMARK_PAIR,
    REASON_INSUFFICIENT_OBSERVATIONS,
    TOP_N_CUTS,
    OutcomeEvaluationConfig,
    PairObservationRecord,
    SnapshotSummaryRecord,
    TerminalState,
    pair_observation_to_dict,
    snapshot_summary_to_dict,
)
from hunter.research_outcome_evaluation.price_source import (
    PriceSeries,
    build_price_source_map,
    load_price_series,
)
from hunter.research_outcome_evaluation.resolution import (
    PairEvaluation,
    compute_window_anchors,
    horizon_elapsed,
    resolve_series,
)
from hunter.research_outcome_evaluation.snapshot_reader import (
    SnapshotCohort,
    SnapshotPairEntry,
    discover_snapshot_audits,
    load_snapshot_audit,
)
from hunter.research_outcome_evaluation.summary import (
    compute_daily_data_availability,
    compute_previous_snapshot_metrics,
    find_previous_snapshot,
)
from hunter.research_outcome_evaluation.writer import write_observations, write_summary

ISO = "%Y-%m-%dT%H:%M:%S+00:00"


@dataclass(frozen=True)
class CohortEvaluation:
    """One persisted cohort: observations plus summary."""

    snapshot_date: str
    ranking_profile: str
    outcome_horizon: str
    observations: tuple[PairObservationRecord, ...]
    summary: SnapshotSummaryRecord
    is_invalid: bool = False


@dataclass(frozen=True)
class RunReport:
    """Aggregate result of one evaluation run (CLI-facing, not persisted)."""

    cohorts: tuple[CohortEvaluation, ...]
    pending_cohorts: tuple[str, ...]
    invalid_snapshots: tuple[tuple[str, str], ...]
    artifact_paths: tuple[Path, ...]
    terminal_state_counts: Mapping[str, int]
    invalid_cohorts: tuple[CohortEvaluation, ...] = ()


def _iso(value: datetime) -> str:
    return value.strftime(ISO)


def _coverage_ratio(evaluation: PairEvaluation) -> Decimal | None:
    if evaluation.series is None:
        return None
    return (Decimal(evaluation.coverage_ratio_num) / Decimal(evaluation.coverage_ratio_den)).quantize(
        Decimal("0.000001")
    )


def _finalize_observation(record: PairObservationRecord) -> PairObservationRecord:
    fingerprint = compute_record_fingerprint(pair_observation_to_dict(record))
    return replace(record, fingerprint=fingerprint)


def _finalize_summary(summary: SnapshotSummaryRecord) -> SnapshotSummaryRecord:
    fingerprint = compute_record_fingerprint(snapshot_summary_to_dict(summary))
    return replace(summary, fingerprint=fingerprint)


def _observation_kwargs(
    *,
    cohort: SnapshotCohort,
    entry: SnapshotPairEntry,
    outcome_horizon: str,
) -> dict:
    return {
        "snapshot_date": cohort.snapshot_date,
        "ranking_profile": cohort.ranking_profile,
        "outcome_horizon": outcome_horizon,
        "pair": entry.pair,
        "is_benchmark_pair": entry.pair == BENCHMARK_PAIR,
        "rank_at_selection": entry.rank,
        "relative_strength_score": entry.relative_strength_score,
        "liquidity_score": entry.liquidity_score,
    }


def _resolve_member(
    *,
    cohort: SnapshotCohort,
    entry: SnapshotPairEntry,
    outcome_horizon: str,
    evaluation: PairEvaluation,
    benchmark_ok: bool,
    benchmark_return: Decimal | None,
) -> PairObservationRecord:
    anchors = evaluation.anchors
    kwargs = _observation_kwargs(cohort=cohort, entry=entry, outcome_horizon=outcome_horizon)
    kwargs["coverage_ratio"] = _coverage_ratio(evaluation)
    kwargs["window_start"] = _iso(anchors.reference_close_time)
    kwargs["window_end"] = _iso(anchors.endpoint_close_time)

    if evaluation.terminal_state is not TerminalState.OUTCOME_AVAILABLE:
        # Diagnostic retention: benchmark_return when computable.
        return _finalize_observation(
            PairObservationRecord(
                terminal_state=evaluation.terminal_state,
                benchmark_return=benchmark_return,
                **kwargs,
            )
        )

    assert evaluation.reference_candle is not None
    assert evaluation.endpoint_candle is not None
    reference_close = Decimal(str(evaluation.reference_candle.close))
    endpoint_close = Decimal(str(evaluation.endpoint_candle.close))
    kwargs["reference_close"] = reference_close
    kwargs["reference_timestamp"] = _iso(anchors.reference_close_time)

    if not benchmark_ok:
        return _finalize_observation(
            PairObservationRecord(
                terminal_state=TerminalState.BENCHMARK_UNAVAILABLE,
                **kwargs,
            )
        )

    realized = compute_realized_return(reference_close, endpoint_close)
    mae, mfe = compute_mae_mfe(evaluation)
    volatility = compute_realized_volatility_pct(evaluation)

    if entry.pair == BENCHMARK_PAIR:
        pair_benchmark_return = realized
        benchmark_relative = Decimal("0").quantize(Decimal("0.000001"))
    else:
        pair_benchmark_return = benchmark_return
        assert benchmark_return is not None
        benchmark_relative = (realized - benchmark_return).quantize(Decimal("0.000001"))

    return _finalize_observation(
        PairObservationRecord(
            terminal_state=TerminalState.OUTCOME_AVAILABLE,
            realized_return=realized,
            benchmark_return=pair_benchmark_return,
            benchmark_relative_return=benchmark_relative,
            mae_pct=mae,
            mfe_pct=mfe,
            realized_volatility_pct=volatility,
            **kwargs,
        )
    )


def _build_summary(
    *,
    cohort: SnapshotCohort,
    outcome_horizon: str,
    observations: tuple[PairObservationRecord, ...],
    config: OutcomeEvaluationConfig,
    benchmark_failure_reason: str | None,
    price_map: Mapping[str, Path],
    previous: SnapshotCohort | None,
    snapshot_trusted: bool,
    snapshot_fingerprint: str,
    invalid_reason: str | None = None,
) -> SnapshotSummaryRecord:
    counts = Counter(obs.terminal_state.value for obs in observations)
    available = [obs for obs in observations if obs.terminal_state is TerminalState.OUTCOME_AVAILABLE]

    ranked_returns = [(obs.rank_at_selection, obs.realized_return) for obs in available if obs.realized_return is not None]
    top_returns = {}
    top_counts = {}
    for n in TOP_N_CUTS:
        top_returns[n], top_counts[n] = top_n_return_and_count(ranked_returns, n)

    spearman_rank = spearman(
        [float(obs.rank_at_selection) for obs in available],
        [float(obs.realized_return) for obs in available if obs.realized_return is not None],
    ) if available and all(obs.realized_return is not None for obs in available) else None

    rs_pairs = [
        (obs.relative_strength_score, obs.realized_return)
        for obs in available
        if obs.relative_strength_score is not None and obs.realized_return is not None
    ]
    spearman_rs = (
        spearman([float(a) for a, _ in rs_pairs], [float(b) for _, b in rs_pairs])
        if len(rs_pairs) >= 2
        else None
    )

    liq_pairs = [
        (obs.liquidity_score, obs.realized_return)
        for obs in available
        if obs.liquidity_score is not None and obs.realized_return is not None
    ]
    spearman_liq = (
        spearman([float(a) for a, _ in liq_pairs], [float(b) for _, b in liq_pairs])
        if len(liq_pairs) >= 2
        else None
    )

    benchmark_relative_values = [
        obs.benchmark_relative_return
        for obs in available
        if not obs.is_benchmark_pair and obs.benchmark_relative_return is not None
    ]

    if snapshot_trusted:
        previous_metrics = compute_previous_snapshot_metrics(current=cohort, previous=previous)
        days_since = previous_metrics.days_since_previous_snapshot
        days_reason = previous_metrics.previous_snapshot_reason
        turnover = previous_metrics.turnover
        turnover_reason = previous_metrics.turnover_reason
        retention = previous_metrics.retention
        retention_reason = previous_metrics.retention_reason
    else:
        days_since = None
        days_reason = REASON_INSUFFICIENT_OBSERVATIONS
        turnover = None
        turnover_reason = REASON_INSUFFICIENT_OBSERVATIONS
        retention = None
        retention_reason = REASON_INSUFFICIENT_OBSERVATIONS

    availability, availability_reason = compute_daily_data_availability(
        pairs=tuple(obs.pair for obs in observations),
        available_sources=frozenset(price_map.keys()),
    )

    summary = SnapshotSummaryRecord(
        snapshot_date=cohort.snapshot_date,
        ranking_profile=cohort.ranking_profile,
        outcome_horizon=outcome_horizon,
        cohort_size=len(observations),
        available_count=len(available),
        unavailable_count=len(observations) - len(available),
        days_since_previous_snapshot=days_since,
        previous_snapshot_reason=days_reason,
        turnover=turnover,
        turnover_reason=turnover_reason,
        retention=retention,
        retention_reason=retention_reason,
        daily_data_availability=availability,
        daily_data_availability_reason=availability_reason,
        top_5_return_pct=top_returns[5],
        top_5_available_count=top_counts[5],
        top_10_return_pct=top_returns[10],
        top_10_available_count=top_counts[10],
        top_20_return_pct=top_returns[20],
        top_20_available_count=top_counts[20],
        top_30_return_pct=top_returns[30],
        top_30_available_count=top_counts[30],
        spearman_rank_return=spearman_rank,
        spearman_relative_strength_return=spearman_rs,
        spearman_liquidity_return=spearman_liq,
        benchmark_relative_return_pct=mean_pct(benchmark_relative_values),
        mae_pct_mean=mean_pct([obs.mae_pct for obs in available if obs.mae_pct is not None]),
        mfe_pct_mean=mean_pct([obs.mfe_pct for obs in available if obs.mfe_pct is not None]),
        realized_volatility_pct_mean=mean_pct(
            [obs.realized_volatility_pct for obs in available if obs.realized_volatility_pct is not None]
        ),
        benchmark_failure_reason=benchmark_failure_reason,
        metadata={
            "terminal_state_counts": dict(sorted(counts.items())),
            "min_window_coverage": str(config.min_window_coverage),
            "snapshot_fingerprint": snapshot_fingerprint,
            "snapshot_id": compute_snapshot_id(cohort.snapshot_date, cohort.ranking_profile),
            **({"invalid_snapshot": True, "invalid_reason": invalid_reason} if invalid_reason else {}),
        },
    )
    return _finalize_summary(summary)


def _evaluate_invalid_snapshot(
    *,
    path: Path,
    error: str,
    members: tuple[SnapshotPairEntry, ...],
    snapshot_date: str,
    ranking_profile: str,
    outcome_horizon: str,
    config: OutcomeEvaluationConfig,
    price_map: Mapping[str, Path],
) -> CohortEvaluation:
    cohort = SnapshotCohort(
        snapshot_date=snapshot_date,
        ranking_profile=ranking_profile,
        entries=members,
        source_path=path,
        source_fingerprint="",
    )
    observations = tuple(
        _finalize_observation(
            PairObservationRecord(
                terminal_state=TerminalState.SNAPSHOT_INVALID,
                **_observation_kwargs(cohort=cohort, entry=entry, outcome_horizon=outcome_horizon),
            )
        )
        for entry in members
    )
    summary = _build_summary(
        cohort=cohort,
        outcome_horizon=outcome_horizon,
        observations=observations,
        config=config,
        benchmark_failure_reason=None,
        price_map=price_map,
        previous=None,
        snapshot_trusted=False,
        snapshot_fingerprint="",
        invalid_reason=error,
    )
    return CohortEvaluation(
        snapshot_date=snapshot_date,
        ranking_profile=ranking_profile,
        outcome_horizon=outcome_horizon,
        observations=observations,
        summary=summary,
        is_invalid=True,
    )


def run_outcome_evaluation(
    *,
    snapshot_dir: Path,
    data_dir: Path,
    store_dir: Path,
    config: OutcomeEvaluationConfig | None = None,
    as_of_start: str | None = None,
    as_of_end: str | None = None,
    all_matured: bool = False,
    now: datetime | None = None,
    series_loader: Callable[[Path, str, datetime], PriceSeries] = load_price_series,
) -> RunReport:
    """Evaluate every selected cohort and persist records exactly once.

    Exactly one selection mode is required: an explicit ``--as-of`` range
    (``as_of_start``/``as_of_end``) or ``all_matured=True``.
    """
    if not all_matured and as_of_start is None:
        raise ValueError("selection required: --as-of range or --all-matured")
    config = config or OutcomeEvaluationConfig()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    price_map = build_price_source_map(data_dir)
    coverage_num = int(config.min_window_coverage * 1000000)
    coverage_den = 1000000

    snapshot_paths = discover_snapshot_audits(snapshot_dir)

    # Strictly-valid snapshots across ALL dates feed the D_prev index.
    valid_snapshots: list[SnapshotCohort] = []
    for path in snapshot_paths:
        try:
            valid_snapshots.append(load_snapshot_audit(path))
        except SnapshotValidationError:
            continue

    series_cache: dict[str, PriceSeries | None] = {}

    def _series_for(pair: str) -> PriceSeries | None:
        if pair not in series_cache:
            source = price_map.get(pair)
            series_cache[pair] = None if source is None else series_loader(source, pair, now)
        return series_cache[pair]

    cohorts: list[CohortEvaluation] = []
    invalid_cohorts: list[CohortEvaluation] = []
    pending: list[str] = []
    invalid: list[tuple[str, str]] = []
    artifact_paths: list[Path] = []
    state_counts: Counter[str] = Counter()

    horizons = sorted(config.horizons, key=lambda h: parse_hours(h))
    for path in snapshot_paths:
        try:
            cohort = load_snapshot_audit(path)
            load_error: str | None = None
        except SnapshotValidationError as exc:
            cohort = None  # type: ignore[assignment]
            load_error = str(exc)

        if cohort is not None:
            in_range = _in_range(cohort.snapshot_date, as_of_start, as_of_end, all_matured)
        else:
            # Best-effort identity for invalid snapshots: filename date.
            in_range = _in_range(_filename_date(path), as_of_start, as_of_end, all_matured)
        if not in_range:
            continue

        for horizon in horizons:
            if cohort is not None:
                anchors = compute_window_anchors(cohort.snapshot_date, horizon)
                if not horizon_elapsed(anchors, now):
                    pending.append(f"{cohort.snapshot_date}|{cohort.ranking_profile}|{horizon}")
                    continue
                result = _evaluate_valid_snapshot(
                    cohort=cohort,
                    horizon=horizon,
                    anchors=anchors,
                    config=config,
                    coverage_num=coverage_num,
                    coverage_den=coverage_den,
                    price_map=price_map,
                    series_for=_series_for,
                    valid_snapshots=tuple(valid_snapshots),
                )
            else:
                members, snap_date, profile = _best_effort_members(path)
                if not members:
                    # Cannot identify any member: nothing to resolve; the
                    # invalid snapshot is still reported, never discarded.
                    invalid.append((str(path), load_error or "unreadable snapshot"))
                    break
                result = _evaluate_invalid_snapshot(
                    path=path,
                    error=load_error or "invalid snapshot",
                    members=members,
                    snapshot_date=snap_date,
                    ranking_profile=profile,
                    outcome_horizon=horizon,
                    config=config,
                    price_map=price_map,
                )
                if (str(path), load_error or "invalid snapshot") not in invalid:
                    invalid.append((str(path), load_error or "invalid snapshot"))

            obs_path = write_observations(
                store_dir=store_dir,
                snapshot_date=result.snapshot_date,
                ranking_profile=result.ranking_profile,
                outcome_horizon=result.outcome_horizon,
                records=result.observations,
            )
            sum_path = write_summary(store_dir=store_dir, summary=result.summary)
            artifact_paths.extend([obs_path, sum_path])
            if result.is_invalid:
                invalid_cohorts.append(result)
            else:
                cohorts.append(result)
            for obs in result.observations:
                state_counts[obs.terminal_state.value] += 1

    return RunReport(
        cohorts=tuple(cohorts),
        pending_cohorts=tuple(pending),
        invalid_snapshots=tuple(invalid),
        artifact_paths=tuple(artifact_paths),
        terminal_state_counts=dict(sorted(state_counts.items())),
        invalid_cohorts=tuple(invalid_cohorts),
    )


def parse_hours(horizon: str) -> int:
    from hunter.research_outcome_evaluation.models import parse_horizon_hours

    return parse_horizon_hours(horizon)


def _filename_date(path: Path) -> str:
    stem = path.name.removeprefix("hunter-pairs-").removesuffix("-audit.json")
    return f"{stem[0:4]}-{stem[4:6]}-{stem[6:8]}"


def _in_range(snapshot_date: str, start: str | None, end: str | None, all_matured: bool) -> bool:
    if all_matured:
        return True
    if start is not None and snapshot_date < start:
        return False
    if end is not None and snapshot_date > end:
        return False
    return True


def _best_effort_members(path: Path) -> tuple[tuple[SnapshotPairEntry, ...], str, str]:
    """Extract identifiable members from an invalid snapshot (never trusted)."""
    import json

    from hunter.research_outcome_evaluation.models import parse_decimal

    snap_date = _filename_date(path)
    profile = "UNKNOWN"
    members: list[SnapshotPairEntry] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return (), snap_date, profile
    if isinstance(raw, dict):
        if isinstance(raw.get("ranking_profile"), str) and raw["ranking_profile"]:
            profile = raw["ranking_profile"]
        if isinstance(raw.get("as_of_date"), str):
            snap_date = raw["as_of_date"]
        selected = raw.get("selected")
        if isinstance(selected, list):
            seen: set[str] = set()
            for item in selected:
                if not isinstance(item, dict):
                    continue
                pair = item.get("pair")
                rank = item.get("rank")
                if not isinstance(pair, str) or not pair or pair in seen:
                    continue
                if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
                    continue
                seen.add(pair)
                try:
                    rs = parse_decimal(item.get("rs_score"))
                    liq = parse_decimal(item.get("liquidity_score"))
                except ValueError:
                    rs = None
                    liq = None
                members.append(
                    SnapshotPairEntry(
                        pair=pair, rank=rank, relative_strength_score=rs, liquidity_score=liq
                    )
                )
    return tuple(members), snap_date, profile


def _evaluate_valid_snapshot(
    *,
    cohort: SnapshotCohort,
    horizon: str,
    anchors: object,
    config: OutcomeEvaluationConfig,
    coverage_num: int,
    coverage_den: int,
    price_map: Mapping[str, Path],
    series_for: Callable[[str], PriceSeries | None],
    valid_snapshots: tuple[SnapshotCohort, ...],
) -> CohortEvaluation:
    # Benchmark validation once per cohort, shared by all members.
    benchmark_series = series_for(BENCHMARK_PAIR)
    benchmark_eval = resolve_series(
        series=benchmark_series,
        anchors=anchors,  # type: ignore[arg-type]
        min_window_coverage_num=coverage_num,
        min_window_coverage_den=coverage_den,
    )
    benchmark_ok = benchmark_eval.terminal_state is TerminalState.OUTCOME_AVAILABLE
    benchmark_return: Decimal | None = None
    if benchmark_ok:
        assert benchmark_eval.reference_candle is not None
        assert benchmark_eval.endpoint_candle is not None
        benchmark_return = compute_realized_return(
            Decimal(str(benchmark_eval.reference_candle.close)),
            Decimal(str(benchmark_eval.endpoint_candle.close)),
        )
    benchmark_failure_reason = None if benchmark_ok else benchmark_eval.terminal_state.value

    observations: list[PairObservationRecord] = []
    for entry in sorted(cohort.entries, key=lambda e: e.rank):
        if entry.pair == BENCHMARK_PAIR:
            evaluation = benchmark_eval
        else:
            evaluation = resolve_series(
                series=series_for(entry.pair),
                anchors=anchors,  # type: ignore[arg-type]
                min_window_coverage_num=coverage_num,
                min_window_coverage_den=coverage_den,
            )
        observations.append(
            _resolve_member(
                cohort=cohort,
                entry=entry,
                outcome_horizon=horizon,
                evaluation=evaluation,
                benchmark_ok=benchmark_ok,
                benchmark_return=benchmark_return,
            )
        )

    previous = find_previous_snapshot(cohort=cohort, valid_snapshots=valid_snapshots)
    summary = _build_summary(
        cohort=cohort,
        outcome_horizon=horizon,
        observations=tuple(observations),
        config=config,
        benchmark_failure_reason=benchmark_failure_reason,
        price_map=price_map,
        previous=previous,
        snapshot_trusted=True,
        snapshot_fingerprint=cohort.source_fingerprint,
    )
    return CohortEvaluation(
        snapshot_date=cohort.snapshot_date,
        ranking_profile=cohort.ranking_profile,
        outcome_horizon=horizon,
        observations=tuple(observations),
        summary=summary,
    )
