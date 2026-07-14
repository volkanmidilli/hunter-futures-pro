"""Tests for research decision gate models."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from hunter.research_decision_gate.models import (
    ALLOW_WITH_REVIEW,
    BLOCKING_REASON_CODES,
    DECISION_GO,
    DECISION_NEEDS_REVIEW,
    DECISION_NO_GO,
    DECISION_REASON_CODES,
    IGNORE,
    REQUIRE,
    RESEARCH_DECISION_GATE_VERSION,
    REVIEW_REASON_CODES,
    DecisionSourceSummary,
    ResearchDecisionGateConfig,
    ResearchDecisionGateError,
    ResearchDecisionGateReport,
)


def test_version_constant() -> None:
    assert RESEARCH_DECISION_GATE_VERSION == "0.59.0-dev"


def test_decision_constants() -> None:
    assert DECISION_GO == "DECISION_GO"
    assert DECISION_NO_GO == "DECISION_NO_GO"
    assert DECISION_NEEDS_REVIEW == "DECISION_NEEDS_REVIEW"
    assert DECISION_GO in DECISION_REASON_CODES
    assert DECISION_NO_GO in DECISION_REASON_CODES
    assert DECISION_NEEDS_REVIEW in DECISION_REASON_CODES


def test_config_defaults() -> None:
    config = ResearchDecisionGateConfig.default()
    assert config.strategy_contract_policy == ALLOW_WITH_REVIEW
    assert config.max_universe_age_seconds == 300
    assert config.max_risk_context_age_seconds == 300
    assert config.allowed_future_skew_seconds == 60
    assert config.output_dir == Path("data/research_decision_gate")
    assert config.report_output_dir == Path("reports/research_decision_gate")
    assert config.json_filename == "latest_decision.json"
    assert config.markdown_filename == "latest_decision.md"
    assert config.metadata == MappingProxyType({})


def test_config_custom_values() -> None:
    config = ResearchDecisionGateConfig(
        strategy_contract_policy=REQUIRE,
        max_universe_age_seconds=120,
        max_risk_context_age_seconds=60,
        allowed_future_skew_seconds=30,
        output_dir=Path("custom/data"),
        report_output_dir=Path("custom/reports"),
        json_filename="decision.json",
        markdown_filename="decision.md",
        metadata={"key": "value"},
    )
    assert config.strategy_contract_policy == REQUIRE
    assert config.max_universe_age_seconds == 120
    assert config.max_risk_context_age_seconds == 60
    assert config.allowed_future_skew_seconds == 30
    assert config.output_dir == Path("custom/data")
    assert config.report_output_dir == Path("custom/reports")
    assert config.json_filename == "decision.json"
    assert config.markdown_filename == "decision.md"
    assert dict(config.metadata) == {"key": "value"}


def test_config_rejects_invalid_policy() -> None:
    with pytest.raises(ValueError, match="strategy_contract_policy"):
        ResearchDecisionGateConfig(strategy_contract_policy="INVALID")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "name,value",
    [
        ("max_universe_age_seconds", -1),
        ("max_risk_context_age_seconds", -1),
        ("allowed_future_skew_seconds", -1),
    ],
)
def test_config_rejects_negative_thresholds(name: str, value: int) -> None:
    with pytest.raises(ValueError, match=name):
        ResearchDecisionGateConfig(**{name: value})


def test_config_rejects_empty_filenames() -> None:
    with pytest.raises(ValueError, match="json_filename"):
        ResearchDecisionGateConfig(json_filename="")
    with pytest.raises(ValueError, match="markdown_filename"):
        ResearchDecisionGateConfig(markdown_filename="")


def test_config_coerces_string_paths() -> None:
    config = ResearchDecisionGateConfig(
        output_dir="data/gate",
        report_output_dir="reports/gate",
    )
    assert isinstance(config.output_dir, Path)
    assert isinstance(config.report_output_dir, Path)
    assert config.output_dir == Path("data/gate")
    assert config.report_output_dir == Path("reports/gate")


def test_config_metadata_is_immutable() -> None:
    config = ResearchDecisionGateConfig(metadata={"a": 1})
    assert isinstance(config.metadata, MappingProxyType)


def test_decision_source_summary_defaults() -> None:
    summary = DecisionSourceSummary(
        source_name="risk_context",
        present=True,
        accepted=True,
        fresh=True,
        fingerprint="fp-1",
        reason_codes=(),
    )
    assert summary.source_name == "risk_context"
    assert summary.present is True
    assert summary.accepted is True
    assert summary.fresh is True
    assert summary.fingerprint == "fp-1"
    assert summary.reason_codes == ()


def test_decision_source_summary_rejects_invalid_bools() -> None:
    with pytest.raises(ValueError, match="present"):
        DecisionSourceSummary(
            source_name="risk_context",
            present="yes",  # type: ignore[arg-type]
            accepted=True,
            fresh=True,
            fingerprint="fp",
            reason_codes=(),
        )


def test_decision_source_summary_allows_none_fingerprint() -> None:
    summary = DecisionSourceSummary(
        source_name="risk_context",
        present=False,
        accepted=False,
        fresh=False,
        fingerprint=None,
        reason_codes=("MISSING_RISK_CONTEXT",),
    )
    assert summary.fingerprint is None


def _make_summary(
    *,
    source_name: str = "risk_context",
    present: bool = True,
    accepted: bool = True,
    fresh: bool = True,
    fingerprint: str = "fp",
    reason_codes: tuple[str, ...] = (),
) -> DecisionSourceSummary:
    return DecisionSourceSummary(
        source_name=source_name,
        present=present,
        accepted=accepted,
        fresh=fresh,
        fingerprint=fingerprint,
        reason_codes=reason_codes,
    )


def test_report_defaults() -> None:
    evaluated_at = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    summary = _make_summary()
    report = ResearchDecisionGateReport(
        version=RESEARCH_DECISION_GATE_VERSION,
        decision="GO",
        decision_fingerprint="abc123",
        evaluated_at=evaluated_at,
        risk_context_summary=summary,
        universe_summary=summary,
        strategy_contract_summary=summary,
        blocking_reason_codes=(),
        review_reason_codes=(),
        safety_flags={"research_only": True},
        research_only=True,
        human_approval_required=True,
    )
    assert report.version == RESEARCH_DECISION_GATE_VERSION
    assert report.decision == "GO"
    assert report.decision_fingerprint == "abc123"
    assert report.evaluated_at == evaluated_at
    assert report.research_only is True
    assert report.human_approval_required is True


def test_report_rejects_unsafe_flags() -> None:
    evaluated_at = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    summary = _make_summary()
    with pytest.raises(ValueError, match="research_only and human_approval_required"):
        ResearchDecisionGateReport(
            version=RESEARCH_DECISION_GATE_VERSION,
            decision="GO",
            decision_fingerprint="abc123",
            evaluated_at=evaluated_at,
            risk_context_summary=summary,
            universe_summary=summary,
            strategy_contract_summary=summary,
            blocking_reason_codes=(),
            review_reason_codes=(),
            safety_flags={"research_only": True},
            research_only=False,
            human_approval_required=True,
        )


def test_report_rejects_naive_datetime() -> None:
    summary = _make_summary()
    with pytest.raises(ValueError, match="evaluated_at"):
        ResearchDecisionGateReport(
            version=RESEARCH_DECISION_GATE_VERSION,
            decision="GO",
            decision_fingerprint="abc123",
            evaluated_at=datetime(2026, 7, 14, 12, 0, 0),
            risk_context_summary=summary,
            universe_summary=summary,
            strategy_contract_summary=summary,
            blocking_reason_codes=(),
            review_reason_codes=(),
            safety_flags={"research_only": True},
            research_only=True,
            human_approval_required=True,
        )


def test_report_rejects_invalid_decision() -> None:
    evaluated_at = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    summary = _make_summary()
    with pytest.raises(ValueError, match="decision"):
        ResearchDecisionGateReport(
            version=RESEARCH_DECISION_GATE_VERSION,
            decision="MAYBE",  # type: ignore[arg-type]
            decision_fingerprint="abc123",
            evaluated_at=evaluated_at,
            risk_context_summary=summary,
            universe_summary=summary,
            strategy_contract_summary=summary,
            blocking_reason_codes=(),
            review_reason_codes=(),
            safety_flags={"research_only": True},
            research_only=True,
            human_approval_required=True,
        )


def test_report_metadata_is_immutable() -> None:
    evaluated_at = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    summary = _make_summary()
    report = ResearchDecisionGateReport(
        version=RESEARCH_DECISION_GATE_VERSION,
        decision="GO",
        decision_fingerprint="abc123",
        evaluated_at=evaluated_at,
        risk_context_summary=summary,
        universe_summary=summary,
        strategy_contract_summary=summary,
        blocking_reason_codes=(),
        review_reason_codes=(),
        safety_flags={"research_only": True},
        research_only=True,
        human_approval_required=True,
        metadata={"note": "test"},
    )
    assert isinstance(report.metadata, MappingProxyType)
