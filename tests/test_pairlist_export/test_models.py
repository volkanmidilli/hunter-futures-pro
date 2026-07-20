"""Focused tests for hunter.pairlist_export.models (SPEC-074)."""

from __future__ import annotations

import pytest

from hunter.pairlist_export.models import (
    PairlistExportSafetyFlags,
    PairlistRankingConfig,
)


def test_default_safety_flags_are_research_only() -> None:
    flags = PairlistExportSafetyFlags()
    assert flags.research_only is True
    assert flags.execution_approval_granted is False
    assert flags.production_approval_granted is False
    assert flags.live_trading_allowed is False
    assert flags.automatic_execution_allowed is False
    assert flags.human_approval_required is True


@pytest.mark.parametrize(
    "field",
    [
        "research_only",
        "execution_approval_granted",
        "production_approval_granted",
        "live_trading_allowed",
        "automatic_execution_allowed",
        "human_approval_required",
    ],
)
def test_safety_flags_reject_unsafe_construction(field: str) -> None:
    defaults = dict(
        research_only=True,
        execution_approval_granted=False,
        production_approval_granted=False,
        live_trading_allowed=False,
        automatic_execution_allowed=False,
        human_approval_required=True,
    )
    # Flip the flag under test to its unsafe value.
    defaults[field] = not defaults[field]
    with pytest.raises(ValueError):
        PairlistExportSafetyFlags(**defaults)


def test_default_ranking_config_matches_spec_074_defaults() -> None:
    config = PairlistRankingConfig()
    assert config.min_pairs == 5
    assert config.target_final_pairs == 20
    assert config.publish_candidates == 30
    assert config.max_pairs == 50
    assert config.refresh_period == 3600


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_pairs": 0},
        {"max_pairs": 4, "min_pairs": 5},
        {"publish_candidates": 4, "min_pairs": 5},
        {"publish_candidates": 60, "max_pairs": 50},
        {"refresh_period": 30},
    ],
)
def test_ranking_config_rejects_invalid_thresholds(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        PairlistRankingConfig(**kwargs)
