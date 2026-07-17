"""Tests for redaction utilities (MVP-65 Stage 5)."""

from __future__ import annotations

from pathlib import Path

from hunter.research_backtest_comparison.redaction import redact_path, redact_text


class TestRedactText:
    def test_empty(self) -> None:
        assert redact_text("") == ""

    def test_api_key(self) -> None:
        text = "api_key=sk-live-1234567890abcdef"
        redacted = redact_text(text)
        assert "sk-live-1234567890abcdef" not in redacted

    def test_home_path(self) -> None:
        text = "error at /home/volkan/project/file.py"
        redacted = redact_text(text)
        assert "/home/volkan" not in redacted

    def test_absolute_tmp_path(self) -> None:
        text = "wrote to /tmp/hunter_backtest_abc123/result.json"
        redacted = redact_text(text)
        assert "/tmp/hunter_backtest_abc123/result.json" not in redacted

    def test_timestamp(self) -> None:
        text = "2024-01-15T10:30:00Z event"
        redacted = redact_text(text)
        assert "2024-01-15T10:30:00Z" not in redacted

    def test_pid(self) -> None:
        text = "process 12345 started"
        redacted = redact_text(text)
        assert "12345" not in redacted


class TestRedactPath:
    def test_redact_path(self) -> None:
        path = Path("/home/volkan/project/file.py")
        redacted = redact_path(path)
        assert "/home/volkan" not in redacted
