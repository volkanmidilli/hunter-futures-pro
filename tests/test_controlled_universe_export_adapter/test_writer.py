"""Tests for the controlled_universe_export_adapter writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.controlled_universe_export_adapter import (
    EXPORT_HUMAN_APPROVAL_REQUIRED,
    EXPORT_RESEARCH_ONLY,
    NO_AUTOMATIC_CONFIG_MUTATION,
    NO_FREQTRADE_RUNTIME_CONNECTION,
    ControlledUniverseExportConfig,
    ControlledUniverseExportResult,
    ControlledUniversePairExportSummary,
    atomic_write_json_controlled_universe_export,
    atomic_write_markdown_controlled_universe_export,
    controlled_universe_export_to_dict,
    controlled_universe_export_to_json_text,
    controlled_universe_export_to_markdown_text,
    write_controlled_universe_export,
)


def _dt() -> datetime:
    return datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)


def _make_result() -> ControlledUniverseExportResult:
    return ControlledUniverseExportResult(
        report_id="report-1",
        generated_at=_dt(),
        whitelist=("BTC/USDT", "ETH/USDT"),
        blacklist=("SOL/USDT",),
        per_pair_summary=(
            ControlledUniversePairExportSummary(
                pair="BTC/USDT",
                state="INCLUDED",
                classification="LONG_RESEARCH",
                reason_codes=("PASSED_UNIVERSE_FILTER",),
                human_note="passed controlled universe filter",
            ),
            ControlledUniversePairExportSummary(
                pair="ETH/USDT",
                state="INCLUDED",
                classification="LONG_RESEARCH",
                reason_codes=("PASSED_UNIVERSE_FILTER",),
                human_note="passed controlled universe filter",
            ),
            ControlledUniversePairExportSummary(
                pair="SOL/USDT",
                state="BLOCKED",
                classification="BLOCKED_BY_MACRO",
                reason_codes=("MACRO_MODE_NONE",),
                human_note="blocked by macro state",
            ),
        ),
        reason_codes=(
            EXPORT_RESEARCH_ONLY,
            EXPORT_HUMAN_APPROVAL_REQUIRED,
            NO_FREQTRADE_RUNTIME_CONNECTION,
            NO_AUTOMATIC_CONFIG_MUTATION,
        ),
        safety_flags={
            "research_only": True,
            "human_approval_required": True,
        },
        metadata={"source": "SPEC-054"},
    )


class TestControlledUniverseExportToDict:
    def test_includes_all_fields(self) -> None:
        result = _make_result()
        data = controlled_universe_export_to_dict(result)
        assert data["kind"] == "controlled_universe_export"
        assert data["report_id"] == "report-1"
        assert data["research_only"] is True
        assert data["human_approval_required"] is True
        assert data["whitelist"] == ["BTC/USDT", "ETH/USDT"]
        assert data["blacklist"] == ["SOL/USDT"]
        assert len(data["per_pair_summary"]) == 3
        assert data["reason_codes"] == list(result.reason_codes)
        assert data["safety_flags"] == result.safety_flags
        assert data["metadata"] == {"source": "SPEC-054"}
        assert "safety_notice" in data


class TestControlledUniverseExportToJsonText:
    def test_valid_json(self) -> None:
        result = _make_result()
        text = controlled_universe_export_to_json_text(result)
        data = json.loads(text)
        assert data["report_id"] == "report-1"
        assert data["whitelist"] == ["BTC/USDT", "ETH/USDT"]

    def test_sorts_keys(self) -> None:
        result = _make_result()
        text = controlled_universe_export_to_json_text(result)
        assert text.startswith('{\n  "blacklist":')


class TestControlledUniverseExportToMarkdownText:
    def test_contains_safety_notice(self) -> None:
        result = _make_result()
        text = controlled_universe_export_to_markdown_text(result)
        assert "Controlled Universe Export" in text
        assert "research-only" in text
        assert "human approval is required" in text

    def test_contains_whitelist_and_blacklist(self) -> None:
        result = _make_result()
        text = controlled_universe_export_to_markdown_text(result)
        assert "BTC/USDT" in text
        assert "ETH/USDT" in text
        assert "SOL/USDT" in text

    def test_contains_per_pair_summary(self) -> None:
        result = _make_result()
        text = controlled_universe_export_to_markdown_text(result)
        assert "## Per-Pair Summary" in text
        assert "PASSED_UNIVERSE_FILTER" in text


class TestAtomicWrites:
    def test_atomic_write_json(self, tmp_path: Path) -> None:
        result = _make_result()
        path = tmp_path / "export.json"
        returned = atomic_write_json_controlled_universe_export(result, path)
        assert returned == path
        data = json.loads(path.read_text())
        assert data["whitelist"] == ["BTC/USDT", "ETH/USDT"]

    def test_atomic_write_markdown(self, tmp_path: Path) -> None:
        result = _make_result()
        path = tmp_path / "export.md"
        returned = atomic_write_markdown_controlled_universe_export(result, path)
        assert returned == path
        text = path.read_text()
        assert "# Controlled Universe Export" in text


class TestWriteControlledUniverseExport:
    def test_writes_both_files(self, tmp_path: Path) -> None:
        result = _make_result()
        config = ControlledUniverseExportConfig(
            output_dir=str(tmp_path / "data"),
            markdown_output_dir=str(tmp_path / "reports"),
        )
        json_path, md_path = write_controlled_universe_export(result, config=config)
        assert json_path is not None
        assert md_path is not None
        assert json_path.exists()
        assert md_path.exists()
        data = json.loads(json_path.read_text())
        assert data["whitelist"] == ["BTC/USDT", "ETH/USDT"]
        text = md_path.read_text()
        assert "# Controlled Universe Export" in text

    def test_skips_when_filename_empty(self, tmp_path: Path) -> None:
        result = _make_result()
        config = ControlledUniverseExportConfig(
            output_dir=str(tmp_path / "data"),
            markdown_output_dir=str(tmp_path / "reports"),
            json_filename="",
            markdown_filename="",
        )
        json_path, md_path = write_controlled_universe_export(result, config=config)
        assert json_path is None
        assert md_path is None

    def test_uses_explicit_output_dir(self, tmp_path: Path) -> None:
        result = _make_result()
        config = ControlledUniverseExportConfig.default()
        json_path, md_path = write_controlled_universe_export(
            result, output_dir=str(tmp_path / "out"), config=config
        )
        assert json_path is not None
        assert md_path is not None
        assert json_path == tmp_path / "out" / "latest_export.json"
        assert md_path == Path(config.markdown_output_dir) / "latest_export.md"
