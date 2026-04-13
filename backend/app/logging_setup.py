"""Centralized logging setup."""
from __future__ import annotations

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JsonLikeFormatter(logging.Formatter):
    """Format logs as compact JSON-like strings without extra dependencies."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging() -> None:
    """Configure root logger once for API and background services."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    level_name = (os.getenv("LOG_LEVEL") or "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    formatter = JsonLikeFormatter(datefmt="%Y-%m-%dT%H:%M:%S")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.setLevel(level)
    root_logger.addHandler(stream_handler)

    log_file = (os.getenv("LOG_FILE") or "").strip()
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(path, maxBytes=10 * 1024 * 1024, backupCount=5)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
