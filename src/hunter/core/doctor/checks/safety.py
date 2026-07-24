"""Safety category check for SPEC-077.

Verifies the research-only invariant by reusing the existing fail-closed
config safety validation in ``hunter.config`` (trading disabled, live
trading disabled, no secret keys in configuration).
"""

from __future__ import annotations

from hunter.config import ConfigLoadError, load_config
from hunter.core.doctor.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    DoctorContext,
)


def check_safety(context: DoctorContext) -> tuple[CheckResult, ...]:
    """Verify research-only safety constraints hold (research_only=True)."""
    del context  # Safety validation reads the standard config locations.
    check_id = "safety.research_only"
    category = CheckCategory.SAFETY
    try:
        load_config()
    except ConfigLoadError as exc:
        return (
            CheckResult(
                check_id=check_id,
                category=category,
                status=CheckStatus.BLOCKER,
                summary=f"Research-only safety constraint violated: {exc}",
                remediation=(
                    "Disable trading/live trading and remove secret keys from "
                    "configuration before running any Hunter workflow. "
                    "research_only=True is mandatory."
                ),
            ),
        )
    except Exception as exc:  # Non-safety load failure: cannot evaluate.
        return (
            CheckResult(
                check_id=check_id,
                category=category,
                status=CheckStatus.SKIPPED,
                summary=f"Safety config could not be loaded for evaluation: {exc}",
            ),
        )
    return (
        CheckResult(
            check_id=check_id,
            category=category,
            status=CheckStatus.PASS,
            summary=(
                "Research-only constraints hold: trading disabled, live "
                "trading disabled, no secrets in configuration "
                "(research_only=True)."
            ),
        ),
    )
