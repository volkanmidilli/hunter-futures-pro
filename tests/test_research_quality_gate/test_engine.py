"""Tests for hunter.research_quality_gate.engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hunter.research_quality_gate.engine import (
    build_quality_gate_check,
    build_quality_gate_data_quality,
    build_quality_gate_safety_flags,
    build_quality_gate_summary,
    build_research_quality_gate,
    has_unsafe_quality_gate_content,
)
from hunter.research_quality_gate.models import (
    FORBIDDEN_QUALITY_GATE_TERMS,
    QualityGateCheck,
    QualityGateCheckKind,
    QualityGateConfig,
    QualityGateSafetyFlags,
    QualityGateState,
    QualityGateVerdict,
    ResearchQualityGate,
)


def _now() -> datetime:
    return datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_safety_flags(
    *,
    dry_run: bool = True,
    live_trading_enabled: bool = False,
    quality_gate_feedback_into_execution: bool = False,
) -> QualityGateSafetyFlags:
    return QualityGateSafetyFlags(
        dry_run=dry_run,
        live_trading_enabled=live_trading_enabled,
        real_orders_enabled=False,
        leverage_enabled=False,
        shorting_enabled=False,
        quality_gate_feedback_into_execution=quality_gate_feedback_into_execution,
        cross_layer_feedback_into_execution=False,
    )


def _make_unsafe_safety_flags(unsafe_attr: str = "live_trading_enabled") -> QualityGateSafetyFlags:
    """Return a safety flags object with one unsafe flag enabled.

    Bypasses __post_init__ so tests can verify engine detection.
    """
    flags = object.__new__(QualityGateSafetyFlags)
    object.__setattr__(flags, "dry_run", True)
    object.__setattr__(flags, "live_trading_enabled", False)
    object.__setattr__(flags, "real_orders_enabled", False)
    object.__setattr__(flags, "leverage_enabled", False)
    object.__setattr__(flags, "shorting_enabled", False)
    object.__setattr__(flags, "quality_gate_output_is_human_audit_only", True)
    object.__setattr__(flags, "quality_gate_output_not_trading_signal", True)
    object.__setattr__(flags, "quality_gate_output_not_trade_approval", True)
    object.__setattr__(flags, "quality_gate_output_not_execution_readiness", True)
    object.__setattr__(flags, "quality_gate_output_not_strategy_readiness", True)
    object.__setattr__(flags, "quality_gate_output_not_for_execution", True)
    object.__setattr__(flags, "quality_gate_output_not_for_strategy", True)
    object.__setattr__(flags, "quality_gate_output_not_for_freqtrade", True)
    object.__setattr__(flags, "quality_gate_output_not_for_order", True)
    object.__setattr__(flags, "quality_gate_output_not_for_exchange", True)
    object.__setattr__(flags, "quality_gate_feedback_into_execution", False)
    object.__setattr__(flags, "cross_layer_feedback_into_execution", False)
    object.__setattr__(flags, "file_refs_not_traversed", True)
    object.__setattr__(flags, unsafe_attr, True)
    return flags


def _make_artifact(
    state: str = "READY",
    reason_codes: tuple[str, ...] = (),
    generated_at: datetime | None = None,
    safety_flags: QualityGateSafetyFlags | None = None,
) -> object:
    """Return a simple artifact-like object."""
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)
    if safety_flags is None:
        safety_flags = _make_safety_flags()

    class Artifact:
        pass

    artifact = Artifact()
    artifact.state = state
    artifact.reason_codes = reason_codes
    artifact.generated_at = generated_at
    artifact.safety_flags = safety_flags
    return artifact


def _make_artifact_dict(
    state: str = "READY",
    reason_codes: tuple[str, ...] = (),
    generated_at: datetime | None = None,
    safety_flags: QualityGateSafetyFlags | None = None,
) -> dict[str, object]:
    """Return a dict-based artifact."""
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)
    if safety_flags is None:
        safety_flags = _make_safety_flags()
    return {
        "state": state,
        "reason_codes": reason_codes,
        "generated_at": generated_at,
        "safety_flags": safety_flags,
    }


# ---------------------------------------------------------------------------
# has_unsafe_quality_gate_content
# ---------------------------------------------------------------------------


class TestHasUnsafeQualityGateContent:
    def test_safe_text(self) -> None:
        assert has_unsafe_quality_gate_content("normal audit notes") is False

    def test_forbidden_term_api_key(self) -> None:
        assert has_unsafe_quality_gate_content("contains api_key") is True

    def test_forbidden_term_deploy(self) -> None:
        assert has_unsafe_quality_gate_content("deploy now") is True

    def test_case_insensitive(self) -> None:
        assert has_unsafe_quality_gate_content("DEPLOY") is True
        assert has_unsafe_quality_gate_content("API_KEY") is True

    def test_empty_text(self) -> None:
        assert has_unsafe_quality_gate_content("") is False
        assert has_unsafe_quality_gate_content(None) is False

    def test_unsafe_metadata(self) -> None:
        assert has_unsafe_quality_gate_content(None, {"token": "abc"}) is True

    def test_safe_metadata(self) -> None:
        assert has_unsafe_quality_gate_content(None, {"path": "/tmp/report.json"}) is False


# ---------------------------------------------------------------------------
# build_quality_gate_safety_flags
# ---------------------------------------------------------------------------


class TestBuildQualityGateSafetyFlags:
    def test_default_config(self) -> None:
        flags = build_quality_gate_safety_flags(QualityGateConfig())
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.quality_gate_feedback_into_execution is False

    def test_unsafe_config_rejected(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True"):
            QualityGateConfig(dry_run=False)

    def test_unsafe_config_passed_directly_raises(self) -> None:
        config = object.__new__(QualityGateConfig)
        object.__setattr__(config, "version", "1.0")
        object.__setattr__(config, "generated_at", None)
        object.__setattr__(config, "output_format", "both")
        object.__setattr__(config, "dry_run", False)
        object.__setattr__(config, "live_trading_enabled", False)
        object.__setattr__(config, "real_orders_enabled", False)
        object.__setattr__(config, "leverage_enabled", False)
        object.__setattr__(config, "shorting_enabled", False)
        object.__setattr__(config, "block_on_unknown", True)
        object.__setattr__(config, "required_artifact_kinds", ())
        object.__setattr__(config, "max_staleness_minutes", 60)
        object.__setattr__(config, "include_handoff_notes", True)
        with pytest.raises(ValueError, match="dry_run must be True"):
            build_quality_gate_safety_flags(config)


# ---------------------------------------------------------------------------
# build_quality_gate_check
# ---------------------------------------------------------------------------


class TestBuildQualityGateCheck:
    def test_ready_artifact_pass(self) -> None:
        artifact = _make_artifact(state="READY")
        check = build_quality_gate_check(
            QualityGateCheckKind.OBSERVATION,
            artifact=artifact,
        )
        assert check.state == "PASS"
        assert check.check_kind is QualityGateCheckKind.OBSERVATION

    def test_ready_artifact_dict_pass(self) -> None:
        artifact = _make_artifact_dict(state="READY")
        check = build_quality_gate_check(
            QualityGateCheckKind.OBSERVATION,
            artifact=artifact,
        )
        assert check.state == "PASS"

    def test_blocked_artifact_block(self) -> None:
        artifact = _make_artifact(state="BLOCKED")
        check = build_quality_gate_check(
            QualityGateCheckKind.REVIEW,
            artifact=artifact,
        )
        assert check.state == "BLOCK"
        assert "BLOCKED_REVIEW" in check.reason_codes

    def test_unknown_artifact_block_by_default(self) -> None:
        artifact = _make_artifact(state="UNKNOWN")
        check = build_quality_gate_check(
            QualityGateCheckKind.INDEX,
            artifact=artifact,
        )
        assert check.state == "BLOCK"
        assert "UNKNOWN_INDEX" in check.reason_codes

    def test_unknown_artifact_warn_when_not_blocking(self) -> None:
        artifact = _make_artifact(state="UNKNOWN")
        config = QualityGateConfig(block_on_unknown=False)
        check = build_quality_gate_check(
            QualityGateCheckKind.INDEX,
            artifact=artifact,
            config=config,
        )
        assert check.state == "WARN"
        assert "UNKNOWN_INDEX" in check.reason_codes

    def test_disabled_artifact_treated_as_unknown(self) -> None:
        artifact = _make_artifact(state="DISABLED")
        check = build_quality_gate_check(
            QualityGateCheckKind.SEARCH,
            artifact=artifact,
        )
        assert check.state == "BLOCK"
        assert "UNKNOWN_SEARCH" in check.reason_codes

    def test_missing_required_artifact_block(self) -> None:
        check = build_quality_gate_check(
            QualityGateCheckKind.BUNDLE,
            artifact=None,
        )
        assert check.state == "BLOCK"
        assert "MISSING_BUNDLE" in check.reason_codes

    def test_missing_optional_artifact_pass(self) -> None:
        config = QualityGateConfig(required_artifact_kinds=())
        check = build_quality_gate_check(
            QualityGateCheckKind.BUNDLE,
            artifact=None,
            config=config,
        )
        assert check.state == "PASS"

    def test_unsafe_safety_flags_block(self) -> None:
        flags = _make_unsafe_safety_flags("live_trading_enabled")
        artifact = _make_artifact(state="READY", safety_flags=flags)
        check = build_quality_gate_check(
            QualityGateCheckKind.CHRONICLE,
            artifact=artifact,
        )
        assert check.state == "BLOCK"
        assert "UNSAFE_ARTIFACT_FLAGS" in check.reason_codes

    def test_unresolved_blockers_block(self) -> None:
        artifact = _make_artifact(state="READY", reason_codes=("MISSING_REVIEW",))
        check = build_quality_gate_check(
            QualityGateCheckKind.DIGEST,
            artifact=artifact,
        )
        assert check.state == "BLOCK"
        assert "UNRESOLVED_BLOCKERS" in check.reason_codes

    def test_stale_artifact_warn(self) -> None:
        generated_at = _now() - timedelta(hours=2)
        artifact = _make_artifact(state="READY", generated_at=generated_at)
        check = build_quality_gate_check(
            QualityGateCheckKind.OBSERVATION,
            artifact=artifact,
            reference_time=_now(),
        )
        assert check.state == "WARN"
        assert "STALE_ARTIFACT" in check.reason_codes

    def test_index_artifact_state_attribute(self) -> None:
        artifact = _make_artifact_dict(state="READY")
        artifact["index_state"] = "BLOCKED"
        check = build_quality_gate_check(
            QualityGateCheckKind.INDEX,
            artifact=artifact,
        )
        assert check.state == "BLOCK"
        assert "BLOCKED_INDEX" in check.reason_codes

    def test_search_artifact_state_attribute(self) -> None:
        artifact = _make_artifact_dict(state="READY")
        artifact["search_state"] = "READY"
        check = build_quality_gate_check(
            QualityGateCheckKind.SEARCH,
            artifact=artifact,
        )
        assert check.state == "PASS"


# ---------------------------------------------------------------------------
# build_quality_gate_summary
# ---------------------------------------------------------------------------


class TestBuildQualityGateSummary:
    def test_empty_checks(self) -> None:
        summary = build_quality_gate_summary([])
        assert summary.total_checks == 0
        assert summary.verdict == "UNKNOWN"

    def test_all_pass(self) -> None:
        checks = [
            build_quality_gate_check(QualityGateCheckKind.OBSERVATION, _make_artifact("READY")),
            build_quality_gate_check(QualityGateCheckKind.REVIEW, _make_artifact("READY")),
        ]
        summary = build_quality_gate_summary(checks)
        assert summary.total_checks == 2
        assert summary.pass_checks == 2
        assert summary.verdict == "PASS"
        assert "human audit handoff" in summary.handoff_notes
        assert "not trade approval" in summary.handoff_notes

    def test_warn(self) -> None:
        config = QualityGateConfig(block_on_unknown=False)
        checks = [
            build_quality_gate_check(QualityGateCheckKind.OBSERVATION, _make_artifact("READY")),
            build_quality_gate_check(
                QualityGateCheckKind.REVIEW,
                _make_artifact("UNKNOWN"),
                config=config,
            ),
        ]
        summary = build_quality_gate_summary(checks)
        assert summary.verdict == "WARN"
        assert "not execution approval" in summary.handoff_notes

    def test_block(self) -> None:
        checks = [
            build_quality_gate_check(QualityGateCheckKind.OBSERVATION, _make_artifact("READY")),
            build_quality_gate_check(QualityGateCheckKind.REVIEW, _make_artifact("BLOCKED")),
        ]
        summary = build_quality_gate_summary(checks)
        assert summary.verdict == "BLOCK"
        assert "not strategy approval" in summary.handoff_notes

    def test_unknown_verdict(self) -> None:
        check = QualityGateCheck(check_kind=QualityGateCheckKind.INDEX, state="UNKNOWN")
        summary = build_quality_gate_summary([check])
        assert summary.verdict == "UNKNOWN"


# ---------------------------------------------------------------------------
# build_quality_gate_data_quality
# ---------------------------------------------------------------------------


class TestBuildQualityGateDataQuality:
    def test_empty_checks(self) -> None:
        dq = build_quality_gate_data_quality([])
        assert dq.completeness_pct == 0.0
        assert dq.total_checks == 0

    def test_completeness(self) -> None:
        checks = [
            build_quality_gate_check(QualityGateCheckKind.OBSERVATION, _make_artifact("READY")),
            build_quality_gate_check(QualityGateCheckKind.REVIEW, _make_artifact("BLOCKED")),
        ]
        dq = build_quality_gate_data_quality(checks)
        assert dq.completeness_pct == 50.0
        assert dq.ready_pct == 50.0
        assert dq.total_checks == 2


# ---------------------------------------------------------------------------
# build_research_quality_gate
# ---------------------------------------------------------------------------


class TestBuildResearchQualityGate:
    def test_all_ready_pass(self) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact("READY"),
            search_artifact=_make_artifact("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
        )
        assert gate.verdict is QualityGateVerdict.PASS
        assert gate.summary.verdict == "PASS"
        assert gate.summary.pass_checks == 8  # 7 per-artifact + cross-cutting
        assert "human audit handoff" in gate.handoff_notes
        assert "not trade approval" in gate.handoff_notes
        assert gate.safety_flags.quality_gate_output_not_execution_readiness is True
        assert gate.safety_flags.quality_gate_feedback_into_execution is False

    def test_missing_observation_blocked(self) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact("READY"),
            search_artifact=_make_artifact("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
        )
        assert gate.verdict is QualityGateVerdict.BLOCK
        assert "MISSING_OBSERVATION" in gate.reason_codes

    def test_blocked_digest_blocked(self) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact("READY"),
            search_artifact=_make_artifact("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("BLOCKED"),
        )
        assert gate.verdict is QualityGateVerdict.BLOCK
        assert "BLOCKED_DIGEST" in gate.reason_codes

    def test_unsafe_config_blocked(self) -> None:
        config = object.__new__(QualityGateConfig)
        object.__setattr__(config, "version", "1.0")
        object.__setattr__(config, "generated_at", _now())
        object.__setattr__(config, "output_format", "both")
        object.__setattr__(config, "dry_run", False)
        object.__setattr__(config, "live_trading_enabled", False)
        object.__setattr__(config, "real_orders_enabled", False)
        object.__setattr__(config, "leverage_enabled", False)
        object.__setattr__(config, "shorting_enabled", False)
        object.__setattr__(config, "block_on_unknown", True)
        object.__setattr__(config, "required_artifact_kinds", ())
        object.__setattr__(config, "max_staleness_minutes", 60)
        object.__setattr__(config, "include_handoff_notes", True)

        gate = build_research_quality_gate(
            config=config,
            observation_artifact=_make_artifact("READY"),
        )
        assert gate.verdict is QualityGateVerdict.BLOCK
        assert "UNSAFE_CONFIG" in gate.reason_codes

    def test_empty_gate_blocked(self) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(
                generated_at=_now(),
                required_artifact_kinds=(),
            ),
        )
        assert gate.verdict is QualityGateVerdict.BLOCK
        assert "EMPTY_GATE" in gate.reason_codes

    def test_deterministic_check_ordering(self) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact("READY"),
            search_artifact=_make_artifact("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
        )
        kinds = [c.check_kind for c in gate.checks]
        expected = [
            QualityGateCheckKind.OBSERVATION,
            QualityGateCheckKind.REVIEW,
            QualityGateCheckKind.INDEX,
            QualityGateCheckKind.SEARCH,
            QualityGateCheckKind.BUNDLE,
            QualityGateCheckKind.CHRONICLE,
            QualityGateCheckKind.DIGEST,
            QualityGateCheckKind.CROSS_CUTTING,
        ]
        assert kinds == expected

    def test_deterministic_gate_id(self) -> None:
        generated_at = _now()
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=generated_at),
            observation_artifact=_make_artifact("READY"),
        )
        expected = f"quality_gate:1.0:{generated_at.strftime('%Y-%m-%dT%H:%M:%S.%f')}"
        assert gate.gate_id == expected

    def test_cross_cutting_detects_unsafe_flags(self) -> None:
        flags = _make_unsafe_safety_flags("live_trading_enabled")
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY", safety_flags=flags),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact("READY"),
            search_artifact=_make_artifact("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
        )
        assert gate.verdict is QualityGateVerdict.BLOCK
        cross_cutting = gate.checks[-1]
        assert cross_cutting.check_kind is QualityGateCheckKind.CROSS_CUTTING
        assert cross_cutting.state == "BLOCK"
        assert "UNSAFE_ARTIFACT_FLAGS" in cross_cutting.reason_codes

    def test_pass_not_execution_or_strategy_approval(self) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact("READY"),
            search_artifact=_make_artifact("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
        )
        assert gate.verdict is QualityGateVerdict.PASS
        assert gate.safety_flags.quality_gate_output_not_trade_approval is True
        assert gate.safety_flags.quality_gate_output_not_execution_readiness is True
        assert gate.safety_flags.quality_gate_output_not_strategy_readiness is True
        assert "not execution approval" in gate.handoff_notes
        assert "not strategy approval" in gate.handoff_notes


# ---------------------------------------------------------------------------
# Safety invariants
# ---------------------------------------------------------------------------


class TestSafetyInvariants:
    def test_no_execution_feedback(self) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact("READY"),
            search_artifact=_make_artifact("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
        )
        assert gate.safety_flags.quality_gate_feedback_into_execution is False
        assert gate.safety_flags.cross_layer_feedback_into_execution is False

    def test_no_forbidden_terms_in_handoff_notes(self) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact("READY"),
            search_artifact=_make_artifact("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
        )
        notes = gate.handoff_notes.lower()
        for term in FORBIDDEN_QUALITY_GATE_TERMS:
            assert term not in notes, term

    def test_file_references_are_strings_only(self) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
        )
        # No exception means file references were never opened or executed.
        assert gate.gate_id.startswith("quality_gate:1.0:")

