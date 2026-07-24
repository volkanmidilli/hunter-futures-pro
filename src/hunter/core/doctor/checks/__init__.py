"""SPEC-077 doctor checks, in deterministic category order."""

from hunter.core.doctor.checks.configuration import check_configuration
from hunter.core.doctor.checks.editable import check_editable_install
from hunter.core.doctor.checks.feather import check_feather_inputs
from hunter.core.doctor.checks.git_checks import check_git_repository
from hunter.core.doctor.checks.outcome_store import check_outcome_store_dir
from hunter.core.doctor.checks.packages import check_package_versions
from hunter.core.doctor.checks.safety import check_safety
from hunter.core.doctor.checks.snapshot import check_snapshot_dir
from hunter.core.doctor.checks.venv import check_venv

__all__ = [
    "check_configuration",
    "check_editable_install",
    "check_feather_inputs",
    "check_git_repository",
    "check_outcome_store_dir",
    "check_package_versions",
    "check_safety",
    "check_snapshot_dir",
    "check_venv",
]
