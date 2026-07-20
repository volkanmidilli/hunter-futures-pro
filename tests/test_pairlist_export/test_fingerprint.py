"""Focused tests for hunter.pairlist_export.fingerprint (SPEC-074)."""

from __future__ import annotations

from decimal import Decimal

from hunter.pairlist_export.fingerprint import (
    canonical_json,
    compute_audit_fingerprint,
    compute_pair_fingerprint,
    compute_pairlist_fingerprint,
    fingerprint_payload,
)


def test_canonical_json_is_key_order_independent() -> None:
    a = canonical_json({"b": 1, "a": 2})
    b = canonical_json({"a": 2, "b": 1})
    assert a == b


def test_canonical_json_renders_decimal_as_string_not_float() -> None:
    encoded = canonical_json({"score": Decimal("82.50")})
    assert '"82.50"' in encoded


def test_fingerprint_payload_is_deterministic_across_calls() -> None:
    payload = {"pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"], "refresh_period": 3600}
    assert fingerprint_payload(payload) == fingerprint_payload(dict(payload))


def test_fingerprint_payload_changes_with_content() -> None:
    base = fingerprint_payload({"pairs": ["BTC/USDT:USDT"], "refresh_period": 3600})
    changed = fingerprint_payload({"pairs": ["ETH/USDT:USDT"], "refresh_period": 3600})
    assert base != changed


def test_compute_pair_fingerprint_sensitive_to_rank_and_scores() -> None:
    base = compute_pair_fingerprint(
        pair="BTC/USDT:USDT",
        rank=1,
        rs_score=Decimal("80"),
        oi_score=Decimal("70"),
        data_quality_pct=Decimal("100"),
        reason_codes=("RS_SCORE", "OI_LIQUIDITY"),
    )
    same = compute_pair_fingerprint(
        pair="BTC/USDT:USDT",
        rank=1,
        rs_score=Decimal("80"),
        oi_score=Decimal("70"),
        data_quality_pct=Decimal("100"),
        reason_codes=("RS_SCORE", "OI_LIQUIDITY"),
    )
    different_rank = compute_pair_fingerprint(
        pair="BTC/USDT:USDT",
        rank=2,
        rs_score=Decimal("80"),
        oi_score=Decimal("70"),
        data_quality_pct=Decimal("100"),
        reason_codes=("RS_SCORE", "OI_LIQUIDITY"),
    )
    assert base == same
    assert base != different_rank


def test_compute_pairlist_fingerprint_is_order_sensitive() -> None:
    first = compute_pairlist_fingerprint(("BTC/USDT:USDT", "ETH/USDT:USDT"), 3600)
    reordered = compute_pairlist_fingerprint(("ETH/USDT:USDT", "BTC/USDT:USDT"), 3600)
    assert first != reordered


def test_compute_audit_fingerprint_deterministic_and_content_sensitive() -> None:
    kwargs = dict(
        as_of_date="2026-07-21",
        universe_total=100,
        eligible_count=40,
        selected_count=30,
        rejected_count=10,
        selected_fingerprints=("f1", "f2"),
        rejected_fingerprints=("f3",),
        reason_code_summary={"RS_SCORE": 30, "OI_LIQUIDITY": 25},
    )
    assert compute_audit_fingerprint(**kwargs) == compute_audit_fingerprint(**kwargs)

    mutated = dict(kwargs)
    mutated["selected_count"] = 29
    assert compute_audit_fingerprint(**kwargs) != compute_audit_fingerprint(**mutated)
