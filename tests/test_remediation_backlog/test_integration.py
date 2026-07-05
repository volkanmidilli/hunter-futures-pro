"""Integration tests for hunter.remediation_backlog package.

These tests exercise the public API end-to-end: build in-memory input, run the
engine, serialize outputs, and verify behavior. No source code is patched and
no filesystem/network/trading activity is performed.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.remediation_backlog import (
    FORBIDDEN_REMEDIATION_BACKLOG_TERMS,
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
def end_to_end_input(now: datetime) -> RemediationBacklogInput:
    return RemediationBacklogInput(
        source_refs=(
            RemediationSourceRef(
                source_id="src-A",
                source_type="audit",
                reference="data/audit/src-a.json",
                label="Source A",
                generated_at=now,
            ),
        ),
        finding_refs=(
            RemediationFindingRef(
                finding_id="fnd-1",
                source_id="src-A",
                reference="data/audit/src-a.json#finding-1",
                label="Finding 1",
                generated_at=now,
            ),
        ),
        backlog_items=(
            RemediationBacklogItem(
                item_id="item-1",
                subject_id="sub-1",
                source_id="src-A",
                finding_id="fnd-1",
                item_type=RemediationBacklogItemType.MANUAL_REVIEW,
                item_state=RemediationBacklogItemState.OPEN,
                severity=RemediationBacklogSeverity.BLOCKING,
                title="Investigate failing check",
                description="Check X is failing and needs human review.",
                owner="owner-1",
                reviewer="reviewer-1",
                generated_at=now,
            ),
            RemediationBacklogItem(
                item_id="item-2",
                subject_id="sub-2",
                source_id="src-A",
                finding_id="fnd-1",
                item_type=RemediationBacklogItemType.MANUAL_REVIEW,
                item_state=RemediationBacklogItemState.OPEN,
                severity=RemediationBacklogSeverity.ADVISORY,
                title="Review documentation",
                description="Documentation could be clearer.",
                generated_at=now,
            ),
        ),
        dependencies=(
            RemediationDependency(
                dependency_id="dep-1",
                source_item_id="item-2",
                target_item_id="item-1",
                dependency_type=RemediationDependencyType.DEPENDS_ON,
            ),
        ),
        acknowledgements=(
            RemediationAcknowledgement(
                acknowledgement_id="ack-1",
                item_id="item-2",
                acknowledged_by="auditor",
                acknowledged_at=now,
                note="Documentation review accepted.",
            ),
        ),
        metadata={"context": "integration-test"},
        generated_at=now,
    )


# ---------------------------------------------------------------------------
# 1. End-to-end successful report
# ---------------------------------------------------------------------------


def test_end_to_end_successful_report(end_to_end_input: RemediationBacklogInput) -> None:
    report = build_remediation_backlog_report(end_to_end_input)
    assert isinstance(report, RemediationBacklogReport)
    assert report.report_id.startswith("remediation_backlog_")
    assert report.generated_at == end_to_end_input.generated_at
    assert isinstance(report.state, RemediationBacklogState)
    assert len(report.backlog_items) > 0
    assert isinstance(report.data_quality, RemediationBacklogDataQuality)
    assert isinstance(report.safety_flags, RemediationBacklogSafetyFlags)
    assert report.safety_flags.is_safe is True
    # Acknowledged item should be present and reclassified.
    assert any(
        i.item_type is RemediationBacklogItemType.ACKNOWLEDGED_ITEM
        for i in report.backlog_items
    )


# ---------------------------------------------------------------------------
# 2. Writer end-to-end
# ---------------------------------------------------------------------------


def test_writer_end_to_end(tmp_path: Path, end_to_end_input: RemediationBacklogInput) -> None:
    report = build_remediation_backlog_report(end_to_end_input)
    json_path = tmp_path / "report.json"
    csv_path = tmp_path / "items.csv"
    md_path = tmp_path / "report.md"
    write_remediation_backlog_report(
        report,
        json_path=json_path,
        csv_path=csv_path,
        markdown_path=md_path,
    )
    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()

    parsed = json.loads(json_path.read_text())
    assert parsed["report_id"] == report.report_id
    assert "source_refs" in parsed
    assert "finding_refs" in parsed
    assert "backlog_items" in parsed
    assert "dependencies" in parsed
    assert "acknowledgements" in parsed
    assert "data_quality" in parsed
    assert "safety_flags" in parsed

    reader = csv.DictReader(csv_path.read_text().splitlines())
    rows = list(reader)
    assert len(rows) == len(report.backlog_items)
    for row in rows:
        assert row["item_id"] in {i.item_id for i in report.backlog_items}

    md_text = md_path.read_text()
    assert md_text.startswith("# Local Research Remediation Backlog")
    assert "audit-only" in md_text.lower() or "research-only" in md_text.lower()


# ---------------------------------------------------------------------------
# 3. Empty / non-empty behavior
# ---------------------------------------------------------------------------


def test_empty_input_is_not_applicable(now: datetime) -> None:
    report = build_remediation_backlog_report(RemediationBacklogInput(generated_at=now))
    assert report.state is RemediationBacklogState.NOT_APPLICABLE
    assert RemediationBacklogReasonCode.NOT_APPLICABLE in report.reason_codes


def test_non_empty_input_with_only_acknowledged_is_ok(now: datetime) -> None:
    item = RemediationBacklogItem(
        item_id="item-1",
        source_id="src-A",
        item_state=RemediationBacklogItemState.ACKNOWLEDGED,
        item_type=RemediationBacklogItemType.ACKNOWLEDGED_ITEM,
        severity=RemediationBacklogSeverity.ADVISORY,
        title="Acknowledged",
        description="Already reviewed",
    )
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            source_refs=(RemediationSourceRef(source_id="src-A"),),
            backlog_items=(item,),
            generated_at=now,
        )
    )
    assert report.state is RemediationBacklogState.OK


# ---------------------------------------------------------------------------
# 4. Built-in checks
# ---------------------------------------------------------------------------


def test_missing_required_source(now: datetime) -> None:
    config = RemediationBacklogConfig(required_source_ids=("missing-src",))
    report = build_remediation_backlog_report(
        RemediationBacklogInput(config=config, generated_at=now)
    )
    assert report.state is RemediationBacklogState.BLOCKED
    assert any(
        i.item_type is RemediationBacklogItemType.REQUIRED_SOURCE
        for i in report.issues
    )
    assert report.data_quality.total_issues >= 1


def test_orphan_finding_ref(now: datetime) -> None:
    item = RemediationBacklogItem(
        item_id="item-1",
        source_id="src-A",
        finding_id="orphan-finding",
        title="Orphan item",
        description="References a missing finding",
    )
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            source_refs=(RemediationSourceRef(source_id="src-A"),),
            backlog_items=(item,),
            generated_at=now,
        )
    )
    assert any(
        i.item_type is RemediationBacklogItemType.ORPHAN_REF
        for i in report.issues
    )
    assert report.data_quality.orphan_finding_count >= 1


def test_orphan_dependency(now: datetime) -> None:
    dep = RemediationDependency(
        dependency_id="dep-1",
        source_item_id="missing-item",
        target_item_id="also-missing",
        dependency_type=RemediationDependencyType.DEPENDS_ON,
    )
    report = build_remediation_backlog_report(
        RemediationBacklogInput(dependencies=(dep,), generated_at=now)
    )
    assert any(
        i.item_type is RemediationBacklogItemType.ORPHAN_REF
        and RemediationBacklogReasonCode.ORPHAN_DEPENDENCY in i.reason_codes
        for i in report.issues
    )
    assert report.data_quality.orphan_dependency_count >= 1


def test_dependency_cycle(now: datetime) -> None:
    items = (
        RemediationBacklogItem(item_id="a", title="A", description="A"),
        RemediationBacklogItem(item_id="b", title="B", description="B"),
    )
    deps = (
        RemediationDependency(
            dependency_id="d1",
            source_item_id="a",
            target_item_id="b",
            dependency_type=RemediationDependencyType.DEPENDS_ON,
        ),
        RemediationDependency(
            dependency_id="d2",
            source_item_id="b",
            target_item_id="a",
            dependency_type=RemediationDependencyType.DEPENDS_ON,
        ),
    )
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            backlog_items=items,
            dependencies=deps,
            generated_at=now,
        )
    )
    assert report.state is RemediationBacklogState.BLOCKED
    assert any(
        i.item_type is RemediationBacklogItemType.DEPENDENCY_CYCLE
        for i in report.issues
    )
    assert report.data_quality.cycle_count >= 1


def test_conflicting_item_states(now: datetime) -> None:
    items = (
        RemediationBacklogItem(
            item_id="a",
            subject_id="sub-1",
            source_id="src-A",
            finding_id="fnd-1",
            item_state=RemediationBacklogItemState.OPEN,
            title="Open",
            description="Open",
        ),
        RemediationBacklogItem(
            item_id="b",
            subject_id="sub-1",
            source_id="src-A",
            finding_id="fnd-1",
            item_state=RemediationBacklogItemState.BLOCKED,
            title="Blocked",
            description="Blocked",
        ),
    )
    report = build_remediation_backlog_report(
        RemediationBacklogInput(backlog_items=items, generated_at=now)
    )
    assert any(
        i.item_type is RemediationBacklogItemType.CONFLICTING_STATE
        for i in report.issues
    )
    assert report.data_quality.conflicting_item_count >= 1


def test_stale_source_and_finding_refs(now: datetime) -> None:
    stale = now - timedelta(seconds=100000)
    source = RemediationSourceRef(source_id="src-A", generated_at=stale)
    finding = RemediationFindingRef(finding_id="fnd-1", source_id="src-A", generated_at=stale)
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            source_refs=(source,),
            finding_refs=(finding,),
            generated_at=now,
        )
    )
    assert report.data_quality.stale_source_count >= 1
    assert report.data_quality.stale_finding_count >= 1


def test_missing_owner_reviewer_manual_review(now: datetime) -> None:
    config = RemediationBacklogConfig(
        require_owner=True,
        require_reviewer=True,
        require_manual_review=True,
    )
    item = RemediationBacklogItem(
        item_id="item-1",
        source_id="src-A",
        item_type=RemediationBacklogItemType.MISSING_REF,
        title="Missing metadata",
        description="Missing owner/reviewer",
    )
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            config=config,
            source_refs=(RemediationSourceRef(source_id="src-A"),),
            backlog_items=(item,),
            generated_at=now,
        )
    )
    assert report.data_quality.missing_owner_count >= 1
    assert report.data_quality.missing_reviewer_count >= 1
    assert report.data_quality.missing_manual_review_count >= 1


# ---------------------------------------------------------------------------
# 5. Acknowledgement behavior
# ---------------------------------------------------------------------------


def test_acknowledged_item_reclassified(now: datetime) -> None:
    item = RemediationBacklogItem(
        item_id="item-1",
        source_id="src-A",
        item_state=RemediationBacklogItemState.OPEN,
        title="Ack me",
        description="To be acknowledged",
    )
    ack = RemediationAcknowledgement(
        acknowledgement_id="ack-1",
        item_id="item-1",
        acknowledged_by="auditor",
        acknowledged_at=now,
    )
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            source_refs=(RemediationSourceRef(source_id="src-A"),),
            backlog_items=(item,),
            acknowledgements=(ack,),
            generated_at=now,
        )
    )
    acknowledged = [i for i in report.backlog_items if i.item_id == "item-1"]
    assert len(acknowledged) == 1
    assert acknowledged[0].item_state is RemediationBacklogItemState.ACKNOWLEDGED
    assert acknowledged[0].item_type is RemediationBacklogItemType.ACKNOWLEDGED_ITEM


def test_acknowledged_items_do_not_block(now: datetime) -> None:
    item = RemediationBacklogItem(
        item_id="item-1",
        source_id="src-A",
        item_state=RemediationBacklogItemState.OPEN,
        severity=RemediationBacklogSeverity.BLOCKING,
        title="Blocker",
        description="Blocker",
    )
    ack = RemediationAcknowledgement(
        acknowledgement_id="ack-1",
        item_id="item-1",
        acknowledged_by="auditor",
        acknowledged_at=now,
    )
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            source_refs=(RemediationSourceRef(source_id="src-A"),),
            backlog_items=(item,),
            acknowledgements=(ack,),
            generated_at=now,
        )
    )
    assert report.state is RemediationBacklogState.OK


# ---------------------------------------------------------------------------
# 6. Duplicate behavior
# ---------------------------------------------------------------------------


def test_duplicate_id_fail_closed(now: datetime) -> None:
    items = (
        RemediationBacklogItem(item_id="dup", title="A", description="A"),
        RemediationBacklogItem(item_id="dup", title="B", description="B"),
    )
    report = build_remediation_backlog_report(
        RemediationBacklogInput(backlog_items=items, generated_at=now)
    )
    assert report.state is RemediationBacklogState.BLOCKED
    assert any(
        i.item_type is RemediationBacklogItemType.DUPLICATE_ID
        for i in report.issues
    )
    assert report.data_quality.duplicate_id_count >= 1


def test_duplicate_backlog_item_deduplication(now: datetime) -> None:
    items = (
        RemediationBacklogItem(
            source_id="src-A",
            finding_id="fnd-1",
            title="Same",
            description="Same",
        ),
        RemediationBacklogItem(
            source_id="src-A",
            finding_id="fnd-1",
            title="Same",
            description="Same",
        ),
    )
    report = build_remediation_backlog_report(
        RemediationBacklogInput(backlog_items=items, generated_at=now)
    )
    duplicates = [
        i for i in report.backlog_items
        if i.item_type is RemediationBacklogItemType.DUPLICATE_ITEM
    ]
    assert len(duplicates) == 1
    assert report.data_quality.duplicate_item_count >= 1


def test_generated_item_id_is_stable(now: datetime) -> None:
    item = RemediationBacklogItem(
        source_id="src-A",
        finding_id="fnd-1",
        title="Generated ID",
        description="No item_id provided",
    )
    inp = RemediationBacklogInput(backlog_items=(item,), generated_at=now)
    report1 = build_remediation_backlog_report(inp)
    report2 = build_remediation_backlog_report(inp)
    assert report1.backlog_items[0].item_id == report2.backlog_items[0].item_id
    assert report1.backlog_items[0].item_id is not None


# ---------------------------------------------------------------------------
# 7. Priority / severity
# ---------------------------------------------------------------------------


def test_blocking_open_item_is_p0_and_blocks(now: datetime) -> None:
    item = RemediationBacklogItem(
        item_id="item-1",
        source_id="src-A",
        item_state=RemediationBacklogItemState.OPEN,
        severity=RemediationBacklogSeverity.BLOCKING,
        title="Blocker",
        description="Blocker",
    )
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            source_refs=(RemediationSourceRef(source_id="src-A"),),
            backlog_items=(item,),
            generated_at=now,
        )
    )
    assert report.state is RemediationBacklogState.BLOCKED
    assert report.backlog_items[0].priority is RemediationBacklogPriority.P0


def test_advisory_open_item_is_p1_and_degraded(now: datetime) -> None:
    item = RemediationBacklogItem(
        item_id="item-1",
        source_id="src-A",
        item_state=RemediationBacklogItemState.OPEN,
        severity=RemediationBacklogSeverity.ADVISORY,
        title="Advisory",
        description="Advisory",
    )
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            source_refs=(RemediationSourceRef(source_id="src-A"),),
            backlog_items=(item,),
            generated_at=now,
        )
    )
    assert report.state is RemediationBacklogState.DEGRADED
    assert report.backlog_items[0].priority is RemediationBacklogPriority.P1


def test_deferred_and_acknowledged_are_lower_priority(now: datetime) -> None:
    deferred = RemediationBacklogItem(
        item_id="d",
        source_id="src-A",
        item_state=RemediationBacklogItemState.DEFERRED,
        severity=RemediationBacklogSeverity.ADVISORY,
        title="Deferred",
        description="Deferred",
    )
    ack = RemediationAcknowledgement(
        acknowledgement_id="ack-1",
        item_id="a",
        acknowledged_at=now,
    )
    open_item = RemediationBacklogItem(
        item_id="a",
        source_id="src-A",
        item_state=RemediationBacklogItemState.OPEN,
        severity=RemediationBacklogSeverity.ADVISORY,
        title="Acked",
        description="Acked",
    )
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            source_refs=(RemediationSourceRef(source_id="src-A"),),
            backlog_items=(deferred, open_item),
            acknowledgements=(ack,),
            generated_at=now,
        )
    )
    deferred_item = next(i for i in report.backlog_items if i.item_id == "d")
    acked_item = next(i for i in report.backlog_items if i.item_id == "a")
    assert deferred_item.priority is RemediationBacklogPriority.P3
    assert acked_item.priority is RemediationBacklogPriority.P3


# ---------------------------------------------------------------------------
# 8. Aggregation
# ---------------------------------------------------------------------------


def test_non_strict_aggregation_blocked_over_degraded(now: datetime) -> None:
    items = (
        RemediationBacklogItem(
            item_id="b",
            source_id="src-A",
            item_state=RemediationBacklogItemState.OPEN,
            severity=RemediationBacklogSeverity.BLOCKING,
            title="Blocker",
            description="Blocker",
        ),
        RemediationBacklogItem(
            item_id="a",
            source_id="src-A",
            item_state=RemediationBacklogItemState.OPEN,
            severity=RemediationBacklogSeverity.ADVISORY,
            title="Advisory",
            description="Advisory",
        ),
    )
    report = build_remediation_backlog_report(
        RemediationBacklogInput(backlog_items=items, generated_at=now)
    )
    assert report.state is RemediationBacklogState.BLOCKED


def test_strict_mode_promotes_degraded_to_blocked(now: datetime) -> None:
    config = RemediationBacklogConfig(strict=True)
    item = RemediationBacklogItem(
        item_id="a",
        source_id="src-A",
        item_state=RemediationBacklogItemState.OPEN,
        severity=RemediationBacklogSeverity.ADVISORY,
        title="Advisory",
        description="Advisory",
    )
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            config=config,
            source_refs=(RemediationSourceRef(source_id="src-A"),),
            backlog_items=(item,),
            generated_at=now,
        )
    )
    assert report.state is RemediationBacklogState.BLOCKED
    assert RemediationBacklogReasonCode.SAFETY_BLOCKED in report.reason_codes


def test_not_applicable_items_do_not_block(now: datetime) -> None:
    item = RemediationBacklogItem(
        item_id="a",
        source_id="src-A",
        item_state=RemediationBacklogItemState.NOT_APPLICABLE,
        severity=RemediationBacklogSeverity.INFO,
        title="NA",
        description="NA",
    )
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            source_refs=(RemediationSourceRef(source_id="src-A"),),
            backlog_items=(item,),
            generated_at=now,
        )
    )
    assert report.state is RemediationBacklogState.OK


# ---------------------------------------------------------------------------
# 9. Unsafe content and forbidden terms
# ---------------------------------------------------------------------------


def test_unsafe_content_blocks_fail_closed(now: datetime) -> None:
    report = build_remediation_backlog_report(
        RemediationBacklogInput(metadata={"key": 123}, generated_at=now)
    )
    assert report.state is RemediationBacklogState.BLOCKED
    assert report.safety_flags.has_unsafe_content is True
    assert any(
        RemediationBacklogReasonCode.UNSAFE_CONTENT in i.reason_codes
        for i in report.issues
    )


def test_forbidden_term_blocks_fail_closed(now: datetime) -> None:
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            metadata={"note": "this is an actionable recommendation"},
            generated_at=now,
        )
    )
    assert report.state is RemediationBacklogState.BLOCKED
    assert report.safety_flags.has_forbidden_terms is True


@pytest.mark.parametrize(
    "safe_text",
    [
        "pending approval from security team",
        "certification body",
        "no recommendation needed",
        "signal processing",
        "no signal detected",
    ],
)
def test_false_positive_safe_terms_do_not_block(safe_text: str, now: datetime) -> None:
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            metadata={"note": safe_text},
            generated_at=now,
        )
    )
    assert report.safety_flags.has_forbidden_terms is False


# ---------------------------------------------------------------------------
# 10. Determinism
# ---------------------------------------------------------------------------


def test_same_input_produces_identical_outputs(now: datetime) -> None:
    inp = RemediationBacklogInput(
        source_refs=(RemediationSourceRef(source_id="src-A"),),
        backlog_items=(
            RemediationBacklogItem(
                item_id="item-1",
                source_id="src-A",
                title="T",
                description="D",
            ),
        ),
        generated_at=now,
    )
    report1 = build_remediation_backlog_report(inp)
    report2 = build_remediation_backlog_report(inp)
    assert report1.report_id == report2.report_id
    assert (
        remediation_backlog_report_to_json_text(report1)
        == remediation_backlog_report_to_json_text(report2)
    )
    assert (
        remediation_backlog_report_to_csv_text(report1)
        == remediation_backlog_report_to_csv_text(report2)
    )
    assert (
        remediation_backlog_report_to_markdown_text(report1)
        == remediation_backlog_report_to_markdown_text(report2)
    )
    assert (
        remediation_backlog_report_to_dict(report1)
        == remediation_backlog_report_to_dict(report2)
    )


# ---------------------------------------------------------------------------
# 11. No mutation
# ---------------------------------------------------------------------------


def test_original_input_tuples_remain_unchanged(now: datetime) -> None:
    source = RemediationSourceRef(source_id="src-A")
    item = RemediationBacklogItem(item_id="item-1", source_id="src-A", title="T", description="D")
    inp = RemediationBacklogInput(
        source_refs=(source,),
        backlog_items=(item,),
        generated_at=now,
    )
    original_sources = inp.source_refs
    original_items = inp.backlog_items
    build_remediation_backlog_report(inp)
    assert inp.source_refs is original_sources
    assert inp.backlog_items is original_items


# ---------------------------------------------------------------------------
# 12. Public exports
# ---------------------------------------------------------------------------


def test_public_exports_include_engine_and_writer() -> None:
    from hunter import remediation_backlog

    assert hasattr(remediation_backlog, "build_remediation_backlog_report")
    assert hasattr(remediation_backlog, "write_remediation_backlog_report")
    assert hasattr(remediation_backlog, "remediation_backlog_report_to_json_text")
    assert hasattr(remediation_backlog, "remediation_backlog_report_to_csv_text")
    assert hasattr(remediation_backlog, "remediation_backlog_report_to_markdown_text")


# ---------------------------------------------------------------------------
# 13. Safety boundaries
# ---------------------------------------------------------------------------


def test_markdown_contains_research_only_safety_language(now: datetime) -> None:
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            source_refs=(RemediationSourceRef(source_id="src-A"),),
            generated_at=now,
        )
    )
    text = remediation_backlog_report_to_markdown_text(report)
    assert "not an approval" in text.lower()
    assert "production readiness" in text.lower()
    assert "trading readiness" in text.lower()
    assert "recommendation" in text.lower() or "suitability" in text.lower()
    assert "signal" in text.lower()
    assert "executable remediation plan" in text.lower()
    assert "human-review ordering only" in text.lower()


def test_markdown_contains_no_trading_or_execution_language(now: datetime) -> None:
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            source_refs=(RemediationSourceRef(source_id="src-A"),),
            generated_at=now,
        )
    )
    text = remediation_backlog_report_to_markdown_text(report)
    for term in [
        "buy signal",
        "sell signal",
        "hold signal",
        "trade recommendation",
        "execute orders",
        "place orders",
        "deploy now",
        "automated remediation",
        "auto fix",
    ]:
        assert term not in text.lower()


# ---------------------------------------------------------------------------
# 14. Opaque refs
# ---------------------------------------------------------------------------


def test_reference_strings_remain_opaque_and_unopened(now: datetime) -> None:
    report = build_remediation_backlog_report(
        RemediationBacklogInput(
            source_refs=(
                RemediationSourceRef(
                    source_id="src-A",
                    reference="data/audit/sensitive.json",
                    generated_at=now,
                ),
            ),
            generated_at=now,
        )
    )
    data = remediation_backlog_report_to_dict(report)
    assert data["source_refs"][0]["reference"] == "data/audit/sensitive.json"
    # No filesystem operation is performed; the writer only serializes the string.
