"""Editable-install category check for SPEC-077."""

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path

from hunter.core.doctor.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    DoctorContext,
)

_DIST_NAME = "hunter-futures-pro"


def _direct_url_info(dist: importlib.metadata.Distribution) -> tuple[bool, str | None] | None:
    """Inspect PEP 610 ``direct_url.json``.

    Returns ``(editable, local_path)`` when determinable — ``local_path``
    is the ``file://`` URL path when present — or None when the metadata
    file is absent or unparseable.
    """
    try:
        raw = dist.read_text("direct_url.json")
    except (OSError, UnicodeDecodeError):
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    dir_info = data.get("dir_info")
    if not isinstance(dir_info, dict) or "editable" not in dir_info:
        return None
    local_path: str | None = None
    url = data.get("url")
    if isinstance(url, str) and url.startswith("file://"):
        local_path = url[len("file://"):]
    return (dir_info.get("editable") is True, local_path)


def _has_editable_finder(dist: importlib.metadata.Distribution) -> bool:
    """Detect setuptools editable finders (``__editable__*`` artifacts)."""
    try:
        files = dist.files
    except OSError:
        return False
    if not files:
        return False
    return any(str(entry).startswith("__editable__") for entry in files)


def check_editable_install(context: DoctorContext) -> tuple[CheckResult, ...]:
    """Verify hunter-futures-pro is installed editable from this repo."""
    check_id = "editable.install"
    category = CheckCategory.EDITABLE
    try:
        dist = importlib.metadata.distribution(_DIST_NAME)
    except importlib.metadata.PackageNotFoundError:
        return (
            CheckResult(
                check_id=check_id,
                category=category,
                status=CheckStatus.SKIPPED,
                summary=(
                    f"Distribution {_DIST_NAME!r} is not installed; "
                    "editable-install state cannot be determined."
                ),
                remediation="Install editable: pip install -e .",
            ),
        )

    info = _direct_url_info(dist)
    if info is None:
        # Setuptools finder/egg-info artifacts only exist for an editable
        # install from this checkout.
        if _has_editable_finder(dist):
            return (
                CheckResult(
                    check_id=check_id,
                    category=category,
                    status=CheckStatus.PASS,
                    summary=(
                        f"{_DIST_NAME} is installed editable "
                        f"(project root: {context.project_root})."
                    ),
                ),
            )
        return (
            CheckResult(
                check_id=check_id,
                category=category,
                status=CheckStatus.SKIPPED,
                summary="Editable-install metadata is unavailable.",
            ),
        )

    editable, local_path = info
    if editable:
        same_location = local_path is None or (
            Path(local_path).resolve() == context.project_root.resolve()
        )
        if same_location:
            return (
                CheckResult(
                    check_id=check_id,
                    category=category,
                    status=CheckStatus.PASS,
                    summary=(
                        f"{_DIST_NAME} is installed editable "
                        f"(project root: {context.project_root})."
                    ),
                ),
            )
        return (
            CheckResult(
                check_id=check_id,
                category=category,
                status=CheckStatus.WARNING,
                summary=(
                    f"{_DIST_NAME} is installed editable but from a different "
                    f"location: {local_path}"
                ),
                details=(f"project root: {context.project_root}",),
                remediation="Reinstall editable from this repository root: pip install -e .",
            ),
        )
    return (
        CheckResult(
            check_id=check_id,
            category=category,
            status=CheckStatus.WARNING,
            summary=f"{_DIST_NAME} is installed but not editable.",
            remediation="Reinstall editable from the repository root: pip install -e .",
        ),
    )
