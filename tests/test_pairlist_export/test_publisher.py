"""Focused tests for hunter.pairlist_export.publisher (SPEC-074)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from hunter.pairlist_export import publisher
from hunter.pairlist_export.models import PairlistPublishError, PairlistRankingConfig
from hunter.pairlist_export.publisher import (
    atomic_write_text,
    pairlist_payload_dict,
    publish_pairlist,
    reject_forbidden_output_dir,
)
from hunter.pairlist_export.ranking_adapter import rank_pairs
from hunter.pairlist_export.validator import run_publish_gate


def _gate_output(pairs=("BTC/USDT:USDT", "ETH/USDT:USDT")):
    config = PairlistRankingConfig(min_pairs=1, publish_candidates=5, max_pairs=5)
    ranked = rank_pairs(
        config,
        pairs,
        rs_scores={p: Decimal("80") - i for i, p in enumerate(pairs)},
        oi_scores={p: Decimal("50") for p in pairs},
    )
    result = run_publish_gate(config, "2026-07-21", 10, ranked)
    assert result.allow_publish is True
    return result.pairlist_output


def test_atomic_write_text_creates_file_with_content(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "file.json"
    atomic_write_text(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"
    # No leftover temp files.
    assert list(target.parent.glob(".*")) == []


def test_reject_forbidden_output_dir_blocks_repo_data_and_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_data = tmp_path / "data"
    fake_reports = tmp_path / "reports"
    monkeypatch.setattr(publisher, "_FORBIDDEN_DIRS", (fake_data, fake_reports))

    with pytest.raises(PairlistPublishError):
        reject_forbidden_output_dir(fake_data)
    with pytest.raises(PairlistPublishError):
        reject_forbidden_output_dir(fake_reports / "nested")

    # An unrelated directory is allowed.
    reject_forbidden_output_dir(tmp_path / "user_data" / "pairlists")


def test_publish_pairlist_writes_native_and_audit_json(tmp_path: Path) -> None:
    output = _gate_output()
    pairlist_path, audit_path = publish_pairlist(output, tmp_path)

    pairlist_payload = json.loads(pairlist_path.read_text(encoding="utf-8"))
    assert pairlist_payload == pairlist_payload_dict(output)
    assert pairlist_payload["pairs"] == ["BTC/USDT:USDT", "ETH/USDT:USDT"]

    audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit_payload["fingerprint"] == output.audit.fingerprint
    assert audit_payload["selected_count"] == 2


def test_publish_pairlist_preserves_and_restores_previous_good_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    good_output = _gate_output(("BTC/USDT:USDT", "ETH/USDT:USDT"))
    pairlist_path, audit_path = publish_pairlist(good_output, tmp_path)
    good_pairlist_text = pairlist_path.read_text(encoding="utf-8")
    good_audit_text = audit_path.read_text(encoding="utf-8")

    bad_output = _gate_output(("SOL/USDT:USDT", "ADA/USDT:USDT"))

    original_write = publisher.atomic_write_text
    calls = {"audit_live_writes": 0}

    def flaky_write(path, content):
        if Path(path).name == publisher.AUDIT_FILENAME:
            calls["audit_live_writes"] += 1
            if calls["audit_live_writes"] == 1:
                raise RuntimeError("simulated audit write failure")
        return original_write(path, content)

    monkeypatch.setattr(publisher, "atomic_write_text", flaky_write)

    with pytest.raises(PairlistPublishError):
        publish_pairlist(bad_output, tmp_path)

    # Live files must still reflect the last good publish, not the failed one.
    assert pairlist_path.read_text(encoding="utf-8") == good_pairlist_text
    assert audit_path.read_text(encoding="utf-8") == good_audit_text

    previous_good_pairlist = pairlist_path.with_name(pairlist_path.name + ".previous-good")
    previous_good_audit = audit_path.with_name(audit_path.name + ".previous-good")
    assert previous_good_pairlist.read_text(encoding="utf-8") == good_pairlist_text
    assert previous_good_audit.read_text(encoding="utf-8") == good_audit_text


def test_publish_pairlist_rolls_back_first_ever_publish_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad_output = _gate_output(("SOL/USDT:USDT", "ADA/USDT:USDT"))

    original_write = publisher.atomic_write_text

    def flaky_write(path, content):
        if Path(path).name == publisher.AUDIT_FILENAME:
            raise RuntimeError("simulated audit write failure")
        return original_write(path, content)

    monkeypatch.setattr(publisher, "atomic_write_text", flaky_write)

    with pytest.raises(PairlistPublishError):
        publish_pairlist(bad_output, tmp_path)

    # No prior good version existed, so a failed first publish must leave no
    # partial pairlist/audit pair behind.
    assert not (tmp_path / publisher.PAIRLIST_FILENAME).exists()
    assert not (tmp_path / publisher.AUDIT_FILENAME).exists()


def test_publish_pairlist_wraps_previous_good_backup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # First publish so a previous-good backup step is attempted on the second.
    publish_pairlist(_gate_output(), tmp_path)

    def always_fail(path, content):
        raise RuntimeError("simulated disk failure during backup")

    monkeypatch.setattr(publisher, "atomic_write_text", always_fail)

    with pytest.raises(PairlistPublishError):
        publish_pairlist(_gate_output(("SOL/USDT:USDT", "ADA/USDT:USDT")), tmp_path)
