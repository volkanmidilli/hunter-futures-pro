"""Safety contract tests for evidence ledger (MVP-68)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.research_evidence_ledger.models import (
    EvidenceLedgerError,
    EvidenceLedgerManifest,
    EvidenceLedgerReport,
    EvidenceLedgerSafetyError,
    EvidenceLedgerSafetyFlags,
    EvidenceLedgerSnapshotError,
    EvidenceLedgerValidationError,
    EvidenceLedgerWriterError,
    ExperimentRegistration,
    IndependenceClass,
    LedgerSnapshot,
)
from hunter.research_evidence_ledger.validator import validate_safety_flags


class TestSafetyFlags:
    def test_defaults_are_safe(self) -> None:
        flags = EvidenceLedgerSafetyFlags()
        assert flags.research_only is True
        assert flags.execution_approval_granted is False
        assert flags.production_approval_granted is False
        assert flags.live_trading_allowed is False
        assert flags.automatic_execution_allowed is False
        assert flags.human_approval_required is True
        assert flags.no_direct_subprocess is True
        assert flags.no_network_connection is True
        assert flags.no_database_connection is True
        assert flags.no_exchange_connection is True
        assert flags.no_remote_changes is True
        assert flags.no_action_commands_emitted is True
        assert flags.no_strategy_mutation is True
        assert flags.no_universe_mutation is True
        assert flags.no_config_mutation is True

    def test_research_only_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="research_only must be True"):
            EvidenceLedgerSafetyFlags(research_only=False)

    def test_execution_approval_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="execution_approval_granted must be False"):
            EvidenceLedgerSafetyFlags(execution_approval_granted=True)

    def test_production_approval_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="production_approval_granted must be False"):
            EvidenceLedgerSafetyFlags(production_approval_granted=True)

    def test_live_trading_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="live_trading_allowed must be False"):
            EvidenceLedgerSafetyFlags(live_trading_allowed=True)

    def test_automatic_execution_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="automatic_execution_allowed must be False"):
            EvidenceLedgerSafetyFlags(automatic_execution_allowed=True)

    def test_human_approval_required_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="human_approval_required must be True"):
            EvidenceLedgerSafetyFlags(human_approval_required=False)

    def test_no_strategy_mutation_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="no_strategy_mutation must be True"):
            EvidenceLedgerSafetyFlags(no_strategy_mutation=False)

    def test_no_universe_mutation_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="no_universe_mutation must be True"):
            EvidenceLedgerSafetyFlags(no_universe_mutation=False)

    def test_no_config_mutation_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="no_config_mutation must be True"):
            EvidenceLedgerSafetyFlags(no_config_mutation=False)

    def test_no_direct_subprocess_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="no_direct_subprocess must be True"):
            EvidenceLedgerSafetyFlags(no_direct_subprocess=False)


class TestSafetyValidation:
    def test_valid_flags_pass(self) -> None:
        validate_safety_flags(EvidenceLedgerSafetyFlags())

    def test_invalid_flags_raise(self) -> None:
        with pytest.raises(ValueError):
            EvidenceLedgerSafetyFlags(research_only=False)


class TestErrorTypes:
    def test_error_base(self) -> None:
        err = EvidenceLedgerError("test error")
        assert str(err) == "test error"
        assert err.reason_code is None

    def test_error_with_reason_code(self) -> None:
        err = EvidenceLedgerError("test error", reason_code="SOME_CODE")
        assert err.reason_code == "SOME_CODE"

    def test_safety_error(self) -> None:
        err = EvidenceLedgerSafetyError("unsafe")
        assert isinstance(err, EvidenceLedgerError)

    def test_validation_error(self) -> None:
        err = EvidenceLedgerValidationError("invalid")
        assert isinstance(err, EvidenceLedgerError)

    def test_writer_error(self) -> None:
        err = EvidenceLedgerWriterError("write failed")
        assert isinstance(err, EvidenceLedgerError)

    def test_snapshot_error(self) -> None:
        err = EvidenceLedgerSnapshotError("snap failed")
        assert isinstance(err, EvidenceLedgerError)


class TestResearchOnlyArtifacts:
    def test_report_research_only(self) -> None:
        """All EvidenceLedgerReport instances must have research_only=True."""
        flags = EvidenceLedgerSafetyFlags()
        reg = ExperimentRegistration(
            experiment_id="e1",
            hypothesis="test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
        )
        snap = LedgerSnapshot(
            version="0.68.0-dev",
            spec_version="SPEC-069",
            snapshot_id="snap_001",
            previous_snapshot_fingerprint="",
            entry_fingerprints=(),
            family_fingerprints=(),
            adjustment_fingerprints=(),
            replication_fingerprints=(),
        )
        object.__setattr__(snap, "fingerprint", "snap_fp")
        manifest = EvidenceLedgerManifest(
            version="1.0",
            spec_version="SPEC-069",
            evidence_ledger_version="0.68.0-dev",
            generated_at=datetime.now(timezone.utc),
            entry_count=0,
            family_count=0,
            adjustment_count=0,
            replication_count=0,
            snapshot_fingerprint="snap_fp",
            overall_fingerprint="overall_fp",
            safety_flags=flags,
        )
        report = EvidenceLedgerReport(
            version="1.0",
            spec_version="SPEC-069",
            evidence_ledger_version="0.68.0-dev",
            registrations=(reg,),
            entries=(),
            hypothesis_families=(),
            experiment_families=(),
            metric_families=(),
            adjustments=(),
            replications=(),
            snapshot=snap,
            manifest=manifest,
            safety_flags=flags,
            fingerprint="report_fp",
        )
        assert report.research_only is True
        assert report.human_approval_required is True

    def test_manifest_safety_flags(self) -> None:
        flags = EvidenceLedgerSafetyFlags()
        manifest = EvidenceLedgerManifest(
            version="1.0",
            spec_version="SPEC-069",
            evidence_ledger_version="0.68.0-dev",
            generated_at=datetime.now(timezone.utc),
            entry_count=0,
            family_count=0,
            adjustment_count=0,
            replication_count=0,
            snapshot_fingerprint="snap_fp",
            overall_fingerprint="overall_fp",
            safety_flags=flags,
        )
        assert manifest.safety_flags.research_only is True
