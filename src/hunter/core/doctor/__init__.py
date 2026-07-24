"""SPEC-077: Hunter Doctor, Versioning and Controlled Update Framework.

Public API for the read-only doctor/update framework.  All models are
frozen dataclasses; no global mutable state is used.
"""

from hunter.core.doctor.config import (
    ConfigFileIssue,
    ConfigKey,
    ConfigSource,
    ResolvedConfig,
    ResolvedValue,
    find_project_root,
    resolve_config,
    user_config_path,
)
from hunter.core.doctor.doctor import run_doctor
from hunter.core.doctor.errors import DoctorError
from hunter.core.doctor.gitutil import GitResult, GitRunner
from hunter.core.doctor.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    DoctorContext,
    DoctorReport,
    compute_exit_code,
)
from hunter.core.doctor.update import (
    MigrationLevel,
    TagCollection,
    UpdateCheckResult,
    UpdatePlan,
    UpdateSource,
    UpdateStatus,
    build_update_plan,
    collect_tags,
    resolve_target_version,
    run_update_check,
)
from hunter.core.doctor.version import (
    Version,
    current_version,
    filter_release_tags,
    is_ignored_tag,
    parse_version,
    parse_version_tag,
)

__all__ = [
    "CheckCategory",
    "CheckResult",
    "CheckStatus",
    "ConfigFileIssue",
    "ConfigKey",
    "ConfigSource",
    "DoctorContext",
    "DoctorError",
    "DoctorReport",
    "GitResult",
    "GitRunner",
    "MigrationLevel",
    "ResolvedConfig",
    "ResolvedValue",
    "TagCollection",
    "UpdateCheckResult",
    "UpdatePlan",
    "UpdateSource",
    "UpdateStatus",
    "Version",
    "build_update_plan",
    "collect_tags",
    "compute_exit_code",
    "current_version",
    "filter_release_tags",
    "find_project_root",
    "is_ignored_tag",
    "parse_version",
    "parse_version_tag",
    "resolve_config",
    "resolve_target_version",
    "run_doctor",
    "run_update_check",
    "user_config_path",
]
