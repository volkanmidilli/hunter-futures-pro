"""Integration tests for hunter.discovery package.

These tests exercise the public API end-to-end: build in-memory context summaries,
run the discovery engine, and write human-research artifacts. They do not read files,
call networks, or interact with exchanges.
"""

from __future__ import annotations

import csv
import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.discovery import (
    ALIGNED_CONTEXT,
    MISALIGNED_CONTEXT,
    MIXED_ALIGNMENT,
    PASSED_DISCOVERY_FILTERS,
    DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    DiscoveryClassification,
    DiscoveryConfig,
    DiscoveryInput,
    DiscoveryOpenInterestSummary,
    DiscoveryRelativeStrengthSummary,
    DiscoveryReport,
    DiscoveryState,
    atomic_write_csv_discovery_report,
    atomic_write_json_discovery_report,
    atomic_write_markdown_discovery_report,
    build_discovery_report,
    build_discovery_score,
    discovery_report_to_csv_text,
    discovery_report_to_dict,
    discovery_report_to_json_text,
    discovery_report_to_markdown,
    write_discovery_report,
)

REPORT_ID = "integration-discovery-report"
GENERATED_AT = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rs(
    pair: str,
    *,
    state: str = "READY",
    decision: str = "OUTPERFORMER",
    total_score: float | None = 80.0,
) -> DiscoveryRelativeStrengthSummary:
    return DiscoveryRelativeStrengthSummary(
        pair=pair,
        state=state,
        decision=decision,
        total_score=total_score,
    )


def _oi(
    pair: str,
    *,
    state: str = "READY",
    positioning: str = "PRICE_UP_OI_UP",
    trend: str = "EXPANDING",
    funding_context: str = "POSITIVE",
    total_score: float | None = 70.0,
) -> DiscoveryOpenInterestSummary:
    return DiscoveryOpenInterestSummary(
        pair=pair,
        state=state,
        positioning=positioning,
        trend=trend,
        funding_context=funding_context,
        total_score=total_score,
    )


def _input(
    pair: str,
    *,
    rs: DiscoveryRelativeStrengthSummary | None = None,
    oi: DiscoveryOpenInterestSummary | None = None,
    tags: tuple[str, ...] = (),
    metadata: dict[str, str] | None = None,
) -> DiscoveryInput:
    return DiscoveryInput(
        pair=pair,
        relative_strength=rs,
        open_interest=oi,
        tags=tags,
        metadata=metadata or {},
    )


def _build_report(
    inputs: tuple[DiscoveryInput, ...],
    config: DiscoveryConfig | None = None,
) -> DiscoveryReport:
    return build_discovery_report(
        inputs=inputs,
        config=config or DiscoveryConfig(),
        report_id=REPORT_ID,
        generated_at=GENERATED_AT,
    )


# ---------------------------------------------------------------------------
# End-to-end success
# ---------------------------------------------------------------------------


class TestEndToEndSuccess:
    def test_build_and_report_structure(self) -> None:
        inputs = (
            _input("BTCUSDT", rs=_rs("BTCUSDT"), oi=_oi("BTCUSDT")),
            _input("ETHUSDT", rs=_rs("ETHUSDT", total_score=70.0), oi=_oi("ETHUSDT", total_score=65.0)),
        )
        report = _build_report(inputs)

        assert report.report_id == REPORT_ID
        assert report.version == "0.26.0-dev"
        assert report.generated_at == GENERATED_AT
        assert len(report.inputs) == 2
        assert len(report.candidates) == 2

        summary = report.universe_summary
        assert summary.total_inputs == 2
        assert summary.candidate_count == 2
        assert summary.watchlist_count == 0
        assert summary.excluded_count == 0
        assert summary.insufficient_data_count == 0
        assert summary.blocked_count == 0
        assert summary.ready_context_count == 2
        assert summary.missing_context_count == 0
        assert summary.blocked_context_count == 0

        dq = report.data_quality
        assert dq.total_inputs == 2
        assert dq.pairs_with_both_contexts == 2
        assert dq.pairs_with_missing_relative_strength == 0
        assert dq.pairs_with_missing_open_interest == 0
        assert dq.pairs_with_blocked_context == 0
        assert dq.pairs_with_insufficient_context == 0

        assert report.safety_flags.is_safe is True
        assert report.safety_flags.no_action_commands_emitted is True
        assert report.safety_flags.no_network_connection is True
        assert report.safety_flags.no_file_read_in_engine is True

        # Deterministic ordering: state priority then score desc then pair asc.
        scores = [c.score.total_score for c in report.candidates]
        assert scores == sorted(scores, reverse=True)
        pairs = [c.pair for c in report.candidates]
        assert pairs == sorted(pairs)

    def test_candidates_have_reason_codes(self) -> None:
        inputs = (_input("BTCUSDT", rs=_rs("BTCUSDT"), oi=_oi("BTCUSDT")),)
        report = _build_report(inputs)
        candidate = report.candidates[0]
        assert PASSED_DISCOVERY_FILTERS in candidate.reason_codes
        assert ALIGNED_CONTEXT in candidate.reason_codes


