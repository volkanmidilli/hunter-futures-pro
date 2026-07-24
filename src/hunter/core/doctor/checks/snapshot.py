"""Snapshot category check for SPEC-077 (read-only)."""

from __future__ import annotations

import os

from hunter.core.doctor.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    DoctorContext,
)


def check_snapshot_dir(context: DoctorContext) -> tuple[CheckResult, ...]:
    """Verify the resolved snapshot directory exists and is readable."""
    resolved = context.config.snapshot_dir
    path = resolved.value
    if path.is_dir() and os.access(path, os.R_OK):
        return (
            CheckResult(
                check_id="snapshot.directory",
                category=CheckCategory.SNAPSHOT,
                status=CheckStatus.PASS,
                summary=f"Snapshot directory is readable: {path}",
                details=(f"source: {resolved.source.value}",),
            ),
        )
    return (
        CheckResult(
            check_id="snapshot.directory",
            category=CheckCategory.SNAPSHOT,
            status=CheckStatus.WARNING,
            summary=f"Snapshot directory is missing or unreadable: {path}",
            details=(f"source: {resolved.source.value}",),
            remediation=(
                "Create the directory or point snapshot_dir at an existing "
                "location via hunter.yaml, HUNTER_SNAPSHOT_DIR, or --snapshot-dir."
            ),
        ),
    )
