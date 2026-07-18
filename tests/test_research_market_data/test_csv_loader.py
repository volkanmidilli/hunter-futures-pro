"""Tests for hunter.research_market_data.csv_loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from hunter.research_market_data.csv_loader import (
    _is_forbidden_path,
    _project_root,
    load_csv_file,
)
from hunter.research_market_data.errors import (
    ResearchMarketDataError,
    ResearchMarketDataIOError,
    ResearchMarketDataValidationError,
)
from hunter.research_market_data.models import (
    EMPTY_FILE,
    FORBIDDEN_PATH,
    INVALID_FILE_PATH,
    MarketDataFileSpec,
    MISSING_COLUMN,
    MISSING_FILE,
)


def write_csv(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


class TestLoadCsvFile:
    def test_loads_valid_csv(self, tmp_path: Path) -> None:
        path = tmp_path / "BTCUSDT.csv"
        write_csv(
            path,
            "date,open,high,low,close,volume\n"
            "2024-01-01T00:00:00+00:00,100,110,90,105,1000\n"
            "2024-01-02T00:00:00+00:00,105,115,95,110,2000\n",
        )
        spec = MarketDataFileSpec(path=path, expected_symbol="BTCUSDT")
        source, rows = load_csv_file(spec)
        assert source.row_count == 2
        assert source.file_hash
        assert len(rows) == 2
        assert rows[0].timestamp_raw == "2024-01-01T00:00:00+00:00"
        assert rows[1].close_raw == "110"
        assert all(r.source is source for r in rows)

    def test_missing_file(self, tmp_path: Path) -> None:
        spec = MarketDataFileSpec(path=tmp_path / "missing.csv")
        with pytest.raises(ResearchMarketDataIOError) as exc:
            load_csv_file(spec)
        assert exc.value.reason_code == MISSING_FILE

    def test_invalid_spec(self) -> None:
        with pytest.raises(ResearchMarketDataIOError) as exc:
            load_csv_file("not_a_spec")  # type: ignore[arg-type]
        assert exc.value.reason_code == INVALID_FILE_PATH

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.csv"
        write_csv(path, "\n")
        with pytest.raises(ResearchMarketDataIOError) as exc:
            load_csv_file(MarketDataFileSpec(path=path))
        assert exc.value.reason_code == EMPTY_FILE

    def test_missing_column(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.csv"
        write_csv(path, "date,open,high,low,close\n2024-01-01,1,2,3,4\n")
        with pytest.raises(ResearchMarketDataValidationError) as exc:
            load_csv_file(MarketDataFileSpec(path=path))
        assert exc.value.reason_code == MISSING_COLUMN

    def test_header_aliases_accepted(self, tmp_path: Path) -> None:
        path = tmp_path / "aliased.csv"
        write_csv(
            path,
            "timestamp,open,high,low,close,vol\n"
            "2024-01-01T00:00:00+00:00,1,2,1,1.5,100\n",
        )
        source, rows = load_csv_file(MarketDataFileSpec(path=path))
        assert len(rows) == 1


class TestForbiddenPath:
    def test_data_path_is_forbidden(self) -> None:
        root = _project_root()
        assert _is_forbidden_path(root / "data" / "x.csv") is True

    def test_reports_path_is_forbidden(self) -> None:
        root = _project_root()
        assert _is_forbidden_path(root / "reports" / "x.csv") is True

    def test_tmp_path_is_allowed(self, tmp_path: Path) -> None:
        path = tmp_path / "x.csv"
        path.write_text("date,open,high,low,close,volume\n", encoding="utf-8")
        assert _is_forbidden_path(path) is False
        source, rows = load_csv_file(MarketDataFileSpec(path=path))
        assert source is not None

    def test_load_forbidden_path_raises(self, tmp_path: Path) -> None:
        root = _project_root()
        # Passing a forbidden path should raise even if the file does not exist,
        # because the forbidden check runs before the existence check.
        spec = MarketDataFileSpec(path=root / "data" / "not_there.csv")
        with pytest.raises(ResearchMarketDataIOError) as exc:
            load_csv_file(spec)
        assert exc.value.reason_code == FORBIDDEN_PATH
