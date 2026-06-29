"""Tests for hunter.research_quality_gate.writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.research_quality_gate.engine import build_research_quality_gate
from hunter.research_quality_gate.models import (
    QualityGateCheck,
    QualityGateCheckKind,
    QualityGateConfig,
    QualityGateDataQuality,
    QualityGateSafetyFlags,
    QualityGateSummary,
    QualityGateVerdict,
    ResearchQualityGate,
)
from hunter.research_quality_gate.writer import (
    DEFAULT_QUALITY_GATE_JSON_PATH,
    DEFAULT_QUALITY_GATE_MARKDOWN_PATH,
    atomic_write_json_research_quality_gate,
    atomic_write_markdown_research_quality_gate,
    quality_gate_check_to_dict,
    quality_gate_config_to_dict,
    quality_gate_data_quality_to_dict,
    quality_gate_safety_flags_to_dict,
    quality_gate_summary_to_dict,
    research_quality_gate_to_dict,
    research_quality_gate_to_markdown,
    write_research_quality_gate,
)


def _now() -> datetime:
    return datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_gate(
    verdict: QualityGateVerdict = QualityGateVerdict.PASS,
    checks: tuple[QualityGateCheck, ...] = (),
    reason_codes: tuple[str, ...] = (),
    handoff_notes: str = "",
) -> ResearchQualityGate:
    if not handoff_notes:
        if verdict is QualityGateVerdict.PASS:
            handoff_notes = (
                "All required artifact categories are ready. Package appears complete "
                "for human audit handoff. This is not trade approval, not execution approval, "
                "not strategy approval, not release permission, and not transaction permission."
            )
        elif verdict is QualityGateVerdict.BLOCK:
            handoff_notes = (
                "Package is not ready for human audit handoff. Resolve blockers before handoff. "
                "This is not trade approval, not execution approval, not strategy approval, "
                "not release permission, and not transaction permission."
            )
        else:
            handoff_notes = "Insufficient information."
    summary = QualityGateSummary(
        total_checks=len(checks),
        pass_checks=sum(1 for c in checks if c.state == "PASS"),
        warn_checks=sum(1 for c in checks if c.state == "WARN"),
        block_checks=sum(1 for c in checks if c.state == "BLOCK"),
        unknown_checks=sum(1 for c in checks if c.state == "UNKNOWN"),
        total_artifacts=len(checks),
        total_blockers=sum(1 for c in checks if c.state in ("BLOCK", "UNKNOWN")),
        unresolved_blockers=sum(len(c.reason_codes) for c in checks if c.state == "BLOCK"),
        verdict=verdict.value,
        handoff_notes=handoff_notes,
    )
    data_quality = QualityGateDataQuality(
        completeness_pct=100.0 if verdict is QualityGateVerdict.PASS else 0.0,
        ready_pct=100.0 if verdict is QualityGateVerdict.PASS else 0.0,
        total_checks=len(checks),
        reason="ok" if verdict is QualityGateVerdict.PASS else "blocked",
    )
    return ResearchQualityGate(
        gate_id="quality_gate:1.0:2025-01-01T12:00:00",
        generated_at=_now(),
        version="1.0",
        verdict=verdict,
        checks=checks,
        summary=summary,
        data_quality=data_quality,
        safety_flags=QualityGateSafetyFlags(),
        config=QualityGateConfig(generated_at=_now()),
        reason_codes=reason_codes,
        handoff_notes=handoff_notes,
    )


# ---------------------------------------------------------------------------
# Dict serialization
# ---------------------------------------------------------------------------


class TestQualityGateSafetyFlagsToDict:
    def test_all_fields_present(self) -> None:
        flags = QualityGateSafetyFlags()
        data = quality_gate_safety_flags_to_dict(flags)
        assert data["dry_run"] is True
        assert data["live_trading_enabled"] is False
        assert data["quality_gate_output_is_human_audit_only"] is True
        assert data["quality_gate_output_not_trade_approval"] is True
        assert data["quality_gate_output_not_execution_readiness"] is True
        assert data["quality_gate_output_not_strategy_readiness"] is True
        assert data["quality_gate_feedback_into_execution"] is False
        assert data["cross_layer_feedback_into_execution"] is False
        assert data["file_refs_not_traversed"] is True


class TestQualityGateConfigToDict:
    def test_fields(self) -> None:
        config = QualityGateConfig(generated_at=_now())
        data = quality_gate_config_to_dict(config)
        assert data["version"] == "1.0"
        assert data["generated_at"] == "2025-01-01T12:00:00+00:00"
        assert data["output_format"] == "both"
        assert data["dry_run"] is True
        assert data["block_on_unknown"] is True
        assert data["required_artifact_kinds"] == [
            "observation",
            "review",
            "index",
            "search",
            "bundle",
            "chronicle",
            "digest",
        ]


class TestQualityGateCheckToDict:
    def test_ready_check(self) -> None:
        check = QualityGateCheck(
            check_kind=QualityGateCheckKind.OBSERVATION,
            state="PASS",
            reason_codes=(),
            notes="ok",
            metadata={"artifact_type": "observation"},
        )
        data = quality_gate_check_to_dict(check)
        assert data["check_kind"] == "observation"
        assert data["state"] == "PASS"
        assert data["reason_codes"] == []
        assert data["notes"] == "ok"
        assert data["metadata"] == {"artifact_type": "observation"}


class TestQualityGateSummaryToDict:
    def test_summary(self) -> None:
        summary = QualityGateSummary(
            total_checks=2,
            pass_checks=1,
            warn_checks=1,
            verdict="WARN",
            handoff_notes="Review warnings.",
        )
        data = quality_gate_summary_to_dict(summary)
        assert data["total_checks"] == 2
        assert data["pass_checks"] == 1
        assert data["warn_checks"] == 1
        assert data["verdict"] == "WARN"
        assert data["handoff_notes"] == "Review warnings."


class TestQualityGateDataQualityToDict:
    def test_data_quality(self) -> None:
        dq = QualityGateDataQuality(
            completeness_pct=75.0,
            ready_pct=50.0,
            missing_count=1,
            total_checks=4,
            reason="partial",
        )
        data = quality_gate_data_quality_to_dict(dq)
        assert data["completeness_pct"] == 75.0
        assert data["ready_pct"] == 50.0
        assert data["missing_count"] == 1
        assert data["total_checks"] == 4
        assert data["reason"] == "partial"


class TestResearchQualityGateToDict:
    def test_pass_gate(self) -> None:
        gate = _make_gate(verdict=QualityGateVerdict.PASS)
        data = research_quality_gate_to_dict(gate)
        assert data["gate_id"] == "quality_gate:1.0:2025-01-01T12:00:00"
        assert data["verdict"] == "pass"
        assert data["version"] == "1.0"
        assert "generated_at" in data
        assert "checks" in data
        assert "summary" in data
        assert "data_quality" in data
        assert "safety_flags" in data
        assert "config" in data
        assert "reason_codes" in data
        assert "handoff_notes" in data
        assert data["safety_flags"]["quality_gate_output_not_execution_readiness"] is True
        assert data["safety_flags"]["quality_gate_output_not_strategy_readiness"] is True

    def test_blocked_gate(self) -> None:
        gate = _make_gate(
            verdict=QualityGateVerdict.BLOCK,
            checks=(
                QualityGateCheck(
                    check_kind=QualityGateCheckKind.OBSERVATION,
                    state="BLOCK",
                    reason_codes=("BLOCKED_OBSERVATION",),
                ),
            ),
            reason_codes=("BLOCKED_OBSERVATION",),
        )
        data = research_quality_gate_to_dict(gate)
        assert data["verdict"] == "block"
        assert data["checks"][0]["check_kind"] == "observation"
        assert data["checks"][0]["state"] == "BLOCK"
        assert data["checks"][0]["reason_codes"] == ["BLOCKED_OBSERVATION"]

    def test_metadata_not_traversed(self) -> None:
        """Check metadata is serialized as plain strings, never opened/executed."""
        check = QualityGateCheck(
            check_kind=QualityGateCheckKind.DIGEST,
            state="PASS",
            metadata={
                "report_path": "reports/2025/btc.md",
                "nested": {"file_ref": "data/observation/x.json"},
            },
        )
        gate = _make_gate(
            verdict=QualityGateVerdict.PASS,
            checks=(check,),
        )
        data = research_quality_gate_to_dict(gate)
        assert data["checks"][0]["metadata"]["report_path"] == "reports/2025/btc.md"
        assert data["checks"][0]["metadata"]["nested"]["file_ref"] == "data/observation/x.json"

    def test_json_safe_determinism(self) -> None:
        """Two identical gates produce identical JSON strings."""
        gate1 = _make_gate(verdict=QualityGateVerdict.PASS)
        gate2 = _make_gate(verdict=QualityGateVerdict.PASS)
        text1 = json.dumps(research_quality_gate_to_dict(gate1), sort_keys=True)
        text2 = json.dumps(research_quality_gate_to_dict(gate2), sort_keys=True)
        assert text1 == text2


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


class TestResearchQualityGateToMarkdown:
    def test_contains_safety_notice(self) -> None:
        gate = _make_gate(verdict=QualityGateVerdict.PASS)
        md = research_quality_gate_to_markdown(gate)
        assert "human-audit artifact only" in md
        assert "not a trading signal" in md
        assert "not trade approval" in md
        assert "not execution readiness" in md
        assert "not strategy readiness" in md

    def test_contains_gate_info(self) -> None:
        gate = _make_gate(verdict=QualityGateVerdict.PASS)
        md = research_quality_gate_to_markdown(gate)
        assert "quality_gate:1.0:2025-01-01T12:00:00" in md
        assert "2025-01-01T12:00:00+00:00" in md
        assert "pass" in md.lower()

    def test_contains_checks_table(self) -> None:
        gate = _make_gate(
            verdict=QualityGateVerdict.PASS,
            checks=(
                QualityGateCheck(
                    check_kind=QualityGateCheckKind.OBSERVATION,
                    state="PASS",
                    reason_codes=(),
                    notes="ready",
                ),
            ),
        )
        md = research_quality_gate_to_markdown(gate)
        assert "observation" in md
        assert "PASS" in md
        assert "ready" in md

    def test_contains_summary(self) -> None:
        gate = _make_gate(
            verdict=QualityGateVerdict.PASS,
            checks=(
                QualityGateCheck(check_kind=QualityGateCheckKind.OBSERVATION, state="PASS"),
            ),
        )
        md = research_quality_gate_to_markdown(gate)
        assert "total_checks" in md
        assert "pass_checks" in md

    def test_contains_data_quality(self) -> None:
        gate = _make_gate(verdict=QualityGateVerdict.PASS)
        md = research_quality_gate_to_markdown(gate)
        assert "completeness_pct" in md
        assert "ready_pct" in md

    def test_contains_safety_flags(self) -> None:
        gate = _make_gate(verdict=QualityGateVerdict.PASS)
        md = research_quality_gate_to_markdown(gate)
        assert "quality_gate_output_not_trade_approval" in md
        assert "quality_gate_output_not_execution_readiness" in md

    def test_contains_handoff_notes(self) -> None:
        gate = _make_gate(verdict=QualityGateVerdict.PASS)
        md = research_quality_gate_to_markdown(gate)
        assert "not trade approval" in md
        assert "not execution approval" in md
        assert "not strategy approval" in md

    def test_blocked_digest_markdown(self) -> None:
        gate = _make_gate(
            verdict=QualityGateVerdict.BLOCK,
            checks=(
                QualityGateCheck(
                    check_kind=QualityGateCheckKind.DIGEST,
                    state="BLOCK",
                    reason_codes=("BLOCKED_DIGEST",),
                ),
            ),
            reason_codes=("BLOCKED_DIGEST",),
        )
        md = research_quality_gate_to_markdown(gate)
        assert "block" in md.lower()
        assert "BLOCKED_DIGEST" in md
        assert "not execution readiness" in md

    def test_pass_not_execution_or_strategy_approval(self) -> None:
        gate = build_research_quality_gate(
            config=QualityGateConfig(generated_at=_now()),
            observation_artifact={"state": "READY", "reason_codes": ()},
            review_artifact={"state": "READY", "reason_codes": ()},
            index_artifact={"index_state": "READY", "reason_codes": ()},
            search_artifact={"search_state": "READY", "reason_codes": ()},
            bundle_artifact={"state": "READY", "reason_codes": ()},
            chronicle_artifact={"state": "READY", "reason_codes": ()},
            digest_artifact={"state": "READY", "reason_codes": ()},
        )
        md = research_quality_gate_to_markdown(gate)
        assert "PASS" in md
        assert "not execution readiness" in md
        assert "not strategy readiness" in md
        assert "not for execution" in md
        assert "not for strategy" in md
        assert "not for Freqtrade shell" in md
        assert "not for transaction placement" in md
        assert "not for exchange" in md


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


class TestAtomicWriteJsonResearchQualityGate:
    def test_writes_json(self, tmp_path: Path) -> None:
        gate = _make_gate(verdict=QualityGateVerdict.PASS)
        target = tmp_path / "gate.json"
        path = atomic_write_json_research_quality_gate(gate, target_path=target)
        assert path == target
        assert target.exists()
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["gate_id"] == gate.gate_id
        assert data["verdict"] == "pass"
        assert data["safety_flags"]["quality_gate_output_is_human_audit_only"] is True

    def test_default_path(self) -> None:
        assert DEFAULT_QUALITY_GATE_JSON_PATH == Path(
            "data/research_quality_gate/latest_research_quality_gate.json"
        )


class TestAtomicWriteMarkdownResearchQualityGate:
    def test_writes_markdown(self, tmp_path: Path) -> None:
        gate = _make_gate(verdict=QualityGateVerdict.PASS)
        target = tmp_path / "gate.md"
        path = atomic_write_markdown_research_quality_gate(gate, target_path=target)
        assert path == target
        assert target.exists()
        text = target.read_text(encoding="utf-8")
        assert "# Research Quality Gate" in text
        assert "human-audit artifact only" in text

    def test_default_path(self) -> None:
        assert DEFAULT_QUALITY_GATE_MARKDOWN_PATH == Path(
            "reports/research_quality_gate/latest_research_quality_gate.md"
        )


class TestWriteResearchQualityGate:
    def test_writes_both(self, tmp_path: Path) -> None:
        gate = _make_gate(verdict=QualityGateVerdict.PASS)
        json_out, md_out = write_research_quality_gate(
            gate,
            json_path=tmp_path / "gate.json",
            markdown_path=tmp_path / "gate.md",
        )
        assert json_out.exists()
        assert md_out.exists()
        data = json.loads(json_out.read_text(encoding="utf-8"))
        assert data["verdict"] == "pass"
        md_text = md_out.read_text(encoding="utf-8")
        assert "human-audit artifact only" in md_text


# ---------------------------------------------------------------------------
# Determinism and safety
# ---------------------------------------------------------------------------


class TestDeterminismAndSafety:
    def test_json_sorted_keys(self, tmp_path: Path) -> None:
        gate = _make_gate(verdict=QualityGateVerdict.PASS)
        path1 = tmp_path / "gate1.json"
        path2 = tmp_path / "gate2.json"
        atomic_write_json_research_quality_gate(gate, target_path=path1)
        atomic_write_json_research_quality_gate(gate, target_path=path2)
        text1 = path1.read_text(encoding="utf-8")
        text2 = path2.read_text(encoding="utf-8")
        assert text1 == text2
        # Re-serialize to dict and compare keys order deterministically.
        data1 = research_quality_gate_to_dict(gate)
        data2 = research_quality_gate_to_dict(gate)
        assert list(data1.keys()) == list(data2.keys())

    def test_no_forbidden_terms_in_markdown(self) -> None:
        from hunter.research_quality_gate.models import FORBIDDEN_QUALITY_GATE_TERMS

        gate = _make_gate(verdict=QualityGateVerdict.PASS)
        md = research_quality_gate_to_markdown(gate)
        # Check only human-facing prose sections; safety flag keys intentionally
        # include forbidden substrings (e.g., leverage_enabled) to surface state.
        prose = md.split("## Safety Flags")[0].lower()
        for term in FORBIDDEN_QUALITY_GATE_TERMS:
            assert term not in prose, term

    def test_metadata_strings_not_traversed(self) -> None:
        """File reference strings in metadata remain strings in output."""
        check = QualityGateCheck(
            check_kind=QualityGateCheckKind.DIGEST,
            state="PASS",
            metadata={"report_path": "reports/2025/btc.md"},
        )
        gate = _make_gate(verdict=QualityGateVerdict.PASS, checks=(check,))
        md = research_quality_gate_to_markdown(gate)
        assert "reports/2025/btc.md" in md
