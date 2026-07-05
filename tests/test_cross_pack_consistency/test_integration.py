"""Integration tests for hunter.cross_pack_consistency package.

MVP-36 Step 3 — Local Research Cross-Pack Consistency Validator.

These tests exercise the public engine and writer end-to-end using only
caller-provided in-memory declarations. They do not touch the filesystem except
for tmp_path writes, do not import Freqtrade, and do not use networks,
exchanges, databases, live trading, or Web UI semantics.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.cross_pack_consistency import (
    CrossPackArtifactRef,
    CrossPackConsistencyConfig,
    CrossPackConsistencyIssueType,
    CrossPackConsistencyReasonCode,
    CrossPackConsistencyRule,
    CrossPackConsistencyRuleType,
    CrossPackConsistencySeverity,
    CrossPackConsistencyState,
    CrossPackConsistencyInput,
    CrossPackDeclaration,
    CrossPackRequirementRef,
    CrossPackSectionRef,
    CrossPackStateClaim,
    atomic_write_csv_cross_pack_consistency_report,
    atomic_write_json_cross_pack_consistency_report,
    atomic_write_markdown_cross_pack_consistency_report,
    build_cross_pack_consistency_report,
    cross_pack_consistency_report_to_csv_text,
    cross_pack_consistency_report_to_dict,
    cross_pack_consistency_report_to_json_text,
    cross_pack_consistency_report_to_markdown_text,
    write_cross_pack_consistency_report,
)


@pytest.fixture
def now() -> datetime:
    """Timezone-aware deterministic timestamp for reproducible reports."""
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _ok_input(now: datetime) -> CrossPackConsistencyInput:
    """Build a non-trivial input that produces an OK report."""
    decl1 = CrossPackDeclaration(
        pack_id="audit_scorecard",
        version="1.0",
        title="Audit Scorecard",
        description="Local audit scorecard",
        declared_state="ok",
        artifact_ref_ids=("a1",),
        section_ref_ids=("s1",),
        requirement_ref_ids=("r1",),
        generated_at=now,
    )
    decl2 = CrossPackDeclaration(
        pack_id="release_hardening",
        version="1.0",
        title="Release Hardening",
        description="Release hardening pack",
        declared_state="ok",
        generated_at=now,
    )
    decl3 = CrossPackDeclaration(
        pack_id="evidence_traceability",
        version="1.0",
        title="Evidence Traceability",
        description="Evidence traceability matrix",
        declared_state="ok",
        generated_at=now,
    )
    artifact_ref = CrossPackArtifactRef(
        ref_id="a1",
        pack_id="audit_scorecard",
        reference="data/audit_scorecard/audit_scorecard.json",
        label="Scorecard artifact",
        generated_at=now,
    )
    section_ref = CrossPackSectionRef(
        ref_id="s1",
        pack_id="audit_scorecard",
        reference="section-1",
        label="Scorecard section",
        generated_at=now,
    )
    requirement_ref = CrossPackRequirementRef(
        ref_id="r1",
        pack_id="audit_scorecard",
        reference="requirement-1",
        label="Scorecard requirement",
        generated_at=now,
    )
    state_claim = CrossPackStateClaim(
        subject_id="final_audit_status",
        state_label="ok",
        pack_id="audit_scorecard",
        message="audit status ok",
    )
    version_rule = CrossPackConsistencyRule(
        rule_type=CrossPackConsistencyRuleType.COMPATIBLE_VERSION,
        source_pack_id="audit_scorecard",
        target_pack_id="release_hardening",
        expected_version="1.0",
        severity=CrossPackConsistencySeverity.BLOCKING,
    )
    state_rule = CrossPackConsistencyRule(
        rule_type=CrossPackConsistencyRuleType.COMPATIBLE_STATE,
        source_pack_id="audit_scorecard",
        target_pack_id="release_hardening",
        forbidden_states=("blocked",),
        severity=CrossPackConsistencySeverity.BLOCKING,
    )
    return CrossPackConsistencyInput(
        declarations=(decl1, decl2, decl3),
        artifact_refs=(artifact_ref,),
        section_refs=(section_ref,),
        requirement_refs=(requirement_ref,),
        state_claims=(state_claim,),
        rules=(version_rule, state_rule),
        metadata={"author": "integration-test"},
        generated_at=now,
        project_version="0.36.0-dev",
    )


def _degraded_input(now: datetime) -> CrossPackConsistencyInput:
    """Build a simple input that produces a DEGRADED report."""
    decl = CrossPackDeclaration(
        pack_id="audit_scorecard",
        version="1.0",
        description="Needs manual review",
        requires_manual_review=True,
        generated_at=now,
    )
    return CrossPackConsistencyInput(declarations=(decl,), generated_at=now)


# -----------------------------------------------------------------------------
# 1. End-to-end successful report
# -----------------------------------------------------------------------------


def test_end_to_end_successful_report(now: datetime) -> None:
    """A full in-memory input produces a deterministic OK report."""
    inp = _ok_input(now)
    report = build_cross_pack_consistency_report(inp)

    assert report.state is CrossPackConsistencyState.OK
    assert report.generated_at == now
    assert report.project_version == "0.36.0-dev"
    assert report.report_id.startswith("cross_pack_consistency_")
    assert report.reason_codes == (CrossPackConsistencyReasonCode.OK,)
    assert report.safety_flags.is_safe is True
    assert report.data_quality.total_packs == 3
    assert report.data_quality.total_artifact_refs == 1
    assert report.data_quality.total_section_refs == 1
    assert report.data_quality.total_requirement_refs == 1
    assert report.data_quality.total_state_claims == 1
    assert report.data_quality.total_rules == 2
    assert report.data_quality.total_issues == 0
    assert report.data_quality.sections_present == 1


# -----------------------------------------------------------------------------
# 2. Writer end-to-end
# -----------------------------------------------------------------------------


def test_writer_end_to_end(now: datetime, tmp_path: Path) -> None:
    """write_cross_pack_consistency_report creates JSON, CSV, and Markdown."""
    report = build_cross_pack_consistency_report(_degraded_input(now))
    json_path = tmp_path / "report.json"
    csv_path = tmp_path / "report.csv"
    md_path = tmp_path / "report.md"

    json_out, csv_out, md_out = write_cross_pack_consistency_report(
        report,
        json_path=json_path,
        csv_path=csv_path,
        markdown_path=md_path,
    )
    assert json_out == json_path
    assert csv_out == csv_path
    assert md_out == md_path

    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["report_id"] == report.report_id
    assert isinstance(parsed["declarations"], list)
    assert isinstance(parsed["artifact_refs"], list)
    assert isinstance(parsed["section_refs"], list)
    assert isinstance(parsed["requirement_refs"], list)
    assert isinstance(parsed["state_claims"], list)
    assert isinstance(parsed["rules"], list)
    assert isinstance(parsed["issues"], list)

    csv_text = csv_path.read_text(encoding="utf-8")
    lines = csv_text.strip().split("\n")
    assert lines[0].startswith("report_id,generated_at,issue_id")
    rows = list(csv.reader(lines))
    data_rows = rows[1:]
    assert len(data_rows) == len(report.issues)
    issue_ids = {row[2] for row in data_rows}
    assert issue_ids == {issue.issue_id for issue in report.issues}

    md_text = md_path.read_text(encoding="utf-8")
    md_lines = md_text.splitlines()
    assert md_lines[0] == "# Local Research Cross-Pack Consistency Validator Report"
    assert any(
        "research-only" in line.lower() or "audit-only" in line.lower()
        for line in md_lines[:5]
    )


# -----------------------------------------------------------------------------
# 3. Empty input
# -----------------------------------------------------------------------------


def test_empty_and_not_applicable_inputs(now: datetime) -> None:
    """Truly empty input is NOT_APPLICABLE; non-empty input with no issues is OK."""
    empty = CrossPackConsistencyInput(generated_at=now)
    report_empty = build_cross_pack_consistency_report(empty)
    assert report_empty.state is CrossPackConsistencyState.NOT_APPLICABLE
    assert CrossPackConsistencyReasonCode.NOT_APPLICABLE in report_empty.reason_codes
    assert report_empty.issues == ()
    assert report_empty.data_quality.total_packs == 0

    metadata_only = CrossPackConsistencyInput(metadata={"key": "value"}, generated_at=now)
    report_metadata = build_cross_pack_consistency_report(metadata_only)
    assert report_metadata.state is CrossPackConsistencyState.NOT_APPLICABLE

    decl = CrossPackDeclaration(pack_id="p1", version="1.0", generated_at=now)
    non_empty = CrossPackConsistencyInput(declarations=(decl,), generated_at=now)
    report_non_empty = build_cross_pack_consistency_report(non_empty)
    assert report_non_empty.state is CrossPackConsistencyState.OK


# -----------------------------------------------------------------------------
# 4. Built-in checks
# -----------------------------------------------------------------------------


def test_builtin_missing_required_pack(now: datetime) -> None:
    """Missing required pack IDs produce a BLOCKING issue."""
    config = CrossPackConsistencyConfig(required_pack_ids=("required_pack",))
    inp = CrossPackConsistencyInput(config=config, generated_at=now)
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.BLOCKED
    issue = report.issues[0]
    assert issue.issue_type is CrossPackConsistencyIssueType.MISSING_REQUIRED_PACK
    assert CrossPackConsistencyReasonCode.MISSING_REQUIRED_PACK in issue.reason_codes


def test_builtin_missing_expected_refs_and_orphan_refs(now: datetime) -> None:
    """Missing expected refs and orphan refs are ADVISORY."""
    decl = CrossPackDeclaration(
        pack_id="p1",
        version="1.0",
        artifact_ref_ids=("a1",),
        section_ref_ids=("s1",),
        requirement_ref_ids=("r1",),
        generated_at=now,
    )
    inp = CrossPackConsistencyInput(declarations=(decl,), generated_at=now)
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.DEGRADED
    assert any(
        i.issue_type is CrossPackConsistencyIssueType.MISSING_EXPECTED_REF
        for i in report.issues
    )
    reason_values = {
        rc.value
        for i in report.issues
        for rc in i.reason_codes
    }
    assert "missing_expected_artifact_ref" in reason_values
    assert "missing_expected_section_ref" in reason_values
    assert "missing_expected_requirement_ref" in reason_values

    # Orphan refs: a ref that no declaration expects.
    decl2 = CrossPackDeclaration(pack_id="p2", version="1.0", generated_at=now)
    art = CrossPackArtifactRef(
        ref_id="a2",
        pack_id="p2",
        reference="data/audit/audit.json",
        generated_at=now,
    )
    inp2 = CrossPackConsistencyInput(
        declarations=(decl2,),
        artifact_refs=(art,),
        generated_at=now,
    )
    report2 = build_cross_pack_consistency_report(inp2)
    assert report2.state is CrossPackConsistencyState.DEGRADED
    issue = next(
        i for i in report2.issues
        if i.issue_type is CrossPackConsistencyIssueType.ORPHAN_REF
    )
    assert issue.reason_codes[0].value == "orphan_artifact_ref"


def test_builtin_stale_unknown_and_manual_review(now: datetime) -> None:
    """Built-in checks cover stale, unknown, and missing manual-review."""
    config = CrossPackConsistencyConfig(
        staleness_threshold_seconds=86400,
        allowed_state_labels=("ok",),
    )
    stale_time = now - timedelta(days=2)
    decl1 = CrossPackDeclaration(
        pack_id="stale_pack",
        version="1.0",
        generated_at=stale_time,
    )
    decl2 = CrossPackDeclaration(
        pack_id="unknown_state_pack",
        version="1.0",
        declared_state="weird",
        generated_at=now,
    )
    decl3 = CrossPackDeclaration(
        pack_id="manual_pack",
        version="1.0",
        requires_manual_review=True,
        generated_at=now,
    )
    inp = CrossPackConsistencyInput(
        declarations=(decl1, decl2, decl3),
        config=config,
        generated_at=now,
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.DEGRADED
    issue_types = {i.issue_type for i in report.issues}
    assert CrossPackConsistencyIssueType.STALE_DECLARATION in issue_types
    assert CrossPackConsistencyIssueType.UNKNOWN_UPSTREAM_STATE in issue_types
    assert CrossPackConsistencyIssueType.MISSING_MANUAL_REVIEW in issue_types


def test_builtin_conflicting_state_claims(now: datetime) -> None:
    """Conflicting state claims for the same subject are fail-closed."""
    claim1 = CrossPackStateClaim(
        subject_id="sub", state_label="ok", pack_id="p1"
    )
    claim2 = CrossPackStateClaim(
        subject_id="sub", state_label="blocked", pack_id="p2"
    )
    inp = CrossPackConsistencyInput(
        state_claims=(claim1, claim2),
        generated_at=now,
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.BLOCKED
    issue = next(
        i for i in report.issues
        if i.issue_type is CrossPackConsistencyIssueType.CONFLICTING_STATE
    )
    assert issue.severity is CrossPackConsistencySeverity.BLOCKING


# -----------------------------------------------------------------------------
# 5. Rule-driven checks
# -----------------------------------------------------------------------------


def test_rule_compatible_version_and_state(now: datetime) -> None:
    """COMPATIBLE_VERSION and COMPATIBLE_STATE rules emit issues on failure."""
    decl1 = CrossPackDeclaration(pack_id="p1", version="1.0", generated_at=now)
    decl2 = CrossPackDeclaration(pack_id="p2", version="2.0", generated_at=now)
    decl3 = CrossPackDeclaration(
        pack_id="p3", version="1.0", declared_state="blocked", generated_at=now
    )
    rules = (
        CrossPackConsistencyRule(
            rule_type=CrossPackConsistencyRuleType.COMPATIBLE_VERSION,
            source_pack_id="p1",
            target_pack_id="p2",
            severity=CrossPackConsistencySeverity.BLOCKING,
        ),
        CrossPackConsistencyRule(
            rule_type=CrossPackConsistencyRuleType.COMPATIBLE_STATE,
            source_pack_id="p3",
            forbidden_states=("blocked",),
            severity=CrossPackConsistencySeverity.BLOCKING,
        ),
    )
    inp = CrossPackConsistencyInput(
        declarations=(decl1, decl2, decl3),
        rules=rules,
        generated_at=now,
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.BLOCKED
    issue_types = {i.issue_type for i in report.issues}
    assert CrossPackConsistencyIssueType.INCOMPATIBLE_VERSION in issue_types
    assert CrossPackConsistencyIssueType.INCOMPATIBLE_STATE_COMBINATION in issue_types


def test_rule_manual_review_and_conflicting_state(now: datetime) -> None:
    """MANUAL_REVIEW and CONFLICTING_STATE rules produce rule-driven issues."""
    decl = CrossPackDeclaration(pack_id="p1", version="1.0", generated_at=now)
    claim1 = CrossPackStateClaim(
        subject_id="sub", state_label="ok", pack_id="p1"
    )
    claim2 = CrossPackStateClaim(
        subject_id="sub", state_label="blocked", pack_id="p2"
    )
    rules = (
        CrossPackConsistencyRule(
            rule_type=CrossPackConsistencyRuleType.MANUAL_REVIEW,
            source_pack_id="p1",
            severity=CrossPackConsistencySeverity.ADVISORY,
        ),
        CrossPackConsistencyRule(
            rule_type=CrossPackConsistencyRuleType.CONFLICTING_STATE,
            source_pack_id="p1",
            subject_id="sub",
            severity=CrossPackConsistencySeverity.ADVISORY,
        ),
    )
    inp = CrossPackConsistencyInput(
        declarations=(decl,),
        state_claims=(claim1, claim2),
        rules=rules,
        generated_at=now,
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.BLOCKED
    assert any(
        i.issue_type is CrossPackConsistencyIssueType.MISSING_MANUAL_REVIEW
        and i.severity is CrossPackConsistencySeverity.ADVISORY
        for i in report.issues
    )
    assert any(
        i.issue_type is CrossPackConsistencyIssueType.CONFLICTING_STATE
        for i in report.issues
    )


def test_rule_explicit_required_expected_and_stale(now: datetime) -> None:
    """Explicit REQUIRED_PACK, EXPECTED_REF, and STALE_DECLARATION rules work."""
    stale_time = now - timedelta(days=2)
    decl = CrossPackDeclaration(
        pack_id="p1", version="1.0", generated_at=stale_time
    )
    rules = (
        CrossPackConsistencyRule(
            rule_type=CrossPackConsistencyRuleType.REQUIRED_PACK,
            source_pack_id="missing_pack",
            severity=CrossPackConsistencySeverity.BLOCKING,
        ),
        CrossPackConsistencyRule(
            rule_type=CrossPackConsistencyRuleType.EXPECTED_REF,
            source_pack_id="p1",
            ref_kind="artifact",
            ref_id="a1",
        ),
        CrossPackConsistencyRule(
            rule_type=CrossPackConsistencyRuleType.STALE_DECLARATION,
            source_pack_id="p1",
        ),
    )
    inp = CrossPackConsistencyInput(
        declarations=(decl,), rules=rules, generated_at=now
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.BLOCKED
    issue_types = {i.issue_type for i in report.issues}
    assert CrossPackConsistencyIssueType.MISSING_REQUIRED_PACK in issue_types
    assert CrossPackConsistencyIssueType.MISSING_EXPECTED_REF in issue_types
    assert CrossPackConsistencyIssueType.STALE_DECLARATION in issue_types


# -----------------------------------------------------------------------------
# 6. Built-in vs rule-driven dedup
# -----------------------------------------------------------------------------


def test_builtin_and_rule_driven_dedup(now: datetime) -> None:
    """Identical built-in and rule-driven issues are retained once."""
    stale_time = now - timedelta(days=2)
    decl = CrossPackDeclaration(
        pack_id="p1",
        version="1.0",
        generated_at=stale_time,
        artifact_ref_ids=("a1",),
        requires_manual_review=True,
    )
    config = CrossPackConsistencyConfig(required_pack_ids=("missing",))
    rules = (
        CrossPackConsistencyRule(
            rule_type=CrossPackConsistencyRuleType.REQUIRED_PACK,
            source_pack_id="missing",
            severity=CrossPackConsistencySeverity.BLOCKING,
        ),
        CrossPackConsistencyRule(
            rule_type=CrossPackConsistencyRuleType.EXPECTED_REF,
            source_pack_id="p1",
            ref_kind="artifact",
            ref_id="a1",
        ),
        CrossPackConsistencyRule(
            rule_type=CrossPackConsistencyRuleType.STALE_DECLARATION,
            source_pack_id="p1",
        ),
        CrossPackConsistencyRule(
            rule_type=CrossPackConsistencyRuleType.MANUAL_REVIEW,
            source_pack_id="p1",
        ),
    )
    inp = CrossPackConsistencyInput(
        declarations=(decl,),
        rules=rules,
        config=config,
        generated_at=now,
    )
    report1 = build_cross_pack_consistency_report(inp)
    report2 = build_cross_pack_consistency_report(inp)

    def count_issues(report, issue_type):
        return sum(1 for i in report.issues if i.issue_type is issue_type)

    for issue_type in (
        CrossPackConsistencyIssueType.MISSING_REQUIRED_PACK,
        CrossPackConsistencyIssueType.MISSING_EXPECTED_REF,
        CrossPackConsistencyIssueType.STALE_DECLARATION,
        CrossPackConsistencyIssueType.MISSING_MANUAL_REVIEW,
    ):
        assert count_issues(report1, issue_type) == 1

    # Issue IDs are stable across identical builds.
    for issue_type in (
        CrossPackConsistencyIssueType.MISSING_REQUIRED_PACK,
        CrossPackConsistencyIssueType.MISSING_EXPECTED_REF,
        CrossPackConsistencyIssueType.STALE_DECLARATION,
        CrossPackConsistencyIssueType.MISSING_MANUAL_REVIEW,
    ):
        id1 = next(i.issue_id for i in report1.issues if i.issue_type is issue_type)
        id2 = next(i.issue_id for i in report2.issues if i.issue_type is issue_type)
        assert id1 == id2


# -----------------------------------------------------------------------------
# 7. Incompatible state combinations
# -----------------------------------------------------------------------------


def test_incompatible_state_combinations(now: datetime) -> None:
    """Rule-driven checks catch common cross-pack contradictory states."""
    # audit_scorecard OK while release_hardening BLOCKED.
    decl1 = CrossPackDeclaration(
        pack_id="audit_scorecard", version="1.0", declared_state="ok", generated_at=now
    )
    decl2 = CrossPackDeclaration(
        pack_id="release_hardening",
        version="1.0",
        declared_state="blocked",
        generated_at=now,
    )
    rule1 = CrossPackConsistencyRule(
        rule_type=CrossPackConsistencyRuleType.COMPATIBLE_STATE,
        source_pack_id="audit_scorecard",
        target_pack_id="release_hardening",
        forbidden_states=("blocked",),
        severity=CrossPackConsistencySeverity.BLOCKING,
    )
    inp1 = CrossPackConsistencyInput(
        declarations=(decl1, decl2), rules=(rule1,), generated_at=now
    )
    report1 = build_cross_pack_consistency_report(inp1)
    assert report1.state is CrossPackConsistencyState.BLOCKED
    assert any(
        i.issue_type is CrossPackConsistencyIssueType.INCOMPATIBLE_STATE_COMBINATION
        for i in report1.issues
    )

    # audit_scorecard COMPLETE while evidence_traceability MISSING.
    decl3 = CrossPackDeclaration(
        pack_id="audit_scorecard",
        version="1.0",
        declared_state="complete",
        generated_at=now,
    )
    claim = CrossPackStateClaim(
        subject_id="evidence_traceability",
        state_label="missing",
        pack_id="evidence_traceability",
    )
    rule2 = CrossPackConsistencyRule(
        rule_type=CrossPackConsistencyRuleType.COMPATIBLE_STATE,
        source_pack_id="audit_scorecard",
        subject_id="evidence_traceability",
        forbidden_states=("missing", "blocked"),
        severity=CrossPackConsistencySeverity.BLOCKING,
    )
    inp2 = CrossPackConsistencyInput(
        declarations=(decl3,),
        state_claims=(claim,),
        rules=(rule2,),
        generated_at=now,
    )
    report2 = build_cross_pack_consistency_report(inp2)
    assert report2.state is CrossPackConsistencyState.BLOCKED
    assert any(
        i.issue_type is CrossPackConsistencyIssueType.INCOMPATIBLE_STATE_COMBINATION
        for i in report2.issues
    )

    # final_audit_pack COMPLETE while required section ref is missing.
    decl4 = CrossPackDeclaration(
        pack_id="final_audit_pack",
        version="1.0",
        declared_state="complete",
        section_ref_ids=("s1",),
        generated_at=now,
    )
    inp3 = CrossPackConsistencyInput(declarations=(decl4,), generated_at=now)
    report3 = build_cross_pack_consistency_report(inp3)
    assert report3.state is CrossPackConsistencyState.DEGRADED
    assert any(
        i.issue_type is CrossPackConsistencyIssueType.MISSING_EXPECTED_REF
        for i in report3.issues
    )


# -----------------------------------------------------------------------------
# 8. Aggregation
# -----------------------------------------------------------------------------


def test_aggregation_non_strict_and_strict(now: datetime) -> None:
    """Non-strict respects BLOCKED > DEGRADED > OK; strict promotes DEGRADED."""
    # Advisory only -> DEGRADED in non-strict mode.
    decl = CrossPackDeclaration(
        pack_id="p1", version="1.0", requires_manual_review=True, generated_at=now
    )
    inp = CrossPackConsistencyInput(declarations=(decl,), generated_at=now)
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.DEGRADED
    assert CrossPackConsistencyReasonCode.CONSISTENCY_DEGRADED in report.reason_codes

    # Adding a BLOCKING issue raises the overall state to BLOCKED.
    config = CrossPackConsistencyConfig(required_pack_ids=("missing",))
    inp2 = CrossPackConsistencyInput(
        declarations=(decl,), config=config, generated_at=now
    )
    report2 = build_cross_pack_consistency_report(inp2)
    assert report2.state is CrossPackConsistencyState.BLOCKED

    # Strict mode promotes a DEGRADED-only report to BLOCKED.
    config_strict = CrossPackConsistencyConfig(strict=True)
    inp3 = CrossPackConsistencyInput(
        declarations=(decl,), config=config_strict, generated_at=now
    )
    report3 = build_cross_pack_consistency_report(inp3)
    assert report3.state is CrossPackConsistencyState.BLOCKED
    assert CrossPackConsistencyReasonCode.SAFETY_BLOCKED in report3.reason_codes


def test_info_and_not_applicable_do_not_block(now: datetime) -> None:
    """INFO issues and NOT_APPLICABLE state do not raise the overall state."""
    decl = CrossPackDeclaration(pack_id="p1", version="1.0", generated_at=now)
    rule = CrossPackConsistencyRule(
        rule_type=CrossPackConsistencyRuleType.MANUAL_REVIEW,
        source_pack_id="p1",
        severity=CrossPackConsistencySeverity.INFO,
    )
    inp = CrossPackConsistencyInput(
        declarations=(decl,), rules=(rule,), generated_at=now
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.OK
    assert any(
        i.issue_type is CrossPackConsistencyIssueType.MISSING_MANUAL_REVIEW
        and i.severity is CrossPackConsistencySeverity.INFO
        for i in report.issues
    )

    empty = CrossPackConsistencyInput(generated_at=now)
    report_empty = build_cross_pack_consistency_report(empty)
    assert report_empty.state is CrossPackConsistencyState.NOT_APPLICABLE


# -----------------------------------------------------------------------------
# 9. Unsafe content
# -----------------------------------------------------------------------------


def test_unsafe_content_blocks_and_false_positives_are_safe(now: datetime) -> None:
    """Unsafe metadata and forbidden terms fail-closed; safe phrases do not."""
    inp1 = CrossPackConsistencyInput(
        metadata={"bad": b"value"}, generated_at=now
    )
    report1 = build_cross_pack_consistency_report(inp1)
    assert report1.state is CrossPackConsistencyState.BLOCKED
    assert report1.safety_flags.has_unsafe_content is True
    assert any(
        i.issue_type is CrossPackConsistencyIssueType.UNSAFE_CONTENT
        and CrossPackConsistencyReasonCode.UNSAFE_CONTENT in i.reason_codes
        for i in report1.issues
    )

    decl2 = CrossPackDeclaration(
        pack_id="p1",
        version="1.0",
        description="This pack is production ready",
        generated_at=now,
    )
    inp2 = CrossPackConsistencyInput(declarations=(decl2,), generated_at=now)
    report2 = build_cross_pack_consistency_report(inp2)
    assert report2.state is CrossPackConsistencyState.BLOCKED
    assert report2.safety_flags.has_forbidden_terms is True
    assert any(
        i.issue_type is CrossPackConsistencyIssueType.UNSAFE_CONTENT
        and CrossPackConsistencyReasonCode.FORBIDDEN_TERM_PRESENT in i.reason_codes
        for i in report2.issues
    )

    safe_decl = CrossPackDeclaration(
        pack_id="p2",
        version="1.0",
        title="Position sizing notes",
        description="Threshold order of operations along the border",
        generated_at=now,
    )
    inp3 = CrossPackConsistencyInput(declarations=(safe_decl,), generated_at=now)
    report3 = build_cross_pack_consistency_report(inp3)
    assert report3.state is CrossPackConsistencyState.OK
    assert report3.safety_flags.has_forbidden_terms is False
    assert report3.safety_flags.has_unsafe_content is False


# -----------------------------------------------------------------------------
# 10. Determinism
# -----------------------------------------------------------------------------


def test_determinism_and_no_mutation(now: datetime) -> None:
    """Identical inputs yield identical outputs and are never mutated."""
    # Determinism
    inp = _ok_input(now)
    report1 = build_cross_pack_consistency_report(inp)
    report2 = build_cross_pack_consistency_report(inp)

    assert report1.report_id == report2.report_id
    assert [i.issue_id for i in report1.issues] == [
        i.issue_id for i in report2.issues
    ]
    assert cross_pack_consistency_report_to_dict(report1) == cross_pack_consistency_report_to_dict(report2)
    assert cross_pack_consistency_report_to_json_text(report1) == cross_pack_consistency_report_to_json_text(report2)
    assert cross_pack_consistency_report_to_csv_text(report1) == cross_pack_consistency_report_to_csv_text(report2)
    assert cross_pack_consistency_report_to_markdown_text(report1) == cross_pack_consistency_report_to_markdown_text(report2)

    # No mutation
    decl = CrossPackDeclaration(
        pack_id="p1", version="1.0", generated_at=now
    )
    art = CrossPackArtifactRef(
        ref_id="a1", pack_id="p1", reference="ref", generated_at=now
    )
    sec = CrossPackSectionRef(
        ref_id="s1", pack_id="p1", reference="ref", generated_at=now
    )
    req = CrossPackRequirementRef(
        ref_id="r1", pack_id="p1", reference="ref", generated_at=now
    )
    claim = CrossPackStateClaim(
        subject_id="sub", state_label="ok", pack_id="p1"
    )
    rule = CrossPackConsistencyRule(
        rule_type=CrossPackConsistencyRuleType.COMPATIBLE_VERSION,
        source_pack_id="p1",
        expected_version="1.0",
    )
    metadata = {"author": "test"}
    inp_mutation = CrossPackConsistencyInput(
        declarations=(decl,),
        artifact_refs=(art,),
        section_refs=(sec,),
        requirement_refs=(req,),
        state_claims=(claim,),
        rules=(rule,),
        metadata=metadata,
        generated_at=now,
    )
    original = (
        inp_mutation.declarations,
        inp_mutation.artifact_refs,
        inp_mutation.section_refs,
        inp_mutation.requirement_refs,
        inp_mutation.state_claims,
        inp_mutation.rules,
        dict(inp_mutation.metadata),
    )

    build_cross_pack_consistency_report(inp_mutation)
    cross_pack_consistency_report_to_json_text(
        build_cross_pack_consistency_report(inp_mutation)
    )

    after = (
        inp_mutation.declarations,
        inp_mutation.artifact_refs,
        inp_mutation.section_refs,
        inp_mutation.requirement_refs,
        inp_mutation.state_claims,
        inp_mutation.rules,
        dict(inp_mutation.metadata),
    )
    assert after == original


# -----------------------------------------------------------------------------
# 12. Public exports
# -----------------------------------------------------------------------------


def test_public_exports_and_safety_boundaries(now: datetime) -> None:
    """The package exposes the engine and writer functions and stays audit-only."""
    import hunter.cross_pack_consistency as cpc

    assert hasattr(cpc, "build_cross_pack_consistency_report")
    assert hasattr(cpc, "CrossPackConsistencyInput")
    assert hasattr(cpc, "CrossPackConsistencyReport")
    assert hasattr(cpc, "write_cross_pack_consistency_report")
    assert hasattr(cpc, "cross_pack_consistency_report_to_json_text")
    assert hasattr(cpc, "cross_pack_consistency_report_to_csv_text")
    assert hasattr(cpc, "cross_pack_consistency_report_to_markdown_text")
    assert hasattr(cpc, "atomic_write_json_cross_pack_consistency_report")
    assert hasattr(cpc, "atomic_write_csv_cross_pack_consistency_report")
    assert hasattr(cpc, "atomic_write_markdown_cross_pack_consistency_report")

    report = build_cross_pack_consistency_report(_ok_input(now))
    text = cross_pack_consistency_report_to_markdown_text(report).lower()

    assert "research-only" in text or "audit-only" in text
    assert "not an approval" in text
    assert "certification" in text
    assert "production readiness" in text
    assert "trading readiness" in text
    assert "recommendation" in text
    assert "suitability assessment" in text
    assert "signal" in text

    for phrase in (
        "buy signal",
        "sell signal",
        "go long",
        "go short",
        "place orders",
        "execute orders",
        "live trading",
    ):
        assert phrase not in text, f"found actionable phrase: {phrase}"

    data = cross_pack_consistency_report_to_dict(report)
    assert "safety_notice" in data
    assert "not an approval" in data["safety_notice"].lower()


# -----------------------------------------------------------------------------
# 14. Opaque refs
# -----------------------------------------------------------------------------


def test_opaque_refs_remain_untouched(now: datetime) -> None:
    """Reference strings are opaque and never interpreted as filesystem paths."""
    ref_string = "data/audit_scorecard/audit_scorecard.json"
    decl = CrossPackDeclaration(
        pack_id="p1",
        version="1.0",
        artifact_ref_ids=("a1",),
        generated_at=now,
    )
    art = CrossPackArtifactRef(
        ref_id="a1",
        pack_id="p1",
        reference=ref_string,
        generated_at=now,
    )
    inp = CrossPackConsistencyInput(
        declarations=(decl,),
        artifact_refs=(art,),
        generated_at=now,
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.OK
    assert report.artifact_refs[0].reference == ref_string

    data = cross_pack_consistency_report_to_dict(report)
    assert data["artifact_refs"][0]["reference"] == ref_string

    # The engine did not require the path to exist on disk.
    assert not Path(ref_string).exists()
