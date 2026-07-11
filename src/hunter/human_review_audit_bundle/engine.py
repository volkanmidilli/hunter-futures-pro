"""Pure-local engine for hunter.human_review_audit_bundle.

MVP-43 — Local Research Human Review Audit Bundle Export.

The engine is deterministic, does not touch the filesystem, and never opens,
follows, traverses, validates, fetches, or executes any reference. It accepts
caller-provided in-memory reports from MVP-40, MVP-41, and MVP-42 and produces
a normalized, human-audit bundle report.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
from json import dumps
from typing import Any

from hunter.human_review_decision_log.models import HumanReviewDecisionLogReport
from hunter.human_review_decision_log_consistency.models import (
    HumanReviewDecisionLogConsistencyReport,
)
from hunter.human_review_queue.models import HumanReviewQueueReport

from .models import (
    BUNDLE_KIND,
    HUMAN_REVIEW_AUDIT_BUNDLE_VERSION,
    SAFETY_NOTICE,
    HumanReviewAuditBundleConfig,
    HumanReviewAuditBundleDataQuality,
    HumanReviewAuditBundleIssue,
    HumanReviewAuditBundleReasonCode,
    HumanReviewAuditBundleReport,
    HumanReviewAuditBundleSafetyFlags,
    HumanReviewAuditBundleSection,
    HumanReviewAuditBundleSeverity,
    HumanReviewAuditBundleState,
)


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


_STATE_PRECEDENCE: dict[str, int] = {
    "ok": 0,
    "not_applicable": 1,
    "degraded": 2,
    "blocked": 3,
}


_STATE_ENUM_TO_BUNDLE: dict[str, HumanReviewAuditBundleState] = {
    "ok": HumanReviewAuditBundleState.OK,
    "not_applicable": HumanReviewAuditBundleState.NOT_APPLICABLE,
    "degraded": HumanReviewAuditBundleState.DEGRADED,
    "blocked": HumanReviewAuditBundleState.BLOCKED,
}


def _bundle_state_from_value(value: str) -> HumanReviewAuditBundleState:
    return _STATE_ENUM_TO_BUNDLE.get(value.lower(), HumanReviewAuditBundleState.NOT_APPLICABLE)


# ---------------------------------------------------------------------------
# Deterministic ID helpers
# ---------------------------------------------------------------------------


def _canonical_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(timezone.utc).isoformat()


def _build_bundle_id(
    queue_report_id: str,
    decision_log_report_id: str,
    consistency_report_id: str,
    project_version: str,
    generated_at: datetime,
) -> str:
    """Return a deterministic bundle identifier.

    The ID is a SHA-256 digest over the sorted upstream report IDs, bundle
    version, and generation timestamp. No time-now, random, env, path, process,
    or network values are included.
    """
    payload = {
        "kind": BUNDLE_KIND,
        "project_version": project_version,
        "generated_at": _canonical_datetime(generated_at),
        "upstream_report_ids": sorted(
            [
                str(queue_report_id).strip(),
                str(decision_log_report_id).strip(),
                str(consistency_report_id).strip(),
            ]
        ),
    }
    digest = sha256(
        dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    return f"bundle-{digest[:24]}"


def _build_report_id(bundle_id: str, generated_at: datetime) -> str:
    """Return a deterministic report_id for the bundle report."""
    payload = {
        "kind": BUNDLE_KIND,
        "bundle_id": bundle_id,
        "generated_at": _canonical_datetime(generated_at),
    }
    digest = sha256(
        dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    return f"human-review-audit-bundle-{digest[:16]}"


def _build_section_id(section_kind: str, upstream_report_id: str, bundle_id: str) -> str:
    """Return a deterministic section_id."""
    payload = {
        "kind": "bundle_section",
        "section_kind": section_kind,
        "upstream_report_id": str(upstream_report_id).strip(),
        "bundle_id": bundle_id,
    }
    digest = sha256(
        dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    return f"section-{digest[:16]}"


def _build_issue_id(source_section_kind: str, source_id: str, bundle_id: str) -> str:
    """Return a deterministic issue_id."""
    payload = {
        "kind": "bundle_issue",
        "source_section_kind": source_section_kind,
        "source_id": str(source_id).strip(),
        "bundle_id": bundle_id,
    }
    digest = sha256(
        dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    return f"issue-{digest[:16]}"


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def _resolve_generated_at(generated_at: datetime | None) -> datetime:
    return generated_at if generated_at is not None else datetime.now(timezone.utc)


def _is_report_empty_or_not_applicable(report: Any, kind: str) -> bool:
    """Return True if the upstream report is empty or not applicable.

    The check is conservative and does not re-validate report internals. It
    looks at the state enum value and either the primary data tuples or the
    data-quality counters that are known to all three upstream report types.
    A report is treated as non-empty if its data-quality counters indicate
    content even when the caller only passes summary information.
    """
    state = getattr(report, "state", None)
    state_value = state.value if state is not None else "not_applicable"
    if state_value == "not_applicable":
        return True

    data_quality = getattr(report, "data_quality", None)

    if kind == "queue":
        if data_quality is not None:
            if getattr(data_quality, "total_source_records", 0) > 0 or getattr(
                data_quality, "total_queue_entries", 0
            ) > 0:
                return False
        return len(getattr(report, "queue_entries", ())) == 0 and len(getattr(report, "source_records", ())) == 0

    if kind == "decision_log":
        if data_quality is not None:
            if (
                getattr(data_quality, "total_decision_records", 0) > 0
                or getattr(data_quality, "total_queue_entry_refs", 0) > 0
                or getattr(data_quality, "total_links", 0) > 0
            ):
                return False
        return (
            len(getattr(report, "decision_records", ())) == 0
            and len(getattr(report, "queue_entry_refs", ())) == 0
        )

    if kind == "consistency":
        if data_quality is not None:
            if (
                getattr(data_quality, "total_queue_entries", 0) > 0
                or getattr(data_quality, "total_decision_log_refs", 0) > 0
            ):
                return False
        return len(getattr(report, "cross_references", ())) == 0

    return False


# ---------------------------------------------------------------------------
# Section building
# ---------------------------------------------------------------------------


def _build_section_summary(report: Any, kind: str, include: bool) -> Mapping[str, Any]:
    """Return a derived summary mapping from upstream data_quality."""
    if not include:
        return {}
    data_quality = getattr(report, "data_quality", None)
    if data_quality is None:
        return {}

    summary: dict[str, Any] = {}

    if kind == "queue":
        for attr in (
            "total_source_records",
            "total_queue_entries",
            "total_issues",
            "duplicate_source_id_count",
            "duplicate_queue_entry_count",
            "orphan_related_record_count",
            "stale_source_record_count",
            "unsafe_content_count",
            "forbidden_term_count",
            "blocking_count",
            "advisory_count",
            "info_count",
        ):
            if hasattr(data_quality, attr):
                summary[attr] = getattr(data_quality, attr)

    elif kind == "decision_log":
        for attr in (
            "total_queue_entry_refs",
            "total_decision_records",
            "total_links",
            "total_issues",
            "total_decision_results",
            "duplicate_queue_entry_id_count",
            "duplicate_decision_id_count",
            "semantic_duplicate_decision_count",
            "orphan_decision_count",
            "conflicting_decision_count",
            "conflicting_outcome_count",
            "unsafe_content_count",
            "forbidden_term_count",
        ):
            if hasattr(data_quality, attr):
                summary[attr] = getattr(data_quality, attr)

    elif kind == "consistency":
        for attr in (
            "total_queue_entries",
            "total_decision_log_refs",
            "matched_refs",
            "orphan_queue_entries",
            "orphan_decision_log_refs",
            "mismatched_refs",
            "blocking_issues",
            "advisory_issues",
            "info_findings",
            "unsafe_content_count",
            "forbidden_term_count",
        ):
            if hasattr(data_quality, attr):
                summary[attr] = getattr(data_quality, attr)

    return summary


def _build_section(
    kind: str,
    report: Any,
    bundle_id: str,
    generated_at: datetime,
    include_summary: bool,
) -> HumanReviewAuditBundleSection | None:
    """Build a bundle section from one upstream report."""
    state = getattr(report, "state", None)
    state_value = state.value if state is not None else "not_applicable"
    # Skip sections that are purely not-applicable and empty; they are handled
    # by the NOT_APPLICABLE early-exit. Include them if they have a non-NA
    # state or if the section is explicitly requested for diagnostic purposes.
    if state_value == "not_applicable" and not _build_section_summary(report, kind, include_summary):
        return None

    reason_codes = getattr(report, "reason_codes", ())
    rc_strings = tuple(str(rc) for rc in reason_codes)
    section_id = _build_section_id(kind, getattr(report, "report_id", ""), bundle_id)
    summary = _build_section_summary(report, kind, include_summary)
    metadata = getattr(report, "metadata", {})
    section_generated_at = getattr(report, "generated_at", None) or generated_at
    return HumanReviewAuditBundleSection(
        section_id=section_id,
        section_kind=kind,
        upstream_report_id=getattr(report, "report_id", ""),
        upstream_state=state_value,
        upstream_reason_codes=rc_strings,
        generated_at=section_generated_at,
        summary=summary,
        metadata=metadata,
        notes=getattr(report, "notes", ""),
    )


# ---------------------------------------------------------------------------
# Issue carry-forward
# ---------------------------------------------------------------------------


def _severity_from_state(state_value: str) -> str:
    """Map upstream state to bundle issue severity."""
    return {
        "blocked": HumanReviewAuditBundleSeverity.BLOCKING.value,
        "degraded": HumanReviewAuditBundleSeverity.ADVISORY.value,
        "not_applicable": HumanReviewAuditBundleSeverity.INFO.value,
        "ok": HumanReviewAuditBundleSeverity.INFO.value,
    }.get(state_value.lower(), HumanReviewAuditBundleSeverity.INFO.value)


def _carry_forward_upstream_issues(
    queue_report: HumanReviewQueueReport,
    decision_log_report: HumanReviewDecisionLogReport,
    consistency_report: HumanReviewDecisionLogConsistencyReport,
    bundle_id: str,
    include: bool,
) -> tuple[HumanReviewAuditBundleIssue, ...]:
    """Carry forward upstream issue references into bundle issues."""
    if not include:
        return ()

    carried: list[HumanReviewAuditBundleIssue] = []
    generated_at = datetime.now(timezone.utc)

    for issue in queue_report.issues:
        carried.append(
            HumanReviewAuditBundleIssue(
                issue_id=_build_issue_id("queue", getattr(issue, "issue_id", ""), bundle_id),
                issue_type=getattr(issue, "issue_type", ""),
                severity=str(getattr(issue, "severity", "info")),
                reason_codes=tuple(str(rc) for rc in getattr(issue, "reason_codes", ())),
                source_section_kind="queue",
                source_id=getattr(issue, "issue_id", ""),
                title=getattr(issue, "title", ""),
                description=getattr(issue, "description", ""),
                generated_at=getattr(issue, "generated_at", None) or generated_at,
            )
        )

    for issue in decision_log_report.issues:
        carried.append(
            HumanReviewAuditBundleIssue(
                issue_id=_build_issue_id("decision_log", getattr(issue, "issue_id", ""), bundle_id),
                issue_type=getattr(issue, "issue_type", ""),
                severity=str(getattr(issue, "severity", "info")),
                reason_codes=tuple(str(rc) for rc in getattr(issue, "reason_codes", ())),
                source_section_kind="decision_log",
                source_id=getattr(issue, "issue_id", ""),
                title=getattr(issue, "title", ""),
                description=getattr(issue, "description", ""),
                generated_at=getattr(issue, "generated_at", None) or generated_at,
            )
        )

    for issue in consistency_report.issues:
        carried.append(
            HumanReviewAuditBundleIssue(
                issue_id=_build_issue_id("consistency", getattr(issue, "issue_id", ""), bundle_id),
                issue_type=getattr(issue, "issue_type", ""),
                severity=str(getattr(issue, "severity", "info")),
                reason_codes=tuple(str(rc) for rc in getattr(issue, "reason_codes", ())),
                source_section_kind="consistency",
                source_id=getattr(issue, "issue_id", ""),
                title=getattr(issue, "title", ""),
                description=getattr(issue, "description", ""),
                generated_at=getattr(issue, "generated_at", None) or generated_at,
            )
        )

    return tuple(carried)


def _carry_forward_upstream_state_issues(
    queue_report: HumanReviewQueueReport,
    decision_log_report: HumanReviewDecisionLogReport,
    consistency_report: HumanReviewDecisionLogConsistencyReport,
    bundle_id: str,
    include: bool,
) -> tuple[HumanReviewAuditBundleIssue, ...]:
    """Emit one bundle-level issue per upstream non-OK state."""
    if not include:
        return ()

    generated_at = datetime.now(timezone.utc)
    emitted: list[HumanReviewAuditBundleIssue] = []

    upstream_items = [
        ("queue", queue_report),
        ("decision_log", decision_log_report),
        ("consistency", consistency_report),
    ]

    for kind, report in upstream_items:
        state = getattr(report, "state", None)
        state_value = state.value if state is not None else "not_applicable"
        if state_value in ("ok", "not_applicable"):
            continue
        severity = _severity_from_state(state_value)
        report_id = getattr(report, "report_id", "")
        title = f"Upstream {kind} report is {state_value}"
        description = (
            f"Upstream {kind} report {report_id!r} has aggregate state "
            f"{state_value!r}; carrying forward into bundle."
        )
        emitted.append(
            HumanReviewAuditBundleIssue(
                issue_id=_build_issue_id(kind, f"state-{state_value}", bundle_id),
                issue_type=f"upstream_{state_value}",
                severity=severity,
                reason_codes=(f"upstream_{state_value}",),
                source_section_kind=kind,
                source_id=report_id,
                title=title,
                description=description,
                generated_at=generated_at,
            )
        )

    return tuple(emitted)


# ---------------------------------------------------------------------------
# Aggregate state and reason codes
# ---------------------------------------------------------------------------


def _aggregate_state(
    upstream_states: list[str],
    issues: tuple[HumanReviewAuditBundleIssue, ...],
    strict: bool,
) -> HumanReviewAuditBundleState:
    """Compute aggregate bundle state from upstream states and issues."""
    base_precedence = max(
        (_STATE_PRECEDENCE.get(s.lower(), 0) for s in upstream_states),
        default=0,
    )

    issue_precedence = 0
    for issue in issues:
        sev = issue.severity.lower()
        if sev == HumanReviewAuditBundleSeverity.BLOCKING.value:
            issue_precedence = max(issue_precedence, 3)
        elif sev == HumanReviewAuditBundleSeverity.ADVISORY.value:
            issue_precedence = max(issue_precedence, 2)
        elif sev == HumanReviewAuditBundleSeverity.INFO.value:
            issue_precedence = max(issue_precedence, 1)

    precedence = max(base_precedence, issue_precedence)
    state = HumanReviewAuditBundleState.OK if precedence == 0 else _bundle_state_from_value(
        [k for k, v in _STATE_PRECEDENCE.items() if v == precedence][0]
    )

    if strict and state in (
        HumanReviewAuditBundleState.DEGRADED,
        HumanReviewAuditBundleState.NOT_APPLICABLE,
    ):
        return HumanReviewAuditBundleState.BLOCKED
    return state


def _build_reason_codes(
    state: HumanReviewAuditBundleState,
    upstream_states: list[str],
    unsafe_content_count: int,
    forbidden_term_count: int,
    empty_input: bool = False,
) -> tuple[HumanReviewAuditBundleReasonCode, ...]:
    """Build the bundle-level reason code tuple."""
    codes: set[HumanReviewAuditBundleReasonCode] = {
        HumanReviewAuditBundleReasonCode.RESEARCH_ONLY,
        HumanReviewAuditBundleReasonCode.HUMAN_AUDIT_ONLY,
        HumanReviewAuditBundleReasonCode.NO_EXECUTABLE_ACTIONS,
        HumanReviewAuditBundleReasonCode.NO_TRADING_INSTRUCTIONS,
        HumanReviewAuditBundleReasonCode.NO_APPROVAL_CLAIMS,
        HumanReviewAuditBundleReasonCode.REFERENCES_OPAQUE,
        HumanReviewAuditBundleReasonCode.NO_NETWORK,
        HumanReviewAuditBundleReasonCode.NO_SERVER,
        HumanReviewAuditBundleReasonCode.NO_DATABASE,
    }

    if state == HumanReviewAuditBundleState.OK:
        codes.add(HumanReviewAuditBundleReasonCode.OK)
    elif state == HumanReviewAuditBundleState.NOT_APPLICABLE:
        codes.add(HumanReviewAuditBundleReasonCode.NOT_APPLICABLE)
        if empty_input:
            codes.add(HumanReviewAuditBundleReasonCode.EMPTY_INPUT_NOT_APPLICABLE)
    elif state in (HumanReviewAuditBundleState.DEGRADED, HumanReviewAuditBundleState.BLOCKED):
        codes.add(HumanReviewAuditBundleReasonCode.BUNDLE_DEGRADED)

    for s in upstream_states:
        sv = s.lower()
        if sv == "blocked":
            codes.add(HumanReviewAuditBundleReasonCode.UPSTREAM_BLOCKED)
        elif sv == "degraded":
            codes.add(HumanReviewAuditBundleReasonCode.UPSTREAM_DEGRADED)
        elif sv == "not_applicable":
            codes.add(HumanReviewAuditBundleReasonCode.UPSTREAM_NOT_APPLICABLE)

    if unsafe_content_count:
        codes.add(HumanReviewAuditBundleReasonCode.UNSAFE_CONTENT)
    if forbidden_term_count:
        codes.add(HumanReviewAuditBundleReasonCode.FORBIDDEN_TERM_PRESENT)

    return tuple(sorted(codes, key=lambda c: c.value))


# ---------------------------------------------------------------------------
# Data quality and safety flags
# ---------------------------------------------------------------------------


def _count_severity(issues: tuple[HumanReviewAuditBundleIssue, ...], severity: str) -> int:
    return sum(1 for issue in issues if issue.severity.lower() == severity)


def _build_data_quality(
    sections: tuple[HumanReviewAuditBundleSection, ...],
    issues: tuple[HumanReviewAuditBundleIssue, ...],
    queue_report: HumanReviewQueueReport,
    decision_log_report: HumanReviewDecisionLogReport,
    consistency_report: HumanReviewDecisionLogConsistencyReport,
    include_summary: bool,
) -> HumanReviewAuditBundleDataQuality:
    """Build bundle-level data quality counters."""
    upstream_unsafe = 0
    upstream_forbidden = 0

    queue_dq = getattr(queue_report, "data_quality", None)
    if queue_dq is not None:
        upstream_unsafe = max(upstream_unsafe, getattr(queue_dq, "unsafe_content_count", 0))
        upstream_forbidden = max(upstream_forbidden, getattr(queue_dq, "forbidden_term_count", 0))

    decision_dq = getattr(decision_log_report, "data_quality", None)
    if decision_dq is not None:
        upstream_unsafe = max(upstream_unsafe, getattr(decision_dq, "unsafe_content_count", 0))
        upstream_forbidden = max(upstream_forbidden, getattr(decision_dq, "forbidden_term_count", 0))

    consistency_dq = getattr(consistency_report, "data_quality", None)
    if consistency_dq is not None:
        upstream_unsafe = max(upstream_unsafe, getattr(consistency_dq, "unsafe_content_count", 0))
        upstream_forbidden = max(upstream_forbidden, getattr(consistency_dq, "forbidden_term_count", 0))

    queue_entry_count = 0
    decision_result_count = 0
    consistency_cross_reference_count = 0

    if include_summary:
        if queue_dq is not None:
            queue_entry_count = max(queue_entry_count, getattr(queue_dq, "total_queue_entries", 0))
        if decision_dq is not None:
            decision_result_count = max(decision_result_count, getattr(decision_dq, "total_decision_results", 0))
        if consistency_dq is not None:
            consistency_cross_reference_count = max(
                consistency_cross_reference_count,
                getattr(consistency_dq, "total_queue_entries", 0),
            )
        # Also allow len() fallbacks if data_quality did not populate the field.
        if queue_entry_count == 0:
            queue_entry_count = len(getattr(queue_report, "queue_entries", ()))
        if decision_result_count == 0:
            decision_result_count = len(getattr(decision_log_report, "decision_results", ()))
        if consistency_cross_reference_count == 0:
            consistency_cross_reference_count = len(getattr(consistency_report, "cross_references", ()))

    return HumanReviewAuditBundleDataQuality(
        section_count=len(sections),
        upstream_issue_count=sum(
            1 for issue in issues if issue.source_section_kind != "bundle" and issue.source_section_kind != ""
        ),
        blocking_issues=_count_severity(issues, HumanReviewAuditBundleSeverity.BLOCKING.value),
        advisory_issues=_count_severity(issues, HumanReviewAuditBundleSeverity.ADVISORY.value),
        info_findings=_count_severity(issues, HumanReviewAuditBundleSeverity.INFO.value),
        queue_entry_count=queue_entry_count,
        decision_result_count=decision_result_count,
        consistency_cross_reference_count=consistency_cross_reference_count,
        unsafe_content_count=1 if upstream_unsafe > 0 else 0,
        forbidden_term_count=1 if upstream_forbidden > 0 else 0,
    )


def _build_safety_flags(data_quality: HumanReviewAuditBundleDataQuality) -> HumanReviewAuditBundleSafetyFlags:
    """Build safety flags from data quality and reason codes."""
    is_safe = not (data_quality.unsafe_content_count or data_quality.forbidden_term_count)
    return HumanReviewAuditBundleSafetyFlags(
        is_safe=is_safe,
        audit_only=True,
        no_executable_actions=True,
        no_trading_instructions=True,
        no_approval_claims=True,
        references_opaque=True,
        no_network=True,
        no_server=True,
    )


# ---------------------------------------------------------------------------
# Main engine entry point
# ---------------------------------------------------------------------------


def build_human_review_audit_bundle(
    input: HumanReviewAuditBundleInput,  # noqa: A002 — matches SPEC API name
) -> HumanReviewAuditBundleReport:
    """Build a deterministic, local, audit-only human review audit bundle.

    The engine accepts caller-provided in-memory reports from MVP-40, MVP-41,
    and MVP-42 and produces a normalized bundle. It does not open, follow,
    traverse, validate, fetch, or execute any reference string. It does not
    touch the filesystem or network.
    """
    generated_at = _resolve_generated_at(input.generated_at)
    project_version = input.project_version or HUMAN_REVIEW_AUDIT_BUNDLE_VERSION

    queue_report = input.queue_report
    decision_log_report = input.decision_log_report
    consistency_report = input.consistency_report
    config = input.config

    bundle_id = _build_bundle_id(
        queue_report.report_id,
        decision_log_report.report_id,
        consistency_report.report_id,
        project_version,
        generated_at,
    )
    report_id = _build_report_id(bundle_id, generated_at)

    all_empty = all(
        [
            _is_report_empty_or_not_applicable(queue_report, "queue"),
            _is_report_empty_or_not_applicable(decision_log_report, "decision_log"),
            _is_report_empty_or_not_applicable(consistency_report, "consistency"),
        ]
    )

    if all_empty and config.empty_input_is_not_applicable:
        sections = ()
        issues = ()
        data_quality = HumanReviewAuditBundleDataQuality()
        safety_flags = _build_safety_flags(data_quality)
        reason_codes = _build_reason_codes(
            HumanReviewAuditBundleState.NOT_APPLICABLE,
            ["not_applicable", "not_applicable", "not_applicable"],
            0,
            0,
            empty_input=True,
        )
        return HumanReviewAuditBundleReport(
            bundle_id=bundle_id,
            report_id=report_id,
            generated_at=generated_at,
            state=HumanReviewAuditBundleState.NOT_APPLICABLE,
            project_version=project_version,
            sections=sections,
            issues=issues,
            data_quality=data_quality,
            safety_flags=safety_flags,
            reason_codes=reason_codes,
            safety_notice=SAFETY_NOTICE,
            metadata=input.metadata,
            notes="All upstream inputs are empty or not applicable.",
        )

    sections: list[HumanReviewAuditBundleSection] = []
    section = _build_section("queue", queue_report, bundle_id, generated_at, config.include_derived_summary)
    if section is not None:
        sections.append(section)
    section = _build_section("decision_log", decision_log_report, bundle_id, generated_at, config.include_derived_summary)
    if section is not None:
        sections.append(section)
    section = _build_section("consistency", consistency_report, bundle_id, generated_at, config.include_derived_summary)
    if section is not None:
        sections.append(section)

    sections = sorted(sections, key=lambda s: s.section_kind)
    sections_tuple = tuple(sections)

    upstream_issues = _carry_forward_upstream_issues(
        queue_report,
        decision_log_report,
        consistency_report,
        bundle_id,
        config.include_upstream_issues,
    )
    state_issues = _carry_forward_upstream_state_issues(
        queue_report,
        decision_log_report,
        consistency_report,
        bundle_id,
        config.carry_forward_upstream_state,
    )
    issues = upstream_issues + state_issues

    upstream_states = [
        queue_report.state.value if queue_report.state else "not_applicable",
        decision_log_report.state.value if decision_log_report.state else "not_applicable",
        consistency_report.state.value if consistency_report.state else "not_applicable",
    ]

    state = _aggregate_state(upstream_states, issues, config.strict)

    data_quality = _build_data_quality(
        sections_tuple,
        issues,
        queue_report,
        decision_log_report,
        consistency_report,
        config.include_derived_summary,
    )
    safety_flags = _build_safety_flags(data_quality)
    reason_codes = _build_reason_codes(
        state,
        upstream_states,
        data_quality.unsafe_content_count,
        data_quality.forbidden_term_count,
        empty_input=all_empty,
    )

    notes = ""
    if state == HumanReviewAuditBundleState.BLOCKED:
        notes = "Bundle blocked due to upstream state or bundle-level blocking issue."
    elif state == HumanReviewAuditBundleState.DEGRADED:
        notes = "Bundle degraded due to upstream state or bundle-level advisory issue."
    elif state == HumanReviewAuditBundleState.NOT_APPLICABLE:
        notes = "Bundle not applicable."
    else:
        notes = "Bundle OK."

    return HumanReviewAuditBundleReport(
        bundle_id=bundle_id,
        report_id=report_id,
        generated_at=generated_at,
        state=state,
        project_version=project_version,
        sections=sections_tuple,
        issues=issues,
        data_quality=data_quality,
        safety_flags=safety_flags,
        reason_codes=reason_codes,
        safety_notice=SAFETY_NOTICE,
        metadata=input.metadata,
        notes=notes,
    )
