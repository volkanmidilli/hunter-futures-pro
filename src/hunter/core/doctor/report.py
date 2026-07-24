"""Deterministic report rendering for SPEC-077.

Text and JSON renderers for doctor reports, update checks, and update
plans.  JSON output uses stable key ordering and contains no timestamps,
so identical inputs produce byte-identical output.
"""

from __future__ import annotations

import json

from hunter.core.doctor.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    DoctorReport,
)
from hunter.core.doctor.update import UpdateCheckResult, UpdatePlan

_STATUS_ORDER: tuple[CheckStatus, ...] = (
    CheckStatus.PASS,
    CheckStatus.WARNING,
    CheckStatus.BLOCKER,
    CheckStatus.SKIPPED,
)


def _render_check_line(result: CheckResult) -> list[str]:
    lines = [f"  {result.status.value:<7} {result.check_id} — {result.summary}"]
    for detail in result.details:
        lines.append(f"          · {detail}")
    if result.remediation:
        lines.append(f"          → {result.remediation}")
    return lines


def render_doctor_text(report: DoctorReport, *, verbose: bool = False) -> str:
    """Render a doctor report grouped by category."""
    lines: list[str] = ["Hunter Doctor (research_only=True)", ""]
    for category in CheckCategory:
        results = [r for r in report.results if r.category is category]
        if not results:
            continue
        lines.append(f"[{category.value}]")
        for result in results:
            lines.extend(_render_check_line(result))
        lines.append("")
    counts = ", ".join(
        f"{report.count(status)} {status.value}" for status in _STATUS_ORDER
    )
    lines.append(f"Summary: {counts}")
    lines.append(f"Exit code: {report.exit_code}")
    if verbose:
        lines.append("")
        lines.append("Resolved configuration:")
        for resolved in report.config.all():
            lines.append(
                f"  {resolved.key.value:<20} = {resolved.value}  "
                f"(source: {resolved.source.value})"
            )
        if report.config.issues:
            lines.append("")
            lines.append("Configuration issues:")
            for issue in report.config.issues:
                lines.append(f"  {issue.path}: {issue.reason}")
    return "\n".join(lines)


def _check_result_payload(result: CheckResult) -> dict:
    return {
        "check_id": result.check_id,
        "category": result.category.value,
        "status": result.status.value,
        "summary": result.summary,
        "details": list(result.details),
        "remediation": result.remediation,
    }


def render_doctor_json(report: DoctorReport) -> str:
    """Render a doctor report as deterministic JSON."""
    payload = {
        "research_only": report.research_only,
        "human_approval_required": report.human_approval_required,
        "exit_code": report.exit_code,
        "results": [_check_result_payload(result) for result in report.results],
        "config": {
            resolved.key.value: {
                "value": str(resolved.value),
                "source": resolved.source.value,
            }
            for resolved in report.config.all()
        },
        "config_issues": [
            {"path": str(issue.path), "reason": issue.reason}
            for issue in report.config.issues
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def render_update_check_text(result: UpdateCheckResult) -> str:
    """Render an update check result as human-readable text."""
    lines = [
        "Hunter Update Check (research_only=True, read-only)",
        f"  current version:  {result.current_version}",
        f"  tag source:       {result.source.value}",
        f"  tags considered:  {result.tags_considered}",
    ]
    if result.latest_version is not None:
        lines.append(f"  latest version:   {result.latest_version}")
    lines.append(f"  status:           {result.status.value}")
    if result.reason:
        lines.append(f"  reason:           {result.reason}")
    if result.status.value == "UPDATE_AVAILABLE":
        lines.append("")
        lines.append(
            "Run `hunter update plan` for a deterministic, non-executing "
            "update plan. Updates remain a human-driven Git operation."
        )
    return "\n".join(lines)


def render_update_check_json(result: UpdateCheckResult) -> str:
    """Render an update check result as deterministic JSON."""
    payload = {
        "research_only": result.research_only,
        "human_approval_required": result.human_approval_required,
        "current_version": str(result.current_version),
        "latest_version": (
            str(result.latest_version) if result.latest_version is not None else None
        ),
        "status": result.status.value,
        "source": result.source.value,
        "tags_considered": result.tags_considered,
        "reason": result.reason,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def render_plan_text(plan: UpdatePlan) -> str:
    """Render an update plan as human-readable text (never executed)."""
    lines = [
        "Hunter Update Plan (research_only=True, human_approval_required=True)",
        "This plan is deterministic and non-executing; no command is run.",
        "",
        f"  current version:  {plan.current_version}",
        f"  target version:   {plan.target_version}",
        f"  migration level:  {plan.migration_level.value}",
        f"  breaking changes: {plan.breaking_changes}",
        f"  rollback tag:     {plan.rollback_tag}"
        + ("" if plan.rollback_tag_verified else " (unverified)"),
        "",
        "Migration requirements:",
    ]
    lines.extend(f"  - {item}" for item in plan.migration_requirements)
    lines.append("")
    if plan.recommended_commands:
        lines.append("Recommended commands (human-executed; never run by Hunter):")
        lines.extend(f"  {index}. {command}" for index, command in
                     enumerate(plan.recommended_commands, start=1))
    else:
        lines.append("No update commands recommended: already at the target version.")
    return "\n".join(lines)


def render_plan_json(plan: UpdatePlan) -> str:
    """Render an update plan as deterministic JSON."""
    payload = {
        "research_only": plan.research_only,
        "human_approval_required": plan.human_approval_required,
        "current_version": str(plan.current_version),
        "target_version": str(plan.target_version),
        "rollback_tag": plan.rollback_tag,
        "rollback_tag_verified": plan.rollback_tag_verified,
        "migration_level": plan.migration_level.value,
        "migration_requirements": list(plan.migration_requirements),
        "breaking_changes": plan.breaking_changes,
        "recommended_commands": list(plan.recommended_commands),
    }
    return json.dumps(payload, indent=2, sort_keys=True)