# ---------------------------------------------------------------------------
# End-to-end writer output
# ---------------------------------------------------------------------------


class TestEndToEndWriterOutput:
    def test_write_all_artifacts(self, tmp_path: Path) -> None:
        inputs = (_input("BTCUSDT", rs=_rs("BTCUSDT"), oi=_oi("BTCUSDT")),)
        report = _build_report(inputs)
        json_path = tmp_path / "report.json"
        csv_path = tmp_path / "candidates.csv"
        md_path = tmp_path / "report.md"

        json_out, csv_out, md_out = write_discovery_report(
            report,
            json_path=json_path,
            csv_path=csv_path,
            md_path=md_path,
        )
        assert json_out == json_path
        assert csv_out == csv_path
        assert md_out == md_path

        assert json_path.exists()
        assert csv_path.exists()
        assert md_path.exists()

        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["report_id"] == REPORT_ID

        reader = csv.reader(csv_path.read_text(encoding="utf-8").splitlines())
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0][2] == "pair"
        assert rows[1][2] == "BTCUSDT"

        md_text = md_path.read_text(encoding="utf-8")
        assert md_text.startswith("# Discovery Report")
        assert "> " in md_text
        assert "human-audit" in md_text.lower() or "research-only" in md_text.lower()


# ---------------------------------------------------------------------------
# Classification paths
# ---------------------------------------------------------------------------


class TestCandidateClassifications:
    def test_strong_research_candidate(self) -> None:
        inputs = (_input("BTCUSDT", rs=_rs("BTCUSDT", total_score=90.0), oi=_oi("BTCUSDT", total_score=80.0)),)
        report = _build_report(inputs)
        candidate = report.candidates[0]
        assert candidate.state == DiscoveryState.CANDIDATE
        assert candidate.classification == DiscoveryClassification.STRONG_RESEARCH_CANDIDATE
        assert candidate.score.total_score >= 75.0

    def test_moderate_research_candidate(self) -> None:
        inputs = (
            _input(
                "BTCUSDT",
                rs=_rs("BTCUSDT", total_score=60.0),
                oi=_oi("BTCUSDT", total_score=50.0),
            ),
        )
        report = _build_report(inputs)
        candidate = report.candidates[0]
        assert candidate.state == DiscoveryState.CANDIDATE
        assert candidate.classification == DiscoveryClassification.MODERATE_RESEARCH_CANDIDATE
        assert 60.0 <= candidate.score.total_score < 75.0

    def test_watchlist_only(self) -> None:
        inputs = (
            _input(
                "BTCUSDT",
                rs=_rs("BTCUSDT", total_score=50.0, decision="NEUTRAL"),
                oi=_oi("BTCUSDT", total_score=50.0, positioning="MIXED", trend="FLAT"),
            ),
        )
        report = _build_report(inputs)
        candidate = report.candidates[0]
        assert candidate.state == DiscoveryState.WATCHLIST
        assert candidate.classification == DiscoveryClassification.WATCHLIST_ONLY
        assert 45.0 <= candidate.score.total_score < 60.0

    def test_excluded_by_filters(self) -> None:
        inputs = (
            _input(
                "BTCUSDT",
                rs=_rs("BTCUSDT", total_score=20.0, decision="NEUTRAL"),
                oi=_oi("BTCUSDT", total_score=20.0, positioning="MIXED", trend="FLAT"),
            ),
        )
        report = _build_report(inputs)
        candidate = report.candidates[0]
        assert candidate.state == DiscoveryState.EXCLUDED
        assert candidate.classification == DiscoveryClassification.EXCLUDED_BY_FILTERS
        assert candidate.score.total_score < 45.0

    def test_insufficient_data(self) -> None:
        inputs = (_input("BTCUSDT", rs=_rs("BTCUSDT"), oi=None),)
        report = _build_report(inputs, config=DiscoveryConfig(block_on_missing_context=False))
        candidate = report.candidates[0]
        assert candidate.state == DiscoveryState.INSUFFICIENT_DATA
        assert candidate.classification == DiscoveryClassification.INSUFFICIENT_DATA

    def test_blocked(self) -> None:
        inputs = (
            _input(
                "BTCUSDT",
                rs=_rs("BTCUSDT", state="BLOCKED"),
                oi=_oi("BTCUSDT"),
            ),
        )
        report = _build_report(inputs)
        candidate = report.candidates[0]
        assert candidate.state == DiscoveryState.BLOCKED
        assert candidate.classification == DiscoveryClassification.BLOCKED
        assert candidate.score.total_score == 0.0


