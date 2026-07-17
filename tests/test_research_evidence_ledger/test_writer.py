"""Tests for evidence ledger writer (MVP-68)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from hunter.research_evidence_ledger.models import (
    EVIDENCE_LEDGER_VERSION,
    SPEC_VERSION,
    EvidenceLedgerSafetyFlags,
    ExperimentRegistration,
    IndependenceClass,
    LedgerSnapshot,
)
from hunter.research_evidence_ledger.writer import (
    EvidenceLedgerWriter,
    write_all_evidence_ledger_artifacts,
    _validate_output_dir,
)
from hunter.research_evidence_ledger.errors import EvidenceLedgerWriterError


class TestValidateOutputDir:
    def test_valid_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _validate_output_dir(tmp)
            assert path is not None

    def test_rejects_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data" / "test"
            data_dir.mkdir(parents=True)
            with pytest.raises(EvidenceLedgerWriterError):
                _validate_output_dir(str(data_dir))

    def test_rejects_reports_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports_dir = Path(tmp) / "reports" / "test"
            reports_dir.mkdir(parents=True)
            with pytest.raises(EvidenceLedgerWriterError):
                _validate_output_dir(str(reports_dir))


class TestEvidenceLedgerWriter:
    def test_init_creates_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "ledger_output"
            writer = EvidenceLedgerWriter(str(output_dir))
            assert output_dir.exists()
            assert writer.output_dir == output_dir.resolve()

    def test_write_registrations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            writer = EvidenceLedgerWriter(tmp)
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
            path = writer.write_registrations((reg,))
            assert path.exists()
            assert path.name == "experiment_registrations.json"

    def test_write_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            writer = EvidenceLedgerWriter(tmp)
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
            from hunter.research_evidence_ledger.models import EvidenceLedgerEntry, ExperimentStatus
            entry = EvidenceLedgerEntry(
                registration=reg,
                evidence=None,
                status=ExperimentStatus.REGISTERED,
            )
            path = writer.write_entries((entry,))
            assert path.exists()
            assert path.name == "evidence_ledger_entries.json"

    def test_write_report_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            writer = EvidenceLedgerWriter(tmp)
            from datetime import datetime, timezone
            from hunter.research_evidence_ledger.models import (
                EvidenceLedgerManifest,
                EvidenceLedgerReport,
                EvidenceLedgerEntry,
                ExperimentStatus,
            )
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
            path = writer.write_report_markdown(report)
            assert path.exists()
            assert path.name == "evidence_ledger_report.md"

    def test_write_all_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            from datetime import datetime, timezone
            from hunter.research_evidence_ledger.models import (
                EvidenceLedgerManifest,
                EvidenceLedgerReport,
                EvidenceLedgerEntry,
                ExperimentStatus,
            )
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
            entry = EvidenceLedgerEntry(
                registration=reg,
                evidence=None,
                status=ExperimentStatus.REGISTERED,
                fingerprint="entry_fp",
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
                entry_count=1,
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
                entries=(entry,),
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
            paths = write_all_evidence_ledger_artifacts(report, tmp)
            assert len(paths) >= 8  # At minimum 8 artifact files
            for p in paths:
                assert p.exists()
