"""Integration tests for hunter.research_quality_gate package.

MVP-17 end-to-end integration tests only.
No network, database, Freqtrade, Binance, exchange, trading,
Web UI, dashboard, or production data access is exercised here.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.research_quality_gate.engine import build_research_quality_gate
from hunter.research_quality_gate.models import (
    FORBIDDEN_QUALITY_GATE_TERMS,
    QualityGateCheckKind,
    QualityGateConfig,
    QualityGateSafetyFlags,
    QualityGateVerdict,
)
from hunter.research_quality_gate.writer import (
    atomic_write_json_research_quality_gate,
    atomic_write_markdown_research_quality_gate,
    research_quality_gate_to_dict,
    research_quality_gate_to_markdown,
    write_research_quality_gate,
)


def _now() -> datetime:
    return datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_safety_flags(**overrides: object) -> QualityGateSafetyFlags:
    """Return safe safety flags, allowing controlled overrides for tests."""
    data: dict[str, object] = {
        "dry_run": True,
        "live_trading_enabled": False,
        "real_orders_enabled": False,
        "leverage_enabled": False,
        "shorting_enabled": False,
        "quality_gate_output_is_human_audit_only": True,
        "quality_gate_output_not_trading_signal": True,
        "quality_gate_output_not_trade_approval": True,
        "quality_gate_output_not_execution_readiness": True,
        "quality_gate_output_not_strategy_readiness": True,
        "quality_gate_output_not_for_execution": True,
        "quality_gate_output_not_for_strategy": True,
        "quality_gate_output_not_for_freqtrade": True,
        "quality_gate_output_not_for_order": True,
        "quality_gate_output_not_for_exchange": True,
        "quality_gate_feedback_into_execution": False,
        "cross_layer_feedback_into_execution": False,
        "file_refs_not_traversed": True,
    }
    data.update(overrides)
    return QualityGateSafetyFlags(**data)  # type: ignore[arg-type]


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
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    """Return a dict-based artifact for end-to-end gate evaluation."""
    if generated_at is None:
        generated_at = _now()
    if safety_flags is None:
        safety_flags = _make_safety_flags()
    return {
        "state": state,
        "reason_codes": reason_codes,
        "generated_at": generated_at,
        "safety_flags": safety_flags,
        "metadata": metadata or {},
    }


def _build_all_ready_gate(**overrides: object) -> QualityGateVerdict:
    """Build a PASS gate with all required artifacts ready."""
    config = QualityGateConfig(generated_at=_now())
    return build_research_quality_gate(
        config=config,
        observation_artifact=_make_artifact("READY"),
        review_artifact=_make_artifact("READY"),
        index_artifact={"index_state": "READY", "reason_codes": (), "generated_at": _now(), "safety_flags": _make_safety_flags(), "metadata": {}},
        search_artifact={"search_state": "READY", "reason_codes": (), "generated_at": _now(), "safety_flags": _make_safety_flags(), "metadata": {}},
        bundle_artifact=_make_artifact("READY"),
        chronicle_artifact=_make_artifact("READY"),
        digest_artifact=_make_artifact("READY"),
    )


# ---------------------------------------------------------------------------
# Happy path / verdict integration
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_full_flow_build_serialize_write(self, tmp_path: Path) -> None:
        gate = _build_all_ready_gate()

        assert gate.verdict is QualityGateVerdict.PASS

        # Serialize to dict
        data = research_quality_gate_to_dict(gate)
        assert data["gate_id"] == gate.gate_id
        assert data["verdict"] == "pass"
        assert len(data["checks"]) == 8

        # Write to files
        json_path = tmp_path / "gate.json"
        md_path = tmp_path / "gate.md"
        write_research_quality_gate(gate, json_path=json_path, markdown_path=md_path)

        assert json_path.exists()
        assert md_path.exists()

        # JSON round-trip
        loaded = json.loads(json_path.read_text(encoding="utf-8"))
        assert loaded["gate_id"] == gate.gate_id
        assert loaded["verdict"] == "pass"

        # Markdown content
        md_text = md_path.read_text(encoding="utf-8")
        assert "# Research Quality Gate" in md_text
        assert "human-audit artifact only" in md_text

    def test_pass_gate_all_ready(self) -> None:
        gate = _build_all_ready_gate()

        assert gate.verdict is QualityGateVerdict.PASS
        assert gate.summary.verdict == "PASS"
        assert gate.summary.pass_checks == 8
        assert gate.summary.block_checks == 0
        assert gate.summary.unknown_checks == 0

        kinds = [check.check_kind for check in gate.checks]
        assert QualityGateCheckKind.CROSS_CUTTING in kinds


class TestVerdictIntegration:
    def test_warn_gate_non_blocking_stale(self) -> None:
        stale = _now() - timedelta(hours=2)
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY", generated_at=stale),
            review_artifact=_make_artifact("READY"),
            index_artifact={"index_state": "READY", "reason_codes": (), "generated_at": _now(), "safety_flags": _make_safety_flags(), "metadata": {}},
            search_artifact={"search_state": "READY", "reason_codes": (), "generated_at": _now(), "safety_flags": _make_safety_flags(), "metadata": {}},
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
        )

        assert gate.verdict is QualityGateVerdict.WARN
        assert gate.summary.warn_checks >= 1
        assert any("STALE_ARTIFACT" in check.reason_codes for check in gate.checks)

    def test_warn_gate_unknown_when_not_blocking(self) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now(), block_on_unknown=False),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("UNKNOWN"),
            index_artifact={"index_state": "READY", "reason_codes": (), "generated_at": _now(), "safety_flags": _make_safety_flags(), "metadata": {}},
            search_artifact={"search_state": "READY", "reason_codes": (), "generated_at": _now(), "safety_flags": _make_safety_flags(), "metadata": {}},
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
        )

        assert gate.verdict is QualityGateVerdict.WARN
        assert any(check.check_kind is QualityGateCheckKind.REVIEW and check.state == "WARN" for check in gate.checks)

    def test_block_gate_missing_required(self) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            review_artifact=_make_artifact("READY"),
            index_artifact={"index_state": "READY", "reason_codes": (), "generated_at": _now(), "safety_flags": _make_safety_flags(), "metadata": {}},
            search_artifact={"search_state": "READY", "reason_codes": (), "generated_at": _now(), "safety_flags": _make_safety_flags(), "metadata": {}},
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
        )

        assert gate.verdict is QualityGateVerdict.BLOCK
        assert "MISSING_OBSERVATION" in gate.reason_codes

    def test_block_gate_blocked_check(self) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact={"index_state": "READY", "reason_codes": (), "generated_at": _now(), "safety_flags": _make_safety_flags(), "metadata": {}},
            search_artifact={"search_state": "READY", "reason_codes": (), "generated_at": _now(), "safety_flags": _make_safety_flags(), "metadata": {}},
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("BLOCKED"),
        )

        assert gate.verdict is QualityGateVerdict.BLOCK
        assert "BLOCKED_DIGEST" in gate.reason_codes

    def test_block_gate_unknown_by_default(self) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact={"index_state": "UNKNOWN", "reason_codes": (), "generated_at": _now(), "safety_flags": _make_safety_flags(), "metadata": {}},
            search_artifact={"search_state": "READY", "reason_codes": (), "generated_at": _now(), "safety_flags": _make_safety_flags(), "metadata": {}},
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
        )

        assert gate.verdict is QualityGateVerdict.BLOCK
        assert "UNKNOWN_INDEX" in gate.reason_codes

    def test_unknown_gate_no_artifacts_required_none(self) -> None:
        # No artifacts provided and none required → UNKNOWN (engine treats empty as BLOCK/EMPTY_GATE)
        gate = build_research_quality_gate(
            config=QualityGateConfig(
                generated_at=_now(),
                required_artifact_kinds=(),
            ),
        )

        # Empty gate with no artifacts and no required kinds is fail-closed to BLOCK.
        assert gate.verdict is QualityGateVerdict.BLOCK
        assert "EMPTY_GATE" in gate.reason_codes


# ---------------------------------------------------------------------------
# Safety and disclaimer integration
# ---------------------------------------------------------------------------


class TestSafetyAndDisclaimers:
    def test_pass_disclaimers_preserved(self) -> None:
        gate = _build_all_ready_gate()

        notes = gate.handoff_notes.lower()
        assert "not trade approval" in notes
        assert "not execution approval" in notes
        assert "not strategy approval" in notes
        assert "not release permission" in notes
        assert "not transaction permission" in notes

    def test_safety_flags_block_unsafe_artifact(self) -> None:
        unsafe_flags = _make_unsafe_safety_flags("live_trading_enabled")
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY", safety_flags=unsafe_flags),
            review_artifact=_make_artifact("READY"),
            index_artifact={"index_state": "READY", "reason_codes": (), "generated_at": _now(), "safety_flags": _make_safety_flags(), "metadata": {}},
            search_artifact={"search_state": "READY", "reason_codes": (), "generated_at": _now(), "safety_flags": _make_safety_flags(), "metadata": {}},
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
        )

        assert gate.verdict is QualityGateVerdict.BLOCK
        assert "UNSAFE_ARTIFACT_FLAGS" in gate.reason_codes

    def test_unresolved_blockers_block(self) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY", reason_codes=("MISSING_REVIEW",)),
            review_artifact=_make_artifact("READY"),
            index_artifact={"index_state": "READY", "reason_codes": (), "generated_at": _now(), "safety_flags": _make_safety_flags(), "metadata": {}},
            search_artifact={"search_state": "READY", "reason_codes": (), "generated_at": _now(), "safety_flags": _make_safety_flags(), "metadata": {}},
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
        )

        assert gate.verdict is QualityGateVerdict.BLOCK
        observation_check = next(
            check for check in gate.checks if check.check_kind is QualityGateCheckKind.OBSERVATION
        )
        assert observation_check.state == "BLOCK"
        assert "UNRESOLVED_BLOCKERS" in observation_check.reason_codes

    def test_no_forbidden_terms_in_handoff_notes(self) -> None:
        gate = _build_all_ready_gate()

        notes = gate.handoff_notes.lower()
        for term in FORBIDDEN_QUALITY_GATE_TERMS:
            assert term not in notes, term

    def test_feedback_flags_false(self) -> None:
        gate = _build_all_ready_gate()

        assert gate.safety_flags.quality_gate_feedback_into_execution is False
        assert gate.safety_flags.cross_layer_feedback_into_execution is False


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_deterministic_check_ordering(self) -> None:
        gate = _build_all_ready_gate()

        kinds = [check.check_kind for check in gate.checks]
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

    def test_same_inputs_same_gate_id(self) -> None:
        generated_at = _now()
        config = QualityGateConfig(generated_at=generated_at)
        gate1 = build_research_quality_gate(
            config=config,
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
        )
        gate2 = build_research_quality_gate(
            config=config,
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
        )

        assert gate1.gate_id == gate2.gate_id
        assert gate1.generated_at == gate2.generated_at


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_research_quality_gate_to_dict_full_gate(self) -> None:
        gate = _build_all_ready_gate()
        data = research_quality_gate_to_dict(gate)

        assert data["gate_id"] == gate.gate_id
        assert data["version"] == "1.0"
        assert data["verdict"] == "pass"
        assert len(data["checks"]) == 8
        assert "summary" in data
        assert "data_quality" in data
        assert "safety_flags" in data
        assert "config" in data
        assert "reason_codes" in data
        assert "handoff_notes" in data

        check_data = data["checks"][0]
        assert "check_kind" in check_data
        assert "state" in check_data
        assert "reason_codes" in check_data
        assert "notes" in check_data
        assert "metadata" in check_data

    def test_dict_preserves_check_kinds_and_reason_codes(self) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            observation_artifact=_make_artifact("BLOCKED"),
        )
        data = research_quality_gate_to_dict(gate)

        kinds = {check["check_kind"] for check in data["checks"]}
        assert "observation" in kinds
        assert "cross_cutting" in kinds
        assert any("BLOCKED_OBSERVATION" in check["reason_codes"] for check in data["checks"])
        assert any("MISSING_REVIEW" in check["reason_codes"] for check in data["checks"])

    def test_dict_preserves_safety_flags(self) -> None:
        gate = _build_all_ready_gate()
        data = research_quality_gate_to_dict(gate)

        flags = data["safety_flags"]
        assert flags["quality_gate_output_is_human_audit_only"] is True
        assert flags["quality_gate_output_not_trade_approval"] is True
        assert flags["quality_gate_output_not_execution_readiness"] is True
        assert flags["quality_gate_output_not_strategy_readiness"] is True
        assert flags["quality_gate_feedback_into_execution"] is False
        assert flags["cross_layer_feedback_into_execution"] is False

    def test_research_quality_gate_to_markdown_includes_safety_notice(self) -> None:
        gate = _build_all_ready_gate()
        md = research_quality_gate_to_markdown(gate)

        assert "human-audit artifact only" in md
        assert "not a trading signal" in md
        assert "not trade approval" in md
        assert "not execution readiness" in md
        assert "not strategy readiness" in md
        assert "not for execution" in md
        assert "not for strategy" in md
        assert "not for Freqtrade shell" in md
        assert "not for transaction placement" in md
        assert "not for exchange" in md

    def test_markdown_includes_checks_as_plain_text(self) -> None:
        gate = _build_all_ready_gate()
        md = research_quality_gate_to_markdown(gate)

        for kind in QualityGateCheckKind:
            assert kind.value in md

        assert "PASS" in md or "pass" in md.lower()

    def test_markdown_includes_handoff_notes(self) -> None:
        gate = _build_all_ready_gate()
        md = research_quality_gate_to_markdown(gate)

        assert "human audit handoff" in md
        assert "not trade approval" in md


# ---------------------------------------------------------------------------
# File writes
# ---------------------------------------------------------------------------


class TestWrites:
    def test_write_research_quality_gate_both_formats(self, tmp_path: Path) -> None:
        gate = _build_all_ready_gate()
        json_out, md_out = write_research_quality_gate(
            gate,
            json_path=tmp_path / "gate.json",
            markdown_path=tmp_path / "gate.md",
        )

        assert json_out.exists()
        assert md_out.exists()

        data = json.loads(json_out.read_text(encoding="utf-8"))
        assert data["gate_id"] == gate.gate_id
        assert data["verdict"] == "pass"

        md_text = md_out.read_text(encoding="utf-8")
        assert "human-audit artifact only" in md_text

    def test_atomic_write_json(self, tmp_path: Path) -> None:
        gate = _build_all_ready_gate()
        target = tmp_path / "gate.json"
        path = atomic_write_json_research_quality_gate(gate, target_path=target)

        assert path == target
        assert target.exists()

        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["gate_id"] == gate.gate_id
        assert data["verdict"] == "pass"

    def test_atomic_write_markdown(self, tmp_path: Path) -> None:
        gate = _build_all_ready_gate()
        target = tmp_path / "gate.md"
        path = atomic_write_markdown_research_quality_gate(gate, target_path=target)

        assert path == target
        assert target.exists()

        text = target.read_text(encoding="utf-8")
        assert "# Research Quality Gate" in text

    def test_json_round_trip_preserves_key_fields(self, tmp_path: Path) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("BLOCKED"),
        )
        json_path = tmp_path / "gate.json"
        atomic_write_json_research_quality_gate(gate, target_path=json_path)

        loaded = json.loads(json_path.read_text(encoding="utf-8"))
        assert loaded["gate_id"] == gate.gate_id
        assert loaded["verdict"] == "block"
        assert any(check["check_kind"] == "observation" for check in loaded["checks"])
        assert any(check["check_kind"] == "review" for check in loaded["checks"])
        assert any("BLOCKED_REVIEW" in check["reason_codes"] for check in loaded["checks"])
        assert loaded["safety_flags"]["quality_gate_output_not_trade_approval"] is True


# ---------------------------------------------------------------------------
# Fail-closed behavior
# ---------------------------------------------------------------------------


class TestFailClosed:
    def test_invalid_config_blocked(self) -> None:
        config = object.__new__(QualityGateConfig)
        object.__setattr__(config, "version", "1.0")
        object.__setattr__(config, "generated_at", _now())
        object.__setattr__(config, "output_format", "invalid")
        object.__setattr__(config, "dry_run", True)
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
        assert "INVALID_CONFIG" in gate.reason_codes

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

    def test_no_artifacts_with_required_blocked(self) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
        )

        assert gate.verdict is QualityGateVerdict.BLOCK
        missing_codes = {"MISSING_OBSERVATION", "MISSING_REVIEW", "MISSING_INDEX", "MISSING_SEARCH", "MISSING_BUNDLE", "MISSING_CHRONICLE", "MISSING_DIGEST"}
        assert missing_codes.issubset(set(gate.reason_codes))


# ---------------------------------------------------------------------------
# Metadata / file reference safety
# ---------------------------------------------------------------------------


class TestMetadataSafety:
    def test_file_reference_strings_not_opened(self, tmp_path: Path) -> None:
        from hunter.research_quality_gate.models import QualityGateCheck, ResearchQualityGate

        check = QualityGateCheck(
            check_kind=QualityGateCheckKind.OBSERVATION,
            state="PASS",
            metadata={
                "report_path": "reports/2025/btc.md",
                "nested": {"file_ref": "data/observation/x.json"},
            },
        )
        gate = ResearchQualityGate(
            gate_id="quality_gate:1.0:2025-01-01T12:00:00",
            generated_at=_now(),
            verdict=QualityGateVerdict.PASS,
            checks=(check,),
        )

        # Serializing and writing must not open or traverse file references.
        json_path = tmp_path / "gate.json"
        md_path = tmp_path / "gate.md"
        write_research_quality_gate(gate, json_path=json_path, markdown_path=md_path)

        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["checks"][0]["metadata"]["report_path"] == "reports/2025/btc.md"
        assert data["checks"][0]["metadata"]["nested"]["file_ref"] == "data/observation/x.json"

        md_text = md_path.read_text(encoding="utf-8")
        assert "reports/2025/btc.md" in md_text

    def test_metadata_preserved_in_dict(self) -> None:
        from hunter.research_quality_gate.models import QualityGateCheck, ResearchQualityGate

        check = QualityGateCheck(
            check_kind=QualityGateCheckKind.OBSERVATION,
            state="PASS",
            metadata={"symbol": "BTC/USDT", "source": "observation"},
        )
        gate = ResearchQualityGate(
            gate_id="quality_gate:1.0:2025-01-01T12:00:00",
            generated_at=_now(),
            verdict=QualityGateVerdict.PASS,
            checks=(check,),
        )

        data = research_quality_gate_to_dict(gate)
        observation_check = next(
            check for check in data["checks"] if check["check_kind"] == "observation"
        )
        assert observation_check["metadata"]["symbol"] == "BTC/USDT"
        assert observation_check["metadata"]["source"] == "observation"
