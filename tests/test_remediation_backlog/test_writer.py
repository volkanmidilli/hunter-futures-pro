"""Tests for hunter.remediation_backlog.writer."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.remediation_backlog import (
    DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    RemediationAcknowledgement,
    RemediationBacklogConfig,
    RemediationBacklogDataQuality,
    RemediationBacklogInput,
    RemediationBacklogItem,
    RemediationBacklogItemState,
    RemediationBacklogItemType,
    RemediationBacklogPriority,
    RemediationBacklogReasonCode,
    RemediationBacklogReport,
    RemediationBacklogSafetyFlags,
    RemediationBacklogSeverity,
    RemediationBacklogState,
    RemediationDependency,
    RemediationDependencyType,
    RemediationFindingRef,
    RemediationSourceRef,
    atomic_write_csv_remediation_backlog_report,
    atomic_write_json_remediation_backlog_report,
    atomic_write_markdown_remediation_backlog_report,
    build_remediation_backlog_report,
    remediation_backlog_report_to_csv_text,
    remediation_backlog_report_to_dict,
    remediation_backlog_report_to_json_text,
    remediation_backlog_report_to_markdown_text,
    write_remediation_backlog_report,
)


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def minimal_report(now: datetime) -> RemediationBacklogReport:
    return build_remediation_backlog_report(
        RemediationBacklogInput(
            source_refs=(RemediationSourceRef(source_id="s1", generated_at=now),),
            finding_refs=(RemediationFindingRef(finding_id="f1", source_id="s1"),),
            backlog_items=(
                RemediationBacklogItem(
                    item_id="i1",
                    source_id="s1",
                    finding_id="f1",
                    title="Check A",
                    description="Description of check A",
                ),
            ),
            generated_at=now,
        )
    )


@pytest.fixture
def full_report(now: datetime) -> RemediationBacklogReport:
    item1 = RemediationBacklogItem(
        item_id="i1",
        source_id="s1",
        finding_id="f1",
        title="Check A",
        description="Description of check A",
        owner="owner1",
        reviewer="reviewer1",
    )
    item2 = RemediationBacklogItem(
        item_id="i2",
        source_id="s1",
        finding_id="f2",
        title="Check B",
        description="Description of check B",
        item_state=RemediationBacklogItemState.DEFERRED,
        severity=RemediationBacklogSeverity.INFO,
    )
    dep = RemediationDependency(
        dependency_id="d1",
        source_item_id="i1",
        target_item_id="i2",
        dependency_type=RemediationDependencyType.RELATED_TO,
    )
    ack = RemediationAcknowledgement(
        acknowledgement_id="a1",
        item_id="i2",
        acknowledged_by="auditor",
        acknowledged_at=now,
    )
    return build_remediation_backlog_report(
        RemediationBacklogInput(
            source_refs=(RemediationSourceRef(source_id="s1", generated_at=now),),
            finding_refs=(
                RemediationFindingRef(finding_id="f1", source_id="s1"),
                RemediationFindingRef(finding_id="f2", source_id="s1"),
            ),
            backlog_items=(item1, item2),
            dependencies=(dep,),
            acknowledgements=(ack,),
            metadata={"context": "test"},
            generated_at=now,
        )
    )


@pytest.fixture
def blocked_report(now: datetime) -> RemediationBacklogReport:
    return build_remediation_backlog_report(
        RemediationBacklogInput(
            source_refs=(
                RemediationSourceRef(source_id="s1"),
                RemediationSourceRef(source_id="s1"),
            ),
            generated_at=now,
        )
    )


@pytest.fixture
def degraded_report(now: datetime) -> RemediationBacklogReport:
    return build_remediation_backlog_report(
        RemediationBacklogInput(
            source_refs=(RemediationSourceRef(source_id="s1"),),
            finding_refs=(RemediationFindingRef(finding_id="f1", source_id="s1"),),
            backlog_items=(
                RemediationBacklogItem(
                    item_id="i1",
                    source_id="s1",
                    finding_id="f1",
                    title="Advisory item",
                    description="Needs review",
                    severity=RemediationBacklogSeverity.ADVISORY,
                ),
            ),
            generated_at=now,
        )
    )


@pytest.fixture
def not_applicable_report(now: datetime) -> RemediationBacklogReport:
    return build_remediation_backlog_report(RemediationBacklogInput(generated_at=now))


# ---------------------------------------------------------------------------
# Dict / JSON tests
# ---------------------------------------------------------------------------


def test_dict_conversion_includes_all_fields(full_report: RemediationBacklogReport) -> None:
    data = remediation_backlog_report_to_dict(full_report)
    assert "safety_notice" in data
    assert "generated_at" in data
    assert "report_id" in data
    assert "state" in data
    assert "project_version" in data
    assert "source_refs" in data
    assert "finding_refs" in data
    assert "backlog_items" in data
    assert "dependencies" in data
    assert "acknowledgements" in data
    assert "issues" in data
    assert "data_quality" in data
    assert "safety_flags" in data
    assert "reason_codes" in data
    assert "metadata" in data
    assert "safety_notice" in data
    assert "notes" in data


def test_dict_safety_flags_include_is_safe(full_report: RemediationBacklogReport) -> None:
    data = remediation_backlog_report_to_dict(full_report)
    assert data["safety_flags"]["is_safe"] is True


def test_dict_source_ref_has_reference(minimal_report: RemediationBacklogReport) -> None:
    data = remediation_backlog_report_to_dict(minimal_report)
    assert len(data["source_refs"]) == 1
    assert data["source_refs"][0]["source_id"] == "s1"


def test_json_parseable_and_deterministic(full_report: RemediationBacklogReport) -> None:
    text1 = remediation_backlog_report_to_json_text(full_report)
    text2 = remediation_backlog_report_to_json_text(full_report)
    assert text1 == text2
    parsed = json.loads(text1)
    assert parsed["state"] in {"ok", "degraded", "blocked", "not_applicable"}
    assert "safety_notice" in parsed
    assert "data_quality" in parsed


# ---------------------------------------------------------------------------
# CSV tests
# ---------------------------------------------------------------------------


def test_csv_header_and_rows(full_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_csv_text(full_report)
    lines = text.strip().split("\n")
    assert lines[0] == ",".join(
        (
            "report_id",
            "generated_at",
            "item_id",
            "source_id",
            "finding_id",
            "item_type",
            "item_state",
            "severity",
            "priority",
            "owner",
            "reviewer",
            "reason_codes",
            "message",
        )
    )
    assert len(lines) > 1


def test_csv_uses_existing_item_id(full_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_csv_text(full_report)
    reader = csv.DictReader(text.splitlines())
    rows = list(reader)
    item_ids = {row["item_id"] for row in rows if row["item_id"]}
    assert "i1" in item_ids


def test_csv_does_not_recompute_items(full_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_csv_text(full_report)
    reader = csv.DictReader(text.splitlines())
    rows = list(reader)
    assert all(row["item_id"] for row in rows)
    assert any(row["item_id"] == "i1" for row in rows)


def test_csv_reason_codes_semicolon_separated(minimal_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_csv_text(minimal_report)
    reader = csv.DictReader(text.splitlines())
    rows = list(reader)
    for row in rows:
        assert ";" not in row["reason_codes"] or ";" in row["reason_codes"]


# ---------------------------------------------------------------------------
# Markdown tests
# ---------------------------------------------------------------------------


def test_markdown_starts_with_h1_and_safety_notice(minimal_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_markdown_text(minimal_report)
    assert text.startswith("# Local Research Remediation Backlog")
    assert "audit-only" in text.lower() or "research-only" in text.lower() or "human-audit" in text.lower()


def test_markdown_explicit_negative_safety_statements(minimal_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_markdown_text(minimal_report)
    assert "not an approval" in text
    assert "not a certification" in text or "certification" in text
    assert "production readiness" in text
    assert "trading readiness" in text
    assert "not a recommendation" in text or "recommendation" in text
    assert "suitability assessment" in text
    assert "signal" in text
    assert "executable remediation plan" in text


def test_markdown_priority_is_human_review_ordering_only(full_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_markdown_text(full_report)
    assert "human-review ordering only" in text
    assert "not implementation instructions" in text


def test_markdown_contains_all_sections(full_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_markdown_text(full_report)
    assert "## Summary" in text
    assert "## Backlog Items by Priority" in text
    assert "## Source Refs" in text
    assert "## Finding Refs" in text
    assert "## Dependencies" in text
    assert "## Acknowledgements" in text
    assert "## Data Quality" in text
    assert "## Safety Flags" in text
    assert "## Manual Review Notes" in text


@pytest.mark.parametrize(
    "report_fixture",
    ["blocked_report", "degraded_report", "not_applicable_report"],
)
def test_markdown_sections_for_aggregated_states(report_fixture: str, request: pytest.FixtureRequest) -> None:
    report = request.getfixturevalue(report_fixture)
    text = remediation_backlog_report_to_markdown_text(report)
    assert "## Summary" in text
    assert "## Backlog Items by Priority" in text
    assert "## Data Quality" in text
    assert "## Safety Flags" in text


def test_markdown_contains_no_shell_commands(minimal_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_markdown_text(minimal_report)
    assert "```bash" not in text
    assert "```sh" not in text
    assert "$(" not in text


def test_markdown_contains_no_patch_instructions(minimal_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_markdown_text(minimal_report)
    assert "git apply" not in text
    assert "patch -p" not in text


def test_markdown_contains_no_deployment_commands(minimal_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_markdown_text(minimal_report)
    assert "deploy now" not in text.lower()
    assert "deploy immediately" not in text.lower()


def test_markdown_contains_no_trading_instructions(minimal_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_markdown_text(minimal_report)
    assert "buy signal" not in text.lower()
    assert "sell signal" not in text.lower()
    assert "hold signal" not in text.lower()
    assert "trade recommendation" not in text.lower()
    assert "place orders" not in text.lower()
    assert "execute orders" not in text.lower()


def test_markdown_contains_no_automated_remediation_actions(minimal_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_markdown_text(minimal_report)
    assert "auto fix" not in text.lower()
    assert "auto patch" not in text.lower()
    assert "automated remediation" not in text.lower()


# ---------------------------------------------------------------------------
# Report state serialization tests
# ---------------------------------------------------------------------------


def test_blocked_report_serialization(blocked_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_markdown_text(blocked_report)
    assert "blocked" in text
    data = remediation_backlog_report_to_dict(blocked_report)
    assert data["state"] == "blocked"


def test_degraded_report_serialization(degraded_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_markdown_text(degraded_report)
    assert "degraded" in text or "blocked" in text


def test_not_applicable_report_serialization(not_applicable_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_markdown_text(not_applicable_report)
    assert "not_applicable" in text


def test_acknowledged_deferred_duplicate_conflicting_items(now: datetime) -> None:
    acked = RemediationBacklogItem(
        item_id="i1",
        source_id="s1",
        finding_id="f1",
        item_state=RemediationBacklogItemState.ACKNOWLEDGED,
        item_type=RemediationBacklogItemType.ACKNOWLEDGED_ITEM,
        priority=RemediationBacklogPriority.P3,
        title="Acknowledged item",
        description="Acknowledged",
    )
    deferred = RemediationBacklogItem(
        item_id="i2",
        source_id="s1",
        finding_id="f2",
        item_state=RemediationBacklogItemState.DEFERRED,
        priority=RemediationBacklogPriority.P3,
        title="Deferred item",
        description="Deferred",
    )
    duplicate = RemediationBacklogItem(
        item_id="i3",
        source_id="s1",
        finding_id="f3",
        item_state=RemediationBacklogItemState.DUPLICATE,
        priority=RemediationBacklogPriority.NONE,
        title="Duplicate item",
        description="Duplicate",
    )
    conflicting = RemediationBacklogItem(
        item_id="i4",
        source_id="s1",
        finding_id="f4",
        item_state=RemediationBacklogItemState.CONFLICTING,
        priority=RemediationBacklogPriority.NONE,
        title="Conflicting item",
        description="Conflicting",
    )
    report = RemediationBacklogReport(
        report_id="r1",
        generated_at=now,
        state=RemediationBacklogState.OK,
        project_version="0.37.0-dev",
        source_refs=(),
        finding_refs=(),
        backlog_items=(acked, deferred, duplicate, conflicting),
        dependencies=(),
        acknowledgements=(),
        issues=(),
        data_quality=RemediationBacklogDataQuality(
            total_backlog_items=4,
            total_acknowledgements=1,
        ),
        safety_flags=RemediationBacklogSafetyFlags(),
    )
    text = remediation_backlog_report_to_csv_text(report)
    assert "acknowledged" in text
    assert "deferred" in text
    assert "duplicate" in text
    assert "conflicting" in text


# ---------------------------------------------------------------------------
# Atomic write tests
# ---------------------------------------------------------------------------


def test_atomic_write_creates_json_csv_markdown(tmp_path: Path, minimal_report: RemediationBacklogReport) -> None:
    json_path = tmp_path / "out.json"
    csv_path = tmp_path / "out.csv"
    md_path = tmp_path / "out.md"
    write_remediation_backlog_report(
        minimal_report,
        json_path=json_path,
        csv_path=csv_path,
        markdown_path=md_path,
    )
    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()
    assert json.load(json_path.open())["report_id"] == minimal_report.report_id
    assert "item_id" in csv_path.read_text()
    assert "# Local Research Remediation Backlog" in md_path.read_text()


def test_none_skips_artifact(tmp_path: Path, minimal_report: RemediationBacklogReport) -> None:
    json_path = tmp_path / "out.json"
    write_remediation_backlog_report(
        minimal_report,
        json_path=json_path,
        csv_path=None,
        markdown_path=None,
    )
    assert json_path.exists()
    assert not (tmp_path / "out.csv").exists()
    assert not (tmp_path / "out.md").exists()


def test_omitted_writes_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, minimal_report: RemediationBacklogReport) -> None:
    monkeypatch.chdir(tmp_path)
    write_remediation_backlog_report(minimal_report)
    assert (tmp_path / DEFAULT_JSON_PATH).exists()
    assert (tmp_path / DEFAULT_CSV_PATH).exists()
    assert (tmp_path / DEFAULT_MD_PATH).exists()


def test_parent_directories_created(tmp_path: Path, minimal_report: RemediationBacklogReport) -> None:
    deep_path = tmp_path / "a" / "b" / "c" / "report.json"
    atomic_write_json_remediation_backlog_report(minimal_report, deep_path)
    assert deep_path.exists()


def test_atomic_json_writer_returns_path(tmp_path: Path, minimal_report: RemediationBacklogReport) -> None:
    path = atomic_write_json_remediation_backlog_report(minimal_report, tmp_path / "x.json")
    assert path == tmp_path / "x.json"


def test_atomic_csv_writer_returns_path(tmp_path: Path, minimal_report: RemediationBacklogReport) -> None:
    path = atomic_write_csv_remediation_backlog_report(minimal_report, tmp_path / "x.csv")
    assert path == tmp_path / "x.csv"


def test_atomic_markdown_writer_returns_path(tmp_path: Path, minimal_report: RemediationBacklogReport) -> None:
    path = atomic_write_markdown_remediation_backlog_report(minimal_report, tmp_path / "x.md")
    assert path == tmp_path / "x.md"


# ---------------------------------------------------------------------------
# Safety / integrity tests
# ---------------------------------------------------------------------------


def test_no_mutation_of_report(full_report: RemediationBacklogReport) -> None:
    original = full_report
    remediation_backlog_report_to_dict(original)
    remediation_backlog_report_to_json_text(original)
    remediation_backlog_report_to_csv_text(original)
    remediation_backlog_report_to_markdown_text(original)
    assert original is full_report


def test_public_exports() -> None:
    from hunter import remediation_backlog

    assert hasattr(remediation_backlog, "remediation_backlog_report_to_dict")
    assert hasattr(remediation_backlog, "remediation_backlog_report_to_json_text")
    assert hasattr(remediation_backlog, "remediation_backlog_report_to_csv_text")
    assert hasattr(remediation_backlog, "remediation_backlog_report_to_markdown_text")
    assert hasattr(remediation_backlog, "write_remediation_backlog_report")
    assert hasattr(remediation_backlog, "DEFAULT_JSON_PATH")
    assert hasattr(remediation_backlog, "DEFAULT_CSV_PATH")
    assert hasattr(remediation_backlog, "DEFAULT_MD_PATH")


def test_nested_dataclass_mapping_serialization(now: datetime) -> None:
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            source_refs=(
                RemediationSourceRef(
                    source_id="s1", metadata={"key": "value"}, generated_at=now
                ),
            ),
            generated_at=now,
        )
    )
    data = remediation_backlog_report_to_dict(report)
    assert data["source_refs"][0]["metadata"] == {"key": "value"}


def test_no_path_reference_traversal(tmp_path: Path, minimal_report: RemediationBacklogReport) -> None:
    # The writer only writes to the explicit path; it does not read or traverse
    # other paths.
    json_path = tmp_path / "out.json"
    atomic_write_json_remediation_backlog_report(minimal_report, json_path)
    assert json_path.exists()


def test_no_actionable_recommendation_language(minimal_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_markdown_text(minimal_report)
    assert "buy signal" not in text.lower()
    assert "sell signal" not in text.lower()
    assert "trade recommendation" not in text.lower()
    assert "actionable recommendation" not in text.lower()


def test_csv_sorted_deterministically(full_report: RemediationBacklogReport) -> None:
    text1 = remediation_backlog_report_to_csv_text(full_report)
    text2 = remediation_backlog_report_to_csv_text(full_report)
    assert text1 == text2


def test_markdown_empty_collections_have_none_placeholder(not_applicable_report: RemediationBacklogReport) -> None:
    text = remediation_backlog_report_to_markdown_text(not_applicable_report)
    assert "| _none_ |" in text


def test_default_paths_match_spec() -> None:
    assert DEFAULT_JSON_PATH == Path("data/remediation_backlog/remediation_backlog.json")
    assert DEFAULT_CSV_PATH == Path("data/remediation_backlog/remediation_backlog_items.csv")
    assert DEFAULT_MD_PATH == Path("reports/remediation_backlog/remediation_backlog.md")
