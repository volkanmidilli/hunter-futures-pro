"""Tests for research evidence ledger models (MVP-68)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.research_evidence_ledger.models import (
    EVIDENCE_LEDGER_REASON_CODES,
    EVIDENCE_LEDGER_VERSION,
    SPEC_VERSION,
    UNAVAILABLE,
    AdjustedEvidence,
    AdjustmentConfig,
    AdjustmentMethod,
    EvidenceLedgerEntry,
    EvidenceLedgerManifest,
    EvidenceLedgerReport,
    EvidenceLedgerSafetyFlags,
    ExperimentEvidence,
    ExperimentFamily,
    ExperimentRegistration,
    ExperimentStatus,
    HypothesisFamily,
    IndependenceClass,
    LedgerSnapshot,
    MetricFamily,
    ReplicationResult,
    ReplicationState,
)


class TestVersionConstants:
    def test_version_constants(self) -> None:
        assert EVIDENCE_LEDGER_VERSION == "0.68.0-dev"
        assert SPEC_VERSION == "SPEC-069"
        assert UNAVAILABLE == "UNAVAILABLE"
        assert isinstance(EVIDENCE_LEDGER_REASON_CODES, frozenset)
        assert len(EVIDENCE_LEDGER_REASON_CODES) > 0


class TestEvidenceLedgerSafetyFlags:
    def test_defaults(self) -> None:
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

    def test_research_only_mutation_rejected(self) -> None:
        with pytest.raises(ValueError):
            EvidenceLedgerSafetyFlags(research_only=False)

    def test_human_approval_required_mutation_rejected(self) -> None:
        with pytest.raises(ValueError):
            EvidenceLedgerSafetyFlags(human_approval_required=False)

    def test_execution_approval_rejected(self) -> None:
        with pytest.raises(ValueError):
            EvidenceLedgerSafetyFlags(execution_approval_granted=True)

    def test_live_trading_allowed_rejected(self) -> None:
        with pytest.raises(ValueError):
            EvidenceLedgerSafetyFlags(live_trading_allowed=True)

    def test_non_bool_rejected(self) -> None:
        with pytest.raises(ValueError):
            EvidenceLedgerSafetyFlags(research_only="yes")

    def test_immutable(self) -> None:
        flags = EvidenceLedgerSafetyFlags()
        with pytest.raises(AttributeError):
            flags.research_only = False


class TestExperimentStatus:
    def test_all_statuses_present(self) -> None:
        values = [s.value for s in ExperimentStatus]
        assert "REGISTERED" in values
        assert "EXECUTED" in values
        assert "FAILED" in values
        assert "BLOCKED" in values
        assert "TIMED_OUT" in values
        assert "INSUFFICIENT_EVIDENCE" in values
        assert "COMPLETED" in values
        assert "WITHDRAWN" in values
        assert len(values) == 8


class TestIndependenceClass:
    def test_all(self) -> None:
        values = [c.value for c in IndependenceClass]
        assert "INDEPENDENT" in values
        assert "RELATED" in values
        assert "DERIVED" in values
        assert "DUPLICATE" in values
        assert "UNKNOWN" in values
        assert len(values) == 5


class TestAdjustmentMethod:
    def test_all(self) -> None:
        values = [m.value for m in AdjustmentMethod]
        assert "BENJAMINI_HOCHBERG" in values
        assert "BONFERRONI" in values
        assert len(values) == 2


class TestReplicationState:
    def test_all(self) -> None:
        values = [s.value for s in ReplicationState]
        assert "NOT_REPLICATED" in values
        assert "PARTIALLY_REPLICATED" in values
        assert "REPLICATED_CANDIDATE" in values
        assert "REPLICATED_BASELINE" in values
        assert "CONFLICTING" in values
        assert "INSUFFICIENT_EVIDENCE" in values
        assert len(values) == 6


class TestExperimentRegistration:
    def test_minimal(self) -> None:
        reg = ExperimentRegistration(
            experiment_id="exp_001",
            hypothesis="Strategy X outperforms buy-and-hold",
            strategy_name="strategy_x",
            universe_plan="top_100_crypto",
            timeframe="1h",
            walk_forward_plan_fingerprint="abc123",
            metric_family=("sharpe_ratio", "sortino_ratio"),
            independence=IndependenceClass.INDEPENDENT,
        )
        assert reg.experiment_id == "exp_001"
        assert reg.status == ExperimentStatus.REGISTERED
        assert reg.fingerprint == ""

    def test_empty_experiment_id_rejected(self) -> None:
        with pytest.raises(ValueError):
            ExperimentRegistration(
                experiment_id="",
                hypothesis="test",
                strategy_name="s",
                universe_plan="u",
                timeframe="1h",
                walk_forward_plan_fingerprint="fp",
                metric_family=("m1",),
                independence=IndependenceClass.INDEPENDENT,
            )

    def test_empty_hypothesis_rejected(self) -> None:
        with pytest.raises(ValueError):
            ExperimentRegistration(
                experiment_id="e1",
                hypothesis="",
                strategy_name="s",
                universe_plan="u",
                timeframe="1h",
                walk_forward_plan_fingerprint="fp",
                metric_family=("m1",),
                independence=IndependenceClass.INDEPENDENT,
            )

    def test_empty_metric_family_rejected(self) -> None:
        with pytest.raises(ValueError):
            ExperimentRegistration(
                experiment_id="e1",
                hypothesis="test",
                strategy_name="s",
                universe_plan="u",
                timeframe="1h",
                walk_forward_plan_fingerprint="fp",
                metric_family=(),
                independence=IndependenceClass.INDEPENDENT,
            )

    def test_invalid_independence_rejected(self) -> None:
        with pytest.raises(ValueError):
            ExperimentRegistration(
                experiment_id="e1",
                hypothesis="test",
                strategy_name="s",
                universe_plan="u",
                timeframe="1h",
                walk_forward_plan_fingerprint="fp",
                metric_family=("m1",),
                independence="INVALID",  # type: ignore[arg-type]
            )

    def test_immutable(self) -> None:
        reg = ExperimentRegistration(
            experiment_id="e1",
            hypothesis="test",
            strategy_name="s",
            universe_plan="u",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
        )
        with pytest.raises(AttributeError):
            reg.experiment_id = "e2"


class TestExperimentEvidence:
    def test_minimal(self) -> None:
        ev = ExperimentEvidence(experiment_id="exp_001")
        assert ev.experiment_id == "exp_001"
        assert ev.walk_forward_report is None
        assert ev.confidence_report is None
        assert ev.evidence_fingerprint == ""

    def test_empty_id_rejected(self) -> None:
        with pytest.raises(ValueError):
            ExperimentEvidence(experiment_id="")


class TestEvidenceLedgerEntry:
    def test_minimal(self) -> None:
        reg = ExperimentRegistration(
            experiment_id="e1",
            hypothesis="test",
            strategy_name="s",
            universe_plan="u",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
        )
        entry = EvidenceLedgerEntry(registration=reg, status=ExperimentStatus.REGISTERED)
        assert entry.registration.experiment_id == "e1"
        assert entry.evidence is None
        assert entry.status == ExperimentStatus.REGISTERED

    def test_invalid_registration_rejected(self) -> None:
        with pytest.raises(ValueError):
            EvidenceLedgerEntry(registration="invalid", status=ExperimentStatus.REGISTERED)  # type: ignore[arg-type]


class TestHypothesisFamily:
    def test_minimal(self) -> None:
        family = HypothesisFamily(
            hypothesis_family_id="hf_001",
            hypothesis="test hypothesis",
            experiment_ids=("e1", "e2"),
            metric_names=("m1", "m2"),
        )
        assert family.hypothesis_family_id == "hf_001"

    def test_empty_id_rejected(self) -> None:
        with pytest.raises(ValueError):
            HypothesisFamily(
                hypothesis_family_id="",
                hypothesis="h",
                experiment_ids=("e1",),
                metric_names=("m1",),
            )


class TestExperimentFamily:
    def test_minimal(self) -> None:
        family = ExperimentFamily(
            experiment_family_id="ef_001",
            strategy_name="strat_a",
            universe_plan="top_100",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp123",
            experiment_ids=("e1", "e2"),
            metric_names=("m1",),
        )
        assert family.experiment_family_id == "ef_001"


class TestMetricFamily:
    def test_minimal(self) -> None:
        family = MetricFamily(metric_names=("m1", "m2"))
        assert family.metric_names == ("m1", "m2")

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValueError):
            MetricFamily(metric_names=())


class TestAdjustmentConfig:
    def test_valid(self) -> None:
        config = AdjustmentConfig(
            method=AdjustmentMethod.BENJAMINI_HOCHBERG,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        assert config.method == AdjustmentMethod.BENJAMINI_HOCHBERG
        assert config.alpha == Decimal("0.05")

    def test_invalid_alpha_zero(self) -> None:
        with pytest.raises(ValueError):
            AdjustmentConfig(
                method=AdjustmentMethod.BENJAMINI_HOCHBERG,
                alpha=Decimal("0"),
                family_id="f",
                family_type="hypothesis",
            )

    def test_invalid_alpha_above_one(self) -> None:
        with pytest.raises(ValueError):
            AdjustmentConfig(
                method=AdjustmentMethod.BENJAMINI_HOCHBERG,
                alpha=Decimal("1.5"),
                family_id="f",
                family_type="hypothesis",
            )

    def test_invalid_family_type(self) -> None:
        with pytest.raises(ValueError):
            AdjustmentConfig(
                method=AdjustmentMethod.BENJAMINI_HOCHBERG,
                alpha=Decimal("0.05"),
                family_id="f",
                family_type="invalid",
            )


class TestAdjustedEvidence:
    def test_valid(self) -> None:
        adj = AdjustedEvidence(
            experiment_id="e1",
            metric_name="sharpe_ratio",
            raw_value=Decimal("0.03"),
            adjusted_value=Decimal("0.06"),
            family_id="fam_001",
            family_type="hypothesis",
            method=AdjustmentMethod.BENJAMINI_HOCHBERG,
            rank=1,
            family_size=5,
            alpha=Decimal("0.05"),
        )
        assert adj.experiment_id == "e1"
        assert adj.raw_value == Decimal("0.03")
        assert adj.adjusted_value == Decimal("0.06")

    def test_rank_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            AdjustedEvidence(
                experiment_id="e1",
                metric_name="m",
                raw_value=Decimal("0.05"),
                adjusted_value=Decimal("0.05"),
                family_id="f",
                family_type="hypothesis",
                method=AdjustmentMethod.BENJAMINI_HOCHBERG,
                rank=0,
                family_size=5,
                alpha=Decimal("0.05"),
            )


class TestReplicationResult:
    def test_valid(self) -> None:
        result = ReplicationResult(
            experiment_id="e1",
            metric_name="sharpe_ratio",
            family_id="fam_001",
            family_type="hypothesis",
            state=ReplicationState.NOT_REPLICATED,
            candidate_count=0,
            baseline_count=0,
            independent_count=1,
            direction=None,
        )
        assert result.experiment_id == "e1"
        assert result.state == ReplicationState.NOT_REPLICATED


class TestLedgerSnapshot:
    def test_minimal(self) -> None:
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
        assert snap.snapshot_id == "snap_001"


class TestEvidenceLedgerManifest:
    def test_valid(self) -> None:
        from datetime import datetime, timezone
        manifest = EvidenceLedgerManifest(
            version="1.0",
            spec_version="SPEC-069",
            evidence_ledger_version="0.68.0-dev",
            generated_at=datetime.now(timezone.utc),
            entry_count=5,
            family_count=3,
            adjustment_count=2,
            replication_count=2,
            snapshot_fingerprint="snap_fp",
            overall_fingerprint="overall_fp",
            safety_flags=EvidenceLedgerSafetyFlags(),
        )
        assert manifest.entry_count == 5


class TestEvidenceLedgerReport:
    def test_valid(self) -> None:
        from datetime import datetime, timezone
        flags = EvidenceLedgerSafetyFlags()
        reg = ExperimentRegistration(
            experiment_id="e1",
            hypothesis="test",
            strategy_name="s",
            universe_plan="u",
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
        assert report.fingerprint == "report_fp"
        assert report.research_only is True
        assert report.human_approval_required is True
