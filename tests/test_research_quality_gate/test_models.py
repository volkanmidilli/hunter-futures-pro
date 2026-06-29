"""Tests for hunter.research_quality_gate.models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from hunter.research_quality_gate.models import (
    FORBIDDEN_QUALITY_GATE_TERMS,
    QUALITY_GATE_BLOCKING_REASON_CODES,
    QUALITY_GATE_REASON_CODES,
    QUALITY_GATE_VERSION,
    QualityGateCheck,
    QualityGateCheckKind,
    QualityGateConfig,
    QualityGateDataQuality,
    QualityGateSafetyFlags,
    QualityGateState,
    QualityGateSummary,
    QualityGateVerdict,
    ResearchQualityGate,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestQualityGateState:
    def test_enum_values(self) -> None:
        assert QualityGateState.PASS.value == "pass"
        assert QualityGateState.WARN.value == "warn"
        assert QualityGateState.BLOCK.value == "block"
        assert QualityGateState.UNKNOWN.value == "unknown"


class TestQualityGateVerdict:
    def test_enum_values(self) -> None:
        assert QualityGateVerdict.PASS.value == "pass"
        assert QualityGateVerdict.WARN.value == "warn"
        assert QualityGateVerdict.BLOCK.value == "block"
        assert QualityGateVerdict.UNKNOWN.value == "unknown"


class TestQualityGateCheckKind:
    def test_enum_values(self) -> None:
        assert QualityGateCheckKind.OBSERVATION.value == "observation"
        assert QualityGateCheckKind.REVIEW.value == "review"
        assert QualityGateCheckKind.INDEX.value == "index"
        assert QualityGateCheckKind.SEARCH.value == "search"
        assert QualityGateCheckKind.BUNDLE.value == "bundle"
        assert QualityGateCheckKind.CHRONICLE.value == "chronicle"
        assert QualityGateCheckKind.DIGEST.value == "digest"
        assert QualityGateCheckKind.CROSS_CUTTING.value == "cross_cutting"

    def test_deterministic_order(self) -> None:
        values = [kind.value for kind in QualityGateCheckKind]
        assert values == [
            "observation",
            "review",
            "index",
            "search",
            "bundle",
            "chronicle",
            "digest",
            "cross_cutting",
        ]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_quality_gate_version(self) -> None:
        assert QUALITY_GATE_VERSION == "1.0"

    def test_reason_codes(self) -> None:
        assert len(QUALITY_GATE_REASON_CODES) == 29
        assert "EMPTY_GATE" in QUALITY_GATE_REASON_CODES
        assert "INVALID_CONFIG" in QUALITY_GATE_REASON_CODES
        assert "UNSAFE_CONFIG" in QUALITY_GATE_REASON_CODES
        assert "MISSING_OBSERVATION" in QUALITY_GATE_REASON_CODES
        assert "BLOCKED_DIGEST" in QUALITY_GATE_REASON_CODES
        assert "UNKNOWN_DIGEST" in QUALITY_GATE_REASON_CODES
        assert "UNSAFE_ARTIFACT_FLAGS" in QUALITY_GATE_REASON_CODES
        assert "UNRESOLVED_BLOCKERS" in QUALITY_GATE_REASON_CODES
        assert "STALE_ARTIFACT" in QUALITY_GATE_REASON_CODES
        assert "UNSAFE_GATE_CONTENT" in QUALITY_GATE_REASON_CODES
        assert "QUALITY_GATE_ERROR" in QUALITY_GATE_REASON_CODES

    def test_blocking_reason_codes(self) -> None:
        assert "EMPTY_GATE" not in QUALITY_GATE_BLOCKING_REASON_CODES
        assert "INVALID_CONFIG" in QUALITY_GATE_BLOCKING_REASON_CODES
        assert "UNSAFE_CONFIG" in QUALITY_GATE_BLOCKING_REASON_CODES
        assert "MISSING_OBSERVATION" in QUALITY_GATE_BLOCKING_REASON_CODES

    def test_forbidden_terms_superset_of_digest(self) -> None:
        digest_terms = {
            "api_key",
            "secret",
            "exchange_credentials",
            "executable_instructions",
            "private_key",
            "password",
            "token",
            "auth",
            "enter_long",
            "enter_short",
            "exit_long",
            "exit_short",
            "order",
            "position",
            "leverage",
            "margin",
            "liquidation",
            "live_trade",
            "real_order",
            "market_order",
            "limit_order",
            "position_size",
        }
        for term in digest_terms:
            assert term in FORBIDDEN_QUALITY_GATE_TERMS, term

    def test_forbidden_terms_quality_gate_specific(self) -> None:
        for term in ("deploy", "go_live", "production_ready", "execution_ready", "strategy_ready"):
            assert term in FORBIDDEN_QUALITY_GATE_TERMS


# ---------------------------------------------------------------------------
# QualityGateConfig
# ---------------------------------------------------------------------------


class TestQualityGateConfig:
    def test_default_construction(self) -> None:
        config = QualityGateConfig()
        assert config.version == "1.0"
        assert config.output_format == "both"
        assert config.dry_run is True
        assert config.live_trading_enabled is False
        assert config.block_on_unknown is True
        assert config.max_staleness_minutes == 60
        assert len(config.required_artifact_kinds) == 7

    def test_invalid_version_empty(self) -> None:
        with pytest.raises(ValueError, match="version must be a non-empty string"):
            QualityGateConfig(version="")

    def test_invalid_output_format(self) -> None:
        with pytest.raises(ValueError, match="output_format must be one of"):
            QualityGateConfig(output_format="xml")

    def test_invalid_dry_run_false(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True"):
            QualityGateConfig(dry_run=False)

    @pytest.mark.parametrize("attr", [
        "live_trading_enabled",
        "real_orders_enabled",
        "leverage_enabled",
        "shorting_enabled",
    ])
    def test_invalid_unsafe_flags_true(self, attr: str) -> None:
        with pytest.raises(ValueError, match=f"{attr} must be False"):
            QualityGateConfig(**{attr: True})

    def test_invalid_block_on_unknown_non_bool(self) -> None:
        with pytest.raises(ValueError, match="block_on_unknown must be a bool"):
            QualityGateConfig(block_on_unknown="yes")  # type: ignore[arg-type]

    def test_invalid_required_artifact_kinds(self) -> None:
        with pytest.raises(
            ValueError, match="required_artifact_kinds must contain QualityGateCheckKind"
        ):
            QualityGateConfig(required_artifact_kinds=("observation",))  # type: ignore[arg-type]

    def test_invalid_staleness_zero(self) -> None:
        with pytest.raises(ValueError, match="max_staleness_minutes must be a positive integer"):
            QualityGateConfig(max_staleness_minutes=0)

    def test_frozen(self) -> None:
        config = QualityGateConfig()
        with pytest.raises(FrozenInstanceError):
            config.dry_run = False


# ---------------------------------------------------------------------------
# QualityGateSafetyFlags
# ---------------------------------------------------------------------------


class TestQualityGateSafetyFlags:
    def test_default_construction(self) -> None:
        flags = QualityGateSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.quality_gate_output_is_human_audit_only is True
        assert flags.quality_gate_output_not_execution_readiness is True
        assert flags.quality_gate_output_not_strategy_readiness is True
        assert flags.quality_gate_feedback_into_execution is False
        assert flags.cross_layer_feedback_into_execution is False

    def test_unsafe_flag_true_raises(self) -> None:
        with pytest.raises(ValueError, match="unsafe quality gate safety flags are enabled"):
            QualityGateSafetyFlags(live_trading_enabled=True)
        with pytest.raises(ValueError, match="unsafe quality gate safety flags are enabled"):
            QualityGateSafetyFlags(quality_gate_feedback_into_execution=True)

    def test_dry_run_false_raises(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True"):
            QualityGateSafetyFlags(dry_run=False)

    def test_safe_output_flag_false_raises(self) -> None:
        with pytest.raises(ValueError, match="safe quality gate output flags must be True"):
            QualityGateSafetyFlags(quality_gate_output_is_human_audit_only=False)

    def test_cross_layer_feedback_into_execution_true_raises(self) -> None:
        with pytest.raises(ValueError, match="unsafe quality gate safety flags are enabled"):
            QualityGateSafetyFlags(cross_layer_feedback_into_execution=True)

    def test_frozen(self) -> None:
        flags = QualityGateSafetyFlags()
        with pytest.raises(FrozenInstanceError):
            flags.dry_run = False


# ---------------------------------------------------------------------------
# QualityGateCheck
# ---------------------------------------------------------------------------


class TestQualityGateCheck:
    def test_valid_construction(self) -> None:
        check = QualityGateCheck(
            check_kind=QualityGateCheckKind.OBSERVATION,
            state="PASS",
        )
        assert check.check_kind is QualityGateCheckKind.OBSERVATION
        assert check.state == "PASS"

    def test_state_normalized(self) -> None:
        check = QualityGateCheck(
            check_kind=QualityGateCheckKind.REVIEW,
            state="block",
        )
        assert check.state == "BLOCK"

    def test_invalid_check_kind(self) -> None:
        with pytest.raises(ValueError, match="check_kind must be a QualityGateCheckKind"):
            QualityGateCheck(check_kind="observation")  # type: ignore[arg-type]

    def test_invalid_state(self) -> None:
        with pytest.raises(ValueError, match="state must be one of"):
            QualityGateCheck(check_kind=QualityGateCheckKind.INDEX, state="CORRUPTED")

    def test_unsafe_notes_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_GATE_CONTENT"):
            QualityGateCheck(
                check_kind=QualityGateCheckKind.BUNDLE,
                notes="deploy now",
            )

    def test_file_reference_not_traversed(self) -> None:
        check = QualityGateCheck(
            check_kind=QualityGateCheckKind.OBSERVATION,
            metadata={"path": "/tmp/report.json"},
        )
        assert check.metadata["path"] == "/tmp/report.json"


# ---------------------------------------------------------------------------
# QualityGateSummary
# ---------------------------------------------------------------------------


class TestQualityGateSummary:
    def test_default_construction(self) -> None:
        summary = QualityGateSummary()
        assert summary.total_checks == 0
        assert summary.verdict == "UNKNOWN"

    def test_valid_construction(self) -> None:
        summary = QualityGateSummary(
            total_checks=4,
            pass_checks=2,
            warn_checks=1,
            block_checks=1,
            unknown_checks=0,
            verdict="WARN",
        )
        assert summary.pass_checks + summary.warn_checks + summary.block_checks == summary.total_checks

    def test_count_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match=r"pass_checks \+ warn_checks \+ block_checks \+ unknown_checks"):
            QualityGateSummary(
                total_checks=4,
                pass_checks=2,
                warn_checks=0,
                block_checks=0,
                unknown_checks=0,
            )

    def test_invalid_verdict(self) -> None:
        with pytest.raises(ValueError, match="verdict must be one of"):
            QualityGateSummary(verdict="CORRUPTED")

    def test_unsafe_handoff_notes_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_GATE_CONTENT"):
            QualityGateSummary(handoff_notes="go_live now")


# ---------------------------------------------------------------------------
# QualityGateDataQuality
# ---------------------------------------------------------------------------


class TestQualityGateDataQuality:
    def test_default_construction(self) -> None:
        dq = QualityGateDataQuality()
        assert dq.completeness_pct == 0.0
        assert dq.total_checks == 0

    def test_completeness_pct_range(self) -> None:
        with pytest.raises(ValueError, match="completeness_pct must be between"):
            QualityGateDataQuality(completeness_pct=101.0)

    def test_ready_pct_range(self) -> None:
        with pytest.raises(ValueError, match="ready_pct must be between"):
            QualityGateDataQuality(ready_pct=-1.0)

    def test_unsafe_reason_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_GATE_CONTENT"):
            QualityGateDataQuality(reason="contains secret")


# ---------------------------------------------------------------------------
# ResearchQualityGate
# ---------------------------------------------------------------------------


class TestResearchQualityGate:
    def test_valid_construction(self) -> None:
        now = datetime.now(timezone.utc)
        gate = ResearchQualityGate(
            gate_id="quality_gate:1.0:2025-01-01T00:00:00",
            generated_at=now,
            verdict=QualityGateVerdict.PASS,
        )
        assert gate.gate_id == "quality_gate:1.0:2025-01-01T00:00:00"
        assert gate.generated_at == now
        assert gate.verdict is QualityGateVerdict.PASS

    def test_default_verdict(self) -> None:
        now = datetime.now(timezone.utc)
        gate = ResearchQualityGate(gate_id="g1", generated_at=now)
        assert gate.verdict is QualityGateVerdict.UNKNOWN

    def test_invalid_gate_id_empty(self) -> None:
        with pytest.raises(ValueError, match="gate_id must be a non-empty string"):
            ResearchQualityGate(gate_id="", generated_at=datetime.now(timezone.utc))

    def test_invalid_generated_at_naive(self) -> None:
        with pytest.raises(ValueError, match="generated_at must be a timezone-aware datetime"):
            ResearchQualityGate(gate_id="g1", generated_at=datetime.now())

    def test_invalid_verdict_type(self) -> None:
        with pytest.raises(ValueError, match="verdict must be a QualityGateVerdict"):
            ResearchQualityGate(
                gate_id="g1",
                generated_at=datetime.now(timezone.utc),
                verdict="PASS",  # type: ignore[arg-type]
            )

    def test_blocked_factory(self) -> None:
        now = datetime.now(timezone.utc)
        gate = ResearchQualityGate.blocked("INVALID_CONFIG", generated_at=now)
        assert gate.verdict is QualityGateVerdict.BLOCK
        assert gate.reason_codes == ("INVALID_CONFIG",)
        assert "Quality gate blocked: INVALID_CONFIG" in gate.summary.handoff_notes
        assert "not trade approval" in gate.summary.handoff_notes
        assert gate.data_quality.blocked_count == 1

    def test_frozen(self) -> None:
        now = datetime.now(timezone.utc)
        gate = ResearchQualityGate(gate_id="g1", generated_at=now)
        with pytest.raises(FrozenInstanceError):
            gate.gate_id = "g2"

    def test_unsafe_handoff_notes_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_GATE_CONTENT"):
            ResearchQualityGate(
                gate_id="g1",
                generated_at=datetime.now(timezone.utc),
                handoff_notes="place order",
            )
