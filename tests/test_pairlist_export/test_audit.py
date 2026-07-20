"""Focused tests for hunter.pairlist_export.audit (SPEC-074)."""

from __future__ import annotations

from decimal import Decimal

from hunter.pairlist_export.audit import (
    audit_record_to_dict,
    build_audit_record,
    explain_audit_record,
)
from hunter.pairlist_export.models import PairlistRankingConfig
from hunter.pairlist_export.ranking_adapter import rank_pairs


def _ranked_pairs():
    config = PairlistRankingConfig(min_pairs=1, publish_candidates=2, max_pairs=10)
    eligible = ("BTC/USDT:USDT", "ETH/USDT:USDT", "XYZ/USDT:USDT")
    rs_scores = {"BTC/USDT:USDT": Decimal("80"), "ETH/USDT:USDT": Decimal("60")}
    oi_scores = {"BTC/USDT:USDT": Decimal("50"), "ETH/USDT:USDT": Decimal("40")}
    return rank_pairs(config, eligible, rs_scores, oi_scores)


def test_build_audit_record_counts_and_reason_summary() -> None:
    ranked = _ranked_pairs()
    audit = build_audit_record(as_of_date="2026-07-21", universe_total=100, ranked_pairs=ranked)

    assert audit.as_of_date == "2026-07-21"
    assert audit.universe_total == 100
    assert audit.eligible_count == 3
    assert audit.selected_count == 2
    assert audit.rejected_count == 1
    assert audit.reason_code_summary["INSUFFICIENT_EVIDENCE"] == 1
    assert audit.fingerprint


def test_build_audit_record_fingerprint_is_deterministic() -> None:
    ranked = _ranked_pairs()
    first = build_audit_record("2026-07-21", 100, ranked)
    second = build_audit_record("2026-07-21", 100, ranked)
    assert first.fingerprint == second.fingerprint


def test_audit_record_to_dict_shapes_selected_and_rejected() -> None:
    ranked = _ranked_pairs()
    audit = build_audit_record("2026-07-21", 100, ranked)
    payload = audit_record_to_dict(audit)

    assert payload["selected_count"] == 2
    assert len(payload["selected"]) == 2
    assert len(payload["rejected"]) == 1
    assert payload["rejected"][0]["pair"] == "XYZ/USDT:USDT"
    assert isinstance(payload["selected"][0]["rs_score"], (str, type(None)))
    assert "research-only" in payload["research_notice"].lower()


def test_explain_audit_record_renders_key_sections() -> None:
    ranked = _ranked_pairs()
    audit = build_audit_record("2026-07-21", 100, ranked)
    text = explain_audit_record(audit)

    assert "as-of 2026-07-21" in text
    assert "Selected: 2" in text
    assert "Rejected: 1" in text
    assert "XYZ/USDT:USDT" in text
