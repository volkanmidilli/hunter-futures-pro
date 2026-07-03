"""Tests for hunter.experiment_ledger.models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from hunter.experiment_ledger import (
    BASELINE_MISSING,
    DUPLICATE_ID,
    EXPERIMENT_LEDGER_ADVISORY_REASON_CODES,
    EXPERIMENT_LEDGER_BLOCKING_REASON_CODES,
    EXPERIMENT_LEDGER_REASON_CODES,
    EXPERIMENT_LEDGER_VERSION,
    INVALID_METRICS,
    MISSING_REQUIRED_FIELDS,
    OK,
    UNSAFE_CONTENT,
    ExperimentComparisonConfig,
    ExperimentComparisonResult,
    ExperimentLedgerDataQuality,
    ExperimentLedgerInput,
    ExperimentLedgerReport,
    ExperimentLedgerSafetyFlags,
    ExperimentMetricSnapshot,
    ExperimentReasonCode,
    ExperimentRecord,
    ExperimentState,
    has_unsafe_experiment_ledger_content,
)


@pytest.fixture
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TestEnums:
    def test_experiment_state_values(self) -> None:
        assert ExperimentState.INCLUDED.value == "included"
        assert ExperimentState.EXCLUDED.value == "excluded"
        assert ExperimentState.BLOCKED.value == "blocked"
        assert ExperimentState.INSUFFICIENT_DATA.value == "insufficient_data"

    def test_experiment_reason_code_values(self) -> None:
        assert ExperimentReasonCode.OK.value == "OK"
        assert ExperimentReasonCode.BASELINE_MISSING.value == "BASELINE_MISSING"
        assert ExperimentReasonCode.DUPLICATE_ID.value == "DUPLICATE_ID"
        assert ExperimentReasonCode.UNSAFE_CONTENT.value == "UNSAFE_CONTENT"
        assert ExperimentReasonCode.INVALID_METRICS.value == "INVALID_METRICS"
        assert ExperimentReasonCode.MISSING_REQUIRED_FIELDS.value == "MISSING_REQUIRED_FIELDS"

    def test_reason_code_constants(self) -> None:
        assert OK == "OK"
        assert BASELINE_MISSING == "BASELINE_MISSING"
        assert DUPLICATE_ID == "DUPLICATE_ID"
        assert UNSAFE_CONTENT == "UNSAFE_CONTENT"
        assert INVALID_METRICS == "INVALID_METRICS"
        assert MISSING_REQUIRED_FIELDS == "MISSING_REQUIRED_FIELDS"
        assert all(code in EXPERIMENT_LEDGER_REASON_CODES for code in (
            OK, BASELINE_MISSING, DUPLICATE_ID, UNSAFE_CONTENT, INVALID_METRICS, MISSING_REQUIRED_FIELDS
        ))
        assert UNSAFE_CONTENT in EXPERIMENT_LEDGER_BLOCKING_REASON_CODES
        assert OK in EXPERIMENT_LEDGER_ADVISORY_REASON_CODES


class TestExperimentLedgerSafetyFlags:
    def test_default_is_safe(self) -> None:
        flags = ExperimentLedgerSafetyFlags()
        assert flags.is_safe is True

    def test_unsafe_content_breaks_is_safe(self) -> None:
        flags = ExperimentLedgerSafetyFlags(has_unsafe_content=True)
        assert flags.is_safe is False

    def test_blocked_record_breaks_is_safe(self) -> None:
        flags = ExperimentLedgerSafetyFlags(has_blocked_record=True)
        assert flags.is_safe is False

    def test_missing_baseline_breaks_is_safe(self) -> None:
        flags = ExperimentLedgerSafetyFlags(has_missing_baseline=True)
        assert flags.is_safe is False

    def test_positive_invariants_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="baseline safety invariants"):
            ExperimentLedgerSafetyFlags(no_network_connection=False)

    def test_build_safety_flags_helper(self) -> None:
        from hunter.experiment_ledger import build_experiment_ledger_safety_flags
        flags = build_experiment_ledger_safety_flags(has_blocked_record=True)
        assert flags.has_blocked_record is True
        assert flags.is_safe is False


class TestExperimentMetricSnapshot:
    def test_valid_snapshot(self, utcnow: datetime) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="exp-1",
            run_id="run-1",
            name="Experiment 1",
            metrics={"total_return_pct": 10.0},
            generated_at=utcnow,
        )
        assert snapshot.experiment_id == "exp-1"
        assert snapshot.run_id == "run-1"
        assert snapshot.name == "Experiment 1"
        assert isinstance(snapshot.metadata, MappingProxyType)

    def test_empty_experiment_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="experiment_id"):
            ExperimentMetricSnapshot(experiment_id="", run_id="run", name="Name", metrics={})

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="name"):
            ExperimentMetricSnapshot(experiment_id="exp", run_id="run", name="", metrics={})

    def test_naive_generated_at_rejected(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            ExperimentMetricSnapshot(
                experiment_id="exp",
                run_id="run",
                name="Name",
                metrics={},
                generated_at=datetime(2024, 1, 1),
            )

    def test_metadata_coerced_to_mapping_proxy(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="exp",
            run_id="run",
            name="Name",
            metrics={},
            metadata={"note": "hello"},
        )
        assert isinstance(snapshot.metadata, MappingProxyType)


class TestExperimentLedgerInput:
    def test_default_input(self) -> None:
        inp = ExperimentLedgerInput()
        assert inp.backtest_reports == ()
        assert inp.run_results == ()
        assert inp.metric_snapshots == ()
        assert isinstance(inp.metadata, MappingProxyType)

    def test_input_coerces_tuples(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="exp", run_id="run", name="Name", metrics={}
        )
        inp = ExperimentLedgerInput(
            backtest_reports=[],
            run_results=[],
            metric_snapshots=[snapshot],
        )
        assert isinstance(inp.metric_snapshots, tuple)

    def test_metadata_must_be_string_mapping(self) -> None:
        with pytest.raises(ValueError, match="mapping of strings"):
            ExperimentLedgerInput(metadata={"note": 123})  # type: ignore[dict-item]


class TestExperimentRecord:
    def test_valid_record(self, utcnow: datetime) -> None:
        record = ExperimentRecord(
            experiment_id="exp-1",
            source_kind="backtest",
            run_id="run-1",
            name="Name",
            state=ExperimentState.INCLUDED,
            reason_codes=(OK,),
            metrics={"total_return_pct": 10.0},
            generated_at=utcnow,
            tags=(),
            metadata={},
            notes=(),
        )
        assert record.state is ExperimentState.INCLUDED

    def test_blocked_record_requires_reason_codes(self, utcnow: datetime) -> None:
        with pytest.raises(ValueError, match="BLOCKED records must have reason_codes"):
            ExperimentRecord(
                experiment_id="exp",
                source_kind="backtest",
                run_id="run",
                name="Name",
                state=ExperimentState.BLOCKED,
                reason_codes=(),
                metrics={},
                generated_at=utcnow,
                tags=(),
                metadata={},
                notes=(),
            )

    def test_unsupported_reason_code_rejected(self, utcnow: datetime) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            ExperimentRecord(
                experiment_id="exp",
                source_kind="backtest",
                run_id="run",
                name="Name",
                state=ExperimentState.INCLUDED,
                reason_codes=("INVALID_CODE",),
                metrics={},
                generated_at=utcnow,
                tags=(),
                metadata={},
                notes=(),
            )

    def test_blocked_factory(self, utcnow: datetime) -> None:
        record = ExperimentRecord.blocked(
            experiment_id="exp",
            run_id="run",
            name="Name",
            source_kind="backtest",
            generated_at=utcnow,
        )
        assert record.state is ExperimentState.BLOCKED
        assert MISSING_REQUIRED_FIELDS in record.reason_codes

    def test_frozen_record_cannot_be_modified(self, utcnow: datetime) -> None:
        record = ExperimentRecord(
            experiment_id="exp",
            source_kind="backtest",
            run_id="run",
            name="Name",
            state=ExperimentState.INCLUDED,
            reason_codes=(OK,),
            metrics={},
            generated_at=utcnow,
            tags=(),
            metadata={},
            notes=(),
        )
        with pytest.raises(FrozenInstanceError):
            record.name = "New Name"  # type: ignore[misc]


class TestExperimentComparisonConfig:
    def test_default_config(self) -> None:
        config = ExperimentComparisonConfig()
        assert config.baseline_experiment_id is None
        assert config.include_blocked is True
        assert config.include_insufficient is True
        assert config.primary_metric == "total_return_pct"

    def test_empty_baseline_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="baseline_experiment_id"):
            ExperimentComparisonConfig(baseline_experiment_id="")

    def test_empty_primary_metric_rejected(self) -> None:
        with pytest.raises(ValueError, match="primary_metric"):
            ExperimentComparisonConfig(primary_metric="")

    def test_include_flags_must_be_bool(self) -> None:
        with pytest.raises(ValueError, match="include_blocked"):
            ExperimentComparisonConfig(include_blocked="yes")  # type: ignore[arg-type]


class TestExperimentComparisonResult:
    def test_valid_result(self, utcnow: datetime) -> None:
        config = ExperimentComparisonConfig()
        record = ExperimentRecord(
            experiment_id="exp",
            source_kind="backtest",
            run_id="run",
            name="Name",
            state=ExperimentState.INCLUDED,
            reason_codes=(OK,),
            metrics={"total_return_pct": 10.0},
            generated_at=utcnow,
            tags=(),
            metadata={},
            notes=(),
        )
        result = ExperimentComparisonResult(
            config=config,
            records=(record,),
            ranked_records=(record,),
            baseline_record=None,
            deltas={},
            summary_metrics={},
            reason_codes=(),
            notes=(),
        )
        assert result.records == (record,)


class TestExperimentLedgerDataQuality:
    def test_valid_data_quality(self) -> None:
        dq = ExperimentLedgerDataQuality(
            total_inputs=3,
            normalized_records=3,
            blocked_records=1,
            insufficient_records=0,
            excluded_records=0,
            included_records=2,
            sections_present=("backtest",),
            sections_expected=("backtest", "run", "metric_snapshot"),
            notes=(),
        )
        assert dq.total_inputs == 3

    def test_normalized_records_cannot_exceed_total(self) -> None:
        with pytest.raises(ValueError, match="normalized_records"):
            ExperimentLedgerDataQuality(
                total_inputs=1,
                normalized_records=2,
                blocked_records=0,
                insufficient_records=0,
                excluded_records=0,
                included_records=0,
                sections_present=(),
                sections_expected=(),
                notes=(),
            )

    def test_state_counts_cannot_exceed_normalized(self) -> None:
        with pytest.raises(ValueError, match="state counts"):
            ExperimentLedgerDataQuality(
                total_inputs=1,
                normalized_records=1,
                blocked_records=1,
                insufficient_records=1,
                excluded_records=0,
                included_records=0,
                sections_present=(),
                sections_expected=(),
                notes=(),
            )


class TestExperimentLedgerReport:
    def test_valid_report(self, utcnow: datetime) -> None:
        inp = ExperimentLedgerInput()
        config = ExperimentComparisonConfig()
        record = ExperimentRecord(
            experiment_id="exp",
            source_kind="backtest",
            run_id="run",
            name="Name",
            state=ExperimentState.INCLUDED,
            reason_codes=(OK,),
            metrics={"total_return_pct": 10.0},
            generated_at=utcnow,
            tags=(),
            metadata={},
            notes=(),
        )
        comparison = ExperimentComparisonResult(
            config=config,
            records=(record,),
            ranked_records=(record,),
            baseline_record=None,
            deltas={},
            summary_metrics={},
            reason_codes=(),
            notes=(),
        )
        data_quality = ExperimentLedgerDataQuality(
            total_inputs=1,
            normalized_records=1,
            blocked_records=0,
            insufficient_records=0,
            excluded_records=0,
            included_records=1,
            sections_present=("backtest",),
            sections_expected=("backtest", "run", "metric_snapshot"),
            notes=(),
        )
        safety_flags = ExperimentLedgerSafetyFlags()
        report = ExperimentLedgerReport(
            report_id="r1",
            version=EXPERIMENT_LEDGER_VERSION,
            generated_at=utcnow,
            input=inp,
            comparison=comparison,
            data_quality=data_quality,
            safety_flags=safety_flags,
            reason_codes=(OK,),
            metadata={},
            notes=(),
        )
        assert report.version == EXPERIMENT_LEDGER_VERSION

    def test_blocked_report_factory(self, utcnow: datetime) -> None:
        inp = ExperimentLedgerInput()
        report = ExperimentLedgerReport.blocked(input=inp, reason_code=UNSAFE_CONTENT)
        assert report.reason_codes == (UNSAFE_CONTENT,)
        assert report.safety_flags.has_unsafe_content is True

    def test_unsupported_reason_code_rejected(self, utcnow: datetime) -> None:
        inp = ExperimentLedgerInput()
        with pytest.raises(ValueError, match="unsupported reason code"):
            ExperimentLedgerReport.blocked(input=inp, reason_code="INVALID_CODE")


class TestUnsafeContentDetection:
    def test_detects_trading_term(self) -> None:
        assert has_unsafe_experiment_ledger_content(text="buy_signal") is True

    def test_detects_exchange_term(self) -> None:
        assert has_unsafe_experiment_ledger_content(text="binance_api") is True

    def test_detects_metadata_term(self) -> None:
        assert has_unsafe_experiment_ledger_content(metadata={"note": "place order now"}) is True

    def test_detects_tag_term(self) -> None:
        assert has_unsafe_experiment_ledger_content(tags=["leverage_10x"]) is True

    def test_safe_content_returns_false(self) -> None:
        assert has_unsafe_experiment_ledger_content(text="research_audit") is False

    def test_custom_forbidden_terms(self) -> None:
        assert has_unsafe_experiment_ledger_content(
            text="xyz", forbidden_terms=frozenset({"xyz"})
        ) is True

    def test_empty_text_is_safe(self) -> None:
        assert has_unsafe_experiment_ledger_content(text="") is False

    def test_none_text_is_safe(self) -> None:
        assert has_unsafe_experiment_ledger_content(text=None) is False
