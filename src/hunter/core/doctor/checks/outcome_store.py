"""Outcome Store category check for SPEC-077 (read-only)."""

from __future__ import annotations

import os

from hunter.core.doctor.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    DoctorContext,
)


def check_outcome_store_dir(context: DoctorContext) -> tuple[CheckResult, ...]:
    """Verify the resolved outcome store directory exists and is readable."""
    resolved = context.config.store_dir
    path = resolved.value
    if path.is_dir() and os.access(path, os.R_OK):
        return (
            CheckResult(
                check_id="outcome_store.directory",
                category=CheckCategory.OUTCOME_STORE,
                status=CheckStatus.PASS,
                summary=f"Outcome store directory is readable: {path}",
                details=(f"source: {resolved.source.value}",),
            ),
        )
    return (
        CheckResult(
            check_id="outcome_store.directory",
            category=CheckCategory.OUTCOME_STORE,
            status=CheckStatus.WARNING,
            summary=f"Outcome store directory is missing or unreadable: {path}",
            details=(f"source: {resolved.source.value}",),
            remediation=(
                "Create the directory or point store_dir at an existing "
                "location via hunter.yaml, HUNTER_STORE_DIR, or --store-dir."
            ),
        ),
    )
