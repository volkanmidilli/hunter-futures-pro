"""Tests for evidence ledger validator (MVP-68)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.research_evidence_ledger.models import (
    EvidenceLedgerSafetyFlags,
    ExperimentRegistration,
    IndependenceClass,
)
from hunter.research_evidence_ledger.validator import (
    validate_raw_value,
    validate_registration,
    validate_safety_flags,
)
from hunter.research_evidence_ledger.errors import (
    EvidenceLedgerRegistrationError,
    EvidenceLedgerSafetyError,
    EvidenceLedgerValidationError,
)


class TestValidateRegistration:
    def test_valid_registration(self) -> None:
        reg = ExperimentRegistration(
            experiment_id="e1",
            hypothesis="test hypothesis",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp1",
            metric_family=("m1", "m2"),
            independence=IndependenceClass.INDEPENDENT,
        )
        # Should not raise
        validate_registration(reg)

    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(EvidenceLedgerRegistrationError):
            validate_registration("not a registration")  # type: ignore[arg-type]

    def test_empty_hypothesis_rejected(self) -> None:
        with pytest.raises(ValueError):
            ExperimentRegistration(
                experiment_id="e1",
                hypothesis="   ",
                strategy_name="s1",
                universe_plan="u1",
                timeframe="1h",
                walk_forward_plan_fingerprint="fp1",
                metric_family=("m1",),
                independence=IndependenceClass.INDEPENDENT,
            )

    def test_empty_metric_family_rejected(self) -> None:
        with pytest.raises(ValueError):
            ExperimentRegistration(
                experiment_id="e1",
                hypothesis="test",
                strategy_name="s1",
                universe_plan="u1",
                timeframe="1h",
                walk_forward_plan_fingerprint="fp1",
                metric_family=(),
                independence=IndependenceClass.INDEPENDENT,
            )


class TestValidateSafetyFlags:
    def test_valid(self) -> None:
        flags = EvidenceLedgerSafetyFlags()
        validate_safety_flags(flags)

    def test_invalid_type(self) -> None:
        with pytest.raises(EvidenceLedgerSafetyError):
            validate_safety_flags("not flags")  # type: ignore[arg-type]

    def test_research_only_false(self) -> None:
        with pytest.raises(ValueError):
            EvidenceLedgerSafetyFlags(research_only=False)

    def test_execution_approval_true(self) -> None:
        with pytest.raises(ValueError):
            EvidenceLedgerSafetyFlags(execution_approval_granted=True)


class TestValidateRawValue:
    def test_none_is_valid(self) -> None:
        validate_raw_value(None)

    def test_zero_is_valid(self) -> None:
        validate_raw_value(0)

    def test_one_is_valid(self) -> None:
        validate_raw_value(1)

    def test_value_in_range(self) -> None:
        validate_raw_value(0.05)
        validate_raw_value(0.5)
        validate_raw_value(0.99)

    def test_negative_rejected(self) -> None:
        with pytest.raises(EvidenceLedgerValidationError):
            validate_raw_value(-0.1)

    def test_above_one_rejected(self) -> None:
        with pytest.raises(EvidenceLedgerValidationError):
            validate_raw_value(1.5)
