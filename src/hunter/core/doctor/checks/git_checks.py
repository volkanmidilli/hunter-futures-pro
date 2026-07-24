"""Git category check for SPEC-077.

Strictly read-only: uses only ``rev-parse``, ``branch --show-current``,
and ``status --porcelain`` via the allowlisted GitRunner.
"""

from __future__ import annotations

from hunter.core.doctor.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    DoctorContext,
)


def check_git_repository(context: DoctorContext) -> tuple[CheckResult, ...]:
    """Verify git availability, worktree membership, branch, and cleanliness."""
    check_id = "git.repository"
    category = CheckCategory.GIT

    inside = context.git.run("rev-parse", "--is-inside-work-tree")
    if inside.error is not None:
        if "not found" in inside.error:
            return (
                CheckResult(
                    check_id=check_id,
                    category=category,
                    status=CheckStatus.SKIPPED,
                    summary="git binary not found; Git checks skipped.",
                ),
            )
        return (
            CheckResult(
                check_id=check_id,
                category=category,
                status=CheckStatus.SKIPPED,
                summary=f"Git check could not run: {inside.error}",
            ),
        )
    if not inside.ok or inside.stdout.strip() != "true":
        return (
            CheckResult(
                check_id=check_id,
                category=category,
                status=CheckStatus.BLOCKER,
                summary="Project root is not inside a git work tree.",
                remediation="Run Hunter from a clone of the repository.",
            ),
        )

    branch = context.git.run("branch", "--show-current")
    status = context.git.run("status", "--porcelain")
    branch_name = branch.stdout.strip() if branch.ok else ""
    dirty_entries = [line for line in status.stdout.splitlines() if line.strip()]
    detached = not branch_name
    dirty = bool(dirty_entries)

    if not detached and not dirty:
        return (
            CheckResult(
                check_id=check_id,
                category=category,
                status=CheckStatus.PASS,
                summary=f"On branch {branch_name!r} with a clean worktree.",
            ),
        )

    details: list[str] = []
    if detached:
        details.append("HEAD is detached (no current branch).")
    if dirty:
        details.append(f"Worktree has {len(dirty_entries)} uncommitted entry(ies).")
    return (
        CheckResult(
            check_id=check_id,
            category=category,
            status=CheckStatus.WARNING,
            summary="Git worktree requires attention.",
            details=tuple(details),
            remediation=(
                "Commit or stash local changes and check out a branch before "
                "running research workflows."
            ),
        ),
    )