# ---------------------------------------------------------------------------
# include_excluded_candidates behavior
# ---------------------------------------------------------------------------


class TestIncludeExcludedCandidates:
    def test_default_includes_excluded(self) -> None:
        inputs = (
            _input(
                "BTCUSDT",
                rs=_rs("BTCUSDT", total_score=20.0, decision="NEUTRAL"),
                oi=_oi("BTCUSDT", total_score=20.0, positioning="MIXED", trend="FLAT"),
            ),
        )
        report = _build_report(inputs, config=DiscoveryConfig())
        assert len(report.candidates) == 1
        assert report.candidates[0].state == DiscoveryState.EXCLUDED
        assert report.universe_summary.excluded_count == 1

    def test_false_omits_excluded_but_keeps_counts(self) -> None:
        inputs = (
            _input(
                "BTCUSDT",
                rs=_rs("BTCUSDT", total_score=20.0, decision="NEUTRAL"),
                oi=_oi("BTCUSDT", total_score=20.0, positioning="MIXED", trend="FLAT"),
            ),
        )
        report = _build_report(inputs, config=DiscoveryConfig(include_excluded_candidates=False))
        assert len(report.candidates) == 0
        assert report.universe_summary.excluded_count == 1
        assert report.universe_summary.total_inputs == 1

    def test_blocked_and_insufficient_always_remain(self) -> None:
        inputs = (
            _input(
                "BTCUSDT",
                rs=_rs("BTCUSDT", state="BLOCKED"),
                oi=_oi("BTCUSDT"),
            ),
            _input("ETHUSDT", rs=_rs("ETHUSDT"), oi=None),
            _input(
                "SOLUSDT",
                rs=_rs("SOLUSDT", total_score=20.0, decision="NEUTRAL"),
                oi=_oi("SOLUSDT", total_score=20.0, positioning="MIXED", trend="FLAT"),
            ),
        )
        report = _build_report(
            inputs,
            config=DiscoveryConfig(block_on_missing_context=False, include_excluded_candidates=False),
        )
        states = {c.state for c in report.candidates}
        assert DiscoveryState.BLOCKED in states
        assert DiscoveryState.INSUFFICIENT_DATA in states
        assert DiscoveryState.EXCLUDED not in states
        assert report.universe_summary.excluded_count == 1


# ---------------------------------------------------------------------------
# Missing context paths
# ---------------------------------------------------------------------------


class TestMissingContextPaths:
    def test_missing_relative_strength_insufficient(self) -> None:
        inputs = (_input("BTCUSDT", rs=None, oi=_oi("BTCUSDT")),)
        report = _build_report(
            inputs,
            config=DiscoveryConfig(
                require_relative_strength=True,
                block_on_missing_context=False,
            ),
        )
        candidate = report.candidates[0]
        assert candidate.state == DiscoveryState.INSUFFICIENT_DATA

    def test_missing_open_interest_insufficient(self) -> None:
        inputs = (_input("BTCUSDT", rs=_rs("BTCUSDT"), oi=None),)
        report = _build_report(
            inputs,
            config=DiscoveryConfig(
                require_open_interest=True,
                block_on_missing_context=False,
            ),
        )
        candidate = report.candidates[0]
        assert candidate.state == DiscoveryState.INSUFFICIENT_DATA

    def test_missing_relative_strength_blocked(self) -> None:
        inputs = (_input("BTCUSDT", rs=None, oi=_oi("BTCUSDT")),)
        report = _build_report(
            inputs,
            config=DiscoveryConfig(
                require_relative_strength=True,
                block_on_missing_context=True,
            ),
        )
        candidate = report.candidates[0]
        assert candidate.state == DiscoveryState.BLOCKED

    def test_missing_open_interest_blocked(self) -> None:
        inputs = (_input("BTCUSDT", rs=_rs("BTCUSDT"), oi=None),)
        report = _build_report(
            inputs,
            config=DiscoveryConfig(
                require_open_interest=True,
                block_on_missing_context=True,
            ),
        )
        candidate = report.candidates[0]
        assert candidate.state == DiscoveryState.BLOCKED


