"""Read-only CSV candle loader for research market data (MVP-63 / SPEC-064)."""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Sequence
from pathlib import Path

from hunter.research_market_data.errors import (
    ResearchMarketDataIOError,
    ResearchMarketDataValidationError,
)
from hunter.research_market_data.models import (
    AMBIGUOUS_COLUMN,
    EMPTY_FILE,
    FORBIDDEN_PATH,
    INVALID_CSV_HEADER,
    MarketDataFileSpec,
    MarketDataSourceRef,
    MISSING_COLUMN,
    MISSING_FILE,
    RawCandleRow,
)

HEADER_ALIASES: dict[str, frozenset[str]] = {
    "date": frozenset({"date", "timestamp", "time", "datetime", "ts"}),
    "open": frozenset({"open"}),
    "high": frozenset({"high"}),
    "low": frozenset({"low"}),
    "close": frozenset({"close"}),
    "volume": frozenset({"volume", "vol"}),
}

REQUIRED_COLUMNS: tuple[str, ...] = ("date", "open", "high", "low", "close", "volume")


def _project_root() -> Path:
    """Return the project root inferred from this file's location."""
    return Path(__file__).resolve().parents[3]


def _is_forbidden_path(path: Path) -> bool:
    """Return True if the path is under ``data/`` or ``reports/``."""
    resolved = path.resolve()
    root = _project_root()
    data_dir = root / "data"
    reports_dir = root / "reports"
    try:
        resolved.relative_to(data_dir)
        return True
    except ValueError:
        pass
    try:
        resolved.relative_to(reports_dir)
        return True
    except ValueError:
        pass
    return False


def _file_hash(path: Path) -> str:
    """Return the SHA-256 hex digest of the file contents."""
    hasher = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _map_headers(fieldnames: Sequence[str] | None) -> dict[str, str]:
    """Map CSV header columns to canonical names.

    Returns a dictionary ``{canonical_name: original_column}``.
    Raises ``ResearchMarketDataValidationError`` on missing or ambiguous columns.
    """
    if fieldnames is None:
        raise ResearchMarketDataValidationError(
            INVALID_CSV_HEADER, "CSV has no header row"
        )
    normalized_fieldnames = {fn.strip().lower(): fn for fn in fieldnames if fn}
    mapping: dict[str, str] = {}
    for canonical in REQUIRED_COLUMNS:
        aliases = HEADER_ALIASES[canonical]
        matches = [col for key, col in normalized_fieldnames.items() if key in aliases]
        if not matches:
            raise ResearchMarketDataValidationError(
                MISSING_COLUMN, f"missing required column: {canonical}"
            )
        if len(matches) > 1:
            raise ResearchMarketDataValidationError(
                AMBIGUOUS_COLUMN,
                f"ambiguous column mapping for {canonical}: {matches}",
            )
        mapping[canonical] = matches[0]
    return mapping


def load_csv_file(
    spec: MarketDataFileSpec,
) -> tuple[MarketDataSourceRef, tuple[RawCandleRow, ...]]:
    """Load a CSV file into raw candle rows with full provenance.

    The file is read once for hashing and once for parsing. The loader is
    read-only, does not follow paths, and rejects paths inside ``data/`` or
    ``reports/``.
    """
    if not isinstance(spec, MarketDataFileSpec):
        raise ResearchMarketDataIOError(INVALID_FILE_PATH, "spec must be a MarketDataFileSpec")

    path = spec.path
    if _is_forbidden_path(path):
        raise ResearchMarketDataIOError(
            FORBIDDEN_PATH, f"path is forbidden: {path}"
        )

    if not path.exists():
        raise ResearchMarketDataIOError(MISSING_FILE, f"file does not exist: {path}")
    if not path.is_file():
        raise ResearchMarketDataIOError(MISSING_FILE, f"path is not a file: {path}")

    file_hash = _file_hash(path)
    label = spec.source_label or path.name

    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ResearchMarketDataIOError(EMPTY_FILE, f"file is empty: {path}")

    reader = csv.DictReader(text.splitlines())
    header_mapping = _map_headers(reader.fieldnames)

    rows: list[RawCandleRow] = []
    for line_number, record in enumerate(reader, start=2):
        rows.append(
            RawCandleRow(
                source=MarketDataSourceRef(
                    source_id=f"{path.name}:{file_hash}",
                    path=path,
                    label=label,
                    row_count=0,
                    file_hash=file_hash,
                ),
                line_number=line_number,
                timestamp_raw=record.get(header_mapping["date"], "").strip(),
                open_raw=record.get(header_mapping["open"], "").strip(),
                high_raw=record.get(header_mapping["high"], "").strip(),
                low_raw=record.get(header_mapping["low"], "").strip(),
                close_raw=record.get(header_mapping["close"], "").strip(),
                volume_raw=record.get(header_mapping["volume"], "").strip(),
            )
        )

    source_ref = MarketDataSourceRef(
        source_id=f"{path.name}:{file_hash}",
        path=path,
        label=label,
        row_count=len(rows),
        file_hash=file_hash,
    )
    rows = [
        RawCandleRow(
            source=source_ref,
            line_number=r.line_number,
            timestamp_raw=r.timestamp_raw,
            open_raw=r.open_raw,
            high_raw=r.high_raw,
            low_raw=r.low_raw,
            close_raw=r.close_raw,
            volume_raw=r.volume_raw,
        )
        for r in rows
    ]
    return source_ref, tuple(rows)
