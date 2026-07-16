"""Input validation for the research universe builder (MVP-64 / SPEC-065)."""

from __future__ import annotations

from hunter.research_market_data.models import ResearchMarketDataBundle
from hunter.research_universe.errors import ResearchUniverseValidationError
from hunter.research_universe.models import (
    INVALID_BUNDLE,
    INVALID_SELECTION_WINDOW,
    MISSING_BUNDLE,
    ResearchUniverseConfig,
)


def validate_config(config: ResearchUniverseConfig | None) -> None:
    """Validate a research universe config."""
    if config is None:
        raise ResearchUniverseValidationError("config is required")
    if not isinstance(config, ResearchUniverseConfig):
        raise ResearchUniverseValidationError(f"config must be ResearchUniverseConfig, got {type(config)}")
    if config.min_coverage_ratio < 0.0 or config.min_coverage_ratio > 1.0:
        raise ResearchUniverseValidationError(
            f"min_coverage_ratio must be in [0, 1], got {config.min_coverage_ratio}"
        )
    if config.max_baseline_pairs < 1:
        raise ResearchUniverseValidationError(
            f"max_baseline_pairs must be >= 1, got {config.max_baseline_pairs}"
        )
    if config.selection_window.start >= config.selection_window.end:
        raise ResearchUniverseValidationError(INVALID_SELECTION_WINDOW)


def validate_bundle(bundle: ResearchMarketDataBundle | None) -> None:
    """Validate a research market data bundle."""
    if bundle is None:
        raise ResearchUniverseValidationError(MISSING_BUNDLE)
    if not isinstance(bundle, ResearchMarketDataBundle):
        raise ResearchUniverseValidationError(INVALID_BUNDLE)
    if not bundle.candidates:
        raise ResearchUniverseValidationError(f"{INVALID_BUNDLE}: bundle has no candidates")


def validate_inputs(
    config: ResearchUniverseConfig | None,
    bundle: ResearchMarketDataBundle | None,
) -> None:
    """Validate both config and bundle."""
    validate_config(config)
    validate_bundle(bundle)
