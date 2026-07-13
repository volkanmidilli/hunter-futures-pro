"""Tests for the controlled_universe models module."""

import pytest

from hunter.controlled_universe.models import (
    CONTROLLED_UNIVERSE_REASON_CODES,
    CONTROLLED_UNIVERSE_VERSION,
    HUMAN_RESEARCH_ONLY,
    INVALID_PAIR,
    MISSING_EXECUTION_CONTEXT,
    MISSING_PORTFOLIO_CONTEXT,
    NO_ACTION_COMMANDS_EMITTED,
    NO_FILE_READ_IN_ENGINE,
    NO_NETWORK_CONNECTION,
    ControlledUniverseConfig,
    ControlledUniverseDataQuality,
    ControlledUniverseItem,
    ControlledUniverseReport,
    ControlledUniverseSafetyFlags,
    ControlledUniverseState,
    ControlledUniverseClassification,
)
from hunter.market_state.models import AllowedMode


def test_version_constant() -> None:
    assert CONTROLLED_UNIVERSE_VERSION == "0.51.0-dev"


def test_config_defaults() -> None:
    config = ControlledUniverseConfig()
    assert config.max_universe_pairs is None
    assert config.min_portfolio_score is None
    assert config.max_watchlist_pairs is None
    assert config.include_capped is True
    assert config.default_mode == AllowedMode.LONG_ONLY
    assert config.require_dry_run is True


def test_config_require_dry_run_must_be_true() -> None:
    with pytest.raises(ValueError, match="require_dry_run must be True"):
        ControlledUniverseConfig(require_dry_run=False)


def test_config_max_universe_pairs_validation() -> None:
    with pytest.raises(ValueError):
        ControlledUniverseConfig(max_universe_pairs=-1)
    with pytest.raises(ValueError):
        ControlledUniverseConfig(max_universe_pairs="ten")  # type: ignore[arg-type]


def test_config_min_portfolio_score_validation() -> None:
    with pytest.raises(ValueError):
        ControlledUniverseConfig(min_portfolio_score=-1.0)
    with pytest.raises(ValueError):
        ControlledUniverseConfig(min_portfolio_score=150.0)


def test_config_frozen() -> None:
    config = ControlledUniverseConfig()
    with pytest.raises(AttributeError):
        config.include_capped = False  # type: ignore[misc]


def test_safety_flags_defaults_are_safe() -> None:
    flags = ControlledUniverseSafetyFlags()
    assert flags.is_safe is True
    assert flags.safety_flags_ok is True


def test_safety_flags_not_safe_when_unsafe_content() -> None:
    flags = ControlledUniverseSafetyFlags(has_unsafe_content=True)
    assert flags.is_safe is False


def test_data_quality_defaults() -> None:
    dq = ControlledUniverseDataQuality()
    assert dq.total_inputs == 0
    assert dq.universe_count == 0
    assert dq.data_quality_score == 0.0


def test_data_quality_score_validation() -> None:
    with pytest.raises(ValueError):
        ControlledUniverseDataQuality(data_quality_score=-1.0)
    with pytest.raises(ValueError):
        ControlledUniverseDataQuality(data_quality_score=150.0)


def test_item_defaults() -> None:
    item = ControlledUniverseItem(
        pair="BTC/USDT",
        state=ControlledUniverseState.INCLUDED,
        classification=ControlledUniverseClassification.LONG_RESEARCH,
    )
    assert item.pair == "BTC/USDT"
    assert item.state == ControlledUniverseState.INCLUDED
    assert item.reason_codes == ()
    assert item.portfolio_score is None
    assert item.portfolio_state is None
    assert item.capped is False


def test_item_rejects_empty_pair() -> None:
    with pytest.raises(ValueError):
        ControlledUniverseItem(
            pair="",
            state=ControlledUniverseState.INCLUDED,
            classification=ControlledUniverseClassification.LONG_RESEARCH,
        )
    with pytest.raises(ValueError):
        ControlledUniverseItem(
            pair="   ",
            state=ControlledUniverseState.INCLUDED,
            classification=ControlledUniverseClassification.LONG_RESEARCH,
        )


def test_report_requires_reason_codes_supported() -> None:
    with pytest.raises(ValueError, match="unsupported reason code"):
        ControlledUniverseReport(
            version=CONTROLLED_UNIVERSE_VERSION,
            generated_at=__import__("datetime").datetime.utcnow(),
            config=ControlledUniverseConfig(),
            execution_state="DRY_RUN_ONLY",
            allowed_mode="LONG_ONLY",
            universe=(),
            watchlist=(),
            blocked=(),
            items=(),
            data_quality=ControlledUniverseDataQuality(),
            safety_flags=ControlledUniverseSafetyFlags(),
            reason_codes=("UNKNOWN_CODE",),
        )


def test_blocked_factory_returns_empty_universe() -> None:
    report = ControlledUniverseReport.fail_closed(reason_code=MISSING_EXECUTION_CONTEXT)
    assert report.universe == ()
    assert report.watchlist == ()
    assert report.blocked == ()
    assert report.items == ()
    assert MISSING_EXECUTION_CONTEXT in report.reason_codes
    assert HUMAN_RESEARCH_ONLY in report.reason_codes
    assert NO_ACTION_COMMANDS_EMITTED in report.reason_codes
    assert NO_FILE_READ_IN_ENGINE in report.reason_codes
    assert NO_NETWORK_CONNECTION in report.reason_codes


def test_all_reason_codes_are_present() -> None:
    expected = {
        INVALID_PAIR,
        "DUPLICATE_PAIR_DETECTED",
        MISSING_EXECUTION_CONTEXT,
        "EXECUTION_BLOCKED",
        "EXECUTION_UNKNOWN",
        "MACRO_MODE_NONE",
        "MACRO_MODE_MISMATCH",
        "TRANSITION_STATE",
        MISSING_PORTFOLIO_CONTEXT,
        "INVALID_PORTFOLIO_SUMMARY",
        "PORTFOLIO_STATE_EXCLUDED",
        "PORTFOLIO_STATE_BLOCKED",
        "PORTFOLIO_STATE_INSUFFICIENT_DATA",
        "PORTFOLIO_STATE_WATCHLIST",
        "LOW_PORTFOLIO_SCORE",
        "MAX_UNIVERSE_PAIRS_EXCEEDED",
        "PASSED_UNIVERSE_FILTER",
        HUMAN_RESEARCH_ONLY,
        NO_ACTION_COMMANDS_EMITTED,
        NO_FILE_READ_IN_ENGINE,
        NO_NETWORK_CONNECTION,
    }
    assert expected.issubset(CONTROLLED_UNIVERSE_REASON_CODES)
