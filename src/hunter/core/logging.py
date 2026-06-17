import logging
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add correlation ID if available
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id

        # Add extra context if available
        if hasattr(record, "context") and record.context is not None:
            log_data["context"] = record.context

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class RedactingFilter(logging.Filter):
    """Filter that redacts sensitive values from log records."""

    SENSITIVE_KEYS = {"api_key", "secret", "password", "token", "private_key"}

    def _redact(self, data: Any) -> Any:
        """Recursively redact sensitive keys from dicts and lists."""
        if isinstance(data, dict):
            return {
                k: "[REDACTED]" if k.lower() in self.SENSITIVE_KEYS else self._redact(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._redact(item) for item in data]
        return data

    def filter(self, record: logging.LogRecord) -> bool:
        # Redact sensitive keys from any dict context
        if hasattr(record, "context") and isinstance(record.context, dict):
            record.context = self._redact(record.context)
        return True


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
    json_format: bool = False,
) -> None:
    """Configure structured logging with console and rotating file handlers.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        log_dir: Directory for log files.
        json_format: If True, output JSON to console. Otherwise human-readable text.
    """
    from logging.handlers import RotatingFileHandler

    Path(log_dir).mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )
        )
    handlers.append(console_handler)

    # File handler with rotation — always JSON for machine parsing
    file_handler = RotatingFileHandler(
        f"{log_dir}/hunter.log",
        maxBytes=10_000_000,  # 10MB
        backupCount=5,
    )
    file_handler.setFormatter(JSONFormatter())
    file_handler.addFilter(RedactingFilter())
    handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=handlers,
        force=True,
    )
