"""Doctor engine for SPEC-077.

Runs all checks in deterministic category order and aggregates them
into a :class:`DoctorReport`.  The engine is strictly read-only.
"""

from __future__ import annotations

from typing import Callable

from hunter.core.doctor.checks import (
    check_configuration,
    check_editable_install,
    check_feather_inputs,
    check_git_repository,
    check_outcome_store_dir,
    check_package_versions,
    check_safety,
    check_snapshot_dir,
    check_venv,
)
from hunter.core.doctor.models import (
    CheckResult,
    DoctorContext,
    DoctorReport,
    compute_exit_code,
)

#: Check functions in deterministic SPEC-077 category order.
CHECK_FUNCTIONS: tuple[Callable[[DoctorContext], tuple[CheckResult, ...]], ...] = (
    check_venv,
    check_editable_install,
    check_package_versions,
    check_git_repository,
    check_snapshot_dir,
    check_feather_inputs,
    check_outcome_store_dir,
    check_safety,
    check_configuration,
)


def run_doctor(context: DoctorContext) -> DoctorReport:
    """Run every check and aggregate the results into a report."""
    results: list[CheckResult] = []
    for check in CHECK_FUNCTIONS:
        results.extend(check(context))
    ordered = tuple(results)
    return DoctorReport(
        results=ordered,
        exit_code=compute_exit_code(ordered),
        config=context.config,
    )
