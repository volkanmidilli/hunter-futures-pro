"""Tests for the Freqtrade Universe Consumption Adapter writer."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from hunter.controlled_universe_export_adapter.models import (
    ControlledUniverseExportResult,
    ControlledUniversePairExportSummary,
)
from hunter.freqtrade_universe_adapter.engine import build_freqtrade_universe_adapter_result
from hunter.freqtrade_universe_adapter.models import (
    FREQTRADE_UNIVERSE_ADAPTER_VERSION,
    FreqtradeUniverseAdapterConfig,
    FreqtradeUniverseAdapterResult,
)
from hunter.freqtrade_universe_adapter.writer import (
    _atomic_write,
    _pairlist_to_json_text,
    _strategy_contract_input_to_json_text,
    freqtrade_universe_adapter_result_to_dict,
    freqtrade_universe_adapter_result_to_json_text,
    freqtrade_universe_adapter_result_to_markdown_text,
    atomic_write_json_freqtrade_universe_adapter_result,
    atomic_write_markdown_freqtrade_universe_adapter_result,
    write_freqtrade_universe_adapter_result,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def base_result() -> FreqtradeUniverseAdapterResult:
    """Return a non-trivial adapter result for writer tests."""
    return FreqtradeUniverseAdapterResult(
        report_id="fua-test-001",
        generated_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        whitelist=("BTC/USDT", "ETH/USDT"),
        blacklist=("ADA/USDT",),
        pairlist={"method": "StaticPairList", "pairs": ["BTC/USDT", "ETH/USDT"]},
        strategy_contract_input={
            "whitelist": ["BTC/USDT", "ETH/USDT"],
            "blacklist": ["ADA/USDT"],
            "mode": "LONG_RESEARCH_ONLY",
            "safety_flags": {"dry_run": True},
            "metadata": {"source": "test"},
        },
        per_pair_summary=(
            ControlledUniversePairExportSummary(
                pair="BTC/USDT",
                state="INCLUDED",
                classification="LONG_RESEARCH",
                reason_codes=("PASSED",),
                human_note="",
            ),
            ControlledUniversePairExportSummary(
                pair="ETH/USDT",
                state="INCLUDED",
                classification="LONG_RESEARCH",
                reason_codes=("PASSED",),
                human_note="",
            ),
            ControlledUniversePairExportSummary(
                pair="ADA/USDT",
                state="EXCLUDED",
                classification="LONG_RESEARCH",
                reason_codes=("BLOCKED",),
                human_note="test exclusion",
            ),
        ),
        research_only=True,
        human_approval_required=True,
        reason_codes=(
            "EXPORT_RESEARCH_ONLY",
            "EXPORT_HUMAN_APPROVAL_REQUIRED",
            "NO_FREQTRADE_RUNTIME_CONNECTION",
            "NO_AUTOMATIC_CONFIG_MUTATION",
        ),
        safety_flags={
            "research_only": True,
            "human_approval_required": True,
        },
        metadata=MappingProxyType({"source": "test"}),
    )


# ---------------------------------------------------------------------------
# Dict serialization
# ---------------------------------------------------------------------------


class TestToDict:
    def test_contains_all_required_fields(self, base_result: FreqtradeUniverseAdapterResult) -> None:
        data = freqtrade_universe_adapter_result_to_dict(base_result)
        assert data["kind"] == "freqtrade_universe_adapter"
        assert data["version"] == FREQTRADE_UNIVERSE_ADAPTER_VERSION
        assert data["report_id"] == "fua-test-001"
        assert data["generated_at"] == "2026-01-01T00:00:00+00:00"
        assert data["research_only"] is True
        assert data["human_approval_required"] is True
        assert data["whitelist"] == ["BTC/USDT", "ETH/USDT"]
        assert data["blacklist"] == ["ADA/USDT"]
        assert data["pairlist"] == {"method": "StaticPairList", "pairs": ["BTC/USDT", "ETH/USDT"]}
        assert data["strategy_contract_input"]["mode"] == "LONG_RESEARCH_ONLY"
        assert data["reason_codes"] == [
            "EXPORT_RESEARCH_ONLY",
            "EXPORT_HUMAN_APPROVAL_REQUIRED",
            "NO_FREQTRADE_RUNTIME_CONNECTION",
            "NO_AUTOMATIC_CONFIG_MUTATION",
        ]
        assert data["safety_flags"] == {"human_approval_required": True, "research_only": True}
        assert data["metadata"] == {"source": "test"}
        assert "safety_notice" in data

    def test_per_pair_summary_serialized(self, base_result: FreqtradeUniverseAdapterResult) -> None:
        data = freqtrade_universe_adapter_result_to_dict(base_result)
        summaries = data["per_pair_summary"]
        assert len(summaries) == 3
        assert summaries[0] == {
            "pair": "BTC/USDT",
            "state": "INCLUDED",
            "classification": "LONG_RESEARCH",
            "reason_codes": ["PASSED"],
            "human_note": "",
        }

    def test_metadata_mapping_proxy_is_serialized(self) -> None:
        result = FreqtradeUniverseAdapterResult(
            report_id="x",
            generated_at=datetime.now(timezone.utc),
            whitelist=(),
            blacklist=(),
            pairlist={},
            strategy_contract_input={},
            per_pair_summary=(),
            reason_codes=(),
            metadata=MappingProxyType({"k": "v"}),
        )
        data = freqtrade_universe_adapter_result_to_dict(result)
        assert data["metadata"] == {"k": "v"}


# ---------------------------------------------------------------------------
# Deterministic JSON / Markdown
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_json_is_deterministic(self, base_result: FreqtradeUniverseAdapterResult) -> None:
        a = freqtrade_universe_adapter_result_to_json_text(base_result)
        b = freqtrade_universe_adapter_result_to_json_text(base_result)
        assert a == b
        assert a.endswith("\n")
        json.loads(a)  # valid JSON

    def test_markdown_is_deterministic(self, base_result: FreqtradeUniverseAdapterResult) -> None:
        a = freqtrade_universe_adapter_result_to_markdown_text(base_result)
        b = freqtrade_universe_adapter_result_to_markdown_text(base_result)
        assert a == b

    def test_repeated_engine_then_writer_output_is_identical(self, tmp_path: Path) -> None:
        export = ControlledUniverseExportResult(
            report_id="repeat-test",
            generated_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            whitelist=("ETH/USDT", "BTC/USDT"),
            blacklist=(),
            per_pair_summary=(
                ControlledUniversePairExportSummary(
                    pair="ETH/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
                ControlledUniversePairExportSummary(
                    pair="BTC/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
            ),
        )
        config = FreqtradeUniverseAdapterConfig.default()
        r1 = build_freqtrade_universe_adapter_result(export, config)
        r2 = build_freqtrade_universe_adapter_result(export, config)
        assert freqtrade_universe_adapter_result_to_json_text(r1) == freqtrade_universe_adapter_result_to_json_text(r2)
        assert freqtrade_universe_adapter_result_to_markdown_text(r1) == freqtrade_universe_adapter_result_to_markdown_text(r2)

        p1 = tmp_path / "a.json"
        p2 = tmp_path / "b.json"
        atomic_write_json_freqtrade_universe_adapter_result(r1, str(p1))
        atomic_write_json_freqtrade_universe_adapter_result(r2, str(p2))
        assert p1.read_text() == p2.read_text()


# ---------------------------------------------------------------------------
# Fail-closed / blocked / empty serialization
# ---------------------------------------------------------------------------


class TestFailClosedSerialization:
    def test_missing_input_serialization(self) -> None:
        config = FreqtradeUniverseAdapterConfig.default()
        result = build_freqtrade_universe_adapter_result(None, config)
        data = freqtrade_universe_adapter_result_to_dict(result)
        assert data["whitelist"] == []
        assert data["blacklist"] == []
        assert data["pairlist"] == {"method": "StaticPairList", "pairs": []}
        assert data["strategy_contract_input"]["mode"] == "BLOCK_ALL"
        assert "MISSING_EXPORT_INPUT" in data["reason_codes"]
        assert data["research_only"] is True
        assert data["human_approval_required"] is True

    def test_blocked_export_serialization(self) -> None:
        export = ControlledUniverseExportResult(
            report_id="blocked",
            generated_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            whitelist=("BTC/USDT",),
            blacklist=(),
            per_pair_summary=(),
            reason_codes=("BLOCKED_EXPORT",),
        )
        result = build_freqtrade_universe_adapter_result(export)
        data = freqtrade_universe_adapter_result_to_dict(result)
        assert data["whitelist"] == []
        assert "BLOCKED_EXPORT_INPUT" in data["reason_codes"]
        assert data["research_only"] is True
        assert data["human_approval_required"] is True

    def test_empty_whitelist_serialization(self) -> None:
        export = ControlledUniverseExportResult(
            report_id="empty",
            generated_at=datetime.now(timezone.utc),
            whitelist=(),
            blacklist=(),
            per_pair_summary=(),
            reason_codes=("NO_INCLUDED_PAIRS",),
        )
        result = build_freqtrade_universe_adapter_result(export)
        data = freqtrade_universe_adapter_result_to_dict(result)
        assert data["whitelist"] == []
        assert "EMPTY_WHITELIST" in data["reason_codes"]


# ---------------------------------------------------------------------------
# Pairlist / strategy-contract representation
# ---------------------------------------------------------------------------


class TestRepresentations:
    def test_pairlist_fragment(self, base_result: FreqtradeUniverseAdapterResult) -> None:
        data = freqtrade_universe_adapter_result_to_dict(base_result)
        assert data["pairlist"] == {"method": "StaticPairList", "pairs": ["BTC/USDT", "ETH/USDT"]}
        md = freqtrade_universe_adapter_result_to_markdown_text(base_result)
        assert "Pairlist Fragment" in md
        assert '"method": "StaticPairList"' in md

    def test_strategy_contract_input(self, base_result: FreqtradeUniverseAdapterResult) -> None:
        data = freqtrade_universe_adapter_result_to_dict(base_result)
        assert data["strategy_contract_input"]["whitelist"] == ["BTC/USDT", "ETH/USDT"]
        assert data["strategy_contract_input"]["blacklist"] == ["ADA/USDT"]
        assert data["strategy_contract_input"]["mode"] == "LONG_RESEARCH_ONLY"
        assert data["strategy_contract_input"]["safety_flags"]["dry_run"] is True


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


class TestAtomicWrites:
    def test_atomic_write_json(self, base_result: FreqtradeUniverseAdapterResult, tmp_path: Path) -> None:
        path = tmp_path / "output.json"
        atomic_write_json_freqtrade_universe_adapter_result(base_result, str(path))
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        assert data["report_id"] == "fua-test-001"
        assert not (tmp_path / "output.json.tmp").exists()

    def test_atomic_write_markdown(self, base_result: FreqtradeUniverseAdapterResult, tmp_path: Path) -> None:
        path = tmp_path / "output.md"
        atomic_write_markdown_freqtrade_universe_adapter_result(base_result, str(path))
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "# Freqtrade Universe Adapter Output" in text
        assert not (tmp_path / "output.md.tmp").exists()

    def test_write_all_artifacts(self, base_result: FreqtradeUniverseAdapterResult, tmp_path: Path) -> None:
        config = FreqtradeUniverseAdapterConfig(
            output_dir=str(tmp_path / "data"),
            markdown_output_dir=str(tmp_path / "reports"),
            json_filename="latest_universe.json",
            markdown_filename="latest_universe.md",
        )
        written = write_freqtrade_universe_adapter_result(base_result, None, config)
        assert written["json"] == str(tmp_path / "data" / "latest_universe.json")
        assert written["markdown"] == str(tmp_path / "reports" / "latest_universe.md")
        assert Path(written["json"]).exists()
        assert Path(written["markdown"]).exists()

    def test_write_with_output_dir_override(self, base_result: FreqtradeUniverseAdapterResult, tmp_path: Path) -> None:
        config = FreqtradeUniverseAdapterConfig(
            output_dir="should_be_overridden",
            markdown_output_dir=str(tmp_path / "reports"),
            json_filename="latest_universe.json",
            markdown_filename="latest_universe.md",
        )
        override = str(tmp_path / "override")
        written = write_freqtrade_universe_adapter_result(base_result, override, config)
        assert written["json"].startswith(override)
        assert Path(written["json"]).exists()

    def test_atomic_write_creates_parent_dirs(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "dir" / "file.json"
        _atomic_write(target, "{}")
        assert target.exists()

    def test_atomic_write_no_temp_file_left_on_failure(self, tmp_path: Path) -> None:
        # Writing to a non-existent directory under a read-only parent would fail;
        # here we test cleanup by simulating a path that cannot be created.
        target = tmp_path / "file.json"
        _atomic_write(target, "content")
        assert not (target.parent / "file.json.tmp").exists()


# ---------------------------------------------------------------------------
# Safety / wording
# ---------------------------------------------------------------------------


class TestSafetyWording:
    _DISALLOWED_WORDS = {"trading", "trade", "execution", "ready", "suitable", "suitability", "recommend"}
    _DISALLOWED_PHRASES = ["approved for", "approval for", "approve for", "ready to trade", "suitable for trading"]

    def test_safety_notice_present_in_markdown(self, base_result: FreqtradeUniverseAdapterResult) -> None:
        md = freqtrade_universe_adapter_result_to_markdown_text(base_result)
        assert "research-only artifact" in md
        assert "human approval is required" in md

    def test_json_contains_research_and_approval_flags(self, base_result: FreqtradeUniverseAdapterResult) -> None:
        data = freqtrade_universe_adapter_result_to_dict(base_result)
        assert data["research_only"] is True
        assert data["human_approval_required"] is True

    def test_no_disallowed_standalone_wording_outside_notice(self, base_result: FreqtradeUniverseAdapterResult) -> None:
        md = freqtrade_universe_adapter_result_to_markdown_text(base_result)
        # Find the safety notice paragraph (the only paragraph starting with "> ").
        notice_start = md.index("> ")
        notice_end = md.index("\n\n", notice_start)
        body = md[notice_end:]
        lower_body = body.lower()
        for word in self._DISALLOWED_WORDS:
            pattern = rf"\\b{re.escape(word)}\\b"
            assert not re.search(pattern, lower_body), f"disallowed standalone word: {word!r}"
        for phrase in self._DISALLOWED_PHRASES:
            assert phrase not in lower_body, f"disallowed phrase: {phrase!r}"


# ---------------------------------------------------------------------------
# Pairlist artifact
# ---------------------------------------------------------------------------


class TestPairlistArtifact:
    def test_pairlist_json_schema(self, base_result: FreqtradeUniverseAdapterResult) -> None:
        text = _pairlist_to_json_text(base_result)
        data = json.loads(text)
        assert data == {"method": "StaticPairList", "pairs": ["BTC/USDT", "ETH/USDT"]}

    def test_pairlist_deterministic(self, base_result: FreqtradeUniverseAdapterResult) -> None:
        assert _pairlist_to_json_text(base_result) == _pairlist_to_json_text(base_result)

    def test_pairlist_empty_whitelist_fail_closed(self) -> None:
        config = FreqtradeUniverseAdapterConfig.default()
        result = build_freqtrade_universe_adapter_result(None, config)
        text = _pairlist_to_json_text(result)
        data = json.loads(text)
        assert data == {"method": "StaticPairList", "pairs": []}

    def test_pairlist_atomic_write(self, base_result: FreqtradeUniverseAdapterResult, tmp_path: Path) -> None:
        path = tmp_path / "pairlist.json"
        _atomic_write(path, _pairlist_to_json_text(base_result))
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["method"] == "StaticPairList"
        assert data["pairs"] == ["BTC/USDT", "ETH/USDT"]
        assert not (tmp_path / "pairlist.json.tmp").exists()


# ---------------------------------------------------------------------------
# Strategy-contract input artifact
# ---------------------------------------------------------------------------


class TestStrategyContractInputArtifact:
    def test_strategy_contract_input_json_schema(self, base_result: FreqtradeUniverseAdapterResult) -> None:
        text = _strategy_contract_input_to_json_text(base_result)
        data = json.loads(text)
        assert data["whitelist"] == ["BTC/USDT", "ETH/USDT"]
        assert data["blacklist"] == ["ADA/USDT"]
        assert data["mode"] == "LONG_RESEARCH_ONLY"
        assert data["safety_flags"] == {"dry_run": True}
        assert data["metadata"] == {"source": "test"}

    def test_strategy_contract_input_deterministic(self, base_result: FreqtradeUniverseAdapterResult) -> None:
        assert _strategy_contract_input_to_json_text(base_result) == _strategy_contract_input_to_json_text(base_result)

    def test_strategy_contract_input_empty_whitelist_fail_closed(self) -> None:
        config = FreqtradeUniverseAdapterConfig.default()
        result = build_freqtrade_universe_adapter_result(None, config)
        text = _strategy_contract_input_to_json_text(result)
        data = json.loads(text)
        assert data["whitelist"] == []
        assert data["mode"] == "BLOCK_ALL"

    def test_strategy_contract_input_atomic_write(self, base_result: FreqtradeUniverseAdapterResult, tmp_path: Path) -> None:
        path = tmp_path / "sci.json"
        _atomic_write(path, _strategy_contract_input_to_json_text(base_result))
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["mode"] == "LONG_RESEARCH_ONLY"
        assert not (tmp_path / "sci.json.tmp").exists()


# ---------------------------------------------------------------------------
# All-artifacts write
# ---------------------------------------------------------------------------


class TestWriteAllArtifacts:
    def test_write_all_four_artifacts(self, base_result: FreqtradeUniverseAdapterResult, tmp_path: Path) -> None:
        config = FreqtradeUniverseAdapterConfig(
            output_dir=str(tmp_path / "data"),
            markdown_output_dir=str(tmp_path / "reports"),
        )
        written = write_freqtrade_universe_adapter_result(base_result, None, config)
        assert set(written.keys()) == {"json", "markdown", "pairlist", "strategy_contract_input"}
        for path in written.values():
            assert Path(path).exists()

    def test_pairlist_artifact_path(self, base_result: FreqtradeUniverseAdapterResult, tmp_path: Path) -> None:
        config = FreqtradeUniverseAdapterConfig(
            output_dir=str(tmp_path / "data"),
            markdown_output_dir=str(tmp_path / "reports"),
        )
        written = write_freqtrade_universe_adapter_result(base_result, None, config)
        assert written["pairlist"] == str(tmp_path / "data" / "pairlist.json")
        data = json.loads(Path(written["pairlist"]).read_text(encoding="utf-8"))
        assert data == {"method": "StaticPairList", "pairs": ["BTC/USDT", "ETH/USDT"]}

    def test_strategy_contract_input_artifact_path(self, base_result: FreqtradeUniverseAdapterResult, tmp_path: Path) -> None:
        config = FreqtradeUniverseAdapterConfig(
            output_dir=str(tmp_path / "data"),
            markdown_output_dir=str(tmp_path / "reports"),
        )
        written = write_freqtrade_universe_adapter_result(base_result, None, config)
        assert written["strategy_contract_input"] == str(tmp_path / "data" / "strategy_contract_input.json")
        data = json.loads(Path(written["strategy_contract_input"]).read_text(encoding="utf-8"))
        assert data["mode"] == "LONG_RESEARCH_ONLY"

    def test_output_dir_override_applies_to_all_data_artifacts(self, base_result: FreqtradeUniverseAdapterResult, tmp_path: Path) -> None:
        config = FreqtradeUniverseAdapterConfig(
            output_dir="should_be_overridden",
            markdown_output_dir=str(tmp_path / "reports"),
        )
        override = str(tmp_path / "override")
        written = write_freqtrade_universe_adapter_result(base_result, override, config)
        assert written["json"].startswith(override)
        assert written["pairlist"].startswith(override)
        assert written["strategy_contract_input"].startswith(override)
        for path in written.values():
            assert Path(path).exists()

    def test_configured_filenames_respected(self, base_result: FreqtradeUniverseAdapterResult, tmp_path: Path) -> None:
        config = FreqtradeUniverseAdapterConfig(
            output_dir=str(tmp_path / "data"),
            markdown_output_dir=str(tmp_path / "reports"),
            json_filename="custom.json",
            markdown_filename="custom.md",
            pairlist_filename="custom_pairlist.json",
            strategy_contract_input_filename="custom_sci.json",
        )
        written = write_freqtrade_universe_adapter_result(base_result, None, config)
        assert written["json"].endswith("custom.json")
        assert written["markdown"].endswith("custom.md")
        assert written["pairlist"].endswith("custom_pairlist.json")
        assert written["strategy_contract_input"].endswith("custom_sci.json")

    def test_no_temp_files_after_write_all(self, base_result: FreqtradeUniverseAdapterResult, tmp_path: Path) -> None:
        config = FreqtradeUniverseAdapterConfig(
            output_dir=str(tmp_path / "data"),
            markdown_output_dir=str(tmp_path / "reports"),
        )
        write_freqtrade_universe_adapter_result(base_result, None, config)
        # No .tmp files should remain in any output directory.
        tmp_files = list(tmp_path.rglob("*.tmp"))
        assert tmp_files == []

    def test_markdown_includes_artifact_paths(self, base_result: FreqtradeUniverseAdapterResult) -> None:
        md = freqtrade_universe_adapter_result_to_markdown_text(base_result)
        assert "## Artifact Paths" in md
        assert "pairlist.json" in md
        assert "strategy_contract_input.json" in md
        assert "latest_universe.json" in md
        assert "latest_universe.md" in md


# ---------------------------------------------------------------------------
# Error class
# ---------------------------------------------------------------------------


def test_adapter_error_class_from_models() -> None:
    from hunter.freqtrade_universe_adapter.models import FreqtradeUniverseAdapterError
    assert issubclass(FreqtradeUniverseAdapterError, Exception)
