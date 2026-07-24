"""Core models for the SPEC-077 doctor framework.

All models are frozen dataclasses; no global mutable state is used.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from hunter.core.doctor.config import ResolvedConfig
from hunter.core.doctor.gitutil import GitRunner


class CheckStatus(str, Enum):
    """Outcome status of a single doctor check."""

    PASS = "PASS"
    WARNING = "WARNING"
    BLOCKER = "BLOCKER"
    SKIPPED = "SKIPPED"


class CheckCategory(str, Enum):
    """The nine SPEC-077 check categories, in deterministic run order."""

    VENV = "Venv"
    EDITABLE = "Editable install"
    PACKAGES = "Package versions"
    GIT = "Git"
    SNAPSHOT = "Snapshot"
    FEATHER = "Feather"
    OUTCOME_STORE = "Outcome Store"
    SAFETY = "Safety"
    CONFIGURATION = "Configuration"


@dataclass(frozen=True)
class CheckResult:
    """Result of a single doctor check."""

    check_id: str
    category: CheckCategory
    status: CheckStatus
    summary: str
    details: tuple[str, ...] = field(default_factory=tuple)
    remediation: str | None = None


@dataclass(frozen=True)
class DoctorContext:
    """Immutable inputs shared by all checks."""

    project_root: Path
    config: ResolvedConfig
    git: GitRunner


@dataclass(frozen=True)
class DoctorReport:
    """Aggregate result of a full doctor run."""

    results: tuple[CheckResult, ...]
    exit_code: int
    config: ResolvedConfig
    research_only: bool = True
    human_approval_required: bool = True

    def count(self, status: CheckStatus) -> int:
        return sum(1 for result in self.results if result.status is status)


def compute_exit_code(results: tuple[CheckResult, ...] | list[CheckResult]) -> int:
    """Derive the exit code: 2 on any BLOCKER, 1 on any WARNING, else 0.

    SKIPPED never influences the exit code.
    """
    statuses = {result.status for result in results}
    if CheckStatus.BLOCKER in statuses:
        return 2
    if CheckStatus.WARNING in statuses:
        return 1
    return 0
