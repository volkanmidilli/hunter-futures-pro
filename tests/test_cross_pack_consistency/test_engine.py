"""Tests for hunter.cross_pack_consistency.engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hunter.cross_pack_consistency import (
    CONFLICTING_STATE_CLAIM,
    CrossPackArtifactRef,
    CrossPackConsistencyConfig,
    CrossPackConsistencyIssueType,
    CrossPackConsistencyReasonCode,
    CrossPackConsistencyRule,
    CrossPackConsistencyRuleType,
    CrossPackConsistencySeverity,
    CrossPackConsistencyState,
    CrossPackDeclaration,
    CrossPackRequirementRef,
    CrossPackSectionRef,
    CrossPackStateClaim,
    CrossPackConsistencyInput,
    build_cross_pack_consistency_report,
)


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_empty_input_not_applicable() -> None:
    inp = CrossPackConsistencyInput()
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.NOT_APPLICABLE
    assert report.issues == ()
    assert report.data_quality.total_packs == 0
    assert CrossPackConsistencyReasonCode.NOT_APPLICABLE in report.reason_codes


def test_empty_input_with_generated_at_not_applicable() -> None:
    inp = CrossPackConsistencyInput(generated_at=_now())
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.NOT_APPLICABLE


def test_non_empty_input_no_issues_ok() -> None:
    """Non-empty input with no issues should return OK, not NOT_APPLICABLE."""
    now = _now()
    decl = CrossPackDeclaration(pack_id="p1", version="1.0", generated_at=now)
    inp = CrossPackConsistencyInput(declarations=(decl,), generated_at=now)
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.OK


def test_deterministic_report_id() -> None:
    now = _now()
    decl = CrossPackDeclaration(pack_id="p1", version="1.0")
    inp1 = CrossPackConsistencyInput(
        declarations=(decl,),
        generated_at=now,
    )
    inp2 = CrossPackConsistencyInput(
        declarations=(decl,),
        generated_at=now,
    )
    assert build_cross_pack_consistency_report(inp1).report_id == build_cross_pack_consistency_report(inp2).report_id


def test_report_id_changes_with_input() -> None:
    now = _now()
    inp1 = CrossPackConsistencyInput(
        declarations=(CrossPackDeclaration(pack_id="p1", version="1.0"),),
        generated_at=now,
    )
    inp2 = CrossPackConsistencyInput(
        declarations=(CrossPackDeclaration(pack_id="p2", version="1.0"),),
        generated_at=now,
    )
    assert build_cross_pack_consistency_report(inp1).report_id != build_cross_pack_consistency_report(inp2).report_id


def test_declarations_copied_sorted() -> None:
    d1 = CrossPackDeclaration(pack_id="p2", version="1.0")
    d2 = CrossPackDeclaration(pack_id="p1", version="1.0")
    inp = CrossPackConsistencyInput(declarations=(d1, d2))
    report = build_cross_pack_consistency_report(inp)
    assert [d.pack_id for d in report.declarations] == ["p1", "p2"]


def test_duplicate_pack_id_blocking() -> None:
    inp = CrossPackConsistencyInput(
        declarations=(
            CrossPackDeclaration(pack_id="p1", version="1.0"),
            CrossPackDeclaration(pack_id="p1", version="2.0"),
        ),
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.BLOCKED
    issue = report.issues[0]
    assert issue.issue_type is CrossPackConsistencyIssueType.DUPLICATE_ID
    assert issue.severity is CrossPackConsistencySeverity.BLOCKING


def test_duplicate_ref_within_kind_advisory() -> None:
    inp = CrossPackConsistencyInput(
        artifact_refs=(
            CrossPackArtifactRef(ref_id="a1", pack_id="p1", reference="ref1"),
            CrossPackArtifactRef(ref_id="a1", pack_id="p1", reference="ref2"),
        ),
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.DEGRADED
    issue = next(i for i in report.issues if i.issue_type is CrossPackConsistencyIssueType.DUPLICATE_ID)
    assert issue.severity is CrossPackConsistencySeverity.ADVISORY


def test_missing_required_pack() -> None:
    config = CrossPackConsistencyConfig(required_pack_ids=("p1",))
    inp = CrossPackConsistencyInput(config=config)
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.BLOCKED
    issue = report.issues[0]
    assert issue.issue_type is CrossPackConsistencyIssueType.MISSING_REQUIRED_PACK


def test_missing_expected_artifact_ref() -> None:
    decl = CrossPackDeclaration(
        pack_id="p1",
        version="1.0",
        artifact_ref_ids=("a1",),
    )
    inp = CrossPackConsistencyInput(declarations=(decl,))
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.DEGRADED
    issue = report.issues[0]
    assert issue.issue_type is CrossPackConsistencyIssueType.MISSING_EXPECTED_REF


def test_missing_expected_section_ref() -> None:
    decl = CrossPackDeclaration(
        pack_id="p1",
        version="1.0",
        section_ref_ids=("s1",),
    )
    inp = CrossPackConsistencyInput(declarations=(decl,))
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.DEGRADED
    issue = report.issues[0]
    assert issue.issue_type is CrossPackConsistencyIssueType.MISSING_EXPECTED_REF


def test_missing_expected_requirement_ref() -> None:
    decl = CrossPackDeclaration(
        pack_id="p1",
        version="1.0",
        requirement_ref_ids=("r1",),
    )
    inp = CrossPackConsistencyInput(declarations=(decl,))
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.DEGRADED
    issue = report.issues[0]
    assert issue.issue_type is CrossPackConsistencyIssueType.MISSING_EXPECTED_REF


def test_orphan_artifact_ref() -> None:
    art = CrossPackArtifactRef(ref_id="a1", pack_id="p1", reference="ref")
    decl = CrossPackDeclaration(pack_id="p1", version="1.0")
    inp = CrossPackConsistencyInput(
        declarations=(decl,),
        artifact_refs=(art,),
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.DEGRADED
    issue = next(i for i in report.issues if i.issue_type is CrossPackConsistencyIssueType.ORPHAN_REF)
    assert issue.severity is CrossPackConsistencySeverity.ADVISORY


def test_orphan_section_ref() -> None:
    sec = CrossPackSectionRef(ref_id="s1", pack_id="p1", reference="ref")
    decl = CrossPackDeclaration(pack_id="p1", version="1.0", section_ref_ids=("s1",))
    inp = CrossPackConsistencyInput(
        declarations=(decl,),
        section_refs=(sec,),
    )
    report = build_cross_pack_consistency_report(inp)
    # Declared expected section s1 matches the section ref, so no orphan.
    orphan_issues = [i for i in report.issues if i.issue_type is CrossPackConsistencyIssueType.ORPHAN_REF]
    assert len(orphan_issues) == 0


def test_incompatible_version_rule() -> None:
    decl1 = CrossPackDeclaration(pack_id="p1", version="1.0")
    decl2 = CrossPackDeclaration(pack_id="p2", version="2.0")
    rule = CrossPackConsistencyRule(
        rule_type=CrossPackConsistencyRuleType.COMPATIBLE_VERSION,
        source_pack_id="p1",
        target_pack_id="p2",
        expected_version="1.0",
        severity=CrossPackConsistencySeverity.BLOCKING,
    )
    inp = CrossPackConsistencyInput(
        declarations=(decl1, decl2),
        rules=(rule,),
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.BLOCKED
    issue = report.issues[0]
    assert issue.issue_type is CrossPackConsistencyIssueType.INCOMPATIBLE_VERSION


def test_stale_declaration() -> None:
    now = _now()
    stale_time = now - timedelta(days=2)
    config = CrossPackConsistencyConfig(staleness_threshold_seconds=86400)
    decl = CrossPackDeclaration(
        pack_id="p1",
        version="1.0",
        generated_at=stale_time,
    )
    inp = CrossPackConsistencyInput(
        declarations=(decl,),
        config=config,
        generated_at=now,
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.DEGRADED
    issue = next(i for i in report.issues if i.issue_type is CrossPackConsistencyIssueType.STALE_DECLARATION)
    assert issue.severity is CrossPackConsistencySeverity.ADVISORY


def test_stale_declaration_rule_dedup_with_builtin() -> None:
    now = _now()
    stale_time = now - timedelta(days=2)
    config = CrossPackConsistencyConfig(staleness_threshold_seconds=86400)
    rule = CrossPackConsistencyRule(
        rule_type=CrossPackConsistencyRuleType.STALE_DECLARATION,
        source_pack_id="p1",
        severity=CrossPackConsistencySeverity.ADVISORY,
    )
    decl = CrossPackDeclaration(
        pack_id="p1",
        version="1.0",
        generated_at=stale_time,
    )
    inp = CrossPackConsistencyInput(
        declarations=(decl,),
        rules=(rule,),
        config=config,
        generated_at=now,
    )
    report = build_cross_pack_consistency_report(inp)
    stale_issues = [i for i in report.issues if i.issue_type is CrossPackConsistencyIssueType.STALE_DECLARATION]
    assert len(stale_issues) == 1


def test_compatible_state_rule_forbidden_state() -> None:
    decl = CrossPackDeclaration(pack_id="p1", version="1.0", declared_state="BLOCKED")
    rule = CrossPackConsistencyRule(
        rule_type=CrossPackConsistencyRuleType.COMPATIBLE_STATE,
        source_pack_id="p1",
        forbidden_states=("blocked",),
        severity=CrossPackConsistencySeverity.BLOCKING,
    )
    inp = CrossPackConsistencyInput(
        declarations=(decl,),
        rules=(rule,),
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.BLOCKED
    issue = report.issues[0]
    assert issue.issue_type is CrossPackConsistencyIssueType.INCOMPATIBLE_STATE_COMBINATION


def test_conflicting_state_claims_builtin() -> None:
    claim1 = CrossPackStateClaim(subject_id="sub", state_label="ok", pack_id="p1")
    claim2 = CrossPackStateClaim(subject_id="sub", state_label="blocked", pack_id="p2")
    inp = CrossPackConsistencyInput(
        state_claims=(claim1, claim2),
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.BLOCKED
    issue = report.issues[0]
    assert issue.issue_type is CrossPackConsistencyIssueType.CONFLICTING_STATE


def test_unknown_upstream_state() -> None:
    decl = CrossPackDeclaration(pack_id="p1", version="1.0", declared_state="weird")
    config = CrossPackConsistencyConfig(allowed_state_labels=("ok", "blocked"))
    inp = CrossPackConsistencyInput(
        declarations=(decl,),
        config=config,
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.DEGRADED
    issue = report.issues[0]
    assert issue.issue_type is CrossPackConsistencyIssueType.UNKNOWN_UPSTREAM_STATE


def test_missing_manual_review() -> None:
    decl = CrossPackDeclaration(pack_id="p1", version="1.0", requires_manual_review=True)
    inp = CrossPackConsistencyInput(declarations=(decl,))
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.DEGRADED
    issue = next(i for i in report.issues if i.issue_type is CrossPackConsistencyIssueType.MISSING_MANUAL_REVIEW)
    assert issue.severity is CrossPackConsistencySeverity.ADVISORY


def test_manual_review_rule_satisfied() -> None:
    decl = CrossPackDeclaration(pack_id="p1", version="1.0", requires_manual_review=True)
    rule = CrossPackConsistencyRule(
        rule_type=CrossPackConsistencyRuleType.MANUAL_REVIEW,
        source_pack_id="p1",
    )
    inp = CrossPackConsistencyInput(
        declarations=(decl,),
        rules=(rule,),
    )
    report = build_cross_pack_consistency_report(inp)
    manual_issues = [i for i in report.issues if i.issue_type is CrossPackConsistencyIssueType.MISSING_MANUAL_REVIEW]
    # Built-in already covers it; rule is duplicative, so dedup should leave one.
    assert len(manual_issues) <= 1


def test_required_pack_rule_dedup() -> None:
    config = CrossPackConsistencyConfig(required_pack_ids=("p1",))
    rule = CrossPackConsistencyRule(
        rule_type=CrossPackConsistencyRuleType.REQUIRED_PACK,
        source_pack_id="p1",
    )
    inp = CrossPackConsistencyInput(
        rules=(rule,),
        config=config,
    )
    report = build_cross_pack_consistency_report(inp)
    missing = [i for i in report.issues if i.issue_type is CrossPackConsistencyIssueType.MISSING_REQUIRED_PACK]
    assert len(missing) == 1


def test_expected_ref_rule_dedup() -> None:
    decl = CrossPackDeclaration(
        pack_id="p1",
        version="1.0",
        artifact_ref_ids=("a1",),
    )
    rule = CrossPackConsistencyRule(
        rule_type=CrossPackConsistencyRuleType.EXPECTED_REF,
        source_pack_id="p1",
        ref_kind="artifact",
        ref_id="a1",
    )
    inp = CrossPackConsistencyInput(
        declarations=(decl,),
        rules=(rule,),
    )
    report = build_cross_pack_consistency_report(inp)
    missing = [i for i in report.issues if i.issue_type is CrossPackConsistencyIssueType.MISSING_EXPECTED_REF]
    assert len(missing) == 1


def test_forbidden_term_present_blocks() -> None:
    decl = CrossPackDeclaration(
        pack_id="p1",
        version="1.0",
        description="This pack is production ready",
    )
    inp = CrossPackConsistencyInput(declarations=(decl,))
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.BLOCKED
    assert report.safety_flags.has_forbidden_terms is True
    issue = report.issues[0]
    assert issue.issue_type is CrossPackConsistencyIssueType.UNSAFE_CONTENT


def test_forbidden_term_no_false_positives() -> None:
    decl = CrossPackDeclaration(
        pack_id="p1",
        version="1.0",
        description="Threshold order of operations along the border",
    )
    inp = CrossPackConsistencyInput(declarations=(decl,))
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.OK


def test_unsafe_content_metadata() -> None:
    inp = CrossPackConsistencyInput(metadata={"key": b"value"})
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.BLOCKED
    assert report.safety_flags.has_unsafe_content is True


def test_strict_mode_promotes_degraded_to_blocked() -> None:
    decl = CrossPackDeclaration(pack_id="p1", version="1.0", requires_manual_review=True)
    config = CrossPackConsistencyConfig(strict=True)
    inp = CrossPackConsistencyInput(
        declarations=(decl,),
        config=config,
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.BLOCKED


def test_info_does_not_block() -> None:
    decl = CrossPackDeclaration(pack_id="p1", version="1.0")
    rule = CrossPackConsistencyRule(
        rule_type=CrossPackConsistencyRuleType.MANUAL_REVIEW,
        source_pack_id="p1",
        severity=CrossPackConsistencySeverity.INFO,
    )
    inp = CrossPackConsistencyInput(
        declarations=(decl,),
        rules=(rule,),
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.OK


def test_state_label_normalization() -> None:
    decl = CrossPackDeclaration(pack_id="p1", version="1.0", declared_state="  OK  ")
    config = CrossPackConsistencyConfig(allowed_state_labels=("ok",))
    inp = CrossPackConsistencyInput(
        declarations=(decl,),
        config=config,
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.OK


def test_path_refs_treated_as_opaque_strings() -> None:
    art = CrossPackArtifactRef(
        ref_id="a1",
        pack_id="p1",
        reference="/some/path/that/does/not/exist.json",
    )
    decl = CrossPackDeclaration(pack_id="p1", version="1.0", artifact_ref_ids=("a1",))
    inp = CrossPackConsistencyInput(
        declarations=(decl,),
        artifact_refs=(art,),
    )
    report = build_cross_pack_consistency_report(inp)
    # Should not fail due to missing file; refs are opaque.
    assert report.state is CrossPackConsistencyState.OK


def test_project_version_precedence() -> None:
    now = _now()
    decl = CrossPackDeclaration(pack_id="p1", version="1.0")
    inp = CrossPackConsistencyInput(
        declarations=(decl,),
        project_version="1.2.3",
        config=CrossPackConsistencyConfig(project_version="0.0.0"),
        generated_at=now,
    )
    report = build_cross_pack_consistency_report(inp)
    assert report.project_version == "1.2.3"


def test_issue_id_deterministic() -> None:
    decl = CrossPackDeclaration(pack_id="p1", version="1.0")
    inp = CrossPackConsistencyInput(declarations=(decl,))
    report1 = build_cross_pack_consistency_report(inp)
    report2 = build_cross_pack_consistency_report(inp)
    assert [i.issue_id for i in report1.issues] == [i.issue_id for i in report2.issues]


def test_issue_deduplication() -> None:
    # Two duplicate pack IDs produce only one duplicate issue.
    inp = CrossPackConsistencyInput(
        declarations=(
            CrossPackDeclaration(pack_id="p1", version="1.0"),
            CrossPackDeclaration(pack_id="p1", version="2.0"),
            CrossPackDeclaration(pack_id="p1", version="3.0"),
        ),
    )
    report = build_cross_pack_consistency_report(inp)
    duplicate_issues = [i for i in report.issues if i.issue_type is CrossPackConsistencyIssueType.DUPLICATE_ID]
    assert len(duplicate_issues) == 1


def test_input_not_mutated() -> None:
    decl = CrossPackDeclaration(pack_id="p1", version="1.0")
    inp = CrossPackConsistencyInput(declarations=(decl,))
    original_pack_id = inp.declarations[0].pack_id
    build_cross_pack_consistency_report(inp)
    assert inp.declarations[0].pack_id == original_pack_id


def test_reason_code_includes_safety_constants() -> None:
    assert CrossPackConsistencyReasonCode.NO_FILE_INGESTION.value == "no_file_ingestion"
    assert CrossPackConsistencyReasonCode.NO_NETWORK_CONNECTION.value == "no_network_connection"


def test_public_api_exports() -> None:
    from hunter import cross_pack_consistency

    assert hasattr(cross_pack_consistency, "build_cross_pack_consistency_report")
    assert hasattr(cross_pack_consistency, "CrossPackConsistencyReport")
