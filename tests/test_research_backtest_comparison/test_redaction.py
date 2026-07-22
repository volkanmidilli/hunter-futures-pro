"""Tests for redaction utilities (MVP-65 Stage 5)."""

from __future__ import annotations

from pathlib import Path

from hunter.research_backtest_comparison.redaction import redact_path, redact_text


class TestRedactText:
    def test_empty(self) -> None:
        assert redact_text("") == ""

    def test_api_key_equals(self) -> None:
        text = "api_key=abcdef1234567890"
        redacted = redact_text(text)
        assert "abcdef1234567890" not in redacted
        assert "api_key=[REDACTED]" in redacted

    def test_api_key_colon(self) -> None:
        text = "api_key: abcdef1234567890"
        redacted = redact_text(text)
        assert "abcdef1234567890" not in redacted
        assert "api_key:[REDACTED]" in redacted

    def test_secret_colon(self) -> None:
        text = "secret: abcdef1234567890"
        redacted = redact_text(text)
        assert "abcdef1234567890" not in redacted
        assert "secret:[REDACTED]" in redacted

    def test_password_colon(self) -> None:
        text = "password: mysecret123456789"
        redacted = redact_text(text)
        assert "mysecret123456789" not in redacted
        assert "password:[REDACTED]" in redacted

    def test_token_colon(self) -> None:
        text = "token: xyz123456789012345"
        redacted = redact_text(text)
        assert "xyz123456789012345" not in redacted
        assert "token:[REDACTED]" in redacted

    def test_api_key_quoted(self) -> None:
        text = 'api_key: "abcdef1234567890"'
        redacted = redact_text(text)
        assert "abcdef1234567890" not in redacted

    def test_api_key_whitespace_around_separator(self) -> None:
        text = "api_key : abcdef1234567890"
        redacted = redact_text(text)
        assert "abcdef1234567890" not in redacted
        assert "api_key:[REDACTED]" in redacted

    def test_api_key_equals_whitespace(self) -> None:
        text = "api_key = abcdef1234567890"
        redacted = redact_text(text)
        assert "abcdef1234567890" not in redacted
        assert "api_key=[REDACTED]" in redacted

    def test_json_like_secret_text(self) -> None:
        text = '{"api_key": "abcdef1234567890", "secret": "ghijklmnop123456"}'
        redacted = redact_text(text)
        assert "abcdef1234567890" not in redacted
        assert "ghijklmnop123456" not in redacted

    def test_legitimate_non_secret_colon(self) -> None:
        text = "ratio: 1.23456, time: 2024-01-15T10:00:00Z"
        redacted = redact_text(text)
        assert "ratio: 1.23456" in redacted
        assert "2024-01-15T10:00:00Z" not in redacted  # timestamp still redacted

    def test_home_path(self) -> None:
        text = "error at /home/YOUR_USER/project/file.py"
        redacted = redact_text(text)
        assert "/home/YOUR_USER" not in redacted

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

    def test_metric_numbers_not_over_redacted(self) -> None:
        text = "return_pct: 12.34, drawdown: 5.67"
        redacted = redact_text(text)
        assert "12.34" in redacted
        assert "5.67" in redacted


class TestRedactPath:
    def test_redact_path(self) -> None:
        path = Path("/home/YOUR_USER/project/file.py")
        redacted = redact_path(path)
        assert "/home/YOUR_USER" not in redacted
