import logging
import json
import pytest

from hunter.core.logging import JSONFormatter, RedactingFilter, setup_logging


class TestJSONFormatter:
    """JSONFormatter outputs structured JSON logs."""

    def test_basic_json_format(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="hunter.test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "hunter.test"
        assert parsed["message"] == "Test message"
        assert "timestamp" in parsed

    def test_correlation_id(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="hunter.test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "abc-123"
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["correlation_id"] == "abc-123"

    def test_context(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="hunter.test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.context = {"symbol": "BTCUSDT"}
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["context"]["symbol"] == "BTCUSDT"

    def test_exception_info(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            record = logging.LogRecord(
                name="hunter.test",
                level=logging.ERROR,
                pathname="",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert "test error" in parsed["exception"]


class TestRedactingFilter:
    """RedactingFilter removes secrets from log context."""

    def test_redacts_api_key(self):
        filter_ = RedactingFilter()
        record = logging.LogRecord(
            name="hunter.test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.context = {"api_key": "secret123", "safe": "value"}
        filter_.filter(record)
        assert record.context["api_key"] == "[REDACTED]"
        assert record.context["safe"] == "value"

    def test_redacts_secret(self):
        filter_ = RedactingFilter()
        record = logging.LogRecord(
            name="hunter.test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.context = {"secret": "hidden", "password": "pass123"}
        filter_.filter(record)
        assert record.context["secret"] == "[REDACTED]"
        assert record.context["password"] == "[REDACTED]"

    def test_redacts_token(self):
        filter_ = RedactingFilter()
        record = logging.LogRecord(
            name="hunter.test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.context = {"token": "bearer_token"}
        filter_.filter(record)
        assert record.context["token"] == "[REDACTED]"

    def test_redacts_private_key(self):
        filter_ = RedactingFilter()
        record = logging.LogRecord(
            name="hunter.test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.context = {"private_key": "-----BEGIN RSA PRIVATE KEY-----"}
        filter_.filter(record)
        assert record.context["private_key"] == "[REDACTED]"

    def test_redacts_nested_dict(self):
        filter_ = RedactingFilter()
        record = logging.LogRecord(
            name="hunter.test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.context = {"nested": {"api_key": "secret", "safe": "ok"}}
        filter_.filter(record)
        assert record.context["nested"]["api_key"] == "[REDACTED]"
        assert record.context["nested"]["safe"] == "ok"

    def test_redacts_list_items(self):
        filter_ = RedactingFilter()
        record = logging.LogRecord(
            name="hunter.test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.context = {"items": [{"api_key": "secret"}, {"safe": "ok"}]}
        filter_.filter(record)
        assert record.context["items"][0]["api_key"] == "[REDACTED]"
        assert record.context["items"][1]["safe"] == "ok"

    def test_no_context_passes_through(self):
        filter_ = RedactingFilter()
        record = logging.LogRecord(
            name="hunter.test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        result = filter_.filter(record)
        assert result is True


class TestSetupLogging:
    """setup_logging configures logging correctly."""

    def test_creates_log_directory(self, tmp_path):
        log_dir = tmp_path / "test_logs"
        setup_logging(log_dir=str(log_dir))
        assert log_dir.exists()

    def test_sets_log_level(self, tmp_path):
        log_dir = tmp_path / "test_logs"
        setup_logging(log_level="DEBUG", log_dir=str(log_dir))
        logger = logging.getLogger("hunter")
        assert logger.level == logging.DEBUG

    def test_json_console_format(self, tmp_path, capsys):
        log_dir = tmp_path / "test_logs"
        setup_logging(json_format=True, log_dir=str(log_dir))
        logger = logging.getLogger("hunter.test")
        logger.info("JSON test")
        captured = capsys.readouterr()
        # Console output should be JSON when json_format=True
        assert "JSON test" in captured.out

    def test_file_handler_always_json(self, tmp_path):
        log_dir = tmp_path / "test_logs"
        setup_logging(log_dir=str(log_dir))
        logger = logging.getLogger("hunter.test")
        logger.info("File test")
        log_file = log_dir / "hunter.log"
        assert log_file.exists()
        content = log_file.read_text()
        parsed = json.loads(content.strip())
        assert parsed["message"] == "File test"
        assert parsed["level"] == "INFO"

    def test_redacting_filter_on_file_handler(self, tmp_path):
        log_dir = tmp_path / "test_logs"
        setup_logging(log_dir=str(log_dir))
        logger = logging.getLogger("hunter.test")
        record = logging.LogRecord(
            name="hunter.test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="Secret test",
            args=(),
            exc_info=None,
        )
        record.context = {"api_key": "secret123"}
        logger.handle(record)
        log_file = log_dir / "hunter.log"
        content = log_file.read_text()
        parsed = json.loads(content.strip())
        assert parsed["context"]["api_key"] == "[REDACTED]"
