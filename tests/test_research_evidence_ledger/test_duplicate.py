"""Tests for evidence ledger duplicate detection (MVP-68)."""

from __future__ import annotations

import pytest

from hunter.research_evidence_ledger.duplicate import DuplicateDetector
from hunter.research_evidence_ledger.models import (
    DUPLICATE_ID,
    DUPLICATE_FINGERPRINT,
    REPEATED_HYPOTHESIS,
    EvidenceLedgerDuplicateError,
    EvidenceLedgerEntry,
    ExperimentEvidence,
    ExperimentRegistration,
    ExperimentStatus,
    IndependenceClass,
)
from hunter.research_evidence_ledger.registration import create_registration


def _make_reg(
    experiment_id: str,
    hypothesis: str = "test hypothesis",
    fingerprint: str = "",
) -> ExperimentRegistration:
    reg = ExperimentRegistration(
        experiment_id=experiment_id,
        hypothesis=hypothesis,
        strategy_name="s1",
        universe_plan="u1",
        timeframe="1h",
        walk_forward_plan_fingerprint="fp",
        metric_family=("m1",),
        independence=IndependenceClass.INDEPENDENT,
        fingerprint=fingerprint,
    )
    if not fingerprint:
        # Assign a unique fingerprint
        object.__setattr__(reg, "fingerprint", f"fp_{experiment_id}")
    return reg


def _make_entry(reg: ExperimentRegistration) -> EvidenceLedgerEntry:
    ev = ExperimentEvidence(
        experiment_id=reg.experiment_id,
        evidence_fingerprint=f"ev_fp_{reg.experiment_id}",
    )
    return EvidenceLedgerEntry(
        registration=reg,
        evidence=ev,
        status=ExperimentStatus.REGISTERED,
        fingerprint=f"entry_fp_{reg.experiment_id}",
    )


class TestDuplicateDetector:
    def test_no_duplicate_on_first_registration(self) -> None:
        detector = DuplicateDetector()
        reg = _make_reg("exp_001")
        detector.check_all(reg)
        detector.register_all(reg)

    def test_duplicate_id_raises(self) -> None:
        detector = DuplicateDetector()
        reg1 = _make_reg("exp_001")
        detector.check_all(reg1)
        detector.register_all(reg1)

        reg2 = _make_reg("exp_001", hypothesis="different hypothesis")
        with pytest.raises(EvidenceLedgerDuplicateError) as exc:
            detector.check_all(reg2)
        assert exc.value.reason_code == DUPLICATE_ID

    def test_duplicate_fingerprint_raises(self) -> None:
        detector = DuplicateDetector()
        reg1 = _make_reg("exp_001", fingerprint="same_fp")
        detector.check_all(reg1)
        detector.register_all(reg1)

        reg2 = _make_reg("exp_002", fingerprint="same_fp")
        with pytest.raises(EvidenceLedgerDuplicateError) as exc:
            detector.check_all(reg2)
        assert exc.value.reason_code == DUPLICATE_FINGERPRINT

    def test_duplicate_hypothesis_raises(self) -> None:
        detector = DuplicateDetector()
        reg1 = _make_reg("exp_001", hypothesis="Same hypothesis")
        detector.check_all(reg1)
        detector.register_all(reg1)

        reg2 = _make_reg("exp_002", hypothesis="Same hypothesis")
        with pytest.raises(EvidenceLedgerDuplicateError) as exc:
            detector.check_all(reg2)
        assert exc.value.reason_code == REPEATED_HYPOTHESIS

    def test_duplicate_evidence_fingerprint_raises(self) -> None:
        detector = DuplicateDetector()
        reg1 = _make_reg("exp_001")
        entry1 = _make_entry(reg1)
        detector.check_all(reg1)
        detector.register_all(reg1)
        detector.register_evidence(entry1)

        reg2 = _make_reg("exp_002", hypothesis="different hypothesis")
        entry2 = EvidenceLedgerEntry(
            registration=reg2,
            evidence=ExperimentEvidence(
                experiment_id="exp_002",
                evidence_fingerprint=f"ev_fp_exp_001",  # Same as entry1
            ),
            status=ExperimentStatus.REGISTERED,
            fingerprint="entry_fp_exp_002",
        )
        with pytest.raises(EvidenceLedgerDuplicateError):
            detector.check_duplicate_evidence(entry2)

    def test_no_duplicate_on_different_hypotheses(self) -> None:
        detector = DuplicateDetector()
        reg1 = _make_reg("exp_001", hypothesis="Hypothesis A")
        detector.check_all(reg1)
        detector.register_all(reg1)

        reg2 = _make_reg("exp_002", hypothesis="Hypothesis B")
        detector.check_all(reg2)
        detector.register_all(reg2)

    def test_check_all_runs_all_checks(self) -> None:
        detector = DuplicateDetector()
        reg = _make_reg("exp_001")
        detector.check_all(reg)
        detector.register_all(reg)

        # Duplicate ID should be caught by check_all
        dup = _make_reg("exp_001", hypothesis="different")
        with pytest.raises(EvidenceLedgerDuplicateError):
            detector.check_all(dup)