# ---------------------------------------------------------------------------
# Blocked context paths
# ---------------------------------------------------------------------------


class TestBlockedContextPaths:
    def test_relative_strength_blocked(self) -> None:
        inputs = (
            _input(
                "BTCUSDT",
                rs=_rs("BTCUSDT", state="BLOCKED"),
                oi=_oi("BTCUSDT"),
            ),
        )
        report = _build_report(inputs, config=DiscoveryConfig(block_on_blocked_context=True))
        candidate = report.candidates[0]
        assert candidate.state == DiscoveryState.BLOCKED
        assert candidate.score.total_score == 0.0

    def test_open_interest_blocked(self) -> None:
        inputs = (
            _input(
                "BTCUSDT",
                rs=_rs("BTCUSDT"),
                oi=_oi("BTCUSDT", state="BLOCKED"),
            ),
        )
        report = _build_report(inputs, config=DiscoveryConfig(block_on_blocked_context=True))
        candidate = report.candidates[0]
        assert candidate.state == DiscoveryState.BLOCKED
        assert candidate.score.total_score == 0.0


# ---------------------------------------------------------------------------
# Alignment paths
# ---------------------------------------------------------------------------


class TestAlignmentPaths:
    def test_aligned_context(self) -> None:
        rs = _rs("BTCUSDT", decision="OUTPERFORMER")
        oi = _oi("BTCUSDT", positioning="PRICE_UP_OI_UP", trend="EXPANDING")
        score = build_discovery_score(rs, oi, DiscoveryConfig())
        assert score.alignment_score == 100.0
        assert ALIGNED_CONTEXT in score.reason_codes

    def test_mixed_context(self) -> None:
        rs = _rs("BTCUSDT", decision="OUTPERFORMER")
        oi = _oi("BTCUSDT", positioning="MIXED", trend="FLAT")
        score = build_discovery_score(rs, oi, DiscoveryConfig())
        assert score.alignment_score == 70.0
        assert MIXED_ALIGNMENT in score.reason_codes

    def test_misaligned_context(self) -> None:
        rs = _rs("BTCUSDT", decision="OUTPERFORMER")
        oi = _oi("BTCUSDT", positioning="PRICE_DOWN_OI_UP", trend="CONTRACTING")
        score = build_discovery_score(rs, oi, DiscoveryConfig())
        assert score.alignment_score == 0.0
        assert MISALIGNED_CONTEXT in score.reason_codes


# ---------------------------------------------------------------------------
# Threshold behavior
# ---------------------------------------------------------------------------


class TestThresholdBehavior:
    def test_threshold_failure_reduces_filter_bonus(self) -> None:
        rs = _rs("BTCUSDT", total_score=55.0, decision="NEUTRAL")
        oi = _oi("BTCUSDT", total_score=50.0, positioning="MIXED", trend="FLAT")
        score = build_discovery_score(rs, oi, DiscoveryConfig())
        assert score.filter_bonus_score < 100.0
        assert score.filter_bonus_score == 50.0

    def test_excluded_depends_on_total_score(self) -> None:
        inputs = (
            _input(
                "BTCUSDT",
                rs=_rs("BTCUSDT", total_score=20.0, decision="NEUTRAL"),
                oi=_oi("BTCUSDT", total_score=20.0, positioning="MIXED", trend="FLAT"),
            ),
        )
        report = _build_report(inputs)
        candidate = report.candidates[0]
        assert candidate.state == DiscoveryState.EXCLUDED
        assert candidate.score.total_score < 45.0

    def test_not_excluded_when_total_above_watchlist(self) -> None:
        inputs = (
            _input(
                "BTCUSDT",
                rs=_rs("BTCUSDT", total_score=50.0, decision="NEUTRAL"),
                oi=_oi("BTCUSDT", total_score=50.0, positioning="MIXED", trend="FLAT"),
            ),
        )
        report = _build_report(inputs)
        candidate = report.candidates[0]
        assert candidate.score.total_score >= 45.0
        assert candidate.state != DiscoveryState.EXCLUDED


