"""Tests for workspace management (MVP-65 Stage 2)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from hunter.research_backtest_comparison.fixture_models import (
    ExternalFixtureManifest,
    FixtureFileRecord,
)
from hunter.research_backtest_comparison.workspace import BacktestWorkspace, create_workspace


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class TestBacktestWorkspace:
    def test_create_and_cleanup(self) -> None:
        ws = create_workspace(prefix="test_ws_")
        ws.create()
        path = ws.path
        assert path.exists()
        assert ws.userdir.exists()
        assert (ws.userdir / "strategies").exists()
        assert ws.config_path.parent.exists()
        ws.cleanup()
        assert not path.exists()

    def test_context_manager_cleanup(self) -> None:
        with create_workspace(prefix="test_ctx_") as ws:
            path = ws.path
            assert path.exists()
        assert not path.exists()

    def test_context_manager_retain_on_failure(self) -> None:
        ws = create_workspace(prefix="test_ret_", retain_on_failure=True)
        path: Path | None = None
        try:
            with ws:
                path = ws.path
                raise ValueError("boom")
        except ValueError:
            pass
        assert path is not None
        assert path.exists()
        ws.cleanup()
        assert not path.exists()

    def test_path_before_create(self) -> None:
        ws = create_workspace()
        with pytest.raises(RuntimeError):
            _ = ws.path

    def test_double_create(self) -> None:
        ws = create_workspace(prefix="test_double_")
        ws.create()
        with pytest.raises(RuntimeError):
            ws.create()
        ws.cleanup()


class TestMaterializeFixtureData:
    def _make_manifest(self, files: tuple[FixtureFileRecord, ...]) -> ExternalFixtureManifest:
        return ExternalFixtureManifest(
            fixture_schema_version="fixture-schema-v1",
            exchange_identifier="binance",
            trading_mode="futures",
            timeframe="5m",
            pair_list=("BTC/USDT:USDT",),
            timerange="20240101-20240201",
            expected_strategy_class="TestStrategy",
            provenance_note="test fixture",
            files=files,
        )

    def test_valid_fixture_materialized(self, tmp_path: Path) -> None:
        fixture_root = tmp_path / "fixture"
        (fixture_root / "futures").mkdir(parents=True)
        content = b"candle data"
        (fixture_root / "futures" / "btc.json").write_bytes(content)
        manifest = self._make_manifest(
            (
                FixtureFileRecord(
                    relative_path="futures/btc.json",
                    sha256=_sha256(content),
                ),
            )
        )
        ws = create_workspace(prefix="test_materialize_")
        ws.create()
        try:
            data_dir = ws.materialize_fixture_data(fixture_root, manifest)
            assert data_dir == ws.data_dir
            materialized = data_dir / "futures" / "btc.json"
            assert materialized.exists()
            assert materialized.read_bytes() == content
            # Materialized copy is isolated from the external fixture root.
            assert not materialized.is_symlink()
        finally:
            ws.cleanup(force=True)

    def test_hash_mismatch_rejected(self, tmp_path: Path) -> None:
        fixture_root = tmp_path / "fixture"
        (fixture_root / "futures").mkdir(parents=True)
        (fixture_root / "futures" / "btc.json").write_bytes(b"candle data")
        manifest = self._make_manifest(
            (
                FixtureFileRecord(
                    relative_path="futures/btc.json",
                    sha256="0" * 64,
                ),
            )
        )
        ws = create_workspace(prefix="test_materialize_bad_hash_")
        ws.create()
        try:
            with pytest.raises(RuntimeError):
                ws.materialize_fixture_data(fixture_root, manifest)
        finally:
            ws.cleanup(force=True)

    def test_symlink_file_rejected(self, tmp_path: Path) -> None:
        fixture_root = tmp_path / "fixture"
        fixture_root.mkdir()
        outside = tmp_path / "outside.json"
        content = b"outside data"
        outside.write_bytes(content)
        symlink = fixture_root / "btc.json"
        symlink.symlink_to(outside)
        manifest = self._make_manifest(
            (
                FixtureFileRecord(
                    relative_path="btc.json",
                    sha256=_sha256(content),
                ),
            )
        )
        ws = create_workspace(prefix="test_materialize_symlink_")
        ws.create()
        try:
            with pytest.raises(RuntimeError):
                ws.materialize_fixture_data(fixture_root, manifest)
        finally:
            ws.cleanup(force=True)

    def test_path_escape_rejected(self, tmp_path: Path) -> None:
        fixture_root = tmp_path / "fixture"
        fixture_root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        content = b"outside data"
        (outside / "secret.json").write_bytes(content)
        # A symlinked directory component that escapes the fixture root.
        (fixture_root / "escape").symlink_to(outside)
        manifest = self._make_manifest(
            (
                FixtureFileRecord(
                    relative_path="escape/secret.json",
                    sha256=_sha256(content),
                ),
            )
        )
        ws = create_workspace(prefix="test_materialize_escape_")
        ws.create()
        try:
            with pytest.raises(RuntimeError):
                ws.materialize_fixture_data(fixture_root, manifest)
        finally:
            ws.cleanup(force=True)

    def test_fixture_fingerprint_deterministic_after_materialization(
        self, tmp_path: Path
    ) -> None:
        from hunter.research_backtest_comparison.fixture_validator import (
            compute_fixture_fingerprint,
        )

        fixture_root = tmp_path / "fixture"
        (fixture_root / "futures").mkdir(parents=True)
        content = b"candle data"
        (fixture_root / "futures" / "btc.json").write_bytes(content)
        manifest = self._make_manifest(
            (
                FixtureFileRecord(
                    relative_path="futures/btc.json",
                    sha256=_sha256(content),
                ),
            )
        )
        fp_before = compute_fixture_fingerprint(manifest)
        ws = create_workspace(prefix="test_materialize_fp_")
        ws.create()
        try:
            ws.materialize_fixture_data(fixture_root, manifest)
            fp_after = compute_fixture_fingerprint(manifest)
            assert fp_before == fp_after
        finally:
            ws.cleanup(force=True)
