"""Configuration category check for SPEC-077."""

from __future__ import annotations

from hunter.core.doctor.config import ConfigKey, ConfigSource
from hunter.core.doctor.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    DoctorContext,
)

#: Keys whose explicitly configured directories should be pairwise distinct.
_DISTINCT_KEYS: tuple[ConfigKey, ...] = (
    ConfigKey.SNAPSHOT_DIR,
    ConfigKey.DATA_DIR,
    ConfigKey.STORE_DIR,
)


def check_configuration(context: DoctorContext) -> tuple[CheckResult, ...]:
    """Verify config resolution succeeded cleanly.

    Reports recorded config-file issues (parse failures, unknown keys,
    invalid values) as warnings, and warns when explicitly configured
    snapshot/data/store directories are not pairwise distinct.
    """
    config = context.config
    check_id = "configuration.resolution"
    category = CheckCategory.CONFIGURATION

    details: list[str] = []
    for issue in config.issues:
        details.append(f"{issue.path}: {issue.reason}")

    explicit = [
        resolved
        for resolved in (config.get(key) for key in _DISTINCT_KEYS)
        if resolved.source is not ConfigSource.DEFAULT
    ]
    if len(explicit) == len(_DISTINCT_KEYS):
        paths = [resolved.value for resolved in explicit]
        if len(set(paths)) != len(paths):
            details.append(
                "Explicitly configured snapshot_dir, data_dir, and store_dir "
                "are not pairwise distinct."
            )

    if details:
        return (
            CheckResult(
                check_id=check_id,
                category=category,
                status=CheckStatus.WARNING,
                summary="Configuration resolution completed with issues.",
                details=tuple(details),
                remediation=(
                    "Fix the reported config file issues; supported keys are "
                    "snapshot_dir, data_dir, store_dir, pairlist_output_dir."
                ),
            ),
        )
    return (
        CheckResult(
            check_id=check_id,
            category=category,
            status=CheckStatus.PASS,
            summary=f"Resolved {len(config.all())} configuration keys cleanly.",
        ),
    )