# ---------------------------------------------------------------------------
# Unsafe content path
# ---------------------------------------------------------------------------


class TestUnsafeContentPath:
    def test_unsafe_pair_produces_blocked(self) -> None:
        inputs = (_input("BTCUSDT_BUY", rs=_rs("BTCUSDT_BUY"), oi=_oi("BTCUSDT_BUY")),)
        report = _build_report(inputs)
        candidate = report.candidates[0]
        assert candidate.state == DiscoveryState.BLOCKED
        assert report.safety_flags.has_unsafe_content is True
        assert report.safety_flags.is_safe is False

    def test_unsafe_tag_produces_blocked(self) -> None:
        inputs = (
            _input(
                "BTCUSDT",
                rs=_rs("BTCUSDT"),
                oi=_oi("BTCUSDT"),
                tags=("buy_signal",),
            ),
        )
        report = _build_report(inputs)
        candidate = report.candidates[0]
        assert candidate.state == DiscoveryState.BLOCKED

    def test_unsafe_metadata_is_opaque_string(self) -> None:
        # Path-like metadata should be treated as an opaque string and never opened.
        inputs = (
            _input(
                "BTCUSDT",
                rs=_rs("BTCUSDT"),
                oi=_oi("BTCUSDT"),
                metadata={"note": "/etc/passwd"},
            ),
        )
        report = _build_report(inputs)
        # The metadata string is present but was not read or validated.
        assert report.inputs[0].metadata["note"] == "/etc/passwd"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_inputs_same_dict(self) -> None:
        inputs = (
            _input("BTCUSDT", rs=_rs("BTCUSDT"), oi=_oi("BTCUSDT")),
            _input("ETHUSDT", rs=_rs("ETHUSDT"), oi=_oi("ETHUSDT")),
        )
        report1 = _build_report(inputs)
        report2 = _build_report(inputs)
        assert discovery_report_to_dict(report1) == discovery_report_to_dict(report2)

    def test_same_inputs_same_json_text(self) -> None:
        inputs = (_input("BTCUSDT", rs=_rs("BTCUSDT"), oi=_oi("BTCUSDT")),)
        report1 = _build_report(inputs)
        report2 = _build_report(inputs)
        assert discovery_report_to_json_text(report1) == discovery_report_to_json_text(report2)

    def test_same_inputs_same_markdown_text(self) -> None:
        inputs = (_input("BTCUSDT", rs=_rs("BTCUSDT"), oi=_oi("BTCUSDT")),)
        report1 = _build_report(inputs)
        report2 = _build_report(inputs)
        assert discovery_report_to_markdown(report1) == discovery_report_to_markdown(report2)

    def test_same_inputs_same_csv_text(self) -> None:
        inputs = (_input("BTCUSDT", rs=_rs("BTCUSDT"), oi=_oi("BTCUSDT")),)
        report1 = _build_report(inputs)
        report2 = _build_report(inputs)
        assert discovery_report_to_csv_text(report1) == discovery_report_to_csv_text(report2)


# ---------------------------------------------------------------------------
# No mutation
# ---------------------------------------------------------------------------


class TestNoMutation:
    def test_inputs_unchanged(self) -> None:
        inputs = (
            _input("BTCUSDT", rs=_rs("BTCUSDT"), oi=_oi("BTCUSDT")),
            _input("ETHUSDT", rs=_rs("ETHUSDT"), oi=_oi("ETHUSDT")),
        )
        originals = tuple(dataclasses.replace(inp) for inp in inputs)
        _build_report(inputs)
        for original, current in zip(originals, inputs):
            assert original == current


# ---------------------------------------------------------------------------
# Atomic tmp_path writes
# ---------------------------------------------------------------------------


