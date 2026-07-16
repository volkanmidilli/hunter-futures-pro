"""Exceptions for the research market data package (MVP-63 / SPEC-064)."""

from __future__ import annotations


class ResearchMarketDataError(Exception):
    """Base exception for the research market data package."""

    def __init__(self, reason_code: str, message: str) -> None:
        self.reason_code = reason_code
        self.message = message
        super().__init__(f"{reason_code}: {message}")


class ResearchMarketDataConfigError(ResearchMarketDataError):
    """Raised when the research market data configuration is invalid."""


class ResearchMarketDataIOError(ResearchMarketDataError):
    """Raised when a read-only file operation fails."""


class ResearchMarketDataValidationError(ResearchMarketDataError):
    """Raised when a single input fails validation and cannot be excluded."""


class ResearchMarketDataBundleError(ResearchMarketDataError):
    """Raised when bundle assembly fails in a fail-closed manner."""


class ResearchMarketDataWriterError(ResearchMarketDataError):
    """Raised when an artifact write fails or is blocked."""
