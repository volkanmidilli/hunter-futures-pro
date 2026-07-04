"""Tests for hunter.final_audit_pack.writer."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

import pytest

from hunter.final_audit_pack import (
    DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    FINAL_AUDIT_PACK_VERSION,
    FinalAuditPackArtifact,
    FinalAuditPackCompleteness,
    FinalAuditPackConfig,
    FinalAuditPackDataQuality,
    FinalAuditPackInput,
    FinalAuditPackReport,
    FinalAuditPackSafetyFlags,
    FinalAuditPackSection,
    FinalAuditPackState,
    UNSAFE_CONTENT,
    build_final_audit_pack_report,
)
from hunter.final_audit_pack.writer import (
    atomic_write_csv_final_audit_pack_report,
    atomic_write_json_final_audit_pack_report,
    atomic_write_markdown_final_audit_pack_report,
    final_audit_pack_report_to_csv_text,
    final_audit_pack_report_to_dict,
    final_audit_pack_report_to_json_text,
    final_audit_pack_report_to_markdown_text,
    write_final_audit_pack_report,
)


def _ts(day: int = 1) -> datetime:
    return datetime(2024, 1, day, tzinfo=timezone.utc)


def _make_section(
    section_id: str = "s1",
    section_kind: str = "backtest",
    *,
    name: str = "",
    state: FinalAuditPackState = FinalAuditPackState.INCLUDED,
    report_id: str = "r1",
    run_id: str = "",
    reason_codes: tuple[str, ...] = ("OK",),
    generated_at: datetime | None = None,
    tags: tuple[str, ...] = (),
    metadata: dict[str, object] | None = None,
) -> FinalAuditPackSection:
    return FinalAuditPackSection(
        section_id=section_id,
        section_kind=section_kind,
        report_id=report_id,
        run_id=run_id,
        name=name,
        state=state,
        reason_codes=reason_codes,
        generated_at=generated_at or _ts(1),
        tags=tags,
        metadata=metadata or {},
    )


def _make_report(
    *,
    sections: tuple[FinalAuditPackSection, ...] = (),
    artifacts: tuple[FinalAuditPackArtifact, ...] = (),
    completeness: FinalAuditPackCompleteness | None = None,
    data_quality: FinalAuditPackDataQuality | None = None,
    safety_flags: FinalAuditPackSafetyFlags | None = None,
    reason_codes: tuple[str, ...] = (),
    metadata: dict[str, object] | None = None,
    notes: tuple[str, ...] = (),
    generated_at: datetime | None = None,
    report_id: str = "report-1",
) -> FinalAuditPackReport:
    return FinalAuditPackReport(
        report_id=report_id,
        generated_at=generated_at or _ts(1),
        version=FINAL_AUDIT_PACK_VERSION,
        sections=sections,
        artifacts=artifacts,
        completeness=completeness or FinalAuditPackCompleteness(),
        data_quality=data_quality or FinalAuditPackDataQuality(),
        safety_flags=safety_flags or FinalAuditPackSafetyFlags(),
        reason_codes=reason_codes,
        metadata=metadata or {},
        notes=notes,
    )


class TestDictSerialization:
    def test_dict_conversion_includes_report_sections_artifacts_completeness_data_quality_safety_flags(
        self,
    ) -> None:
        section = _make_section()
        artifact = FinalAuditPackArtifact(kind="artifact", reference="data/foo.json")
        report = _make_report(sections=(section,), artifacts=(artifact,))
        data = final_audit_pack_report_to_dict(report)

        assert data["report_id"] == report.report_id
        assert data["version"] == FINAL_AUDIT_PACK_VERSION
        assert data["generated_at"] == report.generated_at.isoformat()

        assert "sections" in data
        assert len(data["sections"]) == 1
        assert data["sections"][0]["section_id"] == "s1"
        assert data["sections"][0]["state"] == "included"

        assert "artifacts" in data
        assert len(data["artifacts"]) == 1
        assert data["artifacts"][0]["reference"] == "data/foo.json"

        assert "completeness" in data
        assert "data_quality" in data
        assert "safety_flags" in data
        assert "is_safe" in data["safety_flags"]

    def test_nested_dataclass_mapping_serialization(self) -> None:
        section = _make_section(metadata={"key": "value"})
        report = _make_report(
            sections=(section,),
            metadata={"nested": {"a": 1}},
            data_quality=FinalAuditPackDataQuality(artifact_references=2),
        )
        data = final_audit_pack_report_to_dict(report)

        assert data["metadata"] == {"nested": {"a": 1}}
        assert data["sections"][0]["metadata"] == {"key": "value"}
        assert data["data_quality"]["artifact_references"] == 2
        assert isinstance(data["sections"][0]["state"], str)
        assert isinstance(data["sections"][0]["reason_codes"], list)

    def test_enum_and_datetime_serialization(self) -> None:
        section = _make_section(state=FinalAuditPackState.BLOCKED, reason_codes=("UNSAFE_CONTENT",))
        report = _make_report(sections=(section,))
        data = final_audit_pack_report_to_dict(report)

        assert data["sections"][0]["state"] == "blocked"
        assert data["sections"][0]["reason_codes"] == ["UNSAFE_CONTENT"]
        assert data["generated_at"].endswith("+00:00")
        datetime.fromisoformat(data["generated_at"])


class TestJsonText:
    def test_json_parseable_and_deterministic(self) -> None:
        report = _make_report(
            sections=(_make_section(),),
            artifacts=(FinalAuditPackArtifact(kind="artifact", reference="data/foo.json"),),
        )
        text1 = final_audit_pack_report_to_json_text(report)
        text2 = final_audit_pack_report_to_json_text(report)
        assert text1 == text2
        assert text1.endswith("\n")

        data = json.loads(text1)
        assert data["report_id"] == report.report_id
        assert data["version"] == FINAL_AUDIT_PACK_VERSION
        assert len(data["sections"]) == 1
        assert len(data["artifacts"]) == 1

    def test_json_sort_keys_deterministic(self) -> None:
        report = _make_report(metadata={"z": 1, "a": 2})
        text = final_audit_pack_report_to_json_text(report)
        data = json.loads(text)
        assert list(data["metadata"].keys()) == sorted(data["metadata"].keys())


class TestCsvText:
    def test_csv_header_and_deterministic_section_rows(self) -> None:
        section1 = _make_section(section_id="s1", section_kind="backtest", name="Backtest")
        section2 = _make_section(
            section_id="s2",
            section_kind="run_orchestrator",
            name="Run",
            run_id="run-1",
        )
        artifact = FinalAuditPackArtifact(kind="artifact", reference="data/foo.json")
        report = _make_report(sections=(section1, section2), artifacts=(artifact,))
        text = final_audit_pack_report_to_csv_text(report)

        lines = text.strip().split("\n")
        header = lines[0].split(",")
        expected_header = [
            "report_id",
            "generated_at",
            "section_id",
            "section_kind",
            "display_name",
            "state",
            "reason_codes",
            "artifact_count",
            "generated_at_section",
            "source_report_id",
            "source_run_id",
        ]
        assert header == expected_header
        assert len(lines) == 3

        rows = list(csv.DictReader(text.splitlines()))
        assert len(rows) == 2
        assert rows[0]["section_id"] == "s1"
        assert rows[0]["display_name"] == "Backtest"
        assert rows[0]["state"] == "included"
        assert rows[0]["reason_codes"] == "OK"
        assert rows[0]["artifact_count"] == "1"
        assert rows[0]["source_report_id"] == "r1"
        assert rows[1]["section_id"] == "s2"
        assert rows[1]["source_run_id"] == "run-1"

    def test_csv_blocked_section_row(self) -> None:
        section = _make_section(
            section_id="s1",
            state=FinalAuditPackState.BLOCKED,
            reason_codes=("UNSAFE_CONTENT", "DUPLICATE_SECTION_ID"),
        )
        report = _make_report(sections=(section,))
        text = final_audit_pack_report_to_csv_text(report)

        rows = list(csv.DictReader(text.splitlines()))
        assert len(rows) == 1
        assert rows[0]["state"] == "blocked"
        assert rows[0]["reason_codes"] == "UNSAFE_CONTENT|DUPLICATE_SECTION_ID"


class TestMarkdown:
    def test_starts_with_h1_and_immediate_research_only_audit_only_notice(self) -> None:
        report = _make_report()
        text = final_audit_pack_report_to_markdown_text(report)
        lines = [line for line in text.split("\n") if line.strip()]
        assert lines[0] == "# Final Audit Pack Report"
        assert lines[1].startswith("> ")
        assert "research-only" in lines[1].lower() or "audit-only" in lines[1].lower()

    def test_explicitly_not_approval_certification_recommendation_trading_readiness_signal(
        self,
    ) -> None:
        report = _make_report()
        text = final_audit_pack_report_to_markdown_text(report)
        notice_lines = [line for line in text.split("\n") if line.startswith("> ")]
        notice = " ".join(notice_lines).lower()
        assert "not a certification of trading readiness" in notice
        assert "not trade approval" in notice
        assert "not strategy approval" in notice
        assert "not execution approval" in notice
        assert "not portfolio approval" in notice
        assert "not universe approval" in notice

    def test_contains_summary_completeness_sections_artifacts_data_quality_safety_flags(
        self,
    ) -> None:
        report = _make_report(
            sections=(_make_section(),),
            artifacts=(FinalAuditPackArtifact(kind="artifact", reference="data/foo.json"),),
        )
        text = final_audit_pack_report_to_markdown_text(report)
        assert "## Summary" in text
        assert "## Completeness Summary" in text
        assert "## Sections" in text
        assert "## Artifacts" in text
        assert "## Data Quality" in text
        assert "## Safety Flags" in text

    def test_no_actionable_recommendation_signal_language(self) -> None:
        report = _make_report()
        text = final_audit_pack_report_to_markdown_text(report)
        # Skip the safety notice; it legitimately mentions trading/execution terms as disclaimers.
        lines = [line for line in text.split("\n") if not line.startswith("> ")]
        body = "\n".join(lines).lower()
        for bad in (
            "buy",
            "sell",
            "place order",
            "execute trade",
            "rebalance now",
            "go live",
            "deploy capital",
        ):
            assert bad not in body, f"found actionable term: {bad}"

    def test_blocked_report_markdown(self) -> None:
        input_obj = FinalAuditPackInput()
        report = FinalAuditPackReport.blocked(input=input_obj, reason_code=UNSAFE_CONTENT)
        text = final_audit_pack_report_to_markdown_text(report)
        assert "# Final Audit Pack Report" in text
        assert "## Safety Flags" in text
        assert "has_unsafe_content" in text


class TestAtomicWrites:
    def test_atomic_json_creates_parent_dir(self, tmp_path) -> None:
        report = _make_report()
        path = tmp_path / "nested" / "report.json"
        atomic_write_json_final_audit_pack_report(report, path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["report_id"] == report.report_id

    def test_atomic_csv_creates_parent_dir(self, tmp_path) -> None:
        report = _make_report(sections=(_make_section(),))
        path = tmp_path / "nested" / "report.csv"
        atomic_write_csv_final_audit_pack_report(report, path)
        assert path.exists()
        assert "," in path.read_text()

    def test_atomic_markdown_creates_parent_dir(self, tmp_path) -> None:
        report = _make_report()
        path = tmp_path / "nested" / "report.md"
        atomic_write_markdown_final_audit_pack_report(report, path)
        assert path.exists()
        assert path.read_text().startswith("# Final Audit Pack Report")

    def test_write_report_writes_all_artifacts(self, tmp_path) -> None:
        report = _make_report(sections=(_make_section(),))
        json_path = tmp_path / "report.json"
        csv_path = tmp_path / "report.csv"
        md_path = tmp_path / "report.md"
        write_final_audit_pack_report(
            report, json_path=json_path, csv_path=csv_path, md_path=md_path
        )
        assert json_path.exists()
        assert csv_path.exists()
        assert md_path.exists()

    def test_write_report_can_skip_format(self, tmp_path) -> None:
        report = _make_report()
        json_path = tmp_path / "report.json"
        write_final_audit_pack_report(
            report, json_path=json_path, csv_path=None, md_path=None
        )
        assert json_path.exists()
        assert not (tmp_path / "report.csv").exists()
        assert not (tmp_path / "report.md").exists()

    def test_does_not_mutate_report(self, tmp_path) -> None:
        report = _make_report(sections=(_make_section(),))
        before = final_audit_pack_report_to_json_text(report)
        write_final_audit_pack_report(report, json_path=tmp_path / "r.json")
        after = final_audit_pack_report_to_json_text(report)
        assert before == after


class TestEdgeReports:
    def test_blocked_report_serialization(self) -> None:
        input_obj = FinalAuditPackInput()
        report = FinalAuditPackReport.blocked(input=input_obj, reason_code=UNSAFE_CONTENT)
        text = final_audit_pack_report_to_json_text(report)
        data = json.loads(text)
        assert data["safety_flags"]["has_unsafe_content"] is True
        assert data["sections"] == []
        assert data["artifacts"] == []
        assert "UNSAFE_CONTENT" in data["reason_codes"]

    def test_engine_report_round_trip(self) -> None:
        from hunter.backtest import (
            BacktestAllocationMode,
            BacktestCandidateDecision,
            BacktestInput,
            BacktestPriceBar,
            BacktestRunConfig,
            build_backtest_report,
        )

        decision = BacktestCandidateDecision(
            pair="A",
            state="INCLUDED",
            classification="CORE_RESEARCH_ALLOCATION",
            final_weight_pct=0.0,
        )
        bar = BacktestPriceBar(pair="A", timestamp=_ts(1), close=100.0)
        inp = BacktestInput(pair="A", decision=decision, price_bars=(bar,))
        cfg = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
        backtest_report = build_backtest_report((inp,), cfg, report_id="bt-1", generated_at=_ts(1))
        final_input = FinalAuditPackInput(
            backtest_reports=(backtest_report,),
            generated_at=_ts(1),
        )
        final_config = FinalAuditPackConfig(
            required_section_kinds=("backtest",),
            optional_section_kinds=(),
            generated_at=_ts(1),
        )
        report = build_final_audit_pack_report(final_input, final_config)

        text = final_audit_pack_report_to_json_text(report)
        data = json.loads(text)
        assert data["report_id"] == report.report_id
        assert len(data["sections"]) == 1
        assert data["sections"][0]["section_kind"] == "backtest"

        csv_text = final_audit_pack_report_to_csv_text(report)
        assert "backtest" in csv_text

        md_text = final_audit_pack_report_to_markdown_text(report)
        assert "## Sections" in md_text


class TestDefaultPaths:
    def test_default_paths_exported(self) -> None:
        assert str(DEFAULT_JSON_PATH) == "data/final_audit_pack/final_audit_pack.json"
        assert str(DEFAULT_CSV_PATH) == "data/final_audit_pack/final_audit_pack_sections.csv"
        assert str(DEFAULT_MD_PATH) == "reports/final_audit_pack/final_audit_pack.md"


class TestPublicExports:
    def test_writer_functions_exported_from_package(self) -> None:
        from hunter.final_audit_pack import (
            atomic_write_csv_final_audit_pack_report,
            atomic_write_json_final_audit_pack_report,
            atomic_write_markdown_final_audit_pack_report,
            final_audit_pack_report_to_csv_text,
            final_audit_pack_report_to_dict,
            final_audit_pack_report_to_json_text,
            final_audit_pack_report_to_markdown_text,
            write_final_audit_pack_report,
        )

        assert callable(final_audit_pack_report_to_dict)
        assert callable(final_audit_pack_report_to_json_text)
        assert callable(final_audit_pack_report_to_csv_text)
        assert callable(final_audit_pack_report_to_markdown_text)
        assert callable(atomic_write_json_final_audit_pack_report)
        assert callable(atomic_write_csv_final_audit_pack_report)
        assert callable(atomic_write_markdown_final_audit_pack_report)
        assert callable(write_final_audit_pack_report)


class TestNoFileTraversal:
    def test_no_metadata_artifact_reference_traversal_opening(self, tmp_path) -> None:
        # Use references that look like paths but ensure writer does not open them.
        artifact = FinalAuditPackArtifact(
            kind="artifact", reference="data/nonexistent_file.txt"
        )
        report = _make_report(
            artifacts=(artifact,),
            metadata={"path": "data/nonexistent_file.txt"},
        )
        text = final_audit_pack_report_to_json_text(report)
        data = json.loads(text)
        assert data["artifacts"][0]["reference"] == "data/nonexistent_file.txt"
        assert data["metadata"]["path"] == "data/nonexistent_file.txt"

        path = tmp_path / "report.json"
        atomic_write_json_final_audit_pack_report(report, path)
        assert path.exists()
