"""CLI for SPEC-076 outcome evaluation: ``hunter outcome evaluate|report``.

Follows the existing from-feather command style: evaluation and reporting
are separate commands with an explicit ``--as-of`` range or
``--all-matured`` selection.  Inputs are strictly separated: read-only
immutable JSON snapshots (``--snapshot-dir``), read-only Feather prices
(``--data-dir``), and the append-only evaluation store (``--store-dir``).

No network access, no execution behavior, no scheduler mutation.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Sequence

from hunter.research_outcome_evaluation.engine import run_outcome_evaluation
from hunter.research_outcome_evaluation.models import (
    DEFAULT_HORIZONS,
    RESEARCH_NOTICE,
    OutcomeEvaluationConfig,
    parse_horizon_hours,
)
from hunter.research_outcome_evaluation.writer import load_summary_artifacts

REPORT_SCHEMA_VERSION = "spec-076-report-v1"

_CALIBRATION_THRESHOLD: int = 30
_CALIBRATION_RECOMMENDED: int = 60


_SUMMARY_METRIC_FIELDS: tuple[str, ...] = (
    "top_5_return_pct",
    "top_5_available_count",
    "top_10_return_pct",
    "top_10_available_count",
    "top_20_return_pct",
    "top_20_available_count",
    "top_30_return_pct",
    "top_30_available_count",
    "spearman_rank_return",
    "spearman_relative_strength_return",
    "spearman_liquidity_return",
    "benchmark_relative_return_pct",
    "mae_pct_mean",
    "mfe_pct_mean",
    "realized_volatility_pct_mean",
)


def _is_invalid_summary(summary: Mapping[str, Any]) -> bool:
    """Classify a persisted summary as an invalid cohort.

    Priority:
    1. Persisted invalid-snapshot/rejection metadata.
    2. Summary terminal_state_counts (all SNAPSHOT_INVALID).
    3. Fail-closed missing/UNKNOWN ranking_profile.
    """
    metadata = summary.get("metadata") or {}
    if metadata.get("invalid_snapshot") is True:
        return True
    counts = metadata.get("terminal_state_counts") or {}
    if counts and set(counts.keys()) == {"SNAPSHOT_INVALID"}:
        return True
    profile = summary.get("ranking_profile")
    if not profile or profile == "UNKNOWN":
        return True
    return False


def _snapshot_identity(summary: Mapping[str, Any]) -> str:
    """Return snapshot_id from metadata or a safe fallback derived from the summary."""
    metadata = summary.get("metadata") or {}
    snapshot_id = metadata.get("snapshot_id")
    if snapshot_id:
        return str(snapshot_id)
    return f"{summary.get('snapshot_date', '')}__{summary.get('outcome_horizon', '')}"

OUTCOME_CLI_HELP_TEXT = """Outcome-evaluation commands (SPEC-076):
  outcome evaluate             Evaluate matured snapshot cohorts and persist records.
  outcome report               Render persisted summaries with horizon-suffixed metric names.

