"""Tests for deterministic research universe writers (MVP-64 Stage 7)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

import pytest
from unittest.mock import patch

from hunter.research_universe.errors import ResearchUniverseWriterError
from hunter.research_universe.models import (
    BaselineUniverseResult,
    CandidateUniverseResult,
    ResearchUniverseComparison,
    ResearchUniverseConfig,
    ResearchUniverseManifest,
    ResearchUniverseReport,
    ResearchUniverseSafetyFlags,
    SelectionWindow,
    UniversePairClassification,
    UniversePairDecision,
    UniversePairDecisionKind,
    UniversePairState,
)
from hunter.research_universe.writer import (
    ResearchUniverseWriter,
    write_all_research_universe_artifacts,
)


def _safety_flags() -> ResearchUniverseSafetyFlags:
    return ResearchUniverseSafetyFlags()


def _candidate() -> CandidateUniverseResult:
    decisions = (
        UniversePairDecision(
            pair="SOL/USDT",
            decision=UniversePairDecisionKind.INCLUDED,
            state=UniversePairState.CANDIDATE,
            classification=UniversePairClassification.LONG_RESEARCH,
            rank=1,
            score=80.0,
            estimated_quote_volume=None,
            source_fingerprint="fp-candidate",
            reason_codes=("CANDIDATE_CLASSIFICATION_INCLUDED",),
        ),
        UniversePairDecision(
            pair="ADA/USDT",
            decision=UniversePairDecisionKind.INCLUDED,
            state=UniversePairState.CANDIDATE,
            classification=UniversePairClassification.LONG_RESEARCH,
            rank=2,
            score=75.0,
            estimated_quote_volume=None,
            source_fingerprint="fp-candidate",
            reason_codes=("CANDIDATE_CLASSIFICATION_INCLUDED",),
        ),
    )
    return CandidateUniverseResult(
        decisions=decisions,
        pairlist={
            "SOL/USDT": {"rank": 1, "score": 80.0, "classification": "LONG_RESEARCH"},
            "ADA/USDT": {"rank": 2, "score": 75.0, "classification": "LONG_RESEARCH"},
        },
        fingerprint="candidate-fp-abc",
        safety_flags=_safety_flags(),
        reason_codes=(),
    )


def _baseline() -> BaselineUniverseResult:
    decisions = (
        UniversePairDecision(
            pair="SOL/USDT",
            decision=UniversePairDecisionKind.INCLUDED,
            state=UniversePairState.BASELINE,
            classification=UniversePairClassification.BASELINE_VOLUME,
            rank=1,
            estimated_quote_volume=Decimal("100000"),
            source_fingerprint="fp-baseline",
            reason_codes=(),
        ),
        UniversePairDecision(
            pair="DOT/USDT",
            decision=UniversePairDecisionKind.INCLUDED,
            state=UniversePairState.BASELINE,
            classification=UniversePairClassification.BASELINE_VOLUME,
            rank=2,
            estimated_quote_volume=Decimal("50000"),
            source_fingerprint="fp-baseline",
            reason_codes=(),
        ),
    )
    return BaselineUniverseResult(
        decisions=decisions,
        pairlist={
            "SOL/USDT": {"rank": 1, "estimated_quote_volume": "100000"},
            "DOT/USDT": {"rank": 2, "estimated_quote_volume": "50000"},
        },
        fingerprint="baseline-fp-xyz",
        safety_flags=_safety_flags(),
        reason_codes=(),
    )


def _comparison(
    candidate: CandidateUniverseResult, baseline: BaselineUniverseResult
) -> ResearchUniverseComparison:
    overlap = tuple(sorted(set(candidate.pairs) & set(baseline.pairs)))
    candidate_only = tuple(sorted(set(candidate.pairs) - set(baseline.pairs)))
    baseline_only = tuple(sorted(set(baseline.pairs) - set(candidate.pairs)))
    union_count = len(set(candidate.pairs) | set(baseline.pairs))
    jaccard = len(overlap) / union_count if union_count else 0.0
    return ResearchUniverseComparison(
        overlap=overlap,
        candidate_only=candidate_only,
        baseline_only=baseline_only,
        union_count=union_count,
        jaccard_similarity=jaccard,
        safety_flags=_safety_flags(),
        fingerprint="comparison-fp-123",
        reason_codes=(),
    )


def _report() -> ResearchUniverseReport:
    window = SelectionWindow(
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 10, tzinfo=timezone.utc),
    )
    config = ResearchUniverseConfig(selection_window=window)
    candidate = _candidate()
    baseline = _baseline()
    comparison = _comparison(candidate, baseline)
    manifest = ResearchUniverseManifest(
        version="0.64.0-dev",
        spec_version="SPEC-065",
        research_universe_version="0.64.0-dev",
        generated_at=datetime(2024, 1, 10, tzinfo=timezone.utc),
        bundle_fingerprint="bundle-fp",
        policy_fingerprint="policy-fp",
        selection_window=window,
        candidate_fingerprint=candidate.fingerprint,
        baseline_fingerprint=baseline.fingerprint,
        comparison_fingerprint=comparison.fingerprint,
        safety_flags=_safety_flags(),
        reason_codes=(),
    )
    return ResearchUniverseReport(
        version="0.64.0-dev",
        spec_version="SPEC-065",
        config=config,
        manifest=manifest,
        candidate=candidate,
        baseline=baseline,
        comparison=comparison,
        safety_flags=_safety_flags(),
        metadata={"generated_at": "2024-01-10T00:00:00+00:00"},
        fingerprint="report-fp-789",
        human_approval_required=True,
        research_only=True,
        reason_codes=(),
    )


class TestCandidateArtifacts:
    def test_candidate_json_deterministic(self, tmp_path: Path) -> None:
        writer = ResearchUniverseWriter(output_dir=tmp_path)
        candidate = _candidate()
        p1 = writer.write_candidate_json(candidate)
        p2 = writer.write_candidate_json(candidate, overwrite=True)
        assert p1 == p2
        assert p1.read_text() == p2.read_text()
        data = json.loads(p1.read_text())
        assert data["fingerprint"] == candidate.fingerprint
        assert data["pairs"] == ["SOL/USDT", "ADA/USDT"]
        assert data["safety_flags"]["research_only"] is True

    def test_candidate_markdown_deterministic(self, tmp_path: Path) -> None:
        writer = ResearchUniverseWriter(output_dir=tmp_path)
        candidate = _candidate()
        p1 = writer.write_candidate_markdown(candidate)
        p2 = writer.write_candidate_markdown(candidate, overwrite=True)
        assert p1 == p2
        assert p1.read_text() == p2.read_text()
        assert "# Candidate Universe" in p1.read_text()
        assert "SOL/USDT" in p1.read_text()


class TestBaselineArtifacts:
    def test_baseline_json_deterministic(self, tmp_path: Path) -> None:
        writer = ResearchUniverseWriter(output_dir=tmp_path)
        baseline = _baseline()
        p1 = writer.write_baseline_json(baseline)
        p2 = writer.write_baseline_json(baseline, overwrite=True)
        assert p1 == p2
        assert p1.read_text() == p2.read_text()
        data = json.loads(p1.read_text())
        assert data["fingerprint"] == baseline.fingerprint
        assert data["pairs"] == ["SOL/USDT", "DOT/USDT"]
        assert data["safety_flags"]["research_only"] is True

    def test_baseline_markdown_deterministic(self, tmp_path: Path) -> None:
        writer = ResearchUniverseWriter(output_dir=tmp_path)
        baseline = _baseline()
        p1 = writer.write_baseline_markdown(baseline)
        p2 = writer.write_baseline_markdown(baseline, overwrite=True)
        assert p1 == p2
        assert p1.read_text() == p2.read_text()
        assert "# Baseline Universe" in p1.read_text()
        assert "SOL/USDT" in p1.read_text()


class TestComparisonArtifacts:
    def test_comparison_json_deterministic(self, tmp_path: Path) -> None:
        writer = ResearchUniverseWriter(output_dir=tmp_path)
        comparison = _comparison(_candidate(), _baseline())
        p1 = writer.write_comparison_json(comparison)
        p2 = writer.write_comparison_json(comparison, overwrite=True)
        assert p1 == p2
        assert p1.read_text() == p2.read_text()
        data = json.loads(p1.read_text())
        assert data["fingerprint"] == comparison.fingerprint
        assert data["safety_flags"]["research_only"] is True

    def test_comparison_markdown_deterministic(self, tmp_path: Path) -> None:
        writer = ResearchUniverseWriter(output_dir=tmp_path)
        comparison = _comparison(_candidate(), _baseline())
        p1 = writer.write_comparison_markdown(comparison)
        p2 = writer.write_comparison_markdown(comparison, overwrite=True)
        assert p1 == p2
        assert p1.read_text() == p2.read_text()
        assert "# Universe Comparison" in p1.read_text()


class TestWriterSafety:
    def test_safety_notice_in_all_artifacts(self, tmp_path: Path) -> None:
        report = _report()
        writer = ResearchUniverseWriter(output_dir=tmp_path, data_dir=tmp_path / "data")
        paths = writer.write_all(report)
        for name, path in paths.items():
            text = path.read_text()
            assert "RESEARCH ONLY" in text
            if name.endswith("_json") or name == "report" or name == "manifest":
                data = json.loads(text)
                assert data["safety_notice"].startswith("RESEARCH ONLY")

    def test_public_outputs_preserve_safety_flags(self, tmp_path: Path) -> None:
        report = _report()
        paths = write_all_research_universe_artifacts(
            report, output_dir=tmp_path / "reports", data_dir=tmp_path / "data"
        )
        for name, path in paths.items():
            if name.endswith("_json") or name == "report" or name == "manifest":
                data = json.loads(path.read_text())
                flags = data.get("safety_flags")
                if flags is None:
                    continue
                assert flags["research_only"] is True
                assert flags["execution_approval_granted"] is False
                assert flags["production_approval_granted"] is False
                assert flags["live_trading_allowed"] is False
                assert flags["automatic_execution_allowed"] is False

    def test_silent_overwrite_rejected(self, tmp_path: Path) -> None:
        writer = ResearchUniverseWriter(output_dir=tmp_path)
        candidate = _candidate()
        writer.write_candidate_json(candidate)
        with pytest.raises(ResearchUniverseWriterError) as exc:
            writer.write_candidate_json(candidate)
        assert exc.value.reason_code == "SILENT_OVERWRITE_BLOCKED"

    def test_explicit_overwrite_allowed(self, tmp_path: Path) -> None:
        writer = ResearchUniverseWriter(output_dir=tmp_path)
        candidate = _candidate()
        p1 = writer.write_candidate_json(candidate)
        p2 = writer.write_candidate_json(candidate, overwrite=True)
        assert p1 == p2

    def test_atomic_write_no_temp_files_left(self, tmp_path: Path) -> None:
        report = _report()
        writer = ResearchUniverseWriter(output_dir=tmp_path, data_dir=tmp_path / "data")
        writer.write_all(report)
        tmp_files = list(tmp_path.rglob("*.tmp"))
        assert tmp_files == []

    def test_failed_write_cleanup(self, tmp_path: Path) -> None:
        writer = ResearchUniverseWriter(output_dir=tmp_path)
        candidate = _candidate()
        # Force os.replace to fail after the temp file has been written.
        with patch("hunter.research_universe.writer.os.replace", side_effect=OSError("forced failure")):
            with pytest.raises(ResearchUniverseWriterError):
                writer.write_candidate_json(candidate)
        tmp_files = list(tmp_path.rglob("*.tmp"))
        assert tmp_files == []

    def test_absolute_path_redaction(self, tmp_path: Path) -> None:
        report = _report()
        writer = ResearchUniverseWriter(output_dir=tmp_path / "reports" / "research_universe", data_dir=tmp_path / "data")
        _, manifest_path = writer.write(report)
        manifest = json.loads(manifest_path.read_text())
        assert "/" not in manifest["report_path"] or manifest["report_path"].startswith("reports/")

    def test_source_candle_files_not_modified(self, tmp_path: Path) -> None:
        source = tmp_path / "SOLUSDT.csv"
        source.write_text("open,high,low,close,volume\n")
        mtime_before = source.stat().st_mtime
        report = _report()
        writer = ResearchUniverseWriter(output_dir=tmp_path, data_dir=tmp_path / "data")
        writer.write_all(report)
        mtime_after = source.stat().st_mtime
        assert mtime_before == mtime_after
        assert source.read_text() == "open,high,low,close,volume\n"

    def test_canonical_ordering_and_stable_serialization(self, tmp_path: Path) -> None:
        writer = ResearchUniverseWriter(output_dir=tmp_path)
        candidate = _candidate()
        path = writer.write_candidate_json(candidate)
        text = path.read_text()
        # Verify keys are sorted (sort_keys=True)
        assert text.index('"decisions"') < text.index('"fingerprint"') < text.index('"pairs"')