class TestAtomicTmpPathWrites:
    def test_json_parent_directory_created(self, tmp_path: Path) -> None:
        inputs = (_input("BTCUSDT", rs=_rs("BTCUSDT"), oi=_oi("BTCUSDT")),)
        report = _build_report(inputs)
        target = tmp_path / "deep" / "report.json"
        path = atomic_write_json_discovery_report(report, target)
        assert path == target
        assert path.exists()
        assert path.parent.exists()

    def test_csv_parent_directory_created(self, tmp_path: Path) -> None:
        inputs = (_input("BTCUSDT", rs=_rs("BTCUSDT"), oi=_oi("BTCUSDT")),)
        report = _build_report(inputs)
        target = tmp_path / "deep" / "candidates.csv"
        path = atomic_write_csv_discovery_report(report, target)
        assert path == target
        assert path.exists()
        assert path.parent.exists()

    def test_markdown_parent_directory_created(self, tmp_path: Path) -> None:
        inputs = (_input("BTCUSDT", rs=_rs("BTCUSDT"), oi=_oi("BTCUSDT")),)
        report = _build_report(inputs)
        target = tmp_path / "deep" / "report.md"
        path = atomic_write_markdown_discovery_report(report, target)
        assert path == target
        assert path.exists()
        assert path.parent.exists()

    def test_outputs_only_under_tmp_path(self, tmp_path: Path) -> None:
        inputs = (_input("BTCUSDT", rs=_rs("BTCUSDT"), oi=_oi("BTCUSDT")),)
        report = _build_report(inputs)
        json_path = tmp_path / "report.json"
        csv_path = tmp_path / "candidates.csv"
        md_path = tmp_path / "report.md"
        write_discovery_report(report, json_path=json_path, csv_path=csv_path, md_path=md_path)
        for p in (json_path, csv_path, md_path):
            assert p.exists()
            assert tmp_path in p.parents or p.parent == tmp_path


# ---------------------------------------------------------------------------
# Human-research safety
# ---------------------------------------------------------------------------


class TestHumanResearchSafety:
    def test_markdown_starts_with_h1_and_safety_notice(self) -> None:
        inputs = (_input("BTCUSDT", rs=_rs("BTCUSDT"), oi=_oi("BTCUSDT")),)
        report = _build_report(inputs)
        md = discovery_report_to_markdown(report)
        lines = md.splitlines()
        assert lines[0] == "# Discovery Report"
        assert lines[1] == ""
        assert lines[2].startswith("> ")
        assert "research-only" in lines[2].lower() or "human-audit" in lines[2].lower()

    def test_markdown_no_actionable_trading_language(self) -> None:
        inputs = (_input("BTCUSDT", rs=_rs("BTCUSDT"), oi=_oi("BTCUSDT")),)
        report = _build_report(inputs)
        md = discovery_report_to_markdown(report)
        lines = md.splitlines()
        notice_end = 0
        for i, line in enumerate(lines):
            if line.startswith("> "):
                notice_end = i
        remaining = "\n".join(lines[notice_end + 1 :])
        actionable = [
            "buy",
            "sell",
            "long",
            "short",
            "enter",
            "entry",
            "exit",
            "stop loss",
            "take profit",
            "leverage",
            "action command",
            "execution approval",
            "trade approval",
            "order suggestion",
        ]
        lower = remaining.lower()
        for term in actionable:
            assert term not in lower, f"found actionable term {term!r}"

    def test_report_safety_flags_are_true(self) -> None:
        inputs = (_input("BTCUSDT", rs=_rs("BTCUSDT"), oi=_oi("BTCUSDT")),)
        report = _build_report(inputs)
        assert report.safety_flags.no_action_commands_emitted is True
        assert report.safety_flags.no_network_connection is True
        assert report.safety_flags.no_file_read_in_engine is True


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


class TestPublicExports:
    def test_build_discovery_report_exported(self) -> None:
        assert callable(build_discovery_report)

    def test_writer_functions_exported(self) -> None:
        assert callable(write_discovery_report)
        assert callable(atomic_write_json_discovery_report)
        assert callable(atomic_write_csv_discovery_report)
        assert callable(atomic_write_markdown_discovery_report)
        assert callable(discovery_report_to_dict)
        assert callable(discovery_report_to_json_text)
        assert callable(discovery_report_to_csv_text)
        assert callable(discovery_report_to_markdown)

    def test_default_paths_exported(self) -> None:
        assert DEFAULT_JSON_PATH.name == "latest_discovery_report.json"
        assert DEFAULT_CSV_PATH.name == "latest_discovery_candidates.csv"
        assert DEFAULT_MD_PATH.name == "latest_discovery_report.md"