Run `hunter outcome <command> --help` for full per-command options.
"""


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="hunter outcome", description=OUTCOME_CLI_HELP_TEXT)
    sub = parser.add_subparsers(dest="command", required=True)

    def _add_selection(p: argparse.ArgumentParser) -> None:
        group = p.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--as-of",
            dest="as_of",
            metavar="YYYY-MM-DD[:YYYY-MM-DD]",
            help="Explicit snapshot date or inclusive date range.",
        )
        group.add_argument(
            "--all-matured",
            action="store_true",
            help="Evaluate every snapshot whose horizon has elapsed.",
        )

    def _add_horizons(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--horizons",
            default=",".join(DEFAULT_HORIZONS),
            help="Comma-separated horizon tokens (default: 1d,3d,7d).",
        )

    evaluate = sub.add_parser("evaluate", help="Evaluate matured cohorts and persist records.")
    evaluate.add_argument("--snapshot-dir", required=True, type=Path)
    evaluate.add_argument("--data-dir", required=True, type=Path)
    evaluate.add_argument("--store-dir", required=True, type=Path)
    evaluate.add_argument(
        "--min-window-coverage",
        default="0.95",
        help="Minimum valid intra-window coverage ratio in (0, 1] (default: 0.95).",
    )
    _add_selection(evaluate)
    _add_horizons(evaluate)

    report = sub.add_parser("report", help="Render persisted summaries.")
    report.add_argument("--store-dir", required=True, type=Path)
    report.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Report output format (default: json).",
    )
    _add_selection(report)
    _add_horizons(report)

    return parser.parse_args(list(argv))


def _parse_horizons(raw: str) -> tuple[str, ...]:
    horizons = tuple(token.strip() for token in raw.split(",") if token.strip())
    for token in horizons:
        parse_horizon_hours(token)
    return horizons


def _parse_iso_date(raw: str) -> date:
    """Parse a YYYY-MM-DD date string; raises ValueError on malformed input."""
    return datetime.strptime(raw, "%Y-%m-%d").date()


def _parse_as_of(raw: str) -> tuple[date | None, date | None]:
    """Parse --as-of YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD into inclusive start/end dates."""
    if ":" in raw:
        start, end = raw.split(":", 1)
        start_date = _parse_iso_date(start)
        end_date = _parse_iso_date(end) if end else None
        return start_date, end_date
    parsed = _parse_iso_date(raw)
    return parsed, parsed


def _paths_are_distinct(paths: list[Path]) -> bool:
    """Return True iff no path equals or is nested inside another."""
    resolved = [p.resolve() for p in paths]
    for i, a in enumerate(resolved):
        for b in resolved[i + 1 :]:
            if a == b or a in b.parents or b in a.parents:
                return False
    return True


def _calibration_gate(summaries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Matured-cohort counts and eligibility per (ranking_profile, outcome_horizon)."""
    counts: dict[tuple[str, str], int] = {}
    for s in summaries:
        if _is_invalid_summary(s):
            continue
        profile = s.get("ranking_profile", "")
        horizon = s.get("outcome_horizon", "")
        counts[(profile, horizon)] = counts.get((profile, horizon), 0) + 1

    result: dict[str, dict[str, Any]] = {}
    for (profile, horizon), count in sorted(counts.items()):
        result.setdefault(profile, {})[horizon] = {
            "matured_cohort_count": count,
            "threshold": _CALIBRATION_THRESHOLD,
            "recommended": _CALIBRATION_RECOMMENDED,
            "eligible": count >= _CALIBRATION_THRESHOLD,
            "eligible_recommended": count >= _CALIBRATION_RECOMMENDED,
        }
    return result


def _flatten_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    """Add the horizon suffix to flattened report metric names."""
    horizon = summary["outcome_horizon"]
    flattened: dict[str, Any] = {}
    for field_name in _SUMMARY_METRIC_FIELDS:
        flattened[f"{field_name}_{horizon}"] = summary.get(field_name)
    return flattened


