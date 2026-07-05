"""Tests for hunter.remediation_backlog.engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hunter.remediation_backlog import (
    RemediationAcknowledgement,
    RemediationBacklogConfig,
    RemediationDependencyType,
    RemediationFindingRef,
    RemediationBacklogInput,
    RemediationBacklogItem,
    RemediationBacklogItemState,
    RemediationBacklogItemType,
    RemediationBacklogPriority,
    RemediationBacklogReasonCode,
    RemediationBacklogSeverity,
    RemediationSourceRef,
    RemediationBacklogState,
    RemediationDependency,
    build_remediation_backlog_report,
)


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Empty input and basic state
# ---------------------------------------------------------------------------


def test_empty_input_not_applicable() -> None:
    inp = RemediationBacklogInput()
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.NOT_APPLICABLE
    assert report.issues == ()
    assert report.backlog_items == ()
    assert RemediationBacklogReasonCode.NOT_APPLICABLE in report.reason_codes


def test_empty_input_with_generated_at_not_applicable() -> None:
    inp = RemediationBacklogInput(generated_at=_now())
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.NOT_APPLICABLE


def test_non_empty_input_no_issues_ok() -> None:
    source = RemediationSourceRef(source_id="s1", generated_at=_now())
    inp = RemediationBacklogInput(source_refs=(source,), generated_at=_now())
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.OK


# ---------------------------------------------------------------------------
# Deterministic IDs and ordering
# ---------------------------------------------------------------------------


def test_deterministic_report_id() -> None:
    now = _now()
    source = RemediationSourceRef(source_id="s1")
    inp1 = RemediationBacklogInput(source_refs=(source,), generated_at=now)
    inp2 = RemediationBacklogInput(source_refs=(source,), generated_at=now)
    assert build_remediation_backlog_report(inp1).report_id == build_remediation_backlog_report(inp2).report_id


def test_report_id_changes_with_input() -> None:
    now = _now()
    inp1 = RemediationBacklogInput(
        source_refs=(RemediationSourceRef(source_id="s1"),),
        generated_at=now,
    )
    inp2 = RemediationBacklogInput(
        source_refs=(RemediationSourceRef(source_id="s2"),),
        generated_at=now,
    )
    assert build_remediation_backlog_report(inp1).report_id != build_remediation_backlog_report(inp2).report_id


def test_source_refs_copied_sorted() -> None:
    s1 = RemediationSourceRef(source_id="s2")
    s2 = RemediationSourceRef(source_id="s1")
    inp = RemediationBacklogInput(source_refs=(s1, s2))
    report = build_remediation_backlog_report(inp)
    assert [s.source_id for s in report.source_refs] == ["s1", "s2"]


def test_generated_item_id_is_stable() -> None:
    item = RemediationBacklogItem(source_id="s1", finding_id="f1", title="title", description="desc")
    inp = RemediationBacklogInput(backlog_items=(item,))
    report1 = build_remediation_backlog_report(inp)
    report2 = build_remediation_backlog_report(inp)
    assert report1.backlog_items[0].item_id == report2.backlog_items[0].item_id


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


def test_duplicate_source_id_blocking() -> None:
    inp = RemediationBacklogInput(
        source_refs=(
            RemediationSourceRef(source_id="s1"),
            RemediationSourceRef(source_id="s1"),
        ),
    )
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.BLOCKED
    issue = report.issues[0]
    assert issue.item_type is RemediationBacklogItemType.DUPLICATE_ID
    assert issue.severity is RemediationBacklogSeverity.BLOCKING


def test_duplicate_item_id_blocking() -> None:
    inp = RemediationBacklogInput(
        backlog_items=(
            RemediationBacklogItem(item_id="i1"),
            RemediationBacklogItem(item_id="i1"),
        ),
    )
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.BLOCKED


def test_duplicate_backlog_item_dedup() -> None:
    inp = RemediationBacklogInput(
        backlog_items=(
            RemediationBacklogItem(source_id="s1", finding_id="f1", title="t", description="d"),
            RemediationBacklogItem(source_id="s1", finding_id="f1", title="t", description="d"),
        ),
    )
    report = build_remediation_backlog_report(inp)
    duplicates = [i for i in report.backlog_items if i.item_type is RemediationBacklogItemType.DUPLICATE_ITEM]
    assert len(duplicates) == 1
    assert report.data_quality.duplicate_item_count == 1


# ---------------------------------------------------------------------------
# Required sources and orphan detection
# ---------------------------------------------------------------------------


def test_missing_required_source() -> None:
    config = RemediationBacklogConfig(required_source_ids=("s1",))
    inp = RemediationBacklogInput(config=config)
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.BLOCKED
    issue = report.issues[0]
    assert issue.item_type is RemediationBacklogItemType.REQUIRED_SOURCE


def test_orphan_finding_ref() -> None:
    item = RemediationBacklogItem(item_id="i1", finding_id="f1")
    inp = RemediationBacklogInput(backlog_items=(item,))
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.DEGRADED
    issue = next(i for i in report.issues if i.item_type is RemediationBacklogItemType.ORPHAN_REF)
    assert issue.reason_codes[0] is RemediationBacklogReasonCode.ORPHAN_FINDING_REF


def test_orphan_dependency() -> None:
    dep = RemediationDependency(dependency_id="d1", source_item_id="missing", target_item_id="i2")
    item = RemediationBacklogItem(item_id="i2")
    inp = RemediationBacklogInput(backlog_items=(item,), dependencies=(dep,))
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.DEGRADED
    issue = next(i for i in report.issues if i.reason_codes[0] is RemediationBacklogReasonCode.ORPHAN_DEPENDENCY)
    assert issue is not None


# ---------------------------------------------------------------------------
# Dependency cycles and conflicts
# ---------------------------------------------------------------------------


def test_dependency_cycle_blocking() -> None:
    dep1 = RemediationDependency(dependency_id="d1", source_item_id="a", target_item_id="b", dependency_type=RemediationDependencyType.DEPENDS_ON)
    dep2 = RemediationDependency(dependency_id="d2", source_item_id="b", target_item_id="a", dependency_type=RemediationDependencyType.DEPENDS_ON)
    item_a = RemediationBacklogItem(item_id="a")
    item_b = RemediationBacklogItem(item_id="b")
    inp = RemediationBacklogInput(backlog_items=(item_a, item_b), dependencies=(dep1, dep2))
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.BLOCKED
    issue = next(i for i in report.issues if i.item_type is RemediationBacklogItemType.DEPENDENCY_CYCLE)
    assert issue is not None


def test_conflicting_item_states_blocking() -> None:
    item1 = RemediationBacklogItem(item_id="i1", subject_id="sub", item_state=RemediationBacklogItemState.OPEN)
    item2 = RemediationBacklogItem(item_id="i2", subject_id="sub", item_state=RemediationBacklogItemState.BLOCKED)
    inp = RemediationBacklogInput(backlog_items=(item1, item2))
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.BLOCKED
    issue = next(i for i in report.issues if i.item_type is RemediationBacklogItemType.CONFLICTING_STATE)
    assert issue.severity is RemediationBacklogSeverity.BLOCKING


def test_conflicting_item_states_advisory() -> None:
    item1 = RemediationBacklogItem(item_id="i1", subject_id="sub", item_state=RemediationBacklogItemState.OPEN)
    item2 = RemediationBacklogItem(item_id="i2", subject_id="sub", item_state=RemediationBacklogItemState.DEFERRED)
    inp = RemediationBacklogInput(backlog_items=(item1, item2))
    report = build_remediation_backlog_report(inp)
    issue = next(i for i in report.issues if i.item_type is RemediationBacklogItemType.CONFLICTING_STATE)
    assert issue.severity is RemediationBacklogSeverity.ADVISORY


# ---------------------------------------------------------------------------
# Stale refs and missing metadata
# ---------------------------------------------------------------------------


def test_stale_source_ref() -> None:
    now = _now()
    stale_time = now - timedelta(days=2)
    config = RemediationBacklogConfig(staleness_threshold_seconds=86400)
    source = RemediationSourceRef(source_id="s1", generated_at=stale_time)
    inp = RemediationBacklogInput(source_refs=(source,), config=config, generated_at=now)
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.DEGRADED
    issue = next(i for i in report.issues if i.reason_codes[0] is RemediationBacklogReasonCode.STALE_SOURCE_REF)
    assert issue is not None


def test_missing_owner() -> None:
    config = RemediationBacklogConfig(require_owner=True)
    item = RemediationBacklogItem(item_id="i1")
    inp = RemediationBacklogInput(backlog_items=(item,), config=config)
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.DEGRADED
    issue = next(i for i in report.issues if i.item_type is RemediationBacklogItemType.MISSING_OWNER)
    assert issue is not None


def test_missing_reviewer() -> None:
    config = RemediationBacklogConfig(require_reviewer=True)
    item = RemediationBacklogItem(item_id="i1")
    inp = RemediationBacklogInput(backlog_items=(item,), config=config)
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.DEGRADED


def test_missing_manual_review() -> None:
    config = RemediationBacklogConfig(require_manual_review=True)
    item = RemediationBacklogItem(item_id="i1", item_type=RemediationBacklogItemType.STALE_REF)
    inp = RemediationBacklogInput(backlog_items=(item,), config=config)
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.DEGRADED
    issue = next(i for i in report.issues if i.item_type is RemediationBacklogItemType.MISSING_MANUAL_REVIEW)
    assert issue is not None


# ---------------------------------------------------------------------------
# Acknowledgements and priorities
# ---------------------------------------------------------------------------


def test_acknowledged_item_reclassified() -> None:
    item = RemediationBacklogItem(item_id="i1", item_state=RemediationBacklogItemState.OPEN)
    ack = RemediationAcknowledgement(acknowledgement_id="a1", item_id="i1")
    inp = RemediationBacklogInput(backlog_items=(item,), acknowledgements=(ack,))
    report = build_remediation_backlog_report(inp)
    acknowledged = next(i for i in report.backlog_items if i.item_state is RemediationBacklogItemState.ACKNOWLEDGED)
    assert acknowledged is not None
    assert acknowledged.item_type is RemediationBacklogItemType.ACKNOWLEDGED_ITEM
    assert acknowledged.priority is RemediationBacklogPriority.P3


def test_priority_first_match_wins() -> None:
    # A DEFERRED BLOCKING item should match P3, not P0, because it is not OPEN.
    item = RemediationBacklogItem(item_id="i1", severity=RemediationBacklogSeverity.BLOCKING, item_state=RemediationBacklogItemState.DEFERRED)
    inp = RemediationBacklogInput(backlog_items=(item,))
    report = build_remediation_backlog_report(inp)
    assert report.backlog_items[0].priority is RemediationBacklogPriority.P3


def test_priority_ordering() -> None:
    item_p0 = RemediationBacklogItem(item_id="p0", severity=RemediationBacklogSeverity.BLOCKING, item_state=RemediationBacklogItemState.OPEN)
    item_p1 = RemediationBacklogItem(item_id="p1", severity=RemediationBacklogSeverity.ADVISORY, item_state=RemediationBacklogItemState.OPEN)
    item_p2 = RemediationBacklogItem(item_id="p2", severity=RemediationBacklogSeverity.INFO, item_state=RemediationBacklogItemState.OPEN)
    inp = RemediationBacklogInput(backlog_items=(item_p2, item_p0, item_p1))
    report = build_remediation_backlog_report(inp)
    priorities = [i.priority for i in report.backlog_items if i.item_type is RemediationBacklogItemType.MANUAL_REVIEW]
    assert priorities == [RemediationBacklogPriority.P0, RemediationBacklogPriority.P1, RemediationBacklogPriority.P2]


# ---------------------------------------------------------------------------
# Unsafe content and forbidden terms
# ---------------------------------------------------------------------------


def test_forbidden_term_present_blocks() -> None:
    item = RemediationBacklogItem(item_id="i1", description="This item is production ready")
    inp = RemediationBacklogInput(backlog_items=(item,))
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.BLOCKED
    assert report.safety_flags.has_forbidden_terms is True


def test_forbidden_term_no_false_positives() -> None:
    benign = [
        "pending approval from security team",
        "certification body",
        "no recommendation needed",
        "signal processing",
        "no signal detected",
    ]
    for text in benign:
        item = RemediationBacklogItem(item_id=text, description=text, severity=RemediationBacklogSeverity.INFO)
        inp = RemediationBacklogInput(backlog_items=(item,))
        report = build_remediation_backlog_report(inp)
        assert report.safety_flags.has_forbidden_terms is False, text
        assert report.state is not RemediationBacklogState.BLOCKED, text


def test_unsafe_content_metadata_blocks() -> None:
    inp = RemediationBacklogInput(metadata={"key": b"value"})
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.BLOCKED
    assert report.safety_flags.has_unsafe_content is True


def test_unsafe_content_in_title_blocks() -> None:
    item = RemediationBacklogItem(item_id="i1", title="safe", metadata={"unsafe": 123})
    inp = RemediationBacklogInput(backlog_items=(item,))
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.BLOCKED


# ---------------------------------------------------------------------------
# Aggregation and strict mode
# ---------------------------------------------------------------------------


def test_strict_mode_promotes_degraded_to_blocked() -> None:
    config = RemediationBacklogConfig(strict=True)
    item = RemediationBacklogItem(item_id="i1", severity=RemediationBacklogSeverity.ADVISORY)
    inp = RemediationBacklogInput(backlog_items=(item,), config=config)
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.BLOCKED
    assert RemediationBacklogReasonCode.SAFETY_BLOCKED in report.reason_codes


def test_acknowledged_item_does_not_block() -> None:
    item = RemediationBacklogItem(item_id="i1", item_state=RemediationBacklogItemState.ACKNOWLEDGED)
    inp = RemediationBacklogInput(backlog_items=(item,))
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.OK


def test_deferred_item_does_not_block() -> None:
    item = RemediationBacklogItem(item_id="i1", item_state=RemediationBacklogItemState.DEFERRED)
    inp = RemediationBacklogInput(backlog_items=(item,))
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.OK


def test_info_item_does_not_block() -> None:
    item = RemediationBacklogItem(item_id="i1", severity=RemediationBacklogSeverity.INFO)
    inp = RemediationBacklogInput(backlog_items=(item,))
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.OK


def test_not_applicable_item_does_not_block() -> None:
    item = RemediationBacklogItem(item_id="i1", item_state=RemediationBacklogItemState.NOT_APPLICABLE)
    inp = RemediationBacklogInput(backlog_items=(item,))
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.OK


# ---------------------------------------------------------------------------
# Safety and opaque refs
# ---------------------------------------------------------------------------


def test_no_executable_remediation_output() -> None:
    source = RemediationSourceRef(source_id="s1", reference="path/to/report.md")
    inp = RemediationBacklogInput(source_refs=(source,))
    report = build_remediation_backlog_report(inp)
    assert report.safety_flags.no_executable_actions is True
    assert report.safety_flags.no_automated_remediation is True


def test_reference_strings_are_opaque() -> None:
    # The engine should not attempt to validate or open the reference string.
    source = RemediationSourceRef(source_id="s1", reference="/does/not/exist")
    inp = RemediationBacklogInput(source_refs=(source,))
    report = build_remediation_backlog_report(inp)
    assert report.state is RemediationBacklogState.OK


def test_no_source_mutation() -> None:
    item = RemediationBacklogItem(item_id="i1")
    inp = RemediationBacklogInput(backlog_items=(item,))
    original_id = id(inp.backlog_items)
    build_remediation_backlog_report(inp)
    assert id(inp.backlog_items) == original_id


def test_safety_notice_present() -> None:
    inp = RemediationBacklogInput()
    report = build_remediation_backlog_report(inp)
    assert "audit-only" in report.safety_notice.lower()
    assert "not an approval" in report.safety_notice.lower()
