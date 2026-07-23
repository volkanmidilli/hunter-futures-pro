"""M5 tests: CLI integration for hunter outcome evaluate/report."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.feather as feather
import pytest

from hunter.core.cli import main as hunter_main
from hunter.research_outcome_evaluation.cli import outcome_cli_main

NOW = datetime(2026, 1, 12, 0, 0, tzinfo=timezone.utc)


def _write_feather(path: Path, start: datetime, count: int, base: float = 100.0) -> None:
    rows = [
        {
            "date": start + timedelta(hours=i),
            "open": base + i,
            "high": base + i + 1.0,
            "low": base + i - 1.0,
            "close": base + i,
            "volume": 10.0,
        }
        for i in range(count)
    ]
    feather.write_feather(pa.Table.from_pylist(rows), str(path))


def _write_snapshot(directory: Path, pairs: list[str], day: str = "2026-01-10") -> None:
    payload = {
        "as_of_date": day,
        "ranking_profile": "V2_RS_LIQUIDITY",
        "schema_version": "hunter-ranking-input-v2",
        "selected": [
            {
                "pair": pair,
                "rank": i + 1,
                "selected": True,
                "rs_score": "90",
                "liquidity_score": "80",
                "reason_codes": [],
                "fingerprint": f"fp{i}",
            }
            for i, pair in enumerate(pairs)
        ],
        "fingerprint": f"audit-{day}",
    }
    (directory / f"hunter-pairs-{day.replace('-', '')}-audit.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


@pytest.fixture()
def workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    snapshot_dir = tmp_path / "snapshots"
    data_dir = tmp_path / "prices"
    store_dir = tmp_path / "store"
    snapshot_dir.mkdir()
    data_dir.mkdir()
    store_dir.mkdir()
    _write_snapshot(snapshot_dir, ["SOL/USDT:USDT"])
    start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
    _write_feather(data_dir / "BTC_USDT_USDT-1h-futures.feather", start, 72, 100.0)
    _write_feather(data_dir / "SOL_USDT_USDT-1h-futures.feather", start, 72, 200.0)
    return snapshot_dir, data_dir, store_dir


def test_evaluate_and_report_roundtrip(workspace: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(store_dir),
            "--all-matured",
            "--horizons", "1d",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["command"] == "evaluate"
    assert payload["cohorts_evaluated"] == 1
    assert payload["terminal_state_counts"]["OUTCOME_AVAILABLE"] == 1
    assert payload["_safety_notice"]

    rc = outcome_cli_main(
        ["report", "--store-dir", str(store_dir), "--all-matured", "--horizons", "1d"]
    )
    assert rc == 0
    report_payload = json.loads(capsys.readouterr().out)
    assert report_payload["command"] == "report"
    assert report_payload["cohort_count"] == 1
    cohort = report_payload["cohorts"][0]
    assert "top_5_return_pct_1d" in cohort["metrics"]
    assert "spearman_rank_return_1d" in cohort["metrics"]
    assert "benchmark_relative_return_pct_1d" in cohort["metrics"]


def test_report_markdown_format(workspace: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    assert outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(store_dir),
            "--all-matured",
            "--horizons", "1d",
        ]
    ) == 0
    capsys.readouterr()
    rc = outcome_cli_main(
        ["report", "--store-dir", str(store_dir), "--all-matured", "--horizons", "1d", "--format", "markdown"]
    )
    assert rc == 0
    text = capsys.readouterr().out
    assert "SPEC-076 Outcome Evaluation Report" in text
    assert "snapshot_date" in text
    assert "Research-only artifact" in text


def test_evaluate_requires_selection(workspace: tuple[Path, Path, Path]) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    with pytest.raises(SystemExit):
        outcome_cli_main(
            [
                "evaluate",
                "--snapshot-dir", str(snapshot_dir),
                "--data-dir", str(data_dir),
                "--store-dir", str(store_dir),
                "--horizons", "1d",
            ]
        )


def test_evaluate_rejects_invalid_coverage(workspace: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(store_dir),
            "--all-matured",
            "--horizons", "1d",
            "--min-window-coverage", "1.5",
        ]
    )
    assert rc == 2
    assert "min_window_coverage" in capsys.readouterr().err


def test_evaluate_rejects_invalid_horizon(workspace: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(store_dir),
            "--all-matured",
            "--horizons", "1w",
        ]
    )
    assert rc == 2


def test_evaluate_as_of_range(workspace: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(store_dir),
            "--as-of", "2026-01-10:2026-01-10",
            "--horizons", "1d",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cohorts_evaluated"] == 1


def test_top_level_dispatch_help(capsys: pytest.CaptureFixture[str]) -> None:
    rc = hunter_main(["--help"])
    assert rc == 0
    text = capsys.readouterr().out
    assert "outcome evaluate" in text
    assert "outcome report" in text


def test_evaluate_rejects_non_distinct_store_dir(
    workspace: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot_dir, data_dir, _store_dir = workspace
    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(snapshot_dir),
            "--all-matured",
            "--horizons", "1d",
        ]
    )
    assert rc == 2
    assert "distinct" in capsys.readouterr().err

    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(data_dir),
            "--all-matured",
            "--horizons", "1d",
        ]
    )
    assert rc == 2
    assert "distinct" in capsys.readouterr().err


def test_report_includes_calibration_gate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    snapshot_dir = tmp_path / "snapshots"
    data_dir = tmp_path / "prices"
    store_dir = tmp_path / "store"
    snapshot_dir.mkdir()
    data_dir.mkdir()
    store_dir.mkdir()

    start = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    for day in ("2026-01-08", "2026-01-09", "2026-01-10"):
        _write_snapshot(snapshot_dir, ["SOL/USDT:USDT"], day=day)
    _write_feather(data_dir / "BTC_USDT_USDT-1h-futures.feather", start, 400, 100.0)
    _write_feather(data_dir / "SOL_USDT_USDT-1h-futures.feather", start, 400, 200.0)

    assert outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(store_dir),
            "--all-matured",
            "--horizons", "1d",
        ]
    ) == 0
    capsys.readouterr()

    rc = outcome_cli_main(
        ["report", "--store-dir", str(store_dir), "--all-matured", "--horizons", "1d"]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cohort_count"] == 3
    assert payload["calibration_gate"]
    profile_info = payload["calibration_gate"]["V2_RS_LIQUIDITY"]
    assert "1d" in profile_info
    info = profile_info["1d"]
    assert info["matured_cohort_count"] == 3
    assert info["threshold"] == 30
    assert info["recommended"] == 60
    assert info["eligible"] is False
    assert info["eligible_recommended"] is False


@pytest.mark.parametrize(
    "coverage_arg",
    [
        ("--min-window-coverage", "NaN"),
        ("--min-window-coverage", "sNaN"),
        ("--min-window-coverage", "Infinity"),
        ("--min-window-coverage=", "-Infinity"),
        ("--min-window-coverage", "Inf"),
        ("--min-window-coverage=", "-Inf"),
    ],
)
def test_evaluate_rejects_non_finite_coverage(
    workspace: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
    coverage_arg: tuple[str, str],
) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    flag, value = coverage_arg
    if flag.endswith("="):
        coverage_tokens = [f"{flag}{value}"]
    else:
        coverage_tokens = [flag, value]
    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(store_dir),
            "--all-matured",
            "--horizons", "1d",
            *coverage_tokens,
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "min-window-coverage" in err


@pytest.mark.parametrize(
    "coverage_value, should_succeed",
    [
        ("0", False),
        ("0.0001", True),
        ("0.95", True),
        ("1", True),
        ("1.0001", False),
        ("1.5", False),
    ],
)
def test_evaluate_coverage_range_boundary(
    workspace: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
    coverage_value: str,
    should_succeed: bool,
) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(store_dir),
            "--all-matured",
            "--horizons", "1d",
            "--min-window-coverage", coverage_value,
        ]
    )
    if should_succeed:
        assert rc == 0
    else:
        assert rc == 2
        assert "min_window_coverage" in capsys.readouterr().err


def test_evaluate_rejects_nested_directories(
    workspace: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    nested_store = snapshot_dir / "store"
    nested_store.mkdir()
    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(nested_store),
            "--all-matured",
            "--horizons", "1d",
        ]
    )
    assert rc == 2
    assert "distinct" in capsys.readouterr().err

    nested_store2 = data_dir / "store"
    nested_store2.mkdir()
    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(nested_store2),
            "--all-matured",
            "--horizons", "1d",
        ]
    )
    assert rc == 2
    assert "distinct" in capsys.readouterr().err


def test_evaluate_accepts_sibling_directories(
    workspace: tuple[Path, Path, Path]
) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(store_dir),
            "--all-matured",
            "--horizons", "1d",
        ]
    )
    assert rc == 0


def test_evaluate_rejects_relative_equivalent_directories(
    workspace: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    # store_dir resolves to the same absolute path as snapshot_dir even though
    # the raw strings differ.
    equivalent_store = snapshot_dir / "." / ".." / snapshot_dir.name
    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(equivalent_store),
            "--all-matured",
            "--horizons", "1d",
        ]
    )
    assert rc == 2
    assert "distinct" in capsys.readouterr().err

    # Second scenario: data_dir resolves to the same directory as snapshot_dir.
    equivalent_data = snapshot_dir / "." / ".." / snapshot_dir.name
    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(equivalent_data),
            "--store-dir", str(store_dir),
            "--all-matured",
            "--horizons", "1d",
        ]
    )
    assert rc == 2
    assert "distinct" in capsys.readouterr().err


def test_evaluate_rejects_missing_input_directory(
    workspace: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    missing = data_dir / "does_not_exist"
    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(missing),
            "--store-dir", str(store_dir),
            "--all-matured",
            "--horizons", "1d",
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "does not exist" in err


def test_evaluate_rejects_file_as_input_directory(
    workspace: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    file_path = snapshot_dir / "not_a_dir.txt"
    file_path.write_text("x", encoding="utf-8")
    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(file_path),
            "--data-dir", str(data_dir),
            "--store-dir", str(store_dir),
            "--all-matured",
            "--horizons", "1d",
        ]
    )
    assert rc == 2
    assert "not a directory" in capsys.readouterr().err


def test_evaluate_accepts_valid_single_as_of_date(
    workspace: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(store_dir),
            "--as-of", "2026-01-10",
            "--horizons", "1d",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cohorts_evaluated"] == 1


def test_evaluate_accepts_inclusive_as_of_range(
    workspace: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(store_dir),
            "--as-of", "2026-01-01:2026-01-31",
            "--horizons", "1d",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cohorts_evaluated"] == 1


@pytest.mark.parametrize(
    "as_of_value, expected_snippet",
    [
        ("2026-01-10:2026-01-09", "after end"),
        ("not-a-date", "invalid --as-of date"),
        ("2026-01-10:bad", "invalid --as-of date"),
        ("bad:2026-01-10", "invalid --as-of date"),
    ],
)
def test_evaluate_rejects_invalid_as_of(
    workspace: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
    as_of_value: str,
    expected_snippet: str,
) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    rc = outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(store_dir),
            "--as-of", as_of_value,
            "--horizons", "1d",
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert expected_snippet in err


def test_report_rejects_malformed_persisted_snapshot_date(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    summaries_dir = store_dir / "summaries"
    summaries_dir.mkdir(parents=True)
    bad_summary = {
        "snapshot_date": "not-a-date",
        "ranking_profile": "V2_RS_LIQUIDITY",
        "outcome_horizon": "1d",
        "fingerprint": "fp",
    }
    (summaries_dir / "bad-summary.json").write_text(
        json.dumps(bad_summary), encoding="utf-8"
    )
    rc = outcome_cli_main(
        ["report", "--store-dir", str(store_dir), "--all-matured", "--horizons", "1d"]
    )
    assert rc == 2
    assert "malformed snapshot_date" in capsys.readouterr().err


def test_report_date_filter_inclusive(
    workspace: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    assert outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(store_dir),
            "--all-matured",
            "--horizons", "1d",
        ]
    ) == 0
    capsys.readouterr()

    rc = outcome_cli_main(
        ["report", "--store-dir", str(store_dir), "--as-of", "2026-01-10:2026-01-10", "--horizons", "1d"]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cohort_count"] == 1


def test_report_without_date_filter_preserves_all_matured(
    workspace: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    assert outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(store_dir),
            "--all-matured",
            "--horizons", "1d",
        ]
    ) == 0
    capsys.readouterr()

    rc = outcome_cli_main(
        ["report", "--store-dir", str(store_dir), "--all-matured", "--horizons", "1d"]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cohort_count"] == 1


def test_report_markdown_includes_calibration_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot_dir = tmp_path / "snapshots"
    data_dir = tmp_path / "prices"
    store_dir = tmp_path / "store"
    snapshot_dir.mkdir()
    data_dir.mkdir()
    store_dir.mkdir()
    _write_snapshot(snapshot_dir, ["SOL/USDT:USDT"], day="2026-01-10")
    start = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    _write_feather(data_dir / "BTC_USDT_USDT-1h-futures.feather", start, 400, 100.0)
    _write_feather(data_dir / "SOL_USDT_USDT-1h-futures.feather", start, 400, 200.0)

    assert outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(store_dir),
            "--all-matured",
            "--horizons", "1d",
        ]
    ) == 0
    capsys.readouterr()

    rc = outcome_cli_main(
        ["report", "--store-dir", str(store_dir), "--all-matured", "--horizons", "1d", "--format", "markdown"]
    )
    assert rc == 0
    text = capsys.readouterr().out
    assert "## Calibration gate" in text
    assert "matured_cohorts" in text


def test_unknown_outcome_command_rejected_by_argparse() -> None:
    with pytest.raises(SystemExit) as exc_info:
        outcome_cli_main(["unknowncmd", "--store-dir", "/tmp/store"])
    assert exc_info.value.code == 2


def test_top_level_dispatch_routes_known_commands(
    capsys: pytest.CaptureFixture[str]
) -> None:
    rc = hunter_main(["--help"])
    assert rc == 0
    text = capsys.readouterr().out
    assert "outcome evaluate" in text
    assert "outcome report" in text


def test_report_separates_invalid_cohorts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot_dir = tmp_path / "snapshots"
    data_dir = tmp_path / "prices"
    store_dir = tmp_path / "store"
    snapshot_dir.mkdir()
    data_dir.mkdir()
    store_dir.mkdir()
    _write_snapshot(snapshot_dir, ["SOL/USDT:USDT"], day="2026-01-10")
    payload = {
        "as_of_date": "2026-01-11",
        "ranking_profile": "V2_RS_LIQUIDITY",
        "schema_version": "hunter-ranking-input-v2",
        "selected": [
            {"pair": "SOL/USDT:USDT", "rank": 1, "selected": True, "rs_score": "90", "liquidity_score": "80", "reason_codes": [], "fingerprint": "fp"},
            {"pair": "SOL/USDT:USDT", "rank": 1, "selected": True, "rs_score": "90", "liquidity_score": "80", "reason_codes": [], "fingerprint": "fp"},
        ],
        "fingerprint": "audit-duplicate",
    }
    (snapshot_dir / "hunter-pairs-20260111-audit.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    start = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    _write_feather(data_dir / "BTC_USDT_USDT-1h-futures.feather", start, 400, 100.0)
    _write_feather(data_dir / "SOL_USDT_USDT-1h-futures.feather", start, 400, 200.0)

    assert outcome_cli_main(
        [
            "evaluate",
            "--snapshot-dir", str(snapshot_dir),
            "--data-dir", str(data_dir),
            "--store-dir", str(store_dir),
            "--all-matured",
            "--horizons", "1d",
        ]
    ) == 0
    capsys.readouterr()

    rc = outcome_cli_main(
        ["report", "--store-dir", str(store_dir), "--all-matured", "--horizons", "1d"]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cohort_count"] == 1
    assert payload["invalid_cohort_count"] == 1
    assert len(payload["cohorts"]) == 1
    assert payload["cohorts"][0]["ranking_profile"] == "V2_RS_LIQUIDITY"
    assert payload["invalid_cohorts"][0]["ranking_profile"] is None
    assert "SNAPSHOT_INVALID" in payload["invalid_cohorts"][0]["terminal_state_counts"]
    # Calibration gate must only count the valid cohort.
    assert payload["calibration_gate"]["V2_RS_LIQUIDITY"]["1d"]["matured_cohort_count"] == 1


def test_report_legacy_summary_missing_counts_show_null(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    summaries_dir = store_dir / "summaries"
    summaries_dir.mkdir(parents=True)
    legacy = {
        "schema_version": "spec-076-store-v1",
        "snapshot_date": "2026-01-10",
        "ranking_profile": "V2_RS_LIQUIDITY",
        "outcome_horizon": "1d",
        "cohort_size": 1,
        "available_count": 1,
        "unavailable_count": 0,
        "top_5_return_pct": None,
        "top_10_return_pct": None,
        "top_20_return_pct": None,
        "top_30_return_pct": None,
        "metadata": {"terminal_state_counts": {"OUTCOME_AVAILABLE": 1}},
        "fingerprint": "legacy-fp",
    }
    (summaries_dir / "2026-01-10__V2_RS_LIQUIDITY__1d.json").write_text(
        json.dumps(legacy), encoding="utf-8"
    )

    rc = outcome_cli_main(
        ["report", "--store-dir", str(store_dir), "--all-matured", "--horizons", "1d"]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cohort_count"] == 1
    metrics = payload["cohorts"][0]["metrics"]
    assert metrics["top_5_available_count_1d"] is None
    assert metrics["top_10_available_count_1d"] is None
    assert metrics["top_20_available_count_1d"] is None
    assert metrics["top_30_available_count_1d"] is None



def test_report_markdown_shows_top_n_counts(
    workspace: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    assert (
        outcome_cli_main(
            [
                "evaluate",
                "--snapshot-dir",
                str(snapshot_dir),
                "--data-dir",
                str(data_dir),
                "--store-dir",
                str(store_dir),
                "--all-matured",
                "--horizons",
                "1d",
            ]
        )
        == 0
    )
    capsys.readouterr()
    rc = outcome_cli_main(
        [
            "report",
            "--store-dir",
            str(store_dir),
            "--all-matured",
            "--horizons",
            "1d",
            "--format",
            "markdown",
        ]
    )
    assert rc == 0
    text = capsys.readouterr().out
    assert "top_5_count" in text
    assert "top_10_count" in text
    assert "top_20_count" in text
    assert "top_30_count" in text


def test_report_json_and_markdown_share_same_top_n_counts(
    workspace: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    snapshot_dir, data_dir, store_dir = workspace
    args = [
        "evaluate",
        "--snapshot-dir",
        str(snapshot_dir),
        "--data-dir",
        str(data_dir),
        "--store-dir",
        str(store_dir),
        "--all-matured",
        "--horizons",
        "1d",
    ]
    assert outcome_cli_main(args) == 0
    capsys.readouterr()

    rc = outcome_cli_main(
        ["report", "--store-dir", str(store_dir), "--all-matured", "--horizons", "1d"]
    )
    assert rc == 0
    json_payload = json.loads(capsys.readouterr().out)
    json_counts = json_payload["cohorts"][0]["metrics"]

    rc = outcome_cli_main(
        [
            "report",
            "--store-dir",
            str(store_dir),
            "--all-matured",
            "--horizons",
            "1d",
            "--format",
            "markdown",
        ]
    )
    assert rc == 0
    markdown = capsys.readouterr().out

    for cut in (5, 10, 20, 30):
        count = json_counts[f"top_{cut}_available_count_1d"]
        # Markdown uses str(count), so None is represented as "None".
        assert str(count) in markdown


def test_report_markdown_partial_top_five_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    summaries_dir = store_dir / "summaries"
    summaries_dir.mkdir(parents=True)
    summary = {
        "schema_version": "spec-076-store-v1",
        "snapshot_date": "2026-01-10",
        "ranking_profile": "V2_RS_LIQUIDITY",
        "outcome_horizon": "1d",
        "cohort_size": 4,
        "available_count": 2,
        "unavailable_count": 2,
        "top_5_return_pct": "2.5",
        "top_5_available_count": 2,
        "top_10_return_pct": "2.5",
        "top_10_available_count": 2,
        "top_20_return_pct": "2.5",
        "top_20_available_count": 2,
        "top_30_return_pct": "2.5",
        "top_30_available_count": 2,
        "metadata": {"terminal_state_counts": {"OUTCOME_AVAILABLE": 2, "OUTCOME_UNAVAILABLE_GAP": 2}},
        "fingerprint": "partial-fp",
    }
    (summaries_dir / "2026-01-10__V2_RS_LIQUIDITY__1d.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )

    rc = outcome_cli_main(
        [
            "report",
            "--store-dir",
            str(store_dir),
            "--all-matured",
            "--horizons",
            "1d",
            "--format",
            "markdown",
        ]
    )
    assert rc == 0
    text = capsys.readouterr().out
    # Verify the top_5 return and its count appear adjacent in the markdown row.
    assert "| 2.5 | 2 |" in text