def _run_evaluate(args: argparse.Namespace) -> int:
    snapshot_dir = args.snapshot_dir.resolve()
    data_dir = args.data_dir.resolve()
    store_dir = args.store_dir.resolve()
    if not _paths_are_distinct([snapshot_dir, data_dir, store_dir]):
        print(
            "Error: --snapshot-dir, --data-dir, and --store-dir must be distinct paths "
            "and none may be inside another.",
            file=sys.stderr,
        )
        return 2
    for label, path in (
        ("--snapshot-dir", snapshot_dir),
        ("--data-dir", data_dir),
    ):
        if not path.exists():
            print(f"Error: {label} does not exist: {path}", file=sys.stderr)
            return 2
        if not path.is_dir():
            print(f"Error: {label} is not a directory: {path}", file=sys.stderr)
            return 2

    as_of_start: date | None = None
    as_of_end: date | None = None
    if args.as_of:
        try:
            as_of_start, as_of_end = _parse_as_of(args.as_of)
        except ValueError as exc:
            print(f"Error: invalid --as-of date: {exc}", file=sys.stderr)
            return 2
        if as_of_start is not None and as_of_end is not None and as_of_start > as_of_end:
            print("Error: --as-of start date must not be after end date.", file=sys.stderr)
            return 2

    try:
        coverage = Decimal(args.min_window_coverage)
    except InvalidOperation:
        print(f"Error: invalid --min-window-coverage: {args.min_window_coverage}", file=sys.stderr)
        return 2
    if not coverage.is_finite():
        print(
            f"Error: --min-window-coverage must be finite (got {args.min_window_coverage}).",
            file=sys.stderr,
        )
        return 2
    try:
        config = OutcomeEvaluationConfig(
            horizons=_parse_horizons(args.horizons),
            min_window_coverage=coverage,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    report = run_outcome_evaluation(
        snapshot_dir=snapshot_dir,
        data_dir=data_dir,
        store_dir=store_dir,
        config=config,
        as_of_start=as_of_start.isoformat() if as_of_start else None,
        as_of_end=as_of_end.isoformat() if as_of_end else None,
        all_matured=args.all_matured,
        now=datetime.now(timezone.utc),
    )
    payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "command": "evaluate",
        "cohorts_evaluated": len(report.cohorts),
        "invalid_cohorts": [
            {
                "snapshot_date": c.snapshot_date,
                "ranking_profile": c.ranking_profile,
                "outcome_horizon": c.outcome_horizon,
                "terminal_state_counts": c.summary.metadata.get("terminal_state_counts", {}),
                "invalid_reason": c.summary.metadata.get("invalid_reason"),
            }
            for c in report.invalid_cohorts
        ],
        "pending_cohorts": list(report.pending_cohorts),
        "invalid_snapshots": [list(item) for item in report.invalid_snapshots],
        "terminal_state_counts": dict(report.terminal_state_counts),
        "artifact_paths": [str(path) for path in report.artifact_paths],
        "_safety_notice": RESEARCH_NOTICE,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _run_report(args: argparse.Namespace) -> int:
    store_dir = args.store_dir.resolve()
    if not store_dir.exists():
        print(f"Error: --store-dir does not exist: {store_dir}", file=sys.stderr)
        return 2
    if not store_dir.is_dir():
        print(f"Error: --store-dir is not a directory: {store_dir}", file=sys.stderr)
        return 2

    as_of_start: date | None = None
    as_of_end: date | None = None
    if args.as_of:
        try:
            as_of_start, as_of_end = _parse_as_of(args.as_of)
        except ValueError as exc:
            print(f"Error: invalid --as-of date: {exc}", file=sys.stderr)
            return 2
        if as_of_start is not None and as_of_end is not None and as_of_start > as_of_end:
            print("Error: --as-of start date must not be after end date.", file=sys.stderr)
            return 2

    try:
        horizons = set(_parse_horizons(args.horizons))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    summaries = []
    for summary in load_summary_artifacts(store_dir):
        if summary.get("outcome_horizon") not in horizons:
            continue
        date_raw = summary.get("snapshot_date", "")
        try:
            summary_date = _parse_iso_date(str(date_raw))
        except ValueError as exc:
            print(
                f"Error: persisted summary has malformed snapshot_date {date_raw!r}: {exc}",
                file=sys.stderr,
            )
            return 2
        if not args.all_matured:
            if as_of_start is not None and summary_date < as_of_start:
                continue
            if as_of_end is not None and summary_date > as_of_end:
                continue
        summaries.append(summary)

    summaries.sort(
        key=lambda s: (
            _parse_iso_date(str(s.get("snapshot_date", ""))).isoformat(),
            s.get("ranking_profile", ""),
            s.get("outcome_horizon", ""),
        )
    )

    valid_summaries = [s for s in summaries if not _is_invalid_summary(s)]
    invalid_summaries = [s for s in summaries if _is_invalid_summary(s)]

    if args.format == "markdown":
        print(_render_markdown(valid_summaries, invalid_summaries))
        return 0

    payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "command": "report",
        "cohort_count": len(valid_summaries),
        "invalid_cohort_count": len(invalid_summaries),
        "calibration_gate": _calibration_gate(valid_summaries),
        "invalid_cohorts": [
            {
                "snapshot_id": _snapshot_identity(s),
                "snapshot_date": s.get("snapshot_date"),
                "ranking_profile": None,
                "outcome_horizon": s.get("outcome_horizon"),
                "terminal_state_counts": (s.get("metadata") or {}).get("terminal_state_counts", {}),
                "invalid_reason": (s.get("metadata") or {}).get("invalid_reason"),
            }
            for s in invalid_summaries
        ],
        "cohorts": [
            {
                "snapshot_date": s.get("snapshot_date"),
                "ranking_profile": s.get("ranking_profile"),
                "outcome_horizon": s.get("outcome_horizon"),
                "cohort_size": s.get("cohort_size"),
                "available_count": s.get("available_count"),
                "unavailable_count": s.get("unavailable_count"),
                "days_since_previous_snapshot": s.get("days_since_previous_snapshot"),
                "turnover": s.get("turnover"),
                "retention": s.get("retention"),
                "daily_data_availability": s.get("daily_data_availability"),
                "benchmark_failure_reason": s.get("benchmark_failure_reason"),
                "metrics": _flatten_metrics(s),
                "fingerprint": s.get("fingerprint"),
            }
            for s in valid_summaries
        ],
        "_safety_notice": RESEARCH_NOTICE,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _render_markdown(
    valid_summaries: list[dict[str, Any]], invalid_summaries: list[dict[str, Any]]
) -> str:
    header = (
        "| snapshot_date | ranking_profile | horizon | cohort | available | "
        "top_5 | top_5_count | top_10 | top_10_count | top_20 | top_20_count | "
        "top_30 | top_30_count | spearman_rank | benchmark_relative | turnover | retention |"
    )
    separator = "|" + "---|" * 17
    lines = [
        "# SPEC-076 Outcome Evaluation Report",
        "",
        RESEARCH_NOTICE,
        "",
        "## Calibration gate",
        "",
    ]
    gate = _calibration_gate(valid_summaries)
    if not gate:
        lines.append("_(no valid persisted summaries matched the selection)_")
    else:
        lines.append(
            "| ranking_profile | horizon | matured_cohorts | threshold | eligible | recommended | eligible_recommended |"
        )
        lines.append("|" + "---|" * 7)
        for profile, horizons in sorted(gate.items()):
            for horizon, info in sorted(horizons.items()):
                row = [
                    profile,
                    horizon,
                    str(info["matured_cohort_count"]),
                    str(info["threshold"]),
                    str(info["eligible"]),
                    str(info["recommended"]),
                    str(info["eligible_recommended"]),
                ]
                lines.append("| " + " | ".join(row) + " |")
    lines.extend(["", "## Cohorts", "", header, separator])
    if not valid_summaries:
        lines.append("| (no valid persisted summaries matched the selection) |" + " |" * 16)
    for summary in valid_summaries:
        horizon = summary.get("outcome_horizon", "")
        row = [
            str(summary.get("snapshot_date", "")),
            str(summary.get("ranking_profile", "")),
            str(horizon),
            str(summary.get("cohort_size", "")),
            str(summary.get("available_count", "")),
            str(summary.get("top_5_return_pct")),
            str(summary.get("top_5_available_count")),
            str(summary.get("top_10_return_pct")),
            str(summary.get("top_10_available_count")),
            str(summary.get("top_20_return_pct")),
            str(summary.get("top_20_available_count")),
            str(summary.get("top_30_return_pct")),
            str(summary.get("top_30_available_count")),
            str(summary.get("spearman_rank_return")),
            str(summary.get("benchmark_relative_return_pct")),
            str(summary.get("turnover")),
            str(summary.get("retention")),
        ]
        lines.append("| " + " | ".join(row) + " |")
    if invalid_summaries:
        lines.extend(["", "## Invalid cohorts", "", "| snapshot_id | snapshot_date | horizon | terminal_state_counts | invalid_reason |", "|" + "---|" * 5])
        for summary in invalid_summaries:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _snapshot_identity(summary),
                        str(summary.get("snapshot_date", "")),
                        str(summary.get("outcome_horizon", "")),
                        str((summary.get("metadata") or {}).get("terminal_state_counts", "")),
                        str((summary.get("metadata") or {}).get("invalid_reason", "")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines)


def outcome_cli_main(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``hunter outcome ...`` dispatch."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "evaluate":
        return _run_evaluate(args)
    if args.command == "report":
        return _run_report(args)
    # argparse subparsers require a valid command, so this branch is unreachable
    # under normal CLI use. It is kept as an internal invariant assertion.
    raise AssertionError(f"unreachable: argparse validated outcome command {args.command!r}")
