"""Feather category check for SPEC-077 (read-only).

Uses the SPEC-075 ranking-input discovery contract: non-recursive scan
for ``<BASE>_USDT_USDT-1h-futures.feather`` files.
"""

from __future__ import annotations

import os
import re

from hunter.core.doctor.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    DoctorContext,
)

#: SPEC-075 Feather filename contract (verified in
#: ``src/hunter/pairlist_export/feather_models.py``).
FEATHER_FILENAME_RE = re.compile(r"^[A-Z0-9]+_USDT_USDT-1h-futures\.feather$")


def check_feather_inputs(context: DoctorContext) -> tuple[CheckResult, ...]:
    """Verify the resolved data dir contains SPEC-075 Feather inputs."""
    resolved = context.config.data_dir
    path = resolved.value
    check_id = "feather.ranking_inputs"
    category = CheckCategory.FEATHER

    if not (path.is_dir() and os.access(path, os.R_OK)):
        return (
            CheckResult(
                check_id=check_id,
                category=category,
                status=CheckStatus.WARNING,
                summary=f"Feather data directory is missing or unreadable: {path}",
                details=(f"source: {resolved.source.value}",),
                remediation=(
                    "Create the directory or point data_dir at an existing "
                    "location via hunter.yaml, HUNTER_DATA_DIR, or --data-dir."
                ),
            ),
        )

    try:
        matches = sorted(
            entry.name
            for entry in os.scandir(path)
            if entry.is_file() and FEATHER_FILENAME_RE.match(entry.name)
        )
    except OSError as exc:
        return (
            CheckResult(
                check_id=check_id,
                category=category,
                status=CheckStatus.WARNING,
                summary=f"Feather data directory could not be scanned: {exc}",
                details=(f"source: {resolved.source.value}",),
            ),
        )

    if matches:
        return (
            CheckResult(
                check_id=check_id,
                category=category,
                status=CheckStatus.PASS,
                summary=(
                    f"Found {len(matches)} SPEC-075 Feather input file(s) in {path}."
                ),
                details=(f"source: {resolved.source.value}", matches[0]),
            ),
        )
    return (
        CheckResult(
            check_id=check_id,
            category=category,
            status=CheckStatus.WARNING,
            summary=f"No SPEC-075 Feather input files found in {path}.",
            details=(f"source: {resolved.source.value}",),
            remediation=(
                "Place <BASE>_USDT_USDT-1h-futures.feather files in the data "
                "directory or override data_dir."
            ),
        ),
    )
