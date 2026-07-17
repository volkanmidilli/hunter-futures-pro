"""Error classes for the research campaign compiler and orchestrator (MVP-69/MVP-70 / SPEC-070)."""

from __future__ import annotations

from hunter.research_campaign.models import RESEARCH_CAMPAIGN_REASON_CODES


class ResearchCampaignError(Exception):
    """Base error for research campaign operations."""

    def __init__(self, message: str, reason_code: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.reason_code = reason_code
        if reason_code and reason_code not in RESEARCH_CAMPAIGN_REASON_CODES:
            raise ValueError(f"Invalid reason_code: {reason_code}")

    def __str__(self) -> str:  # pragma: no cover
        if self.reason_code:
            return f"[{self.reason_code}] {self.message}"
        return self.message


class ResearchCampaignDefinitionError(ResearchCampaignError):
    """Campaign definition is invalid."""


class ResearchCampaignCompilationError(ResearchCampaignError):
    """Campaign matrix compilation failed."""


class ResearchCampaignFilterError(ResearchCampaignError):
    """Filter rule is invalid or contradictory."""


class ResearchCampaignRegistrationError(ResearchCampaignError):
    """Pre-registration failed or registration drift detected."""


class ResearchCampaignResumeError(ResearchCampaignError):
    """Resume manifest is invalid or evidence is stale."""


class ResearchCampaignRunnerError(ResearchCampaignError):
    """Sequential batch runner encountered a fatal error."""


class ResearchCampaignWriterError(ResearchCampaignError):
    """Campaign writer failed."""


class ResearchCampaignSafetyError(ResearchCampaignError):
    """Mandatory safety invariant was violated."""


class ResearchCampaignExecutionError(ResearchCampaignError):
    """Experiment execution failed in a non-recoverable way."""
