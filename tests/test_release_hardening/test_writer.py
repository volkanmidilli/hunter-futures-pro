"""Tests for hunter.release_hardening.writer."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.release_hardening.engine import build_release_hardening_report
from hunter.release_hardening.models import (
    PackageDeclaration,
    ReleaseHardeningInput,
    ReleaseHardeningState,
)
from hunter.release_hardening.writer import (
    DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    atomic_write_csv_release_hardening_report,
    atomic_write_json_release_hardening_report,
    atomic_write_markdown_release_hardening_report,
    release_hardening_report_to_csv_text,
    release_hardening_report_to_dict,
    release_hardening_report_to_json_text,
    release_hardening_report_to_markdown_text,
    write_release_hardening_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def generated_at() -> datetime:
    return datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def good_package(generated_at: datetime) -> PackageDeclaration:
    return PackageDeclaration(
        package_id="good_pkg",
        package_name="Good Package",
        module_path="hunter.good",
        expected_public_exports=("build_report",),
        actual_public_exports=("build_report", "__version__"),
        expected_modules=("__init__.py", "models.py", "engine.py", "writer.py"),
        actual_modules_present=("__init__.py", "models.py", "engine.py", "writer.py"),
        writer_default_paths=("data/good/output.json",),
        test_default_paths=("tests/test_good/test_output.json",),
        safety_notices=("Research-only output, not trading advice.",),
        markdown_disclaimer=(
            "This report is a human-audit research artifact. "
            "It is not trading advice and not a certification of trading readiness."
        ),
        version="0.33.0-dev",
    )


@pytest.fixture
def pass_report(
    good_package: PackageDeclaration, generated_at: datetime
) -> object:
    inp = ReleaseHardeningInput(
        packages=(good_package,),
        project_version="0.33.0-dev",
        generated_at=generated_at,
    )
    return build_release_hardening_report(inp)


@pytest.fixture
def degraded_report(generated_at: datetime) -> object:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_modules=("__init__.py",),
        actual_modules_present=("__init__.py",),
        writer_default_paths=("data/pkg/output.json",),
        test_default_paths=("data/pkg/test_output.json",),  # overlaps production
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    inp = ReleaseHardeningInput(
        packages=(pkg,), generated_at=generated_at
    )
    return build_release_hardening_report(inp)


@pytest.fixture
def blocked_report(generated_at: datetime) -> object:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_modules=("__init__.py", "models.py"),
        actual_modules_present=("__init__.py",),
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    inp = ReleaseHardeningInput(packages=(pkg,), generated_at=generated_at)
    return build_release_hardening_report(inp)


# ---------------------------------------------------------------------------
# Dict conversion
# ---------------------------------------------------------------------------


def test_dict_conversion_includes_report_fields(pass_report: object) -> None:
    data = release_hardening_report_to_dict(pass_report)
    assert data["state"] == pass_report.state.value
    assert data["generated_at"] == "2026-07-04T12:00:00+00:00"
    assert "checks" in data
    assert "data_quality" in data
    assert "safety_flags" in data


def test_dict_conversion_safety_notice_first(pass_report: object) -> None:
    data = release_hardening_report_to_dict(pass_report)
    keys = list(data.keys())
    assert keys[0] == "safety_notice"
    assert keys[1] == "generated_at"


def test_dict_conversion_serializes_enums_as_values(pass_report: object) -> None:
    data = release_hardening_report_to_dict(pass_report)
    assert data["state"] == "pass"
    assert all(isinstance(code, str) for code in data["reason_codes"])


def test_dict_conversion_serializes_safety_flags(pass_report: object) -> None:
    data = release_hardening_report_to_dict(pass_report)
    flags = data["safety_flags"]
    assert isinstance(flags, dict)
    assert flags["is_safe"] is True


def test_dict_conversion_does_not_mutate_report(pass_report: object) -> None:
    original = release_hardening_report_to_dict(pass_report)
    data = release_hardening_report_to_dict(pass_report)
    data["extra"] = "extra"
    assert "extra" not in original


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


def test_json_parseable(pass_report: object) -> None:
    text = release_hardening_report_to_json_text(pass_report)
    parsed = json.loads(text)
    assert parsed["state"] == "pass"
    assert parsed["generated_at"] == "2026-07-04T12:00:00+00:00"


def test_json_deterministic(pass_report: object) -> None:
    t1 = release_hardening_report_to_json_text(pass_report)
    t2 = release_hardening_report_to_json_text(pass_report)
    assert t1 == t2


def test_json_contains_safety_notice(pass_report: object) -> None:
    text = release_hardening_report_to_json_text(pass_report)
    assert "human-audit research artifact" in text
    assert "not trading advice" in text


def test_json_blocked_report(blocked_report: object) -> None:
    text = release_hardening_report_to_json_text(blocked_report)
    parsed = json.loads(text)
    assert parsed["state"] == "blocked"
    assert parsed["data_quality"]["blocked_count"] > 0


def test_json_degraded_report(degraded_report: object) -> None:
    text = release_hardening_report_to_json_text(degraded_report)
    parsed = json.loads(text)
    assert parsed["state"] == "degraded"
    assert parsed["data_quality"]["degraded_count"] > 0


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def _csv_rows(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def test_csv_header(pass_report: object) -> None:
    text = release_hardening_report_to_csv_text(pass_report)
    rows = _csv_rows(text)
    expected_columns = [
        "report_id",
        "generated_at",
        "check_id",
        "package_id",
        "category",
        "state",
        "severity",
        "reason_codes",
        "message",
    ]
    assert list(rows[0].keys()) == expected_columns


def test_csv_rows_are_deterministic(pass_report: object) -> None:
    text1 = release_hardening_report_to_csv_text(pass_report)
    text2 = release_hardening_report_to_csv_text(pass_report)
    assert text1 == text2


def test_csv_includes_check_results(pass_report: object) -> None:
    text = release_hardening_report_to_csv_text(pass_report)
    rows = _csv_rows(text)
    assert len(rows) > 0
    categories = {row["category"] for row in rows}
    assert "public_exports" in categories


def test_csv_severity_for_blocked(blocked_report: object) -> None:
    text = release_hardening_report_to_csv_text(blocked_report)
    rows = _csv_rows(text)
    blocked_rows = [r for r in rows if r["state"] == "blocked"]
    assert blocked_rows
    assert all(r["severity"] == "blocking" for r in blocked_rows)


def test_csv_severity_for_degraded(degraded_report: object) -> None:
    text = release_hardening_report_to_csv_text(degraded_report)
    rows = _csv_rows(text)
    degraded_rows = [r for r in rows if r["state"] == "degraded"]
    assert degraded_rows
    assert all(r["severity"] == "advisory" for r in degraded_rows)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def test_markdown_starts_with_h1(pass_report: object) -> None:
    text = release_hardening_report_to_markdown_text(pass_report)
    assert text.startswith("# Release Hardening Report")


def test_markdown_contains_safety_notice(pass_report: object) -> None:
    text = release_hardening_report_to_markdown_text(pass_report)
    assert "human-audit research artifact" in text
    assert "not trading advice" in text
    assert "not a certification of trading readiness" in text


def test_markdown_not_approval_or_certification(pass_report: object) -> None:
    text = release_hardening_report_to_markdown_text(pass_report).lower()
    assert "not a certification of trading readiness" in text
    assert "not a trading signal" in text
    assert "approval" not in text or "not" in text


def test_markdown_contains_summary(pass_report: object) -> None:
    text = release_hardening_report_to_markdown_text(pass_report)
    assert "## Summary" in text
    assert "total_checks" in text


def test_markdown_contains_data_quality(pass_report: object) -> None:
    text = release_hardening_report_to_markdown_text(pass_report)
    assert "## Data Quality" in text


def test_markdown_contains_check_results(pass_report: object) -> None:
    text = release_hardening_report_to_markdown_text(pass_report)
    assert "## Checks by Category" in text
    assert "public_exports" in text


def test_markdown_contains_safety_flags(pass_report: object) -> None:
    text = release_hardening_report_to_markdown_text(pass_report)
    assert "## Safety Flags" in text
    assert "is_safe" in text


def test_markdown_no_actionable_language(pass_report: object) -> None:
    text = release_hardening_report_to_markdown_text(pass_report).lower()
    # The safety notice may include "order placement" as a negative instruction
    # ("Do not use it for ... order placement"). Reject standalone actionable
    # recommendation language, not the safety disclaimer itself.
    assert "buy signal" not in text
    assert "sell signal" not in text
    assert "buy now" not in text
    assert "sell now" not in text
    assert "place orders" not in text
    assert "execute orders" not in text


def test_markdown_blocked_report(blocked_report: object) -> None:
    text = release_hardening_report_to_markdown_text(blocked_report)
    assert "## Summary" in text
    assert "blocked" in text


def test_markdown_degraded_report(degraded_report: object) -> None:
    text = release_hardening_report_to_markdown_text(degraded_report)
    assert "## Summary" in text
    assert "degraded" in text


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


def test_atomic_write_json_creates_file(pass_report: object, tmp_path: Path) -> None:
    target = tmp_path / "report.json"
    path = atomic_write_json_release_hardening_report(pass_report, target)
    assert path == target
    assert target.exists()
    parsed = json.loads(target.read_text())
    assert parsed["state"] == "pass"


def test_atomic_write_csv_creates_file(pass_report: object, tmp_path: Path) -> None:
    target = tmp_path / "report.csv"
    path = atomic_write_csv_release_hardening_report(pass_report, target)
    assert path == target
    assert target.exists()
    rows = _csv_rows(target.read_text())
    assert rows


def test_atomic_write_markdown_creates_file(
    pass_report: object, tmp_path: Path
) -> None:
    target = tmp_path / "report.md"
    path = atomic_write_markdown_release_hardening_report(pass_report, target)
    assert path == target
    assert target.exists()
    assert target.read_text().startswith("# Release Hardening Report")


def test_parent_directories_created(pass_report: object, tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dirs" / "report.json"
    atomic_write_json_release_hardening_report(pass_report, target)
    assert target.exists()


def test_write_report_all_formats(pass_report: object, tmp_path: Path) -> None:
    json_path = tmp_path / "out.json"
    csv_path = tmp_path / "out.csv"
    md_path = tmp_path / "out.md"
    out_json, out_csv, out_md = write_release_hardening_report(
        pass_report, json_path=json_path, csv_path=csv_path, md_path=md_path
    )
    assert out_json == json_path
    assert out_csv == csv_path
    assert out_md == md_path
    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()


def test_write_report_skips_none(pass_report: object, tmp_path: Path) -> None:
    json_path = tmp_path / "out.json"
    out_json, out_csv, out_md = write_release_hardening_report(
        pass_report, json_path=json_path, csv_path=None, md_path=None
    )
    assert out_json == json_path
    assert out_csv is None
    assert out_md is None


def test_write_report_defaults(pass_report: object, tmp_path: Path) -> None:
    # Default paths are relative to cwd; override via tmp_path to stay safe.
    out_json, out_csv, out_md = write_release_hardening_report(
        pass_report,
        json_path=tmp_path / DEFAULT_JSON_PATH,
        csv_path=tmp_path / DEFAULT_CSV_PATH,
        md_path=tmp_path / DEFAULT_MD_PATH,
    )
    assert out_json is not None
    assert out_csv is not None
    assert out_md is not None
    assert out_json.exists()
    assert out_csv.exists()
    assert out_md.exists()


def test_atomic_write_does_not_mutate_report(
    pass_report: object, tmp_path: Path
) -> None:
    original_state = pass_report.state
    atomic_write_json_release_hardening_report(pass_report, tmp_path / "r.json")
    assert pass_report.state is original_state


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


def test_public_writer_exports() -> None:
    from hunter.release_hardening import (
        DEFAULT_CSV_PATH,
        DEFAULT_JSON_PATH,
        DEFAULT_MD_PATH,
        atomic_write_csv_release_hardening_report,
        atomic_write_json_release_hardening_report,
        atomic_write_markdown_release_hardening_report,
        release_hardening_report_to_csv_text,
        release_hardening_report_to_dict,
        release_hardening_report_to_json_text,
        release_hardening_report_to_markdown_text,
        write_release_hardening_report,
    )

    assert release_hardening_report_to_dict is not None
    assert release_hardening_report_to_json_text is not None
    assert release_hardening_report_to_csv_text is not None
    assert release_hardening_report_to_markdown_text is not None
    assert atomic_write_json_release_hardening_report is not None
    assert atomic_write_csv_release_hardening_report is not None
    assert atomic_write_markdown_release_hardening_report is not None
    assert write_release_hardening_report is not None
    assert DEFAULT_JSON_PATH is not None
    assert DEFAULT_CSV_PATH is not None
    assert DEFAULT_MD_PATH is not None


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_full_report_writer_determinism(pass_report: object, tmp_path: Path) -> None:
    json1 = tmp_path / "a.json"
    json2 = tmp_path / "b.json"
    atomic_write_json_release_hardening_report(pass_report, json1)
    atomic_write_json_release_hardening_report(pass_report, json2)
    assert json1.read_text() == json2.read_text()
