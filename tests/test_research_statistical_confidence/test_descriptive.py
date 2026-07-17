"""Tests for the descriptive statistics module (MVP-67)."""

from __future__ import annotations

from decimal import Decimal

from hunter.research_statistical_confidence.descriptive import (
    _mad,
    _median,
    _quartiles,
    _std_dev,
    compute_metric_descriptive,
)


class TestMedian:
    def test_odd_count(self) -> None:
        assert _median([Decimal("1"), Decimal("3"), Decimal("5")]) == Decimal("3")

    def test_even_count(self) -> None:
        assert _median([Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")]) == Decimal("2.5")

    def test_single_value(self) -> None:
        assert _median([Decimal("7")]) == Decimal("7")

    def test_empty(self) -> None:
        assert _median([]) == Decimal("0")


class TestQuartiles:
    def test_basic(self) -> None:
        q1, q3 = _quartiles([Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")])
        # Even count: lower=[1,2], upper=[3,4], q1=1.5, q3=3.5
        assert q1 == Decimal("1.5")
        assert q3 == Decimal("3.5")

    def test_odd(self) -> None:
        q1, q3 = _quartiles([Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"), Decimal("5")])
        # Odd count: lower=[1,2,3], upper=[3,4,5], q1=2, q3=4
        assert q1 == Decimal("2")
        assert q3 == Decimal("4")

    def test_single(self) -> None:
        q1, q3 = _quartiles([Decimal("7")])
        assert q1 == Decimal("7")
        assert q3 == Decimal("7")

    def test_two_values(self) -> None:
        q1, q3 = _quartiles([Decimal("1"), Decimal("5")])
        assert q1 == Decimal("1")
        assert q3 == Decimal("5")


class TestMAD:
    def test_basic(self) -> None:
        # values: [1, 2, 3, 4, 100], median=3, abs devs=[2,1,0,1,97], MAD=1
        mad = _mad([Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"), Decimal("100")])
        assert mad == Decimal("1")

    def test_all_same(self) -> None:
        mad = _mad([Decimal("5"), Decimal("5"), Decimal("5")])
        assert mad == Decimal("0")


class TestStdDev:
    def test_basic(self) -> None:
        std = _std_dev([Decimal("2"), Decimal("4"), Decimal("4"), Decimal("4"), Decimal("5"), Decimal("5"), Decimal("7"), Decimal("9")])
        # Sample std dev approx 2.138
        assert std > Decimal("2")
        assert std < Decimal("2.2")

    def test_single_value(self) -> None:
        assert _std_dev([Decimal("5")]) == Decimal("0")

    def test_all_same(self) -> None:
        assert _std_dev([Decimal("3"), Decimal("3"), Decimal("3")]) == Decimal("0")


class TestComputeMetricDescriptive:
    def test_basic(self) -> None:
        deltas = [Decimal("1"), Decimal("2"), Decimal("3"), None, Decimal("5")]
        desc = compute_metric_descriptive(deltas)
        assert desc["available_count"] == 4
        assert desc["unavailable_count"] == 1
        assert desc["mean"] == Decimal("2.75")
        assert desc["median"] == Decimal("2.5")
        assert desc["min"] == Decimal("1")
        assert desc["max"] == Decimal("5")
        assert desc["q1"] == Decimal("1.5")
        assert desc["q3"] == Decimal("4")
        assert desc["iqr"] == Decimal("2.5")
        assert desc["positive_share"] == Decimal("1")
        assert desc["negative_share"] == Decimal("0")
        assert desc["zero_share"] == Decimal("0")

    def test_all_unavailable(self) -> None:
        desc = compute_metric_descriptive([None, None])
        assert desc["available_count"] == 0
        assert desc["unavailable_count"] == 2
        assert desc["mean"] is None
        assert desc["median"] is None
        assert desc["positive_share"] == Decimal("0")

    def test_mixed_signs(self) -> None:
        deltas = [Decimal("1"), Decimal("-1"), Decimal("0"), Decimal("2")]
        desc = compute_metric_descriptive(deltas)
        assert desc["available_count"] == 4
        assert desc["positive_share"] == Decimal("0.5")
        assert desc["negative_share"] == Decimal("0.25")
        assert desc["zero_share"] == Decimal("0.25")

    def test_empty_deltas(self) -> None:
        desc = compute_metric_descriptive([])
        assert desc["available_count"] == 0

    def test_std_dev_discrete(self) -> None:
        # Simple case: deltas [0, 1], mean=0.5, variance = ((0-0.5)^2+(1-0.5)^2)/(2-1) = 0.5
        from pytest import approx
        desc = compute_metric_descriptive([Decimal("0"), Decimal("1")])
        assert desc["std_dev"] is not None
        # sqrt(0.5) = 0.7071...
        assert float(desc["std_dev"]) == approx(0.70710678, rel=1e-6)

    def test_mad_example(self) -> None:
        # values [1, 1, 2, 2, 4, 6, 9], median=2
        # abs devs [1,1,0,0,2,4,7], sorted [0,0,1,1,2,4,7], median=1
        desc = compute_metric_descriptive([
            Decimal("1"), Decimal("1"), Decimal("2"),
            Decimal("2"), Decimal("4"), Decimal("6"), Decimal("9"),
        ])
        assert desc["mad"] == Decimal("1")
