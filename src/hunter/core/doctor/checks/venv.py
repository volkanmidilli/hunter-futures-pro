"""Venv category check for SPEC-077."""

from __future__ import annotations

import sys

from hunter.core.doctor.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    DoctorContext,
)


def check_venv(context: DoctorContext) -> tuple[CheckResult, ...]:
    """Verify the process runs inside a virtual environment."""
    del context  # The venv state is a property of this process.
    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        return (
            CheckResult(
                check_id="venv.active",
                category=CheckCategory.VENV,
                status=CheckStatus.PASS,
                summary=f"Running inside a virtual environment: {sys.prefix}",
            ),
        )
    return (
        CheckResult(
            check_id="venv.active",
            category=CheckCategory.VENV,
            status=CheckStatus.WARNING,
            summary="Not running inside a virtual environment.",
            remediation=(
                "Create and activate a virtual environment, then reinstall: "
                "python -m venv .venv && source .venv/bin/activate && pip install -e ."
            ),
        ),
    )
